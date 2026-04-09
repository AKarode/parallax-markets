"""Mapping policy for prediction-to-contract alignment with fair-value gating."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import duckdb

from parallax.contracts.registry import ContractRegistry
from parallax.contracts.schemas import (
    ContractFamily,
    FairValueEstimate,
    MappingCostInputs,
    MappingResult,
    MarketStalenessPolicy,
    ProxyClass,
)
from parallax.markets.schemas import MarketPrice
from parallax.prediction.schemas import PredictionOutput

logger = logging.getLogger(__name__)


class MappingPolicy:
    """Decides whether and how to map a prediction to tradeable contracts."""

    DEFAULT_OIL_MOVE_SCALE_USD = 8.0

    def __init__(
        self,
        registry: ContractRegistry,
        min_effective_edge_pct: float = 5.0,
        default_cost_inputs: MappingCostInputs | None = None,
        default_staleness_policy: MarketStalenessPolicy | None = None,
    ) -> None:
        self._registry = registry
        self._min_edge = min_effective_edge_pct / 100.0
        self._per_class_min_edge: dict[str, float] = {}
        self._default_cost_inputs = default_cost_inputs or MappingCostInputs()
        self._default_staleness_policy = (
            default_staleness_policy or MarketStalenessPolicy()
        )

    def evaluate(
        self,
        prediction: PredictionOutput,
        market_prices: list[MarketPrice],
        *,
        cost_inputs: MappingCostInputs | None = None,
        staleness_policy: MarketStalenessPolicy | None = None,
        evaluated_at: datetime | None = None,
    ) -> list[MappingResult]:
        market_by_ticker = {market.ticker: market for market in market_prices}
        candidates = self._registry.get_contracts_for_model(prediction.model_id)
        results: list[MappingResult] = []
        evaluation_time = evaluated_at or datetime.now(timezone.utc)

        for contract, proxy_class, _legacy_discount, invert in candidates:
            market = market_by_ticker.get(contract.ticker)
            if market is None:
                logger.debug("No market price for %s, skipping", contract.ticker)
                continue

            contract_family = self._classify_contract_family(contract)
            resolved_costs = self._resolve_cost_inputs(contract.metadata, cost_inputs)
            resolved_staleness = self._resolve_staleness_policy(
                contract.metadata,
                staleness_policy,
            )
            quote_timestamp, quote_age_seconds = self._resolve_quote_age(
                market,
                evaluation_time,
                resolved_staleness,
            )

            fair_value = self._estimate_fair_value(
                prediction=prediction,
                proxy_class=proxy_class,
                contract_family=contract_family,
                invert=invert,
                contract_metadata=contract.metadata or {},
            )
            if fair_value is None:
                results.append(
                    self._build_non_tradable_result(
                        prediction_model_id=prediction.model_id,
                        contract_ticker=contract.ticker,
                        proxy_class=proxy_class,
                        contract_family=contract_family,
                        estimator_name=None,
                        fair_value_yes=None,
                        fair_value_no=None,
                        quote_timestamp=quote_timestamp,
                        quote_age_seconds=quote_age_seconds,
                        staleness_threshold_seconds=resolved_staleness.max_quote_age_seconds,
                        reason=(
                            "Rejected: no explicit contract-native fair-value estimator "
                            f"for {prediction.model_id} -> {contract_family.value}"
                        ),
                    ),
                )
                continue

            if quote_timestamp is None:
                results.append(
                    self._build_non_tradable_result(
                        prediction_model_id=prediction.model_id,
                        contract_ticker=contract.ticker,
                        proxy_class=proxy_class,
                        contract_family=contract_family,
                        estimator_name=fair_value.estimator_name,
                        fair_value_yes=fair_value.fair_value_yes,
                        fair_value_no=fair_value.fair_value_no,
                        quote_timestamp=None,
                        quote_age_seconds=None,
                        staleness_threshold_seconds=resolved_staleness.max_quote_age_seconds,
                        reason="Rejected: market quote has no usable timestamp",
                    ),
                )
                continue

            if quote_age_seconds is not None and (
                quote_age_seconds > resolved_staleness.max_quote_age_seconds
            ):
                results.append(
                    self._build_non_tradable_result(
                        prediction_model_id=prediction.model_id,
                        contract_ticker=contract.ticker,
                        proxy_class=proxy_class,
                        contract_family=contract_family,
                        estimator_name=fair_value.estimator_name,
                        fair_value_yes=fair_value.fair_value_yes,
                        fair_value_no=fair_value.fair_value_no,
                        quote_timestamp=quote_timestamp,
                        quote_age_seconds=quote_age_seconds,
                        staleness_threshold_seconds=resolved_staleness.max_quote_age_seconds,
                        reason=(
                            f"Rejected: quote stale at {quote_age_seconds:.0f}s "
                            f"(threshold {resolved_staleness.max_quote_age_seconds:.0f}s)"
                        ),
                    ),
                )
                continue

            buy_yes_edge = None
            buy_no_edge = None
            if market.best_yes_ask is not None:
                buy_yes_edge = fair_value.fair_value_yes - market.best_yes_ask
            if market.best_no_ask is not None:
                buy_no_edge = fair_value.fair_value_no - market.best_no_ask

            result = self._build_mapping_result(
                prediction_model_id=prediction.model_id,
                contract_ticker=contract.ticker,
                proxy_class=proxy_class,
                contract_family=contract_family,
                estimator_name=fair_value.estimator_name,
                fair_value_yes=fair_value.fair_value_yes,
                fair_value_no=fair_value.fair_value_no,
                quote_timestamp=quote_timestamp,
                quote_age_seconds=quote_age_seconds,
                staleness_threshold_seconds=resolved_staleness.max_quote_age_seconds,
                min_edge=self._per_class_min_edge.get(proxy_class.value, self._min_edge),
                buy_yes_edge=buy_yes_edge,
                buy_no_edge=buy_no_edge,
                yes_ask=market.best_yes_ask,
                no_ask=market.best_no_ask,
                yes_spread=market.yes_bid_ask_spread,
                no_spread=market.no_bid_ask_spread,
                costs=resolved_costs,
            )
            results.append(result)

        results.sort(
            key=lambda result: result.effective_edge
            if result.effective_edge is not None
            else float("-inf"),
            reverse=True,
        )
        return results

    def _build_mapping_result(
        self,
        *,
        prediction_model_id: str,
        contract_ticker: str,
        proxy_class: ProxyClass,
        contract_family: ContractFamily,
        estimator_name: str,
        fair_value_yes: float,
        fair_value_no: float,
        quote_timestamp: datetime,
        quote_age_seconds: float | None,
        staleness_threshold_seconds: float,
        min_edge: float,
        buy_yes_edge: float | None,
        buy_no_edge: float | None,
        yes_ask: float | None,
        no_ask: float | None,
        yes_spread: float | None,
        no_spread: float | None,
        costs: MappingCostInputs,
    ) -> MappingResult:
        if buy_yes_edge is None and buy_no_edge is None:
            return self._build_non_tradable_result(
                prediction_model_id=prediction_model_id,
                contract_ticker=contract_ticker,
                proxy_class=proxy_class,
                contract_family=contract_family,
                estimator_name=estimator_name,
                fair_value_yes=fair_value_yes,
                fair_value_no=fair_value_no,
                quote_timestamp=quote_timestamp,
                quote_age_seconds=quote_age_seconds,
                staleness_threshold_seconds=staleness_threshold_seconds,
                reason="Rejected: no executable YES or NO ask available",
            )

        chosen_side: str
        chosen_edge: float
        observed_spread: float | None
        if buy_yes_edge is None:
            chosen_side = "no"
            chosen_edge = buy_no_edge or 0.0
            observed_spread = no_spread
        elif buy_no_edge is None:
            chosen_side = "yes"
            chosen_edge = buy_yes_edge
            observed_spread = yes_spread
        elif buy_yes_edge >= buy_no_edge:
            chosen_side = "yes"
            chosen_edge = buy_yes_edge
            observed_spread = yes_spread
        else:
            chosen_side = "no"
            chosen_edge = buy_no_edge
            observed_spread = no_spread

        expected_slippage_rate = costs.slippage_for_spread(observed_spread)
        expected_total_cost = costs.total_cost_for_spread(observed_spread)
        net_edge = chosen_edge - expected_total_cost
        should_trade = chosen_edge > expected_total_cost and net_edge >= min_edge

        if chosen_side == "yes":
            entry_price_kind = "best_yes_ask"
            entry_price = yes_ask
        else:
            entry_price_kind = "best_no_ask"
            entry_price = no_ask

        if should_trade:
            tradeability_status = "tradable"
            reason = (
                f"{contract_family.value} via {estimator_name}: {chosen_side.upper()} "
                f"gross edge {chosen_edge:.1%}, costs {expected_total_cost:.1%}, "
                f"net edge {net_edge:.1%}"
            )
        elif chosen_edge <= expected_total_cost:
            tradeability_status = "cost_blocked"
            reason = (
                f"Rejected: executable {chosen_side.upper()} gross edge {chosen_edge:.1%} "
                f"does not clear costs {expected_total_cost:.1%}"
            )
        else:
            tradeability_status = "edge_blocked"
            reason = (
                f"Rejected: post-cost {chosen_side.upper()} net edge {net_edge:.1%} "
                f"below {min_edge:.1%} threshold"
            )

        return MappingResult(
            prediction_model_id=prediction_model_id,
            contract_ticker=contract_ticker,
            proxy_class=proxy_class,
            contract_family=contract_family,
            estimator_name=estimator_name,
            fair_value_yes=fair_value_yes,
            fair_value_no=fair_value_no,
            quote_timestamp=quote_timestamp,
            quote_age_seconds=quote_age_seconds,
            staleness_threshold_seconds=staleness_threshold_seconds,
            quote_is_stale=False,
            buy_yes_edge=buy_yes_edge,
            buy_no_edge=buy_no_edge,
            gross_edge=chosen_edge,
            raw_edge=chosen_edge,
            confidence_discount=1.0,
            expected_fee_rate=costs.expected_fee_rate,
            expected_slippage_rate=expected_slippage_rate,
            expected_total_cost=expected_total_cost,
            net_edge=net_edge,
            effective_edge=net_edge,
            entry_side=chosen_side,
            entry_price=entry_price,
            entry_price_kind=entry_price_kind,
            entry_price_is_executable=True,
            tradeability_status=tradeability_status,
            should_trade=should_trade,
            reason=reason,
        )

    def _build_non_tradable_result(
        self,
        *,
        prediction_model_id: str,
        contract_ticker: str,
        proxy_class: ProxyClass,
        contract_family: ContractFamily | None,
        estimator_name: str | None,
        fair_value_yes: float | None,
        fair_value_no: float | None,
        quote_timestamp: datetime | None,
        quote_age_seconds: float | None,
        staleness_threshold_seconds: float | None,
        reason: str,
    ) -> MappingResult:
        return MappingResult(
            prediction_model_id=prediction_model_id,
            contract_ticker=contract_ticker,
            proxy_class=proxy_class,
            contract_family=contract_family,
            estimator_name=estimator_name,
            fair_value_yes=fair_value_yes,
            fair_value_no=fair_value_no,
            quote_timestamp=quote_timestamp,
            quote_age_seconds=quote_age_seconds,
            staleness_threshold_seconds=staleness_threshold_seconds,
            quote_is_stale=quote_age_seconds is None
            or (
                staleness_threshold_seconds is not None
                and quote_age_seconds > staleness_threshold_seconds
            ),
            buy_yes_edge=None,
            buy_no_edge=None,
            gross_edge=None,
            raw_edge=None,
            confidence_discount=1.0,
            expected_fee_rate=None,
            expected_slippage_rate=None,
            expected_total_cost=None,
            net_edge=None,
            effective_edge=None,
            entry_side=None,
            entry_price=None,
            entry_price_kind=None,
            entry_price_is_executable=False,
            tradeability_status="non_tradable",
            should_trade=False,
            reason=reason,
        )

    def _resolve_cost_inputs(
        self,
        contract_metadata: dict | None,
        override: MappingCostInputs | None,
    ) -> MappingCostInputs:
        base = override or self._default_cost_inputs
        metadata = contract_metadata or {}
        return MappingCostInputs(
            expected_fee_rate=float(
                metadata.get("expected_fee_rate", base.expected_fee_rate),
            ),
            expected_slippage_rate=float(
                metadata.get("expected_slippage_rate", base.expected_slippage_rate),
            ),
            use_half_spread_as_slippage_floor=bool(
                metadata.get(
                    "use_half_spread_as_slippage_floor",
                    base.use_half_spread_as_slippage_floor,
                ),
            ),
        )

    def _resolve_staleness_policy(
        self,
        contract_metadata: dict | None,
        override: MarketStalenessPolicy | None,
    ) -> MarketStalenessPolicy:
        base = override or self._default_staleness_policy
        metadata = contract_metadata or {}
        return MarketStalenessPolicy(
            max_quote_age_seconds=float(
                metadata.get("staleness_threshold_seconds", base.max_quote_age_seconds),
            ),
            allow_fetched_at_fallback=bool(
                metadata.get(
                    "allow_fetched_at_fallback",
                    base.allow_fetched_at_fallback,
                ),
            ),
        )

    @staticmethod
    def _resolve_quote_age(
        market: MarketPrice,
        evaluated_at: datetime,
        staleness_policy: MarketStalenessPolicy,
    ) -> tuple[datetime | None, float | None]:
        quote_timestamp = market.quote_timestamp or market.venue_timestamp
        if quote_timestamp is None and staleness_policy.allow_fetched_at_fallback:
            quote_timestamp = market.fetched_at

        if quote_timestamp is None:
            return None, None

        if quote_timestamp.tzinfo is None:
            quote_timestamp = quote_timestamp.replace(tzinfo=timezone.utc)
        if evaluated_at.tzinfo is None:
            evaluated_at = evaluated_at.replace(tzinfo=timezone.utc)

        age_seconds = max((evaluated_at - quote_timestamp).total_seconds(), 0.0)
        return quote_timestamp, age_seconds

    def _estimate_fair_value(
        self,
        *,
        prediction: PredictionOutput,
        proxy_class: ProxyClass,
        contract_family: ContractFamily,
        invert: bool,
        contract_metadata: dict[str, object],
    ) -> FairValueEstimate | None:
        if proxy_class == ProxyClass.DIRECT or contract_family == ContractFamily.GENERIC_BINARY:
            if proxy_class != ProxyClass.DIRECT:
                return None
            fair_yes = self._confidence_shrunk_probability(
                1.0 - prediction.probability if invert else prediction.probability,
                prediction.confidence,
            )
            return FairValueEstimate(
                estimator_name="direct_binary_probability",
                contract_family=contract_family,
                fair_value_yes=fair_yes,
                fair_value_no=1.0 - fair_yes,
                inputs={"invert_probability": invert},
            )

        if (
            prediction.model_id == "ceasefire"
            and contract_family == ContractFamily.IRAN_AGREEMENT
        ):
            fair_yes = self._confidence_shrunk_probability(
                prediction.probability,
                prediction.confidence,
            )
            return FairValueEstimate(
                estimator_name="ceasefire_to_agreement",
                contract_family=contract_family,
                fair_value_yes=fair_yes,
                fair_value_no=1.0 - fair_yes,
                inputs={"confidence": prediction.confidence},
            )

        if (
            prediction.model_id == "hormuz_reopening"
            and contract_family == ContractFamily.HORMUZ_CLOSURE
        ):
            reopening_yes = self._confidence_shrunk_probability(
                prediction.probability,
                prediction.confidence,
            )
            fair_yes = 1.0 - reopening_yes
            return FairValueEstimate(
                estimator_name="hormuz_reopening_to_closure",
                contract_family=contract_family,
                fair_value_yes=fair_yes,
                fair_value_no=1.0 - fair_yes,
                inputs={"confidence": prediction.confidence},
            )

        if (
            prediction.model_id == "oil_price"
            and contract_family in (ContractFamily.OIL_PRICE_MAX, ContractFamily.OIL_PRICE_MIN)
        ):
            bullish = contract_family == ContractFamily.OIL_PRICE_MAX
            move_scale = float(
                contract_metadata.get("oil_move_scale_usd", self.DEFAULT_OIL_MOVE_SCALE_USD),
            )
            fair_yes = self._estimate_oil_extreme_probability(
                prediction=prediction,
                bullish=bullish,
                move_scale_usd=move_scale,
            )
            return FairValueEstimate(
                estimator_name="oil_direction_to_extreme",
                contract_family=contract_family,
                fair_value_yes=fair_yes,
                fair_value_no=1.0 - fair_yes,
                inputs={
                    "bullish": bullish,
                    "move_scale_usd": move_scale,
                    "direction": prediction.direction,
                    "magnitude_range": prediction.magnitude_range,
                },
            )

        return None

    @staticmethod
    def _confidence_shrunk_probability(probability: float, confidence: float) -> float:
        """Shrink uncertain predictions toward 50% instead of proxy-discounting edges."""
        centered = 0.5 + (probability - 0.5) * confidence
        return max(0.01, min(0.99, centered))

    def _estimate_oil_extreme_probability(
        self,
        *,
        prediction: PredictionOutput,
        bullish: bool,
        move_scale_usd: float,
    ) -> float:
        shrunk_probability = self._confidence_shrunk_probability(
            prediction.probability,
            prediction.confidence,
        )
        mean_move = 0.0
        if prediction.magnitude_range:
            mean_move = sum(abs(value) for value in prediction.magnitude_range) / len(
                prediction.magnitude_range,
            )

        intensity = max(0.0, min(1.0, mean_move / max(move_scale_usd, 0.01)))
        if prediction.direction == "stable":
            return max(0.05, 0.5 - 0.25 * intensity)

        aligned_direction = "increase" if bullish else "decrease"
        directional_probability = (
            shrunk_probability
            if prediction.direction == aligned_direction
            else 1.0 - shrunk_probability
        )
        fair_yes = 0.5 + (directional_probability - 0.5) * intensity
        return max(0.01, min(0.99, fair_yes))

    @staticmethod
    def _classify_contract_family(contract) -> ContractFamily:
        metadata = contract.metadata or {}
        metadata_family = metadata.get("contract_family")
        if isinstance(metadata_family, str):
            try:
                return ContractFamily(metadata_family)
            except ValueError:
                logger.warning("Unknown contract_family metadata %s", metadata_family)

        ticker = contract.ticker.upper()
        title = contract.title.lower()
        resolution = contract.resolution_criteria.lower()

        if "USAIRANAGREEMENT" in ticker or "agreement" in title or "agreement" in resolution:
            return ContractFamily.IRAN_AGREEMENT
        if "CLOSEHORMUZ" in ticker or "closure" in title or "closed" in resolution:
            return ContractFamily.HORMUZ_CLOSURE
        if "WTIMAX" in ticker or "maximum" in title:
            return ContractFamily.OIL_PRICE_MAX
        if "WTIMIN" in ticker or "minimum" in title:
            return ContractFamily.OIL_PRICE_MIN
        return ContractFamily.GENERIC_BINARY

    def update_discounts_from_history(self, conn: duckdb.DuckDBPyConnection) -> None:
        del conn
        logger.info(
            "Skipping heuristic discount recalibration; explicit fair-value estimators are active",
        )

    def update_thresholds_from_history(self, conn: duckdb.DuckDBPyConnection) -> None:
        rows = conn.execute("""
            SELECT
                proxy_class,
                AVG(CASE WHEN counterfactual_pnl > 0 THEN 1.0 ELSE 0.0 END) AS win_rate
            FROM signal_quality_evaluation
            WHERE ABS(effective_edge) < 0.08
            GROUP BY proxy_class
        """).fetchall()

        for proxy_class_val, win_rate in rows:
            if win_rate < 0.4:
                raised = max(self._min_edge, 0.08)
                if raised > self._min_edge:
                    self._per_class_min_edge[proxy_class_val] = raised
                    logger.info(
                        "Raised min_edge for %s to %.1f%% (win_rate=%.1f%% on small executable edges)",
                        proxy_class_val,
                        raised * 100,
                        win_rate * 100,
                    )
