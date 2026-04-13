"""Per-model track record builder for LLM prompt injection.

Queries signal_ledger for resolved signals and builds a concise text summary
of the model's past performance (aggregate stats + last 3 outcomes).
Injected into prediction model prompts so they can self-correct.
"""

from __future__ import annotations

import logging

import duckdb

logger = logging.getLogger(__name__)

_NO_DATA_TEXT = "No track record available yet."


def build_track_record(model_id: str, conn: duckdb.DuckDBPyConnection) -> str:
    """Build a formatted track record string for a specific prediction model.

    Queries signal_ledger for resolved signals belonging to model_id.
    Returns aggregate stats (hit rate) plus last 3 individual outcomes,
    or a fallback message if no resolved signals exist.

    Args:
        model_id: The prediction model identifier (e.g. "oil_price", "ceasefire").
        conn: DuckDB connection with signal_ledger table.

    Returns:
        Formatted track record text for prompt injection (~300 tokens max).
    """
    # Aggregate stats with parameterized query (T-03-07 mitigation)
    row = conn.execute(
        """
        SELECT
            COUNT(*) AS total,
            SUM(CASE WHEN model_was_correct THEN 1 ELSE 0 END) AS correct
        FROM signal_ledger
        WHERE model_id = ? AND model_was_correct IS NOT NULL
        """,
        [model_id],
    ).fetchone()

    if row is None or row[0] == 0:
        return _NO_DATA_TEXT

    total = int(row[0])
    if total < 10:
        return f"Track record: {total} resolved signal(s) -- too few for reliable statistics (minimum 10 required)."
    correct = int(row[1])
    hit_rate = correct / total

    lines = [
        f"Your track record: {correct}/{total} correct ({hit_rate:.0%} hit rate).",
    ]

    # Last 3 resolved signals with parameterized query
    recent = conn.execute(
        """
        SELECT
            contract_ticker,
            model_probability,
            resolution_price,
            model_was_correct,
            signal
        FROM signal_ledger
        WHERE model_id = ? AND model_was_correct IS NOT NULL
        ORDER BY resolved_at DESC
        LIMIT 3
        """,
        [model_id],
    ).fetchall()

    for r in recent:
        ticker = r[0]
        prob = float(r[1])
        res = float(r[2])
        was_correct = r[3]
        signal = r[4]
        label = "CORRECT" if was_correct else "WRONG"
        lines.append(
            f"  - {ticker}: predicted {prob:.0%}, resolved {res:.0%} -> {label} ({signal})"
        )

    return "\n".join(lines)
