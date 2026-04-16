"""Synthetic backtest engine — replays historical days through prediction models.

For each day in the backtest window:
1. Build a date-limited crisis context (only events up to that day)
2. Load that day's market prices from backtest_prices.json
3. Run all 3 prediction models
4. Record predictions
5. Compare to next-day market movement and eventual settlement

This is valid because Claude's training cutoff is ~Aug 2025 and the entire
Iran-Hormuz crisis started Feb 2026 — no data leakage possible.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import anthropic

from parallax.budget.tracker import BudgetTracker
from parallax.prediction.ceasefire import CeasefirePredictor
from parallax.prediction.hormuz import HormuzReopeningPredictor
from parallax.prediction.oil_price import OilPricePredictor
from parallax.prediction.schemas import PredictionOutput
from parallax.simulation.cascade import CascadeEngine
from parallax.simulation.config import load_scenario_config
from parallax.simulation.world_state import WorldState

logger = logging.getLogger(__name__)

DATA_DIR = Path(__file__).resolve().parent.parent.parent.parent / "data"
BACKTEST_PRICES_PATH = DATA_DIR / "backtest_prices.json"
BACKTEST_TIMELINE_PATH = Path(__file__).resolve().parent / "timeline.json"
RESULTS_PATH = DATA_DIR / "backtest_results.json"

# Contracts we care about for P&L
SETTLEMENT_DATA = {
    "KXWTIMAX-26DEC31-T135": {"settled": None},
    "KXWTIMAX-26DEC31-T140": {"settled": None},
    "KXWTIMAX-26DEC31-T150": {"settled": None},
    "KXWTIMIN-26DEC31-T75": {"settled": None},
    "KXWTIMIN-26DEC31-T80": {"settled": None},
    "KXWTIMIN-26DEC31-T85": {"settled": None},
    "KXUSAIRANAGREEMENT-27-26AUG": {"settled": None},
    "KXUSAIRANAGREEMENT-27-26JUN": {"settled": None},
    "KXUSAIRANAGREEMENT-27-26MAY": {"settled": None},
}


def _load_backtest_prices() -> dict[str, list[dict]]:
    """Load daily OHLC from backtest_prices.json."""
    with open(BACKTEST_PRICES_PATH) as f:
        return json.load(f)


def _load_timeline() -> list[dict]:
    """Load day-by-day timeline events."""
    with open(BACKTEST_TIMELINE_PATH) as f:
        return json.load(f)


def _build_context_as_of(timeline: list[dict], as_of_date: str) -> str:
    """Build crisis context including only events up to as_of_date."""
    context_lines = [
        "## CRITICAL CONTEXT — You must read this carefully before making predictions.",
        "",
        "Your training data ends around August 2025. The following events have occurred",
        "AFTER your knowledge cutoff. This is not hypothetical — these are real events.",
        "",
        "### Background",
        "- Mid-2025: Failed US-Iran nuclear negotiations in Geneva.",
        "- June 2025: Brief 12-day US air conflict with Iran. Oil stayed below $70.",
        "- Feb 6, 2026: Indirect US-Iran nuclear talks in Oman.",
        "- Feb 15-20: Iran tripled oil exports anticipating disruption.",
        "- Feb 27: Oman announced breakthrough — Iran agreed to halt enrichment stockpiling.",
        "- **Feb 28: US and Israel launched coordinated air strikes on Iran. Supreme Leader",
        "  Khamenei killed.** Iran retaliated with missiles on Israel, US bases, Gulf allies.",
        "- **Feb 28: Iran closed Strait of Hormuz.** IRGC attacking ships, laying mines.",
        "- Mar 2: IRGC confirmed closure. Brent surged from $72 to $82.",
        "- Mar 4: Strait fully blocked. Brent broke $120.",
        "- Mar 9: Brent hit $119.50. WTI biggest weekly gain in history (+35.6%).",
        "- Mar 19: US began aerial campaign to forcibly reopen Hormuz.",
        "- Mar 21: Trump 48-hour ultimatum to Iran. Iran doubled down.",
        "- Mar 25: Pakistan delivered US 15-point proposal. Iran rejected it.",
        "",
        f"### Events through {as_of_date}",
    ]

    for entry in timeline:
        if entry["date"] <= as_of_date:
            context_lines.append(f"- **{entry['date']}**: {entry['summary']}")

    context_lines.extend([
        "",
        "### Prediction Market Context",
        "- KXUSAIRANAGREEMENT: 'Will US and Iran reach formal agreement?' Requires SIGNED DEAL.",
        "  JCPOA took 2+ years of formal negotiations. This is a very high bar.",
        "- KXWTIMAX/KXWTIMIN: Oil price range contracts (WTI annual max/min).",
        "- Market volume: $200M+ wagered across Iran contracts on Kalshi/Polymarket.",
    ])

    return "\n".join(context_lines)


def _get_market_prices_for_day(
    prices: dict[str, list[dict]], target_date: str
) -> dict[str, dict]:
    """Get closing prices for each contract on a given day."""
    result = {}
    for ticker, daily in prices.items():
        for day_data in daily:
            if day_data["date"] == target_date:
                result[ticker] = day_data
                break
    return result


async def run_backtest(
    start_date: str = "2026-03-29",
    end_date: str = "2026-04-11",
) -> dict[str, Any]:
    """Run the full synthetic backtest."""

    prices = _load_backtest_prices()
    timeline = _load_timeline()

    # Determine which dates we have data for
    all_dates = set()
    for ticker, daily in prices.items():
        for day_data in daily:
            all_dates.add(day_data["date"])

    test_dates = sorted(d for d in all_dates if start_date <= d <= end_date)
    logger.info("Backtest dates: %s", test_dates)

    if not test_dates:
        return {"error": "No dates with market data in range", "dates_available": sorted(all_dates)}

    # Initialize models
    client = anthropic.AsyncAnthropic()
    budget = BudgetTracker(daily_cap_usd=50.0)  # Higher cap for backtest
    config = load_scenario_config(
        Path(__file__).resolve().parent.parent.parent.parent / "config" / "scenario_hormuz.yaml"
    )
    cascade = CascadeEngine(config=config)
    world_state = WorldState()

    oil_pred = OilPricePredictor(cascade, budget, client)
    ceasefire_pred = CeasefirePredictor(budget, client)
    hormuz_pred = HormuzReopeningPredictor(cascade, budget, client)

    results: list[dict] = []

    for i, test_date in enumerate(test_dates):
        logger.info("=== Backtest day %d/%d: %s ===", i + 1, len(test_dates), test_date)

        # Build date-limited context
        context_text = _build_context_as_of(timeline, test_date)

        # Get market prices for this day
        day_prices = _get_market_prices_for_day(prices, test_date)
        if not day_prices:
            logger.warning("No market data for %s, skipping", test_date)
            continue

        # Build minimal news events from timeline
        day_events = [
            {"title": e["summary"], "url": "", "source": "timeline", "published_at": e["date"]}
            for e in timeline
            if e["date"] == test_date
        ]
        if not day_events:
            # Use events from last 2 days as context
            day_events = [
                {"title": e["summary"], "url": "", "source": "timeline", "published_at": e["date"]}
                for e in timeline
                if e["date"] <= test_date and e["date"] >= str(date.fromisoformat(test_date) - timedelta(days=2))
            ]

        # Temporarily override crisis context
        import parallax.prediction.crisis_context as ctx
        original_fn = ctx.get_crisis_context
        ctx.get_crisis_context = lambda: context_text

        try:
            # Run all 3 models
            oil_prices_data = [{"series": "RBRTE", "value": 138.0, "period": test_date}]

            oil_result, ceasefire_result, hormuz_result = await asyncio.gather(
                oil_pred.predict(day_events, oil_prices_data, world_state),
                ceasefire_pred.predict(day_events),
                hormuz_pred.predict(day_events, world_state),
            )

            predictions = {
                "oil_price": {
                    "probability": oil_result.probability,
                    "direction": oil_result.direction,
                    "confidence": oil_result.confidence,
                    "reasoning": oil_result.reasoning[:500],
                },
                "ceasefire": {
                    "probability": ceasefire_result.probability,
                    "direction": ceasefire_result.direction,
                    "confidence": ceasefire_result.confidence,
                    "reasoning": ceasefire_result.reasoning[:500],
                },
                "hormuz_reopening": {
                    "probability": hormuz_result.probability,
                    "direction": hormuz_result.direction,
                    "confidence": hormuz_result.confidence,
                    "reasoning": hormuz_result.reasoning[:500],
                },
            }

        except Exception as e:
            logger.error("Model error on %s: %s", test_date, e)
            predictions = {"error": str(e)}
        finally:
            ctx.get_crisis_context = original_fn

        # Get next-day prices for comparison
        next_date_idx = test_dates.index(test_date)
        next_date = test_dates[next_date_idx + 1] if next_date_idx + 1 < len(test_dates) else None
        next_day_prices = _get_market_prices_for_day(prices, next_date) if next_date else {}

        results.append({
            "date": test_date,
            "predictions": predictions,
            "market_prices": {t: {"close": d.get("close")} for t, d in day_prices.items()},
            "next_day_prices": {t: {"close": d.get("close")} for t, d in next_day_prices.items()} if next_day_prices else None,
        })

        logger.info(
            "  Oil: %.0f%% %s | Ceasefire: %.0f%% | Hormuz: %.0f%%",
            predictions.get("oil_price", {}).get("probability", 0) * 100,
            predictions.get("oil_price", {}).get("direction", "?"),
            predictions.get("ceasefire", {}).get("probability", 0) * 100,
            predictions.get("hormuz_reopening", {}).get("probability", 0) * 100,
        )

    # Save results
    with open(RESULTS_PATH, "w") as f:
        json.dump(results, f, indent=2, default=str)
    logger.info("Backtest results saved to %s", RESULTS_PATH)

    # Score results
    summary = _score_results(results, prices)
    summary["total_days"] = len(results)
    summary["budget_used"] = f"${budget._spend_today:.2f}"

    return summary


def _score_results(
    results: list[dict],
    prices: dict[str, list[dict]],
) -> dict[str, Any]:
    """Score backtest results against actual market movements."""
    agreement_calls = []
    oil_direction_calls = []
    hormuz_calls = []

    for i, day in enumerate(results):
        preds = day.get("predictions", {})
        if "error" in preds:
            continue

        today_prices = day.get("market_prices", {})
        next_prices = day.get("next_day_prices")

        if not next_prices:
            continue

        # Score ceasefire/agreement model
        ceasefire_prob = preds.get("ceasefire", {}).get("probability")
        if ceasefire_prob is not None:
            for ticker in ["KXUSAIRANAGREEMENT-27-26AUG", "KXUSAIRANAGREEMENT-27-26JUN"]:
                today_close = today_prices.get(ticker, {}).get("close")
                next_close = next_prices.get(ticker, {}).get("close")
                if today_close and next_close:
                    model_says_buy_yes = ceasefire_prob > today_close
                    market_went_up = next_close > today_close
                    correct = model_says_buy_yes == market_went_up
                    agreement_calls.append({
                        "date": day["date"],
                        "ticker": ticker,
                        "model_prob": ceasefire_prob,
                        "market_price": today_close,
                        "next_price": next_close,
                        "signal": "BUY_YES" if model_says_buy_yes else "BUY_NO",
                        "correct": correct,
                        "pnl": next_close - today_close if model_says_buy_yes else today_close - next_close,
                    })

        # Score oil direction
        oil_prob = preds.get("oil_price", {}).get("probability")
        oil_dir = preds.get("oil_price", {}).get("direction")
        if oil_prob is not None and oil_dir:
            for ticker in ["KXWTIMAX-26DEC31-T140", "KXWTIMIN-26DEC31-T80"]:
                today_close = today_prices.get(ticker, {}).get("close")
                next_close = next_prices.get(ticker, {}).get("close")
                if today_close and next_close:
                    # For WTI max contracts, "increase" direction = bullish = BUY_YES
                    # For WTI min contracts, "decrease" direction = bearish = BUY_YES
                    if "MAX" in ticker:
                        model_says_buy_yes = oil_dir == "increase" and oil_prob > 0.5
                    else:
                        model_says_buy_yes = oil_dir == "decrease" and oil_prob > 0.5
                    market_went_up = next_close > today_close
                    correct = model_says_buy_yes == market_went_up
                    oil_direction_calls.append({
                        "date": day["date"],
                        "ticker": ticker,
                        "model_prob": oil_prob,
                        "direction": oil_dir,
                        "market_price": today_close,
                        "next_price": next_close,
                        "correct": correct,
                        "pnl": next_close - today_close if model_says_buy_yes else today_close - next_close,
                    })

        # Score Hormuz
        hormuz_prob = preds.get("hormuz_reopening", {}).get("probability")
        if hormuz_prob is not None:
            hormuz_calls.append({
                "date": day["date"],
                "model_prob": hormuz_prob,
            })

    # Compute aggregate stats
    def _compute_stats(calls: list[dict]) -> dict:
        if not calls:
            return {"count": 0, "win_rate": None, "total_pnl": 0}
        wins = sum(1 for c in calls if c.get("correct"))
        total_pnl = sum(c.get("pnl", 0) for c in calls)
        return {
            "count": len(calls),
            "wins": wins,
            "losses": len(calls) - wins,
            "win_rate": wins / len(calls),
            "total_pnl": total_pnl,
            "avg_pnl_per_call": total_pnl / len(calls),
            "calls": calls,
        }

    return {
        "agreement": _compute_stats(agreement_calls),
        "oil_direction": _compute_stats(oil_direction_calls),
        "hormuz": {
            "count": len(hormuz_calls),
            "avg_reopening_prob": sum(c["model_prob"] for c in hormuz_calls) / len(hormuz_calls) if hormuz_calls else None,
            "calls": hormuz_calls,
        },
    }


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    result = asyncio.run(run_backtest())
    print(json.dumps(result, indent=2, default=str))
