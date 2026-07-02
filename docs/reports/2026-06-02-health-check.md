# Parallax Health Check — 2026-06-02

**Status: YELLOW**

## Summary

The codebase has **intentionally pivoted** from the Phase 1 design spec (50-agent geopolitical swarm with H3 visualization) to a focused prediction-market edge-finder. Core pipeline is solid — 42 test files, full signal lifecycle from ingestion through paper trading. However, several DuckDB single-writer topology violations exist across multiple modules, all three predictors use Claude Opus where the budget model assumes Sonnet costs, and several spec modules were never built (agents swarm, spatial layer, DES engine, circuit breaker).

---

## Issues Found

### [HIGH] DuckDB Single-Writer Violations

The spec mandates a single-writer topology via `DbWriter`'s `asyncio.Queue`. The following modules bypass it and write directly to DuckDB:

- **`scoring/ledger.py`** — `INSERT INTO signal_ledger` and `UPDATE signal_ledger` at lines 225, 256
- **`scoring/tracker.py`** — `INSERT INTO trade_positions`, `UPDATE trade_positions`, `INSERT INTO trade_orders`, `UPDATE trade_orders`, `INSERT INTO trade_fills` at lines 518, 462, 674, 713, 746
- **`scoring/prediction_log.py`** — `INSERT INTO prediction_log` at line 81
- **`scoring/scorecard.py`** — `INSERT INTO daily_scorecard` with ON CONFLICT at line 21, plus many reads
- **`ops/alerts.py`** — `INSERT INTO ops_events` at line 106
- **`budget/tracker.py`** — `INSERT INTO llm_usage` at line 43
- **`backtest/runner.py`** — `INSERT INTO backtest_runs`, `INSERT INTO backtest_predictions`, two `UPDATE` statements at lines 292, 310, 331, 358

Under concurrent FastAPI + CLI execution, these are potential write-write races. The existing tests use in-memory DuckDB connections per test, which masks the problem. The `brief.py` CLI and the FastAPI app can be invoked concurrently (e.g. cron + web dashboard), creating a real collision window.

### [HIGH] Model Cost Mismatch vs Budget Cap

- **CLAUDE.md states**: "$20/day cap — 3 Sonnet calls ~$0.02/run, massive headroom"
- **Actual code**: All three predictors hardcode `claude-opus-4-20250514` (Opus)
  - `prediction/oil_price.py:143`, `prediction/ceasefire.py:116`, `prediction/hormuz.py:118`
- Opus is approximately 15× more expensive per token than Sonnet. Three Opus calls with full context windows could cost $0.30–$0.60/run, not $0.02. At frequent polling this could blow the daily cap.
- **Recommendation**: Either switch predictors to `claude-sonnet-4-6` or update the budget model to reflect Opus pricing and add hard enforcement.

### [MEDIUM] Architecture Drift — Agent Swarm Not Implemented

The Phase 1 spec and plan define Tasks 9–14+ building:
- `agents/schemas.py` — `AgentDecision`, `SubActorRecommendation`
- `agents/registry.py` — 50-agent roster with country→sub-actor hierarchy
- `agents/router.py` — event-to-agent routing
- `agents/runner.py` — async agent execution with cooling

**None of these exist.** The `agents/` directory is absent entirely. The project pivoted to a 3-model ensemble instead, which is a reasonable product decision but is not reflected in the spec or plan documents.

### [MEDIUM] Architecture Drift — Spatial Layer Not Implemented

The spec defines a 4-resolution H3 spatial model:
- `spatial/h3_utils.py` — H3 resolution bands, cell chains, chokepoint zones
- `spatial/` directory entirely absent

Dependencies `h3`, `searoute`, `shapely` are listed in CLAUDE.md as Key Dependencies but do not appear in `pyproject.toml` and are not installed. The cascade engine uses abstract cell identifiers (strings) rather than actual H3 hex cells, which limits geographic realism.

### [MEDIUM] Missing Simulation Modules from Plan

From the plan, these were specified and remain unbuilt:
- `simulation/engine.py` — Discrete Event Simulation (DES) with asyncio+heapq scheduler
- `simulation/circuit_breaker.py` — Threshold-gated LLM activation with cooldown

The `backtest/engine.py` exists but handles historical replay, not live DES. Without the DES engine, the simulation runs as a one-shot pipeline rather than a continuous event-driven loop.

### [LOW] Outdated Model ID in Code

The model string `claude-opus-4-20250514` is hardcoded across three predictor files. As of June 2026, the current model roster has moved to `claude-opus-4-8` (Opus 4.8) and `claude-sonnet-4-6`. The `20250514` suffix is a retired release date identifier. Verify the hardcoded string still resolves, or migrate to the canonical model ID.

### [LOW] CLAUDE.md Key Dependencies Out of Sync

CLAUDE.md lists `h3 4.1+`, `searoute 1.3+`, `shapely 2.0+`, `sentence-transformers 3.4+`, and `websockets 14.0+` as Key Dependencies, but none appear in `pyproject.toml`. These were planned for the spatial layer that was never built. The CLAUDE.md metadata overstates actual dependencies and should be pruned to match the current `pyproject.toml`.

### [LOW] `truthbrush` Dependency Installed but Potentially Fragile

`truthbrush>=0.2` is in `pyproject.toml` and `ingestion/truth_social.py` exists with a test (`test_truth_social.py`). The `truthbrush` library is an unofficial scraper — it can break on site changes without a versioned API contract. No circuit-breaking or graceful degradation for a Truth Social fetch failure was observed in `brief.py`'s ingestion loop.

### [INFO] BUG-01 Comment in `prediction/oil_price.py`

Line 89 has an inline comment: `# BUG-01 FIX: operate on a copy so cascade mutations don't corrupt shared state`. The bug is fixed, but the comment signals that cascade state mutation was a prior production incident. The fix (deep-copying world state before running cascade scenarios) appears correct. No action needed, but confirms that cascade→world_state interactions are a fragile surface.

---

## Test Coverage Assessment

**Strong coverage (42 test files):**
- Schema, writer, cascade, world state, config ✓
- GDELT, Google News, EIA oil prices ✓
- Kalshi, Polymarket market clients ✓
- Prediction ensemble, calibration, recalibration ✓
- Signal ledger, divergence detector, paper trade tracker ✓
- Dashboard data/endpoints, scorecard, report card ✓
- Backtest look-ahead guard (data leakage) ✓
- Portfolio simulator ✓

**Gaps:**
- No tests for agent swarm (not implemented)
- No tests for H3 spatial utilities (not implemented)
- No concurrent-write stress test for DuckDB (masks the single-writer violations)
- No integration test exercising `brief.py` + FastAPI simultaneously
- `test_truth_social.py` exists but `truthbrush` was not found installed in the environment

---

## Recommendations

1. **[URGENT] Route all writes through `DbWriter`** — Wrap `SignalLedger`, `PaperTradeTracker`, `PredictionLogger`, `DuckDBAlertSink`, `BudgetTracker`, `compute_daily_scorecard()`, and `BacktestRunner` to enqueue writes instead of executing directly. For components that currently hold a `conn` reference, inject the `DbWriter` instead.

2. **[URGENT] Reconcile model vs. budget** — Either downgrade predictors to `claude-sonnet-4-6` (matching the CLAUDE.md cost model) or raise the budget cap and update the daily spend guardrail in `BudgetTracker` accordingly.

3. **[MEDIUM] Update spec/plan to reflect pivot** — The existing spec and plan describe unbuilt components as if they are planned work. Either archive them or update with a clear note that the project scope narrowed to the 3-model prediction market tool.

4. **[MEDIUM] Update CLAUDE.md dependencies section** — Remove h3, searoute, shapely, sentence-transformers, websockets from Key Dependencies since they are not in `pyproject.toml`. Add missing runtime deps: `cryptography>=44.0`, `truthbrush>=0.2`.

5. **[LOW] Verify or update Opus model ID** — Audit whether `claude-opus-4-20250514` still resolves. If not, migrate to `claude-opus-4-8` or the cost-appropriate `claude-sonnet-4-6`.

6. **[LOW] Add graceful degradation for `truth_social.py`** — Wrap the fetch in `brief.py` with a try/except that logs and continues, since `truthbrush` is an unofficial scraper with no stability guarantees.
