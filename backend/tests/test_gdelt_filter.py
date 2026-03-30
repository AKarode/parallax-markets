"""Tests for GDELT ingestion: entity list, volume gate, structural dedup,
relevance scoring, and the async fetch pipeline."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from parallax.ingestion.entities import CRITICAL_ENTITIES, matches_critical_entity
from parallax.ingestion.gdelt import (
    fetch_gdelt_events,
    relevance_score,
    structural_dedup,
    volume_gate,
)


# ── Entity list ──────────────────────────────────────────────────────────

def test_critical_entities_includes_key_actors():
    flat = " ".join(CRITICAL_ENTITIES).lower()
    assert "irgc" in flat
    assert "centcom" in flat
    assert "hormuz" in flat
    assert "aramco" in flat
    assert "bandar abbas" in flat


def test_matches_critical_entity_positive():
    assert matches_critical_entity("IRGC forces deployed near Hormuz") is True
    assert matches_critical_entity("CENTCOM repositions carrier group") is True


def test_matches_critical_entity_negative():
    assert matches_critical_entity("Weather update for London") is False


# ── Volume gate ──────────────────────────────────────────────────────────

def test_volume_gate_passes_high_volume():
    event = {"NumMentions": 10, "NumSources": 5, "Actor1Name": "IRAN"}
    assert volume_gate(event) is True


def test_volume_gate_blocks_low_volume():
    event = {"NumMentions": 1, "NumSources": 1, "Actor1Name": "IRAN"}
    assert volume_gate(event) is False


def test_volume_gate_overrides_for_critical_entity():
    event = {
        "NumMentions": 1,
        "NumSources": 1,
        "Actor1Name": "IRGC",
        "summary": "IRGC conducts naval exercise",
    }
    assert volume_gate(event, check_entity_override=True) is True


def test_volume_gate_no_override_without_flag():
    """Even if entity matches, override is off by default."""
    event = {"NumMentions": 1, "NumSources": 1, "Actor1Name": "IRGC"}
    assert volume_gate(event, check_entity_override=False) is False


# ── Structural dedup ─────────────────────────────────────────────────────

def test_structural_dedup_collapses_same_window():
    events = [
        {
            "Actor1Code": "IRN",
            "EventCode": "190",
            "Actor2Code": "USA",
            "DateAdded": "20260330120000",
            "NumMentions": 3,
        },
        {
            "Actor1Code": "IRN",
            "EventCode": "190",
            "Actor2Code": "USA",
            "DateAdded": "20260330123000",  # 30 min later
            "NumMentions": 10,
        },
    ]
    result = structural_dedup(events, window_hours=1)
    assert len(result) == 1
    assert result[0]["NumMentions"] == 10  # kept the higher-mention one


def test_structural_dedup_keeps_different_actors():
    events = [
        {
            "Actor1Code": "IRN",
            "EventCode": "190",
            "Actor2Code": "USA",
            "DateAdded": "20260330120000",
            "NumMentions": 5,
        },
        {
            "Actor1Code": "SAU",
            "EventCode": "040",
            "Actor2Code": "RUS",
            "DateAdded": "20260330120000",
            "NumMentions": 5,
        },
    ]
    result = structural_dedup(events)
    assert len(result) == 2


def test_structural_dedup_keeps_events_outside_window():
    events = [
        {
            "Actor1Code": "IRN",
            "EventCode": "190",
            "Actor2Code": "USA",
            "DateAdded": "20260330100000",
            "NumMentions": 5,
        },
        {
            "Actor1Code": "IRN",
            "EventCode": "190",
            "Actor2Code": "USA",
            "DateAdded": "20260330140000",  # 4 hours later
            "NumMentions": 5,
        },
    ]
    result = structural_dedup(events, window_hours=1)
    assert len(result) == 2


def test_structural_dedup_empty_and_single():
    assert structural_dedup([]) == []
    ev = {"Actor1Code": "X", "EventCode": "1", "Actor2Code": "Y"}
    assert structural_dedup([ev]) == [ev]


# ── Relevance scoring ───────────────────────────────────────────────────

def test_relevance_score_high_for_critical_entity():
    event = {
        "GoldsteinScale": -8.0,
        "NumSources": 15,
        "Actor1Name": "IRGC",
    }
    score = relevance_score(event)
    assert score >= 0.8


def test_relevance_score_low_for_irrelevant():
    event = {
        "GoldsteinScale": 1.0,
        "NumSources": 1,
        "Actor1Name": "FRA",
    }
    score = relevance_score(event)
    assert score < 0.2


def test_relevance_score_bounds():
    """Score should always be in [0, 1]."""
    for gs in [-10, 0, 10]:
        for ns in [0, 5, 20]:
            event = {"GoldsteinScale": gs, "NumSources": ns}
            s = relevance_score(event)
            assert 0.0 <= s <= 1.0, f"score={s} for GS={gs}, NS={ns}"


# ── Async fetch pipeline (mocked BigQuery) ──────────────────────────────

async def test_fetch_gdelt_events_pipeline():
    """Full pipeline with a mocked BigQuery client."""
    fake_rows = [
        # Should pass: high volume
        {
            "NumMentions": 10,
            "NumSources": 5,
            "Actor1Name": "IRN",
            "Actor1Code": "IRN",
            "Actor2Code": "USA",
            "EventCode": "190",
            "GoldsteinScale": -5.0,
            "DateAdded": "20260330120000",
        },
        # Should fail: low volume, no entity match
        {
            "NumMentions": 1,
            "NumSources": 1,
            "Actor1Name": "FRA",
            "Actor1Code": "FRA",
            "Actor2Code": "DEU",
            "EventCode": "040",
            "GoldsteinScale": 1.0,
            "DateAdded": "20260330120500",
        },
        # Should pass: low volume but entity override (IRGC)
        {
            "NumMentions": 2,
            "NumSources": 1,
            "Actor1Name": "IRGC",
            "Actor1Code": "IRGIRGCN",
            "Actor2Code": "USA",
            "EventCode": "173",
            "GoldsteinScale": -7.0,
            "DateAdded": "20260330121000",
        },
    ]

    # Mock BigQuery: query().result() returns list of dict-like rows
    mock_result = MagicMock()
    mock_result.result.return_value = fake_rows

    mock_bq = MagicMock()
    mock_bq.query.return_value = mock_result

    result = await fetch_gdelt_events(mock_bq, "SELECT 1")
    # Row 0 passes volume gate, Row 2 passes entity override
    # Row 1 fails both -> filtered out
    assert len(result) >= 1
    assert all("relevance_score" in ev for ev in result)
    # The FRA event should have been filtered
    actor_names = [ev.get("Actor1Name") for ev in result]
    assert "FRA" not in actor_names
