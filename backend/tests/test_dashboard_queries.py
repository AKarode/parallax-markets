"""Tests for new dashboard query functions."""

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


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _seed_scorecard(conn, date_str: str = "2026-04-09"):
    """Insert daily_scorecard rows."""
    metrics = [
        ("signal_hit_rate", 0.65),
        ("signal_brier_score", 0.22),
        ("signal_calibration_max_gap", 0.08),
        ("ops_llm_cost_usd", 0.04),
        ("ops_run_count", 2.0),
        ("ops_run_success_rate", 1.0),
        ("ops_error_alert_count", 0.0),
    ]
    for name, value in metrics:
        conn.execute(
            """
            INSERT INTO daily_scorecard (score_date, metric_name, metric_value)
            VALUES (?, ?, ?)
            """,
            [date_str, name, value],
        )


def _seed_signal_ledger_for_contract(conn, contract_ticker: str, n: int = 3):
    """Insert signal_ledger rows for a specific contract."""
    for i in range(n):
        conn.execute(
            """
            INSERT INTO signal_ledger
            (signal_id, created_at, run_id, model_id, model_claim, model_probability,
             model_timeframe, contract_ticker, proxy_class, confidence_discount,
             effective_edge, signal, entry_side, entry_price)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                str(uuid.uuid4()), _now_iso(), f"run-{i}",
                "oil_price", "test claim", 0.7, "7d",
                contract_ticker, "DIRECT", 1.0,
                0.1 - i * 0.02, "BUY_YES", "yes", 0.55,
            ],
        )


def _seed_contract_registry(conn, ticker: str = "KXTEST-1"):
    """Insert a contract_registry row with proxy mapping."""
    conn.execute(
        """
        INSERT INTO contract_registry
        (ticker, source, event_ticker, title, resolution_criteria, is_active)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        [ticker, "kalshi", "KXEVENT", "Test contract", "Resolves if test passes", True],
    )
    conn.execute(
        """
        INSERT INTO contract_proxy_map
        (ticker, model_type, proxy_class, confidence_discount)
        VALUES (?, ?, ?, ?)
        """,
        [ticker, "oil_price", "DIRECT", 1.0],
    )


def _seed_market_prices(conn, ticker: str = "KXTEST-1", n: int = 5):
    """Insert market_prices rows for a specific ticker."""
    for i in range(n):
        conn.execute(
            """
            INSERT INTO market_prices
            (ticker, source, yes_price, no_price, volume, best_yes_bid,
             best_yes_ask, fetched_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                ticker, "kalshi", 0.55 + i * 0.01, 0.45 - i * 0.01,
                10000 + i * 100, 0.54 + i * 0.01, 0.56 + i * 0.01,
                _now_iso(),
            ],
        )


def _seed_prediction_log(conn, n: int = 6):
    """Insert prediction_log rows for multiple models."""
    models = ["oil_price", "ceasefire", "hormuz_reopening"]
    for i in range(n):
        model = models[i % len(models)]
        conn.execute(
            """
            INSERT INTO prediction_log
            (log_id, run_id, model_id, probability, direction, confidence,
             reasoning, timeframe, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                str(uuid.uuid4()), f"run-{i // 3}",
                model, 0.6 + i * 0.03, "increase", 0.7,
                f"Reasoning {i}", "7d", _now_iso(),
            ],
        )


class TestGetScorecardMetrics:
    """Test get_scorecard_metrics()."""

    def test_empty_returns_all_none(self, conn):
        from parallax.dashboard.data import get_scorecard_metrics

        result = get_scorecard_metrics(conn)
        assert result["score_date"] is None
        assert result["signal_hit_rate"] is None

    def test_returns_metrics_for_latest_date(self, conn):
        from parallax.dashboard.data import get_scorecard_metrics

        _seed_scorecard(conn, "2026-04-08")
        _seed_scorecard(conn, "2026-04-09")
        result = get_scorecard_metrics(conn)
        assert result["score_date"] == "2026-04-09"
        assert result["signal_hit_rate"] == pytest.approx(0.65)

    def test_returns_metrics_for_specific_date(self, conn):
        from parallax.dashboard.data import get_scorecard_metrics

        _seed_scorecard(conn, "2026-04-08")
        _seed_scorecard(conn, "2026-04-09")
        result = get_scorecard_metrics(conn, "2026-04-08")
        assert result["score_date"] == "2026-04-08"

    def test_expected_keys(self, conn):
        from parallax.dashboard.data import get_scorecard_metrics

        _seed_scorecard(conn)
        result = get_scorecard_metrics(conn)
        expected = {
            "signal_hit_rate", "signal_brier_score", "signal_calibration_max_gap",
            "ops_llm_cost_usd", "ops_run_count", "ops_run_success_rate",
            "ops_error_alert_count", "score_date",
        }
        assert expected == set(result.keys())


class TestGetSignalsForContract:
    """Test get_signals_for_contract()."""

    def test_empty_returns_empty_list(self, conn):
        from parallax.dashboard.data import get_signals_for_contract

        result = get_signals_for_contract(conn, "KXTEST-NONE")
        assert result == []

    def test_returns_signals_for_contract(self, conn):
        from parallax.dashboard.data import get_signals_for_contract

        _seed_signal_ledger_for_contract(conn, "KXTEST-1", n=3)
        _seed_signal_ledger_for_contract(conn, "KXTEST-2", n=2)
        result = get_signals_for_contract(conn, "KXTEST-1")
        assert len(result) == 3

    def test_respects_limit(self, conn):
        from parallax.dashboard.data import get_signals_for_contract

        _seed_signal_ledger_for_contract(conn, "KXTEST-1", n=5)
        result = get_signals_for_contract(conn, "KXTEST-1", limit=2)
        assert len(result) == 2

    def test_expected_keys(self, conn):
        from parallax.dashboard.data import get_signals_for_contract

        _seed_signal_ledger_for_contract(conn, "KXTEST-1")
        result = get_signals_for_contract(conn, "KXTEST-1")
        expected = {
            "signal_id", "created_at", "model_id", "effective_edge", "signal",
            "model_probability", "entry_price", "entry_side", "resolution_price",
            "model_was_correct", "run_id",
        }
        assert expected == set(result[0].keys())


class TestGetActiveContracts:
    """Test get_active_contracts()."""

    def test_empty_returns_empty_list(self, conn):
        from parallax.dashboard.data import get_active_contracts

        result = get_active_contracts(conn)
        assert result == []

    def test_returns_contracts_with_proxy_map(self, conn):
        from parallax.dashboard.data import get_active_contracts

        _seed_contract_registry(conn, "KXTEST-1")
        result = get_active_contracts(conn)
        assert len(result) == 1
        assert result[0]["ticker"] == "KXTEST-1"
        assert "oil_price" in result[0]["proxy_map"]
        assert result[0]["best_proxy"] == "DIRECT"

    def test_expected_keys(self, conn):
        from parallax.dashboard.data import get_active_contracts

        _seed_contract_registry(conn)
        result = get_active_contracts(conn)
        expected = {
            "ticker", "source", "event_ticker", "title", "resolution_criteria",
            "resolution_date", "contract_family", "expected_fee_rate",
            "expected_slippage_rate", "proxy_map", "best_proxy",
        }
        assert expected == set(result[0].keys())


class TestGetEdgeDecayForContract:
    """Test get_edge_decay_for_contract()."""

    def test_no_data_returns_insufficient(self, conn):
        from parallax.dashboard.data import get_edge_decay_for_contract

        result = get_edge_decay_for_contract(conn, "KXTEST-NONE")
        assert result["n_pairs"] == 0
        assert result["verdict"] == "insufficient data"
        assert result["round_trip_cost"] == 0.055

    def test_expected_keys(self, conn):
        from parallax.dashboard.data import get_edge_decay_for_contract

        result = get_edge_decay_for_contract(conn, "KXTEST-1")
        expected = {
            "n_pairs", "avg_decay_rate", "avg_edge_change", "time_to_zero_edge",
            "round_trip_cost", "exit_profitable", "verdict",
        }
        assert expected == set(result.keys())


class TestGetPriceHistory:
    """Test get_price_history()."""

    def test_empty_returns_empty_list(self, conn):
        from parallax.dashboard.data import get_price_history

        result = get_price_history(conn, "KXTEST-NONE")
        assert result == []

    def test_returns_prices_for_ticker(self, conn):
        from parallax.dashboard.data import get_price_history

        _seed_market_prices(conn, "KXTEST-1", n=5)
        result = get_price_history(conn, "KXTEST-1")
        assert len(result) == 5

    def test_expected_keys(self, conn):
        from parallax.dashboard.data import get_price_history

        _seed_market_prices(conn, "KXTEST-1")
        result = get_price_history(conn, "KXTEST-1")
        expected = {
            "fetched_at", "yes_price", "no_price", "volume",
            "best_yes_bid", "best_yes_ask",
        }
        assert expected == set(result[0].keys())

    def test_respects_limit(self, conn):
        from parallax.dashboard.data import get_price_history

        _seed_market_prices(conn, "KXTEST-1", n=10)
        result = get_price_history(conn, "KXTEST-1", limit=3)
        assert len(result) == 3


class TestGetPredictionHistory:
    """Test get_prediction_history()."""

    def test_empty_returns_empty_dict(self, conn):
        from parallax.dashboard.data import get_prediction_history

        result = get_prediction_history(conn)
        assert result == {}

    def test_groups_by_model_id(self, conn):
        from parallax.dashboard.data import get_prediction_history

        _seed_prediction_log(conn, n=6)
        result = get_prediction_history(conn)
        assert isinstance(result, dict)
        assert "oil_price" in result
        assert "ceasefire" in result
        assert "hormuz_reopening" in result

    def test_expected_keys_per_entry(self, conn):
        from parallax.dashboard.data import get_prediction_history

        _seed_prediction_log(conn)
        result = get_prediction_history(conn)
        first_model = next(iter(result.values()))
        expected = {"probability", "direction", "confidence", "created_at", "run_id"}
        assert expected == set(first_model[0].keys())
