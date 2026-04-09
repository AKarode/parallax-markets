"""Tests for cost-aware divergence detection."""
from datetime import datetime, timezone
import pytest
from parallax.costs.fee_model import CostModel
from parallax.divergence.detector import DivergenceDetector, Divergence
from parallax.markets.schemas import MarketPrice
from parallax.prediction.schemas import PredictionOutput


def _make_prediction(probability: float = 0.70) -> PredictionOutput:
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
) -> MarketPrice:
    now = datetime.now(timezone.utc)
    return MarketPrice(
        ticker=ticker,
        source="kalshi",
        fetched_at=now,
        quote_timestamp=now,
        best_yes_ask=best_yes_ask,
        best_no_ask=best_no_ask,
        yes_price=best_yes_ask,
        no_price=best_no_ask,
        derived_price_kind="midpoint",
    )


class TestDetectorWithCosts:
    def test_no_cost_model_preserves_old_behavior(self):
        detector = DivergenceDetector(min_edge_pct=5.0)
        pred = _make_prediction(0.70)
        market = _make_market(best_yes_ask=0.60)
        result = detector.detect([pred], [market])
        assert len(result) == 1
        assert result[0].signal == "BUY_YES"

    def test_cost_model_filters_marginal_edge(self):
        cost_model = CostModel()  # 0.08 total cost
        detector = DivergenceDetector(min_edge_pct=5.0, cost_model=cost_model)
        # 0.68 - 0.60 = 0.08 raw edge, minus 0.08 cost = 0.00 net edge < 0.05 min
        pred = _make_prediction(0.68)
        market = _make_market(best_yes_ask=0.60)
        result = detector.detect([pred], [market])
        assert len(result) == 1
        assert result[0].signal == "HOLD"

    def test_cost_model_allows_strong_edge(self):
        cost_model = CostModel()  # 0.08 total cost
        detector = DivergenceDetector(min_edge_pct=5.0, cost_model=cost_model)
        # 0.80 - 0.60 = 0.20 raw edge, minus 0.08 = 0.12 net edge > 0.05 min
        pred = _make_prediction(0.80)
        market = _make_market(best_yes_ask=0.60)
        result = detector.detect([pred], [market])
        assert len(result) == 1
        assert result[0].signal == "BUY_YES"

    def test_divergence_has_gross_and_net_edge(self):
        cost_model = CostModel()
        detector = DivergenceDetector(min_edge_pct=5.0, cost_model=cost_model)
        pred = _make_prediction(0.80)
        market = _make_market(best_yes_ask=0.60)
        result = detector.detect([pred], [market])
        assert len(result) == 1
        div = result[0]
        assert div.gross_edge == pytest.approx(0.20)
        assert div.net_edge == pytest.approx(0.12)

    def test_zero_cost_model_same_as_none(self):
        zero_cost = CostModel(taker_fee_per_contract=0.0, slippage_buffer=0.0)
        detector_with = DivergenceDetector(min_edge_pct=5.0, cost_model=zero_cost)
        detector_without = DivergenceDetector(min_edge_pct=5.0)
        pred = _make_prediction(0.70)
        market = _make_market(best_yes_ask=0.60)
        r1 = detector_with.detect([pred], [market])
        r2 = detector_without.detect([pred], [market])
        assert r1[0].signal == r2[0].signal
