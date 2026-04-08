"""Ceasefire probability prediction model.

Filters GDELT events for diplomatic signals (CAMEO codes 03/04 = cooperation),
feeds diplomatic event chain to Claude Sonnet for probability estimation.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Any

from parallax.budget.tracker import BudgetTracker
from parallax.prediction.schemas import PredictionOutput

logger = logging.getLogger(__name__)

CEASEFIRE_SYSTEM_PROMPT = """You are a geopolitical analyst specializing in conflict resolution. Given these recent diplomatic events about Iran-US negotiations, estimate the probability of a ceasefire holding through the next 14 days.

Consider:
- Talks location and formality
- Mediator involvement (Qatar, Oman, Switzerland)
- Military posture signals (deployments, exercises, withdrawals)
- Historical precedent for similar diplomatic configurations
- Economic pressure indicators

Recent diplomatic events:
{diplomatic_events}

Additional context:
{context}

Output ONLY valid JSON (no markdown):
{{
  "probability": <float 0-1, probability of ceasefire holding>,
  "reasoning": "<2-3 sentence analysis>",
  "evidence": ["<key evidence point 1>", "<key evidence point 2>"]
}}"""

# CAMEO event codes for cooperative actions
DIPLOMATIC_CODES = {"03", "04", "05", "036", "040", "042", "043", "046"}


class CeasefirePredictor:
    """Predicts ceasefire probability from diplomatic signal analysis."""

    def __init__(
        self,
        budget: BudgetTracker,
        anthropic_client: Any,
    ) -> None:
        self._budget = budget
        self._client = anthropic_client

    async def predict(
        self,
        recent_events: list[dict],
        current_negotiations: str | None = None,
    ) -> PredictionOutput:
        """Run ceasefire prediction pipeline.

        1. Filter events for diplomatic signals
        2. Feed to Claude Sonnet
        3. Parse structured response
        """
        # Step 1: Filter for diplomatic events
        diplomatic = self._filter_diplomatic(recent_events)

        # Step 2: Format and call LLM
        events_text = self._format_events(diplomatic) if diplomatic else self._format_events(recent_events[:5])
        context = current_negotiations or "No specific negotiation context provided."

        prompt = CEASEFIRE_SYSTEM_PROMPT.format(
            diplomatic_events=events_text,
            context=context,
        )

        response = await self._client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=500,
            messages=[{"role": "user", "content": prompt}],
        )

        usage = response.usage
        self._budget.record(usage.input_tokens, usage.output_tokens, "sonnet")

        # Step 3: Parse response
        text = response.content[0].text
        parsed = json.loads(text)

        return PredictionOutput(
            model_id="ceasefire",
            prediction_type="ceasefire_probability",
            probability=parsed["probability"],
            direction="stable",
            magnitude_range=[0.0, 1.0],
            unit="probability",
            timeframe="14d",
            confidence=parsed["probability"],
            reasoning=parsed["reasoning"],
            evidence=parsed.get("evidence", []),
            created_at=datetime.now(timezone.utc),
            kalshi_ticker="KXIRANCEASEFIRE",
        )

    @staticmethod
    def _filter_diplomatic(events: list[dict]) -> list[dict]:
        """Filter events for diplomatic/cooperative signals.

        For new-format news events (with 'title'), use keyword matching
        since they lack CAMEO codes. For legacy GDELT BigQuery events,
        use CAMEO event code filtering.
        """
        diplomatic_keywords = {
            "ceasefire", "negotiation", "talks", "diplomacy", "diplomatic",
            "mediator", "mediation", "peace", "agreement", "treaty",
            "de-escalation", "withdrawal", "cooperation",
        }
        result = []
        for e in events:
            # New news format: keyword-based filtering
            if "title" in e:
                title_lower = e["title"].lower()
                if any(kw in title_lower for kw in diplomatic_keywords):
                    result.append(e)
                continue
            # Legacy GDELT BigQuery format: CAMEO code filtering
            code = str(e.get("EventCode", ""))
            root_code = code[:2] if len(code) >= 2 else code
            if root_code in DIPLOMATIC_CODES or code in DIPLOMATIC_CODES:
                result.append(e)
        return result

    @staticmethod
    def _format_events(events: list[dict]) -> str:
        if not events:
            return "No events available."
        lines = []
        for e in events[:20]:
            # Support both new news format and legacy GDELT BigQuery format
            if "title" in e:
                lines.append(f"- [{e.get('published_at', 'unknown')}] {e['title']}")
                if e.get("snippet"):
                    lines.append(f"  {e['snippet'][:200]}")
            else:
                actor1 = e.get("Actor1Name", "Unknown")
                actor2 = e.get("Actor2Name", "Unknown")
                code = e.get("EventCode", "?")
                goldstein = e.get("GoldsteinScale", 0)
                lines.append(f"- {actor1} -> {actor2}: code={code}, goldstein={goldstein}")
        return "\n".join(lines)
