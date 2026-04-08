"""Tests for 3 prediction models with mocked Anthropic client."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from unittest.mock import MagicMock

import pytest

from pathlib import Path

from parallax.budget.tracker import BudgetTracker
from parallax.prediction.ceasefire import CeasefirePredictor
from parallax.prediction.hormuz import HormuzReopeningPredictor
from parallax.prediction.oil_price import OilPricePredictor
from parallax.prediction.schemas import PredictionOutput
from parallax.simulation.cascade import CascadeEngine
from parallax.simulation.config import load_scenario_config
from parallax.simulation.world_state import WorldState

SCENARIO_YAML = Path(__file__).resolve().parent.parent / "config" / "scenario_hormuz.yaml"


@dataclass
class MockUsage:
    input_tokens: int = 500
    output_tokens: int = 200


@dataclass
class MockContentBlock:
    text: str


@dataclass
class MockResponse:
    content: list[MockContentBlock]
    usage: MockUsage


def make_mock_client(response_json: dict):
    """Create a mock Anthropic client that returns canned JSON."""
    mock = MagicMock()
    mock_response = MockResponse(
        content=[MockContentBlock(text=json.dumps(response_json))],
        usage=MockUsage(),
    )

    async def mock_create(**kwargs):
        return mock_response

    mock.messages.create = mock_create
    return mock


@pytest.fixture()
def budget():
    return BudgetTracker(daily_cap_usd=20.0)


@pytest.fixture()
def config():
    return load_scenario_config(SCENARIO_YAML)


@pytest.fixture()
def cascade(config):
    return CascadeEngine(config=config)


@pytest.fixture()
def world_state():
    ws = WorldState()
    # Add a Hormuz-area cell
    ws.update_cell(612345678, flow=5_000_000, status="restricted", threat_level=0.7)
    ws.update_cell(612345679, flow=10_000_000, status="open", threat_level=0.2)
    return ws


SAMPLE_EVENTS = [
    {
        "Actor1Name": "IRAN",
        "Actor2Name": "USA",
        "EventCode": "036",
        "GoldsteinScale": 3.4,
        "NumMentions": 15,
        "NumSources": 8,
    },
    {
        "Actor1Name": "IRGC",
        "Actor2Name": "USN",
        "EventCode": "190",
        "GoldsteinScale": -9.0,
        "NumMentions": 25,
        "NumSources": 12,
    },
]

SAMPLE_PRICES = [
    {"period": "2026-04-07", "value": 82.50, "series-id": "RBRTE"},
    {"period": "2026-04-06", "value": 81.20, "series-id": "RBRTE"},
]


class TestOilPricePredictor:
    """Test oil price prediction model."""

    async def test_predict_returns_prediction_output(self, cascade, budget, world_state):
        mock_client = make_mock_client({
            "probability": 0.72,
            "direction": "increase",
            "magnitude_range": [2.5, 8.0],
            "reasoning": "Supply disruption likely to push prices up.",
            "evidence": ["Hormuz flow restricted", "IRGC naval exercises"],
        })

        predictor = OilPricePredictor(cascade, budget, mock_client)
        result = await predictor.predict(SAMPLE_EVENTS, SAMPLE_PRICES, world_state)

        assert isinstance(result, PredictionOutput)
        assert result.model_id == "oil_price"
        assert result.probability == 0.72
        assert result.direction == "increase"
        assert result.magnitude_range == [2.5, 8.0]
        assert result.unit == "USD/bbl"
        assert result.timeframe == "7d"
        assert len(result.evidence) == 2

    async def test_budget_tracked(self, cascade, budget, world_state):
        mock_client = make_mock_client({
            "probability": 0.5,
            "direction": "stable",
            "magnitude_range": [0.0, 1.0],
            "reasoning": "Stable.",
            "evidence": [],
        })

        predictor = OilPricePredictor(cascade, budget, mock_client)
        await predictor.predict(SAMPLE_EVENTS, SAMPLE_PRICES, world_state)

        stats = budget.stats()
        assert stats["call_count"] == 1
        assert stats["spend_today_usd"] > 0

    async def test_empty_events(self, cascade, budget, world_state):
        mock_client = make_mock_client({
            "probability": 0.4,
            "direction": "stable",
            "magnitude_range": [0.0, 2.0],
            "reasoning": "No events to analyze.",
            "evidence": [],
        })

        predictor = OilPricePredictor(cascade, budget, mock_client)
        result = await predictor.predict([], SAMPLE_PRICES, world_state)
        assert result.probability == 0.4

    async def test_missing_prices_uses_fallback(self, cascade, budget, world_state):
        mock_client = make_mock_client({
            "probability": 0.6,
            "direction": "increase",
            "magnitude_range": [1.0, 5.0],
            "reasoning": "No price data, using fallback.",
            "evidence": [],
        })

        predictor = OilPricePredictor(cascade, budget, mock_client)
        result = await predictor.predict(SAMPLE_EVENTS, [], world_state)
        assert result.probability == 0.6


class TestCeasefirePredictor:
    """Test ceasefire prediction model."""

    async def test_predict_returns_prediction_output(self, budget):
        mock_client = make_mock_client({
            "probability": 0.65,
            "reasoning": "Diplomatic signals suggest ceasefire likely to hold.",
            "evidence": ["Iran-US talks in Oman", "Qatar mediation active"],
        })

        predictor = CeasefirePredictor(budget, mock_client)
        result = await predictor.predict(SAMPLE_EVENTS)

        assert isinstance(result, PredictionOutput)
        assert result.model_id == "ceasefire"
        assert result.probability == 0.65
        assert result.timeframe == "14d"
        assert result.direction == "stable"
        assert len(result.evidence) == 2

    async def test_filters_diplomatic_events(self, budget):
        mock_client = make_mock_client({
            "probability": 0.8,
            "reasoning": "Strong cooperative signals.",
            "evidence": ["Cooperation event"],
        })

        predictor = CeasefirePredictor(budget, mock_client)
        # Event 036 is diplomatic, 190 is not
        diplomatic = predictor._filter_diplomatic(SAMPLE_EVENTS)
        assert len(diplomatic) == 1
        assert diplomatic[0]["EventCode"] == "036"

    async def test_empty_events(self, budget):
        mock_client = make_mock_client({
            "probability": 0.5,
            "reasoning": "No diplomatic events.",
            "evidence": [],
        })

        predictor = CeasefirePredictor(budget, mock_client)
        result = await predictor.predict([])
        assert result.probability == 0.5

    async def test_with_negotiation_context(self, budget):
        mock_client = make_mock_client({
            "probability": 0.75,
            "reasoning": "Active Oman talks increase probability.",
            "evidence": ["Oman mediation"],
        })

        predictor = CeasefirePredictor(budget, mock_client)
        result = await predictor.predict(
            SAMPLE_EVENTS,
            current_negotiations="Oman-mediated talks ongoing since April 5",
        )
        assert result.probability == 0.75


class TestHormuzReopeningPredictor:
    """Test Hormuz reopening prediction model."""

    async def test_predict_returns_prediction_output(self, cascade, budget, world_state):
        mock_client = make_mock_client({
            "probability": 0.35,
            "direction": "increase",
            "magnitude_range": [10.0, 40.0],
            "reasoning": "Partial reopening possible with diplomatic progress.",
            "evidence": ["Naval de-escalation signals", "Insurance rate stabilizing"],
        })

        predictor = HormuzReopeningPredictor(cascade, budget, mock_client)
        result = await predictor.predict(SAMPLE_EVENTS, world_state)

        assert isinstance(result, PredictionOutput)
        assert result.model_id == "hormuz_reopening"
        assert result.probability == 0.35
        assert result.direction == "increase"
        assert result.timeframe == "14d"

    async def test_hormuz_status_summary(self, world_state):
        status = HormuzReopeningPredictor._get_hormuz_status(world_state)
        assert "restricted" in status
        assert "open" in status
        assert "flow" in status.lower()

    async def test_empty_world_state(self, cascade, budget):
        mock_client = make_mock_client({
            "probability": 0.5,
            "direction": "stable",
            "magnitude_range": [0.0, 100.0],
            "reasoning": "No data.",
            "evidence": [],
        })

        ws = WorldState()
        predictor = HormuzReopeningPredictor(cascade, budget, mock_client)
        result = await predictor.predict([], ws)
        assert result.probability == 0.5
