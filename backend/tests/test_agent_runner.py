import pytest
from unittest.mock import AsyncMock, patch
from parallax.agents.runner import AgentRunner
from parallax.agents.schemas import SubActorRecommendation
from parallax.agents.registry import AgentRegistry
from parallax.budget.tracker import BudgetTracker


@pytest.mark.asyncio
async def test_runner_calls_llm_and_parses_response():
    mock_client = AsyncMock()
    mock_client.messages.create.return_value = AsyncMock(
        content=[AsyncMock(text='{"action_type":"patrol","description":"Increased patrols","reasoning":"Deterrence","intensity":0.6,"confidence":0.7,"significance":0.8}')],
        usage=AsyncMock(input_tokens=1000, output_tokens=200),
    )

    runner = AgentRunner(
        client=mock_client,
        budget=BudgetTracker(daily_cap_usd=20.0),
        max_input_tokens=4000,
        max_output_tokens=500,
    )

    rec = await runner.run_sub_actor(
        agent_id="iran/irgc_navy",
        system_prompt="You are the IRGC Navy.",
        context="CENTCOM repositioned carrier group.",
        prompt_version="v1.0.0",
        model="haiku",
    )

    assert isinstance(rec, SubActorRecommendation)
    assert rec.action_type == "patrol"
    assert rec.confidence == 0.7


@pytest.mark.asyncio
async def test_runner_respects_budget_cap():
    runner = AgentRunner(
        client=AsyncMock(),
        budget=BudgetTracker(daily_cap_usd=0.0),  # Zero budget
        max_input_tokens=4000,
        max_output_tokens=500,
    )

    rec = await runner.run_sub_actor(
        agent_id="iran/irgc_navy",
        system_prompt="You are the IRGC Navy.",
        context="Event",
        prompt_version="v1.0.0",
        model="haiku",
    )
    assert rec is None  # Should skip due to budget


@pytest.mark.asyncio
async def test_runner_handles_llm_failure_gracefully():
    mock_client = AsyncMock()
    mock_client.messages.create.side_effect = Exception("API error")

    runner = AgentRunner(
        client=mock_client,
        budget=BudgetTracker(daily_cap_usd=20.0),
    )

    rec = await runner.run_sub_actor(
        agent_id="iran/irgc_navy",
        system_prompt="You are the IRGC Navy.",
        context="Event",
        prompt_version="v1.0.0",
        model="haiku",
    )
    assert rec is None  # Should return None on failure


@pytest.mark.asyncio
async def test_runner_handles_invalid_json_gracefully():
    mock_client = AsyncMock()
    mock_client.messages.create.return_value = AsyncMock(
        content=[AsyncMock(text="Not valid JSON")],
        usage=AsyncMock(input_tokens=500, output_tokens=50),
    )

    runner = AgentRunner(
        client=mock_client,
        budget=BudgetTracker(daily_cap_usd=20.0),
    )

    rec = await runner.run_sub_actor(
        agent_id="iran/irgc_navy",
        system_prompt="You are the IRGC Navy.",
        context="Event",
        prompt_version="v1.0.0",
        model="haiku",
    )
    assert rec is None


@pytest.mark.asyncio
async def test_runner_records_spend_after_call():
    mock_client = AsyncMock()
    mock_client.messages.create.return_value = AsyncMock(
        content=[AsyncMock(text='{"action_type":"patrol","description":"x","reasoning":"x","intensity":0.5,"confidence":0.5,"significance":0.5}')],
        usage=AsyncMock(input_tokens=2000, output_tokens=300),
    )

    budget = BudgetTracker(daily_cap_usd=20.0)
    runner = AgentRunner(client=mock_client, budget=budget)

    await runner.run_sub_actor(
        agent_id="iran/irgc_navy",
        system_prompt="test",
        context="test",
        prompt_version="v1.0.0",
        model="haiku",
    )

    assert budget.total_spend_today() > 0.0


@pytest.mark.asyncio
async def test_runner_uses_prompt_caching():
    """Verify the runner sends system prompt with cache_control for prompt caching."""
    mock_client = AsyncMock()
    mock_client.messages.create.return_value = AsyncMock(
        content=[AsyncMock(text='{"action_type":"patrol","description":"x","reasoning":"x","intensity":0.5,"confidence":0.5,"significance":0.5}')],
        usage=AsyncMock(input_tokens=1000, output_tokens=200),
    )

    runner = AgentRunner(
        client=mock_client,
        budget=BudgetTracker(daily_cap_usd=20.0),
    )

    await runner.run_sub_actor(
        agent_id="iran/irgc_navy",
        system_prompt="You are the IRGC Navy.",
        context="Event",
        prompt_version="v1.0.0",
        model="haiku",
    )

    # Verify the system prompt was sent with cache_control
    call_kwargs = mock_client.messages.create.call_args
    system_arg = call_kwargs.kwargs.get("system") or call_kwargs[1].get("system")
    assert isinstance(system_arg, list)
    assert system_arg[0]["cache_control"] == {"type": "ephemeral"}


@pytest.mark.asyncio
async def test_runner_parallel_execution():
    mock_client = AsyncMock()
    mock_client.messages.create.return_value = AsyncMock(
        content=[AsyncMock(text='{"action_type":"patrol","description":"x","reasoning":"x","intensity":0.5,"confidence":0.5,"significance":0.5}')],
        usage=AsyncMock(input_tokens=1000, output_tokens=200),
    )

    runner = AgentRunner(
        client=mock_client,
        budget=BudgetTracker(daily_cap_usd=20.0),
    )

    agents = [
        {"agent_id": "iran/irgc_navy", "system_prompt": "test", "context": "event", "prompt_version": "v1.0.0"},
        {"agent_id": "iran/irgc", "system_prompt": "test", "context": "event", "prompt_version": "v1.0.0"},
    ]

    results = await runner.run_sub_actors_parallel(agents, model="haiku")
    assert len(results) == 2
    assert all(isinstance(r, SubActorRecommendation) for r in results)
