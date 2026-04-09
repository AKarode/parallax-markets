"""Resolution checker -- polls Kalshi for settled contracts, backfills signal_ledger.

Closes the feedback loop: prediction -> signal -> trade -> resolution -> evaluation.
Queries signal_ledger for unresolved BUY_YES/BUY_NO signals, checks settlement status
via Kalshi production API, and backfills resolution_price, realized_pnl, model_was_correct.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone

import duckdb

from parallax.markets.kalshi import KalshiClient

logger = logging.getLogger(__name__)


async def _check_market_resolution(
    client: KalshiClient, ticker: str,
) -> dict | None:
    """Check if a Kalshi market has settled.

    Args:
        client: Kalshi API client (must use production URL).
        ticker: Market ticker to check.

    Returns:
        Resolution dict if settled, None if still active.
    """
    data = await client._request("GET", f"/markets/{ticker}")
    market = data.get("market", data)

    status = market.get("status", "")
    if status not in ("determined", "finalized"):
        return None

    result = market.get("result", "")
    settlement_value = market.get("settlement_value", "0")
    settlement_ts = market.get("settlement_ts")

    # Validate settlement_value is numeric and in range 0.0-1.0 (T-02-04)
    try:
        resolution_price = float(settlement_value)
    except (TypeError, ValueError):
        logger.warning(
            "Invalid settlement_value for %s: %r", ticker, settlement_value,
        )
        return None

    if not (0.0 <= resolution_price <= 1.0):
        logger.warning(
            "Settlement value out of range for %s: %s", ticker, resolution_price,
        )
        return None

    return {
        "status": status,
        "result": result,
        "resolution_price": resolution_price,
        "settled_at": settlement_ts,
    }


def _backfill_signal(
    conn: duckdb.DuckDBPyConnection,
    ticker: str,
    resolution_price: float,
    settled_at: str | datetime,
) -> int:
    """Backfill signal_ledger rows with resolution outcome.

    Updates only rows where resolution_price IS NULL to prevent double-update (T-02-05).

    P&L formulas:
        BUY_YES: resolution_price - market_yes_price
        BUY_NO:  (1.0 - resolution_price) - market_no_price
        HOLD/REFUSED: NULL

    model_was_correct:
        BUY_YES and resolution_price > 0.5: True
        BUY_NO and resolution_price <= 0.5: True
        Otherwise: False

    Args:
        conn: DuckDB connection.
        ticker: Contract ticker to backfill.
        resolution_price: Settlement price (0.0 or 1.0 for binary).
        settled_at: Settlement timestamp.

    Returns:
        Number of rows updated.
    """
    if isinstance(settled_at, datetime):
        resolved_at_str = settled_at.isoformat()
    elif isinstance(settled_at, (int, float)):
        # Unix epoch timestamp from Kalshi API
        resolved_at_str = datetime.fromtimestamp(
            settled_at, tz=timezone.utc,
        ).isoformat()
    else:
        resolved_at_str = str(settled_at)

    # Use parameterized SQL with CASE WHEN for signal-dependent logic (T-02-05)
    result = conn.execute(
        """
        UPDATE signal_ledger
        SET resolution_price = ?,
            resolved_at = ?,
            realized_pnl = CASE
                WHEN signal = 'BUY_YES' THEN ? - market_yes_price
                WHEN signal = 'BUY_NO' THEN (1.0 - ?) - market_no_price
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
        [resolution_price, resolved_at_str,
         resolution_price, resolution_price,
         resolution_price, resolution_price,
         resolution_price, resolution_price,
         ticker],
    )

    # DuckDB returns rowcount via fetchone on UPDATE
    # Use a follow-up query to count affected rows
    count = conn.execute(
        """
        SELECT COUNT(*) FROM signal_ledger
        WHERE contract_ticker = ?
          AND resolution_price IS NOT NULL
          AND resolved_at = ?
        """,
        [ticker, resolved_at_str],
    ).fetchone()[0]

    return count


async def check_resolutions(
    conn: duckdb.DuckDBPyConnection,
    kalshi_client: KalshiClient,
) -> list[dict]:
    """Poll Kalshi for settled contracts and backfill signal_ledger.

    Queries signal_ledger for distinct contract tickers with unresolved
    BUY_YES/BUY_NO signals, checks each against Kalshi production API,
    and backfills resolution data for any that have settled.

    Args:
        conn: DuckDB connection.
        kalshi_client: Kalshi API client (must use production URL).

    Returns:
        List of resolution dicts for contracts that were resolved.
    """
    # Find distinct tickers with unresolved actionable signals
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

    logger.info("Checking resolution status for %d ticker(s)", len(tickers))

    results = []
    for ticker in tickers:
        try:
            resolution = await _check_market_resolution(kalshi_client, ticker)
            if resolution is None:
                logger.debug("Ticker %s still active", ticker)
                continue

            n = _backfill_signal(
                conn, ticker,
                resolution["resolution_price"],
                resolution["settled_at"],
            )
            resolution["ticker"] = ticker
            resolution["signals_updated"] = n
            results.append(resolution)
            logger.info(
                "Resolved %s: %s, backfilled %d signal(s)",
                ticker, resolution["result"], n,
            )
        except Exception:
            # T-02-07: Don't crash on individual API failures
            logger.warning("Failed to check resolution for %s", ticker, exc_info=True)
            continue

    return results
