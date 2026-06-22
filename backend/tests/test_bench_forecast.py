"""Tests for benchmark forecast parsing and dataset derived columns."""

from __future__ import annotations

import pandas as pd
import pytest

from parallax.bench.forecast import (
    ForecastStats,
    _build_prompt,
    _extract_tool_prob,
    _parse_prob,
)


class _Block:
    def __init__(self, type_, name=None, input=None, text=None):
        self.type = type_
        self.name = name
        self.input = input
        self.text = text


class _Resp:
    def __init__(self, content):
        self.content = content


def test_extract_tool_prob_ok():
    r = _Resp([_Block("tool_use", name="report_probability", input={"p_yes": 0.73})])
    assert _extract_tool_prob(r) == pytest.approx(0.73)


def test_extract_tool_prob_clamps():
    r = _Resp([_Block("tool_use", name="report_probability", input={"p_yes": 1.4})])
    assert _extract_tool_prob(r) == 1.0


def test_extract_tool_prob_missing():
    assert _extract_tool_prob(_Resp([_Block("text", text="hi")])) is None
    r = _Resp([_Block("tool_use", name="report_probability", input={})])
    assert _extract_tool_prob(r) is None


@pytest.mark.parametrize(
    "text,expected",
    [
        ("PROBABILITY: 0.72", 0.72),
        ("reasoning here.\nPROBABILITY: 0.05", 0.05),
        ("probability: 1.0", 1.0),
        ("PROBABILITY: 0", 0.0),
        ("It is likely. PROBABILITY: 0.9", 0.9),
        ("0.42", 0.42),  # bare fallback
        ("Closes before Jan 1, 2025. Final answer 0.30", 0.30),  # ignores 1 and 2025
        (".66", 0.66),
    ],
)
def test_parse_prob_ok(text, expected):
    assert _parse_prob(text) == pytest.approx(expected)


@pytest.mark.parametrize("text", ["no number here", "", "1500 dollars only", "P=200%"])
def test_parse_prob_none(text):
    assert _parse_prob(text) is None


def test_parse_prob_prefers_tag_over_stray_numbers():
    # The tag wins even if earlier reasoning mentions other in-range numbers.
    assert _parse_prob("Base rate ~0.10 historically. PROBABILITY: 0.80") == pytest.approx(0.80)


def test_build_prompt_includes_fields():
    row = pd.Series({
        "question": "Will X happen?",
        "description": "Resolves yes if X.",
        "category": "Politics",
        "close_time": "2025-10-01T00:00:00Z",
    })
    p = _build_prompt(row)
    assert "Will X happen?" in p
    assert "Resolves yes if X." in p
    assert "Politics" in p
    assert "2025-10-01" in p


def test_forecast_stats_cost():
    s = ForecastStats(model="claude-haiku-4-5-20251001", input_tokens=1_000_000, output_tokens=1_000_000)
    # haiku price (1, 5) per 1M -> 1 + 5 = 6
    assert s.est_cost_usd == pytest.approx(6.0)
