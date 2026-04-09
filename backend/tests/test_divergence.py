"""Tests for divergence detector — signal generation and edge calculation."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from parallax.divergence.detector import Divergence, DivergenceDetector
from parallax.markets.schemas import MarketPrice
from parallax.prediction.schemas import PredictionOutput


def make_prediction(
    probability: float,
    model_id: str = "test_model",
    kalshi_ticker: str | None = "KXTEST",
) -> PredictionOutput:
    return PredictionOutput(
        model_id=model_id,
        prediction_type="test",
        probability=probability,
        direction="increase",
        magnitude_range=[0.0, 1.0],
        unit="probability",
        timeframe="7d",
        confidence=probability,
        reasoning="Test reasoning",
        evidence=["Test evidence"],
        created_at=datetime.now(timezone.utc),
        kalshi_ticker=kalshi_ticker,
    )


def make_market_price(
    yes_price: float,
    ticker: str = "KXTEST",
    source: str = "kalshi",
) -> MarketPrice:
    no_price = 1.0 - yes_price
    return MarketPrice(
        ticker=ticker,
        source=source,
        best_yes_bid=max(yes_price - 0.01, 0.0),
        best_yes_ask=yes_price,
        best_no_bid=max(no_price - 0.01, 0.0),
        best_no_ask=no_price,
        yes_price=yes_price,
        no_price=no_price,
        derived_price_kind="midpoint",
        volume=10000,
        fetched_at=datetime.now(timezone.utc),
    )


@pytest.fixture()
def detector():
    return DivergenceDetector(min_edge_pct=5.0)


class TestDivergenceDetection:
    """Test core divergence detection logic."""

    def test_buy_yes_strong(self, detector):
        """Model 80% vs market 60% -> BUY_YES, strong (20% edge)."""
        pred = make_prediction(0.80)
        market = make_market_price(0.60)
        divs = detector.detect([pred], [market])

        assert len(divs) == 1
        d = divs[0]
        assert d.signal == "BUY_YES"
        assert d.strength == "strong"
        assert d.edge == pytest.approx(0.20, abs=0.01)
        assert d.edge_pct == pytest.approx(20.0, abs=1.0)

    def test_buy_no_strong(self, detector):
        """Model 30% vs market 70% -> BUY_NO, strong (40% edge)."""
        pred = make_prediction(0.30)
        market = make_market_price(0.70)
        divs = detector.detect([pred], [market])

        assert len(divs) == 1
        d = divs[0]
        assert d.signal == "BUY_NO"
        assert d.strength == "strong"
        assert d.edge == pytest.approx(-0.40, abs=0.01)

    def test_hold_at_threshold(self, detector):
        """Model 54% vs market 50% -> HOLD (4% edge, below 5% threshold)."""
        pred = make_prediction(0.54)
        market = make_market_price(0.50)
        divs = detector.detect([pred], [market])

        assert len(divs) == 1
        d = divs[0]
        assert d.signal == "HOLD"

    def test_hold_within_threshold(self, detector):
        """Model 52% vs market 50% -> HOLD (2% edge, below threshold)."""
        pred = make_prediction(0.52)
        market = make_market_price(0.50)
        divs = detector.detect([pred], [market])

        assert len(divs) == 1
        assert divs[0].signal == "HOLD"

    def test_moderate_edge(self, detector):
        """Model 72% vs market 60% -> BUY_YES, moderate (12% edge)."""
        pred = make_prediction(0.72)
        market = make_market_price(0.60)
        divs = detector.detect([pred], [market])

        assert len(divs) == 1
        assert divs[0].strength == "moderate"

    def test_weak_edge(self, detector):
        """Model 66% vs market 60% -> BUY_YES, weak (6% edge)."""
        pred = make_prediction(0.66)
        market = make_market_price(0.60)
        divs = detector.detect([pred], [market])

        assert len(divs) == 1
        assert divs[0].strength == "weak"


class TestDivergenceMatching:
    """Test prediction-to-market matching logic."""

    def test_no_matching_markets(self, detector):
        """Prediction with no matching market ticker -> no divergence."""
        pred = make_prediction(0.80, kalshi_ticker="KXUNKNOWN")
        market = make_market_price(0.60, ticker="KXOTHER")
        divs = detector.detect([pred], [market])
        assert len(divs) == 0

    def test_empty_predictions(self, detector):
        """Empty predictions list -> no divergences."""
        market = make_market_price(0.60)
        divs = detector.detect([], [market])
        assert len(divs) == 0

    def test_empty_markets(self, detector):
        """Empty markets list -> no divergences."""
        pred = make_prediction(0.80)
        divs = detector.detect([pred], [])
        assert len(divs) == 0

    def test_multiple_predictions(self, detector):
        """Multiple predictions with matching markets."""
        pred1 = make_prediction(0.80, model_id="oil", kalshi_ticker="KXOIL")
        pred2 = make_prediction(0.30, model_id="ceasefire", kalshi_ticker="KXCEASEFIRE")
        market1 = make_market_price(0.60, ticker="KXOIL")
        market2 = make_market_price(0.70, ticker="KXCEASEFIRE")

        divs = detector.detect([pred1, pred2], [market1, market2])
        assert len(divs) == 2

        oil_div = next(d for d in divs if d.model_id == "oil")
        assert oil_div.signal == "BUY_YES"

        ceasefire_div = next(d for d in divs if d.model_id == "ceasefire")
        assert ceasefire_div.signal == "BUY_NO"

    def test_polymarket_matching(self, detector):
        """Match via polymarket_id."""
        pred = make_prediction(0.80, kalshi_ticker=None)
        pred.polymarket_id = "poly-iran"
        market = make_market_price(0.60, ticker="poly-iran", source="polymarket")

        divs = detector.detect([pred], [market])
        assert len(divs) == 1
        assert divs[0].signal == "BUY_YES"


class TestCustomThreshold:
    """Test custom minimum edge threshold."""

    def test_higher_threshold(self):
        """With 10% threshold, 8% edge should be HOLD."""
        detector = DivergenceDetector(min_edge_pct=10.0)
        pred = make_prediction(0.68)
        market = make_market_price(0.60)
        divs = detector.detect([pred], [market])
        assert divs[0].signal == "HOLD"

    def test_zero_threshold(self):
        """With 0% threshold, any difference triggers signal."""
        detector = DivergenceDetector(min_edge_pct=0.0)
        pred = make_prediction(0.51)
        market = make_market_price(0.50)
        divs = detector.detect([pred], [market])
        assert divs[0].signal == "BUY_YES"
