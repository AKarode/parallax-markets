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
              +---------+---------+
              |                   |
         Paper Trading      Signal Ledger
       (Kalshi sandbox)    (DuckDB + calibration)
                                  |
                          Feedback Loop
                    (recalibration, track records,
                     discount auto-adjustment)
```

## Prediction Models

| Model | What It Predicts | Method |
|-------|-----------------|--------|
| **Oil Price** | Brent/WTI direction + magnitude over 7 days | Cascade engine (blockade -> flow -> bypass -> price) + LLM reasoning |
| **Ceasefire** | Probability of ceasefire holding 14 days | Diplomatic event filtering + LLM analysis |
| **Hormuz Reopening** | Probability of strait reopening in 14 days | Cascade scenario modeling + LLM reasoning |

Each model makes a single Claude Sonnet call (~$0.007/call). Total cost: ~$0.02 per brief run, well under the $20/day budget.

## Dashboard

Dark-themed Streamlit dashboard showing real-time predictions, signal history with contract descriptions, edge analysis charts, and prediction timeline.

```bash
cd backend && DUCKDB_PATH=data/parallax.duckdb streamlit run src/parallax/dashboard/app.py
```

Requires a pipeline run first to populate the database:

```bash
cd backend && DUCKDB_PATH=data/parallax.duckdb python -m parallax.cli.brief --no-trade
```

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

# Create .env file
cat > .env << 'EOF'
ANTHROPIC_API_KEY=your-key
KALSHI_API_KEY=your-kalshi-key-id
KALSHI_PRIVATE_KEY_PATH=~/.kalshi/private_key.pem
EIA_API_KEY=your-eia-key
DUCKDB_PATH=data/parallax.duckdb
EOF

# Load env and run
set -a && source .env && set +a
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

# Scheduled mode (JSON output for cron)
python -m parallax.cli.brief --scheduled
```

### Example Output

```
====================================================
PARALLAX DAILY INTELLIGENCE BRIEF
2026-04-09 05:56 UTC | Budget: $0.02/$20.00
====================================================

--- PREDICTIONS ---

CEASEFIRE
  Probability: 25%
  Confidence: 70% | Timeframe: 14d
  Reasoning: The ceasefire appears to be unraveling rapidly...

HORMUZ REOPENING
  Probability: 75%
  Confidence: 65% | Timeframe: 14d
  Reasoning: The current complete closure represents an unprecedented...

OIL PRICE
  Direction: decrease | Magnitude: $-5-$-2
  Confidence: 70% | Timeframe: 7d
  Reasoning: Significant disconnect between spot prices ($138.21)...

--- DIVERGENCES ---

  SIGNAL: BUY_NO KXUSAIRANAGREEMENT-27
  Model: 25% vs Market: 50% | Edge: -15.0% (moderate)

--- SIGNAL AUDIT ---

  KXUSAIRANAGREEMENT-27   ceasefire       near_proxy   -15.0%  BUY_NO [HALF]
  KXUSAIRANAGREEMENT-27   hormuz_reopen   loose_proxy   +7.5%  BUY_YES [HALF]
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
  contracts/
    schemas.py              # ContractRecord, MappingResult, ProxyClass
    registry.py             # DuckDB-backed contract registry CRUD
    mapping_policy.py       # Proxy-aware alignment, edge discounting, auto-tuning
  dashboard/
    app.py                  # Streamlit dashboard (dark terminal theme)
    data.py                 # Reusable data layer (pure DuckDB queries)
  ingestion/
    google_news.py          # Google News RSS poller
    gdelt_doc.py            # GDELT DOC 2.0 API
    oil_prices.py           # EIA API v2 (Brent/WTI)
    entities.py             # Critical entity list (IRGC, CENTCOM, etc.)
  markets/
    kalshi.py               # Kalshi API client (RSA-PSS auth)
    polymarket.py           # Polymarket read-only client
    schemas.py              # MarketPrice, Orderbook, Position
  prediction/
    oil_price.py            # Oil price direction predictor
    ceasefire.py            # Ceasefire probability predictor
    hormuz.py               # Hormuz reopening predictor
    schemas.py              # PredictionOutput model
  divergence/
    detector.py             # Model vs market comparison
  scoring/
    tracker.py              # Paper trade tracking + P&L
    ledger.py               # Signal ledger with contract provenance
    prediction_log.py       # Persisted model outputs with run context
    resolution.py           # Kalshi settlement polling + P&L backfill
    calibration.py          # Hit rate, calibration curve, edge decay
    recalibration.py        # Bucket-based probability adjustment
    report_card.py          # P&L by proxy class, significance tests
    track_record.py         # Per-model hit rate for prompt injection
  simulation/
    cascade.py              # 6-rule cascade engine
    world_state.py          # In-memory world state
    config.py               # YAML scenario config
  budget/
    tracker.py              # $20/day LLM budget enforcement
  db/
    schema.py               # DuckDB schema (12 tables)
    writer.py               # Async single-writer queue
```

## Calibration Loop

The system self-improves through three feedback mechanisms:

1. **Discount auto-adjustment** -- proxy class discount factors (DIRECT=1.0, NEAR_PROXY=0.6, LOOSE_PROXY=0.3) shift toward historical hit rates using bounded EMA. DIRECT never drops below 0.8, LOOSE_PROXY never rises above 0.5.

2. **Threshold tuning** -- per-class min_edge thresholds auto-raise when small edges historically lose (win_rate < 0.4 on edges < 8%).

3. **Track record injection** -- each prediction model's prompt includes its own hit rate history, enabling self-correction based on past performance.

## Testing

```bash
cd backend
python -m pytest tests/ -x -v    # 241 tests
```

## Key Design Decisions

- **3 models, not 50 agents**: Structured causal reasoning on oil/ceasefire/Hormuz beats shallow sentiment analysis at 1/100th the cost
- **Cascade engine as causal model**: The 6-rule cascade chain (blockade -> flow -> bypass -> price -> downstream -> insurance) IS the reasoning that market bots miss
- **Paper trading first**: Prove edge on Kalshi sandbox before risking capital
- **P&L as eval**: Prediction market resolution replaces manual ground truth scoring
- **Google News RSS over BigQuery**: Free, no auth, 5-15 min latency vs BigQuery's cost and credential requirements
- **Self-calibrating pipeline**: All three tuning levers (discounts, thresholds, track records) activate automatically as data accumulates

## Context

- Active US-Iran war (Operation Epic Fury, Feb 28 2026). Khamenei killed. Strait of Hormuz was effectively closed.
- 2-week ceasefire agreed April 7 2026, mediated by Pakistan. Talks in Islamabad.
- Oil: Brent hit $118 Q1, dropped 16% to $92 on ceasefire. Pre-war ~$70.
- $200M+ traded on Kalshi/Polymarket on Iran outcomes.
- 30%+ of Polymarket wallets are AI bots. Edge is in reasoning depth, not speed.

## License

Private project. Not open source.
