# Parallax Dashboard Redesign — Design Spec

## Overview

Replace the existing Streamlit dashboard and simulation-focused React frontend with a single React trading intelligence dashboard. Single-page layout, dark terminal aesthetic, sharp edges, tight spacing. Consumes existing FastAPI endpoints with 5-minute auto-polling.

## Decisions Made

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Map / simulation | Skip entirely | No real tanker/AIS data. Tanker data is a lagging indicator — doesn't help models that predict from news. Cosmetic without actionable data. |
| Tech stack | React + Vite + TypeScript + charting lib | Full control, no extra abstractions. Existing Vite/React/TS setup in repo. |
| UI framework | None (custom CSS) | Sharp terminal aesthetic, zero border-radius, tight spacing. No shadcn/Tailwind. |
| Data refresh | Auto-poll every 5 minutes | Matches twice-daily cron cadence. Shows "last updated" timestamp. Simple `setInterval` + fetch. |
| Layout | Dashboard grid with expandable panels | Most info-dense. Sticky KPI header, model cards, markets table with click-to-expand contract detail. |
| Edge style | Sharp (0 border-radius), 1px borders, 8-10px padding | Terminal-dense, every pixel earns its keep. |
| Signal aggregation | Weighted ensemble (hit-rate-based weights) | Self-correcting — bad models auto-downweight. Used by Polymarket/agents and quant funds. |
| Portfolio simulation | $1,000 fake capital, Quarter-Kelly sizing, hold-to-settlement | Pure computation on existing signal_ledger + market_prices data. No new API calls. |

## Priority Order (User-Defined)

1. **P&L** — Am I making or losing money? (hero: sticky KPI bar + cumulative chart)
2. **Model performance** — Getting better or worse? (hero: model cards + health panel)
3. **Markets** — What am I tracking? (full section: expandable contract table)
4. **Signals** — Where are edges? Explained well. (inside contract expansion)
5. **Ops health** — Pipeline working? (compact footer)

## Architecture

### Frontend

```
frontend/src/
  App.tsx                    # Single-page layout, data fetching, 5m polling
  types.ts                   # TypeScript interfaces for API responses
  components/
    KpiBar.tsx               # Sticky header: P&L, hit rate, signals, last run, budget
    ModelCards.tsx            # 3-across: probability, direction, timeframe, sparkline, hit rate, trend
    MarketsTable.tsx          # Contract rows: ticker, description, market%, model%, edge, proxy, signal, volume
    ContractDetail.tsx        # Expanded row: resolution criteria, order book, price chart, edge math, reasoning, signal history, exit analysis
    ModelHealth.tsx           # Brier score, hit rates by proxy, calibration gap, edge quality, signal breakdown
    PortfolioPanel.tsx        # Simulated portfolio: equity curve, open positions, closed trades, risk metrics
    OpsFooter.tsx             # Pipeline status, run count, errors, LLM cost, staleness, refresh timer
    Sparkline.tsx             # Reusable inline sparkline (SVG)
    PriceChart.tsx            # Model vs market probability over time (Recharts or raw SVG)
  hooks/
    usePolling.ts             # Generic polling hook: fetch on mount, refetch every N ms
    useApi.ts                 # Typed fetch wrappers for each endpoint
  lib/
    format.ts                # Formatting: percentages, USD, dates, edge display
    colors.ts                # Color constants matching design palette
```

### Data Flow

```
FastAPI Backend (existing)          React Frontend (new)
────────────────────────            ────────────────────
GET /api/health          ◄────────  usePolling(5min) → KpiBar, OpsFooter
GET /api/predictions     ◄────────  usePolling(5min) → ModelCards
GET /api/markets         ◄────────  usePolling(5min) → MarketsTable
GET /api/divergences     ◄────────  usePolling(5min) → MarketsTable (edge/signal data)
GET /api/portfolio       ◄────────  usePolling(5min) → PortfolioPanel, KpiBar
```

### New API Endpoints Needed

The existing 5 endpoints cover most needs, but the dashboard requires additional data not currently exposed:

| Endpoint | Purpose | Data Source |
|----------|---------|-------------|
| `GET /api/scorecard` | Model health metrics (Brier, hit rate, calibration) | `daily_scorecard` table |
| `GET /api/signals?contract=X` | Signal history for a specific contract | `signal_ledger` table |
| `GET /api/contracts` | Contract registry with resolution criteria | `contract_registry` table |
| `GET /api/edge-decay?contract=X` | Edge decay data for exit analysis | `calibration.edge_decay_over_time()` |
| `GET /api/price-history?ticker=X` | Market price history for chart | `market_prices` table |
| `GET /api/prediction-history` | Prediction probabilities over time per model | `prediction_log` table |
| `GET /api/portfolio` | Simulated portfolio state (positions, equity, P&L) | Computed from `signal_ledger` + `market_prices` |

## Section Specifications

### 1. KPI Bar (Sticky Header)

Always visible at top of viewport.

| KPI | Source | Format | Color Logic |
|-----|--------|--------|-------------|
| Portfolio | `/api/portfolio` → portfolio_value | `$1,024.50 +2.45%` | Green if above starting capital, red if below |
| Hit Rate | `/api/scorecard` → signal_hit_rate | `3/5 (60%)` | Fraction + percentage. Always show sample size. |
| Active Signals | `/api/divergences` → count where signal != HOLD/REFUSED | `5 signals` | Amber |
| Last Run | `/api/health` → last_brief_time | `2h ago` | Relative time. Red if >24h. |
| Budget | `/api/health` → budget stats | `$5.23/$20` | Amber if >80% used, red if >95% |

### 2. Model Cards (3-Across Row)

One card per model: oil_price, ceasefire, hormuz_reopening.

Each card shows:
- **Model name** (uppercase label)
- **Probability** (large number, colored by direction)
- **Direction + timeframe** (e.g., "increase 7d")
- **Sparkline** (last 10 predictions from `/api/prediction-history`)
- **Hit rate** as fraction (e.g., "hit: 3/4") from `/api/scorecard` calibration data
- **Trend indicator** (improving/stable/new) based on hit rate direction

### 3. Markets Table

Default view: collapsed rows sorted by absolute edge descending.

| Column | Width | Content |
|--------|-------|---------|
| Contract | 2.2fr | Ticker + resolution description (from registry) |
| Market | 0.6fr | Current market price (derived yes price) |
| Model | 0.6fr | Model's fair value probability |
| Edge | 0.6fr | Effective edge (colored green/red) |
| Proxy | 0.5fr | Badge: DIRECT / NEAR / LOOSE |
| Signal | 0.6fr | Badge: BUY YES / BUY NO / HOLD |
| Volume | 0.4fr | Contract volume |
| Expand | 0.2fr | Arrow indicator |

Row styling:
- Active signals (BUY_YES/BUY_NO): full color text
- HOLD signals: muted/dimmed text
- Selected/expanded row: subtle indigo background tint

### 4. Contract Detail (Expanded Row)

Appears inline below the clicked row. Left border: 2px solid indigo.

**Row 1** (2 columns):
- Left: Contract resolution text, venue, proxy class, expiry. Order book (YES/NO bid/ask/spread).
- Right: Price history chart (model probability line + market price line over time). Edge math breakdown (raw edge - fee - slippage = effective edge).

**Row 2** (3 columns):
- Left: Model reasoning (full text from latest prediction).
- Center: Signal history (last 5 runs showing signal + edge per run, with trend annotation).
- Right: Exit analysis — counterfactual hold-vs-sell comparison using edge decay data. Shows avg decay rate, time to zero edge, round-trip cost, and verdict (hold/sell).

### 5. Model Health Panel (Left Column)

All metrics include: current value, target/benchmark, and plain-English label.

| Metric | Format | Target | Explanation |
|--------|--------|--------|-------------|
| Brier Score | 0.23 | good < 0.22, random = 0.25 | Lower = better calibrated |
| Overall Hit Rate | 3/5 (60%) with trend arrow | >50% | Fraction always shown for sample size |
| Hit Rate by Proxy | Indented rows per class | Direct > Near > Loose expected | Shows which proxy types are reliable |
| Calibration Gap | 12% | <10% | Max gap between predicted and actual |
| Edge Quality | 2.3x | >1.0 | Ratio: big edge win rate / small edge win rate |
| Avg Edge (actionable) | +11.2% | >5% min | Mean effective edge on tradable signals |
| Signal Breakdown | Inline counts | — | BUY_YES / BUY_NO / HOLD / REFUSED counts + actionable ratio |

### 6. Simulated Portfolio (Right Column)

$1,000 fake capital starting Apr 1, running through the 14-day validation window (Apr 7-21). Uses actual signals from signal_ledger + Quarter-Kelly sizing from portfolio allocator. Hold-to-settlement strategy. All computed server-side from existing data — no new API calls to external services.

**Summary Row** (5 cells):
| Metric | Format | Notes |
|--------|--------|-------|
| Portfolio Value | $1,024.50 (+2.45%) | Current value = cash + mark-to-market positions |
| Cash Available | $847.20 (82.7%) | Undeployed capital |
| Deployed | $177.30 (3 positions) | Sum of open position notional |
| Max Drawdown | -$12.40 (-1.24%) | Largest peak-to-trough decline |
| Sharpe (annualized) | 1.8 | Annualized from daily returns. Show sample size. |

**Equity Curve**: Line chart from Apr 1 to today, with future dates (to Apr 21) dimmed. Starting capital line at $1,000 dashed. Drawdown periods shaded red. Current value labeled.

**Open Positions Table**:
| Column | Content |
|--------|---------|
| Contract | Ticker |
| Side | YES/NO |
| Qty | Number of contracts |
| Entry | Entry price |
| Current | Current market price |
| Size | Notional ($) |
| Unreal P&L | Unrealized profit/loss |
| Weight | % of portfolio |

**Closed Trades Table**: Contract, side, qty, entry, exit (settlement), P&L, return %.

**Risk Footer** (4 cells): Max concentration vs limit, win rate on closed trades, total fees paid, days remaining in validation window.

### 6a. Signal Aggregation Logic

When multiple models generate signals on the same contract in the same run, signals are combined using a **weighted ensemble**:

- Each model's weight = its historical hit rate on that contract's proxy class
- Combined edge = weighted average of individual model edges
- Combined signal = BUY_YES/BUY_NO/HOLD based on combined edge vs 5% threshold
- Dashboard shows: "2/3 models agree, weighted edge +8.6%, oil_price driving"

This is computed server-side in a new `portfolio/simulator.py` module. Weights auto-update as more signals resolve.

### 6b. Exit Analysis (Per-Contract, Inside Contract Detail)

Counterfactual tracker showing hold-vs-sell comparison:

| Metric | Source |
|--------|--------|
| Avg decay rate | `calibration.edge_decay_over_time()` — edge change between consecutive runs |
| Time to zero edge | Extrapolated from decay rate |
| Round-trip cost | 5.5% (2x fee + 2x slippage) |
| Exit profitable? | YES if avg decay > round-trip cost, NO otherwise |
| Verdict | "Hold to settlement" or "Exit trading may be profitable" |

Not a sell engine — purely observational. When data shows exits ARE profitable, the dashboard flags it.

### 7. Ops Footer (Single Line)

Compact status bar:
- Pipeline status dot (green = healthy, red = errors)
- Run count today + success rate
- Error count
- LLM cost today
- Quote staleness rate
- Auto-refresh countdown

## Design System

### Colors (Keep Existing Palette)

```
Background:  #09090b
Surface:     #111113
Border:      #1c1c1f
Dim:         #3f3f46
Muted:       #52525b
Subtle:      #71717a
Text:        #e4e4e7
White:       #fafafa
Green:       #22c55e   (positive edge, profit, good metrics)
Red:         #ef4444   (negative edge, loss, bad metrics)
Amber:       #f59e0b   (warning, counterfactual labels)
Indigo:      #818cf8   (neutral, direct proxy, market price line)
Purple:      #a78bfa   (near proxy)
Cyan:        #22d3ee   (info accents)
```

### Typography

- **Headers/KPIs**: Inter, system-ui (sans-serif). Weight 700 for numbers, 600 for labels.
- **Data/Code**: JetBrains Mono, monospace. Weight 400 for values, 500 for labels.
- **Section labels**: JetBrains Mono, 9px, uppercase, letter-spacing 0.1em, color muted.

### Spacing Rules

- Zero border-radius everywhere
- 1px solid borders (#1c1c1f)
- Cell padding: 8-10px
- Grid gaps: 0 (borders act as separators)
- No margin between sections — borders define boundaries

### Component Patterns

- **Badges**: Inline-block, 1px border, 10px font. Color variants: buy (green), sell (red), hold (gray), direct (indigo), near (purple), loose (gray).
- **Metric rows**: Flex between label and value. Subtle color for label, white/colored for value, dim for benchmark text.
- **Expandable rows**: Click toggles detail panel. Arrow rotates (right=collapsed, down=expanded). Expanded panel has left indigo border.
- **Charts**: Raw SVG for sparklines. Recharts (or lightweight alternative) for price history charts. Dark background (#0a0a0c), dim grid lines (#18181b).

## Data Refresh Strategy

- All endpoints polled on page load
- `setInterval` re-fetches every 5 minutes (300,000ms)
- Each section shows data independently (no global loading state)
- "Last updated" timestamp in ops footer
- Manual refresh button in KPI bar (optional)
- Stale data indicator: if any endpoint fails, show amber dot next to affected section

## What We're NOT Building

- No map/simulation visualization (no real data to power it)
- No WebSocket real-time updates (overkill for 2x/day cron)
- No authentication/login
- No settings/configuration UI
- No mobile-specific layout (desktop-first, functional at 1200px+)
- No sell/exit engine (counterfactual tracking only)
- No multi-day news context or reflection calls (next phase — saved to memory)

## New Backend Modules

### `portfolio/simulator.py`

Server-side portfolio simulator that replays signal_ledger chronologically:

1. Initialize with $1,000 cash, empty positions
2. For each run (chronological), aggregate signals per contract using weighted ensemble
3. On BUY signal: open position using Quarter-Kelly sizing (respecting risk limits)
4. On HOLD for existing position: no action, update mark-to-market
5. On settlement (resolution_price backfilled): close position, realize P&L
6. Track equity curve, drawdown, fees, Sharpe ratio

Weights per model = historical hit rate on that contract's proxy class. Weights update as signals resolve.

No partial sells. No active exits. Hold-to-settlement only.

Exposed via `GET /api/portfolio` returning: portfolio_value, cash, deployed, positions[], closed_trades[], equity_curve[], max_drawdown, sharpe, total_fees, days_remaining.

## Migration Plan

1. Replace existing `frontend/src/` contents with new dashboard code
2. Add 7 new API endpoints to `backend/src/parallax/main.py`
3. Add `portfolio/simulator.py` for server-side portfolio computation
4. Keep Streamlit dashboard as-is (can remove later once React is validated)
5. Keep existing Vite/React/TypeScript build tooling
6. Remove deck.gl, MapLibre, react-map-gl, h3-js dependencies (map code deleted)
