"""Tests for crisis_context.py DB rendering and staleness penalty."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import duckdb
import pytest

from parallax.db.schema import create_tables
from parallax.ingestion.crisis_ingester import _headline_hash
from parallax.prediction.crisis_context import (
    CRISIS_TIMELINE,
    SEED_EVENTS,
    compute_staleness_penalty,
    get_crisis_context,
    get_crisis_context_with_metadata,
    render_crisis_context_from_db,
    seed_crisis_events,
)


@pytest.fixture()
def conn() -> duckdb.DuckDBPyConnection:
    conn = duckdb.connect(":memory:")
    create_tables(conn)
    return conn


class TestRenderFromDB:
    def test_renders_from_db_when_events_exist(self, conn: duckdb.DuckDBPyConnection) -> None:
        now = datetime.now(timezone.utc)
        conn.execute(
            """
            INSERT INTO crisis_events (id, event_time, headline, source, category, headline_hash)
            VALUES ('test-1', ?, 'Test crisis event', 'test', 'general', ?)
            """,
            [now - timedelta(hours=1), _headline_hash('Test crisis event')],
        )
        result = render_crisis_context_from_db(conn)
        assert result.is_from_db is True
        assert result.event_count == 1
        assert "Test crisis event" in result.context
        assert result.context_age_hours < 2

    def test_returns_empty_when_no_events(self, conn: duckdb.DuckDBPyConnection) -> None:
        result = render_crisis_context_from_db(conn)
        assert result.event_count == 0
        assert result.context == ""
        assert result.context_age_hours == float("inf")

    def test_filters_by_lookback_days(self, conn: duckdb.DuckDBPyConnection) -> None:
        now = datetime.now(timezone.utc)
        conn.execute(
            """
            INSERT INTO crisis_events (id, event_time, headline, source, category, headline_hash)
            VALUES
                ('recent', ?, 'Recent event', 'test', 'general', ?),
                ('old', ?, 'Old event', 'test', 'general', ?)
            """,
            [now - timedelta(days=5), _headline_hash('Recent event'), now - timedelta(days=30), _headline_hash('Old event')],
        )
        result = render_crisis_context_from_db(conn, lookback_days=21)
        assert result.event_count == 1
        assert "Recent event" in result.context
        assert "Old event" not in result.context


class TestStalenessPenalty:
    def test_no_penalty_within_24_hours(self) -> None:
        assert compute_staleness_penalty(0) == 1.0
        assert compute_staleness_penalty(12) == 1.0
        assert compute_staleness_penalty(24) == 1.0

    def test_penalty_at_48_hours(self) -> None:
        assert compute_staleness_penalty(48) == pytest.approx(0.5)

    def test_penalty_at_72_hours(self) -> None:
        assert compute_staleness_penalty(72) == pytest.approx(0.0)

    def test_penalty_beyond_72_hours(self) -> None:
        assert compute_staleness_penalty(100) == 0.0
        assert compute_staleness_penalty(1000) == 0.0

    def test_penalty_linear_decay(self) -> None:
        assert compute_staleness_penalty(36) == pytest.approx(0.75)
        assert compute_staleness_penalty(60) == pytest.approx(0.25)


class TestEnsembleStalenessPenalty:
    def test_no_penalty_within_24_hours(self) -> None:
        assert 0.9 * compute_staleness_penalty(12) == 0.9
        assert 0.9 * compute_staleness_penalty(24) == 0.9

    def test_confidence_halved_at_48_hours(self) -> None:
        assert 0.9 * compute_staleness_penalty(48) == pytest.approx(0.45)

    def test_confidence_zero_at_72_hours(self) -> None:
        assert 0.9 * compute_staleness_penalty(72) == pytest.approx(0.0)
        assert 0.9 * compute_staleness_penalty(200) == pytest.approx(0.0)


class TestFallbackToSeed:
    def test_falls_back_to_hardcoded_when_db_empty(self, conn: duckdb.DuckDBPyConnection) -> None:
        context = get_crisis_context(conn)
        assert context == CRISIS_TIMELINE
        assert "CRITICAL CONTEXT" in context

    def test_uses_db_when_events_exist(self, conn: duckdb.DuckDBPyConnection) -> None:
        now = datetime.now(timezone.utc)
        conn.execute(
            """
            INSERT INTO crisis_events (id, event_time, headline, source, category, headline_hash)
            VALUES ('test-1', ?, 'DB crisis event', 'test', 'general', ?)
            """,
            [now - timedelta(hours=1), _headline_hash('DB crisis event')],
        )
        context = get_crisis_context(conn)
        assert "DB crisis event" in context
        assert "CRISIS TIMELINE (from database)" in context

    def test_falls_back_when_no_conn_provided(self) -> None:
        context = get_crisis_context(None)
        assert context == CRISIS_TIMELINE


class TestSeedCrisisEvents:
    def test_seeds_events_when_empty(self, conn: duckdb.DuckDBPyConnection) -> None:
        count = seed_crisis_events(conn)
        assert count == len(SEED_EVENTS)
        row = conn.execute("SELECT COUNT(*) FROM crisis_events").fetchone()
        assert row[0] == len(SEED_EVENTS)

    def test_does_not_seed_when_populated(self, conn: duckdb.DuckDBPyConnection) -> None:
        conn.execute(
            """
            INSERT INTO crisis_events (id, event_time, headline, source, category, headline_hash)
            VALUES ('existing', CURRENT_TIMESTAMP, 'Existing event', 'test', 'general', ?)
            """,
            [_headline_hash("Existing event")],
        )
        count = seed_crisis_events(conn)
        assert count == 0
        row = conn.execute("SELECT COUNT(*) FROM crisis_events").fetchone()
        assert row[0] == 1


class TestContextWithMetadata:
    def test_returns_metadata_with_db_context(self, conn: duckdb.DuckDBPyConnection) -> None:
        now = datetime.now(timezone.utc)
        conn.execute(
            """
            INSERT INTO crisis_events (id, event_time, headline, source, category, headline_hash)
            VALUES ('test-1', ?, 'Test event', 'test', 'general', ?)
            """,
            [now - timedelta(hours=2), _headline_hash('Test event')],
        )
        result = get_crisis_context_with_metadata(conn)
        assert result.is_from_db is True
        assert result.event_count == 1
        assert result.context_age_hours < 3
        assert result.latest_event_time is not None

    def test_returns_fallback_metadata(self) -> None:
        result = get_crisis_context_with_metadata(None)
        assert result.is_from_db is False
        assert result.event_count == len(SEED_EVENTS)
        assert result.latest_event_time is not None
        assert result.context_age_hours > 0.0
