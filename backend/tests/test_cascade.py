from pathlib import Path

from parallax.simulation.cascade import CascadeEngine, ReroutePenalty
from parallax.simulation.config import load_scenario_config
from parallax.simulation.world_state import WorldState


def _config():
    return load_scenario_config(
        Path(__file__).parent.parent / "config" / "scenario_hormuz.yaml"
    )


def test_blockade_reduces_flow():
    config = _config()
    ws = WorldState()
    ws.update_cell(111, flow=20_000_000.0, status="open")
    ws.advance_tick()

    engine = CascadeEngine(config)
    effects = engine.apply_blockade(ws, cell_id=111, reduction_pct=0.5)

    cell = ws.get_cell(111)
    assert cell["flow"] == 10_000_000.0
    assert cell["status"] == "restricted"
    assert effects["supply_loss"] == 10_000_000.0


def test_blockade_full_closure():
    config = _config()
    ws = WorldState()
    ws.update_cell(111, flow=20_000_000.0, status="open")
    ws.advance_tick()

    engine = CascadeEngine(config)
    effects = engine.apply_blockade(ws, cell_id=111, reduction_pct=1.0)

    cell = ws.get_cell(111)
    assert cell["flow"] == 0.0
    assert cell["status"] == "blocked"
    assert effects["supply_loss"] == 20_000_000.0


def test_blockade_nonexistent_cell():
    config = _config()
    ws = WorldState()
    engine = CascadeEngine(config)
    effects = engine.apply_blockade(ws, cell_id=999, reduction_pct=0.5)
    assert effects["supply_loss"] == 0.0


def test_supply_loss_triggers_price_shock():
    config = _config()
    engine = CascadeEngine(config)
    current_price = 80.0
    supply_loss = 5_000_000
    bypass_used = 3_500_000

    new_price = engine.compute_price_shock(
        current_price=current_price,
        supply_loss=supply_loss,
        bypass_active=bypass_used,
    )

    assert new_price > current_price
    assert new_price <= config.oil_price_ceiling


def test_price_shock_clamped_to_floor_and_ceiling():
    config = _config()
    engine = CascadeEngine(config)

    # Massive supply loss -> should hit ceiling
    price = engine.compute_price_shock(
        current_price=150.0, supply_loss=20_000_000, bypass_active=0
    )
    assert price == config.oil_price_ceiling

    # No loss -> price stays
    price = engine.compute_price_shock(
        current_price=80.0, supply_loss=0, bypass_active=0
    )
    assert price == 80.0


def test_reroute_penalty_computed():
    config = _config()
    engine = CascadeEngine(config)
    penalty = engine.reroute_penalty()
    assert isinstance(penalty, ReroutePenalty)
    # Cape reroute ~84% longer based on default config
    assert 0.80 < penalty.distance_increase_pct < 0.90
    assert penalty.transit_days_min == config.reroute_transit_days_min
    assert penalty.transit_days_max == config.reroute_transit_days_max


def test_downstream_country_effects():
    """Price shock distributes per-country impact based on energy dependency."""
    config = _config()
    engine = CascadeEngine(config)

    dependencies = {
        "japan": 0.85,  # 85% of oil through Hormuz
        "south_korea": 0.70,
        "india": 0.60,
        "china": 0.40,
    }
    price_increase_pct = 0.30  # 30% price increase

    effects = engine.compute_downstream_effects(
        dependencies=dependencies,
        price_increase_pct=price_increase_pct,
    )

    assert "japan" in effects
    assert "china" in effects
    # Japan more exposed than China
    assert effects["japan"]["impact_score"] > effects["china"]["impact_score"]
    # Impact scores should be between 0 and 1
    for country, data in effects.items():
        assert 0.0 <= data["impact_score"] <= 1.0


def test_insurance_cost_spike():
    """Shipping insurance cost spikes based on threat level."""
    config = _config()
    engine = CascadeEngine(config)

    base_rate = 0.25  # 0.25% of hull value
    result = engine.compute_insurance_spike(
        base_rate_pct=base_rate, threat_level=0.8
    )

    assert result["new_rate_pct"] > base_rate
    assert result["multiplier"] > 1.0


def test_insurance_cost_no_threat():
    config = _config()
    engine = CascadeEngine(config)

    base_rate = 0.25
    result = engine.compute_insurance_spike(
        base_rate_pct=base_rate, threat_level=0.0
    )
    assert result["new_rate_pct"] == base_rate
    assert result["multiplier"] == 1.0


def test_full_cascade_chain():
    """Test the full cascade: blockade -> bypass -> price -> downstream."""
    config = _config()
    ws = WorldState()
    ws.update_cell(111, flow=20_000_000.0, status="open")
    ws.advance_tick()

    engine = CascadeEngine(config)

    # Step 1: Blockade
    effects = engine.apply_blockade(ws, cell_id=111, reduction_pct=0.6)
    supply_loss = effects["supply_loss"]
    assert supply_loss == 12_000_000.0

    # Step 2: Bypass activation
    bypass = engine.activate_bypass(supply_loss=supply_loss)
    assert bypass["bypass_flow"] >= config.total_bypass_capacity_min
    assert bypass["bypass_flow"] <= config.total_bypass_capacity_max

    # Step 3: Price shock
    new_price = engine.compute_price_shock(
        current_price=80.0,
        supply_loss=supply_loss,
        bypass_active=bypass["bypass_flow"],
    )
    assert new_price > 80.0

    # Step 4: Downstream effects
    price_increase_pct = (new_price - 80.0) / 80.0
    downstream = engine.compute_downstream_effects(
        dependencies={"japan": 0.85, "india": 0.60},
        price_increase_pct=price_increase_pct,
    )
    assert len(downstream) == 2
