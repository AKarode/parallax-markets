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
               effective_edge, signal, resolution_price, realized_pnl, model_was_correct
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
            "effective_edge": float(row[5]),
            "signal": row[6],
            "resolution_price": float(row[7]) if row[7] is not None else None,
            "realized_pnl": float(row[8]) if row[8] is not None else None,
            "model_was_correct": row[9],
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
        SELECT ticker, source, yes_price, no_price, volume, fetched_at
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
            "yes_price": float(row[2]) if row[2] is not None else None,
            "no_price": float(row[3]) if row[3] is not None else None,
            "volume": float(row[4]) if row[4] is not None else None,
            "fetched_at": row[5],
        }
        for row in rows
    ]
