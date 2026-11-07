# Parallax Health Check — 2026-11-07

**Status: YELLOW**

The core prediction market pipeline remains healthy with ~491 tests passing and no new regressions. Two DuckDB single-writer violations first identified on 2026-11-05 remain unresolved and are carried forward as the primary risk.

---

## Summary

The codebase has intentionally evolved from the Phase 1 spec (50-agent geopolitical simulation with H3 spatial visualization) into a leaner prediction market edge-finder. CLAUDE.md accurately describes the actual product. The simulation/cascade infrastructure from the spec is present; the agent swarm, spatial, and eval modules are absent by design. No changes since yesterday's health check.

---

## Issues Found

### HIGH

- **[HIGH][PERSISTENT] DuckDB single-writer violation — `backtest/runner.py` lines 290, 308, 329, 356**
  `BacktestRunner._persist_backtest_start()`, `_persist_prediction()`, `_update_prediction_resolution()`, and `_finalize_result()` all call `self._conn.execute(INSERT/UPDATE ...)` directly. `BacktestRunner.run()` is synchronous and takes the shared DuckDB connection as a constructor argument. If invoked while the FastAPI process's `DbWriter` asyncio queue is active, these writes bypass the queue and risk a `database is locked` conflict. Fix: route all writes through `DbWriter.enqueue()` or run the backtest against a separate DuckDB file.

- **[HIGH][PERSISTENT] DuckDB single-writer violation — `ops/alerts.py` line 106**
  `DuckDBAlertSink.send()` is an `async` method but calls `self.db_conn.execute(INSERT ...)` synchronously, bypassing the `DbWriter` queue entirely. This is a direct write from the async event loop. Fix: replace with `await db_writer.enqueue(sql, params)`.

### MEDIUM

- **[MEDIUM][PERSISTENT] 7 tests skipped in `test_mapping_policy.py`**
  Skipped with `_PRE_REFACTOR_REASON` ("predates confidence-shrinkage on fair-value estimators"). These represent post-refactor behavior in the mapping policy that lacks unit test coverage. The refactored paths are exercised indirectly via integration tests but no direct assertions cover the new confidence-shrinkage logic.

- **[MEDIUM] `requires-python = ">=3.11"` in pyproject.toml**
  CLAUDE.md and the deployment stack target Python 3.12. The looser lower bound allows installation on 3.11, where some typing features used in the codebase (`str | None` union syntax, `dict[str, Any]` in signatures) require `from __future__ import annotations`. Current CI likely runs 3.12 so this is latent rather than active.

### LOW

- **[LOW] `simulation/engine.py` and `simulation/circuit_breaker.py` absent**
  The DES engine and escalation limiter defined in the Phase 1 plan were never built. The cascade rules engine (`simulation/cascade.py`) and world state (`simulation/world_state.py`) exist. If the full simulation loop is a future target, these two files are the gap.

- **[LOW] Dual runtime modules: `db/runtime.py` and `ops/runtime.py`**
  Both exist with different purposes (DuckDB path resolution vs. API/execution environment config). Naming is confusing for newcomers; `db/runtime.py` could be renamed `db/paths.py` to clarify scope.

- **[LOW] Frontend deps diverge from spec**
  `frontend/package.json` has only `react`, `react-dom`, `recharts`. The Phase 1 spec called for `deck.gl`, `maplibre-gl`, `react-map-gl`, `h3-js`. These are absent because the product pivoted away from the H3 hex map — this is intentional but the spec is now stale.

---

## Spec/Plan Consistency

| Area | Spec | Actual | Verdict |
|------|------|--------|---------|
| Prediction pipeline (oil, ceasefire, hormuz) | Yes | Yes | ✅ |
| Cascade rules engine | Yes | Yes | ✅ |
| DuckDB single-writer topology | Yes | Partial — 2 violations | ⚠️ |
| World state + delta tracking | Yes | Yes | ✅ |
| Scenario config YAML | Yes | Yes | ✅ |
| Agent swarm (~50 agents) | Yes | No — intentional pivot | ℹ️ |
| H3 spatial / deck.gl | Yes | No — intentional pivot | ℹ️ |
| DES simulation engine | Yes | Partial — cascade only | ⚠️ |
| Kalshi/Polymarket market integration | No | Yes | ℹ️ (added value) |
| Scoring/calibration/scorecard | No | Yes | ℹ️ (added value) |
| Backtest engine | No | Yes | ℹ️ (added value) |
| Portfolio allocator | No | Yes | ℹ️ (added value) |

---

## Test Coverage

| Category | Status |
|----------|--------|
| Total passing | ~491 |
| Skipped | 13 (7 mapping_policy, rest low-risk) |
| Plan tests present | test_schema, test_writer, test_world_state, test_config, test_cascade ✅ |
| Plan tests absent (unbuilt modules) | test_h3_utils, test_dedup, test_circuit_breaker, test_agent_*, test_auth ℹ️ |
| Actual product coverage | Comprehensive — brief, scoring, calibration, divergence, markets, backtest all tested |

---

## Recommendations

1. **Fix `ops/alerts.py` line 106** (30-min effort) — replace `self.db_conn.execute(...)` with an `await db_writer.enqueue(...)` call. This is the simpler of the two violations.
2. **Decide on `BacktestRunner` write strategy** — either inject `DbWriter` and make `run()` async, or document that the backtest CLI must open a separate DuckDB file (not the live production DB).
3. **Fix the `requires-python` lower bound** — bump to `>=3.12` to match the runtime.
4. **Update the spec** — the Phase 1 design doc no longer matches the product. Either archive it or update it to describe the actual prediction-market architecture to avoid confusion for future contributors.
