# Parallax Health Check — 2026-11-09

**Status: YELLOW**

No code commits since the 2026-11-08 health check — only a tech research document landed yesterday. The two HIGH-severity DuckDB single-writer violations identified on 2026-11-05 remain unresolved, now entering their **5th consecutive day** without a fix. A new MEDIUM issue surfaced today: `test_bench_forecast.py` fails to collect because `pandas` is not installed in the test environment, breaking `pytest tests/` with a collection error unless that file is explicitly excluded.

---

## Summary

The core prediction pipeline remains structurally sound. 473 tests pass (13 skipped) when the bench test file is excluded. The unresolved DuckDB write-path violations in `ops/alerts.py` and `backtest/runner.py` continue to be the primary risk — if live trading runs against the production DuckDB file while either path is active, a `database is locked` error or silent data loss is plausible.

---

## Issues Found

### HIGH — Carry-Over (Unresolved 5 Days)

- **[BUG] DuckDB single-writer violation — `ops/alerts.py:108`**
  `DuckDBAlertSink.send()` is `async` but calls `self.db_conn.execute(INSERT INTO ops_events ...)` synchronously, bypassing the `DbWriter` asyncio queue entirely. Any alert fired during a concurrent write from the queue risks a `database is locked` crash.
  **Fix:** Inject `DbWriter` into `DuckDBAlertSink.__init__`, replace `self.db_conn.execute(...)` with `await db_writer.enqueue(sql, params)`. Estimated effort: 30 min.

- **[BUG] DuckDB single-writer violation — `backtest/runner.py` lines 292, 310, 331, 358**
  `BacktestRunner._persist_backtest_start()`, `_persist_prediction()`, `_update_prediction_resolution()`, and `_finalize_result()` all call `self._conn.execute(INSERT/UPDATE ...)` directly. If invoked while the FastAPI `DbWriter` queue is active, these writes contend for the DuckDB file lock.
  **Fix (option A):** Inject `DbWriter`, make `run()` async, route all writes through the queue. **Fix (option B):** Require the CLI backtest path to open a separate DuckDB file (never the production DB). ~2 hours either way.

### MEDIUM — New

- **[TEST] `test_bench_forecast.py` fails collection — missing `pandas`**
  Running `pytest tests/` exits with a collection error at `test_bench_forecast.py` because `pandas` is a `[bench]` optional dependency not installed in the standard dev environment. This breaks CI if `pytest tests/` is run without the bench extras or an explicit `--ignore`. Previous runs may have been shielded by a pre-cached `pandas` install.
  **Fix:** Either add `--ignore=tests/test_bench_forecast.py` to `pytest.ini`'s `addopts`, or gate the import in the test with `pytest.importorskip("pandas")`. ~5 min.

### MEDIUM — Carry-Over

- **[TEST] 7 tests skipped in `test_mapping_policy.py`**
  Skipped with `_PRE_REFACTOR_REASON` ("predates confidence-shrinkage on fair-value estimators"). The post-refactor confidence-shrinkage logic has no direct unit test coverage.

- **[CONFIG] `requires-python = ">=3.11"` in `pyproject.toml`**
  CLAUDE.md and the deployment stack target Python 3.12. The looser lower bound permits `pip install` on 3.11 where `str | None` union syntax and unquoted generic type hints fail without `from __future__ import annotations`. Latent rather than active (CI runs 3.12).

### LOW — Carry-Over

- **[ARCH] `simulation/engine.py` and `simulation/circuit_breaker.py` absent**
  The DES engine and escalation limiter from the Phase 1 plan were never built. `simulation/cascade.py` and `simulation/world_state.py` exist and are tested. This is an intentional scope reduction (product pivoted to prediction-market edge-finder), not a regression.

- **[ARCH] Dual runtime modules: `db/runtime.py` vs. `ops/runtime.py`**
  `db/runtime.py` handles DuckDB path resolution; `ops/runtime.py` handles execution environment config. Renaming `db/runtime.py` → `db/paths.py` would clarify scope without changing behavior.

- **[ARCH] Frontend deps diverge from spec**
  `frontend/package.json` contains only `react`, `react-dom`, `recharts`. The Phase 1 spec required `deck.gl`, `maplibre-gl`, `react-map-gl`, `h3-js`. Absent because the product pivoted from the H3 hex map — intentional, spec is stale.

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
| Kalshi/Polymarket integration | No (spec) | Yes | ℹ️ (added value) |
| Scoring/calibration/scorecard | No (spec) | Yes | ℹ️ (added value) |
| Backtest engine | No (spec) | Yes | ℹ️ (added value) |
| Portfolio allocator | No (spec) | Yes | ℹ️ (added value) |

---

## Test Coverage

| Category | Status |
|----------|--------|
| Total test files | 46 |
| Passing | 473 |
| Skipped | 13 (7 mapping_policy, 6 low-risk) |
| Collection errors | 1 (`test_bench_forecast.py` — missing `pandas`) |
| Plan tests present | test_schema, test_writer, test_world_state, test_config, test_cascade ✅ |
| Plan tests absent (unbuilt) | test_h3_utils, test_dedup, test_circuit_breaker, test_agent_*, test_auth ℹ️ |

---

## Recommendations

**Priority 1 — Fix immediately (data integrity at risk, now 5 days overdue):**
1. **`ops/alerts.py:108`** — Inject `DbWriter`, route INSERT through `await db_writer.enqueue(...)`. ~30 min.
2. **`backtest/runner.py:292,310,331,358`** — Choose fix option A or B (see above). ~2 hours.

**Priority 2 — Fix this sprint:**
3. **`test_bench_forecast.py`** — Add `pytest.importorskip("pandas")` or `--ignore` in `pytest.ini`. ~5 min.
4. **`pyproject.toml`** — Bump `requires-python` to `>=3.12` to match runtime.
5. **`test_mapping_policy.py`** — Replace the 7 skipped tests with direct assertions against the confidence-shrinkage logic.

**Priority 3 — Backlog:**
6. Archive or update the Phase 1 design spec to reflect the actual prediction-market architecture.
7. Rename `db/runtime.py` → `db/paths.py` for clarity.
