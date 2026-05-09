"""Backtest report generation with calibration and performance metrics.

Reads backtest results and produces:
- Hit rate per proxy class
- Brier score
- Calibration curve data (10 buckets)
- Edge-realized vs edge-predicted scatter
"""

from __future__ import annotations

import logging
import statistics
from dataclasses import dataclass, field

import duckdb

logger = logging.getLogger(__name__)


@dataclass
class CalibrationBucket:
    """A single bucket in the calibration curve."""

    bucket_index: int
    predicted_range_low: float
    predicted_range_high: float
    mean_predicted: float
    mean_actual: float
    count: int


@dataclass
class ProxyClassMetrics:
    """Performance metrics for a specific proxy class."""

    proxy_class: str
    total_predictions: int
    correct_predictions: int
    hit_rate: float
    brier_score: float
    mean_edge_predicted: float
    mean_edge_realized: float


@dataclass
class BacktestReport:
    """Complete backtest report with all metrics."""

    backtest_id: str
    total_predictions: int
    resolved_predictions: int
    overall_hit_rate: float
    overall_brier_score: float
    calibration_buckets: list[CalibrationBucket]
    proxy_class_metrics: list[ProxyClassMetrics]
    edge_scatter_data: list[tuple[float, float]]


def generate_backtest_report(
    conn: duckdb.DuckDBPyConnection,
    backtest_id: str,
) -> BacktestReport:
    """Generate a comprehensive report for a backtest run.

    Args:
        conn: DuckDB connection.
        backtest_id: ID of the backtest to report on.

    Returns:
        BacktestReport with all metrics.
    """
    total_predictions = _count_predictions(conn, backtest_id)
    resolved_predictions = _count_resolved_predictions(conn, backtest_id)

    hit_rate = _compute_overall_hit_rate(conn, backtest_id)
    brier_score = _compute_brier_score(conn, backtest_id)

    calibration_buckets = _compute_calibration_curve(conn, backtest_id, n_buckets=10)
    proxy_metrics = _compute_proxy_class_metrics(conn, backtest_id)
    edge_scatter = _get_edge_scatter_data(conn, backtest_id)

    return BacktestReport(
        backtest_id=backtest_id,
        total_predictions=total_predictions,
        resolved_predictions=resolved_predictions,
        overall_hit_rate=hit_rate,
        overall_brier_score=brier_score,
        calibration_buckets=calibration_buckets,
        proxy_class_metrics=proxy_metrics,
        edge_scatter_data=edge_scatter,
    )


def _count_predictions(conn: duckdb.DuckDBPyConnection, backtest_id: str) -> int:
    """Count total predictions in a backtest."""
    row = conn.execute(
        "SELECT COUNT(*) FROM backtest_predictions WHERE backtest_id = ?",
        [backtest_id],
    ).fetchone()
    return int(row[0]) if row else 0


def _count_resolved_predictions(conn: duckdb.DuckDBPyConnection, backtest_id: str) -> int:
    """Count predictions with resolution data."""
    row = conn.execute(
        """
        SELECT COUNT(*)
        FROM backtest_predictions
        WHERE backtest_id = ? AND resolution_price IS NOT NULL
        """,
        [backtest_id],
    ).fetchone()
    return int(row[0]) if row else 0


def _compute_overall_hit_rate(conn: duckdb.DuckDBPyConnection, backtest_id: str) -> float:
    """Compute overall hit rate (fraction of correct predictions)."""
    row = conn.execute(
        """
        SELECT
            COUNT(CASE WHEN was_correct THEN 1 END) AS correct,
            COUNT(*) AS total
        FROM backtest_predictions
        WHERE backtest_id = ? AND was_correct IS NOT NULL
        """,
        [backtest_id],
    ).fetchone()

    if row is None or row[1] == 0:
        return 0.0
    return float(row[0]) / float(row[1])


def _compute_brier_score(conn: duckdb.DuckDBPyConnection, backtest_id: str) -> float:
    """Compute Brier score (mean squared error of probability predictions).

    Brier = mean((predicted_probability - actual_outcome)^2)
    where actual_outcome is 1 if resolution_price >= 0.5, else 0.
    """
    rows = conn.execute(
        """
        SELECT predicted_probability, resolution_price
        FROM backtest_predictions
        WHERE backtest_id = ? AND resolution_price IS NOT NULL
        """,
        [backtest_id],
    ).fetchall()

    if not rows:
        return 0.0

    squared_errors = []
    for pred_prob, res_price in rows:
        actual = 1.0 if res_price >= 0.5 else 0.0
        squared_errors.append((pred_prob - actual) ** 2)

    return statistics.mean(squared_errors)


def _compute_calibration_curve(
    conn: duckdb.DuckDBPyConnection,
    backtest_id: str,
    n_buckets: int = 10,
) -> list[CalibrationBucket]:
    """Compute calibration curve data (predicted vs actual by bucket).

    Divides predictions into n_buckets based on predicted probability,
    and computes mean predicted and mean actual for each bucket.
    """
    rows = conn.execute(
        """
        SELECT predicted_probability, resolution_price
        FROM backtest_predictions
        WHERE backtest_id = ? AND resolution_price IS NOT NULL
        ORDER BY predicted_probability
        """,
        [backtest_id],
    ).fetchall()

    if not rows:
        return []

    bucket_size = 1.0 / n_buckets
    buckets: list[CalibrationBucket] = []

    for i in range(n_buckets):
        low = i * bucket_size
        high = (i + 1) * bucket_size

        bucket_preds = [
            (pred, 1.0 if res >= 0.5 else 0.0)
            for pred, res in rows
            if low <= pred < high or (i == n_buckets - 1 and pred == 1.0)
        ]

        if bucket_preds:
            mean_pred = statistics.mean(p for p, _ in bucket_preds)
            mean_actual = statistics.mean(a for _, a in bucket_preds)
            count = len(bucket_preds)
        else:
            mean_pred = (low + high) / 2
            mean_actual = 0.0
            count = 0

        buckets.append(
            CalibrationBucket(
                bucket_index=i,
                predicted_range_low=low,
                predicted_range_high=high,
                mean_predicted=mean_pred,
                mean_actual=mean_actual,
                count=count,
            )
        )

    return buckets


def _compute_proxy_class_metrics(
    conn: duckdb.DuckDBPyConnection,
    backtest_id: str,
) -> list[ProxyClassMetrics]:
    """Compute performance metrics per proxy class."""
    rows = conn.execute(
        """
        SELECT
            cpm.proxy_class,
            COUNT(*) AS total,
            SUM(CASE WHEN bp.was_correct THEN 1 ELSE 0 END) AS correct,
            AVG(bp.edge_predicted) AS mean_edge_predicted,
            AVG(bp.edge_realized) AS mean_edge_realized
        FROM backtest_predictions bp
        JOIN contract_proxy_map cpm
            ON bp.contract_ticker = cpm.ticker
        WHERE bp.backtest_id = ?
          AND bp.resolution_price IS NOT NULL
        GROUP BY cpm.proxy_class
        """,
        [backtest_id],
    ).fetchall()

    metrics = []
    for proxy_class, total, correct, mean_edge_pred, mean_edge_real in rows:
        hit_rate = correct / total if total > 0 else 0.0

        proxy_rows = conn.execute(
            """
            SELECT bp.predicted_probability, bp.resolution_price
            FROM backtest_predictions bp
            JOIN contract_proxy_map cpm ON bp.contract_ticker = cpm.ticker
            WHERE bp.backtest_id = ?
              AND cpm.proxy_class = ?
              AND bp.resolution_price IS NOT NULL
            """,
            [backtest_id, proxy_class],
        ).fetchall()

        squared_errors = [
            (p - (1.0 if r >= 0.5 else 0.0)) ** 2
            for p, r in proxy_rows
        ]
        brier = statistics.mean(squared_errors) if squared_errors else 0.0

        metrics.append(
            ProxyClassMetrics(
                proxy_class=proxy_class,
                total_predictions=total,
                correct_predictions=correct,
                hit_rate=hit_rate,
                brier_score=brier,
                mean_edge_predicted=mean_edge_pred or 0.0,
                mean_edge_realized=mean_edge_real or 0.0,
            )
        )

    return metrics


def _get_edge_scatter_data(
    conn: duckdb.DuckDBPyConnection,
    backtest_id: str,
) -> list[tuple[float, float]]:
    """Get edge-predicted vs edge-realized data for scatter plot."""
    rows = conn.execute(
        """
        SELECT edge_predicted, edge_realized
        FROM backtest_predictions
        WHERE backtest_id = ?
          AND edge_predicted IS NOT NULL
          AND edge_realized IS NOT NULL
        """,
        [backtest_id],
    ).fetchall()

    return [(float(ep), float(er)) for ep, er in rows]


def format_report_text(report: BacktestReport) -> str:
    """Format a backtest report as human-readable text."""
    lines = [
        "=" * 60,
        "BACKTEST REPORT",
        f"Backtest ID: {report.backtest_id}",
        "=" * 60,
        "",
        "--- SUMMARY ---",
        f"Total predictions: {report.total_predictions}",
        f"Resolved predictions: {report.resolved_predictions}",
        f"Overall hit rate: {report.overall_hit_rate:.1%}",
        f"Overall Brier score: {report.overall_brier_score:.4f}",
        "",
        "--- CALIBRATION CURVE ---",
        "Bucket | Predicted Range | Mean Pred | Mean Actual | Count",
        "-" * 55,
    ]

    for bucket in report.calibration_buckets:
        lines.append(
            f"  {bucket.bucket_index:2d}   | "
            f"{bucket.predicted_range_low:.1f}-{bucket.predicted_range_high:.1f}        | "
            f"{bucket.mean_predicted:.2f}      | "
            f"{bucket.mean_actual:.2f}        | "
            f"{bucket.count:4d}"
        )

    lines.extend([
        "",
        "--- BY PROXY CLASS ---",
        "Class        | Predictions | Hit Rate | Brier  | Mean Edge Pred | Mean Edge Real",
        "-" * 75,
    ])

    for pm in report.proxy_class_metrics:
        lines.append(
            f"{pm.proxy_class:<12} | "
            f"{pm.total_predictions:11d} | "
            f"{pm.hit_rate:7.1%} | "
            f"{pm.brier_score:.4f} | "
            f"{pm.mean_edge_predicted:14.2%} | "
            f"{pm.mean_edge_realized:14.2%}"
        )

    lines.extend([
        "",
        f"Edge scatter data points: {len(report.edge_scatter_data)}",
        "=" * 60,
    ])

    return "\n".join(lines)
