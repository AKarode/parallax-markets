"""Tests for semantic deduplication.

Uses a mock sentence-transformers model so tests don't require
downloading the actual ~80 MB model or GPU resources.
"""

from __future__ import annotations

from unittest.mock import MagicMock

import numpy as np
import pytest

from parallax.ingestion.dedup import DEFAULT_THRESHOLD, SemanticDeduplicator


def _make_mock_model(embeddings: np.ndarray) -> MagicMock:
    """Create a mock SentenceTransformer that returns pre-set embeddings."""
    model = MagicMock()
    model.encode.return_value = embeddings
    return model


def _normalise(v: np.ndarray) -> np.ndarray:
    norms = np.linalg.norm(v, axis=1, keepdims=True)
    return v / norms


# ── Threshold default ────────────────────────────────────────────────────

def test_default_threshold_is_090():
    """Validated: 0.90, not 0.85 — lower values risk merging distinct events."""
    assert DEFAULT_THRESHOLD == 0.90


# ── Exact duplicates ────────────────────────────────────────────────────

def test_exact_duplicates_removed():
    """Two identical summaries should collapse to one."""
    vec = np.array([[1.0, 0.0, 0.0]])
    # Same vector repeated = cosine sim 1.0
    embeddings = _normalise(np.vstack([vec, vec]))
    model = _make_mock_model(embeddings)

    dedup = SemanticDeduplicator(similarity_threshold=0.90, model=model)
    events = [
        {"event_id": "1", "summary": "Iran deploys naval forces near Hormuz"},
        {"event_id": "2", "summary": "Iran deploys naval forces near Hormuz"},
    ]
    result = dedup.deduplicate(events)
    assert len(result) == 1
    assert result[0]["event_id"] == "1"


# ── Near-duplicates above threshold ─────────────────────────────────────

def test_similar_events_deduplicated():
    """Events with sim >= threshold are collapsed."""
    # Two vectors with cosine sim ~0.95 (above 0.90)
    v1 = np.array([1.0, 0.0, 0.0])
    v2 = np.array([0.97, 0.24, 0.0])  # cos(v1, v2) ≈ 0.97
    embeddings = _normalise(np.vstack([v1, v2]))
    model = _make_mock_model(embeddings)

    dedup = SemanticDeduplicator(similarity_threshold=0.90, model=model)
    events = [
        {"event_id": "1", "summary": "Iran deploys naval forces near Strait of Hormuz"},
        {"event_id": "2", "summary": "Iranian navy deploys military ships near Hormuz strait"},
    ]
    result = dedup.deduplicate(events)
    assert len(result) == 1


# ── Distinct events below threshold ─────────────────────────────────────

def test_different_events_kept():
    """Events with low sim should both be retained."""
    v1 = np.array([1.0, 0.0, 0.0])
    v2 = np.array([0.0, 1.0, 0.0])  # orthogonal, sim = 0
    embeddings = _normalise(np.vstack([v1, v2]))
    model = _make_mock_model(embeddings)

    dedup = SemanticDeduplicator(similarity_threshold=0.90, model=model)
    events = [
        {"event_id": "1", "summary": "Iran deploys naval forces near Hormuz"},
        {"event_id": "2", "summary": "Saudi Arabia increases oil production output"},
    ]
    result = dedup.deduplicate(events)
    assert len(result) == 2


# ── Edge cases ───────────────────────────────────────────────────────────

def test_empty_list():
    model = _make_mock_model(np.array([]))
    dedup = SemanticDeduplicator(model=model)
    assert dedup.deduplicate([]) == []


def test_single_event():
    model = _make_mock_model(np.array([]))
    dedup = SemanticDeduplicator(model=model)
    events = [{"event_id": "1", "summary": "Test"}]
    assert dedup.deduplicate(events) == events


def test_three_events_two_similar():
    """A, B similar; C distinct. Should keep A and C."""
    v1 = np.array([1.0, 0.0, 0.0])
    v2 = np.array([0.98, 0.2, 0.0])   # sim with v1 ≈ 0.98
    v3 = np.array([0.0, 0.0, 1.0])    # orthogonal to both
    embeddings = _normalise(np.vstack([v1, v2, v3]))
    model = _make_mock_model(embeddings)

    dedup = SemanticDeduplicator(similarity_threshold=0.90, model=model)
    events = [
        {"event_id": "1", "summary": "A"},
        {"event_id": "2", "summary": "B"},
        {"event_id": "3", "summary": "C"},
    ]
    result = dedup.deduplicate(events)
    assert len(result) == 2
    ids = {e["event_id"] for e in result}
    assert "1" in ids
    assert "3" in ids


# ── Async variant ────────────────────────────────────────────────────────

async def test_deduplicate_async():
    """The async path should produce the same results."""
    vec = np.array([[1.0, 0.0, 0.0]])
    embeddings = _normalise(np.vstack([vec, vec]))
    model = _make_mock_model(embeddings)

    dedup = SemanticDeduplicator(similarity_threshold=0.90, model=model)
    events = [
        {"event_id": "1", "summary": "Same event"},
        {"event_id": "2", "summary": "Same event"},
    ]
    result = await dedup.deduplicate_async(events)
    assert len(result) == 1
