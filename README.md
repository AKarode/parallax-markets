# Parallax

**Prediction-market edge finder for the Iran-Hormuz crisis.**

Parallax ingests news, runs AI prediction models, normalizes live Kalshi and Polymarket quotes, computes edge against executable entry prices, and records a paper-trading journal with order attempts, fills, and positions.

## What Changed

The repo now treats pricing and trading honestly:

- executable quotes are explicit: `best_yes_bid`, `best_yes_ask`, `best_no_bid`, `best_no_ask`
- derived prices are labeled and never used as execution inputs
- signals can be `tradable`, `degraded`, or `non_tradable`
- paper trading records `signal -> order attempt -> accepted/rejected/cancelled -> fill -> open position -> closed position`
- trading report cards use only actually filled and later closed paper positions
- signal-quality analysis remains available separately through counterfactual evaluation
- dry-run data is isolated from demo/live data by default

## How It Works

```text
News Sources                    Market Data
  Google News RSS                 Kalshi API
  GDELT DOC API                   Polymarket CLOB/Gamma
  EIA Oil Prices                         |
         |                                |
         v                                v
  3 Prediction Models            Normalized Market Snapshots
  (Claude + cascade)             executable + derived fields
         |                                |
         +----------> Mapping Policy <----+
                        executable edge
                              |
                         Signal Ledger
                explicit entry side/price semantics
                              |
                   +----------+-----------+
                   |                      |
            Signal-Quality Eval      Trade Journal
            counterfactual only      orders / fills / positions
                                             |
                                      Trading Report Card
                                     traded positions only
```

## Quick Start

### Prerequisites

- Python 3.11+
- Anthropic API key
- Kalshi API credentials for live/demo reads and paper execution

### Setup

```bash
cd backend
pip install -e ".[dev]"

cat > .env << 'EOF'
ANTHROPIC_API_KEY=your-key
KALSHI_API_KEY=your-kalshi-key-id
KALSHI_PRIVATE_KEY_PATH=~/.kalshi/private_key.pem
EIA_API_KEY=your-eia-key
PARALLAX_ENV=demo
DUCKDB_PATH=data/parallax-demo.duckdb
EOF

set -a && source .env && set +a
```

### Run

```bash
# Isolated dry run: mock predictions + isolated in-memory DB
python -m parallax.cli.brief --dry-run

# Live predictions + real market prices, no paper execution
python -m parallax.cli.brief --no-trade

# Full demo paper-trading pipeline
python -m parallax.cli.brief

# Signal-quality report (counterfactual, not traded P&L)
python -m parallax.cli.brief --calibration

# Trading report card (real paper positions only)
python -m parallax.cli.brief --report-card

# Settlement backfill
python -m parallax.cli.brief --check-resolutions
```

## Data Environments

Parallax now keeps environments explicit:

- `--dry-run` uses `dry_run` data environment and isolated in-memory storage by default
- `PARALLAX_ENV=demo` uses demo paper-trading storage, for example `data/parallax-demo.duckdb`
- `PARALLAX_ENV=live` is for live-market data / future live execution, for example `data/parallax-live.duckdb`

Persisted records include `data_environment` and execution environment fields so demo and live learning data do not silently mix.

## API Server

```bash
uvicorn parallax.main:app --reload
```

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/health` | GET | Runtime status plus data/execution environment |
| `/api/predictions` | GET | Latest predictions |
| `/api/markets` | GET | Latest normalized market snapshots |
| `/api/divergences` | GET | Current in-memory divergences |
| `/api/trades` | GET | Order journal and tracked positions |
| `/api/brief/run` | POST | Trigger a dry-run brief |

## Storage Model

Key tables:

- `market_prices`: normalized executable quotes plus labeled derived fields
- `signal_ledger`: mapping evaluation, tradability, entry semantics, execution linkages
- `trade_orders`: every order attempt and outcome
- `trade_fills`: actual fills
- `trade_positions`: open/closed paper positions

Key views:

- `signal_quality_evaluation`: resolved signal-quality / counterfactual analysis
- `trade_evaluation`: resolved traded-position analysis

## Architecture

```text
backend/src/parallax/
  cli/brief.py              brief orchestration, market persistence, paper execution
  main.py                   FastAPI API
  contracts/
    mapping_policy.py       executable edge selection + proxy discounting
    registry.py             contract registry
    schemas.py              mapping result with entry semantics
  dashboard/
    app.py                  Streamlit dashboard
    data.py                 dashboard/API query helpers
  db/
    runtime.py              environment + DB path resolution
    schema.py               DuckDB schema + additive migrations
    writer.py               async writer helper
  divergence/
    detector.py             executable-entry divergence detector
  markets/
    kalshi.py               Kalshi normalization, orderbook handling, sandbox orders
    polymarket.py           Polymarket executable/derived quote normalization
    schemas.py              market snapshot + orderbook schemas
  prediction/
    ceasefire.py
    hormuz.py
    oil_price.py
    schemas.py
  scoring/
    calibration.py          signal-quality analysis
    ledger.py               signal ledger with entry semantics
    prediction_log.py       persisted predictions with environment labels
    report_card.py          traded-only report card
    recalibration.py        bucket-based probability recalibration
    resolution.py           settlement backfill for signals and positions
    scorecard.py            daily scorecard ETL (15+ metrics, 5 categories)
    tracker.py              order/fill/position journal
    track_record.py         prompt track record
  ops/
    alerts.py               alert dispatcher + DuckDB persistence sink
    runtime.py              runtime config and kill switch
  budget/
    tracker.py              $20/day LLM budget + per-call cost persistence
  scripts/
    cron_pipeline.sh        automated pipeline runner (cron/launchd)
```

## Testing

```bash
cd backend
python -m pytest tests/ -x -v
```

The executable-pricing and journal refactor is covered by focused tests for:

- Kalshi normalization
- Polymarket normalization
- divergence detection
- mapping policy
- signal ledger
- resolution backfill
- trade/report evaluation split
- brief formatting and dry-run isolation

## Daily Scorecard

Compute 15+ metrics across Signal Quality, Execution, Portfolio/Risk, Data Quality, and Ops:

```bash
# Today's scorecard
python -m parallax.cli.brief --scorecard

# Specific date
python -m parallax.cli.brief --scorecard --date 2026-04-09
```

Metrics are persisted to the `daily_scorecard` DuckDB table and can be trended over time.

## Automated Pipeline (Cron)

Run the full pipeline on a schedule: predictions → resolution check → scorecard.

### Deploy on WSL / Linux

```bash
# Clone and install
git clone git@github.com:AKarode/parallax-markets.git
cd parallax-markets/backend
pip install -e ".[dev]"

# Set up environment
cp .env.example .env
# Edit .env with your API keys:
#   ANTHROPIC_API_KEY, KALSHI_API_KEY, KALSHI_PRIVATE_KEY_PATH

# Test the pipeline
source .env && python -m parallax.cli.brief --no-trade

# Install cron (8am + 8pm UTC)
(crontab -l 2>/dev/null; echo "0 8,20 * * * $(pwd)/scripts/cron_pipeline.sh") | crontab -

# Verify
crontab -l
```

The cron script auto-detects paths from its own location — no editing needed. Logs go to `~/parallax-logs/`.

### Deploy on macOS

Same setup, just use `launchd` or `crontab -e` to add:

```
0 8,20 * * * /path/to/parallax-markets/backend/scripts/cron_pipeline.sh
```

### What the cron does

Each run:
1. `parallax brief --no-trade --scheduled` — predictions + market reads + signal evaluation
2. `parallax brief --check-resolutions` — backfill settled contracts
3. `parallax brief --scorecard` — compute daily metrics

## Current Limitations

- accepted-but-resting orders are recorded, but there is not yet a background reconciler for later partial fills
- slippage and fee modeling are still thin outside venue response fields
- there are no hard portfolio/risk controls yet
- live trading remains out of scope; this is still a paper-trading system
