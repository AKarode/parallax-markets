"""Resolution checker for signal-quality and traded-position backfills."""

from __future__ import annotations

import logging
from datetime import datetime, timezone

import duckdb

from parallax.markets.kalshi import KalshiClient

logger = logging.getLogger(__name__)


def _normalize_settled_at(value: str | datetime | int | float) -> str:
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, (int, float)):
        return datetime.fromtimestamp(float(value), tz=timezone.utc).isoformat()
    return str(value)


async def _check_market_resolution(
    client: KalshiClient,
    ticker: str,
) -> dict | None:
    data = await client._request("GET", f"/markets/{ticker}")
    market = data.get("market", data)

    status = market.get("status", "")
    if status not in ("determined", "finalized"):
        return None

    settlement_value = market.get("settlement_value", "0")
    try:
        resolution_price = float(settlement_value)
    except (TypeError, ValueError):
        logger.warning("Invalid settlement_value for %s: %r", ticker, settlement_value)
        return None

    if not (0.0 <= resolution_price <= 1.0):
        logger.warning("Settlement value out of range for %s: %s", ticker, resolution_price)
        return None

    return {
        "status": status,
        "result": market.get("result", ""),
        "resolution_price": resolution_price,
        "settled_at": market.get("settlement_ts"),
    }


def _backfill_signal(
    conn: duckdb.DuckDBPyConnection,
    ticker: str,
    resolution_price: float,
    settled_at: str | datetime | int | float,
) -> int:
    resolved_at = _normalize_settled_at(settled_at)
    conn.execute(
        """
        UPDATE signal_ledger
        SET resolution_price = ?,
            resolved_at = ?,
            realized_pnl = CASE
                WHEN signal = 'BUY_YES' AND entry_price IS NOT NULL THEN ? - entry_price
                WHEN signal = 'BUY_NO' AND entry_price IS NOT NULL THEN (1.0 - ?) - entry_price
                ELSE NULL
            END,
            counterfactual_pnl = CASE
                WHEN signal = 'BUY_YES' AND entry_price IS NOT NULL THEN ? - entry_price
                WHEN signal = 'BUY_NO' AND entry_price IS NOT NULL THEN (1.0 - ?) - entry_price
                ELSE NULL
            END,
            model_was_correct = CASE
                WHEN signal = 'BUY_YES' AND ? > 0.5 THEN true
                WHEN signal = 'BUY_NO' AND ? <= 0.5 THEN true
                WHEN signal IN ('BUY_YES', 'BUY_NO') THEN false
                ELSE NULL
            END,
            proxy_was_aligned = CASE
                WHEN signal = 'BUY_YES' AND ? > 0.5 THEN true
                WHEN signal = 'BUY_NO' AND ? <= 0.5 THEN true
                WHEN signal IN ('BUY_YES', 'BUY_NO') THEN false
                ELSE NULL
            END
        WHERE contract_ticker = ?
          AND resolution_price IS NULL
        """,
        [
            resolution_price,
            resolved_at,
            resolution_price,
            resolution_price,
            resolution_price,
            resolution_price,
            resolution_price,
            resolution_price,
            resolution_price,
            resolution_price,
            ticker,
        ],
    )

    count = conn.execute(
        """
        SELECT COUNT(*)
        FROM signal_ledger
        WHERE contract_ticker = ?
          AND resolved_at = ?
        """,
        [ticker, resolved_at],
    ).fetchone()[0]
    return int(count)


def _close_positions(
    conn: duckdb.DuckDBPyConnection,
    ticker: str,
    resolution_price: float,
    settled_at: str | datetime | int | float,
) -> int:
    resolved_at = _normalize_settled_at(settled_at)
    conn.execute(
        """
        UPDATE trade_positions
        SET resolution_price = ?,
            resolution_source = 'kalshi_settlement',
            settlement_price = CASE
                WHEN side = 'yes' THEN ?
                WHEN side = 'no' THEN (1.0 - ?)
                ELSE NULL
            END,
            exit_price = CASE
                WHEN side = 'yes' THEN ?
                WHEN side = 'no' THEN (1.0 - ?)
                ELSE NULL
            END,
            closed_at = ?,
            status = 'closed',
            open_quantity = 0,
            realized_pnl = CASE
                WHEN side = 'yes' THEN (? - entry_price) * quantity
                WHEN side = 'no' THEN ((1.0 - ?) - entry_price) * quantity
                ELSE NULL
            END,
            unrealized_pnl = NULL
        WHERE ticker = ?
          AND status = 'open'
        """,
        [
            resolution_price,
            resolution_price,
            resolution_price,
            resolution_price,
            resolution_price,
            resolved_at,
            resolution_price,
            resolution_price,
            ticker,
        ],
    )
    row = conn.execute(
        """
        SELECT COUNT(*)
        FROM trade_positions
        WHERE ticker = ?
          AND closed_at = ?
        """,
        [ticker, resolved_at],
    ).fetchone()
    return int(row[0]) if row else 0


async def check_resolutions(
    conn: duckdb.DuckDBPyConnection,
    kalshi_client: KalshiClient,
) -> list[dict]:
    rows = conn.execute(
        """
        SELECT DISTINCT contract_ticker
        FROM signal_ledger
        WHERE resolution_price IS NULL
          AND signal IN ('BUY_YES', 'BUY_NO')
        """
    ).fetchall()
    tickers = [row[0] for row in rows]
    if not tickers:
        logger.info("No unresolved signals to check")
        return []

    results = []
    for ticker in tickers:
        try:
            resolution = await _check_market_resolution(kalshi_client, ticker)
            if resolution is None:
                continue

            signal_updates = _backfill_signal(
                conn,
                ticker,
                resolution["resolution_price"],
                resolution["settled_at"],
            )
            position_updates = _close_positions(
                conn,
                ticker,
                resolution["resolution_price"],
                resolution["settled_at"],
            )

            resolution["ticker"] = ticker
            resolution["signals_updated"] = signal_updates
            resolution["positions_closed"] = position_updates
            results.append(resolution)
            logger.info(
                "Resolved %s: signal rows=%d, positions=%d",
                ticker,
                signal_updates,
                position_updates,
            )
        except Exception:
            logger.warning("Failed to check resolution for %s", ticker, exc_info=True)
            continue

    return results
