"""Calibration analysis queries for prediction accuracy assessment.

Provides three SQL-based analyses against signal_ledger and prediction_log:
1. Hit rate by proxy class -- accuracy grouped by DIRECT/NEAR_PROXY/LOOSE_PROXY
2. Calibration curve -- predicted vs actual probability across 5 buckets
3. Edge decay -- realized P&L and hit rate by edge size bucket

All queries are literal SQL (no user input) against local DuckDB.
A 7-day minimum data guard prevents premature analysis.
"""

from __future__ import annotations

import logging

import duckdb

logger = logging.getLogger(__name__)


def hit_rate_by_proxy_class(conn: duckdb.DuckDBPyConnection) -> list[dict]:
    """Return hit rate grouped by proxy class for resolved signals.

    Returns:
        List of dicts with keys: proxy_class, total, correct, hit_rate.
    """
    rows = conn.execute("""
        SELECT
            proxy_class,
            COUNT(*) AS total,
            SUM(CASE WHEN model_was_correct THEN 1 ELSE 0 END) AS correct,
            ROUND(SUM(CASE WHEN model_was_correct THEN 1 ELSE 0 END)::DOUBLE / COUNT(*), 3) AS hit_rate
        FROM signal_ledger
        WHERE model_was_correct IS NOT NULL
        GROUP BY proxy_class
        ORDER BY proxy_class
    """).fetchall()

    return [
        {
            "proxy_class": row[0],
            "total": int(row[1]),
            "correct": int(row[2]),
            "hit_rate": float(row[3]),
        }
        for row in rows
    ]


def calibration_curve(conn: duckdb.DuckDBPyConnection) -> list[dict]:
    """Return calibration curve with 5 probability buckets.

    Buckets: 0-20%, 20-40%, 40-60%, 60-80%, 80-100%.

    Returns:
        List of dicts with keys: bucket, n, avg_predicted, actual_rate.
    """
    rows = conn.execute("""
        SELECT
            CASE
                WHEN model_probability < 0.2 THEN '0-20%'
                WHEN model_probability < 0.4 THEN '20-40%'
                WHEN model_probability < 0.6 THEN '40-60%'
                WHEN model_probability < 0.8 THEN '60-80%'
                ELSE '80-100%'
            END AS bucket,
            COUNT(*) AS n,
            ROUND(AVG(model_probability), 3) AS avg_predicted,
            ROUND(AVG(CASE WHEN model_was_correct THEN 1.0 ELSE 0.0 END), 3) AS actual_rate
        FROM signal_ledger
        WHERE model_was_correct IS NOT NULL
        GROUP BY bucket
        ORDER BY bucket
    """).fetchall()

    return [
        {
            "bucket": row[0],
            "n": int(row[1]),
            "avg_predicted": float(row[2]),
            "actual_rate": float(row[3]),
        }
        for row in rows
    ]


def edge_decay(conn: duckdb.DuckDBPyConnection) -> list[dict]:
    """Return edge decay analysis by edge size bucket.

    Buckets: <5%, 5-10%, 10-15%, 15%+.

    Returns:
        List of dicts with keys: edge_bucket, n, avg_edge, avg_pnl, hit_rate.
    """
    rows = conn.execute("""
        SELECT
            CASE
                WHEN ABS(effective_edge) < 0.05 THEN '<5%'
                WHEN ABS(effective_edge) < 0.10 THEN '5-10%'
                WHEN ABS(effective_edge) < 0.15 THEN '10-15%'
                ELSE '15%+'
            END AS edge_bucket,
            COUNT(*) AS n,
            ROUND(AVG(ABS(effective_edge)), 3) AS avg_edge,
            ROUND(AVG(realized_pnl), 4) AS avg_pnl,
            ROUND(AVG(CASE WHEN model_was_correct THEN 1.0 ELSE 0.0 END), 3) AS hit_rate
        FROM signal_ledger
        WHERE realized_pnl IS NOT NULL
        GROUP BY edge_bucket
        ORDER BY edge_bucket
    """).fetchall()

    return [
        {
            "edge_bucket": row[0],
            "n": int(row[1]),
            "avg_edge": float(row[2]),
            "avg_pnl": float(row[3]),
            "hit_rate": float(row[4]),
        }
        for row in rows
    ]


def _check_minimum_data(conn: duckdb.DuckDBPyConnection, min_days: int = 7) -> tuple[bool, str]:
    """Check whether there is enough prediction data for calibration.

    Requires at least min_days between first and last prediction.

    Returns:
        Tuple of (sufficient: bool, message: str).
    """
    row = conn.execute(
        "SELECT MIN(created_at) AS first, MAX(created_at) AS last, COUNT(*) AS total FROM prediction_log"
    ).fetchone()

    if row is None or row[2] == 0:
        return (False, "No prediction data found")

    first, last, total = row[0], row[1], int(row[2])
    days_span = (last - first).days

    if days_span < min_days:
        return (False, f"Insufficient data: {days_span} days of predictions (minimum {min_days} required)")

    return (True, f"{total} predictions over {days_span} days")


def calibration_report(conn: duckdb.DuckDBPyConnection) -> str:
    """Generate a formatted calibration report for CLI output.

    Checks the 7-day minimum data guard before running queries.
    Returns the report as a formatted string.
    """
    sufficient, data_msg = _check_minimum_data(conn)
    if not sufficient:
        return data_msg

    lines = [
        "=== PARALLAX CALIBRATION REPORT ===",
        f"Data: {data_msg}",
        "",
    ]

    # Hit rate by proxy class
    lines.append("--- HIT RATE BY PROXY CLASS ---")
    hr_data = hit_rate_by_proxy_class(conn)
    if hr_data:
        lines.append(f"{'Proxy Class':<15} {'Total':>5} {'Correct':>7} {'Hit Rate':>8}")
        for row in hr_data:
            lines.append(
                f"{row['proxy_class']:<15} {row['total']:>5} {row['correct']:>7} {row['hit_rate']:>8.3f}"
            )
    else:
        lines.append("No resolved signals yet.")
    lines.append("")

    # Calibration curve
    lines.append("--- CALIBRATION CURVE ---")
    cc_data = calibration_curve(conn)
    if cc_data:
        lines.append(f"{'Bucket':<10} {'N':>5} {'Avg Predicted':>12} {'Actual Rate':>11}")
        for row in cc_data:
            lines.append(
                f"{row['bucket']:<10} {row['n']:>5} {row['avg_predicted']:>12.3f} {row['actual_rate']:>11.3f}"
            )
    else:
        lines.append("No resolved signals yet.")
    lines.append("")

    # Edge decay
    lines.append("--- EDGE DECAY ---")
    ed_data = edge_decay(conn)
    if ed_data:
        lines.append(f"{'Bucket':<10} {'N':>5} {'Avg Edge':>9} {'Avg PnL':>9} {'Hit Rate':>8}")
        for row in ed_data:
            lines.append(
                f"{row['edge_bucket']:<10} {row['n']:>5} {row['avg_edge']:>9.3f} {row['avg_pnl']:>9.4f} {row['hit_rate']:>8.3f}"
            )
    else:
        lines.append("No resolved signals yet.")
    lines.append("")

    return "\n".join(lines)
