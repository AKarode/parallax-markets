"""Rule-based cascade engine for geopolitical simulation.

Cascade chain:
1. Blockade -> shipping flow reduction (partial, based on blockade severity)
2. Flow reduction -> pipeline bypass activation
3. Net supply loss -> oil price shock
4. Price shock -> downstream per-country effects (based on energy dependency ratios)
5. Rerouting -> Cape of Good Hope path activation
6. Insurance/risk -> shipping insurance cost spike

All rules are parameterized from ScenarioConfig, not hard-coded.
"""

from dataclasses import dataclass

from parallax.simulation.config import ScenarioConfig
from parallax.simulation.world_state import WorldState


@dataclass(frozen=True)
class ReroutePenalty:
    distance_increase_pct: float
    transit_days_min: int
    transit_days_max: int


class CascadeEngine:
    """Deterministic, rule-based cascade propagation.

    All parameters come from the scenario config to allow tuning
    without code changes.
    """

    # Default elasticity: 10% supply loss -> ~30% price increase
    PRICE_ELASTICITY = 3.0

    # Insurance threat multiplier: threat_level * this = multiplier above 1.0
    INSURANCE_THREAT_MULTIPLIER = 5.0

    def __init__(self, config: ScenarioConfig) -> None:
        self._config = config

    # --- Rule 1: Blockade -> Flow Reduction ---

    def apply_blockade(
        self, ws: WorldState, cell_id: int, reduction_pct: float
    ) -> dict:
        """Apply a blockade to a cell, reducing its flow.

        Args:
            ws: Current world state.
            cell_id: H3 cell to blockade.
            reduction_pct: Fraction of flow to remove (0.0 to 1.0).

        Returns:
            Dict with 'supply_loss' indicating barrels/day lost.
        """
        cell = ws.get_cell(cell_id)
        if cell is None:
            return {"supply_loss": 0.0}

        original_flow = cell["flow"]
        reduced_flow = original_flow * (1.0 - reduction_pct)
        supply_loss = original_flow - reduced_flow

        new_status = "blocked" if reduction_pct >= 0.95 else "restricted"
        ws.update_cell(cell_id, flow=reduced_flow, status=new_status)

        return {"supply_loss": supply_loss}

    # --- Rule 2: Flow Reduction -> Pipeline Bypass Activation ---

    def activate_bypass(self, supply_loss: float) -> dict:
        """Activate pipeline bypass capacity in response to supply loss.

        Bypass ramps linearly between min and max capacity based on
        how much supply is lost relative to total Hormuz flow.

        Returns:
            Dict with 'bypass_flow' in bbl/day.
        """
        if supply_loss <= 0:
            return {"bypass_flow": 0.0}

        loss_fraction = min(1.0, supply_loss / self._config.hormuz_daily_flow)
        min_cap = self._config.total_bypass_capacity_min
        max_cap = self._config.total_bypass_capacity_max

        # Linear ramp: at 0% loss -> min capacity, at 100% loss -> max capacity
        bypass_flow = min_cap + (max_cap - min_cap) * loss_fraction

        return {"bypass_flow": bypass_flow}

    # --- Rule 3: Net Supply Loss -> Oil Price Shock ---

    def compute_price_shock(
        self,
        current_price: float,
        supply_loss: float,
        bypass_active: float,
    ) -> float:
        """Compute new oil price based on net supply loss after bypass.

        Uses a simple elasticity model: price increase is proportional
        to net loss as a fraction of total Hormuz flow.

        Returns:
            New oil price, clamped to [floor, ceiling].
        """
        net_loss = max(0.0, supply_loss - bypass_active)
        if net_loss == 0:
            return current_price

        loss_fraction = net_loss / self._config.hormuz_daily_flow
        price_multiplier = 1.0 + (loss_fraction * self.PRICE_ELASTICITY)
        new_price = current_price * price_multiplier

        return max(
            self._config.oil_price_floor,
            min(self._config.oil_price_ceiling, new_price),
        )

    # --- Rule 4: Price Shock -> Downstream Per-Country Effects ---

    def compute_downstream_effects(
        self,
        dependencies: dict[str, float],
        price_increase_pct: float,
    ) -> dict[str, dict]:
        """Compute per-country economic impact from an oil price shock.

        Args:
            dependencies: Country -> fraction of oil through Hormuz (0-1).
            price_increase_pct: Price increase as a fraction (e.g. 0.30 = 30%).

        Returns:
            Dict of country -> {impact_score, dependency, price_increase_pct}.
        """
        effects = {}
        for country, dependency in dependencies.items():
            # Impact is the product of dependency and price increase,
            # clamped to [0, 1]
            impact = min(1.0, dependency * price_increase_pct)
            effects[country] = {
                "impact_score": impact,
                "dependency": dependency,
                "price_increase_pct": price_increase_pct,
            }
        return effects

    # --- Rule 5: Rerouting -> Cape of Good Hope Path ---

    def reroute_penalty(self) -> ReroutePenalty:
        """Compute the penalty for rerouting via Cape of Good Hope."""
        return ReroutePenalty(
            distance_increase_pct=self._config.reroute_distance_penalty_pct,
            transit_days_min=self._config.reroute_transit_days_min,
            transit_days_max=self._config.reroute_transit_days_max,
        )

    # --- Rule 6: Insurance / Risk -> Shipping Insurance Cost Spike ---

    def compute_insurance_spike(
        self,
        base_rate_pct: float,
        threat_level: float,
    ) -> dict:
        """Compute shipping insurance cost spike based on threat level.

        Args:
            base_rate_pct: Baseline insurance rate as % of hull value.
            threat_level: Current threat level (0.0 to 1.0).

        Returns:
            Dict with 'new_rate_pct' and 'multiplier'.
        """
        if threat_level <= 0.0:
            return {"new_rate_pct": base_rate_pct, "multiplier": 1.0}

        multiplier = 1.0 + (threat_level * self.INSURANCE_THREAT_MULTIPLIER)
        new_rate = base_rate_pct * multiplier

        return {"new_rate_pct": new_rate, "multiplier": multiplier}
