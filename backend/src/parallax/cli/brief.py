"""Daily intelligence brief -- prediction market edge finder.

Usage: python -m parallax.cli.brief [--dry-run] [--no-trade]

Runs the full pipeline:
1. Fetch latest GDELT events (last 24h)
2. Fetch latest EIA oil prices
3. Fetch Kalshi + Polymarket market prices
4. Run 3 prediction models
5. Detect divergences
6. Output intelligence brief with trade signals
7. (Optional) Execute paper trades on Kalshi sandbox
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import os
from datetime import datetime, timezone
from pathlib import Path

from parallax.budget.tracker import BudgetTracker
from parallax.divergence.detector import DivergenceDetector
from parallax.markets.kalshi import KalshiClient
from parallax.markets.polymarket import PolymarketClient
from parallax.markets.schemas import MarketPrice
from parallax.prediction.ceasefire import CeasefirePredictor
from parallax.prediction.hormuz import HormuzReopeningPredictor
from parallax.prediction.oil_price import OilPricePredictor
from parallax.prediction.schemas import PredictionOutput
from parallax.scoring.tracker import PaperTradeTracker
from parallax.simulation.cascade import CascadeEngine
from parallax.simulation.config import ScenarioConfig, load_scenario_config
from parallax.simulation.world_state import WorldState

logger = logging.getLogger(__name__)

SCENARIO_CONFIG_PATH = Path(__file__).resolve().parent.parent.parent.parent / "config" / "scenario_hormuz.yaml"


def _make_dry_run_predictions() -> list[PredictionOutput]:
    """Generate mock predictions for --dry-run mode."""
    now = datetime.now(timezone.utc)
    return [
        PredictionOutput(
            model_id="oil_price",
            prediction_type="oil_price_direction",
            probability=0.72,
            direction="increase",
            magnitude_range=[3.0, 8.0],
            unit="USD/bbl",
            timeframe="7d",
            confidence=0.72,
            reasoning="Cascade analysis shows 2.5M bbl/day supply loss. Bypass capacity partially offsets but net loss drives Brent up $3-8.",
            evidence=["Hormuz flow restricted to 60%", "IRGC naval exercises ongoing"],
            created_at=now,
            kalshi_ticker="KXOIL",
        ),
        PredictionOutput(
            model_id="ceasefire",
            prediction_type="ceasefire_probability",
            probability=0.62,
            direction="stable",
            magnitude_range=[0.0, 1.0],
            unit="probability",
            timeframe="14d",
            confidence=0.62,
            reasoning="Oman-mediated talks showing progress. Both sides signaling willingness but military posture unchanged.",
            evidence=["Oman mediation active", "US-Iran indirect talks confirmed"],
            created_at=now,
            kalshi_ticker="KXIRANCEASEFIRE",
        ),
        PredictionOutput(
            model_id="hormuz_reopening",
            prediction_type="hormuz_reopening",
            probability=0.35,
            direction="increase",
            magnitude_range=[10.0, 40.0],
            unit="pct_reopening",
            timeframe="14d",
            confidence=0.35,
            reasoning="Partial reopening possible if ceasefire holds. Insurance rates still elevated, suggesting market skepticism.",
            evidence=["Naval de-escalation signals", "Insurance premiums stabilizing"],
            created_at=now,
            kalshi_ticker="KXCLOSEHORMUZ",
        ),
    ]


def _make_dry_run_markets() -> list[MarketPrice]:
    """Generate mock market prices for --dry-run mode."""
    now = datetime.now(timezone.utc)
    return [
        MarketPrice(ticker="KXOIL", source="kalshi", yes_price=0.55, no_price=0.45, volume=12000, fetched_at=now),
        MarketPrice(ticker="KXIRANCEASEFIRE", source="kalshi", yes_price=0.48, no_price=0.52, volume=8500, fetched_at=now),
        MarketPrice(ticker="KXCLOSEHORMUZ", source="kalshi", yes_price=0.60, no_price=0.40, volume=15000, fetched_at=now),
        MarketPrice(ticker="iran-ceasefire-2026", source="polymarket", yes_price=0.51, no_price=0.49, volume=250000, fetched_at=now),
    ]


def _format_brief(
    predictions: list[PredictionOutput],
    market_prices: list[MarketPrice],
    divergences: list,
    budget: BudgetTracker,
    trade_table: str = "",
) -> str:
    """Format the intelligence brief as structured text."""
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    stats = budget.stats()

    lines = [
        "=" * 52,
        "PARALLAX DAILY INTELLIGENCE BRIEF",
        f"{now} | Budget: ${stats['spend_today_usd']:.2f}/${stats['daily_cap_usd']:.2f}",
        "=" * 52,
        "",
        "--- PREDICTIONS ---",
        "",
    ]

    for pred in predictions:
        title = pred.model_id.upper().replace("_", " ")
        lines.append(title)
        if pred.model_id == "oil_price":
            low, high = pred.magnitude_range
            lines.append(f"  Direction: {pred.direction} | Magnitude: ${low:.0f}-${high:.0f}")
        else:
            lines.append(f"  Probability: {pred.probability:.0%}")
        lines.append(f"  Confidence: {pred.confidence:.0%} | Timeframe: {pred.timeframe}")
        lines.append(f"  Reasoning: {pred.reasoning}")
        lines.append("")

    lines.append("--- MARKET PRICES ---")
    lines.append("")
    lines.append(f"  {'Ticker':<30} {'Source':<12} {'Yes':>6} {'No':>6} {'Volume':>10}")
    lines.append(f"  {'-'*30} {'-'*12} {'-'*6} {'-'*6} {'-'*10}")
    for mp in market_prices:
        lines.append(
            f"  {mp.ticker:<30} {mp.source:<12} {mp.yes_price:>5.0%} {mp.no_price:>5.0%} {mp.volume:>10,.0f}"
        )
    lines.append("")

    lines.append("--- DIVERGENCES ---")
    lines.append("")
    if not divergences:
        lines.append("  No significant divergences detected.")
    else:
        for div in divergences:
            if div.signal != "HOLD":
                lines.append(f"  SIGNAL: {div.signal} {div.market_price.ticker}")
                lines.append(
                    f"  Model: {div.model_probability:.0%} vs Market: {div.market_probability:.0%} "
                    f"| Edge: {div.edge_pct:+.1f}% ({div.strength})"
                )
                lines.append("")

    if trade_table:
        lines.append("--- PAPER TRADES ---")
        lines.append("")
        lines.append(trade_table)
        lines.append("")

    lines.append("=" * 52)
    return "\n".join(lines)


async def run_brief(dry_run: bool = False, no_trade: bool = False) -> str:
    """Run the full intelligence brief pipeline.

    Args:
        dry_run: Skip LLM calls, use mock predictions.
        no_trade: Show signals but do not execute paper trades.

    Returns:
        Formatted brief as string.
    """
    budget = BudgetTracker(daily_cap_usd=20.0)

    if dry_run:
        predictions = _make_dry_run_predictions()
        market_prices = _make_dry_run_markets()
    else:
        # Initialize clients
        anthropic_client = _init_anthropic()
        config = _load_config()
        cascade = CascadeEngine(config=config)
        world_state = WorldState()

        # Fetch data (parallel)
        events, prices, kalshi_markets, poly_markets = await asyncio.gather(
            _fetch_gdelt_events(),
            _fetch_oil_prices(),
            _fetch_kalshi_markets(),
            _fetch_polymarket_markets(),
        )

        market_prices = kalshi_markets + poly_markets

        # Run predictions (parallel)
        oil_pred = OilPricePredictor(cascade, budget, anthropic_client)
        ceasefire_pred = CeasefirePredictor(budget, anthropic_client)
        hormuz_pred = HormuzReopeningPredictor(cascade, budget, anthropic_client)

        predictions = list(await asyncio.gather(
            oil_pred.predict(events, prices, world_state),
            ceasefire_pred.predict(events),
            hormuz_pred.predict(events, world_state),
        ))

    # Detect divergences
    detector = DivergenceDetector(min_edge_pct=5.0)
    divergences = detector.detect(predictions, market_prices)

    # Paper trades
    trade_table = ""
    if not dry_run and not no_trade:
        kalshi_key = os.environ.get("KALSHI_API_KEY", "")
        kalshi_pk = os.environ.get("KALSHI_PRIVATE_KEY_PATH", "")
        if kalshi_key and kalshi_pk:
            kalshi = KalshiClient(api_key=kalshi_key, private_key_path=kalshi_pk)
            tracker = PaperTradeTracker(kalshi_client=kalshi)
            for div in divergences:
                if div.strength == "strong" and div.signal != "HOLD":
                    await tracker.open_trade(div)
            trade_table = tracker.to_table()

    # Format and output
    brief = _format_brief(predictions, market_prices, divergences, budget, trade_table)
    print(brief)
    return brief


def _init_anthropic():
    """Initialize Anthropic client from env."""
    import anthropic
    return anthropic.Anthropic()


def _load_config() -> ScenarioConfig:
    """Load scenario config from YAML."""
    if SCENARIO_CONFIG_PATH.exists():
        return load_scenario_config(SCENARIO_CONFIG_PATH)
    # Fallback: find config relative to working directory
    alt = Path("backend/config/scenario_hormuz.yaml")
    if alt.exists():
        return load_scenario_config(alt)
    raise FileNotFoundError(f"Scenario config not found at {SCENARIO_CONFIG_PATH} or {alt}")


async def _fetch_gdelt_events() -> list[dict]:
    """Fetch recent GDELT events. Gracefully degrades if no BigQuery credentials."""
    try:
        from google.cloud import bigquery
        # Would fetch from BigQuery here
        logger.info("BigQuery GDELT fetch not yet wired — returning empty events")
    except ImportError:
        logger.info("google-cloud-bigquery not available, skipping GDELT fetch")
    return []


async def _fetch_oil_prices() -> list[dict]:
    """Fetch latest EIA oil prices."""
    api_key = os.environ.get("EIA_API_KEY", "")
    if not api_key:
        logger.warning("EIA_API_KEY not set, skipping oil price fetch")
        return []
    try:
        from parallax.ingestion.oil_prices import fetch_brent
        return await fetch_brent(api_key)
    except Exception:
        logger.exception("Failed to fetch oil prices")
        return []


async def _fetch_kalshi_markets() -> list[MarketPrice]:
    """Fetch Kalshi market prices for tracked tickers."""
    api_key = os.environ.get("KALSHI_API_KEY", "")
    pk_path = os.environ.get("KALSHI_PRIVATE_KEY_PATH", "")
    if not api_key or not pk_path:
        logger.warning("Kalshi credentials not set, skipping market fetch")
        return []
    try:
        client = KalshiClient(api_key=api_key, private_key_path=pk_path)
        from parallax.markets.kalshi import HORMUZ_SERIES, OIL_PRICE_SERIES
        markets = await client.get_markets()
        prices = []
        for m in markets[:20]:
            ticker = m.get("ticker", "")
            try:
                price = await client.get_market_price(ticker)
                prices.append(price)
            except Exception:
                continue
        return prices
    except Exception:
        logger.exception("Failed to fetch Kalshi markets")
        return []


async def _fetch_polymarket_markets() -> list[MarketPrice]:
    """Fetch Polymarket Iran-related market prices."""
    try:
        client = PolymarketClient()
        return await client.get_iran_markets()
    except Exception:
        logger.exception("Failed to fetch Polymarket markets")
        return []


def main():
    """CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Parallax Daily Intelligence Brief",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Skip LLM calls, use mock predictions",
    )
    parser.add_argument(
        "--no-trade",
        action="store_true",
        help="Show signals but do not execute paper trades",
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Enable debug logging",
    )
    args = parser.parse_args()

    if args.verbose:
        logging.basicConfig(level=logging.DEBUG)
    else:
        logging.basicConfig(level=logging.WARNING)

    asyncio.run(run_brief(dry_run=args.dry_run, no_trade=args.no_trade))


if __name__ == "__main__":
    main()
