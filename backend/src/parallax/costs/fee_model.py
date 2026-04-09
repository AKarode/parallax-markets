"""Transaction cost model for prediction market edge calculations."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class CostModel:
    """Models transaction costs in probability space for binary contracts.

    All costs expressed as fractions of the $1 contract payout.
    """

    taker_fee_per_contract: float = 0.07  # Kalshi taker fee
    maker_fee_per_contract: float = 0.00  # currently zero on Kalshi
    slippage_buffer: float = 0.01         # 1% for thin geopolitical markets

    def total_cost_probability_space(self) -> float:
        """Total cost as a fraction of the $1 contract payout.

        Uses taker fee (not maker) since we cross the spread.
        """
        return self.taker_fee_per_contract + self.slippage_buffer

    def net_edge(self, raw_edge: float) -> float:
        """Subtract costs from raw edge. Negative means no real edge."""
        return raw_edge - self.total_cost_probability_space()
