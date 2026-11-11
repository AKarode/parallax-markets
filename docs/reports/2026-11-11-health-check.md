# Parallax Health Check — 2026-11-11

**Status: YELLOW → RED (escalating)**

No code commits have landed since October 10, 2026 — over a month of documentation-only activity. The three HIGH-severity DuckDB single-writer violations identified on November 5 are now on **day 7 without a fix**. The last actual backend code change was `fix: resolve HIGH bugs — np.trapezoid + scikit-learn/numpy to base deps` (Oct 10). All commits from Oct 11 onward have been health checks and tech research docs only.

---

## Summary

The core prediction pipeline remains functionally intact but completely static. The primary risk is the accumulating DuckDB write-path violations: three separate code paths (`ops/alerts.py`, `backtest/runner.py`, `budget/tracker.py`) bypass the `DbWriter` asyncio queue and write directly to the shared DuckDB file. If any of these paths fire concurrently with the main queue-driven writer, a `database is locked` crash or silent data loss is likely. Seven consecutive days of non-resolution — now spanning a month of zero backend development — signals that this project may be in a maintenance-only or paused state.

---

## Issues Found

### HIGH — Carry-Over + Escalating (Unresolved 7 Days, No Code Activity 32 Days)

- **[BUG] DuckDB single-writer violation — `ops/alerts.py:106-108`**
  `DuckDBAlertSink.send()` calls `self.db_conn.execute(INSERT INTO ops_events ...)` directly, bypassing the `DbWriter` queue. Any alert fired while the queue is processing will contend for the DuckDB file lock.
  **Fix:** Inject `DbWriter` into `DuckDBAlertSink.__init__`, replace direct execute with `await db_writer.enqueue(sql, params)`. ~30 min.

- **[BUG] DuckDB single-writer violation — `backtest/runner.py` lines 290, 308, 329, 356**
  `_persist_backtest_start()`, `_persist_prediction()`, `_update_prediction_resolution()`, and `_finalize_result()` all call `self._conn.execute(INSERT/UPDATE ...)` directly. If the CLI backtest path ever opens the production DuckDB file while FastAPI is running, these contend.
  **Fix A:** Inject `DbWriter`, make the backtest run path async. **Fix B:** Require backtest CLI to always use a separate DB file, never the production path. ~2 hours.

- **[BUG] DuckDB single-writer violation — `budget/tracker.py:43-55`**
  `BudgetTracker.record()` calls `self._db_conn.execute(INSERT INTO llm_usage ...)` directly when a `db_conn` is provided. This path is active on every live LLM call during `cli/brief.py` runs.
  **Fix:** Accept `DbWriter` instead of a raw connection; replace `self._db_conn.execute(...)` with `await db_writer.enqueue(sql, params)` and make `record()` async. ~30 min.

### MEDIUM — Carry-Over

- **[TEST] `test_bench_forecast.py` fails collection — missing `pandas`**
  `pandas` is a `[bench]` optional dependency not installed in the standard dev environment. Running `pytest tests/` exits with a collection error. **Fix:** Add `pytest.importorskip("pandas")` at the top of `test_bench_forecast.py`, or add `--ignore=tests/test_bench_forecast.py` to `pytest.ini` `addopts`. ~5 min.

- **[TEST] 7 tests skipped in `test_mapping_policy.py`**
  Skipped with `_PRE_REFACTOR_REASON` ("predates confidence-shrinkage on fair-value estimators"). The post-refactor confidence-shrinkage logic remains without direct unit test coverage.

- **[CONFIG] `requires-python = ">=3.11"` in `pyproject.toml`**
  CLAUDE.md and the deployment stack target Python 3.12. The `>=3.11` lower bound permits installation on 3.11 where `str | None` syntax and unquoted PEP 604 type hints fail without `from __future__ import annotations`. Latent rather than active (CI runs 3.12). **Fix:** Pin `requires-python = ">=3.12"`.

### LOW — Carry-Over

- **[ARCH] `simulation/engine.py` and `simulation/circuit_breaker.py` absent**
  The DES engine and escalation limiter from the Phase 1 spec were never built. `simulation/cascade.py` and `simulation/world_state.py` exist and are tested. This is an intentional scope reduction (product pivoted to prediction-market edge-finder), not a regression.

- **[ARCH] Dual runtime modules: `db/runtime.py` vs. `ops/runtime.py`**
  `db/runtime.py` handles DuckDB path resolution; `ops/runtime.py` handles execution environment config. Renaming `db/runtime.py` → `db/paths.py` would clarify scope without changing behavior.

- **[ARCH] Frontend deps diverge from spec**
  `frontend/package.json` contains only `react`, `react-dom`, `recharts`. The Phase 1 spec required `deck.gl`, `maplibre-gl`, `react-map-gl`, `h3-js`. Absent because the product pivoted from the H3 hex map — intentional, spec is stale.

---

## Activity Signal

| Period | Backend Code Commits |
|--------|---------------------|
| Oct 10 | Last backend fix (`np.trapezoid`, `scikit-learn`) |
| Oct 11–Nov 11 | **0 code commits** — docs only (32 days) |

This is the longest zero-code streak since the project's inception. Combined with the escalating DuckDB violations, the project appears paused or the team is working off a fork not reflected in `main`.

---

## Spec/Plan Consistency

| Area | Spec | Actual | Verdict |
|------|------|--------|---------|
| Prediction pipeline (oil, ceasefire, hormuz) | Yes | Yes | ✅ |
| Cascade rules engine | Yes | Yes | ✅ |
| DuckDB single-writer topology | Yes | Partial — 3 violations | ⚠️ |
| Agent swarm (registry, router, runner) | Yes | No — intentional pivot | ℹ️ |
| H3 spatial layer | Yes | No — intentional pivot | ℹ️ |
| Eval framework (scoring, predictions) | Yes | Partially (ledger, calibration) | ⚠️ |
| Budget tracker | Yes | Yes (but write violation) | ⚠️ |
| Paper trading (Kalshi demo) | Yes | Yes | ✅ |

---

## Dependency Audit

No dependency changes since October 10. Findings from prior reports unchanged:

| Dependency | Spec requires | Status |
|-----------|---------------|--------|
| `h3>=4.1` | H3 spatial utilities | Missing (intentional pivot) |
| `searoute>=1.3` | Shipping route visualization | Missing (intentional) |
| `shapely>=2.0` | Geometric operations | Missing (intentional) |
| `sentence-transformers>=3.4` | GDELT semantic dedup | Missing (GDELT dedup not built) |
| `websockets>=14.0` | WebSocket server | Missing (FastAPI/uvicorn handles WS) |
| `google-cloud-bigquery>=3.27` | GDELT via BigQuery | Missing (using GDELT DOC API instead) |

---

## Recommendations

**Immediate (before next trading session):**
1. Fix `budget/tracker.py` direct-write — fires on every LLM call during live runs (30 min)
2. Fix `ops/alerts.py` direct-write — fires on every alert condition (30 min)
3. Fix `test_bench_forecast.py` collection error — prevents running full test suite (5 min)

**This week:**
4. Fix `backtest/runner.py` write violations — either inject `DbWriter` or enforce a separate DB file for backtest CLI (2 hours)
5. Pin `requires-python = ">=3.12"` in `pyproject.toml` (5 min)
6. Write unit tests for confidence-shrinkage logic to replace the 7 skipped mapping_policy tests

**Investigation needed:**
7. Confirm whether active development is continuing on a different branch or fork — 32 days with no code commits to `main` while health checks continue suggests either a paused project or a detached workflow.
