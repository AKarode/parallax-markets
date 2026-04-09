"""Tests for LLM usage persistence in DuckDB."""

from __future__ import annotations

from uuid import UUID

import duckdb
import pytest

from parallax.budget.tracker import BudgetTracker
from parallax.db.schema import create_tables


@pytest.fixture
def conn():
    c = duckdb.connect(":memory:")
    create_tables(c)
    yield c
    c.close()


def test_create_tables_creates_llm_usage_with_expected_columns(conn):
    tables = conn.execute("SHOW TABLES").fetchall()
    table_names = {table[0] for table in tables}

    assert "llm_usage" in table_names

    columns = conn.execute(
        """
        SELECT column_name
        FROM information_schema.columns
        WHERE table_name = 'llm_usage'
        ORDER BY ordinal_position
        """
    ).fetchall()
    column_names = [column[0] for column in columns]

    assert column_names == [
        "usage_id",
        "run_id",
        "model_id",
        "input_tokens",
        "output_tokens",
        "cost_usd",
        "created_at",
    ]


def test_record_persists_llm_usage_row_with_run_id(conn):
    tracker = BudgetTracker(daily_cap_usd=20.0, db_conn=conn, run_id="run-123")

    tracker.record(input_tokens=2000, output_tokens=1000, model="sonnet")

    row = conn.execute(
        """
        SELECT usage_id, run_id, model_id, input_tokens, output_tokens, cost_usd, created_at
        FROM llm_usage
        """
    ).fetchone()

    assert row is not None
    UUID(row[0])
    assert row[1] == "run-123"
    assert row[2] == "sonnet"
    assert row[3] == 2000
    assert row[4] == 1000
    assert row[5] == pytest.approx(0.021)
    assert row[6] is not None
    assert tracker.total_spend_today() == pytest.approx(0.021)


def test_record_persists_null_run_id_when_not_provided(conn):
    tracker = BudgetTracker(daily_cap_usd=20.0, db_conn=conn)

    tracker.record(input_tokens=1000, output_tokens=500, model="haiku")

    row = conn.execute(
        """
        SELECT run_id, model_id, input_tokens, output_tokens, cost_usd
        FROM llm_usage
        """
    ).fetchone()

    assert row == (None, "haiku", 1000, 500, pytest.approx(0.0035))
