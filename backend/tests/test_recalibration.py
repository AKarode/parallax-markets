"""Tests for bucket-based probability recalibration."""

from __future__ import annotations

from datetime import datetime, timezone

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
    model_id: str = "oil_price",
    model_probability: float = 0.7,
    effective_edge: float = 0.10,
    signal: str = "BUY_YES",
    model_was_correct: bool | None = True,
    realized_pnl: float | None = None,
    proxy_class: str = "DIRECT",
) -> None:
    """Insert a minimal signal_ledger row for testing."""
    now = datetime.now(timezone.utc).isoformat()
    conn.execute(
        """
        INSERT INTO signal_ledger
        (signal_id, created_at, model_id, model_claim, model_probability,
         model_timeframe, contract_ticker, proxy_class, confidence_discount,
         market_yes_price, market_no_price, raw_edge, effective_edge,
         signal, model_was_correct, realized_pnl)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        [
            signal_id, now, model_id, "test claim", model_probability,
            "7d", "KXTEST-01", proxy_class, 1.0,
            0.50, 0.50, effective_edge, effective_edge,
            signal, model_was_correct, realized_pnl,
        ],
    )


class TestRecalibrateProbability:
    """Test recalibrate_probability function."""

    def test_below_min_signals_returns_unchanged(self, conn):
        """With < 10 resolved signals, return raw probability unchanged."""
        from parallax.scoring.recalibration import recalibrate_probability

        # Insert 5 signals (below threshold of 10)
        for i in range(5):
            _insert_signal(conn, signal_id=f"s{i}", model_id="oil_price",
                           model_probability=0.7, model_was_correct=True)

        calibrated, raw = recalibrate_probability(0.7, "oil_price", conn)
        assert calibrated == 0.7
        assert raw == 0.7

    def test_above_min_signals_adjusts_probability(self, conn):
        """With 15 resolved signals, return adjusted probability based on bucket offset."""
        from parallax.scoring.recalibration import recalibrate_probability

        # Insert 15 signals in 60-80% bucket: predicted 0.7, but only 40% correct
        # avg_predicted ~0.7, actual_rate ~0.4, offset = 0.7 - 0.4 = 0.3 -> capped at 0.15
        for i in range(15):
            _insert_signal(
                conn, signal_id=f"s{i}", model_id="oil_price",
                model_probability=0.7,
                model_was_correct=(i < 6),  # 6/15 = 0.4 actual rate
            )

        calibrated, raw = recalibrate_probability(0.7, "oil_price", conn)
        assert raw == 0.7
        # offset would be ~0.3 but capped at 0.15, so calibrated = 0.7 - 0.15 = 0.55
        assert abs(calibrated - 0.55) < 0.02

    def test_offset_capped_at_max(self, conn):
        """Offset capped at +/-0.15 even if bucket offset is larger."""
        from parallax.scoring.recalibration import recalibrate_probability

        # All signals at 0.9, none correct -> offset = 0.9 - 0.0 = 0.9, capped to 0.15
        for i in range(12):
            _insert_signal(
                conn, signal_id=f"s{i}", model_id="oil_price",
                model_probability=0.9, model_was_correct=False,
            )

        calibrated, raw = recalibrate_probability(0.9, "oil_price", conn)
        assert raw == 0.9
        assert abs(calibrated - 0.75) < 0.02  # 0.9 - 0.15

    def test_calibrated_clamped_to_valid_range(self, conn):
        """Calibrated probability clamped to [0.0, 1.0]."""
        from parallax.scoring.recalibration import recalibrate_probability

        # Signals at 0.05 (low bucket), all correct -> actual_rate = 1.0
        # offset = avg_predicted - actual_rate = 0.05 - 1.0 = -0.95, capped at -0.15
        # calibrated = 0.05 - (-0.15) = 0.20
        for i in range(12):
            _insert_signal(
                conn, signal_id=f"s{i}", model_id="oil_price",
                model_probability=0.05, model_was_correct=True,
            )

        calibrated, raw = recalibrate_probability(0.05, "oil_price", conn)
        assert raw == 0.05
        assert 0.0 <= calibrated <= 1.0


class TestCalibrationCurveModelFilter:
    """Test calibration_curve with optional model_id parameter."""

    def test_model_id_filter(self, conn):
        """calibration_curve(conn, model_id='oil_price') filters by model_id."""
        from parallax.scoring.calibration import calibration_curve

        _insert_signal(conn, signal_id="s1", model_id="oil_price",
                       model_probability=0.7, model_was_correct=True)
        _insert_signal(conn, signal_id="s2", model_id="ceasefire",
                       model_probability=0.3, model_was_correct=False)

        result = calibration_curve(conn, model_id="oil_price")
        assert len(result) == 1
        assert result[0]["bucket"] == "60-80%"

    def test_no_model_id_returns_global(self, conn):
        """calibration_curve(conn) without model_id returns global (backward compatible)."""
        from parallax.scoring.calibration import calibration_curve

        _insert_signal(conn, signal_id="s1", model_id="oil_price",
                       model_probability=0.7, model_was_correct=True)
        _insert_signal(conn, signal_id="s2", model_id="ceasefire",
                       model_probability=0.3, model_was_correct=False)

        result = calibration_curve(conn)
        assert len(result) == 2  # Both models included


class TestSignalRecordRawProbability:
    """Test raw_probability field on SignalRecord."""

    def test_signal_record_has_raw_probability(self):
        """SignalRecord includes raw_probability field."""
        from parallax.scoring.ledger import SignalRecord

        record = SignalRecord(
            signal_id="test",
            created_at=datetime.now(timezone.utc),
            model_id="oil_price",
            model_claim="test",
            model_probability=0.65,
            model_timeframe="7d",
            contract_ticker="KXTEST",
            proxy_class="DIRECT",
            confidence_discount=1.0,
            market_yes_price=0.5,
            market_no_price=0.5,
            raw_edge=0.15,
            effective_edge=0.15,
            signal="BUY_YES",
            raw_probability=0.70,
        )
        assert record.raw_probability == 0.70

    def test_record_signal_stores_raw_probability(self, conn):
        """record_signal stores raw_probability when provided."""
        from parallax.scoring.ledger import SignalLedger
        from parallax.contracts.schemas import MappingResult, ProxyClass
        from parallax.prediction.schemas import PredictionOutput
        from parallax.markets.schemas import MarketPrice

        ledger = SignalLedger(conn)

        now = datetime.now(timezone.utc)
        pred = PredictionOutput(
            model_id="oil_price",
            prediction_type="oil_price_direction",
            probability=0.65,
            direction="increase",
            magnitude_range=[60.0, 70.0],
            unit="USD/barrel",
            confidence=0.7,
            reasoning="test",
            evidence=["a"],
            timeframe="7d",
            created_at=now,
        )
        mapping = MappingResult(
            prediction_model_id="oil_price",
            contract_ticker="KXTEST",
            proxy_class=ProxyClass.DIRECT,
            confidence_discount=1.0,
            raw_edge=0.15,
            effective_edge=0.15,
            should_trade=True,
            reason="Edge above threshold",
        )
        mp = MarketPrice(
            ticker="KXTEST",
            source="kalshi",
            yes_price=0.50,
            no_price=0.50,
            volume=100.0,
            fetched_at=now,
        )

        record = ledger.record_signal(pred, mapping, mp, raw_probability=0.70)
        assert record.raw_probability == 0.70

        # Verify stored in DB
        row = conn.execute(
            "SELECT raw_probability FROM signal_ledger WHERE signal_id = ?",
            [record.signal_id],
        ).fetchone()
        assert row[0] == 0.70
