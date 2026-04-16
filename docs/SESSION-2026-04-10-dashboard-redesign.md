# Session Log: Dashboard Redesign Implementation

**Date:** 2026-04-10
**Branch:** `feat/dashboard-redesign` (11 commits, not yet merged to main)
**Duration:** Full session — plan, implement, debug

## Summary

Replaced the Streamlit dashboard and simulation-focused React frontend with a single-page React trading intelligence dashboard. Built from the design spec at `docs/superpowers/specs/2026-04-09-dashboard-redesign-design.md`. Backend-first: portfolio simulator, 8 new API endpoints, 7 new query functions. Then React SPA with dark terminal aesthetic, 10 components, 5-minute auto-polling.

## What Was Built

### Backend — New Modules

| File | Purpose |
|------|---------|
| `portfolio/simulator.py` | Replays signal_ledger chronologically with weighted ensemble aggregation, Quarter-Kelly sizing, equity curve tracking. Hold-to-settlement. |
| `dashboard/data.py` (6 new functions) | `get_scorecard_metrics`, `get_signals_for_contract`, `get_active_contracts`, `get_edge_decay_for_contract`, `get_price_history`, `get_prediction_history`, `get_latest_signals_with_markets` |
| `main.py` (8 new endpoints) | `/api/scorecard`, `/api/contracts`, `/api/signals`, `/api/edge-decay`, `/api/price-history`, `/api/prediction-history`, `/api/portfolio`, `/api/latest-signals` |

### Backend — Tests

| File | Tests |
|------|-------|
| `tests/test_simulator.py` | 4 tests — empty portfolio, single buy, hold skip, Kelly sizing cap |
| `tests/test_dashboard_queries.py` | 20 tests — all 6 query functions with empty + populated data |
| `tests/test_dashboard_endpoints.py` | 20 tests — all 8 endpoints with TestClient |

### Frontend — New SPA

| File | Purpose |
|------|---------|
| `App.tsx` | Orchestrates all components, 9 polling hooks (5min interval) |
| `types.ts` | 22 TypeScript interfaces for all API responses |
| `styles.css` | Dark terminal design system — #09090b bg, zero border-radius, JetBrains Mono |
| `hooks/usePolling.ts` | Generic fetch-on-mount + interval polling hook |
| `lib/format.ts` | 9 formatting utils (usd, pct, edge, relativeTime, etc.) |
| `lib/colors.ts` | Color constants matching design palette |
| `components/KpiBar.tsx` | Sticky header — portfolio, hit rate, active signals, last run, budget |
| `components/ModelCards.tsx` | 3-across probability cards with sparklines |
| `components/Sparkline.tsx` | Reusable SVG polyline sparkline |
| `components/MarketsTable.tsx` | Expandable contract rows sorted by edge |
| `components/ContractDetail.tsx` | Expanded row — resolution, order book, price chart, reasoning, signals, exit analysis |
| `components/PriceChart.tsx` | Recharts LineChart — model vs market probability |
| `components/ModelHealth.tsx` | Brier score, hit rate, calibration gap with benchmarks |
| `components/PortfolioPanel.tsx` | Equity curve, open positions, closed trades, risk footer |
| `components/OpsFooter.tsx` | Pipeline status bar with refresh countdown |

## Architecture

```
React SPA (port 3000)                    FastAPI (port 8000)
─────────────────────                    ───────────────────
usePolling(5min) ──────────────────────► GET /api/health
usePolling(5min) ──────────────────────► GET /api/predictions (app.state cache)
usePolling(5min) ──────────────────────► GET /api/markets (app.state cache)
usePolling(5min) ──────────────────────► GET /api/divergences (app.state cache)
usePolling(5min) ──────────────────────► GET /api/scorecard → daily_scorecard table
usePolling(5min) ──────────────────────► GET /api/contracts → contract_registry table
usePolling(5min) ──────────────────────► GET /api/prediction-history → prediction_log table
usePolling(5min) ──────────────────────► GET /api/portfolio → PortfolioSimulator(signal_ledger)
usePolling(5min) ──────────────────────► GET /api/latest-signals → signal_ledger + market_prices
On expand:
  usePolling ──────────────────────────► GET /api/signals?contract=X
  usePolling ──────────────────────────► GET /api/edge-decay?contract=X
  usePolling ──────────────────────────► GET /api/price-history?ticker=X
```

Key design: existing endpoints (`/api/predictions`, `/api/markets`, `/api/divergences`) serve from `app.state` memory cache, which is only populated during live API brief runs. The new endpoints serve from DuckDB directly. The frontend falls back to DB-backed data (`/api/latest-signals`, `/api/prediction-history`) when the cache is empty.

## Key Design Decisions

1. **DB-backed fallback for markets table** — The existing divergences endpoint only has data during live API runs. Added `/api/latest-signals` that queries signal_ledger directly, picking the most recent signal per contract across all runs.

2. **Portfolio simulator as pure computation** — No new tables. Replays signal_ledger chronologically, applies Quarter-Kelly sizing with weighted ensemble, tracks equity curve. All server-side, no external API calls.

3. **Entry price inference** — Many signal_ledger rows have `entry_price=NULL` and `entry_side=NULL`. Fixed by: (a) inferring entry_side from signal name (BUY_YES→yes), (b) falling back to `market_yes_price`/`market_no_price` from signal_ledger, (c) COALESCE with market_prices table.

4. **Health endpoint DB fallback** — `last_brief_time` was only set by POST /api/brief/run. Added fallback to `MAX(started_at) FROM runs` so CLI cron runs show up.

5. **No UI framework** — Custom CSS with sharp terminal aesthetic. Zero border-radius, 1px borders, monospace data font. Matches the existing Streamlit dashboard palette.

## Setbacks and Fixes

### 1. Cash Double-Counting in Portfolio Simulator
**Problem:** `_recalculate_cash()` method reconstructed cash from scratch but was called after the main loop had already tracked cash, causing position costs to be deducted twice.
**Root cause:** Implementer added a "safety" recalculation that conflicted with the running cash tracker.
**Fix:** Removed `_recalculate_cash()`. Made `_settle_remaining()` return `(cash_delta, fees_delta)` tuple instead of trying to mutate caller's float.
**Lesson:** Don't reconstruct derived state — track it incrementally.

### 2. Empty Markets Table (Only 1 Contract)
**Problem:** Markets table showed only KXUSAIRANAGREEMENT-27 instead of all 4 contracts.
**Root cause:** The `get_latest_signals_with_markets` query used a CTE that picked the latest run_id with actionable signals, but that run only evaluated one contract. Other contracts' signals were in earlier runs.
**Fix:** Changed query to pick the latest signal per contract across ALL runs (ROW_NUMBER PARTITION BY contract_ticker ORDER BY created_at DESC).
**Lesson:** Don't assume all contracts are evaluated in every run.

### 3. Divergences/Predictions/Markets Endpoints Return Empty
**Problem:** `/api/predictions`, `/api/markets`, `/api/divergences` all return empty arrays.
**Root cause:** These endpoints serve from `app.state.last_*` which is only populated by `POST /api/brief/run`. The CLI cron (`parallax.cli.brief`) doesn't update app.state.
**Fix:** Added `/api/latest-signals` endpoint that queries DuckDB directly. Frontend falls back to this when divergences are empty. ModelCards falls back to prediction_history.
**Lesson:** If endpoints serve from memory cache, always have a DB-backed fallback for the dashboard.

### 4. Portfolio Simulator Opens Zero Positions
**Problem:** Simulator showed $1,000 flat with no positions despite having BUY signals.
**Root cause:** All signal_ledger rows had `entry_price=NULL` and `entry_side=NULL`. The simulator skipped them.
**Fix:** Three changes: (a) infer entry_side from signal name, (b) fall back to market_yes_price from signal_ledger, (c) COALESCE with market_prices table in the _load_signals query.
**Lesson:** Pipeline signal recording needs to populate entry_price and entry_side. Current data has these as NULL because market orderbook data wasn't flowing when signals were recorded.

### 5. Latest Run Shows All REFUSED
**Problem:** `get_latest_signals_with_markets` returned empty because the absolute latest run had only REFUSED signals, which were filtered out.
**Root cause:** The CTE `SELECT run_id FROM signal_ledger ORDER BY created_at DESC LIMIT 1` picked the latest run regardless of signal type.
**Fix:** Added `WHERE signal IN ('BUY_YES', 'BUY_NO', 'HOLD')` to the latest_run CTE.
**Lesson:** Filter for actionable signals before picking the "latest" run.

### 6. Divergence Type Mismatch
**Problem:** TypeScript `Divergence.prediction` was typed as `string`, `market_price` as `number | null`. Components couldn't access nested fields like `divergence.prediction.reasoning`.
**Root cause:** Subagent typed these as primitives instead of nested objects.
**Fix:** Changed to `prediction: Prediction | null` and `market_price: MarketData | null`.
**Lesson:** Cross-check API response shapes against Pydantic model_dump() output.

### 7. Disk Full During Session
**Problem:** `/dev/disk3s1s1` hit 100% capacity, blocking all bash commands.
**Root cause:** Accumulated Claude worktree copies, Playwright snapshots, and temp files.
**Fix:** User cleared space manually. Need to clean `.claude/worktrees/` periodically.
**Lesson:** Monitor disk space during long sessions with many subagent dispatches.

## Current State

**Working:**
- All 7 dashboard sections render with real data
- 4 contracts visible in markets table with edges, signals, proxy badges
- Model cards show probabilities from prediction_history with sparklines
- Last Run shows real cron timestamp
- Equity curve renders (flat at $1,000 — data issue, not code issue)
- 44 backend tests pass
- TypeScript compiles clean
- Vite production build succeeds (553KB JS + 6KB CSS)

**Not Working / Known Limitations:**
- Portfolio stays at $1,000 — signal_ledger rows lack `market_yes_price` for most contracts, so simulator can't determine entry prices for older runs
- Hit Rate, Brier Score, Calibration Gap all show "—" — no contracts have resolved yet (no `model_was_correct` data)
- Contract detail expansion not tested with Playwright (browser context died)
- `git add -A` commit accidentally included worktree artifacts — needs cleanup before merge

**Data gaps (not code bugs):**
- Only 3 pipeline runs in DB (need more for calibration metrics)
- `market_yes_price` NULL in most signal_ledger rows (pipeline wasn't recording market prices)
- No contract resolutions yet (needed for hit rate, Brier score)

## Environment Setup

```bash
# Backend
cd backend && pip install -e ".[dev]"
DUCKDB_PATH=data/parallax.duckdb uvicorn parallax.main:app --port 8000

# Frontend
cd frontend && npm install
npm run dev  # starts on port 3000, proxies /api to :8000

# Tests
cd backend && python -m pytest tests/test_simulator.py tests/test_dashboard_queries.py tests/test_dashboard_endpoints.py -v
cd frontend && npx tsc --noEmit
```

## Next Steps

1. **Merge branch** — Clean up the commit that included worktree artifacts, then merge `feat/dashboard-redesign` to main
2. **Fix pipeline market price recording** — Ensure `signal_ledger.market_yes_price` is populated on every signal record so the portfolio simulator has entry prices
3. **Run more pipeline crons** — Need 7+ days of data for calibration metrics to populate
4. **Model Intelligence phase** — Spec at `docs/superpowers/specs/2026-04-09-model-intelligence-design.md`: multi-day context, reflection calls, news impact tracking
5. **Contract detail Playwright testing** — Verify expand/collapse, price charts, signal history render correctly

## Commits

```
217aa64 fix: show all contracts, infer entry prices, pull last run from DB
ebc06e7 fix: use DB-backed data for dashboard when live cache is empty
41c54ae feat: wire dashboard App.tsx with all components and 5-minute polling
232f714 feat: add ModelHealth, PortfolioPanel, and OpsFooter components
d7fbf4f feat: add MarketsTable with expandable ContractDetail and PriceChart
d6fabcc feat: add KpiBar, ModelCards, and Sparkline components
0f9ae86 feat: scaffold frontend with Vite + React + TypeScript, design system, polling hook
573b9b5 feat: add 7 dashboard API endpoints
a602af7 feat: add dashboard query functions for scorecard, contracts, price history, signals
ecaf120 feat: add portfolio simulator with weighted ensemble and Quarter-Kelly sizing
fd8815b feat: add portfolio simulator with Quarter-Kelly sizing and equity tracking
```
