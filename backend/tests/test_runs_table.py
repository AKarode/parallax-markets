"""Tests for the runs table and daily_scorecard table (TEL-01, SCORE-01)."""

from __future__ import annotations

from datetime import datetime, timezone

import duckdb
import pytest

from parallax.db.schema import create_tables


@pytest.fixture
def conn():
    db = duckdb.connect(":memory:")
    create_tables(db)
    yield db
    db.close()


def test_runs_table_exists(conn):
    row = conn.execute(
        "SELECT COUNT(*) FROM information_schema.tables WHERE table_name = 'runs'"
    ).fetchone()
    assert row[0] == 1


def test_runs_table_columns(conn):
    cols = {
        r[0]
        for r in conn.execute(
            "SELECT column_name FROM information_schema.columns WHERE table_name = 'runs'"
        ).fetchall()
    }
    expected = {
        "run_id", "started_at", "ended_at", "status",
        "data_environment", "execution_environment",
        "git_sha", "error", "config_hash",
        "predictions_count", "signals_count", "trades_count",
    }
    assert expected.issubset(cols)


def test_runs_insert_and_update(conn):
    now = datetime.now(timezone.utc)
    conn.execute(
        "INSERT INTO runs (run_id, started_at, status, data_environment) VALUES (?, ?, 'running', 'live')",
        ["test-run-1", now],
    )
    conn.execute(
        "UPDATE runs SET ended_at = ?, status = 'completed', predictions_count = 3 WHERE run_id = ?",
        [now, "test-run-1"],
    )
    row = conn.execute("SELECT status, predictions_count FROM runs WHERE run_id = 'test-run-1'").fetchone()
    assert row[0] == "completed"
    assert row[1] == 3


def test_daily_scorecard_table_exists(conn):
    row = conn.execute(
        "SELECT COUNT(*) FROM information_schema.tables WHERE table_name = 'daily_scorecard'"
    ).fetchone()
    assert row[0] == 1


def test_daily_scorecard_columns(conn):
    cols = {
        r[0]
        for r in conn.execute(
            "SELECT column_name FROM information_schema.columns WHERE table_name = 'daily_scorecard'"
        ).fetchall()
    }
    expected = {"score_date", "metric_name", "metric_value", "dimensions", "computed_at", "run_id"}
    assert expected.issubset(cols)


def test_daily_scorecard_insert_and_query(conn):
    conn.execute(
        "INSERT INTO daily_scorecard (score_date, metric_name, metric_value, dimensions) VALUES (?, ?, ?, ?)",
        ["2026-04-09", "brier_score", 0.25, '{"model": "oil_price"}'],
    )
    conn.execute(
        "INSERT INTO daily_scorecard (score_date, metric_name, metric_value) VALUES (?, ?, ?)",
        ["2026-04-09", "hit_rate", 0.68],
    )
    rows = conn.execute(
        "SELECT metric_name, metric_value FROM daily_scorecard WHERE score_date = '2026-04-09' ORDER BY metric_name"
    ).fetchall()
    assert len(rows) == 2
    assert rows[0] == ("brier_score", 0.25)
    assert rows[1] == ("hit_rate", 0.68)


def test_daily_scorecard_upsert_on_conflict(conn):
    conn.execute(
        "INSERT INTO daily_scorecard (score_date, metric_name, metric_value) VALUES (?, ?, ?)",
        ["2026-04-09", "brier_score", 0.30],
    )
    conn.execute(
        """
        INSERT INTO daily_scorecard (score_date, metric_name, metric_value)
        VALUES (?, ?, ?)
        ON CONFLICT (score_date, metric_name) DO UPDATE SET metric_value = EXCLUDED.metric_value
        """,
        ["2026-04-09", "brier_score", 0.22],
    )
    row = conn.execute(
        "SELECT metric_value FROM daily_scorecard WHERE score_date = '2026-04-09' AND metric_name = 'brier_score'"
    ).fetchone()
    assert row[0] == 0.22
