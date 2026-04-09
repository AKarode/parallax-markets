"""Oil price prediction model using cascade engine + LLM reasoning.

Combines deterministic cascade analysis (supply disruption scenarios)
with a single Claude Sonnet call for probabilistic prediction.
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

OIL_PRICE_SYSTEM_PROMPT = """You are an oil market analyst. Given the cascade analysis and recent events, predict oil price direction and magnitude over the next 7 days.

Context:
- Cascade analysis shows {supply_loss:.0f} bbl/day disruption
- Bypass flow: {bypass_flow:.0f} bbl/day through alternate routes
- Price shock estimate: {price_shock_pct:.1f}%
- Current Brent price: ${current_price:.2f}/bbl

Recent GDELT events:
{events_summary}

Current EIA price data:
{price_data}

## YOUR TRACK RECORD
{track_record}

Output ONLY valid JSON (no markdown):
{{
  "probability": <float 0-1, probability of significant price movement>,
  "confidence": <float 0-1, how confident you are in this estimate>,
  "direction": "<increase|decrease|stable>",
  "magnitude_range": [<low_dollars>, <high_dollars>],
  "reasoning": "<detailed chain-of-thought analysis (500-1000 words). Explain what the market may be missing, second-order effects, and key uncertainties>",
  "evidence": ["<evidence 1>", "<evidence 2>", "<evidence 3>", "...(3-5 total)"]
}}"""


class OilPricePredictor:
    """Predicts oil price direction using cascade engine + LLM."""

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
        current_prices: list[dict],
        world_state: WorldState,
        db_conn: duckdb.DuckDBPyConnection | None = None,
    ) -> PredictionOutput:
        """Run oil price prediction pipeline.

        1. Run cascade engine for supply disruption scenario
        2. Feed results + events to Claude Sonnet
        3. Parse structured response
        """
        # Build track record for prompt injection
        if db_conn is not None:
            from parallax.scoring.track_record import build_track_record
            track_record = build_track_record("oil_price", db_conn)
        else:
            track_record = "No track record available yet."

        # Step 1: Cascade analysis
        supply_loss = 0.0
        bypass_flow = 0.0
        price_shock_pct = 0.0

        # Find Hormuz cells and compute disruption
        for cell_id, cell_data in self._iter_cells(world_state):
            if cell_data.get("status") in ("blocked", "restricted"):
                result = self._cascade.apply_blockade(world_state, cell_id, 0.5)
                supply_loss += result.get("supply_loss", 0.0)

        if supply_loss > 0:
            current_price = self._get_current_brent(current_prices)
            # compute_price_shock(current_price, supply_loss, bypass_active) -> float
            new_price = self._cascade.compute_price_shock(
                current_price, supply_loss, bypass_flow,
            )
            if current_price > 0:
                price_shock_pct = ((new_price - current_price) / current_price) * 100

        current_price = self._get_current_brent(current_prices)

        # Step 2: Format events summary
        events_summary = self._format_events(recent_events[:10])
        price_data = self._format_prices(current_prices[:5])

        # Step 3: LLM call
        prompt = OIL_PRICE_SYSTEM_PROMPT.format(
            supply_loss=supply_loss,
            bypass_flow=bypass_flow,
            price_shock_pct=price_shock_pct,
            current_price=current_price,
            events_summary=events_summary,
            price_data=price_data,
            track_record=track_record,
        )

        response = await self._client.messages.create(
            model="claude-opus-4-20250514",
            max_tokens=2000,
            messages=[{"role": "user", "content": prompt}],
        )

        # Record budget
        usage = response.usage
        self._budget.record(usage.input_tokens, usage.output_tokens, "opus")

        # Step 4: Parse response
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
            logger.error("Failed to parse oil_price raw response: %s", raw_text)
            raise ValueError(
                f"Failed to parse oil_price LLM response: {text[:200]}",
            ) from exc

        return PredictionOutput(
            model_id="oil_price",
            prediction_type="oil_price_direction",
            probability=parsed["probability"],
            direction=parsed["direction"],
            magnitude_range=parsed["magnitude_range"],
            unit="USD/bbl",
            timeframe="7d",
            confidence=parsed.get("confidence", 0.5),
            reasoning=parsed["reasoning"],
            evidence=parsed.get("evidence", []),
            created_at=datetime.now(timezone.utc),
            kalshi_ticker=None,  # mapped dynamically by brief pipeline
        )

    @staticmethod
    def _iter_cells(ws: WorldState):
        """Iterate over all cells in world state."""
        for cell_id in list(ws._cells.keys()):
            yield cell_id, ws.get_cell(cell_id) or {}

    @staticmethod
    def _get_current_brent(prices: list[dict]) -> float:
        """Extract latest Brent price from EIA data."""
        for p in prices:
            if p.get("series-id", "").startswith("RBRTE") or "brent" in str(p).lower():
                return float(p.get("value", 100.0))
        return 100.0  # fallback

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
                action = e.get("EventCode", "")
                lines.append(f"- {actor1} -> {actor2}: {action}")
        return "\n".join(lines)

    @staticmethod
    def _format_prices(prices: list[dict]) -> str:
        if not prices:
            return "No price data available."
        lines = []
        for p in prices:
            period = p.get("period", "?")
            value = p.get("value", "?")
            lines.append(f"- {period}: ${value}")
        return "\n".join(lines)

