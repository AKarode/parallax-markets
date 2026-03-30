import json
from parallax.agents.schemas import AgentDecision, SubActorRecommendation, CountryDecision, AgentPrediction
from parallax.agents.registry import AgentRegistry, AgentInfo


def test_agent_decision_validates():
    d = AgentDecision(
        agent_id="iran/irgc_navy",
        tick=10,
        action_type="military_deployment",
        target_h3_cells=[612345678],
        intensity=0.7,
        description="Patrol increase",
        reasoning="Deterrence",
        confidence=0.78,
        prompt_version="v1.0.0",
    )
    assert d.agent_id == "iran/irgc_navy"
    assert 0.0 <= d.confidence <= 1.0


def test_agent_decision_rejects_invalid_confidence():
    try:
        AgentDecision(
            agent_id="x",
            tick=1,
            action_type="x",
            target_h3_cells=[],
            intensity=0.5,
            description="x",
            reasoning="x",
            confidence=1.5,  # Invalid
            prompt_version="v1.0.0",
        )
        assert False, "Should have raised"
    except ValueError:
        pass


def test_sub_actor_recommendation_validates():
    rec = SubActorRecommendation(
        agent_id="iran/irgc_navy",
        action_type="patrol",
        description="Increase patrols",
        reasoning="Deterrence",
        intensity=0.6,
        confidence=0.7,
        significance=0.8,
    )
    assert rec.agent_id == "iran/irgc_navy"
    assert rec.significance == 0.8


def test_sub_actor_recommendation_rejects_invalid_significance():
    try:
        SubActorRecommendation(
            agent_id="x",
            action_type="x",
            description="x",
            reasoning="x",
            intensity=0.5,
            confidence=0.5,
            significance=1.5,  # Invalid
        )
        assert False, "Should have raised"
    except ValueError:
        pass


def test_country_decision_validates():
    d = CountryDecision(
        country="iran",
        tick=10,
        action_type="escalation",
        target_h3_cells=[],
        intensity=0.6,
        description="National escalation",
        reasoning="Sub-actor consensus",
        confidence=0.75,
        prompt_version="v1.0.0",
        contributing_agents=["iran/irgc", "iran/irgc_navy"],
    )
    assert d.country == "iran"
    assert len(d.contributing_agents) == 2


def test_agent_prediction_validates():
    p = AgentPrediction(
        agent_id="iran/oil_ministry",
        prediction_type="oil_price",
        direction="increase",
        magnitude_range=[5.0, 15.0],
        unit="usd_per_barrel",
        timeframe="7d",
        confidence=0.65,
        reasoning="Supply disruption",
        prompt_version="v1.0.0",
    )
    assert p.direction == "increase"
    assert p.magnitude_range == [5.0, 15.0]


def test_agent_prediction_rejects_invalid_direction():
    try:
        AgentPrediction(
            agent_id="x",
            prediction_type="x",
            direction="sideways",  # Invalid
            magnitude_range=[0, 10],
            unit="x",
            timeframe="1d",
            confidence=0.5,
            reasoning="x",
            prompt_version="v1.0.0",
        )
        assert False, "Should have raised"
    except ValueError:
        pass


def test_registry_loads_all_countries():
    registry = AgentRegistry()
    countries = registry.list_countries()
    assert "iran" in countries
    assert "usa" in countries
    assert "saudi_arabia" in countries
    assert len(countries) >= 12


def test_registry_sub_actors_for_iran():
    registry = AgentRegistry()
    actors = registry.sub_actors("iran")
    actor_ids = [a.agent_id for a in actors]
    assert "iran/supreme_leader" in actor_ids
    assert "iran/irgc" in actor_ids
    assert "iran/irgc_navy" in actor_ids


def test_registry_agent_info_has_weight():
    registry = AgentRegistry()
    info = registry.get_agent("iran/irgc")
    assert info is not None
    assert 0.0 < info.weight <= 1.0


def test_registry_country_agent():
    registry = AgentRegistry()
    ca = registry.country_agent("iran")
    assert ca is not None
    assert ca.is_country_agent is True
    assert ca.agent_id == "iran"


def test_registry_all_agents():
    registry = AgentRegistry()
    all_agents = registry.all_agents()
    # Should have 12 country agents + ~38 sub-actors = ~50 total
    assert len(all_agents) >= 45
    country_agents = [a for a in all_agents if a.is_country_agent]
    assert len(country_agents) == 12
