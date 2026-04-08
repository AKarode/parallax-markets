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
import uuid
from datetime import datetime, timezone
from pathlib import Path

import duckdb

from parallax.budget.tracker import BudgetTracker
from parallax.contracts.mapping_policy import MappingPolicy
from parallax.contracts.registry import ContractRegistry
from parallax.contracts.schemas import MappingResult
from parallax.db.schema import create_tables
from parallax.divergence.detector import Divergence, DivergenceDetector
from parallax.markets.kalshi import KalshiClient
from parallax.markets.polymarket import PolymarketClient
from parallax.markets.schemas import MarketPrice
from parallax.prediction.ceasefire import CeasefirePredictor
from parallax.prediction.hormuz import HormuzReopeningPredictor
from parallax.prediction.oil_price import OilPricePredictor
from parallax.prediction.schemas import PredictionOutput
from parallax.scoring.ledger import SignalLedger
from parallax.scoring.prediction_log import PredictionLogger
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
        ),
    ]


def _make_dry_run_markets() -> list[MarketPrice]:
    """Generate mock market prices for --dry-run mode using registry tickers."""
    now = datetime.now(timezone.utc)
    return [
        MarketPrice(ticker="KXWTIMAX-26DEC31", source="kalshi", yes_price=0.55, no_price=0.45, volume=12000, fetched_at=now),
        MarketPrice(ticker="KXUSAIRANAGREEMENT-27", source="kalshi", yes_price=0.48, no_price=0.52, volume=8500, fetched_at=now),
        MarketPrice(ticker="KXCLOSEHORMUZ-27JAN", source="kalshi", yes_price=0.60, no_price=0.40, volume=15000, fetched_at=now),
        MarketPrice(ticker="KXWTIMIN-26DEC31", source="kalshi", yes_price=0.30, no_price=0.70, volume=5000, fetched_at=now),
    ]


def _format_brief(
    predictions: list[PredictionOutput],
    market_prices: list[MarketPrice],
    divergences: list,
    budget: BudgetTracker,
    trade_table: str = "",
    signals: list | None = None,
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

    lines.append("--- SIGNAL AUDIT ---")
    lines.append("")
    if signals:
        for sig in signals:
            status = sig.signal
            proxy = sig.proxy_class
            lines.append(f"  {sig.contract_ticker:<30} {sig.model_id:<18} {proxy:<12} {sig.effective_edge:>+6.1%}  {status}")
        lines.append("")
    else:
        lines.append("  No signals evaluated.")
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
    run_id = str(uuid.uuid4())

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

    # Initialize contract registry, prediction logger, and signal ledger
    db_path = os.environ.get("DUCKDB_PATH", ":memory:")
    conn = duckdb.connect(db_path)
    create_tables(conn)
    registry = ContractRegistry(conn)
    registry.seed_initial_contracts()
    policy = MappingPolicy(registry=registry, min_effective_edge_pct=5.0)
    pred_logger = PredictionLogger(conn)
    ledger = SignalLedger(conn)

    # Persist all predictions
    for pred in predictions:
        if dry_run:
            news_ctx: list[dict] = []
        else:
            news_ctx = [
                {"title": e["title"], "url": e["url"], "source": e["source"],
                 "fetched_at": e.get("published_at", "")}
                for e in events[:20]
            ]
        # cascade_inputs nullable -- ceasefire model has no cascade
        cascade_ctx = None
        pred_logger.log_prediction(run_id, pred, news_ctx, cascade_ctx)

    # Contract-aware mapping with signal ledger
    all_signals = []
    for pred in predictions:
        mappings = policy.evaluate(pred, market_prices)
        for mapping in mappings:
            # Find matching market price for this contract
            mp = next((m for m in market_prices if m.ticker == mapping.contract_ticker), None)
            if mp is None:
                continue
            # Find contract title from registry
            contract_title = None
            active = registry.get_active_contracts()
            for c in active:
                if c.ticker == mapping.contract_ticker:
                    contract_title = c.title
                    break
            signal = ledger.record_signal(pred, mapping, mp, contract_title=contract_title, run_id=run_id)
            all_signals.append(signal)

    # Convert actionable signals to Divergence objects for existing paper trade + display code
    divergences = []
    for sig in all_signals:
        if sig.signal in ("BUY_YES", "BUY_NO"):
            pred_match = next((p for p in predictions if p.model_id == sig.model_id), None)
            mp_match = next((m for m in market_prices if m.ticker == sig.contract_ticker), None)
            if pred_match and mp_match:
                pred_match.kalshi_ticker = sig.contract_ticker
                div = Divergence(
                    model_id=sig.model_id,
                    prediction=pred_match,
                    market_price=mp_match,
                    model_probability=sig.model_probability,
                    market_probability=sig.market_yes_price,
                    edge=sig.effective_edge,
                    edge_pct=sig.effective_edge * 100,
                    signal=sig.signal,
                    strength="strong" if abs(sig.effective_edge) > 0.15 else "moderate" if abs(sig.effective_edge) > 0.10 else "weak",
                    created_at=sig.created_at,
                )
                divergences.append(div)

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
    brief = _format_brief(predictions, market_prices, divergences, budget, trade_table, signals=all_signals)
    print(brief)
    return brief


async def _run_check_resolutions() -> None:
    """Poll Kalshi production API for settled contracts and backfill signal_ledger."""
    from parallax.scoring.resolution import check_resolutions

    db_path = os.environ.get("DUCKDB_PATH", ":memory:")
    conn = duckdb.connect(db_path)
    create_tables(conn)

    api_key = os.environ.get("KALSHI_API_KEY", "")
    pk_path = os.environ.get("KALSHI_PRIVATE_KEY_PATH", "")
    if not api_key or not pk_path:
        print("ERROR: KALSHI_API_KEY and KALSHI_PRIVATE_KEY_PATH required for resolution checking")
        conn.close()
        return

    PROD_URL = "https://api.elections.kalshi.com/trade-api/v2"
    client = KalshiClient(api_key=api_key, private_key_path=pk_path, base_url=PROD_URL)
    results = await check_resolutions(conn, client)

    if results:
        print(f"Resolved {len(results)} contract(s):")
        for r in results:
            print(f"  {r.get('ticker', '?')}: {r.get('result', '?')} (settlement: {r.get('resolution_price', '?')})")
    else:
        print("No contracts have settled since last check.")

    conn.close()


def _map_predictions_to_markets_legacy(
    predictions: list[PredictionOutput],
    market_prices: list[MarketPrice],
) -> list[PredictionOutput]:
    """DEPRECATED: Legacy heuristic mapping. Replaced by MappingPolicy in Phase 1. Kept for reference."""
    # Index markets by ticker prefix for fast lookup
    markets_by_prefix: dict[str, list[MarketPrice]] = {}
    for mp in market_prices:
        # Extract prefix: "KXUSAIRANAGREEMENT-27-26MAY" → "KXUSAIRANAGREEMENT"
        parts = mp.ticker.split("-")
        prefix = parts[0]
        markets_by_prefix.setdefault(prefix, []).append(mp)

    for pred in predictions:
        if pred.kalshi_ticker:
            continue  # Already mapped

        if pred.model_id == "ceasefire":
            # Map to US-Iran agreement — closest proxy for ceasefire holding
            # Prefer the nearest-term open market (highest urgency)
            candidates = markets_by_prefix.get("KXUSAIRANAGREEMENT", [])
            if candidates:
                # Pick the one with most volume (most liquid = best price)
                best = max(candidates, key=lambda m: m.volume)
                pred.kalshi_ticker = best.ticker

        elif pred.model_id == "hormuz_reopening":
            # Map to Hormuz series or fall back to Iran agreement
            candidates = markets_by_prefix.get("KXCLOSEHORMUZ", [])
            if candidates:
                best = max(candidates, key=lambda m: m.volume)
                pred.kalshi_ticker = best.ticker
            else:
                # Fallback: Iran agreement is correlated with Hormuz reopening
                candidates = markets_by_prefix.get("KXUSAIRANAGREEMENT", [])
                if candidates:
                    best = max(candidates, key=lambda m: m.volume)
                    pred.kalshi_ticker = best.ticker

        elif pred.model_id == "oil_price":
            # Map to WTI max price targets
            # KXWTIMAX-26DEC31-T125 = "Will WTI hit $125 by year end?"
            # If model predicts decrease → low prob of hitting high targets
            # If model predicts increase → high prob of hitting targets
            candidates = markets_by_prefix.get("KXWTIMAX", [])
            if candidates:
                # Extract price target from ticker: "KXWTIMAX-26DEC31-T125" → 125
                def _target(mp: MarketPrice) -> float:
                    for part in mp.ticker.split("-"):
                        if part.startswith("T"):
                            try:
                                return float(part[1:])
                            except ValueError:
                                pass
                    return 0.0

                # Pick the $120 target as baseline (closest to current ~$92-113 range)
                # Model predicting decrease → prob of hitting $120 is LOW
                # Model predicting increase → prob of hitting $120 is HIGH
                target_120 = [m for m in candidates if _target(m) == 120]
                target_125 = [m for m in candidates if _target(m) == 125]
                best_candidates = target_120 or target_125 or candidates
                best = max(best_candidates, key=lambda m: m.volume)
                pred.kalshi_ticker = best.ticker

                # Translate oil direction prediction into market probability
                # Model says P(decrease) = 0.75 → P(WTI hits $120) ≈ 1 - 0.75 = 0.25
                # Model says P(increase) = 0.80 → P(WTI hits $120) ≈ 0.80
                if pred.direction == "decrease":
                    pred.probability = 1.0 - pred.confidence
                elif pred.direction == "increase":
                    pred.probability = pred.confidence
                # "stable" keeps probability as-is (around 0.5)

    return predictions


def _init_anthropic():
    """Initialize Anthropic client from env."""
    import anthropic
    return anthropic.AsyncAnthropic()


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
    """Fetch recent news events from Google News RSS + GDELT DOC API."""
    from parallax.ingestion.google_news import fetch_google_news
    from parallax.ingestion.gdelt_doc import fetch_gdelt_docs

    events = []
    seen: set[str] = set()

    # Fetch from both sources in parallel
    try:
        gn_events, gdelt_events = await asyncio.gather(
            fetch_google_news(seen_hashes=seen),
            fetch_gdelt_docs(timespan="24h", seen_hashes=seen),
            return_exceptions=True,
        )
        if isinstance(gn_events, list):
            events.extend(gn_events)
            seen.update(e.event_hash for e in gn_events)
        else:
            logger.warning("Google News fetch failed: %s", gn_events)
        if isinstance(gdelt_events, list):
            # Dedup against Google News results
            for e in gdelt_events:
                if e.event_hash not in seen:
                    events.append(e)
                    seen.add(e.event_hash)
        else:
            logger.warning("GDELT DOC fetch failed: %s", gdelt_events)
    except Exception:
        logger.exception("Failed to fetch news events")

    logger.info(
        "Fetched %d news events (%d Google News, %d GDELT DOC)",
        len(events),
        sum(1 for e in events if e.source == "google_news"),
        sum(1 for e in events if e.source == "gdelt_doc"),
    )

    # Convert NewsEvent to dict format expected by prediction models
    return [
        {
            "title": e.title,
            "url": e.url,
            "source": e.source,
            "published_at": e.published_at.isoformat(),
            "snippet": e.snippet,
            "query": e.query,
        }
        for e in events
    ]


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
    # Use production API for market data (demo only has sports/crypto)
    PROD_URL = "https://api.elections.kalshi.com/trade-api/v2"
    try:
        client = KalshiClient(
            api_key=api_key, private_key_path=pk_path, base_url=PROD_URL,
        )
        from parallax.markets.kalshi import IRAN_EVENT_TICKERS
        prices = []
        # Fetch markets for each known event ticker
        for event_ticker in IRAN_EVENT_TICKERS:
            try:
                data = await client._request(
                    "GET", "/markets",
                    params={"event_ticker": event_ticker, "limit": 10},
                )
                markets = data.get("markets", [])
                for m in markets:
                    if m.get("status") not in ("open", "active"):
                        continue
                    ticker = m.get("ticker", "")
                    if ticker and not any(p.ticker == ticker for p in prices):
                        price = await client.get_market_price(ticker)
                        if price.yes_price > 0 or price.no_price > 0:
                            prices.append(price)
            except Exception:
                logger.debug("Failed to fetch event %s", event_ticker)
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
    parser.add_argument(
        "--check-resolutions",
        action="store_true",
        help="Poll Kalshi for settled contracts and backfill outcomes",
    )
    parser.add_argument(
        "--calibration",
        action="store_true",
        help="Print calibration report (requires 7+ days of data)",
    )
    args = parser.parse_args()

    if args.verbose:
        logging.basicConfig(level=logging.DEBUG)
    else:
        logging.basicConfig(level=logging.WARNING)

    if args.check_resolutions:
        asyncio.run(_run_check_resolutions())
        return

    asyncio.run(run_brief(dry_run=args.dry_run, no_trade=args.no_trade))


if __name__ == "__main__":
    main()
