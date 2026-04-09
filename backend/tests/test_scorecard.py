"""Tests for the daily scorecard ETL (Phase 7: SCORE-02 through SCORE-07, TEL-04)."""

from __future__ import annotations

import json
from datetime import datetime, timezone

import duckdb
import pytest

from parallax.db.schema import create_tables
from parallax.scoring.scorecard import compute_daily_scorecard


@pytest.fixture
def conn():
    db = duckdb.connect(":memory:")
    create_tables(db)
    yield db
    db.close()


def _seed_run(conn, run_id="run-1", date="2026-04-09", status="completed"):
    conn.execute(
        "INSERT INTO runs (run_id, started_at, ended_at, status, data_environment, predictions_count, signals_count) "
        "VALUES (?, ?, ?, ?, 'live', 3, 5)",
        [run_id, f"{date}T10:00:00+00:00", f"{date}T10:01:00+00:00", status],
    )


def _seed_signal(conn, signal_id, date="2026-04-09", **kwargs):
    defaults = {
        "run_id": "run-1",
        "model_id": "oil_price",
        "model_claim": "oil up",
        "model_probability": 0.72,
        "model_timeframe": "7d",
        "contract_ticker": "KXWTIMAX",
        "proxy_class": "DIRECT",
        "confidence_discount": 1.0,
        "signal": "BUY_YES",
        "tradeability_status": "tradeable",
        "effective_edge": 0.12,
        "entry_price_is_executable": True,
        "quote_is_stale": False,
    }
    defaults.update(kwargs)
    conn.execute(
        """
        INSERT INTO signal_ledger
        (signal_id, run_id, created_at, model_id, model_claim, model_probability,
         model_timeframe, contract_ticker, proxy_class, confidence_discount,
         signal, tradeability_status, effective_edge, entry_price_is_executable,
         quote_is_stale)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        [
            signal_id,
            defaults["run_id"],
            f"{date}T10:00:00+00:00",
            defaults["model_id"],
            defaults["model_claim"],
            defaults["model_probability"],
            defaults["model_timeframe"],
            defaults["contract_ticker"],
            defaults["proxy_class"],
            defaults["confidence_discount"],
            defaults["signal"],
            defaults["tradeability_status"],
            defaults["effective_edge"],
            defaults["entry_price_is_executable"],
            defaults["quote_is_stale"],
        ],
    )


def _resolve_signal(conn, signal_id, resolution_price, model_was_correct, date="2026-04-09"):
    conn.execute(
        "UPDATE signal_ledger SET resolution_price = ?, resolved_at = ?, model_was_correct = ?, "
        "counterfactual_pnl = ? WHERE signal_id = ?",
        [resolution_price, f"{date}T18:00:00+00:00", model_was_correct, 0.10 if model_was_correct else -0.05, signal_id],
    )


class TestScorecardComputation:
    def test_empty_scorecard(self, conn):
        result = compute_daily_scorecard(conn, "2026-04-09")
        assert "PARALLAX DAILY SCORECARD" in result
        assert "2026-04-09" in result

    def test_scorecard_writes_to_table(self, conn):
        _seed_run(conn)
        compute_daily_scorecard(conn, "2026-04-09")
        rows = conn.execute(
            "SELECT COUNT(*) FROM daily_scorecard WHERE score_date = '2026-04-09'"
        ).fetchone()
        assert rows[0] > 0

    def test_signal_quality_metrics(self, conn):
        _seed_run(conn)
        _seed_signal(conn, "s1", model_probability=0.70)
        _seed_signal(conn, "s2", model_probability=0.80)
        _seed_signal(conn, "s3", model_probability=0.60)
        _resolve_signal(conn, "s1", 1.0, True)
        _resolve_signal(conn, "s2", 1.0, True)
        _resolve_signal(conn, "s3", 0.0, False)

        result = compute_daily_scorecard(conn, "2026-04-09")
        assert "SIGNAL QUALITY" in result

        row = conn.execute(
            "SELECT metric_value FROM daily_scorecard WHERE metric_name = 'signal_hit_rate'"
        ).fetchone()
        assert row is not None
        assert abs(row[0] - 2.0 / 3.0) < 0.01

    def test_brier_score_computed(self, conn):
        _seed_run(conn)
        _seed_signal(conn, "s1", model_probability=0.90)
        _resolve_signal(conn, "s1", 1.0, True)

        compute_daily_scorecard(conn, "2026-04-09")
        row = conn.execute(
            "SELECT metric_value FROM daily_scorecard WHERE metric_name = 'signal_brier_score'"
        ).fetchone()
        assert row is not None
        # Brier = (0.9 - 1.0)^2 = 0.01
        assert abs(row[0] - 0.01) < 0.001

    def test_tradeability_funnel(self, conn):
        _seed_run(conn)
        _seed_signal(conn, "s1", tradeability_status="tradeable")
        _seed_signal(conn, "s2", tradeability_status="tradeable")
        _seed_signal(conn, "s3", tradeability_status="below_min_edge")

        compute_daily_scorecard(conn, "2026-04-09")
        row = conn.execute(
            "SELECT metric_value, dimensions FROM daily_scorecard WHERE metric_name = 'signal_tradeability_funnel'"
        ).fetchone()
        assert row is not None
        assert row[0] == 3.0
        dims = json.loads(row[1])
        assert dims["tradeable"] == 2
        assert dims["below_min_edge"] == 1


class TestOpsMetrics:
    def test_run_count(self, conn):
        _seed_run(conn, "run-1")
        _seed_run(conn, "run-2")

        compute_daily_scorecard(conn, "2026-04-09")
        row = conn.execute(
            "SELECT metric_value FROM daily_scorecard WHERE metric_name = 'ops_run_count'"
        ).fetchone()
        assert row[0] == 2.0

    def test_run_success_rate(self, conn):
        _seed_run(conn, "run-1", status="completed")
        _seed_run(conn, "run-2", status="failed")

        compute_daily_scorecard(conn, "2026-04-09")
        row = conn.execute(
            "SELECT metric_value FROM daily_scorecard WHERE metric_name = 'ops_run_success_rate'"
        ).fetchone()
        assert row[0] == 0.5

    def test_no_run_alert(self, conn):
        # No runs at all — should trigger alert
        result = compute_daily_scorecard(conn, "2026-04-09")
        assert "No pipeline run in 24+ hours" in result

    def test_llm_cost(self, conn):
        _seed_run(conn)
        conn.execute(
            "INSERT INTO llm_usage (usage_id, run_id, model_id, input_tokens, output_tokens, cost_usd, created_at) "
            "VALUES ('u1', 'run-1', 'sonnet', 1000, 500, 0.015, '2026-04-09T10:00:00+00:00')"
        )
        conn.execute(
            "INSERT INTO llm_usage (usage_id, run_id, model_id, input_tokens, output_tokens, cost_usd, created_at) "
            "VALUES ('u2', 'run-1', 'sonnet', 800, 400, 0.012, '2026-04-09T10:01:00+00:00')"
        )

        compute_daily_scorecard(conn, "2026-04-09")
        row = conn.execute(
            "SELECT metric_value FROM daily_scorecard WHERE metric_name = 'ops_llm_cost_usd'"
        ).fetchone()
        assert abs(row[0] - 0.027) < 0.001


class TestDataQualityMetrics:
    def test_quote_staleness(self, conn):
        _seed_run(conn)
        _seed_signal(conn, "s1", quote_is_stale=False)
        _seed_signal(conn, "s2", quote_is_stale=True)

        compute_daily_scorecard(conn, "2026-04-09")
        row = conn.execute(
            "SELECT metric_value FROM daily_scorecard WHERE metric_name = 'data_quote_staleness_rate'"
        ).fetchone()
        assert row is not None
        assert abs(row[0] - 0.5) < 0.01

    def test_executable_coverage(self, conn):
        _seed_run(conn)
        _seed_signal(conn, "s1", entry_price_is_executable=True)
        _seed_signal(conn, "s2", entry_price_is_executable=False)
        _seed_signal(conn, "s3", entry_price_is_executable=True)

        compute_daily_scorecard(conn, "2026-04-09")
        row = conn.execute(
            "SELECT metric_value FROM daily_scorecard WHERE metric_name = 'data_executable_quote_coverage'"
        ).fetchone()
        assert row is not None
        assert abs(row[0] - 2.0 / 3.0) < 0.01


class TestScorecardIdempotent:
    def test_rerun_overwrites(self, conn):
        _seed_run(conn)
        _seed_signal(conn, "s1")
        _resolve_signal(conn, "s1", 1.0, True)

        compute_daily_scorecard(conn, "2026-04-09")
        compute_daily_scorecard(conn, "2026-04-09")

        count = conn.execute(
            "SELECT COUNT(*) FROM daily_scorecard WHERE score_date = '2026-04-09' AND metric_name = 'signal_hit_rate'"
        ).fetchone()
        assert count[0] == 1
