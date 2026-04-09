"""Mapping policy for prediction-to-contract alignment with executable pricing."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import duckdb

from parallax.contracts.registry import ContractRegistry
from parallax.contracts.schemas import MappingResult, ProxyClass
from parallax.markets.schemas import MarketPrice
from parallax.prediction.schemas import PredictionOutput

logger = logging.getLogger(__name__)


class MappingPolicy:
    """Decides whether and how to map a prediction to tradeable contracts."""

    DEFAULT_DISCOUNTS = {
        ProxyClass.DIRECT: 1.0,
        ProxyClass.NEAR_PROXY: 0.6,
        ProxyClass.LOOSE_PROXY: 0.3,
        ProxyClass.NONE: 0.0,
    }

    DISCOUNT_BOUNDS: dict[ProxyClass, tuple[float, float]] = {
        ProxyClass.DIRECT: (0.8, 1.0),
        ProxyClass.NEAR_PROXY: (0.2, 0.8),
        ProxyClass.LOOSE_PROXY: (0.1, 0.5),
        ProxyClass.NONE: (0.0, 0.0),
    }

    MIN_SIGNALS_FOR_DISCOUNT = 5

    def __init__(
        self,
        registry: ContractRegistry,
        min_effective_edge_pct: float = 5.0,
    ) -> None:
        self._registry = registry
        self._min_edge = min_effective_edge_pct / 100.0
        self._per_class_min_edge: dict[str, float] = {}

    def evaluate(
        self,
        prediction: PredictionOutput,
        market_prices: list[MarketPrice],
    ) -> list[MappingResult]:
        market_by_ticker = {market.ticker: market for market in market_prices}
        candidates = self._registry.get_contracts_for_model(prediction.model_id)
        results: list[MappingResult] = []

        for contract, proxy_class, discount, invert in candidates:
            market = market_by_ticker.get(contract.ticker)
            if market is None:
                logger.debug("No market price for %s, skipping", contract.ticker)
                continue

            model_yes_probability = (
                1.0 - prediction.probability if invert else prediction.probability
            )
            model_no_probability = 1.0 - model_yes_probability

            buy_yes_edge = None
            buy_no_edge = None
            if market.best_yes_ask is not None:
                buy_yes_edge = model_yes_probability - market.best_yes_ask
            if market.best_no_ask is not None:
                buy_no_edge = model_no_probability - market.best_no_ask

            proxy_key = proxy_class.value
            min_edge = self._per_class_min_edge.get(proxy_key, self._min_edge)
            result = self._build_mapping_result(
                prediction_model_id=prediction.model_id,
                contract_ticker=contract.ticker,
                proxy_class=proxy_class,
                confidence_discount=discount,
                min_edge=min_edge,
                buy_yes_edge=buy_yes_edge,
                buy_no_edge=buy_no_edge,
                yes_ask=market.best_yes_ask,
                no_ask=market.best_no_ask,
            )
            results.append(result)

        results.sort(key=lambda result: abs(result.effective_edge or 0.0), reverse=True)
        return results

    def _build_mapping_result(
        self,
        *,
        prediction_model_id: str,
        contract_ticker: str,
        proxy_class: ProxyClass,
        confidence_discount: float,
        min_edge: float,
        buy_yes_edge: float | None,
        buy_no_edge: float | None,
        yes_ask: float | None,
        no_ask: float | None,
    ) -> MappingResult:
        if buy_yes_edge is None and buy_no_edge is None:
            return MappingResult(
                prediction_model_id=prediction_model_id,
                contract_ticker=contract_ticker,
                proxy_class=proxy_class,
                buy_yes_edge=None,
                buy_no_edge=None,
                raw_edge=None,
                confidence_discount=confidence_discount,
                effective_edge=None,
                entry_side=None,
                entry_price=None,
                entry_price_kind=None,
                entry_price_is_executable=False,
                tradeability_status="non_tradable",
                should_trade=False,
                reason="Rejected: no executable YES or NO ask available",
            )

        chosen_side: str
        chosen_edge: float
        if buy_yes_edge is None:
            chosen_side = "no"
            chosen_edge = buy_no_edge or 0.0
        elif buy_no_edge is None:
            chosen_side = "yes"
            chosen_edge = buy_yes_edge
        elif buy_yes_edge >= buy_no_edge:
            chosen_side = "yes"
            chosen_edge = buy_yes_edge
        else:
            chosen_side = "no"
            chosen_edge = buy_no_edge

        signed_raw_edge = chosen_edge if chosen_side == "yes" else -chosen_edge
        effective_edge = signed_raw_edge * confidence_discount
        should_trade = chosen_edge >= min_edge

        if chosen_side == "yes":
            entry_price_kind = "best_yes_ask"
        else:
            entry_price_kind = "best_no_ask"

        if not should_trade:
            reason = (
                f"Rejected: executable {chosen_side.upper()} edge {chosen_edge:.1%} "
                f"below {min_edge:.1%} threshold"
            )
        else:
            label = proxy_class.value.upper().replace("_", " ")
            reason = (
                f"{label} match via executable {chosen_side.upper()} ask, "
                f"discounted edge {abs(effective_edge):.1%}"
            )

        return MappingResult(
            prediction_model_id=prediction_model_id,
            contract_ticker=contract_ticker,
            proxy_class=proxy_class,
            buy_yes_edge=buy_yes_edge,
            buy_no_edge=buy_no_edge,
            raw_edge=signed_raw_edge,
            confidence_discount=confidence_discount,
            effective_edge=effective_edge,
            entry_side=chosen_side,
            entry_price_kind=entry_price_kind,
            entry_price=yes_ask if chosen_side == "yes" else no_ask,
            entry_price_is_executable=True,
            tradeability_status="tradable",
            should_trade=should_trade,
            reason=reason,
        )

    def update_discounts_from_history(self, conn: duckdb.DuckDBPyConnection) -> None:
        from parallax.scoring.calibration import hit_rate_by_proxy_class

        rows = hit_rate_by_proxy_class(conn)
        if not rows:
            return

        for row in rows:
            proxy_class_str = row["proxy_class"]
            total = row["total"]
            hit_rate = row["hit_rate"]

            if total < self.MIN_SIGNALS_FOR_DISCOUNT:
                continue

            try:
                proxy_class = ProxyClass(proxy_class_str)
            except ValueError:
                continue

            if proxy_class == ProxyClass.NONE:
                continue

            default_discount = self.DEFAULT_DISCOUNTS[proxy_class]
            new_discount = default_discount * 0.7 + hit_rate * 0.3
            lo, hi = self.DISCOUNT_BOUNDS[proxy_class]
            new_discount = round(max(lo, min(hi, new_discount)), 2)

            conn.execute(
                """
                UPDATE contract_proxy_map
                SET confidence_discount = ?
                WHERE proxy_class = ?
                """,
                [new_discount, proxy_class_str],
            )

            logger.info(
                "Adjusted discount for %s: %.2f -> %.2f (hit_rate=%.1f%%, n=%d)",
                proxy_class_str,
                default_discount,
                new_discount,
                hit_rate * 100,
                total,
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
