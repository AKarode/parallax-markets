"""End-to-end staleness penalty wiring.

Predictors must:
1. Receive ``context_age_hours`` from the brief pipeline (or fall back to
   reading it from the crisis_context module if absent).
2. Forward it to ``ensemble_predict`` so confidence is shrunk when context
   is stale (and untouched when fresh).
3. Stamp ``staleness_penalty_applied``, ``context_age_hours``, and
   ``penalty_factor`` onto the resulting ``PredictionOutput`` and onto the
   ``prediction_log`` row written by ``PredictionLogger``.

Probability is unchanged by the staleness penalty -- only confidence shrinks.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import duckdb
import pytest

from parallax.db.schema import create_tables
from parallax.prediction import ceasefire as ceasefire_mod
from parallax.prediction import hormuz as hormuz_mod
from parallax.prediction import oil_price as oil_mod
from parallax.prediction.crisis_context import compute_staleness_penalty
from parallax.scoring.prediction_log import PredictionLogger
from parallax.simulation.world_state import WorldState


@pytest.fixture()
def conn() -> duckdb.DuckDBPyConnection:
    conn = duckdb.connect(":memory:")
    create_tables(conn)
    return conn


def _fake_anthropic(probability: float = 0.7, confidence: float = 0.9) -> MagicMock:
    """Mock AsyncAnthropic that returns a parseable JSON payload."""
    client = MagicMock()
    client.messages = MagicMock()

    async def _create(**_kwargs):
        response = MagicMock()
        response.usage = MagicMock(input_tokens=10, output_tokens=10)
        content = MagicMock()
        content.text = (
            '{"probability": %s, "confidence": %s, "direction": "increase", '
            '"magnitude_range": [1, 2], "reasoning": "r", "evidence": ["e"]}'
            % (probability, confidence)
        )
        response.content = [content]
        return response

    client.messages.create = AsyncMock(side_effect=_create)
    return client


def _make_oil_predictor(client: MagicMock) -> oil_mod.OilPricePredictor:
    cascade = MagicMock()
    cascade.activate_bypass.return_value = {"bypass_flow": 0.0}
    cascade.compute_price_shock.return_value = 100.0
    budget = MagicMock()
    budget.record = MagicMock()
    return oil_mod.OilPricePredictor(cascade, budget, client)


def _make_ceasefire_predictor(client: MagicMock) -> ceasefire_mod.CeasefirePredictor:
    budget = MagicMock()
    budget.record = MagicMock()
    return ceasefire_mod.CeasefirePredictor(budget, client)


def _make_hormuz_predictor(client: MagicMock) -> hormuz_mod.HormuzReopeningPredictor:
    cascade = MagicMock()
    cascade._config = MagicMock(hormuz_daily_flow=21_000_000)
    budget = MagicMock()
    budget.record = MagicMock()
    return hormuz_mod.HormuzReopeningPredictor(cascade, budget, client)


# ---------------------------------------------------------------------------
# 1. Stale context discounts confidence; fresh context leaves it alone.
# ---------------------------------------------------------------------------


class TestStaleContextDiscountsConfidence:
    @pytest.mark.asyncio
    async def test_stale_context_shrinks_confidence(self, conn) -> None:
        client = _fake_anthropic(probability=0.7, confidence=0.9)
        predictor = _make_oil_predictor(client)

        result = await predictor.predict(
            recent_events=[], current_prices=[], world_state=WorldState(),
            db_conn=conn,
            context_age_hours=48.0,
            crisis_context_text="stale",
        )
        # 0.9 * compute_staleness_penalty(48) == 0.45
        assert result.confidence == pytest.approx(0.45)
        # Probability is unchanged by the staleness penalty.
        assert result.probability == pytest.approx(0.7)
        assert result.staleness_penalty_applied is True
        assert result.context_age_hours == pytest.approx(48.0)
        assert result.penalty_factor == pytest.approx(0.5)

    @pytest.mark.asyncio
    async def test_fresh_context_preserves_confidence(self, conn) -> None:
        client = _fake_anthropic(probability=0.7, confidence=0.9)
        predictor = _make_oil_predictor(client)

        result = await predictor.predict(
            recent_events=[], current_prices=[], world_state=WorldState(),
            db_conn=conn,
            context_age_hours=12.0,
            crisis_context_text="fresh",
        )
        assert result.confidence == pytest.approx(0.9)
        assert result.probability == pytest.approx(0.7)
        assert result.staleness_penalty_applied is False
        assert result.context_age_hours == pytest.approx(12.0)
        assert result.penalty_factor == pytest.approx(1.0)

    @pytest.mark.asyncio
    async def test_72h_context_zeroes_confidence(self, conn) -> None:
        client = _fake_anthropic(probability=0.6, confidence=0.8)
        predictor = _make_ceasefire_predictor(client)

        result = await predictor.predict(
            recent_events=[], db_conn=conn,
            context_age_hours=72.0,
            crisis_context_text="ancient",
        )
        assert result.confidence == pytest.approx(0.0)
        assert result.probability == pytest.approx(0.6)
        assert result.staleness_penalty_applied is True
        assert result.penalty_factor == pytest.approx(0.0)


# ---------------------------------------------------------------------------
# 2. PredictionLogger stamps staleness fields on the persisted row.
# ---------------------------------------------------------------------------


class TestPersistedStalenessFields:
    @pytest.mark.asyncio
    async def test_prediction_log_row_carries_staleness_fields(self, conn) -> None:
        client = _fake_anthropic(probability=0.7, confidence=0.9)
        predictor = _make_oil_predictor(client)

        prediction = await predictor.predict(
            recent_events=[], current_prices=[], world_state=WorldState(),
            db_conn=conn,
            context_age_hours=48.0,
            crisis_context_text="stale",
        )

        logger = PredictionLogger(conn)
        run_id = str(uuid.uuid4())
        logger.log_prediction(run_id, prediction, news_context=[])

        row = conn.execute(
            """
            SELECT confidence, probability, staleness_penalty_applied,
                   context_age_hours, penalty_factor
            FROM prediction_log
            WHERE run_id = ?
            """,
            [run_id],
        ).fetchone()
        confidence, probability, applied, age, factor = row
        # Penalty halves confidence at 48h; probability untouched.
        assert confidence == pytest.approx(0.45)
        assert probability == pytest.approx(0.7)
        assert applied is True
        assert age == pytest.approx(48.0)
        assert factor == pytest.approx(0.5)

    @pytest.mark.asyncio
    async def test_prediction_log_row_for_fresh_context(self, conn) -> None:
        client = _fake_anthropic(probability=0.7, confidence=0.9)
        predictor = _make_hormuz_predictor(client)

        prediction = await predictor.predict(
            recent_events=[], world_state=WorldState(), db_conn=conn,
            context_age_hours=2.0,
            crisis_context_text="fresh",
        )

        logger = PredictionLogger(conn)
        run_id = str(uuid.uuid4())
        logger.log_prediction(run_id, prediction, news_context=[])

        row = conn.execute(
            """
            SELECT staleness_penalty_applied, context_age_hours, penalty_factor
            FROM prediction_log
            WHERE run_id = ?
            """,
            [run_id],
        ).fetchone()
        applied, age, factor = row
        assert applied is False
        assert age == pytest.approx(2.0)
        assert factor == pytest.approx(1.0)


# ---------------------------------------------------------------------------
# 3. Predictors forward whatever ``context_age_hours`` brief.py passes them.
# ---------------------------------------------------------------------------


class TestPredictorAcceptsContextAge:
    @pytest.mark.asyncio
    async def test_oil_predictor_uses_caller_provided_age(
        self, conn, monkeypatch,
    ) -> None:
        captured: dict = {}

        async def _fake_ensemble(**kwargs):
            captured.update(kwargs)
            penalty = compute_staleness_penalty(kwargs["context_age_hours"])
            return {
                "ensemble": {
                    "probability": 0.5, "std_dev": 0.0, "is_unstable": False,
                    "individual_probabilities": [0.5],
                },
                "parsed": {
                    "probability": 0.5, "direction": "stable",
                    "magnitude_range": [0, 1], "reasoning": "r",
                    "evidence": [], "confidence": 0.8 * penalty,
                },
                "all_parsed": [],
                "call_count": 1,
                "context_age_hours": kwargs["context_age_hours"],
                "penalty_factor": penalty,
                "staleness_penalty_applied": penalty < 1.0,
            }

        monkeypatch.setattr(oil_mod, "ensemble_predict", _fake_ensemble)
        predictor = _make_oil_predictor(_fake_anthropic())

        await predictor.predict(
            recent_events=[], current_prices=[], world_state=WorldState(),
            db_conn=conn,
            context_age_hours=36.0,
            crisis_context_text="...",
        )
        # Caller-supplied age wins over any DB lookup.
        assert captured["context_age_hours"] == pytest.approx(36.0)

    @pytest.mark.asyncio
    async def test_ceasefire_predictor_uses_caller_provided_age(
        self, conn, monkeypatch,
    ) -> None:
        captured: dict = {}

        async def _fake_ensemble(**kwargs):
            captured.update(kwargs)
            return {
                "ensemble": {
                    "probability": 0.5, "std_dev": 0.0, "is_unstable": False,
                    "individual_probabilities": [0.5],
                },
                "parsed": {
                    "probability": 0.5, "direction": "stable",
                    "magnitude_range": [0, 1], "reasoning": "r",
                    "evidence": [], "confidence": 0.8,
                },
                "all_parsed": [], "call_count": 1,
                "context_age_hours": kwargs["context_age_hours"],
                "penalty_factor": 1.0,
                "staleness_penalty_applied": False,
            }

        monkeypatch.setattr(ceasefire_mod, "ensemble_predict", _fake_ensemble)
        predictor = _make_ceasefire_predictor(_fake_anthropic())
        await predictor.predict(
            recent_events=[], db_conn=conn,
            context_age_hours=10.0, crisis_context_text="...",
        )
        assert captured["context_age_hours"] == pytest.approx(10.0)

    @pytest.mark.asyncio
    async def test_hormuz_predictor_uses_caller_provided_age(
        self, conn, monkeypatch,
    ) -> None:
        captured: dict = {}

        async def _fake_ensemble(**kwargs):
            captured.update(kwargs)
            return {
                "ensemble": {
                    "probability": 0.5, "std_dev": 0.0, "is_unstable": False,
                    "individual_probabilities": [0.5],
                },
                "parsed": {
                    "probability": 0.5, "direction": "stable",
                    "magnitude_range": [0, 1], "reasoning": "r",
                    "evidence": [], "confidence": 0.8,
                },
                "all_parsed": [], "call_count": 1,
                "context_age_hours": kwargs["context_age_hours"],
                "penalty_factor": 1.0,
                "staleness_penalty_applied": False,
            }

        monkeypatch.setattr(hormuz_mod, "ensemble_predict", _fake_ensemble)
        predictor = _make_hormuz_predictor(_fake_anthropic())
        await predictor.predict(
            recent_events=[], world_state=WorldState(), db_conn=conn,
            context_age_hours=5.0, crisis_context_text="...",
        )
        assert captured["context_age_hours"] == pytest.approx(5.0)


# ---------------------------------------------------------------------------
# 4. crisis_context fallback emits a real age, not 0.0 -- so the penalty
#    actually fires when the DB ingester is broken in live mode.
# ---------------------------------------------------------------------------


class TestFallbackContextHasRealAge:
    def test_seed_fallback_age_is_nonzero(self) -> None:
        from parallax.prediction.crisis_context import (
            get_crisis_context_with_metadata,
        )

        result = get_crisis_context_with_metadata(None)
        assert result.is_from_db is False
        # Age computed from the latest SEED_EVENTS entry, not 0.0.
        assert result.context_age_hours > 0.0

    def test_seed_fallback_age_triggers_penalty(self) -> None:
        from parallax.prediction.crisis_context import (
            get_crisis_context_with_metadata,
        )

        result = get_crisis_context_with_metadata(None)
        # SEED_EVENTS' latest entry is 2026-04-12 -- months stale by any clock
        # the test runs on. Penalty must have already saturated to 0.
        penalty = compute_staleness_penalty(result.context_age_hours)
        assert penalty == pytest.approx(0.0)
