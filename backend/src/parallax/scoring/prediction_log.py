"""Append-only prediction log backed by DuckDB.

Persists every prediction the system makes with full context:
probability, reasoning, evidence, news inputs, and cascade state.
Each prediction run shares a run_id for correlation.
"""

from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime, timezone

import duckdb
from pydantic import BaseModel

from parallax.prediction.schemas import PredictionOutput

logger = logging.getLogger(__name__)


class PredictionLogEntry(BaseModel):
    """Immutable record of a single prediction."""

    log_id: str
    run_id: str
    data_environment: str = "live"
    model_id: str
    probability: float
    direction: str
    confidence: float
    reasoning: str
    evidence: list[str]
    timeframe: str
    news_context: list[dict]
    cascade_inputs: dict | None = None
    created_at: datetime


class PredictionLogger:
    """Append-only prediction log backed by DuckDB."""

    def __init__(self, conn: duckdb.DuckDBPyConnection) -> None:
        self._conn = conn

    def log_prediction(
        self,
        run_id: str,
        prediction: PredictionOutput,
        news_context: list[dict],
        cascade_inputs: dict | None = None,
        *,
        data_environment: str = "live",
    ) -> PredictionLogEntry:
        """Persist a prediction with full context.

        Args:
            run_id: Shared ID for all predictions in one brief run.
            prediction: The PredictionOutput from a model.
            news_context: List of news event dicts (title, url, source, fetched_at).
            cascade_inputs: Cascade engine state dict, or None for non-cascade models.

        Returns:
            PredictionLogEntry with all fields populated.
        """
        log_id = str(uuid.uuid4())

        entry = PredictionLogEntry(
            log_id=log_id,
            run_id=run_id,
            data_environment=data_environment,
            model_id=prediction.model_id,
            probability=prediction.probability,
            direction=prediction.direction,
            confidence=prediction.confidence,
            reasoning=prediction.reasoning,
            evidence=prediction.evidence,
            timeframe=prediction.timeframe,
            news_context=news_context,
            cascade_inputs=cascade_inputs,
            created_at=prediction.created_at,
        )

        self._conn.execute(
            """
            INSERT INTO prediction_log
            (log_id, run_id, data_environment, model_id, probability, direction, confidence,
             reasoning, evidence, timeframe, news_context, cascade_inputs,
             created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                entry.log_id,
                entry.run_id,
                entry.data_environment,
                entry.model_id,
                entry.probability,
                entry.direction,
                entry.confidence,
                entry.reasoning,
                json.dumps(entry.evidence),
                entry.timeframe,
                json.dumps(entry.news_context),
                json.dumps(entry.cascade_inputs) if entry.cascade_inputs is not None else None,
                entry.created_at.isoformat(),
            ],
        )

        logger.debug(
            "Logged prediction %s: %s P=%.2f (%s)",
            log_id[:8], entry.model_id, entry.probability, entry.direction,
        )
        return entry

    def get_predictions(
        self, run_id: str | None = None, limit: int = 100,
    ) -> list[PredictionLogEntry]:
        """Return predictions from the log, optionally filtered by run_id.

        Results ordered by created_at descending.
        """
        if run_id is not None:
            rows = self._conn.execute(
                """
                SELECT log_id, run_id, model_id, probability, direction,
                       data_environment, confidence, reasoning, evidence, timeframe,
                       news_context, cascade_inputs, created_at
                FROM prediction_log
                WHERE run_id = ?
                ORDER BY created_at DESC
                LIMIT ?
                """,
                [run_id, limit],
            ).fetchall()
        else:
            rows = self._conn.execute(
                """
                SELECT log_id, run_id, model_id, probability, direction,
                       data_environment, confidence, reasoning, evidence, timeframe,
                       news_context, cascade_inputs, created_at
                FROM prediction_log
                ORDER BY created_at DESC
                LIMIT ?
                """,
                [limit],
            ).fetchall()

        return [self._row_to_entry(row) for row in rows]

    def _row_to_entry(self, row: tuple) -> PredictionLogEntry:
        """Convert a DuckDB row tuple to a PredictionLogEntry."""
        evidence_raw = row[8]
        news_raw = row[10]
        cascade_raw = row[11]

        return PredictionLogEntry(
            log_id=row[0],
            run_id=row[1],
            model_id=row[2],
            probability=row[3],
            direction=row[4],
            data_environment=row[5],
            confidence=row[6],
            reasoning=row[7],
            evidence=json.loads(evidence_raw) if isinstance(evidence_raw, str) else evidence_raw,
            timeframe=row[9],
            news_context=json.loads(news_raw) if isinstance(news_raw, str) else news_raw,
            cascade_inputs=json.loads(cascade_raw) if isinstance(cascade_raw, str) and cascade_raw else cascade_raw if cascade_raw is not None else None,
            created_at=row[12],
        )
