"""Oil price prediction model using cascade engine + LLM ensemble.

Combines deterministic cascade analysis (supply disruption scenarios)
with 3 concurrent Claude Sonnet calls for probabilistic prediction.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

import duckdb

from parallax.budget.tracker import BudgetTracker
from parallax.prediction.ensemble import ensemble_predict
from parallax.prediction.schemas import PredictionOutput, _sanitize_headline
from parallax.simulation.cascade import CascadeEngine
from parallax.simulation.world_state import WorldState

logger = logging.getLogger(__name__)

OIL_PRICE_SYSTEM_PROMPT = """You are an oil market analyst. Given the cascade analysis and recent events, predict oil price direction and magnitude over the next 7 days.

Context:
- Cascade analysis shows {supply_loss:.0f} bbl/day disruption
- Bypass flow: {bypass_flow:.0f} bbl/day through alternate routes
- Price shock estimate: {price_shock_pct:.1f}%
- Brent {price_signal}

Recent GDELT events:
{events_summary}

## YOUR TRACK RECORD
{track_record}

Consider what the market may already be pricing in and where it might be wrong. Reason from supply/demand fundamentals and cascade dynamics, not from anchoring to the current price level.

Output ONLY valid JSON (no markdown):
{{
  "probability": <float 0-1, probability of significant price movement>,
  "confidence": <float 0-1, how confident you are in this estimate>,
  "direction": "<increase|decrease|stable>",
  "magnitude_range": [<low_dollars>, <high_dollars>],
  "reasoning": "<detailed chain-of-thought analysis (500-1000 words). Explain what the market may be missing, second-order effects, and key uncertainties>",
  "evidence": ["<evidence 1>", "<evidence 2>", "<evidence 3>", "...(3-5 total)"]
}}

## Reference Data
{price_data}"""


def _classify_price_regime(price: float) -> str:
    """Bucket Brent price into a regime label to avoid LLM anchoring on exact $."""
    if price < 80.0:
        return "normal"
    if price < 100.0:
        return "elevated"
    return "high"


def _build_price_signal(current_price: float, pct_change_24h: float | None) -> str:
    """Build a relative price signal string (no verbatim $ value in reasoning frame).

    Returns a regime + delta signal rather than the literal price to reduce
    mean-reversion anchoring bias.
    """
    regime = _classify_price_regime(current_price)
    if pct_change_24h is None:
        # TODO: wire pct_change_24h through from EIA history when available
        return f"price is in {regime} regime"
    return f"price moved {pct_change_24h:+.1f}% in last 24h, currently in {regime} regime"


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
        *,
        context_age_hours: float | None = None,
        crisis_context_text: str | None = None,
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

        # BUG-01 FIX: operate on a copy so cascade mutations don't corrupt shared state
        ws_copy = world_state.copy()

        # Step 1: Cascade analysis
        supply_loss = 0.0
        price_shock_pct = 0.0

        # Find Hormuz cells and compute disruption
        for cell_id, cell_data in self._iter_cells(ws_copy):
            if cell_data.get("status") in ("blocked", "restricted"):
                result = self._cascade.apply_blockade(ws_copy, cell_id, 0.5)
                supply_loss += result.get("supply_loss", 0.0)

        # Compute bypass flow from cascade engine
        bypass_result = self._cascade.activate_bypass(supply_loss)
        bypass_flow = bypass_result["bypass_flow"]

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
        if context_age_hours is None or crisis_context_text is None:
            from parallax.prediction.crisis_context import get_crisis_context_with_metadata

            crisis = get_crisis_context_with_metadata(db_conn)
            if context_age_hours is None:
                context_age_hours = crisis.context_age_hours
            if crisis_context_text is None:
                crisis_context_text = crisis.context

        # TODO: pct_change_24h not yet plumbed through current_prices; use regime-only signal
        price_signal = _build_price_signal(current_price, pct_change_24h=None)
        prompt = crisis_context_text + "\n\n" + OIL_PRICE_SYSTEM_PROMPT.format(
            supply_loss=supply_loss,
            bypass_flow=bypass_flow,
            price_shock_pct=price_shock_pct,
            price_signal=price_signal,
            events_summary=events_summary,
            price_data=price_data,
            track_record=track_record,
        )

        result = await ensemble_predict(
            client=self._client,
            model="claude-opus-4-20250514",
            prompt=prompt,
            budget=self._budget,
            max_tokens=2000,
            context_age_hours=context_age_hours,
        )
        ensemble = result["ensemble"]
        parsed = result["parsed"]

        confidence = parsed.get("confidence", 0.5)
        if ensemble["is_unstable"]:
            confidence *= 0.5

        return PredictionOutput(
            model_id="oil_price",
            prediction_type="oil_price_direction",
            probability=ensemble["probability"],
            direction=parsed["direction"],
            magnitude_range=parsed["magnitude_range"],
            unit="USD/bbl",
            timeframe="7d",
            confidence=confidence,
            reasoning=f"{parsed['reasoning']}\n\n[Ensemble: probabilities={ensemble['individual_probabilities']}, method=trimmed_mean, std_dev={ensemble['std_dev']:.3f}]",
            evidence=parsed.get("evidence", []),
            created_at=datetime.now(timezone.utc),
            kalshi_ticker=None,  # mapped dynamically by brief pipeline
            ensemble_probabilities=ensemble["individual_probabilities"],
            ensemble_std_dev=ensemble["std_dev"],
            ensemble_is_unstable=ensemble["is_unstable"],
            context_age_hours=result.get("context_age_hours"),
            penalty_factor=result.get("penalty_factor", 1.0),
            staleness_penalty_applied=result.get("staleness_penalty_applied", False),
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
                published = _sanitize_headline(str(e.get("published_at", "unknown")))
                title = _sanitize_headline(e["title"])
                lines.append(f"- [{published}] {title}")
                if e.get("snippet"):
                    lines.append(f"  {_sanitize_headline(e['snippet'])}")
            else:
                actor1 = _sanitize_headline(str(e.get("Actor1Name", "Unknown")))
                actor2 = _sanitize_headline(str(e.get("Actor2Name", "Unknown")))
                action = _sanitize_headline(str(e.get("EventCode", "")))
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

