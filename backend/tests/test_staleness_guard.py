"""Tests for quote staleness guard in divergence detection."""
from datetime import datetime, timezone, timedelta
import pytest
from parallax.divergence.detector import DivergenceDetector
from parallax.markets.schemas import MarketPrice
from parallax.prediction.schemas import PredictionOutput


def _make_prediction(probability: float = 0.80) -> PredictionOutput:
    return PredictionOutput(
        model_id="test_model",
        prediction_type="test",
        probability=probability,
        direction="increase",
        magnitude_range=[0.0, 1.0],
        unit="probability",
        timeframe="7d",
        confidence=0.7,
        reasoning="test",
        evidence=["test"],
        created_at=datetime.now(timezone.utc),
        kalshi_ticker="TEST-TICKER",
    )


def _make_market(
    ticker: str = "TEST-TICKER",
    best_yes_ask: float = 0.60,
    best_no_ask: float = 0.45,
    quote_age_seconds: float = 10.0,
    quote_timestamp: datetime | None = None,
) -> MarketPrice:
    now = datetime.now(timezone.utc)
    if quote_timestamp is None:
        quote_timestamp = now - timedelta(seconds=quote_age_seconds)
    return MarketPrice(
        ticker=ticker,
        source="kalshi",
        fetched_at=now,
        quote_timestamp=quote_timestamp,
        best_yes_ask=best_yes_ask,
        best_no_ask=best_no_ask,
        yes_price=best_yes_ask,
        no_price=best_no_ask,
        derived_price_kind="midpoint",
    )


class TestStalenessGuard:
    def test_fresh_quote_processed_normally(self):
        detector = DivergenceDetector(min_edge_pct=5.0, max_quote_age_seconds=120.0)
        pred = _make_prediction(0.80)
        market = _make_market(quote_age_seconds=10.0)
        result = detector.detect([pred], [market])
        assert len(result) == 1
        assert result[0].signal != "STALE_QUOTE"

    def test_stale_quote_rejected(self):
        detector = DivergenceDetector(min_edge_pct=5.0, max_quote_age_seconds=120.0)
        pred = _make_prediction(0.80)
        market = _make_market(quote_age_seconds=200.0)
        result = detector.detect([pred], [market])
        assert len(result) == 1
        assert result[0].signal == "STALE_QUOTE"
        assert result[0].tradeability_status == "non_tradable"
        assert result[0].entry_price_is_executable is False

    def test_exactly_at_boundary_is_fresh(self):
        detector = DivergenceDetector(min_edge_pct=5.0, max_quote_age_seconds=120.0)
        pred = _make_prediction(0.80)
        # Use 119s to account for sub-second drift between market creation and detect()
        market = _make_market(quote_age_seconds=119.0)
        result = detector.detect([pred], [market])
        assert len(result) == 1
        # Just under the boundary should pass (staleness > max triggers guard)
        assert result[0].signal != "STALE_QUOTE"

    def test_fallback_to_fetched_at_when_no_quote_timestamp(self):
        detector = DivergenceDetector(min_edge_pct=5.0, max_quote_age_seconds=120.0)
        pred = _make_prediction(0.80)
        now = datetime.now(timezone.utc)
        market = MarketPrice(
            ticker="TEST-TICKER",
            source="kalshi",
            fetched_at=now - timedelta(seconds=200.0),
            quote_timestamp=None,
            best_yes_ask=0.60,
            best_no_ask=0.45,
            yes_price=0.60,
            no_price=0.45,
            derived_price_kind="midpoint",
        )
        result = detector.detect([pred], [market])
        assert len(result) == 1
        assert result[0].signal == "STALE_QUOTE"

    def test_zero_max_age_disables_guard(self):
        detector = DivergenceDetector(min_edge_pct=5.0, max_quote_age_seconds=0.0)
        pred = _make_prediction(0.80)
        market = _make_market(quote_age_seconds=9999.0)
        result = detector.detect([pred], [market])
        assert len(result) == 1
        assert result[0].signal != "STALE_QUOTE"

    def test_default_no_staleness_check(self):
        """Default detector (no max_quote_age_seconds) should not check staleness."""
        detector = DivergenceDetector(min_edge_pct=5.0)
        pred = _make_prediction(0.80)
        market = _make_market(quote_age_seconds=9999.0)
        result = detector.detect([pred], [market])
        assert len(result) == 1
        assert result[0].signal != "STALE_QUOTE"
