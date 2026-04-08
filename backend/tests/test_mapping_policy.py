"""Tests for MappingPolicy decision logic."""

from __future__ import annotations

from datetime import datetime, timezone

import duckdb
import pytest

from parallax.contracts.mapping_policy import MappingPolicy
from parallax.contracts.registry import ContractRegistry, INITIAL_CONTRACTS
from parallax.contracts.schemas import MappingResult, ProxyClass
from parallax.db.schema import create_tables
from parallax.markets.schemas import MarketPrice
from parallax.prediction.schemas import PredictionOutput


def _make_prediction(
    model_id: str = "hormuz_reopening",
    probability: float = 0.7,
) -> PredictionOutput:
    return PredictionOutput(
        model_id=model_id,
        prediction_type="binary",
        probability=probability,
        direction="increase",
        magnitude_range=[0.0, 1.0],
        unit="probability",
        timeframe="14d",
        confidence=0.8,
        reasoning="test reasoning",
        evidence=["test evidence"],
        created_at=datetime.now(tz=timezone.utc),
    )


def _make_market_price(
    ticker: str,
    yes_price: float = 0.5,
) -> MarketPrice:
    return MarketPrice(
        ticker=ticker,
        source="kalshi",
        yes_price=yes_price,
        no_price=1.0 - yes_price,
        volume=1000.0,
        fetched_at=datetime.now(tz=timezone.utc),
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


class TestDirectProxyDiscount:
    """Test 1: DIRECT proxy class applies discount=1.0."""

    def test_direct_proxy_full_edge(self, policy: MappingPolicy) -> None:
        # KXCLOSEHORMUZ-27JAN is DIRECT for hormuz_reopening (invert=True)
        # Model prob 0.7, inverted -> model_prob = 0.3
        # Market yes_price = 0.5
        # raw_edge = 0.3 - 0.5 = -0.2
        # discount = 1.0 (DIRECT)
        # effective_edge = -0.2 * 1.0 = -0.2
        prediction = _make_prediction(model_id="hormuz_reopening", probability=0.7)
        market_prices = [_make_market_price("KXCLOSEHORMUZ-27JAN", yes_price=0.5)]

        results = policy.evaluate(prediction, market_prices)

        direct_results = [r for r in results if r.contract_ticker == "KXCLOSEHORMUZ-27JAN"]
        assert len(direct_results) == 1
        result = direct_results[0]
        assert result.proxy_class == ProxyClass.DIRECT
        assert result.confidence_discount == 1.0
        assert abs(result.effective_edge - result.raw_edge) < 1e-9


class TestNearProxyDiscount:
    """Test 2: NEAR_PROXY proxy class applies discount=0.6."""

    def test_near_proxy_discounted_edge(self, policy: MappingPolicy) -> None:
        # KXWTIMAX-26DEC31 is NEAR_PROXY for oil_price
        # Model prob 0.8, invert=False
        # Market yes_price = 0.5
        # raw_edge = 0.8 - 0.5 = 0.3
        # discount = 0.6 (NEAR_PROXY)
        # effective_edge = 0.3 * 0.6 = 0.18
        prediction = _make_prediction(model_id="oil_price", probability=0.8)
        market_prices = [_make_market_price("KXWTIMAX-26DEC31", yes_price=0.5)]

        results = policy.evaluate(prediction, market_prices)

        near_results = [r for r in results if r.contract_ticker == "KXWTIMAX-26DEC31"]
        assert len(near_results) == 1
        result = near_results[0]
        assert result.proxy_class == ProxyClass.NEAR_PROXY
        assert result.confidence_discount == pytest.approx(0.6)
        assert result.effective_edge == pytest.approx(0.3 * 0.6)


class TestLooseProxyDiscount:
    """Test 3: LOOSE_PROXY proxy class applies discount=0.3."""

    def test_loose_proxy_discounted_edge(self, policy: MappingPolicy) -> None:
        # KXWTIMAX-26DEC31 is LOOSE_PROXY for hormuz_reopening
        # Model prob 0.7, invert=False
        # Market yes_price = 0.5
        # raw_edge = 0.7 - 0.5 = 0.2
        # discount = 0.3 (LOOSE_PROXY)
        # effective_edge = 0.2 * 0.3 = 0.06
        prediction = _make_prediction(model_id="hormuz_reopening", probability=0.7)
        market_prices = [
            _make_market_price("KXCLOSEHORMUZ-27JAN", yes_price=0.5),
            _make_market_price("KXWTIMAX-26DEC31", yes_price=0.5),
            _make_market_price("KXWTIMIN-26DEC31", yes_price=0.5),
            _make_market_price("KXUSAIRANAGREEMENT-27", yes_price=0.5),
        ]

        results = policy.evaluate(prediction, market_prices)

        loose_results = [r for r in results if r.contract_ticker == "KXWTIMAX-26DEC31"]
        assert len(loose_results) == 1
        result = loose_results[0]
        assert result.proxy_class == ProxyClass.LOOSE_PROXY
        assert result.confidence_discount == pytest.approx(0.3)
        assert result.effective_edge == pytest.approx(0.2 * 0.3)


class TestNoneProxyRejected:
    """Test 4: NONE proxy class always returns should_trade=False."""

    def test_none_proxy_never_traded(self, policy: MappingPolicy) -> None:
        # KXUSAIRANAGREEMENT-27 has oil_price=NONE
        # get_contracts_for_model filters out NONE, so it should not appear
        prediction = _make_prediction(model_id="oil_price", probability=0.9)
        market_prices = [_make_market_price("KXUSAIRANAGREEMENT-27", yes_price=0.1)]

        results = policy.evaluate(prediction, market_prices)

        none_results = [r for r in results if r.contract_ticker == "KXUSAIRANAGREEMENT-27"]
        # NONE proxy contracts are filtered out by registry, should not appear in results
        assert len(none_results) == 0


class TestProbabilityInversion:
    """Test 5: When invert_probability=True, model probability is flipped."""

    def test_inverted_probability(self, policy: MappingPolicy) -> None:
        # KXCLOSEHORMUZ-27JAN has hormuz_reopening invert=True
        # Model predicts reopening prob=0.7, but contract is about CLOSURE
        # So model_prob = 1.0 - 0.7 = 0.3 (closure probability)
        # Market yes_price = 0.5
        # raw_edge = 0.3 - 0.5 = -0.2
        prediction = _make_prediction(model_id="hormuz_reopening", probability=0.7)
        market_prices = [_make_market_price("KXCLOSEHORMUZ-27JAN", yes_price=0.5)]

        results = policy.evaluate(prediction, market_prices)

        direct_result = [r for r in results if r.contract_ticker == "KXCLOSEHORMUZ-27JAN"][0]
        assert direct_result.raw_edge == pytest.approx(-0.2)


class TestBelowThreshold:
    """Test 6: Effective edge below min_effective_edge_pct returns should_trade=False."""

    def test_below_threshold_no_trade(self, registry: ContractRegistry) -> None:
        # Use 20% threshold to make it easy to be below
        policy = MappingPolicy(registry=registry, min_effective_edge_pct=20.0)

        # KXWTIMAX-26DEC31 is NEAR_PROXY for oil_price
        # Model prob 0.55, market 0.5
        # raw_edge = 0.05, effective = 0.05 * 0.6 = 0.03 -> 3% < 20%
        prediction = _make_prediction(model_id="oil_price", probability=0.55)
        market_prices = [_make_market_price("KXWTIMAX-26DEC31", yes_price=0.5)]

        results = policy.evaluate(prediction, market_prices)

        wti_results = [r for r in results if r.contract_ticker == "KXWTIMAX-26DEC31"]
        assert len(wti_results) == 1
        assert wti_results[0].should_trade is False


class TestAboveThreshold:
    """Test 7: Effective edge above threshold returns should_trade=True."""

    def test_above_threshold_trades(self, policy: MappingPolicy) -> None:
        # KXWTIMAX-26DEC31 is NEAR_PROXY for oil_price
        # Model prob 0.8, market 0.5
        # raw_edge = 0.3, effective = 0.3 * 0.6 = 0.18 -> 18% > 5%
        prediction = _make_prediction(model_id="oil_price", probability=0.8)
        market_prices = [_make_market_price("KXWTIMAX-26DEC31", yes_price=0.5)]

        results = policy.evaluate(prediction, market_prices)

        wti_results = [r for r in results if r.contract_ticker == "KXWTIMAX-26DEC31"]
        assert len(wti_results) == 1
        assert wti_results[0].should_trade is True


class TestAuditTrail:
    """Test 8: All contracts are evaluated and returned for full audit trail."""

    def test_all_contracts_returned(self, policy: MappingPolicy) -> None:
        # hormuz_reopening has mappings to 3 contracts (DIRECT, LOOSE_PROXY, LOOSE_PROXY)
        # NONE contracts are excluded by registry.get_contracts_for_model
        prediction = _make_prediction(model_id="hormuz_reopening", probability=0.7)
        market_prices = [
            _make_market_price("KXCLOSEHORMUZ-27JAN", yes_price=0.5),
            _make_market_price("KXWTIMAX-26DEC31", yes_price=0.5),
            _make_market_price("KXWTIMIN-26DEC31", yes_price=0.5),
            _make_market_price("KXUSAIRANAGREEMENT-27", yes_price=0.5),
        ]

        results = policy.evaluate(prediction, market_prices)

        # hormuz_reopening maps to: KXCLOSEHORMUZ (DIRECT), KXWTIMAX (LOOSE),
        # KXWTIMIN (LOOSE), KXUSAIRANAGREEMENT (LOOSE)
        tickers = {r.contract_ticker for r in results}
        assert "KXCLOSEHORMUZ-27JAN" in tickers
        assert "KXWTIMAX-26DEC31" in tickers
        assert "KXWTIMIN-26DEC31" in tickers
        assert "KXUSAIRANAGREEMENT-27" in tickers
        # All results are MappingResult instances
        assert all(isinstance(r, MappingResult) for r in results)


class TestMissingMarketPrice:
    """Test 9: When no market price exists for a contract ticker, mapping is skipped."""

    def test_missing_market_price_skipped(self, policy: MappingPolicy) -> None:
        prediction = _make_prediction(model_id="hormuz_reopening", probability=0.7)
        # Only provide market price for one of the contracts
        market_prices = [_make_market_price("KXCLOSEHORMUZ-27JAN", yes_price=0.5)]

        results = policy.evaluate(prediction, market_prices)

        # Should only have the one with a market price
        assert len(results) == 1
        assert results[0].contract_ticker == "KXCLOSEHORMUZ-27JAN"


class TestSortedByEffectiveEdge:
    """Test 10: evaluate() returns MappingResult list sorted by effective_edge descending."""

    def test_sorted_descending(self, policy: MappingPolicy) -> None:
        prediction = _make_prediction(model_id="hormuz_reopening", probability=0.7)
        # Give different market prices to create different edges
        market_prices = [
            _make_market_price("KXCLOSEHORMUZ-27JAN", yes_price=0.1),  # large edge
            _make_market_price("KXWTIMAX-26DEC31", yes_price=0.65),  # small edge
            _make_market_price("KXWTIMIN-26DEC31", yes_price=0.69),  # tiny edge
            _make_market_price("KXUSAIRANAGREEMENT-27", yes_price=0.6),  # medium edge
        ]

        results = policy.evaluate(prediction, market_prices)

        # Should be sorted by abs(effective_edge) descending
        edges = [abs(r.effective_edge) for r in results]
        assert edges == sorted(edges, reverse=True)
