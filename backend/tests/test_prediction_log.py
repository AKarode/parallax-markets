"""Tests for prediction persistence in DuckDB."""

from __future__ import annotations

from datetime import datetime, timezone

import duckdb
import pytest

from parallax.db.schema import create_tables
from parallax.prediction.schemas import PredictionOutput


@pytest.fixture
def conn():
    """In-memory DuckDB connection with tables created."""
    c = duckdb.connect(":memory:")
    create_tables(c)
    yield c
    c.close()


def _make_prediction(model_id: str = "oil_price") -> PredictionOutput:
    """Helper to create a PredictionOutput for testing."""
    return PredictionOutput(
        model_id=model_id,
        prediction_type="oil_price_direction",
        probability=0.72,
        direction="increase",
        magnitude_range=[3.0, 8.0],
        unit="USD/bbl",
        timeframe="7d",
        confidence=0.72,
        reasoning="Test reasoning for prediction.",
        evidence=["Evidence point 1", "Evidence point 2"],
        created_at=datetime(2026, 4, 8, 12, 0, 0, tzinfo=timezone.utc),
    )


class TestLogPrediction:
    """Test PredictionLogger.log_prediction() persistence."""

    def test_log_prediction_persists_all_fields(self, conn):
        from parallax.scoring.prediction_log import PredictionLogger

        logger = PredictionLogger(conn)
        pred = _make_prediction()
        news_ctx = [
            {"title": "Iran talks resume", "url": "https://example.com/1", "source": "google_news", "fetched_at": "2026-04-08T12:00:00Z"},
        ]
        cascade_ctx = {"supply_loss": 2.5, "bypass_flow": 1.0, "price_shock_pct": 8.5, "current_price": 96.0}

        entry = logger.log_prediction("run-123", pred, news_ctx, cascade_ctx)

        # Check returned entry
        assert entry.run_id == "run-123"
        assert entry.model_id == "oil_price"
        assert entry.probability == 0.72
        assert entry.direction == "increase"
        assert entry.confidence == 0.72
        assert entry.reasoning == "Test reasoning for prediction."
        assert entry.evidence == ["Evidence point 1", "Evidence point 2"]
        assert entry.timeframe == "7d"
        assert entry.news_context == news_ctx
        assert entry.cascade_inputs == cascade_ctx
        assert entry.log_id  # non-empty

        # Check persisted in DB
        rows = conn.execute("SELECT * FROM prediction_log WHERE log_id = ?", [entry.log_id]).fetchall()
        assert len(rows) == 1
        row = rows[0]
        assert row[1] == "run-123"  # run_id
        assert row[2] == "oil_price"  # model_id
        assert row[3] == 0.72  # probability

    def test_run_id_correlates_predictions(self, conn):
        from parallax.scoring.prediction_log import PredictionLogger

        logger = PredictionLogger(conn)
        run_id = "shared-run-id"

        for model_id in ["oil_price", "ceasefire", "hormuz_reopening"]:
            pred = _make_prediction(model_id)
            logger.log_prediction(run_id, pred, [], None)

        rows = conn.execute(
            "SELECT DISTINCT run_id FROM prediction_log WHERE run_id = ?",
            [run_id],
        ).fetchall()
        assert len(rows) == 1

        count = conn.execute(
            "SELECT COUNT(*) FROM prediction_log WHERE run_id = ?",
            [run_id],
        ).fetchone()[0]
        assert count == 3

    def test_news_context_json_roundtrip(self, conn):
        from parallax.scoring.prediction_log import PredictionLogger

        logger = PredictionLogger(conn)
        news_ctx = [
            {"title": "Iran talks resume", "url": "https://example.com/1", "source": "google_news", "fetched_at": "2026-04-08T12:00:00Z"},
            {"title": "Oil prices spike", "url": "https://example.com/2", "source": "gdelt_doc", "fetched_at": "2026-04-08T13:00:00Z"},
        ]

        entry = logger.log_prediction("run-456", _make_prediction(), news_ctx, None)
        results = logger.get_predictions(run_id="run-456")

        assert len(results) == 1
        assert results[0].news_context == news_ctx
        assert results[0].news_context[0]["title"] == "Iran talks resume"
        assert results[0].news_context[1]["source"] == "gdelt_doc"

    def test_cascade_inputs_nullable(self, conn):
        from parallax.scoring.prediction_log import PredictionLogger

        logger = PredictionLogger(conn)
        pred = _make_prediction("ceasefire")

        entry = logger.log_prediction("run-789", pred, [], None)

        assert entry.cascade_inputs is None

        rows = conn.execute(
            "SELECT cascade_inputs FROM prediction_log WHERE log_id = ?",
            [entry.log_id],
        ).fetchall()
        assert rows[0][0] is None

    def test_get_predictions_by_run_id(self, conn):
        from parallax.scoring.prediction_log import PredictionLogger

        logger = PredictionLogger(conn)

        # Insert predictions with 2 different run_ids
        for model_id in ["oil_price", "ceasefire"]:
            logger.log_prediction("run-A", _make_prediction(model_id), [], None)
        logger.log_prediction("run-B", _make_prediction("hormuz_reopening"), [], None)

        results_a = logger.get_predictions(run_id="run-A")
        results_b = logger.get_predictions(run_id="run-B")

        assert len(results_a) == 2
        assert len(results_b) == 1
        assert all(r.run_id == "run-A" for r in results_a)
        assert results_b[0].run_id == "run-B"


class TestPredictionLogTable:
    """Test that create_tables() creates the prediction_log table."""

    def test_prediction_log_table_created(self, conn):
        tables = conn.execute("SHOW TABLES").fetchall()
        table_names = {t[0] for t in tables}
        assert "prediction_log" in table_names

    def test_prediction_log_columns(self, conn):
        cols = conn.execute(
            "SELECT column_name FROM information_schema.columns "
            "WHERE table_name = 'prediction_log' ORDER BY ordinal_position"
        ).fetchall()
        col_names = [c[0] for c in cols]
        assert col_names == [
            "log_id", "run_id", "model_id", "probability", "direction",
            "confidence", "reasoning", "evidence", "timeframe",
            "news_context", "cascade_inputs", "created_at",
        ]
