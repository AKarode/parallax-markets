from __future__ import annotations

import duckdb
import pytest

from parallax.db.schema import create_tables


TABLES_WITH_TAGS = (
    "prediction_log",
    "signal_ledger",
    "trade_orders",
    "trade_positions",
)


@pytest.fixture
def conn():
    connection = duckdb.connect(":memory:")
    yield connection
    connection.close()


def _get_column_names(conn: duckdb.DuckDBPyConnection, table_name: str) -> list[str]:
    rows = conn.execute(
        """
        SELECT column_name
        FROM information_schema.columns
        WHERE table_name = ?
        ORDER BY ordinal_position
        """,
        [table_name],
    ).fetchall()
    return [row[0] for row in rows]


def _create_legacy_prediction_log(conn: duckdb.DuckDBPyConnection) -> None:
    conn.execute("""
        CREATE TABLE prediction_log (
            log_id VARCHAR PRIMARY KEY,
            run_id VARCHAR NOT NULL,
            model_id VARCHAR NOT NULL,
            probability DOUBLE NOT NULL,
            direction VARCHAR NOT NULL,
            confidence DOUBLE NOT NULL,
            reasoning TEXT,
            evidence JSON,
            timeframe VARCHAR NOT NULL,
            news_context JSON,
            cascade_inputs JSON,
            created_at TIMESTAMP NOT NULL
        )
    """)


def _create_legacy_signal_ledger(conn: duckdb.DuckDBPyConnection) -> None:
    conn.execute("""
        CREATE TABLE signal_ledger (
            signal_id VARCHAR PRIMARY KEY,
            run_id VARCHAR,
            created_at TIMESTAMP NOT NULL,
            model_id VARCHAR NOT NULL,
            model_claim TEXT NOT NULL,
            model_probability DOUBLE NOT NULL,
            raw_probability DOUBLE,
            model_timeframe VARCHAR NOT NULL,
            model_reasoning TEXT,
            contract_ticker VARCHAR NOT NULL,
            contract_title VARCHAR,
            proxy_class VARCHAR NOT NULL,
            confidence_discount DOUBLE NOT NULL,
            raw_edge DOUBLE,
            effective_edge DOUBLE,
            signal VARCHAR NOT NULL,
            trade_refused_reason TEXT,
            suggested_size VARCHAR,
            resolution_price DOUBLE,
            resolved_at TIMESTAMP,
            model_was_correct BOOLEAN,
            proxy_was_aligned BOOLEAN
        )
    """)


def _create_legacy_trade_orders(conn: duckdb.DuckDBPyConnection) -> None:
    conn.execute("""
        CREATE TABLE trade_orders (
            order_id VARCHAR PRIMARY KEY,
            signal_id VARCHAR,
            run_id VARCHAR,
            ticker VARCHAR NOT NULL,
            venue VARCHAR NOT NULL,
            venue_environment VARCHAR NOT NULL,
            side VARCHAR NOT NULL,
            quantity INTEGER NOT NULL,
            intended_price DOUBLE,
            intended_price_kind VARCHAR,
            executable_reference_price DOUBLE,
            order_type VARCHAR NOT NULL DEFAULT 'limit',
            status VARCHAR NOT NULL,
            venue_order_id VARCHAR,
            submitted_at TIMESTAMP NOT NULL,
            accepted_at TIMESTAMP,
            rejected_at TIMESTAMP,
            rejected_reason TEXT,
            cancelled_at TIMESTAMP,
            cancellation_reason TEXT,
            last_update_at TIMESTAMP,
            filled_quantity INTEGER DEFAULT 0,
            avg_fill_price DOUBLE,
            raw_response JSON
        )
    """)


def _create_legacy_trade_positions(conn: duckdb.DuckDBPyConnection) -> None:
    conn.execute("""
        CREATE TABLE trade_positions (
            position_id VARCHAR PRIMARY KEY,
            signal_id VARCHAR,
            run_id VARCHAR,
            ticker VARCHAR NOT NULL,
            venue VARCHAR NOT NULL,
            venue_environment VARCHAR NOT NULL,
            side VARCHAR NOT NULL,
            quantity INTEGER NOT NULL,
            open_quantity INTEGER NOT NULL,
            entry_price DOUBLE NOT NULL,
            opened_at TIMESTAMP NOT NULL,
            exit_price DOUBLE,
            settlement_price DOUBLE,
            closed_at TIMESTAMP,
            status VARCHAR NOT NULL,
            realized_pnl DOUBLE,
            unrealized_pnl DOUBLE,
            resolution_price DOUBLE,
            resolution_source VARCHAR
        )
    """)


def test_create_tables_adds_experiment_tag_columns_to_core_tables(conn):
    create_tables(conn)

    for table_name in TABLES_WITH_TAGS:
        column_names = _get_column_names(conn, table_name)
        assert "experiment_id" in column_names
        assert "variant" in column_names


def test_create_tables_migrates_legacy_tables_with_experiment_tag_columns(conn):
    _create_legacy_prediction_log(conn)
    _create_legacy_signal_ledger(conn)
    _create_legacy_trade_orders(conn)
    _create_legacy_trade_positions(conn)

    create_tables(conn)

    for table_name in TABLES_WITH_TAGS:
        column_names = _get_column_names(conn, table_name)
        assert "experiment_id" in column_names
        assert "variant" in column_names
