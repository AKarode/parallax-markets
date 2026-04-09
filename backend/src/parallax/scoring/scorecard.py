"""Daily scorecard ETL — computes metrics across 5 categories and writes to daily_scorecard."""

from __future__ import annotations

import json
import logging
from datetime import date, datetime, timezone

import duckdb

logger = logging.getLogger(__name__)


def _upsert_metric(
    conn: duckdb.DuckDBPyConnection,
    score_date: str,
    metric_name: str,
    metric_value: float | None,
    dimensions: dict | None = None,
) -> None:
    conn.execute(
        """
        INSERT INTO daily_scorecard (score_date, metric_name, metric_value, dimensions, computed_at)
        VALUES (?, ?, ?, ?, ?)
        ON CONFLICT (score_date, metric_name) DO UPDATE
        SET metric_value = EXCLUDED.metric_value,
            dimensions = EXCLUDED.dimensions,
            computed_at = EXCLUDED.computed_at
        """,
        [
            score_date,
            metric_name,
            metric_value,
            json.dumps(dimensions) if dimensions else None,
            datetime.now(timezone.utc),
        ],
    )


def _compute_signal_quality(conn: duckdb.DuckDBPyConnection, score_date: str) -> list[dict]:
    metrics = []

    # Resolved signal volume
    row = conn.execute(
        """
        SELECT COUNT(*) FROM signal_quality_evaluation
        WHERE DATE(resolved_at) = ?
        """,
        [score_date],
    ).fetchone()
    resolved_volume = row[0] if row else 0
    metrics.append({"name": "signal_resolved_volume", "value": float(resolved_volume)})

    # Counterfactual mean PnL
    row = conn.execute(
        """
        SELECT AVG(counterfactual_pnl) FROM signal_quality_evaluation
        WHERE DATE(resolved_at) = ? AND counterfactual_pnl IS NOT NULL
        """,
        [score_date],
    ).fetchone()
    cf_pnl = row[0] if row and row[0] is not None else None
    metrics.append({"name": "signal_counterfactual_mean_pnl", "value": cf_pnl})

    # Counterfactual hit rate
    row = conn.execute(
        """
        SELECT AVG(CASE WHEN model_was_correct THEN 1.0 ELSE 0.0 END)
        FROM signal_quality_evaluation
        WHERE DATE(resolved_at) = ? AND model_was_correct IS NOT NULL
        """,
        [score_date],
    ).fetchone()
    hit_rate = row[0] if row and row[0] is not None else None
    metrics.append({"name": "signal_hit_rate", "value": hit_rate})

    # Brier score
    row = conn.execute(
        """
        SELECT AVG(
            POWER(model_probability - CASE WHEN model_was_correct THEN 1.0 ELSE 0.0 END, 2)
        )
        FROM signal_quality_evaluation
        WHERE DATE(resolved_at) = ? AND model_was_correct IS NOT NULL
        """,
        [score_date],
    ).fetchone()
    brier = row[0] if row and row[0] is not None else None
    metrics.append({"name": "signal_brier_score", "value": brier})

    # Calibration bucket gaps (max absolute gap)
    rows = conn.execute(
        """
        SELECT
            FLOOR(model_probability * 5) / 5 AS bucket,
            COUNT(*) AS n,
            AVG(model_probability) AS avg_predicted,
            AVG(CASE WHEN model_was_correct THEN 1.0 ELSE 0.0 END) AS actual_rate
        FROM signal_quality_evaluation
        WHERE model_was_correct IS NOT NULL
        GROUP BY bucket
        HAVING COUNT(*) >= 3
        ORDER BY bucket
        """,
    ).fetchall()
    if rows:
        max_gap = max(abs(r[2] - r[3]) for r in rows)
        metrics.append({"name": "signal_calibration_max_gap", "value": max_gap})
        bucket_details = [
            {"bucket": f"{r[0]:.0%}-{r[0]+0.2:.0%}", "n": r[1], "predicted": round(r[2], 3), "actual": round(r[3], 3)}
            for r in rows
        ]
        metrics.append({"name": "signal_calibration_buckets", "value": len(rows), "dims": {"buckets": bucket_details}})
    else:
        metrics.append({"name": "signal_calibration_max_gap", "value": None})

    # Edge-decay sanity (correlation between edge size and hit rate)
    rows = conn.execute(
        """
        SELECT
            CASE
                WHEN ABS(effective_edge) < 0.05 THEN '<5%'
                WHEN ABS(effective_edge) < 0.10 THEN '5-10%'
                WHEN ABS(effective_edge) < 0.15 THEN '10-15%'
                ELSE '15%+'
            END AS edge_bucket,
            COUNT(*) AS n,
            AVG(CASE WHEN model_was_correct THEN 1.0 ELSE 0.0 END) AS hit_rate
        FROM signal_quality_evaluation
        WHERE model_was_correct IS NOT NULL AND effective_edge IS NOT NULL
        GROUP BY edge_bucket
        """,
    ).fetchall()
    if rows:
        edge_detail = [{"bucket": r[0], "n": r[1], "hit_rate": round(r[2], 3)} for r in rows]
        metrics.append({"name": "signal_edge_decay", "value": len(rows), "dims": {"buckets": edge_detail}})

    # Tradeability funnel
    rows = conn.execute(
        """
        SELECT tradeability_status, COUNT(*) AS cnt
        FROM signal_ledger
        WHERE DATE(created_at) = ?
        GROUP BY tradeability_status
        """,
        [score_date],
    ).fetchall()
    funnel = {r[0]: r[1] for r in rows}
    total_signals = sum(funnel.values()) if funnel else 0
    metrics.append({"name": "signal_tradeability_funnel", "value": float(total_signals), "dims": funnel})

    return metrics


def _compute_execution_quality(conn: duckdb.DuckDBPyConnection, score_date: str) -> list[dict]:
    metrics = []

    # Orders attempted vs accepted
    row = conn.execute(
        """
        SELECT
            COUNT(*) AS attempted,
            SUM(CASE WHEN status NOT IN ('rejected', 'error') THEN 1 ELSE 0 END) AS accepted,
            SUM(CASE WHEN status = 'filled' THEN 1 ELSE 0 END) AS filled,
            SUM(CASE WHEN status = 'partially_filled' THEN 1 ELSE 0 END) AS partial
        FROM trade_orders
        WHERE DATE(submitted_at) = ?
        """,
        [score_date],
    ).fetchone()
    if row:
        attempted = row[0] or 0
        accepted = row[1] or 0
        filled = row[2] or 0
        partial = row[3] or 0
        metrics.append({"name": "exec_orders_attempted", "value": float(attempted)})
        metrics.append({"name": "exec_orders_accepted", "value": float(accepted)})
        fill_rate = (filled + partial) / attempted if attempted > 0 else None
        metrics.append({"name": "exec_fill_rate", "value": fill_rate})

    # Time-to-fill p50/p90
    rows = conn.execute(
        """
        SELECT
            EPOCH(last_update_at) - EPOCH(submitted_at) AS fill_seconds
        FROM trade_orders
        WHERE DATE(submitted_at) = ? AND status = 'filled'
          AND last_update_at IS NOT NULL
        ORDER BY fill_seconds
        """,
        [score_date],
    ).fetchall()
    if rows:
        times = sorted([r[0] for r in rows if r[0] is not None])
        if times:
            p50_idx = len(times) // 2
            p90_idx = min(int(len(times) * 0.9), len(times) - 1)
            metrics.append({"name": "exec_time_to_fill_p50", "value": times[p50_idx]})
            metrics.append({"name": "exec_time_to_fill_p90", "value": times[p90_idx]})

    # Slippage vs executable reference
    row = conn.execute(
        """
        SELECT AVG(avg_fill_price - executable_reference_price)
        FROM trade_orders
        WHERE DATE(submitted_at) = ? AND status = 'filled'
          AND avg_fill_price IS NOT NULL AND executable_reference_price IS NOT NULL
        """,
        [score_date],
    ).fetchone()
    slippage = row[0] if row and row[0] is not None else None
    metrics.append({"name": "exec_slippage_vs_reference", "value": slippage})

    # Fees per contract
    row = conn.execute(
        """
        SELECT
            CASE WHEN SUM(quantity) > 0
                 THEN SUM(fee_amount) / SUM(quantity)
                 ELSE NULL END
        FROM trade_fills
        WHERE DATE(filled_at) = ?
        """,
        [score_date],
    ).fetchone()
    fees_per = row[0] if row and row[0] is not None else None
    metrics.append({"name": "exec_fees_per_contract", "value": fees_per})

    return metrics


def _compute_portfolio_risk(conn: duckdb.DuckDBPyConnection, score_date: str) -> list[dict]:
    metrics = []

    # Gross exposure and concentration
    rows = conn.execute(
        """
        SELECT ticker, SUM(open_quantity * entry_price) AS notional
        FROM trade_positions
        WHERE status = 'open'
        GROUP BY ticker
        """,
    ).fetchall()
    gross = sum(r[1] for r in rows) if rows else 0.0
    max_ticker = max((r[1] for r in rows), default=0.0)
    concentration = max_ticker / gross if gross > 0 else 0.0
    metrics.append({"name": "risk_gross_exposure", "value": gross})
    metrics.append({"name": "risk_max_concentration", "value": concentration})

    # Daily realized PnL
    row = conn.execute(
        """
        SELECT SUM(realized_pnl)
        FROM trade_positions
        WHERE DATE(closed_at) = ? AND realized_pnl IS NOT NULL
        """,
        [score_date],
    ).fetchone()
    daily_pnl = row[0] if row and row[0] is not None else 0.0
    metrics.append({"name": "risk_daily_realized_pnl", "value": daily_pnl})

    # Loss-cap utilization (assumes $20 daily loss cap)
    loss_cap = 20.0
    utilization = max(0.0, -daily_pnl) / loss_cap if loss_cap > 0 else 0.0
    metrics.append({"name": "risk_loss_cap_utilization", "value": utilization})

    return metrics


def _compute_data_quality(conn: duckdb.DuckDBPyConnection, score_date: str) -> list[dict]:
    metrics = []

    # Executable quote coverage
    row = conn.execute(
        """
        SELECT
            AVG(CASE WHEN entry_price_is_executable THEN 1.0 ELSE 0.0 END)
        FROM signal_ledger
        WHERE DATE(created_at) = ? AND signal IN ('BUY_YES', 'BUY_NO')
        """,
        [score_date],
    ).fetchone()
    coverage = row[0] if row and row[0] is not None else None
    metrics.append({"name": "data_executable_quote_coverage", "value": coverage})

    # Quote staleness rate
    row = conn.execute(
        """
        SELECT
            AVG(CASE WHEN quote_is_stale THEN 1.0 ELSE 0.0 END)
        FROM signal_ledger
        WHERE DATE(created_at) = ?
        """,
        [score_date],
    ).fetchone()
    stale_rate = row[0] if row and row[0] is not None else None
    metrics.append({"name": "data_quote_staleness_rate", "value": stale_rate})

    # Market freshness (avg quote age)
    row = conn.execute(
        """
        SELECT AVG(quote_age_seconds)
        FROM signal_ledger
        WHERE DATE(created_at) = ? AND quote_age_seconds IS NOT NULL
        """,
        [score_date],
    ).fetchone()
    freshness = row[0] if row and row[0] is not None else None
    metrics.append({"name": "data_avg_quote_age_seconds", "value": freshness})

    return metrics


def _compute_ops_runtime(conn: duckdb.DuckDBPyConnection, score_date: str) -> list[dict]:
    metrics = []

    # Pipeline health
    row = conn.execute(
        """
        SELECT
            COUNT(*) AS total_runs,
            SUM(CASE WHEN status = 'completed' THEN 1 ELSE 0 END) AS successful,
            MAX(ended_at) AS latest_run
        FROM runs
        WHERE DATE(started_at) = ?
        """,
        [score_date],
    ).fetchone()
    if row:
        total, successful, latest = row
        metrics.append({"name": "ops_run_count", "value": float(total)})
        success_rate = successful / total if total > 0 else None
        metrics.append({"name": "ops_run_success_rate", "value": success_rate})
        if latest:
            age_hours = (datetime.now(timezone.utc) - latest).total_seconds() / 3600.0
            metrics.append({"name": "ops_latest_run_age_hours", "value": age_hours})

    # LLM cost
    row = conn.execute(
        """
        SELECT SUM(cost_usd)
        FROM llm_usage
        WHERE DATE(created_at) = ?
        """,
        [score_date],
    ).fetchone()
    llm_cost = row[0] if row and row[0] is not None else 0.0
    metrics.append({"name": "ops_llm_cost_usd", "value": llm_cost})

    # Alert count
    row = conn.execute(
        """
        SELECT COUNT(*)
        FROM ops_events
        WHERE DATE(created_at) = ? AND severity IN ('error', 'critical')
        """,
        [score_date],
    ).fetchone()
    alert_count = row[0] if row else 0
    metrics.append({"name": "ops_error_alert_count", "value": float(alert_count)})

    return metrics


def compute_daily_scorecard(
    conn: duckdb.DuckDBPyConnection,
    date_str: str | None = None,
) -> str:
    """Compute all scorecard metrics for a date and persist to daily_scorecard table."""
    if date_str is None:
        date_str = date.today().isoformat()

    all_metrics: list[dict] = []
    all_metrics.extend(_compute_signal_quality(conn, date_str))
    all_metrics.extend(_compute_execution_quality(conn, date_str))
    all_metrics.extend(_compute_portfolio_risk(conn, date_str))
    all_metrics.extend(_compute_data_quality(conn, date_str))
    all_metrics.extend(_compute_ops_runtime(conn, date_str))

    for metric in all_metrics:
        _upsert_metric(
            conn,
            date_str,
            metric["name"],
            metric.get("value"),
            metric.get("dims"),
        )

    # Check no-run-in-24h alert (TEL-04)
    row = conn.execute(
        """
        SELECT MAX(started_at) FROM runs
        """,
    ).fetchone()
    no_run_alert = False
    if row and row[0]:
        age_hours = (datetime.now(timezone.utc) - row[0]).total_seconds() / 3600.0
        if age_hours > 24:
            no_run_alert = True
            logger.warning("ALERT: No pipeline run in %.1f hours", age_hours)
    else:
        no_run_alert = True
        logger.warning("ALERT: No pipeline runs found at all")

    return _format_scorecard(date_str, all_metrics, no_run_alert)


def _format_scorecard(date_str: str, metrics: list[dict], no_run_alert: bool) -> str:
    lines = [
        "=" * 72,
        f"PARALLAX DAILY SCORECARD — {date_str}",
        "=" * 72,
        "",
    ]

    if no_run_alert:
        lines.append("*** ALERT: No pipeline run in 24+ hours ***")
        lines.append("")

    categories = [
        ("SIGNAL QUALITY", "signal_"),
        ("EXECUTION QUALITY", "exec_"),
        ("PORTFOLIO / RISK", "risk_"),
        ("DATA QUALITY", "data_"),
        ("OPS / RUNTIME", "ops_"),
    ]

    for cat_name, prefix in categories:
        lines.append(f"--- {cat_name} ---")
        lines.append("")
        cat_metrics = [m for m in metrics if m["name"].startswith(prefix)]
        for m in cat_metrics:
            val = m.get("value")
            if val is None:
                val_str = "N/A (insufficient data)"
            elif isinstance(val, float) and abs(val) < 1.0 and val != 0.0:
                val_str = f"{val:.4f}"
            else:
                val_str = f"{val}"
            label = m["name"].removeprefix(prefix).replace("_", " ").title()
            lines.append(f"  {label:<35} {val_str}")
        lines.append("")

    lines.append("=" * 72)
    return "\n".join(lines)
