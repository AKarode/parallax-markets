"""Tests for SignalLedger -- append-only signal tracking in DuckDB."""

from __future__ import annotations

from datetime import datetime, timezone

import duckdb
import pytest

from parallax.contracts.schemas import MappingResult, ProxyClass
from parallax.db.schema import create_tables
from parallax.markets.schemas import MarketPrice
from parallax.prediction.schemas import PredictionOutput
from parallax.scoring.ledger import SignalLedger, SignalRecord


@pytest.fixture
def conn():
    """In-memory DuckDB connection with schema created."""
    c = duckdb.connect(":memory:")
    create_tables(c)
    return c


@pytest.fixture
def ledger(conn):
    """SignalLedger instance backed by in-memory DuckDB."""
    return SignalLedger(conn)


@pytest.fixture
def sample_prediction():
    """A sample PredictionOutput for testing."""
    return PredictionOutput(
        model_id="ceasefire",
        prediction_type="ceasefire_probability",
        probability=0.65,
        direction="stable",
        magnitude_range=[0.0, 1.0],
        unit="probability",
        timeframe="14d",
        confidence=0.65,
        reasoning="Test reasoning for ceasefire prediction.",
        evidence=["evidence 1", "evidence 2"],
        created_at=datetime(2026, 4, 8, 12, 0, 0, tzinfo=timezone.utc),
    )


@pytest.fixture
def sample_mapping():
    """A sample MappingResult for testing."""
    return MappingResult(
        prediction_model_id="ceasefire",
        contract_ticker="KXUSAIRANAGREEMENT-27",
        proxy_class=ProxyClass.NEAR_PROXY,
        buy_yes_edge=0.17,
        buy_no_edge=-0.04,
        raw_edge=0.17,
        confidence_discount=0.6,
        effective_edge=0.102,
        entry_side="yes",
        entry_price=0.48,
        entry_price_kind="best_yes_ask",
        entry_price_is_executable=True,
        tradeability_status="tradable",
        should_trade=True,
        reason="NEAR PROXY match, edge +10.2%",
    )


@pytest.fixture
def sample_market():
    """A sample MarketPrice for testing."""
    return MarketPrice(
        ticker="KXUSAIRANAGREEMENT-27",
        source="kalshi",
        best_yes_bid=0.47,
        best_yes_ask=0.48,
        best_no_bid=0.51,
        best_no_ask=0.52,
        yes_price=0.48,
        no_price=0.52,
        derived_price_kind="midpoint",
        volume=8500,
        fetched_at=datetime(2026, 4, 8, 12, 0, 0, tzinfo=timezone.utc),
    )


class TestSignalRecordModel:
    """Test 1: SignalRecord model validates with all required fields."""

    def test_signal_record_validates(self):
        record = SignalRecord(
            signal_id="test-id-123",
            created_at=datetime.now(timezone.utc),
            model_id="ceasefire",
            model_claim="ceasefire: stable with P=0.65 over 14d",
            model_probability=0.65,
            model_timeframe="14d",
            model_reasoning="Test reasoning",
            contract_ticker="KXUSAIRANAGREEMENT-27",
            contract_title="US-Iran Agreement",
            proxy_class="near_proxy",
            confidence_discount=0.6,
            market_yes_price=0.48,
            market_no_price=0.52,
            market_volume=8500,
            raw_edge=0.17,
            effective_edge=0.102,
            signal="BUY_YES",
        )
        assert record.signal_id == "test-id-123"
        assert record.traded is False
        assert record.trade_id is None
        assert record.resolution_price is None

    def test_signal_record_optional_fields(self):
        record = SignalRecord(
            signal_id="test-id-456",
            created_at=datetime.now(timezone.utc),
            model_id="oil_price",
            model_claim="oil_price: increase with P=0.72 over 7d",
            model_probability=0.72,
            model_timeframe="7d",
            contract_ticker="KXWTIMAX-26DEC31",
            proxy_class="near_proxy",
            confidence_discount=0.6,
            market_yes_price=0.55,
            market_no_price=0.45,
            raw_edge=0.17,
            effective_edge=0.102,
            signal="BUY_YES",
        )
        assert record.model_reasoning is None
        assert record.contract_title is None
        assert record.market_volume is None


class TestRecordSignal:
    """Test 2: ledger.record_signal() inserts a row and returns SignalRecord."""

    def test_record_signal_returns_signal_record(
        self, ledger, sample_prediction, sample_mapping, sample_market,
    ):
        result = ledger.record_signal(
            sample_prediction, sample_mapping, sample_market,
            contract_title="US-Iran Agreement",
        )
        assert isinstance(result, SignalRecord)
        assert result.model_id == "ceasefire"
        assert result.contract_ticker == "KXUSAIRANAGREEMENT-27"
        assert result.proxy_class == "near_proxy"
        assert result.signal == "BUY_YES"
        assert result.effective_edge == pytest.approx(0.102)
        assert result.traded is False

    def test_record_signal_persists_to_db(
        self, ledger, conn, sample_prediction, sample_mapping, sample_market,
    ):
        ledger.record_signal(
            sample_prediction, sample_mapping, sample_market,
        )
        rows = conn.execute("SELECT COUNT(*) FROM signal_ledger").fetchone()
        assert rows[0] == 1

    def test_record_signal_refused(self, ledger, sample_prediction, sample_market):
        """When should_trade is False, signal should be REFUSED."""
        mapping = MappingResult(
            prediction_model_id="ceasefire",
            contract_ticker="KXUSAIRANAGREEMENT-27",
            proxy_class=ProxyClass.LOOSE_PROXY,
            buy_yes_edge=0.05,
            raw_edge=0.05,
            confidence_discount=0.3,
            effective_edge=0.015,
            entry_side="yes",
            entry_price=0.48,
            entry_price_kind="best_yes_ask",
            entry_price_is_executable=True,
            tradeability_status="tradable",
            should_trade=False,
            reason="Rejected: edge 1.5% below 5.0% threshold",
        )
        result = ledger.record_signal(
            sample_prediction, mapping, sample_market,
        )
        assert result.signal == "HOLD"

    def test_record_signal_buy_no(self, ledger, sample_market):
        """Negative effective_edge should produce BUY_NO."""
        pred = PredictionOutput(
            model_id="ceasefire",
            prediction_type="ceasefire_probability",
            probability=0.30,
            direction="stable",
            magnitude_range=[0.0, 1.0],
            unit="probability",
            timeframe="14d",
            confidence=0.30,
            reasoning="Low probability.",
            evidence=[],
            created_at=datetime.now(timezone.utc),
        )
        mapping = MappingResult(
            prediction_model_id="ceasefire",
            contract_ticker="KXUSAIRANAGREEMENT-27",
            proxy_class=ProxyClass.NEAR_PROXY,
            buy_no_edge=0.18,
            raw_edge=-0.18,
            confidence_discount=0.6,
            effective_edge=-0.108,
            entry_side="no",
            entry_price=0.52,
            entry_price_kind="best_no_ask",
            entry_price_is_executable=True,
            tradeability_status="tradable",
            should_trade=True,
            reason="NEAR PROXY match, edge -10.8%",
        )
        result = ledger.record_signal(pred, mapping, sample_market)
        assert result.signal == "BUY_NO"


class TestGetSignals:
    """Test 3 & 4: get_signals returns signals ordered by created_at desc, with optional filter."""

    def test_get_signals_returns_all(
        self, ledger, sample_prediction, sample_mapping, sample_market,
    ):
        ledger.record_signal(sample_prediction, sample_mapping, sample_market)
        signals = ledger.get_signals()
        assert len(signals) == 1
        assert signals[0].model_id == "ceasefire"

    def test_get_signals_filter_by_model_id(
        self, ledger, sample_prediction, sample_mapping, sample_market,
    ):
        ledger.record_signal(sample_prediction, sample_mapping, sample_market)

        # Create a second signal for a different model
        oil_pred = PredictionOutput(
            model_id="oil_price",
            prediction_type="oil_price_direction",
            probability=0.72,
            direction="increase",
            magnitude_range=[3.0, 8.0],
            unit="USD/bbl",
            timeframe="7d",
            confidence=0.72,
            reasoning="Test oil reasoning.",
            evidence=[],
            created_at=datetime.now(timezone.utc),
        )
        oil_mapping = MappingResult(
            prediction_model_id="oil_price",
            contract_ticker="KXWTIMAX-26DEC31",
            proxy_class=ProxyClass.NEAR_PROXY,
            raw_edge=0.17,
            confidence_discount=0.6,
            effective_edge=0.102,
            should_trade=True,
            reason="NEAR PROXY match",
        )
        oil_market = MarketPrice(
            ticker="KXWTIMAX-26DEC31",
            source="kalshi",
            best_yes_bid=0.54,
            best_yes_ask=0.55,
            best_no_bid=0.44,
            best_no_ask=0.45,
            yes_price=0.55,
            no_price=0.45,
            derived_price_kind="midpoint",
            volume=12000,
            fetched_at=datetime.now(timezone.utc),
        )
        ledger.record_signal(oil_pred, oil_mapping, oil_market)

        ceasefire_only = ledger.get_signals(model_id="ceasefire")
        assert len(ceasefire_only) == 1
        assert ceasefire_only[0].model_id == "ceasefire"

        all_signals = ledger.get_signals()
        assert len(all_signals) == 2


class TestGetActionableSignals:
    """Test 5: get_actionable_signals returns only tradeable, untraded signals."""

    def test_actionable_excludes_refused(
        self, ledger, sample_prediction, sample_market,
    ):
        # Add a REFUSED signal
        refused_mapping = MappingResult(
            prediction_model_id="ceasefire",
            contract_ticker="KXUSAIRANAGREEMENT-27",
            proxy_class=ProxyClass.LOOSE_PROXY,
            raw_edge=0.02,
            confidence_discount=0.3,
            effective_edge=0.006,
            should_trade=False,
            reason="Below threshold",
        )
        ledger.record_signal(sample_prediction, refused_mapping, sample_market)

        actionable = ledger.get_actionable_signals()
        assert len(actionable) == 0

    def test_actionable_returns_buy_signals(
        self, ledger, sample_prediction, sample_mapping, sample_market,
    ):
        ledger.record_signal(sample_prediction, sample_mapping, sample_market)
        actionable = ledger.get_actionable_signals()
        assert len(actionable) == 1
        assert actionable[0].signal in ("BUY_YES", "BUY_NO")

    def test_actionable_excludes_traded(
        self, ledger, sample_prediction, sample_mapping, sample_market,
    ):
        signal = ledger.record_signal(
            sample_prediction, sample_mapping, sample_market,
        )
        ledger.mark_traded(signal.signal_id, "trade-abc")

        actionable = ledger.get_actionable_signals()
        assert len(actionable) == 0


class TestSignalLedgerTable:
    """Test 6: signal_ledger table is created by create_tables()."""

    def test_table_exists(self, conn):
        tables = conn.execute(
            "SELECT table_name FROM information_schema.tables WHERE table_schema = 'main'"
        ).fetchall()
        table_names = {t[0] for t in tables}
        assert "signal_ledger" in table_names

    def test_table_columns(self, conn):
        cols = conn.execute(
            "SELECT column_name FROM information_schema.columns WHERE table_name = 'signal_ledger'"
        ).fetchall()
        col_names = {c[0] for c in cols}
        expected = {
            "signal_id", "created_at", "model_id", "model_claim",
            "model_probability", "model_timeframe", "model_reasoning",
            "contract_ticker", "contract_title", "proxy_class",
            "confidence_discount", "market_yes_price", "market_no_price",
            "market_volume", "raw_edge", "effective_edge", "signal",
            "trade_id", "traded", "trade_refused_reason",
            "resolution_price", "resolved_at", "realized_pnl",
            "model_was_correct", "proxy_was_aligned",
        }
        assert expected.issubset(col_names)
