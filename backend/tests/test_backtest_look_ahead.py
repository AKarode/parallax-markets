"""Tests for backtest look-ahead guard preventing future data leakage."""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone

import duckdb
import pytest

from parallax.backtest.look_ahead_guard import (
    LookAheadGuard,
    look_ahead_safe,
)
from parallax.db.schema import create_tables


@pytest.fixture()
def conn() -> duckdb.DuckDBPyConnection:
    """In-memory DuckDB with schema and test data."""
    conn = duckdb.connect(":memory:")
    create_tables(conn)

    now = datetime.now(timezone.utc)
    past = now - timedelta(days=5)
    future = now + timedelta(days=5)

    conn.execute(
        """
        INSERT INTO crisis_events (id, event_time, headline, source, category)
        VALUES
            ('past-1', ?, 'Past event 1', 'test', 'general'),
            ('past-2', ?, 'Past event 2', 'test', 'general'),
            ('future-1', ?, 'Future event', 'test', 'general')
        """,
        [past, past - timedelta(days=1), future],
    )

    conn.execute(
        """
        INSERT INTO market_prices
        (ticker, source, data_environment, fetched_at, yes_price, no_price, volume)
        VALUES
            ('KXTEST-1', 'test', 'backtest', ?, 0.50, 0.50, 100),
            ('KXTEST-2', 'test', 'backtest', ?, 0.60, 0.40, 100),
            ('KXTEST-3', 'test', 'backtest', ?, 0.70, 0.30, 100)
        """,
        [past, past - timedelta(days=1), future],
    )

    return conn


class TestLookAheadGuardBasics:
    def test_guard_is_context_manager(self, conn: duckdb.DuckDBPyConnection) -> None:
        sim_date = date.today()
        with LookAheadGuard(conn, sim_date) as guard:
            assert guard.is_active is True
            assert guard.sim_date == sim_date
        assert guard.is_active is False

    def test_guard_cannot_be_nested(self, conn: duckdb.DuckDBPyConnection) -> None:
        sim_date = date.today()
        guard = LookAheadGuard(conn, sim_date)
        with guard:
            with pytest.raises(RuntimeError, match="already active"):
                guard.__enter__()


class TestLookAheadPrevention:
    def test_filters_future_crisis_events(self, conn: duckdb.DuckDBPyConnection) -> None:
        sim_date = date.today()
        rows_unguarded = conn.execute("SELECT headline FROM crisis_events").fetchall()
        assert len(rows_unguarded) == 3
        with look_ahead_safe(conn, sim_date) as guard:
            rows_guarded = guard.execute("SELECT headline FROM crisis_events").fetchall()
        headlines = [r[0] for r in rows_guarded]
        assert "Past event 1" in headlines
        assert "Past event 2" in headlines
        assert "Future event" not in headlines

    def test_filters_future_market_prices(self, conn: duckdb.DuckDBPyConnection) -> None:
        sim_date = date.today()
        rows_unguarded = conn.execute("SELECT ticker FROM market_prices").fetchall()
        assert len(rows_unguarded) == 3
        with look_ahead_safe(conn, sim_date) as guard:
            rows_guarded = guard.execute("SELECT ticker FROM market_prices").fetchall()
        tickers = [r[0] for r in rows_guarded]
        assert "KXTEST-1" in tickers
        assert "KXTEST-2" in tickers
        assert "KXTEST-3" not in tickers

    def test_sim_date_boundary(self, conn: duckdb.DuckDBPyConnection) -> None:
        today = date.today()
        conn.execute(
            """
            INSERT INTO crisis_events (id, event_time, headline, source, category)
            VALUES ('today', ?, 'Today event', 'test', 'general')
            """,
            [datetime.combine(today, datetime.min.time(), tzinfo=timezone.utc)],
        )
        with look_ahead_safe(conn, today) as guard:
            rows = guard.execute(
                "SELECT headline FROM crisis_events WHERE headline = 'Today event'"
            ).fetchall()
        assert len(rows) == 1


class TestLookAheadDecorator:
    def test_guard_execute_method(self, conn: duckdb.DuckDBPyConnection) -> None:
        sim_date = date.today()
        with look_ahead_safe(conn, sim_date) as guard:
            rows = guard.execute("SELECT headline FROM crisis_events").fetchall()
        headlines = [r[0] for r in rows]
        assert "Future event" not in headlines

    def test_guard_passes_unfiltered_queries(self, conn: duckdb.DuckDBPyConnection) -> None:
        sim_date = date.today()
        with look_ahead_safe(conn, sim_date) as guard:
            guard.execute(
                """
                INSERT INTO crisis_events (id, event_time, headline, source, category)
                VALUES ('new-via-guard', CURRENT_TIMESTAMP, 'Guard insert', 'test', 'general')
                """
            )
        row = conn.execute(
            "SELECT headline FROM crisis_events WHERE id = 'new-via-guard'"
        ).fetchone()
        assert row is not None


class TestNonSelectQueries:
    def test_insert_not_filtered(self, conn: duckdb.DuckDBPyConnection) -> None:
        sim_date = date.today()
        with look_ahead_safe(conn, sim_date) as guard:
            guard.execute(
                """
                INSERT INTO crisis_events (id, event_time, headline, source, category)
                VALUES ('new', CURRENT_TIMESTAMP, 'New event', 'test', 'general')
                """
            )
        row = conn.execute(
            "SELECT headline FROM crisis_events WHERE id = 'new'"
        ).fetchone()
        assert row is not None
        assert row[0] == "New event"

    def test_update_not_filtered(self, conn: duckdb.DuckDBPyConnection) -> None:
        sim_date = date.today()
        with look_ahead_safe(conn, sim_date) as guard:
            guard.execute(
                "UPDATE crisis_events SET headline = 'Updated' WHERE id = 'past-1'"
            )
        row = conn.execute(
            "SELECT headline FROM crisis_events WHERE id = 'past-1'"
        ).fetchone()
        assert row[0] == "Updated"


class TestComplexQueries:
    def test_query_with_where_clause(self, conn: duckdb.DuckDBPyConnection) -> None:
        sim_date = date.today()
        with look_ahead_safe(conn, sim_date) as guard:
            rows = guard.execute(
                "SELECT headline FROM crisis_events WHERE source = 'test'"
            ).fetchall()
        headlines = [r[0] for r in rows]
        assert "Future event" not in headlines

    def test_query_with_order_by(self, conn: duckdb.DuckDBPyConnection) -> None:
        sim_date = date.today()
        with look_ahead_safe(conn, sim_date) as guard:
            rows = guard.execute(
                "SELECT headline FROM crisis_events ORDER BY event_time DESC"
            ).fetchall()
        headlines = [r[0] for r in rows]
        assert "Future event" not in headlines

    def test_query_with_limit(self, conn: duckdb.DuckDBPyConnection) -> None:
        sim_date = date.today()
        with look_ahead_safe(conn, sim_date) as guard:
            rows = guard.execute(
                "SELECT headline FROM crisis_events LIMIT 10"
            ).fetchall()
        headlines = [r[0] for r in rows]
        assert "Future event" not in headlines
