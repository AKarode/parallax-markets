# Parallax

Prediction market edge detection for geopolitical events.

Finds mispriced contracts on [Kalshi](https://kalshi.com) and [Polymarket](https://polymarket.com) by modeling second-order effects that headline-scraping bots miss. Ingests real-time news and economic data, runs ensemble AI predictions, compares model probabilities against live market prices, and surfaces divergences as trade signals. Currently targeting geopolitical energy markets, paper-trading to validate edge before putting real money on it.

Instead of just reading headlines, the system simulates physical supply chain effects (blockade disrupts flow, flow reroutes through bypass, price shocks hit downstream, insurance costs spiral) and uses that to inform predictions.

## How It Works

```
       DATA SOURCES                      MODELS                         SIGNALS
 ┌──────────────────┐          ┌───────────────────────┐         ┌──────────────────┐
 │ Google News RSS  │          │ 3 Prediction Models   │         │ Divergence       │
 │ GDELT DOC API    │────────▶ │ (Claude Opus x3 each) │────────▶│ Detector         │
 │ EIA Oil Prices   │          │                       │         │                  │
 │ Truth Social     │          │ + Cascade Engine      │         │ BUY / SELL /     │
 └──────────────────┘          │   (6-rule physical    │         │ HOLD signals     │
                               │    supply chain sim)  │         │                  │
 ┌──────────────────┐          └───────────────────────┘         └────────┬─────────┘
 │ Kalshi API       │                                                     │
 │ Polymarket API   │──── live market prices ────────────────────────────▶│
 └──────────────────┘                                            ┌────────▼─────────┐
                                                                 │ Paper Trading    │
                                                                 │ (Kalshi sandbox) │
                                                                 └──────────────────┘
```

## What Makes It Interesting

**Ensemble predictions** - Each model makes 3 independent API calls at different temperatures and aggregates with trimmed mean. If the calls disagree too much (>10pp std dev), the prediction gets flagged as low-confidence and edge is downgraded. Reduces single-call noise without just averaging away signal.

**Cascade reasoning** - Predictions aren't just LLM vibes on headlines. A 6-rule engine simulates physical supply chain effects (blockade, flow disruption, bypass rerouting, price shock, downstream impact, insurance spiral) and feeds that into the oil price model.

**Proxy-aware contract mapping** - Not every prediction maps cleanly to a tradeable contract. Each contract gets an explicit proxy classification (direct, near-proxy, loose-proxy) with edge discounting so the system doesn't treat a loose thematic connection the same as a direct match.

**Crisis context injection** - Claude's training data cuts off before the crisis started. A manually maintained timeline gets injected into every prompt so the models actually know what's happened.

**Paper trading with real execution semantics** - Signals use actual bid/ask quotes, not mid-prices. Slippage and fees are modeled before any trade decision. The system tracks the full lifecycle: signal, order attempt, fill, position, settlement.

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
    allocator.py              Position sizing
  ingestion/
    google_news.py            Google News RSS poller
    gdelt_doc.py              GDELT DOC 2.0 API
    oil_prices.py             EIA API v2 (Brent/WTI)
  budget/
    tracker.py                LLM budget enforcement
  dashboard/
    data.py                   Query layer for React dashboard
  db/
    schema.py                 DuckDB schema (20+ tables)

frontend/                     React + Vite + TypeScript dashboard
```

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Backend | Python 3.12, FastAPI, DuckDB |
| AI | Claude Opus 4 (3x ensemble calls per prediction) |
| Frontend | React 18, TypeScript, Vite, deck.gl, MapLibre GL |
| Data | Google News RSS, GDELT, EIA API v2, Kalshi API, Polymarket API |
| Geo | H3 hexagonal indexing, Shapely, Searoute |
| Testing | pytest (265+ tests), pytest-asyncio, pytest-httpx |

## Roadmap

### In Progress

> Fix structural flaws in how models reason, expand contract coverage, validate the hold-to-settlement thesis against actual outcomes.

- [x] Prompt fixes (remove market price anchoring, fix cascade data bugs, sample size guards)
- [x] Ensemble predictions (3 calls per model, trimmed mean, instability detection)
- [ ] Risk gate filter (5-gate sequential: Kelly, liquidity, correlation, concentration, drawdown)
- [ ] Context foundation (file-based crisis context, model registry)
- [ ] Contract discovery (enumerate full contract landscape, classify into families)
- [ ] New capabilities (political transition model, rolling context, news diversification)
- [ ] Resolution validation (settlement-scored backtest, before/after comparison)

### Planned

> Transform from "LLM with scaffolding" into a principled hybrid pricing engine.

- [ ] Bayesian evidence aggregation (log-likelihood ratios, source grading, correlation-adjusted clustering)
- [ ] Multi-provider ensemble (Claude + GPT + Gemini with consensus threshold)
- [ ] Cascade engine upgrade (OPEC spare capacity, SPR levels, seasonal demand, insurance feedback loops)

### Future

- Live trading (pending proven edge on paper)
- Additional domains beyond current thesis
- Real-time dashboard with WebSocket updates

## Quick Start

```bash
cd backend
pip install -e ".[dev]"

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

## Testing

```bash
cd backend && python -m pytest tests/ -x -v
```

265+ tests covering ensemble aggregation, cascade modeling, contract mapping, signal evaluation, resolution backfill, and paper trade lifecycle.
