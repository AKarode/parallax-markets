# Parallax

**Prediction market edge-finder for the Iran-Hormuz crisis.**

Parallax ingests real-world news, runs AI prediction models with causal reasoning, compares predictions against live Kalshi/Polymarket prices, and flags mispriced contracts. Built for a single analyst exploiting second-order effects that sentiment bots miss.

## How It Works

```
News Sources                    Market Data
  Google News RSS (5-15 min)      Kalshi API (production)
  GDELT DOC API (15-60 min)       Polymarket API
  EIA Oil Prices                          |
         |                                |
         v                                v
  3 Prediction Models              Market Prices
  (Claude Sonnet + Cascade)        (live probabilities)
         |                                |
         +---------> Divergence <---------+
                     Detector
                        |
                   Trade Signals
              BUY_YES / BUY_NO / HOLD
                        |
                   Paper Trading
                 (Kalshi sandbox)
```

## Prediction Models

| Model | What It Predicts | Method |
|-------|-----------------|--------|
| **Oil Price** | Brent/WTI direction + magnitude over 7 days | Cascade engine (blockade -> flow -> bypass -> price) + LLM reasoning |
| **Ceasefire** | Probability of ceasefire holding 14 days | Diplomatic event filtering + LLM analysis |
| **Hormuz Reopening** | Probability of strait reopening in 14 days | Cascade scenario modeling + LLM reasoning |

Each model makes a single Claude Sonnet call (~$0.007/call). Total cost: ~$0.02 per brief run, well under the $20/day budget.

## Quick Start

### Prerequisites

- Python 3.11+
- Anthropic API key
- Kalshi account with API access (free)

### Setup

```bash
# Clone and install
cd backend
pip install -e ".[dev]"

# Set environment variables
export ANTHROPIC_API_KEY="your-key"
export KALSHI_API_KEY="your-kalshi-key-id"
export KALSHI_PRIVATE_KEY_PATH="$HOME/.kalshi/private_key.pem"

# Optional
export EIA_API_KEY="your-eia-key"  # For oil price data
```

### Kalshi API Keys

1. Create account at [kalshi.com](https://kalshi.com)
2. Go to Settings -> API Keys
3. Generate an RSA key pair
4. Save the private key to `~/.kalshi/private_key.pem`
5. Copy the API Key ID

### Run

```bash
# Dry run (mock data, no API calls)
python -m parallax.cli.brief --dry-run

# Live predictions + real market prices (no trades)
python -m parallax.cli.brief --no-trade

# Full pipeline with paper trade execution
python -m parallax.cli.brief

# With debug logging
python -m parallax.cli.brief --no-trade -v
```

### Example Output

```
====================================================
PARALLAX DAILY INTELLIGENCE BRIEF
2026-04-08 06:53 UTC | Budget: $0.02/$20.00
====================================================

--- PREDICTIONS ---

OIL PRICE
  Direction: decrease | Magnitude: $-8-$-3
  Confidence: 85% | Timeframe: 7d
  Reasoning: US-Iran ceasefire reduces geopolitical risk premium...

CEASEFIRE
  Probability: 35%
  Confidence: 35% | Timeframe: 14d
  Reasoning: Ceasefire faces structural weaknesses despite initial optimism...

HORMUZ REOPENING
  Probability: 65%
  Confidence: 65% | Timeframe: 14d
  Reasoning: Ceasefire creates momentum but two-week timeframe is tight...

--- DIVERGENCES ---

  SIGNAL: BUY_NO KXWTIMAX-26DEC31-T120
  Model: 15% vs Market: 58% | Edge: -43.1% (strong)

  SIGNAL: BUY_YES KXUSAIRANAGREEMENT-27-26MAY
  Model: 35% vs Market: 9% | Edge: +26.0% (strong)
```

## API Server

```bash
uvicorn parallax.main:app --reload
```

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/health` | GET | Pipeline status, budget, last fetch times |
| `/api/predictions` | GET | Latest predictions from all 3 models |
| `/api/markets` | GET | Live Kalshi + Polymarket prices |
| `/api/divergences` | GET | Current divergence signals |
| `/api/trades` | GET | Open paper trades with P&L |
| `/api/brief/run` | POST | Trigger a full brief run |

## Architecture

```
backend/src/parallax/
  cli/brief.py              # Main entry point - daily intelligence brief
  main.py                   # FastAPI REST API
  ingestion/
    google_news.py           # Google News RSS poller (free, no auth)
    gdelt_doc.py             # GDELT DOC 2.0 API (free, no auth)
    gdelt.py                 # GDELT BigQuery pipeline (4-stage filter)
    oil_prices.py            # EIA API v2 (Brent/WTI)
    entities.py              # Critical entity list (IRGC, CENTCOM, etc.)
    dedup.py                 # Semantic dedup (sentence-transformers)
  markets/
    kalshi.py                # Kalshi API client (RSA-PSS auth)
    polymarket.py            # Polymarket read-only client
    schemas.py               # MarketPrice, Orderbook, Position models
  prediction/
    oil_price.py             # Oil price direction predictor
    ceasefire.py             # Ceasefire probability predictor
    hormuz.py                # Hormuz reopening predictor
    schemas.py               # PredictionOutput model
  divergence/
    detector.py              # Model vs market comparison
  scoring/
    tracker.py               # Paper trade tracking + P&L
  simulation/
    cascade.py               # 6-rule cascade engine
    engine.py                # Discrete event simulation
    world_state.py           # In-memory world state
    config.py                # YAML scenario config
    circuit_breaker.py       # Escalation limiter
  budget/
    tracker.py               # $20/day LLM budget enforcement
  db/
    schema.py                # DuckDB schema (12 tables)
    writer.py                # Async single-writer queue
    queries.py               # Read-only query functions
```

## Testing

```bash
cd backend
python -m pytest tests/ -x -v    # 147 tests
```

## Key Design Decisions

- **3 models, not 50 agents**: Structured causal reasoning on oil/ceasefire/Hormuz beats shallow sentiment analysis at 1/100th the cost
- **Cascade engine as causal model**: The 6-rule cascade chain (blockade -> flow -> bypass -> price -> downstream -> insurance) IS the reasoning that market bots miss
- **Paper trading first**: Prove edge on Kalshi sandbox before risking capital
- **P&L as eval**: Prediction market resolution replaces manual ground truth scoring
- **Google News RSS over BigQuery**: Free, no auth, 5-15 min latency vs BigQuery's cost and credential requirements

## Context

- Active US-Iran war (Operation Epic Fury, Feb 28 2026). Khamenei killed. Strait of Hormuz was effectively closed.
- 2-week ceasefire agreed April 7 2026, mediated by Pakistan. Talks in Islamabad.
- Oil: Brent hit $118 Q1, dropped 16% to $92 on ceasefire. Pre-war ~$70.
- $200M+ traded on Kalshi/Polymarket on Iran outcomes.
- 30%+ of Polymarket wallets are AI bots. Edge is in reasoning depth, not speed.

## License

Private project. Not open source.
