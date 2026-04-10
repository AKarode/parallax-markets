"""Tests for edge decay over time tracking (exit-logic feasibility)."""

from __future__ import annotations

import duckdb
import pytest

from parallax.db.schema import create_tables
from parallax.scoring.calibration import edge_decay_over_time, edge_decay_summary


@pytest.fixture
def conn():
    db = duckdb.connect(":memory:")
    create_tables(db)
    yield db
    db.close()


def _seed_signal(conn, signal_id, run_id, ticker, model_id, edge, signal, ts):
    conn.execute(
        """
        INSERT INTO signal_ledger
        (signal_id, run_id, created_at, model_id, model_claim, model_probability,
         model_timeframe, contract_ticker, proxy_class, confidence_discount,
         signal, tradeability_status, effective_edge)
        VALUES (?, ?, ?, ?, 'claim', 0.70, '7d', ?, 'DIRECT', 1.0, ?, 'tradable', ?)
        """,
        [signal_id, run_id, ts, model_id, ticker, signal, edge],
    )


class TestEdgeDecayOverTime:
    def test_empty_returns_empty(self, conn):
        assert edge_decay_over_time(conn) == []

    def test_single_signal_no_pairs(self, conn):
        _seed_signal(conn, "s1", "run-1", "KXWTI", "oil_price", 0.12, "BUY_YES", "2026-04-09 08:00:00+00")
        assert edge_decay_over_time(conn) == []

    def test_two_runs_creates_one_pair(self, conn):
        _seed_signal(conn, "s1", "run-1", "KXWTI", "oil_price", 0.12, "BUY_YES", "2026-04-09 08:00:00+00")
        _seed_signal(conn, "s2", "run-2", "KXWTI", "oil_price", 0.08, "BUY_YES", "2026-04-09 20:00:00+00")

        pairs = edge_decay_over_time(conn)
        assert len(pairs) == 1
        p = pairs[0]
        assert p["contract_ticker"] == "KXWTI"
        assert p["edge_a"] == 0.12
        assert p["edge_b"] == 0.08
        assert abs(p["edge_change"] - (-0.04)) < 0.001
        assert abs(p["hours_between"] - 12.0) < 0.1

    def test_three_runs_creates_two_pairs(self, conn):
        _seed_signal(conn, "s1", "run-1", "KXWTI", "oil_price", 0.12, "BUY_YES", "2026-04-09 08:00:00+00")
        _seed_signal(conn, "s2", "run-2", "KXWTI", "oil_price", 0.08, "BUY_YES", "2026-04-09 20:00:00+00")
        _seed_signal(conn, "s3", "run-3", "KXWTI", "oil_price", 0.03, "HOLD", "2026-04-10 08:00:00+00")

        pairs = edge_decay_over_time(conn)
        assert len(pairs) == 2
        # First pair: 12% → 8% = -4%
        assert abs(pairs[0]["edge_change"] - (-0.04)) < 0.001
        # Second pair: 8% → 3% = -5%
        assert abs(pairs[1]["edge_change"] - (-0.05)) < 0.001

    def test_different_contracts_tracked_separately(self, conn):
        _seed_signal(conn, "s1", "run-1", "KXWTI", "oil_price", 0.12, "BUY_YES", "2026-04-09 08:00:00+00")
        _seed_signal(conn, "s2", "run-1", "KXHORMUZ", "hormuz", 0.10, "BUY_NO", "2026-04-09 08:00:00+00")
        _seed_signal(conn, "s3", "run-2", "KXWTI", "oil_price", 0.08, "BUY_YES", "2026-04-09 20:00:00+00")
        _seed_signal(conn, "s4", "run-2", "KXHORMUZ", "hormuz", 0.14, "BUY_NO", "2026-04-09 20:00:00+00")

        pairs = edge_decay_over_time(conn)
        assert len(pairs) == 2
        wti = [p for p in pairs if p["contract_ticker"] == "KXWTI"]
        hormuz = [p for p in pairs if p["contract_ticker"] == "KXHORMUZ"]
        assert len(wti) == 1
        assert len(hormuz) == 1
        # WTI edge decayed
        assert wti[0]["edge_change"] < 0
        # Hormuz edge grew
        assert hormuz[0]["edge_change"] > 0

    def test_edge_increase_is_positive(self, conn):
        _seed_signal(conn, "s1", "run-1", "KXWTI", "oil_price", 0.05, "HOLD", "2026-04-09 08:00:00+00")
        _seed_signal(conn, "s2", "run-2", "KXWTI", "oil_price", 0.11, "BUY_YES", "2026-04-09 20:00:00+00")

        pairs = edge_decay_over_time(conn)
        assert pairs[0]["edge_change"] > 0  # Edge grew, not decayed


class TestEdgeDecaySummary:
    def test_empty_returns_no_data(self, conn):
        s = edge_decay_summary(conn)
        assert s["n_pairs"] == 0
        assert "No data" in s["verdict"]

    def test_slow_decay_says_hold(self, conn):
        # Edge decays 2% over 12h — well below 5.5c threshold
        _seed_signal(conn, "s1", "run-1", "KXWTI", "oil_price", 0.10, "BUY_YES", "2026-04-09 08:00:00+00")
        _seed_signal(conn, "s2", "run-2", "KXWTI", "oil_price", 0.08, "BUY_YES", "2026-04-09 20:00:00+00")

        s = edge_decay_summary(conn)
        assert s["n_pairs"] == 1
        assert "NO" in s["verdict"]
        assert s["pct_decayed_past_threshold"] == 0.0

    def test_fast_decay_says_maybe(self, conn):
        # All edges decay 8%+ — past the 5.5c threshold
        for i in range(5):
            _seed_signal(conn, f"a{i}", f"run-{i}", "KXWTI", "oil_price", 0.15, "BUY_YES", f"2026-04-{9+i:02d} 08:00:00+00")
            _seed_signal(conn, f"b{i}", f"run-{i}b", "KXWTI", "oil_price", 0.05, "HOLD", f"2026-04-{9+i:02d} 20:00:00+00")

        s = edge_decay_summary(conn)
        assert s["n_pairs"] == 9  # 10 signals = 9 consecutive pairs
        assert s["pct_decayed_past_threshold"] > 0
