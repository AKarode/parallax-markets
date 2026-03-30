"""Country-level agent that synthesizes sub-actor recommendations with weighted conflict resolution."""

import json
import logging
from typing import Any

from parallax.agents.registry import AgentRegistry
from parallax.agents.schemas import CountryDecision, SubActorRecommendation
from parallax.budget.tracker import BudgetTracker

logger = logging.getLogger(__name__)


class CountryAgent:
    """Synthesizes sub-actor recommendations into a single country-level decision.

    Uses Sonnet (higher-tier model) for country-level reasoning.
    Applies influence weights from the registry to resolve conflicts.
    """

    def __init__(
        self,
        client: Any,  # anthropic.AsyncAnthropic
        registry: AgentRegistry,
        budget: BudgetTracker,
        max_input_tokens: int = 8000,
        max_output_tokens: int = 1000,
    ) -> None:
        self._client = client
        self._registry = registry
        self._budget = budget
        self._max_input = max_input_tokens
        self._max_output = max_output_tokens

    def _build_synthesis_prompt(
        self,
        country: str,
        recommendations: list[SubActorRecommendation],
    ) -> str:
        """Build a prompt that presents weighted sub-actor recommendations for synthesis."""
        lines = []
        for rec in recommendations:
            agent_info = self._registry.get_agent(rec.agent_id)
            weight = agent_info.weight if agent_info else 0.5
            lines.append(
                f"- {rec.agent_id} (weight={weight:.1f}): "
                f"action={rec.action_type}, intensity={rec.intensity:.2f}, "
                f"confidence={rec.confidence:.2f}, significance={rec.significance:.2f}\n"
                f"  Reasoning: {rec.reasoning}"
            )

        return (
            f"You are the {country} country-level decision agent. "
            f"Below are recommendations from your sub-actors, each with an influence weight. "
            f"Higher-weight actors have more authority.\n\n"
            f"Sub-actor recommendations:\n" + "\n".join(lines) + "\n\n"
            f"Synthesize these into a single country decision. Resolve conflicts by "
            f"weighting higher-authority actors more heavily. Respond with a JSON object "
            f"containing: action_type, target_h3_cells (list of ints, use [] if not spatial), "
            f"intensity (0-1), description, reasoning, confidence (0-1)."
        )

    async def synthesize(
        self,
        country: str,
        recommendations: list[SubActorRecommendation],
        tick: int,
        prompt_version: str,
    ) -> CountryDecision | None:
        """Synthesize sub-actor recommendations into a country decision.

        Only fires if at least one recommendation has significance >= 0.5.
        Uses Sonnet model for higher-quality reasoning.
        """
        # Only fire if significant recommendations exist
        if not any(r.significance >= 0.5 for r in recommendations):
            logger.debug("No significant recommendations for %s, skipping", country)
            return None

        if self._budget.is_over_budget():
            logger.warning("Budget exceeded, skipping country agent for %s", country)
            return None

        synthesis_prompt = self._build_synthesis_prompt(country, recommendations)

        try:
            response = await self._client.messages.create(
                model="claude-sonnet-4-6",
                max_tokens=self._max_output,
                system=[
                    {
                        "type": "text",
                        "text": (
                            f"You are the country-level synthesis agent for {country}. "
                            f"Your job is to resolve conflicting sub-actor recommendations "
                            f"into a single coherent national decision."
                        ),
                        "cache_control": {"type": "ephemeral"},
                    }
                ],
                messages=[
                    {"role": "user", "content": synthesis_prompt},
                ],
            )

            self._budget.record(
                input_tokens=response.usage.input_tokens,
                output_tokens=response.usage.output_tokens,
                model="sonnet",
            )

            raw = response.content[0].text
            data = json.loads(raw)

            return CountryDecision(
                country=country,
                tick=tick,
                action_type=data["action_type"],
                target_h3_cells=data.get("target_h3_cells", []),
                intensity=data["intensity"],
                description=data["description"],
                reasoning=data["reasoning"],
                confidence=data["confidence"],
                prompt_version=prompt_version,
                contributing_agents=[r.agent_id for r in recommendations],
            )

        except Exception:
            logger.exception("Country agent for %s failed", country)
            return None
