import json
import logging
from typing import Any

from parallax.agents.schemas import SubActorRecommendation
from parallax.budget.tracker import BudgetTracker

logger = logging.getLogger(__name__)

# Model ID mapping with prompt caching support
_MODEL_IDS = {
    "haiku": "claude-haiku-4-5-20251001",
    "sonnet": "claude-sonnet-4-6",
    "opus": "claude-opus-4-6",
}


class AgentRunner:
    """Runs sub-actor LLM calls with budget enforcement and prompt caching."""

    def __init__(
        self,
        client: Any,  # anthropic.AsyncAnthropic
        budget: BudgetTracker,
        max_input_tokens: int = 4000,
        max_output_tokens: int = 500,
    ) -> None:
        self._client = client
        self._budget = budget
        self._max_input = max_input_tokens
        self._max_output = max_output_tokens

    async def run_sub_actor(
        self,
        agent_id: str,
        system_prompt: str,
        context: str,
        prompt_version: str,
        model: str = "haiku",
    ) -> SubActorRecommendation | None:
        """Run a single sub-actor agent against an event context.

        Uses Anthropic prompt caching (1-hour TTL) for system prompts.
        Returns None if budget is exceeded or the call fails.
        """
        if self._budget.is_over_budget():
            logger.warning("Budget exceeded, skipping %s", agent_id)
            return None

        model_id = _MODEL_IDS.get(model, _MODEL_IDS["sonnet"])

        try:
            response = await self._client.messages.create(
                model=model_id,
                max_tokens=self._max_output,
                system=[
                    {
                        "type": "text",
                        "text": system_prompt,
                        "cache_control": {"type": "ephemeral"},
                    }
                ],
                messages=[
                    {
                        "role": "user",
                        "content": (
                            f"Analyze this event and respond with a JSON object containing: "
                            f"action_type, description, reasoning, intensity (0-1), "
                            f"confidence (0-1), significance (0-1).\n\n"
                            f"Event:\n{context}"
                        ),
                    }
                ],
            )

            self._budget.record(
                input_tokens=response.usage.input_tokens,
                output_tokens=response.usage.output_tokens,
                model=model,
            )

            raw = response.content[0].text
            data = json.loads(raw)
            return SubActorRecommendation(agent_id=agent_id, **data)

        except Exception:
            logger.exception("Agent %s failed", agent_id)
            return None

    async def run_sub_actors_parallel(
        self,
        agents: list[dict],
        model: str = "haiku",
    ) -> list[SubActorRecommendation]:
        """Run multiple sub-actor agents in parallel.

        Each entry in agents should have: agent_id, system_prompt, context, prompt_version
        """
        import asyncio

        tasks = [
            self.run_sub_actor(
                agent_id=a["agent_id"],
                system_prompt=a["system_prompt"],
                context=a["context"],
                prompt_version=a["prompt_version"],
                model=model,
            )
            for a in agents
        ]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        return [r for r in results if isinstance(r, SubActorRecommendation)]
