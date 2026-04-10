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


def edge_decay_over_time(conn: duckdb.DuckDBPyConnection) -> list[dict]:
    """Track how edge changes for the same contract across consecutive runs.

    This answers the exit-logic question: "After we identify an edge, how fast
    does it disappear?"

    How it works:
    ─────────────
    Each pipeline run evaluates the same contracts. For example:

        Run 1 (8am):  KXCLOSEHORMUZ → BUY_NO, edge = +12%
        Run 2 (8pm):  KXCLOSEHORMUZ → BUY_NO, edge = +8%    ← edge shrank 4%
        Run 3 (next): KXCLOSEHORMUZ → HOLD,   edge = +3%    ← edge shrank 9% total

    This function pairs consecutive signals for the same contract and computes:
    - edge_change: how much edge moved between runs (negative = decayed)
    - hours_between: time gap between observations
    - decay_rate: edge change per hour (cents/hour)

    Why this matters for exit logic:
    ────────────────────────────────
    If edge typically decays 5+ cents within 12 hours, selling before settlement
    *might* be worth the ~5.5 cent round-trip cost. If edge decays slowly (1-2
    cents/day), holding to settlement is strictly better because settlement is free.

    The breakeven threshold is ~5.5 cents of edge decay (at mid-range prices).
    If avg_edge_change is smaller than that, exit trading loses money to fees.
    """
    rows = conn.execute("""
        WITH ordered_signals AS (
            SELECT
                contract_ticker,
                run_id,
                created_at,
                effective_edge,
                signal,
                model_id,
                entry_price,
                market_yes_price,
                ROW_NUMBER() OVER (
                    PARTITION BY contract_ticker, model_id
                    ORDER BY created_at
                ) AS seq
            FROM signal_ledger
            WHERE signal IN ('BUY_YES', 'BUY_NO', 'HOLD')
              AND effective_edge IS NOT NULL
        ),
        paired AS (
            SELECT
                a.contract_ticker,
                a.model_id,
                a.run_id AS run_a,
                b.run_id AS run_b,
                a.created_at AS time_a,
                b.created_at AS time_b,
                a.effective_edge AS edge_a,
                b.effective_edge AS edge_b,
                a.signal AS signal_a,
                b.signal AS signal_b,
                b.effective_edge - a.effective_edge AS edge_change,
                EXTRACT(EPOCH FROM (b.created_at - a.created_at)) / 3600.0 AS hours_between
            FROM ordered_signals a
            JOIN ordered_signals b
              ON a.contract_ticker = b.contract_ticker
              AND a.model_id = b.model_id
              AND b.seq = a.seq + 1
        )
        SELECT
            contract_ticker,
            model_id,
            run_a,
            run_b,
            time_a,
            time_b,
            edge_a,
            edge_b,
            signal_a,
            signal_b,
            edge_change,
            hours_between,
            CASE WHEN hours_between > 0
                 THEN edge_change / hours_between
                 ELSE NULL END AS decay_rate_per_hour
        FROM paired
        ORDER BY contract_ticker, model_id, time_a
    """).fetchall()

    return [
        {
            "contract_ticker": r[0],
            "model_id": r[1],
            "run_a": r[2],
            "run_b": r[3],
            "time_a": r[4],
            "time_b": r[5],
            "edge_a": float(r[6]),
            "edge_b": float(r[7]),
            "signal_a": r[8],
            "signal_b": r[9],
            "edge_change": float(r[10]),
            "hours_between": float(r[11]) if r[11] else None,
            "decay_rate_per_hour": float(r[12]) if r[12] else None,
        }
        for r in rows
    ]


def edge_decay_summary(conn: duckdb.DuckDBPyConnection) -> dict:
    """Aggregate edge decay stats to answer: should we build exit logic?

    Returns a dict with:
    - n_pairs: how many consecutive signal pairs were analyzed
    - avg_edge_change: mean edge change (negative = decay). Compare to -0.055
      (the round-trip cost threshold). If avg decay is smaller, exits lose money.
    - pct_decayed_past_threshold: % of pairs where edge decayed > 5.5 cents.
      This is the fraction of positions where exit *might* have been profitable.
    - avg_hours_between: typical time between observations
    - verdict: human-readable recommendation
    """
    pairs = edge_decay_over_time(conn)
    if not pairs:
        return {
            "n_pairs": 0,
            "avg_edge_change": None,
            "pct_decayed_past_threshold": None,
            "avg_hours_between": None,
            "verdict": "No data yet. Need 2+ runs with overlapping contracts.",
        }

    n = len(pairs)
    avg_change = sum(p["edge_change"] for p in pairs) / n
    threshold = 0.055  # round-trip cost at mid-range prices
    decayed_past = sum(1 for p in pairs if p["edge_change"] < -threshold) / n
    hours = [p["hours_between"] for p in pairs if p["hours_between"]]
    avg_hours = sum(hours) / len(hours) if hours else None

    if decayed_past > 0.20 and avg_change < -0.03:
        verdict = (
            f"MAYBE: {decayed_past:.0%} of edges decayed past 5.5c threshold. "
            f"Avg decay {avg_change:+.1%}/observation. Worth investigating exit logic."
        )
    else:
        verdict = (
            f"NO: Only {decayed_past:.0%} of edges decayed past 5.5c threshold. "
            f"Avg decay {avg_change:+.1%}/observation. Hold to settlement is better."
        )

    return {
        "n_pairs": n,
        "avg_edge_change": avg_change,
        "pct_decayed_past_threshold": decayed_past,
        "avg_hours_between": avg_hours,
        "verdict": verdict,
    }


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

    lines.append("--- EDGE DECAY (by entry size) ---")
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

    lines.append("--- EDGE DECAY (over time, exit-logic feasibility) ---")
    summary = edge_decay_summary(conn)
    lines.append(f"  Observation pairs:       {summary['n_pairs']}")
    if summary["avg_edge_change"] is not None:
        lines.append(f"  Avg edge change/obs:     {summary['avg_edge_change']:+.3f}")
        lines.append(f"  Decayed past 5.5c:       {summary['pct_decayed_past_threshold']:.0%}")
        lines.append(f"  Avg hours between runs:  {summary['avg_hours_between']:.1f}h" if summary["avg_hours_between"] else "  Avg hours between runs:  --")
    lines.append(f"  Verdict: {summary['verdict']}")
    lines.append("")

    return "\n".join(lines)
