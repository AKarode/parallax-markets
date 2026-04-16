"""Ceasefire probability prediction model.

Filters GDELT events for diplomatic signals (CAMEO codes 03/04 = cooperation),
feeds diplomatic event chain to Claude Sonnet ensemble for probability estimation.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

import duckdb

from parallax.budget.tracker import BudgetTracker
from parallax.prediction.ensemble import ensemble_predict
from parallax.prediction.schemas import PredictionOutput

logger = logging.getLogger(__name__)

CEASEFIRE_SYSTEM_PROMPT = """You are a geopolitical analyst specializing in conflict resolution. Given these recent diplomatic events about Iran-US negotiations, estimate the probability that a formal US-Iran agreement will be reached by mid-2027.

IMPORTANT: You are predicting a FORMAL AGREEMENT — a signed deal, framework accord, or binding diplomatic agreement between the US and Iran. This is NOT about whether a ceasefire holds day-to-day. A ceasefire holding is necessary but NOT sufficient — many ceasefires never produce formal agreements.

Consider:
- Current negotiation stage (back-channel vs. formal talks vs. near-framework)
- Historical base rate: US-Iran formal agreements are extremely rare (JCPOA took 2+ years of formal talks)
- Mediator involvement and track record (Qatar, Oman, Switzerland)
- Domestic political constraints on both sides (US election cycle, Iranian hardliners)
- Military posture signals (deployments, exercises, withdrawals)
- Sanctions relief dynamics and economic pressure
- Gap between ceasefire/de-escalation and formal agreement

Recent diplomatic events:
{diplomatic_events}

Additional context:
{context}

## YOUR TRACK RECORD
{track_record}

Consider what the market may already be pricing in and where it might be wrong.

Output ONLY valid JSON (no markdown):
{{
  "probability": <float 0-1, probability of formal US-Iran agreement by mid-2027>,
  "confidence": <float 0-1, how confident you are in this estimate>,
  "direction": "<increase|decrease|stable>",
  "magnitude_range": [<low>, <high>],
  "reasoning": "<detailed chain-of-thought analysis (500-1000 words). Explain what the market may be missing, second-order effects, and key uncertainties>",
  "evidence": ["<evidence 1>", "<evidence 2>", "<evidence 3>", "...(3-5 total)"]
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
        db_conn: duckdb.DuckDBPyConnection | None = None,
    ) -> PredictionOutput:
        """Run ceasefire prediction pipeline.

        1. Filter events for diplomatic signals
        2. Feed to Claude Sonnet
        3. Parse structured response
        """
        # Build track record for prompt injection
        if db_conn is not None:
            from parallax.scoring.track_record import build_track_record
            track_record = build_track_record("ceasefire", db_conn)
        else:
            track_record = "No track record available yet."

        # Step 1: Filter for diplomatic events
        diplomatic = self._filter_diplomatic(recent_events)

        # Step 2: Format and call LLM
        events_text = self._format_events(diplomatic) if diplomatic else self._format_events(recent_events[:5])
        context = current_negotiations or "No specific negotiation context provided."

        from parallax.prediction.crisis_context import get_crisis_context

        prompt = get_crisis_context() + "\n\n" + CEASEFIRE_SYSTEM_PROMPT.format(
            diplomatic_events=events_text,
            context=context,
            track_record=track_record,
        )

        result = await ensemble_predict(
            client=self._client,
            model="claude-opus-4-20250514",
            prompt=prompt,
            budget=self._budget,
            max_tokens=2000,
        )
        ensemble = result["ensemble"]
        parsed = result["parsed"]

        confidence = parsed.get("confidence", 0.5)
        if ensemble["is_unstable"]:
            confidence *= 0.5

        return PredictionOutput(
            model_id="ceasefire",
            prediction_type="ceasefire_probability",
            probability=ensemble["probability"],
            direction=parsed.get("direction", "stable"),
            magnitude_range=parsed.get("magnitude_range", [0.0, 1.0]),
            unit="probability",
            timeframe="14d",
            confidence=confidence,
            reasoning=f"{parsed['reasoning']}\n\n[Ensemble: probabilities={ensemble['individual_probabilities']}, method=trimmed_mean, std_dev={ensemble['std_dev']:.3f}]",
            evidence=parsed.get("evidence", []),
            created_at=datetime.now(timezone.utc),
            kalshi_ticker=None,  # mapped dynamically by brief pipeline
            ensemble_probabilities=ensemble["individual_probabilities"],
            ensemble_std_dev=ensemble["std_dev"],
            ensemble_is_unstable=ensemble["is_unstable"],
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

