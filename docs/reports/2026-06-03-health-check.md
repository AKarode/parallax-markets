# Parallax Health Check — 2026-06-03

**Status: YELLOW**

## Summary

No code changes since the 2026-06-02 report — the only commit was the health check document itself. All issues flagged yesterday remain open. Two new observations are added today: the budget cap has no actual gate (it is measured but never checked before making LLM calls), and ingestion source failures are silently dropped with no per-source logging.

---

## Issues Found

### [HIGH] DuckDB Single-Writer Violations *(carry-over, unresolved)*

The spec mandates all writes via `DbWriter`'s `asyncio.Queue`. The following modules bypass it with direct `conn.execute()` writes:

- **`scoring/ledger.py`** — `INSERT`/`UPDATE signal_ledger` (lines 227, 258)
- **`scoring/tracker.py`** — `INSERT`/`UPDATE trade_positions`, `INSERT`/`UPDATE trade_orders`, `INSERT INTO trade_fills` (lines 518, 462, 674, 713, 746)
- **`scoring/prediction_log.py`** — `INSERT INTO prediction_log` (line 81)
- **`scoring/scorecard.py`** — `INSERT INTO daily_scorecard` with ON CONFLICT (line 21)
- **`ops/alerts.py`** — `INSERT INTO ops_events` (line 106)
- **`budget/tracker.py`** — `INSERT INTO llm_usage` (line 43)
- **`backtest/runner.py`** — `INSERT`/`UPDATE backtest_runs`, `INSERT`/`UPDATE backtest_predictions` (lines 290, 308, 329, 356)

Concurrent CLI (cron) + FastAPI execution creates a real write-write race. Tests use per-test in-memory connections, masking this.

### [HIGH] Budget Cap Not Enforced as a Gate *(new observation)*

`BudgetTracker.is_over_budget()` exists but is **never called before making LLM API calls**. In `cli/brief.py`, `BudgetTracker` is initialized (`budget = BudgetTracker(daily_cap_usd=20.0)`) and its stats are printed in the formatted brief — but no code path checks `budget.is_over_budget()` before invoking the three predictors. The budget is a reporting metric only, not an enforced limit. If the cap is breached, the next cron run will still make three Opus calls.

### [HIGH] Model Cost Mismatch vs Budget Cap *(carry-over, unresolved)*

All three predictors hardcode `claude-opus-4-20250514`:
- `prediction/oil_price.py:143`
- `prediction/ceasefire.py:116`
- `prediction/hormuz.py:118`

The `ensemble.py:128` records cost with the string `"opus"`, which does correctly match `_PRICING["opus"]` (input=$0.015/1K, output=$0.075/1K). However, CLAUDE.md states "3 Sonnet calls ~$0.02/run" — the actual cost with Opus is ~$0.30–$0.60/run, ~15–30× higher. The $20/day cap comment claiming "massive headroom" is inaccurate under Opus pricing.

### [MEDIUM] Silent Ingestion Source Failures *(new observation)*

`cli/brief.py:_fetch_gdelt_events()` uses `asyncio.gather(..., return_exceptions=True)` and checks `isinstance(result, list)` to skip failed sources. This gracefully degrades but **logs nothing** when an individual source fails. If Google News, GDELT, or Truth Social throws, the exception object is silently discarded. The outer `except Exception: logger.exception(...)` only fires if `asyncio.gather` itself raises (it won't with `return_exceptions=True`). Operators have no visibility into which sources are failing.

### [MEDIUM] Architecture Drift — Agent Swarm Not Implemented *(carry-over, unresolved)*

The Phase 1 spec (Tasks 9–14+) defines `agents/schemas.py`, `agents/registry.py`, `agents/router.py`, `agents/runner.py` for a 50-agent hierarchy. The `agents/` directory is entirely absent. The project pivoted to a 3-model ensemble, which is a sound product decision, but the spec and plan have not been updated to reflect this.

### [MEDIUM] Architecture Drift — Spatial Layer Not Implemented *(carry-over, unresolved)*

The spec defines `spatial/h3_utils.py` and a 4-resolution H3 model. The `spatial/` directory does not exist. Dependencies `h3`, `searoute`, `shapely` appear in CLAUDE.md's Key Dependencies but are absent from `pyproject.toml`. The cascade engine uses abstract string cell identifiers, not real H3 cells. `frontend/package.json` also lacks `deck.gl`, `maplibre-gl`, `h3-js`, and `react-map-gl` — all listed in CLAUDE.md's Technology Stack.

### [MEDIUM] Missing Simulation Modules from Plan *(carry-over, unresolved)*

From the implementation plan, these remain unbuilt:
- `simulation/engine.py` — Discrete Event Simulation scheduler (asyncio + heapq)
- `simulation/circuit_breaker.py` — Threshold-gated LLM activation with cooldown

`backtest/engine.py` handles historical replay only, not live event-driven simulation.

### [LOW] Outdated Model ID `claude-opus-4-20250514` *(carry-over, unresolved)*

The `20250514` release-date suffix is a retired identifier. As of June 2026, the canonical ID is `claude-opus-4-8`. Verify the old string still resolves at the Anthropic API, or migrate to `claude-opus-4-8` (or cost-appropriate `claude-sonnet-4-6`).

### [LOW] CLAUDE.md Key Dependencies Out of Sync *(carry-over, unresolved)*

CLAUDE.md lists `h3 4.1+`, `searoute 1.3+`, `shapely 2.0+`, `sentence-transformers 3.4+`, `websockets 14.0+`, `google-cloud-bigquery 3.27+` as Key Dependencies. None appear in `pyproject.toml`. Conversely, `cryptography>=44.0` and `truthbrush>=0.2` are in `pyproject.toml` but not in CLAUDE.md.

### [LOW] `truthbrush` Dependency Fragile *(carry-over, unresolved)*

`truthbrush>=0.2` is an unofficial scraper with no stable API contract. It can break on site changes silently. Combined with the per-source silent failure mode noted above, Truth Social outages will go undetected.

---

## Test Coverage Assessment

**Strong (42 test files):** schema, writer, cascade, world state, config, GDELT, Google News, EIA, Kalshi, Polymarket, prediction ensemble, calibration, recalibration, signal ledger, divergence, paper trade tracker, dashboard, scorecard, report card, backtest look-ahead guard, portfolio simulator.

**Gaps:**
- No concurrent-write stress test exposing the single-writer violations
- No test verifying `is_over_budget()` gates LLM calls (it doesn't — the test would fail)
- No test verifying per-source ingestion failures are logged
- No integration test running `brief.py` + FastAPI simultaneously
- Agents/spatial/DES not implemented, so no coverage needed there
- `test_truth_social.py` exists; `truthbrush` may not be installable in CI

---

## Recommendations

1. **[URGENT] Enforce budget cap before LLM calls** — Add `if budget.is_over_budget(): return _get_fallback_prediction(...)` (or raise) before the three predictor calls in `brief.py`. Without this, the `$20/day` cap is decorative.

2. **[URGENT] Route all writes through `DbWriter`** — Inject `DbWriter` into `SignalLedger`, `PaperTradeTracker`, `PredictionLogger`, `DuckDBAlertSink`, `BudgetTracker`, `compute_daily_scorecard()`, and `BacktestRunner`. The single-writer pattern only protects data integrity if it is universal.

3. **[HIGH] Log per-source ingestion failures** — After the `asyncio.gather` in `_fetch_gdelt_events`, add a check for each result: `if isinstance(result, Exception): logger.warning("source X failed: %s", result)`.

4. **[MEDIUM] Reconcile model vs. budget** — Either switch to `claude-sonnet-4-6` (matching CLAUDE.md's cost claim) or update the budget model to Opus pricing and add real enforcement. Update CLAUDE.md to reflect actual model and cost.

5. **[MEDIUM] Update spec/plan to reflect the pivot** — Add a brief note to the spec and plan documents acknowledging the agent-swarm scope was narrowed to a 3-model ensemble. Keeps future readers from being confused about missing agents/ and spatial/ directories.

6. **[LOW] Migrate to current model ID** — Replace `claude-opus-4-20250514` with `claude-opus-4-8` (or `claude-sonnet-4-6`) in all three predictor files and `ensemble.py` docstring.

7. **[LOW] Prune CLAUDE.md dependencies** — Remove uninstalled/unbuilt deps (h3, searoute, shapely, sentence-transformers, websockets, google-cloud-bigquery, deck.gl, maplibre-gl). Add actually-used deps (cryptography, truthbrush).
