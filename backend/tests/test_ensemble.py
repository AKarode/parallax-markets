"""Tests for ensemble prediction utility."""

from __future__ import annotations

import json
from dataclasses import dataclass
from unittest.mock import MagicMock

import pytest

from parallax.budget.tracker import BudgetTracker
from parallax.prediction.ensemble import (
    INSTABILITY_THRESHOLD,
    compute_ensemble,
    ensemble_predict,
    parse_llm_json,
    trimmed_mean,
)


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


def make_ensemble_mock_client(responses: list[dict | str]):
    """Mock client that returns different responses per call."""
    mock = MagicMock()
    call_idx = {"n": 0}

    async def mock_create(**kwargs):
        idx = call_idx["n"]
        call_idx["n"] += 1
        resp_data = responses[idx % len(responses)]
        if isinstance(resp_data, str):
            text = resp_data  # raw string, possibly invalid JSON
        else:
            text = json.dumps(resp_data)
        return MockResponse(
            content=[MockContentBlock(text=text)],
            usage=MockUsage(),
        )

    mock.messages.create = mock_create
    return mock


# --- trimmed_mean tests ---


def test_trimmed_mean_three_values():
    assert trimmed_mean([0.3, 0.7, 0.5]) == 0.5


def test_trimmed_mean_two_values():
    assert trimmed_mean([0.3, 0.7]) == 0.5


def test_trimmed_mean_one_value():
    assert trimmed_mean([0.4]) == 0.4


# --- compute_ensemble tests ---


def test_compute_ensemble_stable():
    result = compute_ensemble([0.50, 0.52, 0.48])
    assert abs(result["probability"] - 0.50) < 0.01
    assert result["is_unstable"] is False
    assert result["std_dev"] < INSTABILITY_THRESHOLD


def test_compute_ensemble_unstable():
    result = compute_ensemble([0.30, 0.70, 0.50])
    assert result["is_unstable"] is True
    assert result["std_dev"] == pytest.approx(0.20, abs=0.01)


def test_compute_ensemble_single():
    result = compute_ensemble([0.60])
    assert result["probability"] == 0.60
    assert result["is_unstable"] is False
    assert result["std_dev"] == 0.0


# --- parse_llm_json tests ---


def test_parse_llm_json_clean():
    assert parse_llm_json('{"probability": 0.5}') == {"probability": 0.5}


def test_parse_llm_json_markdown():
    text = '```json\n{"probability": 0.5}\n```'
    assert parse_llm_json(text) == {"probability": 0.5}


def test_parse_llm_json_invalid():
    with pytest.raises(ValueError):
        parse_llm_json("not json at all")


# --- ensemble_predict tests ---


@pytest.mark.asyncio
async def test_ensemble_predict_three_calls():
    responses = [
        {"probability": 0.50, "reasoning": "low", "evidence": ["a"]},
        {"probability": 0.55, "reasoning": "mid", "evidence": ["b"]},
        {"probability": 0.60, "reasoning": "high", "evidence": ["c"]},
    ]
    client = make_ensemble_mock_client(responses)
    budget = BudgetTracker(daily_cap_usd=20.0)

    result = await ensemble_predict(client, "claude-sonnet-4-20250514", "test prompt", budget)

    assert result["ensemble"]["probability"] == 0.55  # median
    assert result["call_count"] == 3
    assert budget.stats()["call_count"] == 3


@pytest.mark.asyncio
async def test_ensemble_predict_partial_failure():
    responses = [
        {"probability": 0.50, "reasoning": "ok", "evidence": ["a"]},
        "this is not valid json!!!",
        {"probability": 0.60, "reasoning": "ok", "evidence": ["c"]},
    ]
    client = make_ensemble_mock_client(responses)
    budget = BudgetTracker(daily_cap_usd=20.0)

    result = await ensemble_predict(client, "claude-sonnet-4-20250514", "test prompt", budget)

    assert result["call_count"] == 2
    # With 2 values, trimmed_mean returns arithmetic mean
    assert result["ensemble"]["probability"] == pytest.approx(0.55, abs=0.01)
