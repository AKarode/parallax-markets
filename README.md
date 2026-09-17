# Parallax

A prediction-market research platform for geopolitical events — built to answer one question rigorously: **can an LLM reasoning system find and profitably trade mispriced prediction-market contracts?**

> **Status: active — cross-venue arbitrage (September 2026). The original thesis is dead and stays dead.**
>
> Phase 1 (March–June 2026) asked whether an LLM reasoning system could find and profitably trade mispriced contracts. Four experiments said no, for about $40 of API calls and no real capital. That record is preserved in [docs/POSTMORTEM.md](docs/POSTMORTEM.md) — it is evidence, not discouragement.
>
> Phase 2 asks a different question, one that needs no forecasting edge: **do Kalshi and Polymarket ever price the same event inconsistently enough to clear both venues' fees?** The new `parallax.arb` package measures exactly that. Nothing there trades; it reports what was quotable.

Parallax ingested real-time news and economic data during the 2026 Iran–Hormuz crisis, ran ensemble LLM predictions informed by a physical supply-chain cascade simulation, compared model probabilities against live Kalshi/Polymarket prices, and paper-traded the divergences with full execution semantics.

## How It Worked

```
       DATA SOURCES                      MODELS                         SIGNALS
 ┌──────────────────┐          ┌───────────────────────┐         ┌──────────────────┐
 │ Google News RSS  │          │ 3 Prediction Models   │         │ Divergence       │
 │ GDELT DOC API    │────────▶ │ (3× ensemble calls    │────────▶│ Detector         │
 │ EIA Oil Prices   │          │  per model)           │         │                  │
 │ Truth Social     │          │                       │         │ BUY / SELL /     │
 └──────────────────┘          │ + Cascade Engine      │         │ HOLD signals     │
                               │   (6-rule physical    │         │                  │
 ┌──────────────────┐          │    supply chain sim)  │         └────────┬─────────┘
 │ Kalshi API       │          └───────────────────────┘                  │
 │ Polymarket API   │──── live market prices ─────────────────────────────▶
 └──────────────────┘                                            ┌────────▼─────────┐
                                                                 │ Paper Trading    │
                                                                 │ (real bid/ask,   │
                                                                 │  fees, slippage) │
                                                                 └──────────────────┘
```

## Findings — Phase 1

The later experiments ran with pre-registered kill criteria; every headline number below is traceable to a report in `docs/`.

1. **Execution, not prediction, was the binding constraint.** Over the live crisis window, 89% of generated signals (67 of 75) were refused for having no executable quote. Zero trades executed, and too few signals ever resolved for the recalibration feedback loop to fire. The forecast-first funnel was inverted — tradability must gate the pipeline before the LLM runs.
2. **No directional skill.** A 13-day backtest over the crisis window: 46% win rate, negative P&L — a coin flip minus fees.
3. **Recalibration measurably improves stated LLM confidence.** Since the live run produced too little resolved data, a standalone harness scored 3 Claude models on 1,531 resolved public Kalshi questions (grouped out-of-fold CV, cluster-bootstrap CIs): isotonic recalibration significantly beat raw model confidence on 3/3 models — and caught a structural non-monotonicity bug in the project's own recalibrator. See [docs/KALSHIBENCH-CALIBRATION.md](docs/KALSHIBENCH-CALIBRATION.md).
4. **The last defensible angle died too.** A same-venue coherence-arbitrage probe (Polymarket midterm joint vs. marginal markets) found the book coherent to sub-tick precision across 292 observations — nothing to act on, even for a patient maker. See [docs/COHERENCE-ARB-PROBE-RESULTS.md](docs/COHERENCE-ARB-PROBE-RESULTS.md).
5. **The external evidence agrees.** As of mid-2026 there is no documented profitable standalone LLM prediction-market trader; exchange fees make even makers negative-EV on average. See [docs/PROFITABILITY-STRATEGY-2026-06.md](docs/PROFITABILITY-STRATEGY-2026-06.md).

## What Makes It Interesting

**Evaluation rigor** — Out-of-fold cross-validation, cluster-bootstrap confidence intervals, pre-registered kill switches, adversarial review of every major claim, and leakage caveats stated before headline numbers. The null result is trustworthy because of this machinery.

**Ensemble predictions** — Each model makes 3 independent API calls at different temperatures and aggregates with trimmed mean. If the calls disagree too much (>10pp std dev), the prediction is flagged low-confidence and its edge downgraded.

**Cascade reasoning** — Predictions aren't LLM vibes on headlines. A 6-rule engine simulates physical supply-chain effects (blockade, flow disruption, bypass rerouting, price shock, downstream impact, insurance spiral) and feeds the oil price model.

**Proxy-aware contract mapping** — Each contract gets an explicit proxy classification (direct, near-proxy, loose-proxy) with edge discounting, so a loose thematic match is never treated like a direct one.

**Crisis context injection** — The crisis postdated the models' training cutoff. A manually maintained timeline is injected into every prompt so the models know what has actually happened.

**Real execution semantics** — Signals use actual bid/ask quotes, not mid-prices; fees and slippage are modeled before any trade decision; the ledger tracks the full signal → order → fill → settlement lifecycle.

## Architecture

```
backend/src/parallax/
  cli/brief.py                Pipeline orchestration and daily brief
  prediction/
    ensemble.py               Multi-call LLM aggregation (trimmed mean, instability detection)
    oil_price.py              Oil price direction model (cascade + LLM)
    ceasefire.py              Ceasefire probability model
    hormuz.py                 Strait reopening model
    crisis_context.py         Historical timeline injection
  bench/
    kalshibench.py            Calibration audit harness (reusable, standalone)
  simulation/
    cascade.py                6-rule physical cascade engine
    world_state.py            Geospatial state (H3 hexagonal grid)
  contracts/
    registry.py               Contract registry and proxy classification
    mapping_policy.py         Proxy-aware signal mapping with cost model
  scoring/
    ledger.py                 Append-only signal records with full provenance
    tracker.py                Paper trade execution and order lifecycle
    calibration.py            Hit rate, calibration curves, edge decay
    scorecard.py              Daily scorecard ETL (15+ metrics across 5 categories)
    resolution.py             Settlement polling and outcome backfill
  markets/
    kalshi.py                 Kalshi API client (RSA-PSS auth)
    polymarket.py             Polymarket read-only client
  portfolio/
    allocator.py              Quarter-Kelly position sizing
  ingestion/
    google_news.py            Google News RSS poller
    gdelt_doc.py              GDELT DOC 2.0 API
    oil_prices.py             EIA API v2 (Brent/WTI)
  budget/
    tracker.py                LLM budget enforcement ($20/day cap)
  dashboard/
    data.py                   Query layer for React dashboard
  db/
    schema.py                 DuckDB schema (20+ tables)
  arb/                        PHASE 2 — cross-venue arbitrage measurement
    venue.py                  Venue protocol (read-only, outcome-addressed)
    adapters.py               KalshiVenue / PolymarketVenue over the clients
    fees.py                   Exact per-venue fee models (Decimal)
    pairs.py                  Settlement-equivalence registry, review-gated
    scanner.py                Package accounting across both ask ladders
```

The React dashboard that served Phase 1 was removed in September 2026 — it was
68% of the repository and has no role in an arbitrage scanner. It remains in
git history.

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Backend | Python 3.11+, FastAPI, DuckDB |
| AI | Claude (3× ensemble calls per prediction, $20/day budget enforcement) |
| Data | Google News RSS, GDELT, EIA API v2, Kalshi API, Polymarket API |
| Geo | H3 hexagonal indexing, Shapely, Searoute |
| Testing | pytest, pytest-asyncio, pytest-httpx |
| Ops | Docker Compose, systemd timers (unattended twice-daily runs) |

## Quick Start

```bash
cd backend
uv sync --extra dev          # or: pip install -e ".[dev]"

# Set environment variables
export ANTHROPIC_API_KEY=your-key
export KALSHI_API_KEY=your-kalshi-key-id
export KALSHI_PRIVATE_KEY_PATH=~/.kalshi/private_key.pem

# Dry run (mock data, no API calls)
python -m parallax.cli.brief --dry-run

# Live predictions + real market prices, no trades
python -m parallax.cli.brief --no-trade

# Full pipeline with paper trade execution
python -m parallax.cli.brief
```

Run the calibration audit harness standalone (no market access needed):

```bash
pip install -e ".[bench]"
python -m parallax.cli.kalshibench --models haiku --limit 60   # cheap smoke test
```

## Testing

```bash
cd backend
uv run --extra dev --extra bench pytest -q
```

**Current state, measured 2026-09-17: 523 passed, 24 failed, 13 skipped.**

The 24 failures are pre-existing and confined to the Phase 1 research pipeline
— `test_scorecard.py` (10), `test_phase1_critical.py` (4),
`test_crisis_context_db.py` (4), `test_brief_resilience.py` (3), and one each
in `test_selective.py`, `test_ops_events.py`, `test_llm_usage.py`. They are
mostly DuckDB schema drift against tables the concluded experiment wrote.

Nothing under `markets/`, `contracts/`, `divergence/` or `arb/` is failing, so
the Phase 2 path is green. The failures are still real debt and are not being
described as anything else.

Note that the `bench` extra is required for collection — without numpy, four
test modules fail at import and pytest reports a collection error rather than
a test result.

## Project History

Built March–June 2026 (~16k LOC, 244 commits) against a live geopolitical crisis with a hard two-week validation deadline. Ran unattended on a VPS for the duration. See [docs/POSTMORTEM.md](docs/POSTMORTEM.md) for the full arc: what was hypothesized, what the four experiments showed, why the edge thesis failed, and which components are reusable.

Reopened September 2026 to ask the cross-venue question. See
[docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) for how the pieces fit together
and [docs/ONBOARDING.md](docs/ONBOARDING.md) to get running.
