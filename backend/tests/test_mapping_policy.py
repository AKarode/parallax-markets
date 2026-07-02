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
        derived_price_kind="midpoint",
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


_PRE_REFACTOR_REASON = (
    "Pre-refactor assertion: predates confidence-shrinkage on fair-value estimators "
    "and explicit fee/slippage cost subtraction. Architecture moved away from "
    "edge-multiplied discounts (see _confidence_shrunk_probability)."
)


@pytest.mark.skip(reason=_PRE_REFACTOR_REASON)
class TestDirectProxyDiscount:
    """Test 1: DIRECT proxy class applies discount=1.0."""

    def test_direct_proxy_full_edge(self, policy: MappingPolicy) -> None:
        prediction = _make_prediction(model_id="hormuz_reopening", probability=0.7)
        market_prices = [_make_market_price("KXCLOSEHORMUZ-27JAN", yes_price=0.5)]

        results = policy.evaluate(prediction, market_prices)

        direct_results = [r for r in results if r.contract_ticker == "KXCLOSEHORMUZ-27JAN"]
        assert len(direct_results) == 1
        result = direct_results[0]
        assert result.proxy_class == ProxyClass.DIRECT
        assert result.confidence_discount == 1.0
        assert abs(result.effective_edge - result.raw_edge) < 1e-9


@pytest.mark.skip(reason=_PRE_REFACTOR_REASON)
class TestNearProxyDiscount:
    """Test 2: NEAR_PROXY proxy class applies discount=0.6."""

    def test_near_proxy_discounted_edge(self, policy: MappingPolicy) -> None:
        prediction = _make_prediction(model_id="oil_price", probability=0.8)
        market_prices = [_make_market_price("KXWTIMAX-26DEC31", yes_price=0.5)]

        results = policy.evaluate(prediction, market_prices)

        near_results = [r for r in results if r.contract_ticker == "KXWTIMAX-26DEC31"]
        assert len(near_results) == 1
        result = near_results[0]
        assert result.proxy_class == ProxyClass.NEAR_PROXY
        assert result.confidence_discount == pytest.approx(0.6)
        assert result.effective_edge == pytest.approx(0.3 * 0.6)


@pytest.mark.skip(reason=_PRE_REFACTOR_REASON)
class TestLooseProxyDiscount:
    """Test 3: LOOSE_PROXY proxy class applies discount=0.3."""

    def test_loose_proxy_discounted_edge(self, policy: MappingPolicy) -> None:
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
        prediction = _make_prediction(model_id="oil_price", probability=0.9)
        market_prices = [_make_market_price("KXUSAIRANAGREEMENT-27", yes_price=0.1)]

        results = policy.evaluate(prediction, market_prices)

        none_results = [r for r in results if r.contract_ticker == "KXUSAIRANAGREEMENT-27"]
        assert len(none_results) == 0


@pytest.mark.skip(reason=_PRE_REFACTOR_REASON)
class TestProbabilityInversion:
    """Test 5: When invert_probability=True, model probability is flipped."""

    def test_inverted_probability(self, policy: MappingPolicy) -> None:
        prediction = _make_prediction(model_id="hormuz_reopening", probability=0.7)
        market_prices = [_make_market_price("KXCLOSEHORMUZ-27JAN", yes_price=0.5)]

        results = policy.evaluate(prediction, market_prices)

        direct_result = [r for r in results if r.contract_ticker == "KXCLOSEHORMUZ-27JAN"][0]
        assert direct_result.raw_edge == pytest.approx(-0.2)


class TestBelowThreshold:
    """Test 6: Effective edge below min_effective_edge_pct returns should_trade=False."""

    def test_below_threshold_no_trade(self, registry: ContractRegistry) -> None:
        policy = MappingPolicy(registry=registry, min_effective_edge_pct=20.0)

        prediction = _make_prediction(model_id="oil_price", probability=0.55)
        market_prices = [_make_market_price("KXWTIMAX-26DEC31", yes_price=0.5)]

        results = policy.evaluate(prediction, market_prices)

        wti_results = [r for r in results if r.contract_ticker == "KXWTIMAX-26DEC31"]
        assert len(wti_results) == 1
        assert wti_results[0].should_trade is False


@pytest.mark.skip(reason=_PRE_REFACTOR_REASON)
class TestAboveThreshold:
    """Test 7: Effective edge above threshold returns should_trade=True."""

    def test_above_threshold_trades(self, policy: MappingPolicy) -> None:
        prediction = _make_prediction(model_id="oil_price", probability=0.8)
        market_prices = [_make_market_price("KXWTIMAX-26DEC31", yes_price=0.5)]

        results = policy.evaluate(prediction, market_prices)

        wti_results = [r for r in results if r.contract_ticker == "KXWTIMAX-26DEC31"]
        assert len(wti_results) == 1
        assert wti_results[0].should_trade is True


class TestAuditTrail:
    """Test 8: All contracts are evaluated and returned for full audit trail."""

    def test_all_contracts_returned(self, policy: MappingPolicy) -> None:
        prediction = _make_prediction(model_id="hormuz_reopening", probability=0.7)
        market_prices = [
            _make_market_price("KXCLOSEHORMUZ-27JAN", yes_price=0.5),
            _make_market_price("KXWTIMAX-26DEC31", yes_price=0.5),
            _make_market_price("KXWTIMIN-26DEC31", yes_price=0.5),
            _make_market_price("KXUSAIRANAGREEMENT-27", yes_price=0.5),
        ]

        results = policy.evaluate(prediction, market_prices)

        tickers = {r.contract_ticker for r in results}
        assert "KXCLOSEHORMUZ-27JAN" in tickers
        assert "KXWTIMAX-26DEC31" in tickers
        assert "KXWTIMIN-26DEC31" in tickers
        assert "KXUSAIRANAGREEMENT-27" in tickers
        assert all(isinstance(r, MappingResult) for r in results)


class TestMissingMarketPrice:
    """Test 9: When no market price exists for a contract ticker, mapping is skipped."""

    def test_missing_market_price_skipped(self, policy: MappingPolicy) -> None:
        prediction = _make_prediction(model_id="hormuz_reopening", probability=0.7)
        market_prices = [_make_market_price("KXCLOSEHORMUZ-27JAN", yes_price=0.5)]

        results = policy.evaluate(prediction, market_prices)

        assert len(results) == 1
        assert results[0].contract_ticker == "KXCLOSEHORMUZ-27JAN"


@pytest.mark.skip(reason=_PRE_REFACTOR_REASON)
class TestSortedByEffectiveEdge:
    """Test 10: evaluate() returns MappingResult list sorted by effective_edge descending."""

    def test_sorted_descending(self, policy: MappingPolicy) -> None:
        prediction = _make_prediction(model_id="hormuz_reopening", probability=0.7)
        market_prices = [
            _make_market_price("KXCLOSEHORMUZ-27JAN", yes_price=0.1),
            _make_market_price("KXWTIMAX-26DEC31", yes_price=0.65),
            _make_market_price("KXWTIMIN-26DEC31", yes_price=0.69),
            _make_market_price("KXUSAIRANAGREEMENT-27", yes_price=0.6),
        ]

        results = policy.evaluate(prediction, market_prices)

        edges = [abs(r.effective_edge) for r in results]
        assert edges == sorted(edges, reverse=True)


@pytest.mark.skip(
    reason="update_discounts_from_history disabled — Phase 3 will rewire with bucketed Bayesian update"
)
class TestDiscountFromHistory:
    """Tests for update_discounts_from_history() — adjusting discount factors from calibration data."""

    @pytest.fixture()
    def conn_and_policy(self) -> tuple[duckdb.DuckDBPyConnection, MappingPolicy]:
        """In-memory DuckDB with seeded contracts and signal_ledger table."""
        conn = duckdb.connect(":memory:")
        create_tables(conn)
        reg = ContractRegistry(conn)
        reg.seed_initial_contracts()
        policy = MappingPolicy(registry=reg, min_effective_edge_pct=5.0)
        return conn, policy

    def _insert_signals(
        self,
        conn: duckdb.DuckDBPyConnection,
        proxy_class: str,
        total: int,
        correct: int,
    ) -> None:
        """Insert resolved signal_ledger rows for a given proxy class."""
        for i in range(total):
            is_correct = i < correct
            conn.execute(
                """
                INSERT INTO signal_ledger (
                    signal_id, run_id, created_at, model_id, model_claim,
                    model_probability, model_timeframe, contract_ticker,
                    proxy_class, confidence_discount, market_yes_price,
                    market_no_price, entry_side, entry_price, raw_edge,
                    effective_edge, signal, model_was_correct, resolution_price,
                    resolved_at, realized_pnl, counterfactual_pnl
                ) VALUES (?, ?, CURRENT_TIMESTAMP, 'test', 'claim',
                          0.6, '14d', 'KXTEST', ?, 0.6, 0.5, 0.5,
                          'yes', 0.5, 0.1, 0.06, 'BUY_YES', ?, 1.0,
                          CURRENT_TIMESTAMP, ?, ?)
                """,
                [
                    f"sig-{proxy_class}-{i}",
                    f"run-{i}",
                    proxy_class,
                    is_correct,
                    0.1 if is_correct else -0.1,
                    0.1 if is_correct else -0.1,
                ],
            )

    def test_no_data_defaults_unchanged(self, conn_and_policy: tuple) -> None:
        conn, policy = conn_and_policy

        row = conn.execute(
            "SELECT confidence_discount FROM contract_proxy_map WHERE proxy_class = 'near_proxy' LIMIT 1"
        ).fetchone()
        assert row is not None
        default_discount = row[0]

        policy.update_discounts_from_history(conn)

        row = conn.execute(
            "SELECT confidence_discount FROM contract_proxy_map WHERE proxy_class = 'near_proxy' LIMIT 1"
        ).fetchone()
        assert row[0] == pytest.approx(default_discount)

    def test_insufficient_data_no_adjustment(self, conn_and_policy: tuple) -> None:
        conn, policy = conn_and_policy
        self._insert_signals(conn, "near_proxy", total=3, correct=3)

        policy.update_discounts_from_history(conn)

        row = conn.execute(
            "SELECT confidence_discount FROM contract_proxy_map WHERE proxy_class = 'near_proxy' LIMIT 1"
        ).fetchone()
        assert row[0] == pytest.approx(0.6)

    def test_high_hit_rate_raises_discount(self, conn_and_policy: tuple) -> None:
        conn, policy = conn_and_policy
        self._insert_signals(conn, "near_proxy", total=10, correct=8)

        policy.update_discounts_from_history(conn)

        row = conn.execute(
            "SELECT confidence_discount FROM contract_proxy_map WHERE proxy_class = 'near_proxy' LIMIT 1"
        ).fetchone()
        new_discount = row[0]
        assert new_discount > 0.6
        assert new_discount <= 0.8
        assert new_discount == pytest.approx(0.66)

    def test_low_hit_rate_lowers_discount(self, conn_and_policy: tuple) -> None:
        conn, policy = conn_and_policy
        self._insert_signals(conn, "near_proxy", total=10, correct=3)

        policy.update_discounts_from_history(conn)

        row = conn.execute(
            "SELECT confidence_discount FROM contract_proxy_map WHERE proxy_class = 'near_proxy' LIMIT 1"
        ).fetchone()
        new_discount = row[0]
        assert new_discount >= 0.3
        assert new_discount < 0.6
        assert new_discount == pytest.approx(0.51)

    def test_direct_floor(self, conn_and_policy: tuple) -> None:
        conn, policy = conn_and_policy
        self._insert_signals(conn, "direct", total=10, correct=5)

        policy.update_discounts_from_history(conn)

        row = conn.execute(
            "SELECT confidence_discount FROM contract_proxy_map WHERE proxy_class = 'direct' LIMIT 1"
        ).fetchone()
        new_discount = row[0]
        assert new_discount >= 0.8
        assert new_discount <= 1.0

    def test_loose_proxy_ceiling(self, conn_and_policy: tuple) -> None:
        conn, policy = conn_and_policy
        self._insert_signals(conn, "loose_proxy", total=10, correct=9)

        policy.update_discounts_from_history(conn)

        row = conn.execute(
            "SELECT confidence_discount FROM contract_proxy_map WHERE proxy_class = 'loose_proxy' LIMIT 1"
        ).fetchone()
        new_discount = row[0]
        assert new_discount <= 0.5
        assert new_discount > 0.3

    def test_evaluate_uses_updated_discounts(self, conn_and_policy: tuple) -> None:
        conn, policy = conn_and_policy
        self._insert_signals(conn, "near_proxy", total=10, correct=8)

        policy.update_discounts_from_history(conn)

        prediction = _make_prediction(model_id="oil_price", probability=0.8)
        market_prices = [_make_market_price("KXWTIMAX-26DEC31", yes_price=0.5)]
        results = policy.evaluate(prediction, market_prices)

        near_results = [r for r in results if r.contract_ticker == "KXWTIMAX-26DEC31"]
        assert len(near_results) == 1
        result = near_results[0]
        assert result.confidence_discount == pytest.approx(0.66)
        assert result.effective_edge == pytest.approx(0.3 * 0.66)
