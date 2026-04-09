"""Bucket-based probability recalibration.

Applies mechanical post-processing to LLM-generated probabilities using
historical calibration data. Only activates when sufficient resolved signals
exist (default: 10+). Offset per bucket capped to prevent oscillation.

This is the second layer of recalibration (D-15/D-16):
1. Prompt self-correction (Plan 03-03) -- LLM sees its own track record
2. Mechanical bucket adjustment (this module) -- post-processing correction
"""

from __future__ import annotations

import logging

import duckdb

from parallax.scoring.calibration import calibration_curve

logger = logging.getLogger(__name__)

# Bucket boundaries: [lower, upper) except last which includes 1.0
_BUCKET_RANGES = [
    (0.0, 0.2, "0-20%"),
    (0.2, 0.4, "20-40%"),
    (0.4, 0.6, "40-60%"),
    (0.6, 0.8, "60-80%"),
    (0.8, 1.01, "80-100%"),  # 1.01 to include 1.0
]


def _bucket_for_prob(prob: float) -> str:
    """Return the bucket string for a probability value.

    Args:
        prob: Probability in [0.0, 1.0].

    Returns:
        Bucket string like '60-80%'.
    """
    for lower, upper, label in _BUCKET_RANGES:
        if lower <= prob < upper:
            return label
    return "80-100%"  # Fallback for edge case prob == 1.0


def recalibrate_probability(
    raw_prob: float,
    model_id: str,
    conn: duckdb.DuckDBPyConnection,
    min_signals: int = 10,
    max_offset: float = 0.15,
) -> tuple[float, float]:
    """Apply bucket-based recalibration. Returns (calibrated, raw).

    Only activates when min_signals resolved signals exist for the model.
    Offset per bucket capped at max_offset to prevent oscillation.

    Args:
        raw_prob: Raw probability from LLM prediction.
        model_id: Model identifier (e.g., 'oil_price').
        conn: DuckDB connection for querying calibration data.
        min_signals: Minimum resolved signals before recalibration activates.
        max_offset: Maximum absolute adjustment per bucket.

    Returns:
        Tuple of (calibrated_probability, raw_probability).
    """
    # Count resolved signals for this model
    row = conn.execute(
        "SELECT COUNT(*) FROM signal_ledger WHERE model_id = ? AND model_was_correct IS NOT NULL",
        [model_id],
    ).fetchone()
    count = int(row[0]) if row else 0

    if count < min_signals:
        return (raw_prob, raw_prob)

    # Get per-model calibration curve
    buckets = calibration_curve(conn, model_id=model_id)
    if not buckets:
        return (raw_prob, raw_prob)

    # Find matching bucket
    target_bucket = _bucket_for_prob(raw_prob)
    bucket_data = None
    for b in buckets:
        if b["bucket"] == target_bucket:
            bucket_data = b
            break

    if bucket_data is None:
        # No data for this bucket yet
        return (raw_prob, raw_prob)

    # Compute offset: positive means model overestimates
    offset = bucket_data["avg_predicted"] - bucket_data["actual_rate"]

    # Cap offset
    offset = max(-max_offset, min(max_offset, offset))

    # Apply correction
    calibrated = raw_prob - offset

    # Clamp to [0.0, 1.0]
    calibrated = max(0.0, min(1.0, calibrated))

    logger.debug(
        "Recalibrated %s: %.3f -> %.3f (bucket=%s, offset=%.3f)",
        model_id, raw_prob, calibrated, target_bucket, offset,
    )

    return (calibrated, raw_prob)
