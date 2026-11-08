# Parallax Health Check — 2026-11-08

**Status: YELLOW**

No code commits have landed since the 2026-11-07 health check — only documentation (yesterday's health report and tech research). The two HIGH-severity DuckDB single-writer violations identified on 2026-11-05 remain unresolved, now entering their 4th consecutive day without a fix. No regressions introduced.

---

## Summary

The prediction market pipeline is structurally sound (47 test files, ~491 passing) and architecturally stable. The only active risk is the two DB write-path violations: `ops/alerts.py:106` bypasses the `DbWriter` queue from an async context, and `backtest/runner.py` writes directly at lines 290, 308, 329, 356. Neither has been touched. At 4 days unresolved, these have crossed from "newly flagged" into "tracked debt" — if live trading runs against the production DuckDB while either path is active, a `database is locked` error or silent data loss is plausible.

---

## Issues Found

### HIGH — Carry-Over (Unresolved 4 Days)

- **[BUG] DuckDB single-writer violation — `ops/alerts.py:106`**
  `DuckDBAlertSink.send()` is `async` but calls `self.db_conn.execute(INSERT ...)` synchronously, bypassing the `DbWriter` asyncio queue entirely. Any alert fired during a concurrent write from the queue risks a `database is locked` crash.
  **Fix:** Replace `self.db_conn.execute(...)` with `await db_writer.enqueue(sql, params)` and inject `db_writer` into `DuckDBAlertSink.__init__`. Estimated effort: 30 minutes.

- **[BUG] DuckDB single-writer violation — `backtest/runner.py` lines 290, 308, 329, 356**
  `BacktestRunner._persist_backtest_start()`, `_persist_prediction()`, `_update_prediction_resolution()`, and `_finalize_result()` all call `self._conn.execute(INSERT/UPDATE ...)` directly. If invoked while the FastAPI `DbWriter` queue is active, these writes contend for the DuckDB file lock.
  **Fix (option A):** Inject `DbWriter` and make `run()` async so writes route through the queue. **Fix (option B):** Require the CLI backtest path to open a separate DuckDB file, never the production DB. Document which is chosen.

### MEDIUM — Carry-Over

- **[TEST] 7 tests skipped in `test_mapping_policy.py`**
  Skipped with `_PRE_REFACTOR_REASON` ("predates confidence-shrinkage on fair-value estimators"). The post-refactor confidence-shrinkage logic has no direct unit test coverage. Relies on indirect integration test coverage only.

- **[CONFIG] `requires-python = ">=3.11"` in `pyproject.toml`**
  CLAUDE.md and the deployment stack target Python 3.12. The looser lower bound permits `pip install` on 3.11 where `str | None` union syntax and unquoted generic type hints fail without `from __future__ import annotations`. Latent rather than active (CI runs 3.12).

### LOW — Carry-Over

- **[ARCH] `simulation/engine.py` and `simulation/circuit_breaker.py` absent**
  The DES engine and escalation limiter from the Phase 1 plan were never built. `simulation/cascade.py` and `simulation/world_state.py` exist and are tested. This is an intentional scope reduction, not a regression.

- **[ARCH] Dual runtime modules: `db/runtime.py` vs. `ops/runtime.py`**
  Naming is confusing; `db/runtime.py` handles DuckDB path resolution while `ops/runtime.py` handles execution environment config. Renaming `db/runtime.py` → `db/paths.py` would clarify scope without changing behavior.

- **[ARCH] Frontend deps diverge from spec**
  `frontend/package.json` contains only `react`, `react-dom`, `recharts`. The Phase 1 spec required `deck.gl`, `maplibre-gl`, `react-map-gl`, `h3-js`. Absent because the product pivoted from the H3 hex map — intentional, but the spec is stale.

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
| Kalshi/Polymarket integration | No | Yes | ℹ️ (added value) |
| Scoring/calibration/scorecard | No | Yes | ℹ️ (added value) |
| Backtest engine | No | Yes | ℹ️ (added value) |
| Portfolio allocator | No | Yes | ℹ️ (added value) |

---

## Test Coverage

| Category | Status |
|----------|--------|
| Total test files | 47 (unchanged) |
| Passing | ~491 |
| Skipped | 13 (7 mapping_policy, 6 low-risk) |
| Plan tests present | test_schema, test_writer, test_world_state, test_config, test_cascade ✅ |
| Plan tests absent (unbuilt) | test_h3_utils, test_dedup, test_circuit_breaker, test_agent_*, test_auth ℹ️ |

---

## Recommendations

**Priority 1 — Fix this week (data integrity at risk):**
1. **`ops/alerts.py:106`** — Inject `DbWriter`, route INSERT through `await db_writer.enqueue(...)`. ~30 min.
2. **`backtest/runner.py:290,308,329,356`** — Choose option A (inject DbWriter, make `run()` async) or option B (require separate DuckDB file for backtest CLI). Document the decision. ~2 hours.

**Priority 2 — This sprint:**
3. **`pyproject.toml`** — Bump `requires-python` to `>=3.12` to match runtime.
4. **`test_mapping_policy.py`** — Replace the 7 skipped tests with direct assertions against the confidence-shrinkage logic.

**Priority 3 — Backlog:**
5. Archive or update the Phase 1 design spec to reflect the actual prediction-market architecture.
6. Rename `db/runtime.py` → `db/paths.py` for clarity.
