from pathlib import Path
from parallax.simulation.config import ScenarioConfig, load_scenario_config


def test_load_hormuz_config():
    config = load_scenario_config(Path(__file__).parent.parent / "config" / "scenario_hormuz.yaml")
    assert config.name == "iran_hormuz"
    assert config.hormuz_daily_flow == 20_000_000
    assert config.total_bypass_capacity_min == 3_500_000
    assert config.total_bypass_capacity_max == 6_500_000
    assert config.cape_reroute_nm == 11600
    assert config.tick_duration_minutes == 15


def test_config_derived_reroute_penalty():
    config = load_scenario_config(Path(__file__).parent.parent / "config" / "scenario_hormuz.yaml")
    expected_pct = (config.cape_reroute_nm - config.hormuz_to_europe_via_suez_nm) / config.hormuz_to_europe_via_suez_nm
    assert abs(config.reroute_distance_penalty_pct - expected_pct) < 0.01


def test_config_circuit_breaker_defaults():
    config = load_scenario_config(Path(__file__).parent.parent / "config" / "scenario_hormuz.yaml")
    assert config.max_escalation_per_tick == 1
    assert config.escalation_cooldown_ticks == 3
    assert config.exogenous_shock_goldstein_threshold == 8.0
