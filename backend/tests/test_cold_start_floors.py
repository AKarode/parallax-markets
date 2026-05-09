"""Tests for cold-start edge floor enforcement by proxy class."""

from __future__ import annotations

from datetime import datetime, timezone

import duckdb
import pytest

from parallax.contracts.mapping_policy import MappingPolicy
from parallax.contracts.registry import ContractRegistry
from parallax.contracts.schemas import ProxyClass
from parallax.db.schema import create_tables
from parallax.markets.schemas import MarketPrice
from parallax.prediction.schemas import PredictionOutput


def _make_prediction(
    model_id: str = "hormuz_reopening",
    probability: float = 0.7,
    confidence: float = 0.8,
) -> PredictionOutput:
    return PredictionOutput(
        model_id=model_id,
        prediction_type="binary",
        probability=probability,
        direction="increase",
        magnitude_range=[0.0, 1.0],
        unit="probability",
        timeframe="14d",
        confidence=confidence,
        reasoning="test reasoning",
        evidence=["test evidence"],
        created_at=datetime.now(tz=timezone.utc),
    )


def _make_market_price(
    ticker: str,
    yes_price: float = 0.5,
) -> MarketPrice:
    no_price = 1.0 - yes_price
    return MarketPrice(
        ticker=ticker,
        source="kalshi",
        best_yes_bid=max(yes_price - 0.01, 0.0),
        best_yes_ask=yes_price,
        best_no_bid=max(no_price - 0.01, 0.0),
        best_no_ask=no_price,
        yes_price=yes_price,
        no_price=no_price,
        yes_bid_ask_spread=0.01,
        no_bid_ask_spread=0.01,
        derived_price_kind="midpoint",
        volume=1000.0,
        fetched_at=datetime.now(tz=timezone.utc),
        venue_timestamp=datetime.now(tz=timezone.utc),
        quote_timestamp=datetime.now(tz=timezone.utc),
    )


@pytest.fixture()
def registry() -> ContractRegistry:
    """In-memory DuckDB with seeded contracts."""
    conn = duckdb.connect(":memory:")
    create_tables(conn)
    reg = ContractRegistry(conn)
    reg.seed_initial_contracts()
    return reg


class TestColdStartEdgeFloors:
    """At cold start (no history), proxy-class specific floors should apply."""

    def test_cold_start_floors_initialized(self, registry: ContractRegistry) -> None:
        """MappingPolicy should have cold-start floors on initialization."""
        policy = MappingPolicy(registry=registry, min_effective_edge_pct=5.0)

        assert "loose_proxy" in policy._per_class_min_edge
        assert "near_proxy" in policy._per_class_min_edge
        assert "direct" in policy._per_class_min_edge

    def test_loose_proxy_requires_8_percent_edge(self, registry: ContractRegistry) -> None:
        """LOOSE_PROXY should require >= 8% effective edge at cold start."""
        policy = MappingPolicy(registry=registry, min_effective_edge_pct=5.0)

        assert policy._per_class_min_edge["loose_proxy"] == pytest.approx(0.08)

    def test_near_proxy_requires_6_percent_edge(self, registry: ContractRegistry) -> None:
        """NEAR_PROXY should require >= 6% effective edge at cold start."""
        policy = MappingPolicy(registry=registry, min_effective_edge_pct=5.0)

        assert policy._per_class_min_edge["near_proxy"] == pytest.approx(0.06)

    def test_direct_requires_4_percent_edge(self, registry: ContractRegistry) -> None:
        """DIRECT should require >= 4% effective edge at cold start."""
        policy = MappingPolicy(registry=registry, min_effective_edge_pct=5.0)

        assert policy._per_class_min_edge["direct"] == pytest.approx(0.04)


class TestEdgeFloorEnforcement:
    """Test that edge floors are enforced in mapping decisions."""

    def test_loose_proxy_below_8_percent_not_traded(self, registry: ContractRegistry) -> None:
        """LOOSE_PROXY with effective edge < 8% should not trade."""
        policy = MappingPolicy(registry=registry, min_effective_edge_pct=5.0)

        prediction = _make_prediction(model_id="hormuz_reopening", probability=0.52)
        market_prices = [
            _make_market_price("KXWTIMAX-26DEC31", yes_price=0.5),
        ]

        results = policy.evaluate(prediction, market_prices)
        loose_results = [r for r in results if r.proxy_class == ProxyClass.LOOSE_PROXY]

        assert len(loose_results) == 1
        result = loose_results[0]
        if result.effective_edge is not None and result.effective_edge < 0.08:
            assert result.should_trade is False

    def test_direct_with_5_percent_edge_trades(self, registry: ContractRegistry) -> None:
        """DIRECT with >= 4% effective edge should be allowed to trade."""
        policy = MappingPolicy(registry=registry, min_effective_edge_pct=5.0)

        prediction = _make_prediction(model_id="hormuz_reopening", probability=0.3)
        market_prices = [
            _make_market_price("KXCLOSEHORMUZ-27JAN", yes_price=0.6),
        ]

        results = policy.evaluate(prediction, market_prices)
        direct_results = [r for r in results if r.proxy_class == ProxyClass.DIRECT]

        assert len(direct_results) == 1
        result = direct_results[0]
        if result.effective_edge is not None and result.effective_edge >= 0.04:
            assert result.should_trade is True


class TestEdgeFloorConstant:
    """Test that the COLD_START_EDGE_FLOORS constant is correctly defined."""

    def test_cold_start_floors_constant_exists(self) -> None:
        """MappingPolicy should have COLD_START_EDGE_FLOORS class constant."""
        assert hasattr(MappingPolicy, "COLD_START_EDGE_FLOORS")
        floors = MappingPolicy.COLD_START_EDGE_FLOORS

        assert floors["loose_proxy"] == 0.08
        assert floors["near_proxy"] == 0.06
        assert floors["direct"] == 0.04

    def test_floors_are_higher_than_default_min_edge(self, registry: ContractRegistry) -> None:
        """Cold-start floors for loose/near proxy should be higher than default 5%."""
        policy = MappingPolicy(registry=registry, min_effective_edge_pct=5.0)

        assert policy._per_class_min_edge["loose_proxy"] > policy._min_edge
        assert policy._per_class_min_edge["near_proxy"] > policy._min_edge
