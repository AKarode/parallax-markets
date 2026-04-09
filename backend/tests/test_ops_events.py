"""Tests for ops_events persistence through schema bootstrap and alert sinks."""

from __future__ import annotations

import asyncio
import json
from uuid import UUID

import duckdb
import pytest

from parallax.db.schema import create_tables
from parallax.ops.alerts import AlertEvent, DuckDBAlertSink, build_alert_dispatcher


@pytest.fixture
def conn():
    db = duckdb.connect(":memory:")
    create_tables(db)
    yield db
    db.close()


def test_ops_events_table_exists_with_expected_columns(conn):
    row = conn.execute(
        "SELECT COUNT(*) FROM information_schema.tables WHERE table_name = 'ops_events'"
    ).fetchone()
    assert row[0] == 1

    cols = {
        record[0]
        for record in conn.execute(
            "SELECT column_name FROM information_schema.columns WHERE table_name = 'ops_events'"
        ).fetchall()
    }
    expected = {
        "event_id",
        "run_id",
        "event_type",
        "severity",
        "message",
        "details",
        "created_at",
    }
    assert expected.issubset(cols)


def test_duckdb_alert_sink_persists_alert_event(conn):
    sink = DuckDBAlertSink(db_conn=conn, run_id="run-123")
    event = AlertEvent(
        event_type="feed_stalled",
        severity="warning",
        message="Price feed stalled for 90 seconds",
        details={"source": "polymarket", "lag_seconds": 90},
    )

    asyncio.run(sink.send(event))

    row = conn.execute(
        """
        SELECT event_id, run_id, event_type, severity, message, details, created_at
        FROM ops_events
        """
    ).fetchone()
    assert row is not None
    UUID(row[0])
    assert row[1] == "run-123"
    assert row[2] == "feed_stalled"
    assert row[3] == "warning"
    assert row[4] == "Price feed stalled for 90 seconds"
    assert json.loads(row[5]) == {"source": "polymarket", "lag_seconds": 90}
    assert row[6] is not None


def test_build_alert_dispatcher_persists_events_when_db_sink_enabled(conn):
    dispatcher = build_alert_dispatcher(db_conn=conn, run_id="run-ops")

    event = asyncio.run(
        dispatcher.emit(
            event_type="run_failed",
            severity="error",
            message="Forecast batch failed",
            details={"stage": "settlement", "attempt": 2},
        )
    )

    stored = conn.execute(
        """
        SELECT run_id, event_type, severity, message, details
        FROM ops_events
        ORDER BY created_at DESC
        LIMIT 1
        """
    ).fetchone()
    assert event.event_type == "run_failed"
    assert stored == (
        "run-ops",
        "run_failed",
        "error",
        "Forecast batch failed",
        json.dumps({"stage": "settlement", "attempt": 2}),
    )
