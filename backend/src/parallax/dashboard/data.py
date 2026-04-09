"""Reusable data layer for dashboard and future API endpoints.

All functions take a DuckDB connection and return plain dicts/lists.
No Streamlit or framework dependencies -- pure data queries.
Reuses calibration.py functions per D-07 (no duplicate SQL).
"""

from __future__ import annotations

import logging

import duckdb

from parallax.scoring.calibration import (
    calibration_curve,
    edge_decay,
    hit_rate_by_proxy_class,
)

logger = logging.getLogger(__name__)


def get_latest_brief(
    conn: duckdb.DuckDBPyConnection, limit: int = 1,
) -> list[dict]:
    """Return latest prediction_log entries grouped by most recent run_id.

    Args:
        conn: DuckDB connection.
        limit: Number of distinct runs to return (default: 1 = latest run only).

    Returns:
        List of dicts with model_id, probability, direction, confidence, reasoning, created_at.
    """
    rows = conn.execute(
        """
        SELECT model_id, probability, direction, confidence, reasoning, created_at
        FROM prediction_log
        WHERE run_id = (
            SELECT run_id FROM prediction_log
            ORDER BY created_at DESC
            LIMIT 1
        )
        ORDER BY model_id
        """,
    ).fetchall()

    return [
        {
            "model_id": row[0],
            "probability": float(row[1]),
            "direction": row[2],
            "confidence": float(row[3]),
            "reasoning": row[4],
            "created_at": row[5],
        }
        for row in rows
    ]


def get_calibration_data(conn: duckdb.DuckDBPyConnection) -> dict:
    """Return calibration data from existing calibration.py queries.

    Returns:
        Dict with keys: hit_rate, calibration_curve, edge_decay.
    """
    return {
        "hit_rate": hit_rate_by_proxy_class(conn),
        "calibration_curve": calibration_curve(conn),
        "edge_decay": edge_decay(conn),
    }


def get_signal_history(
    conn: duckdb.DuckDBPyConnection, limit: int = 100,
) -> list[dict]:
    """Return recent signals from signal_ledger ordered by created_at DESC.

    Args:
        conn: DuckDB connection.
        limit: Max signals to return.

    Returns:
        List of dicts with signal fields.
    """
    rows = conn.execute(
        """
        SELECT signal_id, created_at, model_id, contract_ticker, proxy_class,
               effective_edge, signal, tradeability_status, execution_status,
               entry_price, entry_price_kind, resolution_price, counterfactual_pnl,
               model_was_correct, traded
        FROM signal_ledger
        ORDER BY created_at DESC
        LIMIT ?
        """,
        [limit],
    ).fetchall()

    return [
        {
            "signal_id": row[0],
            "created_at": row[1],
            "model_id": row[2],
            "contract_ticker": row[3],
            "proxy_class": row[4],
            "effective_edge": float(row[5]) if row[5] is not None else 0.0,
            "signal": row[6],
            "tradeability_status": row[7],
            "execution_status": row[8],
            "entry_price": float(row[9]) if row[9] is not None else None,
            "entry_price_kind": row[10],
            "resolution_price": float(row[11]) if row[11] is not None else None,
            "counterfactual_pnl": float(row[12]) if row[12] is not None else None,
            "model_was_correct": row[13],
            "traded": bool(row[14]) if row[14] is not None else False,
        }
        for row in rows
    ]


def get_market_prices(
    conn: duckdb.DuckDBPyConnection, limit: int = 50,
) -> list[dict]:
    """Return latest market_prices table entries.

    Args:
        conn: DuckDB connection.
        limit: Max entries to return.

    Returns:
        List of dicts with ticker, source, yes_price, no_price, volume, fetched_at.
    """
    rows = conn.execute(
        """
        SELECT ticker, source, best_yes_bid, best_yes_ask, best_no_bid, best_no_ask,
               yes_price, no_price, derived_price_kind, volume, fetched_at, data_environment
        FROM market_prices
        ORDER BY fetched_at DESC
        LIMIT ?
        """,
        [limit],
    ).fetchall()

    return [
        {
            "ticker": row[0],
            "source": row[1],
            "best_yes_bid": float(row[2]) if row[2] is not None else None,
            "best_yes_ask": float(row[3]) if row[3] is not None else None,
            "best_no_bid": float(row[4]) if row[4] is not None else None,
            "best_no_ask": float(row[5]) if row[5] is not None else None,
            "yes_price": float(row[6]) if row[6] is not None else None,
            "no_price": float(row[7]) if row[7] is not None else None,
            "derived_price_kind": row[8],
            "volume": float(row[9]) if row[9] is not None else None,
            "fetched_at": row[10],
            "data_environment": row[11],
        }
        for row in rows
    ]


def get_trade_journal(
    conn: duckdb.DuckDBPyConnection,
    limit: int = 100,
) -> list[dict]:
    rows = conn.execute(
        """
        SELECT
            o.order_id,
            o.signal_id,
            o.ticker,
            o.side,
            o.quantity,
            o.intended_price,
            o.status,
            o.submitted_at,
            o.accepted_at,
            o.rejected_at,
            o.cancelled_at,
            o.avg_fill_price,
            p.position_id,
            p.status,
            p.realized_pnl,
            o.venue_environment
        FROM trade_orders AS o
        LEFT JOIN trade_positions AS p
          ON p.signal_id = o.signal_id
        ORDER BY o.submitted_at DESC
        LIMIT ?
        """,
        [limit],
    ).fetchall()
    return [
        {
            "order_id": row[0],
            "signal_id": row[1],
            "ticker": row[2],
            "side": row[3],
            "quantity": row[4],
            "intended_price": float(row[5]) if row[5] is not None else None,
            "order_status": row[6],
            "submitted_at": row[7],
            "accepted_at": row[8],
            "rejected_at": row[9],
            "cancelled_at": row[10],
            "avg_fill_price": float(row[11]) if row[11] is not None else None,
            "position_id": row[12],
            "position_status": row[13],
            "realized_pnl": float(row[14]) if row[14] is not None else None,
            "venue_environment": row[15],
        }
        for row in rows
    ]
