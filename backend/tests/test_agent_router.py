from parallax.agents.router import AgentRouter
from parallax.agents.registry import AgentRegistry


def test_routes_iran_event_to_iran_agents():
    router = AgentRouter(AgentRegistry())
    event = {
        "actor1": "IRGC",
        "actor2": "USA",
        "summary": "IRGC deploys forces near Hormuz",
        "relevance_score": 0.8,
    }
    agents = router.route(event)
    agent_ids = [a.agent_id for a in agents]
    # Should include Iran sub-actors and USA sub-actors
    assert any("iran/" in aid for aid in agent_ids)
    assert any("usa/" in aid for aid in agent_ids)
    # Should NOT include country-level agents (those fire via escalation)
    assert "iran" not in agent_ids
    assert "usa" not in agent_ids


def test_low_relevance_event_routes_to_nobody():
    router = AgentRouter(AgentRegistry())
    event = {
        "actor1": "UNKNOWN",
        "actor2": "",
        "summary": "Weather forecast for Dubai",
        "relevance_score": 0.2,
    }
    agents = router.route(event)
    assert len(agents) == 0


def test_oil_event_routes_to_energy_actors():
    router = AgentRouter(AgentRegistry())
    event = {
        "actor1": "ARAMCO",
        "actor2": "",
        "summary": "Aramco increases pipeline capacity to Yanbu",
        "relevance_score": 0.7,
    }
    agents = router.route(event)
    agent_ids = [a.agent_id for a in agents]
    assert "saudi_arabia/aramco" in agent_ids


def test_multi_country_event_routes_to_multiple():
    router = AgentRouter(AgentRegistry())
    event = {
        "actor1": "Iran",
        "actor2": "Israel",
        "summary": "Iran threatens Israel over nuclear program",
        "relevance_score": 0.9,
    }
    agents = router.route(event)
    agent_ids = [a.agent_id for a in agents]
    assert any("iran/" in aid for aid in agent_ids)
    assert any("israel/" in aid for aid in agent_ids)


def test_event_without_relevance_score_treated_as_zero():
    router = AgentRouter(AgentRegistry())
    event = {
        "actor1": "IRGC",
        "actor2": "USA",
        "summary": "Something important",
        # No relevance_score
    }
    agents = router.route(event)
    assert len(agents) == 0
