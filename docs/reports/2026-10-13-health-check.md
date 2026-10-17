# Parallax Health Check — 2026-10-13

**Status: YELLOW**

Test failures increased from 2 yesterday to 21 today, primarily due to a DuckDB 1.2.x `DATE()` function incompatibility in `scoring/scorecard.py` that broke all 18 scorecard tests. The `np.trapz` and `sklearn` failures from yesterday remain unresolved. The DuckDB single-writer constraint violation across 11 production files continues with no remediation progress.

---

## Issues Found

### CRITICAL

- **[CRITICAL] `scoring/scorecard.py` — `DATE()` not a function in DuckDB 1.2.x — 18 new test failures [REGRESSION].**
  All `_compute_signal_quality`, `_compute_brier_metrics`, and related helpers use `WHERE DATE(resolved_at) = ?` (lines 44, 58, 70, 84, 143). In DuckDB 1.2.x, `DATE` is a type cast, not a scalar function — the correct syntax is `CAST(resolved_at AS DATE)` or `strftime(resolved_at, '%Y-%m-%d')`. This breaks every scorecard test class (`TestScorecardComputation`, `TestOpsMetrics`, `TestDataQualityMetrics`, `TestScorecardIdempotent`). The `--scorecard` CLI flag is non-functional in any environment running DuckDB 1.2.x.
  Fix: Replace all `DATE(col)` with `CAST(col AS DATE)` in `scorecard.py`.

- **[CRITICAL] DuckDB single-writer constraint violated across 11 production files — unresolved for 5 days.**
  The `DbWriter` asyncio.Queue pattern exists in `db/writer.py` but is bypassed by every write path:
  - `ops/alerts.py:106` — direct INSERT into `ops_events`
  - `budget/tracker.py:43` — direct INSERT into `llm_usage`
  - `cli/brief.py:130,149,431` — direct writes from async context
  - `backtest/runner.py:290,308,329,356` — direct writes
  - `scoring/` modules (ledger, prediction_log, resolution, scorecard, tracker) — all bypass queue
  Any concurrent async write in the live server can cause `database is locked` errors under load.

### HIGH

- **[HIGH] `np.trapz` removed in NumPy 2.x — `scoring/selective.py:106` — ongoing [DAY 2].**
  `np.trapz(risk, coverage)` raises `AttributeError` on NumPy ≥ 2.0 (installed: 2.5.3). Breaks `test_selective.py::test_risk_coverage_perfect_ranking` and the selective-trading AUC path in production.
  Fix: replace `np.trapz` with `np.trapezoid` at `selective.py:106`.

- **[HIGH] `sklearn` import in `scoring/recalibrators.py` fails without bench extras — ongoing [DAY 2].**
  `IsotonicRecalibrator.fit()` and `PlattRecalibrator.fit()` do lazy `from sklearn.*` imports. `scikit-learn` is only in the `[bench]` optional group. Any production caller without bench extras installed hits `ModuleNotFoundError` at runtime; 4 `test_recalibrators.py` tests fail.
  Fix: add `scikit-learn` to core deps, or add a `try/except ImportError` with a clear message.

- **[HIGH] `test_phase1_critical.py::TestBackfillResolutions::test_skips_resolutions_before_sim_date` — new regression.**
  `result.status == 'failed'` where `'completed'` is expected (line 223). The `BacktestRunner` is marking a run that should succeed as failed. This indicates a logic error in the resolution backfill date-range guard introduced since the last green run.

- **[HIGH] Architecture drift — `agents/`, `eval/`, `api/`, `spatial/` subpackages absent — ongoing.**
  The Phase 1 spec's 50-agent LLM swarm, eval framework, H3 spatial model, and WebSocket API are unbuilt. Tables `agent_memory`, `agent_prompts`, `decisions`, `world_state_delta`, `eval_results` exist in schema but hold no data. `simulation/engine.py` and `simulation/circuit_breaker.py` are absent. The frontend has no H3 hex map, no agent feed, no WebSocket — it is a polling-based market dashboard, not the spec's three-panel geospatial interface.

### MEDIUM

- **[MEDIUM] `pyproject.toml` missing key dependencies.**
  - `h3`, `searoute`, `shapely`, `sentence-transformers`, `google-cloud-bigquery` are in the spec and CLAUDE.md but absent from `[project].dependencies` (and from the codebase — the spatial and dedup modules were never built).
  - `scikit-learn` used in production code (`recalibrators.py`) but only in `[bench]` extras.

- **[MEDIUM] `frontend/` components diverged from spec.**
  The spec calls for `HexMap.tsx`, `AgentFeed.tsx`, `LiveIndicators.tsx`, `Timeline.tsx`, `PredictionCards.tsx`, `HexPopover.tsx`, `useWebSocket.ts`, `useHexData.ts`. None exist. The actual components (`MarketsTable`, `ModelCards`, `KpiBar`, `PortfolioPanel`, etc.) reflect a prediction-market dashboard, not the H3 geospatial interface.

### LOW

- **[LOW] `simulation/engine.py` and `simulation/circuit_breaker.py` absent despite tests passing for related modules.**
  `test_engine.py` and `test_circuit_breaker.py` (from the plan) do not exist. The plan's Tasks 7 and 8 were never executed.

---

## Test Summary

| Result | Count |
|--------|-------|
| Passed | 470 |
| Failed | 21 |
| Skipped | 13 |

**New failures vs yesterday:** +19 (scorecard regression + backtest regression). `np.trapz` and `sklearn` failures carry over from yesterday.

---

## Recommendations

1. **Fix `scorecard.py` immediately** — replace all `DATE(col)` with `CAST(col AS DATE)`. 18 tests fail because of this single pattern. The `--scorecard` CLI is broken in production.
2. **Fix `selective.py:106`** — `np.trapz` → `np.trapezoid`. One-line change, restores selective-trading AUC.
3. **Investigate `BacktestRunner` regression** — `test_skips_resolutions_before_sim_date` was passing before; a recent commit broke the date-range guard. Check git blame on `backtest/runner.py`.
4. **Add `scikit-learn` to core deps** or guard the import in `recalibrators.py` with a clear `ImportError` message.
5. **Address single-writer violations** — at minimum, add a note in CLAUDE.md that `brief.py` and `backtest/` run synchronously (single-process, no concurrency) so violations there are low-risk, but `ops/alerts.py` and `budget/tracker.py` fire in the async FastAPI context and must route through `DbWriter`.
