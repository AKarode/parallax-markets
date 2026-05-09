"""Tests for proxy-class confidence discount application in MappingPolicy."""

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


@pytest.fixture()
def policy(registry: ContractRegistry) -> MappingPolicy:
    """MappingPolicy with default 5% threshold."""
    return MappingPolicy(registry=registry, min_effective_edge_pct=5.0)


class TestLooseProxyDiscount:
    """LOOSE_PROXY contracts should have confidence_discount < 1.0 applied."""

    def test_loose_proxy_has_discount_applied(self, policy: MappingPolicy) -> None:
        """LOOSE_PROXY mapping should have confidence_discount=0.3."""
        prediction = _make_prediction(model_id="hormuz_reopening", probability=0.7)
        market_prices = [
            _make_market_price("KXCLOSEHORMUZ-27JAN", yes_price=0.5),
            _make_market_price("KXWTIMAX-26DEC31", yes_price=0.5),
            _make_market_price("KXWTIMIN-26DEC31", yes_price=0.5),
            _make_market_price("KXUSAIRANAGREEMENT-27", yes_price=0.5),
        ]

        results = policy.evaluate(prediction, market_prices)

        loose_results = [r for r in results if r.proxy_class == ProxyClass.LOOSE_PROXY]
        assert len(loose_results) > 0

        for result in loose_results:
            assert result.confidence_discount == pytest.approx(0.3)
            assert result.confidence_discount < 1.0

    def test_loose_proxy_effective_edge_is_discounted(self, policy: MappingPolicy) -> None:
        """LOOSE_PROXY effective_edge should be net_edge * 0.3."""
        prediction = _make_prediction(model_id="hormuz_reopening", probability=0.7)
        market_prices = [
            _make_market_price("KXWTIMAX-26DEC31", yes_price=0.5),
        ]

        results = policy.evaluate(prediction, market_prices)

        assert len(results) == 1
        result = results[0]
        assert result.proxy_class == ProxyClass.LOOSE_PROXY
        assert result.confidence_discount == pytest.approx(0.3)
        assert result.effective_edge == pytest.approx(result.net_edge * 0.3)


class TestNearProxyDiscount:
    """NEAR_PROXY contracts should have confidence_discount=0.65 applied."""

    def test_near_proxy_has_discount_applied(self, policy: MappingPolicy) -> None:
        """NEAR_PROXY mapping should have confidence_discount=0.65."""
        prediction = _make_prediction(model_id="ceasefire", probability=0.7)
        market_prices = [
            _make_market_price("KXUSAIRANAGREEMENT-27", yes_price=0.5),
        ]

        results = policy.evaluate(prediction, market_prices)

        near_results = [r for r in results if r.proxy_class == ProxyClass.NEAR_PROXY]
        assert len(near_results) == 1

        result = near_results[0]
        assert result.confidence_discount == pytest.approx(0.65)
        assert result.effective_edge == pytest.approx(result.net_edge * 0.65)


class TestDirectProxyDiscount:
    """DIRECT proxy should have confidence_discount=1.0 (no discount)."""

    def test_direct_proxy_full_edge(self, policy: MappingPolicy) -> None:
        """DIRECT mapping should have confidence_discount=1.0."""
        prediction = _make_prediction(model_id="hormuz_reopening", probability=0.7)
        market_prices = [
            _make_market_price("KXCLOSEHORMUZ-27JAN", yes_price=0.5),
        ]

        results = policy.evaluate(prediction, market_prices)

        direct_results = [r for r in results if r.proxy_class == ProxyClass.DIRECT]
        assert len(direct_results) == 1

        result = direct_results[0]
        assert result.confidence_discount == pytest.approx(1.0)
        assert result.effective_edge == pytest.approx(result.net_edge * 1.0)


class TestDiscountValuesMatch:
    """Verify the exact discount values for each proxy class."""

    def test_discount_values(self, registry: ContractRegistry) -> None:
        """Check that discount_map values are applied correctly."""
        conn = registry._conn
        rows = conn.execute(
            """
            SELECT proxy_class, confidence_discount
            FROM contract_proxy_map
            WHERE proxy_class IN ('direct', 'near_proxy', 'loose_proxy')
            """
        ).fetchall()

        discounts = {row[0]: row[1] for row in rows}

        assert discounts.get("direct") == pytest.approx(1.0)
        assert discounts.get("near_proxy") == pytest.approx(0.65)
        assert discounts.get("loose_proxy") == pytest.approx(0.3)
