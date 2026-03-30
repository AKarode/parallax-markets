from dataclasses import dataclass
from pathlib import Path

import yaml


@dataclass(frozen=True)
class ScenarioConfig:
    name: str
    description: str
    tick_duration_minutes: int

    # Shipping & Oil Flow
    hormuz_daily_flow: int
    saudi_eastwest_pipeline_capacity: int
    uae_habshan_fujairah_capacity: int
    total_bypass_capacity_min: int
    total_bypass_capacity_max: int

    # Rerouting
    hormuz_to_europe_via_suez_nm: int
    cape_reroute_nm: int
    reroute_transit_days_min: int
    reroute_transit_days_max: int

    # Circuit Breaker
    max_escalation_per_tick: int
    escalation_cooldown_ticks: int
    exogenous_shock_goldstein_threshold: float

    # Oil Price
    oil_price_floor: float
    oil_price_ceiling: float

    # Budget
    daily_budget_cap_usd: float
    sub_actor_max_input_tokens: int
    sub_actor_max_output_tokens: int
    country_agent_max_input_tokens: int
    country_agent_max_output_tokens: int

    # Agent Timing
    sub_actor_cooldown_minutes: int
    country_agent_cooldown_minutes: int

    # State Management
    snapshot_interval_ticks: int
    delta_retention_days: int

    @property
    def reroute_distance_penalty_pct(self) -> float:
        return (self.cape_reroute_nm - self.hormuz_to_europe_via_suez_nm) / self.hormuz_to_europe_via_suez_nm


def load_scenario_config(path: Path) -> ScenarioConfig:
    with open(path) as f:
        data = yaml.safe_load(f)
    return ScenarioConfig(**data)
