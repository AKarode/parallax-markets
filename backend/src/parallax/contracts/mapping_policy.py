"""Mapping policy for prediction-to-contract alignment with proxy discounting.

Replaces the heuristic _map_predictions_to_markets() in cli/brief.py
with explicit proposition alignment and confidence discounting.
"""

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
    """Decides whether and how to map a prediction to tradeable contracts.

    For each prediction, evaluates all active contracts from the registry,
    applies proxy-aware confidence discounting, handles probability inversion,
    and returns all evaluated mappings for audit.
    """

    DEFAULT_DISCOUNTS = {
        ProxyClass.DIRECT: 1.0,
        ProxyClass.NEAR_PROXY: 0.6,
        ProxyClass.LOOSE_PROXY: 0.3,
        ProxyClass.NONE: 0.0,
    }

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
        """Evaluate all contract mappings for a single prediction.

        For each contract in the registry that has a non-NONE proxy class
        for this prediction's model_type:
        1. Find the matching MarketPrice by contract ticker
        2. Compute model_prob (invert if needed)
        3. Compute raw_edge = model_prob - market_yes_price
        4. Apply confidence_discount from proxy class
        5. Compute effective_edge = raw_edge * confidence_discount
        6. Determine should_trade: abs(effective_edge) >= min_edge
        7. Determine signal direction from edge sign

        Returns ALL evaluated mappings sorted by abs(effective_edge) descending.
        Contracts without a matching market price are skipped.
        """
        market_by_ticker: dict[str, MarketPrice] = {
            mp.ticker: mp for mp in market_prices
        }

        candidates = self._registry.get_contracts_for_model(prediction.model_id)
        results: list[MappingResult] = []

        for contract, proxy_class, discount, invert in candidates:
            if contract.ticker not in market_by_ticker:
                logger.debug(
                    "No market price for %s, skipping", contract.ticker,
                )
                continue

            model_prob = (1.0 - prediction.probability) if invert else prediction.probability
            market_prob = market_by_ticker[contract.ticker].yes_price
            raw_edge = model_prob - market_prob
            effective_edge = raw_edge * discount
            # Use per-class threshold if available (only raises, never lowers)
            proxy_key = proxy_class.value
            min_edge = self._per_class_min_edge.get(proxy_key, self._min_edge)
            should_trade = abs(effective_edge) >= min_edge

            reason = self._build_reason(proxy_class, effective_edge, should_trade)

            results.append(MappingResult(
                prediction_model_id=prediction.model_id,
                contract_ticker=contract.ticker,
                proxy_class=proxy_class,
                raw_edge=raw_edge,
                confidence_discount=discount,
                effective_edge=effective_edge,
                should_trade=should_trade,
                reason=reason,
            ))

        results.sort(key=lambda r: abs(r.effective_edge), reverse=True)
        return results

    def update_thresholds_from_history(self, conn: duckdb.DuckDBPyConnection) -> None:
        """Auto-adjust per-class min_edge thresholds based on edge_decay history.

        For proxy classes where small edges (< 8%) historically lose (win_rate < 0.4),
        raise the threshold. Thresholds are only raised, never lowered below the
        global min_effective_edge_pct.
        """
        rows = conn.execute("""
            SELECT
                proxy_class,
                AVG(CASE WHEN realized_pnl > 0 THEN 1.0 ELSE 0.0 END) AS win_rate
            FROM signal_ledger
            WHERE realized_pnl IS NOT NULL
              AND ABS(effective_edge) < 0.08
            GROUP BY proxy_class
        """).fetchall()

        for proxy_class_val, win_rate in rows:
            if win_rate < 0.4:
                # Raise threshold for this proxy class -- small edges are losing
                raised = max(self._min_edge, 0.08)  # At least 8%
                if raised > self._min_edge:
                    self._per_class_min_edge[proxy_class_val] = raised
                    logger.info(
                        "Raised min_edge for %s to %.1f%% (win_rate=%.1f%% on small edges)",
                        proxy_class_val, raised * 100, win_rate * 100,
                    )

    def _build_reason(
        self,
        proxy_class: ProxyClass,
        effective_edge: float,
        should_trade: bool,
    ) -> str:
        """Build a human-readable reason string for the mapping decision."""
        proxy_key = proxy_class.value
        min_edge = self._per_class_min_edge.get(proxy_key, self._min_edge)
        if not should_trade:
            return (
                f"Rejected: edge {effective_edge:.1%} below "
                f"{min_edge:.1%} threshold"
            )

        label = proxy_class.value.upper().replace("_", " ")
        return f"{label} match, edge {effective_edge:.1%}"
