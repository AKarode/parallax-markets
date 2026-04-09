"""Tests for dashboard data layer -- reusable query functions."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

import duckdb
import pytest

from parallax.db.schema import create_tables


@pytest.fixture
def conn():
    """In-memory DuckDB connection with schema created."""
    c = duckdb.connect(":memory:")
    create_tables(c)
    return c


def _seed_prediction_log(conn, run_id: str = "run-1", n: int = 3):
    """Insert prediction_log rows for testing."""
    models = ["oil_price", "ceasefire", "hormuz_reopening"]
    for i, model in enumerate(models[:n]):
        conn.execute(
            """
            INSERT INTO prediction_log
            (log_id, run_id, model_id, probability, direction, confidence,
             reasoning, timeframe, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [str(uuid.uuid4()), run_id, model, 0.7 + i * 0.05,
             "increase", 0.7 + i * 0.05, f"Test reasoning for {model}",
             "7d", datetime.now(timezone.utc).isoformat()],
        )


def _seed_signal_ledger(conn, n: int = 3):
    """Insert signal_ledger rows for testing."""
    for i in range(n):
        conn.execute(
            """
            INSERT INTO signal_ledger
            (signal_id, created_at, model_id, model_claim, model_probability,
             model_timeframe, contract_ticker, proxy_class, confidence_discount,
             market_yes_price, market_no_price, raw_edge, effective_edge, signal)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [str(uuid.uuid4()), datetime.now(timezone.utc).isoformat(),
             "test_model", "test claim", 0.7, "7d",
             f"KXTEST-{i}", "DIRECT", 1.0, 0.40, 0.60, 0.1, 0.1, "BUY_YES"],
        )


def _seed_market_prices(conn, n: int = 3):
    """Insert market_prices rows for testing."""
    for i in range(n):
        conn.execute(
            """
            INSERT INTO market_prices
            (ticker, source, yes_price, no_price, volume, fetched_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            [f"KXTEST-{i}", "kalshi", 0.55, 0.45, 10000 + i * 1000,
             datetime.now(timezone.utc).isoformat()],
        )


class TestGetLatestBrief:
    """Test get_latest_brief() data retrieval."""

    def test_returns_list_of_dicts(self, conn):
        from parallax.dashboard.data import get_latest_brief

        _seed_prediction_log(conn)
        result = get_latest_brief(conn)
        assert isinstance(result, list)
        assert len(result) > 0
        assert isinstance(result[0], dict)

    def test_dict_has_expected_keys(self, conn):
        from parallax.dashboard.data import get_latest_brief

        _seed_prediction_log(conn)
        result = get_latest_brief(conn)
        expected_keys = {"model_id", "probability", "direction", "confidence", "reasoning", "created_at"}
        assert expected_keys.issubset(result[0].keys())

    def test_empty_when_no_data(self, conn):
        from parallax.dashboard.data import get_latest_brief

        result = get_latest_brief(conn)
        assert result == []


class TestGetSignalHistory:
    """Test get_signal_history() data retrieval."""

    def test_returns_list_of_dicts(self, conn):
        from parallax.dashboard.data import get_signal_history

        _seed_signal_ledger(conn)
        result = get_signal_history(conn)
        assert isinstance(result, list)
        assert len(result) == 3

    def test_ordered_by_created_at_desc(self, conn):
        from parallax.dashboard.data import get_signal_history

        _seed_signal_ledger(conn)
        result = get_signal_history(conn)
        # All timestamps should be in descending order
        timestamps = [r["created_at"] for r in result]
        assert timestamps == sorted(timestamps, reverse=True)

    def test_dict_has_expected_keys(self, conn):
        from parallax.dashboard.data import get_signal_history

        _seed_signal_ledger(conn)
        result = get_signal_history(conn)
        expected_keys = {"signal_id", "created_at", "model_id", "contract_ticker",
                         "proxy_class", "effective_edge", "signal"}
        assert expected_keys.issubset(result[0].keys())


class TestGetCalibrationData:
    """Test get_calibration_data() data retrieval."""

    def test_returns_dict_with_three_keys(self, conn):
        from parallax.dashboard.data import get_calibration_data

        result = get_calibration_data(conn)
        assert isinstance(result, dict)
        assert "hit_rate" in result
        assert "calibration_curve" in result
        assert "edge_decay" in result

    def test_empty_lists_when_no_data(self, conn):
        from parallax.dashboard.data import get_calibration_data

        result = get_calibration_data(conn)
        assert result["hit_rate"] == []
        assert result["calibration_curve"] == []
        assert result["edge_decay"] == []


class TestGetMarketPrices:
    """Test get_market_prices() data retrieval."""

    def test_returns_list_of_dicts(self, conn):
        from parallax.dashboard.data import get_market_prices

        _seed_market_prices(conn)
        result = get_market_prices(conn)
        assert isinstance(result, list)
        assert len(result) == 3

    def test_dict_has_expected_keys(self, conn):
        from parallax.dashboard.data import get_market_prices

        _seed_market_prices(conn)
        result = get_market_prices(conn)
        expected_keys = {"ticker", "source", "yes_price", "no_price", "volume", "fetched_at"}
        assert expected_keys.issubset(result[0].keys())

    def test_empty_when_no_data(self, conn):
        from parallax.dashboard.data import get_market_prices

        result = get_market_prices(conn)
        assert result == []
