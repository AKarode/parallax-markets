"""Hormuz Strait reopening prediction model.

Checks current world state for Hormuz cell status, runs cascade scenarios
for partial and full reopening, and feeds analysis to Claude Sonnet.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Any

import duckdb

from parallax.budget.tracker import BudgetTracker
from parallax.prediction.schemas import PredictionOutput
from parallax.simulation.cascade import CascadeEngine
from parallax.simulation.world_state import WorldState

logger = logging.getLogger(__name__)

HORMUZ_SYSTEM_PROMPT = """You are a maritime security analyst. Given the current Hormuz strait status and recent events, estimate reopening probabilities.

Current status:
{flow_data}

Scenario analysis:
- 25% reopening: supply recovery = {recovery_25:.0f} bbl/day
- 50% reopening: supply recovery = {recovery_50:.0f} bbl/day
- 100% reopening: supply recovery = {recovery_100:.0f} bbl/day

Recent events:
{events_summary}

Current market prices:
{market_prices_text}

## YOUR TRACK RECORD
{track_record}

Consider what the market may already be pricing in and where it might be wrong.

Estimate:
(a) Probability of partial reopening (>25% flow restored) within 14 days
(b) Probability of full reopening within 30 days

Output ONLY valid JSON (no markdown):
{{
  "probability": <float 0-1, probability of partial reopening within 14d>,
  "confidence": <float 0-1, how confident you are in this estimate>,
  "direction": "<increase|decrease|stable>",
  "magnitude_range": [<low_pct_reopening>, <high_pct_reopening>],
  "reasoning": "<detailed chain-of-thought analysis (500-1000 words). Explain what the market may be missing, second-order effects, and key uncertainties>",
  "evidence": ["<evidence 1>", "<evidence 2>", "<evidence 3>", "...(3-5 total)"]
}}"""


class HormuzReopeningPredictor:
    """Predicts Hormuz strait reopening probability."""

    def __init__(
        self,
        cascade_engine: CascadeEngine,
        budget: BudgetTracker,
        anthropic_client: Any,
    ) -> None:
        self._cascade = cascade_engine
        self._budget = budget
        self._client = anthropic_client

    async def predict(
        self,
        recent_events: list[dict],
        world_state: WorldState,
        market_prices: list[dict] | None = None,
        db_conn: duckdb.DuckDBPyConnection | None = None,
    ) -> PredictionOutput:
        """Run Hormuz reopening prediction pipeline.

        1. Check current Hormuz cell status
        2. Run cascade scenarios for 25/50/100% reopening
        3. Feed to Claude Sonnet
        4. Parse structured response
        """
        # Build track record for prompt injection
        if db_conn is not None:
            from parallax.scoring.track_record import build_track_record
            track_record = build_track_record("hormuz_reopening", db_conn)
        else:
            track_record = "No track record available yet."

        # Step 1: Current status
        flow_data = self._get_hormuz_status(world_state)

        # Step 2: Scenario analysis
        recovery_25 = self._estimate_recovery(world_state, 0.25)
        recovery_50 = self._estimate_recovery(world_state, 0.50)
        recovery_100 = self._estimate_recovery(world_state, 1.00)

        # Step 3: LLM call
        events_summary = self._format_events(recent_events[:10])
        prompt = HORMUZ_SYSTEM_PROMPT.format(
            flow_data=flow_data,
            recovery_25=recovery_25,
            recovery_50=recovery_50,
            recovery_100=recovery_100,
            events_summary=events_summary,
            market_prices_text=self._format_market_prices(market_prices),
            track_record=track_record,
        )

        response = await self._client.messages.create(
            model="claude-opus-4-20250514",
            max_tokens=2000,
            messages=[{"role": "user", "content": prompt}],
        )

        usage = response.usage
        self._budget.record(usage.input_tokens, usage.output_tokens, "opus")

        # Step 4: Parse
        raw_text = response.content[0].text
        text = raw_text.strip()
        if text.startswith("```json") or text.startswith("```"):
            lines = text.splitlines()
            text = "\n".join(lines[1:]).strip()
        if text.endswith("```"):
            text = text[:-3].rstrip()
        try:
            parsed = json.loads(text)
        except json.JSONDecodeError as exc:
            logger.error("Failed to parse hormuz_reopening raw response: %s", raw_text)
            raise ValueError(
                f"Failed to parse hormuz_reopening LLM response: {text[:200]}",
            ) from exc

        return PredictionOutput(
            model_id="hormuz_reopening",
            prediction_type="hormuz_reopening",
            probability=parsed["probability"],
            direction=parsed.get("direction", "stable"),
            magnitude_range=parsed.get("magnitude_range", [0.0, 100.0]),
            unit="pct_reopening",
            timeframe="14d",
            confidence=parsed.get("confidence", 0.5),
            reasoning=parsed["reasoning"],
            evidence=parsed.get("evidence", []),
            created_at=datetime.now(timezone.utc),
            kalshi_ticker=None,  # mapped dynamically by brief pipeline
        )

    @staticmethod
    def _get_hormuz_status(ws: WorldState) -> str:
        """Summarize current Hormuz-area cell status."""
        blocked = 0
        restricted = 0
        open_cells = 0
        total_flow = 0.0

        for cell_id in list(ws._cells.keys()):
            cell = ws.get_cell(cell_id)
            if cell is None:
                continue
            status = cell.get("status", "open")
            if status == "blocked":
                blocked += 1
            elif status == "restricted":
                restricted += 1
            else:
                open_cells += 1
            total_flow += cell.get("flow", 0.0)

        return (
            f"Cells: {blocked} blocked, {restricted} restricted, {open_cells} open. "
            f"Total flow: {total_flow:.0f} bbl/day"
        )

    def _estimate_recovery(self, ws: WorldState, reopening_pct: float) -> float:
        """Estimate supply recovery if Hormuz reopens by given percentage."""
        config = self._cascade._config
        max_flow = getattr(config, "hormuz_daily_flow", 21_000_000)
        # Current flow from all cells
        current = sum(
            (ws.get_cell(cid) or {}).get("flow", 0.0) for cid in ws._cells
        )
        potential_recovery = (max_flow - current) * reopening_pct
        return max(potential_recovery, 0.0)

    @staticmethod
    def _format_events(events: list[dict]) -> str:
        if not events:
            return "No recent events available."
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
                lines.append(f"- {actor1} -> {actor2}: code={code}")
        return "\n".join(lines)

    @staticmethod
    def _format_market_prices(market_prices: list[dict] | None) -> str:
        if not market_prices:
            return "No market prices available."
        lines = []
        for mp in market_prices:
            lines.append(f"- {mp['ticker']} ({mp['source']}): YES {mp['yes_price']:.0%}")
        return "\n".join(lines)
