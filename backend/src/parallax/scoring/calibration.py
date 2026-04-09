"""Signal-quality analysis over counterfactual outcomes, not traded P&L."""

from __future__ import annotations

import logging

import duckdb

logger = logging.getLogger(__name__)


def hit_rate_by_proxy_class(conn: duckdb.DuckDBPyConnection) -> list[dict]:
    rows = conn.execute("""
        SELECT
            proxy_class,
            COUNT(*) AS total,
            SUM(CASE WHEN model_was_correct THEN 1 ELSE 0 END) AS correct,
            ROUND(SUM(CASE WHEN model_was_correct THEN 1 ELSE 0 END)::DOUBLE / COUNT(*), 3) AS hit_rate
        FROM signal_quality_evaluation
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


def calibration_curve(
    conn: duckdb.DuckDBPyConnection,
    model_id: str | None = None,
) -> list[dict]:
    where_clause = "WHERE model_was_correct IS NOT NULL"
    params: list = []
    if model_id is not None:
        where_clause += " AND model_id = ?"
        params.append(model_id)

    rows = conn.execute(f"""
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
        FROM signal_quality_evaluation
        {where_clause}
        GROUP BY bucket
        ORDER BY bucket
    """, params).fetchall()

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
            ROUND(AVG(counterfactual_pnl), 4) AS avg_counterfactual_pnl,
            ROUND(AVG(CASE WHEN model_was_correct THEN 1.0 ELSE 0.0 END), 3) AS hit_rate
        FROM signal_quality_evaluation
        WHERE counterfactual_pnl IS NOT NULL
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


def _check_minimum_data(
    conn: duckdb.DuckDBPyConnection,
    min_days: int = 7,
) -> tuple[bool, str]:
    row = conn.execute(
        """
        SELECT MIN(created_at) AS first, MAX(created_at) AS last, COUNT(*) AS total
        FROM prediction_log
        """
    ).fetchone()

    if row is None or row[2] == 0:
        return False, "No prediction data found"

    first, last, total = row[0], row[1], int(row[2])
    days_span = (last - first).days
    if days_span < min_days:
        return False, f"Insufficient data: {days_span} days of predictions (minimum {min_days} required)"
    return True, f"{total} predictions over {days_span} days"


def calibration_report(conn: duckdb.DuckDBPyConnection) -> str:
    sufficient, data_msg = _check_minimum_data(conn)
    if not sufficient:
        return data_msg

    lines = [
        "=== PARALLAX SIGNAL-QUALITY REPORT ===",
        "Counterfactual outcomes use executable entry prices but include untraded signals.",
        f"Data: {data_msg}",
        "",
    ]

    lines.append("--- HIT RATE BY PROXY CLASS ---")
    hr_data = hit_rate_by_proxy_class(conn)
    if hr_data:
        lines.append(f"{'Proxy Class':<15} {'Total':>5} {'Correct':>7} {'Hit Rate':>8}")
        for row in hr_data:
            lines.append(
                f"{row['proxy_class']:<15} {row['total']:>5} {row['correct']:>7} {row['hit_rate']:>8.3f}"
            )
    else:
        lines.append("No resolved signal-quality rows yet.")
    lines.append("")

    lines.append("--- CALIBRATION CURVE ---")
    curve = calibration_curve(conn)
    if curve:
        lines.append(f"{'Bucket':<10} {'N':>5} {'Avg Predicted':>12} {'Actual Rate':>11}")
        for row in curve:
            lines.append(
                f"{row['bucket']:<10} {row['n']:>5} {row['avg_predicted']:>12.3f} {row['actual_rate']:>11.3f}"
            )
    else:
        lines.append("No resolved signal-quality rows yet.")
    lines.append("")

    lines.append("--- EDGE DECAY ---")
    decay = edge_decay(conn)
    if decay:
        lines.append(f"{'Bucket':<10} {'N':>5} {'Avg Edge':>9} {'Avg CfPnL':>11} {'Hit Rate':>8}")
        for row in decay:
            lines.append(
                f"{row['edge_bucket']:<10} {row['n']:>5} {row['avg_edge']:>9.3f} {row['avg_pnl']:>11.4f} {row['hit_rate']:>8.3f}"
            )
    else:
        lines.append("No resolved signal-quality rows yet.")
    lines.append("")

    return "\n".join(lines)
