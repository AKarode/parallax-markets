"""Tests for calibration analysis queries and report."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import duckdb
import pytest

from parallax.db.schema import create_tables


@pytest.fixture
def conn():
    """Create an in-memory DuckDB connection with schema."""
    c = duckdb.connect(":memory:")
    create_tables(c)
    return c


def _insert_signal(
    conn: duckdb.DuckDBPyConnection,
    *,
    signal_id: str,
    proxy_class: str = "DIRECT",
    model_probability: float = 0.6,
    effective_edge: float = 0.10,
    signal: str = "BUY_YES",
    model_was_correct: bool | None = True,
    realized_pnl: float | None = None,
    model_id: str = "oil_price",
) -> None:
    """Insert a minimal signal_ledger row for testing."""
    now = datetime.now(timezone.utc).isoformat()
    conn.execute(
        """
        INSERT INTO signal_ledger
        (signal_id, created_at, model_id, model_claim, model_probability,
         model_timeframe, contract_ticker, proxy_class, confidence_discount,
         market_yes_price, market_no_price, entry_side, entry_price, raw_edge,
         effective_edge, signal, model_was_correct, realized_pnl,
         counterfactual_pnl, resolution_price, resolved_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        [
            signal_id, now, model_id, "test claim", model_probability,
            "7d", "KXTEST-01", proxy_class, 1.0,
            0.50, 0.50,
            "yes" if signal == "BUY_YES" else "no",
            0.50,
            effective_edge, effective_edge,
            signal, model_was_correct, realized_pnl,
            realized_pnl, 1.0 if signal == "BUY_YES" else 0.0, now,
        ],
    )


def _insert_prediction(
    conn: duckdb.DuckDBPyConnection,
    *,
    log_id: str,
    run_id: str = "run-1",
    created_at: datetime | None = None,
) -> None:
    """Insert a minimal prediction_log row for testing."""
    ts = (created_at or datetime.now(timezone.utc)).isoformat()
    conn.execute(
        """
        INSERT INTO prediction_log
        (log_id, run_id, model_id, probability, direction, confidence,
         reasoning, evidence, timeframe, news_context, cascade_inputs, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        [
            log_id, run_id, "oil_price", 0.7, "increase", 0.7,
            "test", "[]", "7d", "[]", None, ts,
        ],
    )


class TestHitRateByProxyClass:
    """Test hit_rate_by_proxy_class query."""

    def test_returns_grouped_results(self, conn):
        from parallax.scoring.calibration import hit_rate_by_proxy_class

        _insert_signal(conn, signal_id="s1", proxy_class="DIRECT", model_was_correct=True)
        _insert_signal(conn, signal_id="s2", proxy_class="DIRECT", model_was_correct=True)
        _insert_signal(conn, signal_id="s3", proxy_class="DIRECT", model_was_correct=False)
        _insert_signal(conn, signal_id="s4", proxy_class="NEAR_PROXY", model_was_correct=True)
        _insert_signal(conn, signal_id="s5", proxy_class="NEAR_PROXY", model_was_correct=False)
        _insert_signal(conn, signal_id="s6", proxy_class="LOOSE_PROXY", model_was_correct=False)

        result = hit_rate_by_proxy_class(conn)
        assert len(result) == 3

        by_class = {r["proxy_class"]: r for r in result}
        assert by_class["DIRECT"]["total"] == 3
        assert by_class["DIRECT"]["correct"] == 2
        assert abs(by_class["DIRECT"]["hit_rate"] - 0.667) < 0.01
        assert by_class["NEAR_PROXY"]["total"] == 2
        assert by_class["NEAR_PROXY"]["correct"] == 1
        assert abs(by_class["NEAR_PROXY"]["hit_rate"] - 0.5) < 0.01
        assert by_class["LOOSE_PROXY"]["total"] == 1
        assert by_class["LOOSE_PROXY"]["correct"] == 0
        assert by_class["LOOSE_PROXY"]["hit_rate"] == 0.0


class TestCalibrationCurve:
    """Test calibration_curve query."""

    def test_returns_bucketed_results(self, conn):
        from parallax.scoring.calibration import calibration_curve

        # Spread across 5 buckets
        _insert_signal(conn, signal_id="s1", model_probability=0.15, model_was_correct=False)
        _insert_signal(conn, signal_id="s2", model_probability=0.35, model_was_correct=True)
        _insert_signal(conn, signal_id="s3", model_probability=0.55, model_was_correct=True)
        _insert_signal(conn, signal_id="s4", model_probability=0.75, model_was_correct=True)
        _insert_signal(conn, signal_id="s5", model_probability=0.90, model_was_correct=True)

        result = calibration_curve(conn)
        assert len(result) == 5

        buckets = {r["bucket"]: r for r in result}
        assert "0-20%" in buckets
        assert "20-40%" in buckets
        assert "40-60%" in buckets
        assert "60-80%" in buckets
        assert "80-100%" in buckets
        assert buckets["0-20%"]["n"] == 1
        assert buckets["0-20%"]["actual_rate"] == 0.0
        assert buckets["80-100%"]["actual_rate"] == 1.0


class TestEdgeDecay:
    """Test edge_decay query."""

    def test_returns_edge_buckets(self, conn):
        from parallax.scoring.calibration import edge_decay

        _insert_signal(conn, signal_id="s1", effective_edge=0.03, realized_pnl=0.02, model_was_correct=True)
        _insert_signal(conn, signal_id="s2", effective_edge=0.07, realized_pnl=0.05, model_was_correct=True)
        _insert_signal(conn, signal_id="s3", effective_edge=0.12, realized_pnl=-0.03, model_was_correct=False)
        _insert_signal(conn, signal_id="s4", effective_edge=0.20, realized_pnl=0.15, model_was_correct=True)

        result = edge_decay(conn)
        assert len(result) == 4

        by_bucket = {r["edge_bucket"]: r for r in result}
        assert "<5%" in by_bucket
        assert "5-10%" in by_bucket
        assert "10-15%" in by_bucket
        assert "15%+" in by_bucket
        assert by_bucket["<5%"]["avg_pnl"] == 0.02
        assert by_bucket["15%+"]["hit_rate"] == 1.0


class TestMinimumDataGuard:
    """Test 7-day minimum data guard."""

    def test_insufficient_data_returns_message(self, conn):
        from parallax.scoring.calibration import calibration_report

        # Insert predictions all from today
        now = datetime.now(timezone.utc)
        _insert_prediction(conn, log_id="p1", created_at=now)
        _insert_prediction(conn, log_id="p2", created_at=now)

        result = calibration_report(conn)
        assert "Insufficient data" in result

    def test_no_data_returns_message(self, conn):
        from parallax.scoring.calibration import calibration_report

        result = calibration_report(conn)
        assert "No prediction data" in result


class TestCalibrationReportFormat:
    """Test full calibration report output."""

    def test_report_contains_all_sections(self, conn):
        from parallax.scoring.calibration import calibration_report

        # Insert 8 days of predictions
        now = datetime.now(timezone.utc)
        for i in range(10):
            _insert_prediction(
                conn,
                log_id=f"p{i}",
                created_at=now - timedelta(days=i),
            )

        # Insert some resolved signals
        _insert_signal(conn, signal_id="s1", proxy_class="DIRECT", model_was_correct=True,
                       model_probability=0.75, effective_edge=0.10, realized_pnl=0.08)
        _insert_signal(conn, signal_id="s2", proxy_class="NEAR_PROXY", model_was_correct=False,
                       model_probability=0.35, effective_edge=0.05, realized_pnl=-0.04)

        result = calibration_report(conn)
        assert "PARALLAX SIGNAL-QUALITY REPORT" in result
        assert "HIT RATE BY PROXY CLASS" in result
        assert "CALIBRATION CURVE" in result
        assert "EDGE DECAY" in result


class TestEmptyResults:
    """Test queries with no resolved signals."""

    def test_hit_rate_empty(self, conn):
        from parallax.scoring.calibration import hit_rate_by_proxy_class

        result = hit_rate_by_proxy_class(conn)
        assert result == []

    def test_calibration_curve_empty(self, conn):
        from parallax.scoring.calibration import calibration_curve

        result = calibration_curve(conn)
        assert result == []

    def test_edge_decay_empty(self, conn):
        from parallax.scoring.calibration import edge_decay

        result = edge_decay(conn)
        assert result == []
