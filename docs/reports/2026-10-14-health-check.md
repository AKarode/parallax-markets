# Parallax Health Check — 2026-10-14

**Status: YELLOW**

No code changes since yesterday's report (only a tech research scout commit). All critical issues from 2026-10-13 remain unresolved: the `scorecard.py` `DATE()` DuckDB incompatibility breaking 18 tests, the `np.trapz` NumPy 2.x breakage, the `sklearn` missing-in-production issue, and the `DbWriter` single-writer abstraction that is defined but bypassed by every production write path. Architecture drift (absent `agents/`, `eval/`, `api/`, `spatial/` modules) continues at the same level.

---

## Issues Found

### CRITICAL

- **[CRITICAL] `scoring/scorecard.py` — `DATE()` not a function in DuckDB 1.2.x — 18 test failures [UNRESOLVED, DAY 2].**
  Lines 47, 58, 70, 84, 143, 167, 187, 206, 222, 255 all use `WHERE DATE(col) = ?`. DuckDB 1.2.x treats `DATE` as a type cast, not a scalar function. Correct syntax: `CAST(col AS DATE)`. Breaks every `TestScorecardComputation`, `TestOpsMetrics`, `TestDataQualityMetrics`, and `TestScorecardIdempotent` test. The `--scorecard` CLI flag is non-functional in any environment running DuckDB 1.2.x.
  **Fix:** Replace all `DATE(col)` with `CAST(col AS DATE)` in `scoring/scorecard.py`.

- **[CRITICAL] DuckDB single-writer constraint violated across all production write paths — `DbWriter` is dead code [UNRESOLVED, DAY 6].**
  `db/writer.py` defines a correct asyncio.Queue-based single-writer. It is never instantiated in `main.py` (no `DbWriter(conn)`, no `asyncio.create_task(writer.run())`). Every module bypasses it:
  - `ops/alerts.py:106` — INSERT into `ops_events`
  - `budget/tracker.py:43` — INSERT into `llm_usage`
  - `cli/brief.py:130, 149, 433` — INSERT/UPDATE `runs`, INSERT `market_prices`
  - `scoring/ledger.py:225, 256` — INSERT/UPDATE `signal_ledger`
  - `scoring/tracker.py:460, 516, 674, 713, 746` — INSERT/UPDATE `trade_positions`, `trade_orders`, `trade_fills`
  - `scoring/prediction_log.py:81` — INSERT `prediction_log`
  - `scoring/resolution.py:62, 126` — UPDATE `signal_ledger`, `trade_positions`
  - `backtest/runner.py:292, 308, 329, 356` — INSERT/UPDATE `backtest_runs`, `backtest_predictions`
  - `contracts/registry.py:106, 116, 199` — DELETE/INSERT/UPDATE contract tables
  - `ingestion/crisis_ingester.py:81` — INSERT `crisis_events`
  The worst-case risk is `database is locked` under concurrent async writes in the FastAPI process. Current CLI-based usage is lower risk (sequential), but `ops/alerts.py` and `budget/tracker.py` fire from the async request path.

### HIGH

- **[HIGH] `np.trapz` removed in NumPy 2.x — `scoring/selective.py:106` [UNRESOLVED, DAY 3].**
  `np.trapz(risk, coverage)` raises `AttributeError` on NumPy ≥ 2.0 (installed: 2.5.3). Breaks `test_selective.py::test_risk_coverage_perfect_ranking` and the selective-trading AUC path in production.
  **Fix:** Replace `np.trapz` with `np.trapezoid` at `selective.py:106`.

- **[HIGH] `sklearn` import failure without bench extras — `scoring/recalibrators.py:111, 145` [UNRESOLVED, DAY 3].**
  `IsotonicRecalibrator.fit()` and `PlattRecalibrator.fit()` do lazy `from sklearn.*` imports. `scikit-learn` is only in the `[bench]` optional group. Any production caller without bench extras hits `ModuleNotFoundError` at runtime; 4 `test_recalibrators.py` tests fail.
  **Fix:** Add `scikit-learn` to core deps, or add `try/except ImportError` with a clear `raise RuntimeError("Install parallax[bench]")` message.

- **[HIGH] `test_phase1_critical.py::TestBackfillResolutions::test_skips_resolutions_before_sim_date` — regression [UNRESOLVED, DAY 2].**
  `result.status == 'failed'` where `'completed'` expected (line 223). `BacktestRunner` is marking a run that should succeed as failed. The resolution backfill date-range guard has a logic error introduced in a recent commit.

- **[HIGH] Architecture drift — `agents/`, `eval/`, `api/`, `spatial/` subpackages absent — ongoing.**
  The Phase 1 spec's 50-agent LLM swarm, eval framework, H3 spatial model, WebSocket API, and auth layer are unbuilt. `simulation/engine.py` and `simulation/circuit_breaker.py` are absent. The frontend has no H3 hex map, no agent feed, no WebSocket — it is a polling-based prediction-market dashboard. ~10 schema tables (`agent_memory`, `agent_prompts`, `decisions`, `world_state_delta`, `predictions`, `curated_events`, `raw_gdelt`, `eval_results`, `simulation_state`) exist in schema but are orphaned with no corresponding code.

### MEDIUM

- **[MEDIUM] `pyproject.toml` missing core dependencies [UNRESOLVED].**
  `h3`, `searoute`, `shapely`, `sentence-transformers`, `google-cloud-bigquery` are listed in the spec and CLAUDE.md tech stack but absent from `[project].dependencies` (and absent from the codebase — spatial and dedup modules were never built). `scikit-learn` used in production code (`recalibrators.py`) is only in `[bench]` extras.

- **[MEDIUM] Frontend components diverged from spec [ONGOING].**
  Spec calls for `HexMap.tsx`, `AgentFeed.tsx`, `LiveIndicators.tsx`, `Timeline.tsx`, `PredictionCards.tsx`, `HexPopover.tsx`, `useWebSocket.ts`, `useHexData.ts`. None exist. Actual components (`MarketsTable`, `ModelCards`, `KpiBar`, `PortfolioPanel`, etc.) reflect a prediction-market dashboard. Frontend has `deck.gl`, `maplibre-gl`, `react-map-gl`, `h3-js` installed but unused (dead weight ~4MB).

### LOW

- **[LOW] `simulation/engine.py` and `simulation/circuit_breaker.py` absent.**
  Plan Tasks 7 and 8 were never executed. `ScenarioConfig` has `max_escalation_per_tick`, `escalation_cooldown_ticks`, `exogenous_shock_goldstein_threshold` fields that configure a circuit breaker that doesn't exist. Cascade can spike prices without escalation throttling.

- **[LOW] `db/queries.py` (plan Task 2) was never created.**
  Read-only query helpers are scattered inline. Not a blocking issue since reads are fine with direct `conn.execute()`.

---

## Test Summary

*Test runner not available in this environment (pytest not installed in active Python). Counts from yesterday's run:*

| Result | Count (2026-10-13) |
|--------|--------------------|
| Passed | 470 |
| Failed | 21 |
| Skipped | 13 |

No code changes since that run; counts expected to be identical.

---

## Recommendations (Priority Order)

1. **Fix `scorecard.py` `DATE()` → `CAST(col AS DATE)` (10 occurrences)** — restores 18 tests, unblocks the `--scorecard` CLI.
2. **Fix `selective.py:106` `np.trapz` → `np.trapezoid`** — one-line change, restores selective-trading AUC.
3. **Add `scikit-learn` to core deps or guard import in `recalibrators.py`** — prevents silent production `ModuleNotFoundError`.
4. **Investigate `BacktestRunner` date-range guard regression** — `test_skips_resolutions_before_sim_date` was passing recently; check `backtest/runner.py` recent changes.
5. **Resolve `DbWriter` ambiguity** — either wire it into `main.py` lifespan and refactor write modules to accept a writer, or remove it and document that the current architecture is single-process-sequential (and why that's acceptable). The dead abstraction creates misleading code.
6. **Prune orphaned schema tables** — either remove `agent_memory`, `agent_prompts`, `decisions`, `world_state_delta`, `predictions`, `curated_events`, `raw_gdelt`, `eval_results`, `simulation_state` from `schema.py`, or add a comment marking them as reserved for a future phase.
