# Parallax Health Check — 2026-11-12

**Status: RED (stalled — 33 days, 0 code commits)**

The three HIGH-severity DuckDB single-writer violations remain unresolved for the **8th consecutive day**. No backend code changes have landed since October 10, 2026 (33 days). All commits since then are health checks and tech research docs only. The project is functionally frozen.

---

## Summary

The core prediction pipeline is functionally intact but static. Three code paths (`ops/alerts.py`, `backtest/runner.py`, `budget/tracker.py`) bypass the `DbWriter` asyncio queue and write directly to the shared DuckDB file — a live crash risk under concurrent access. After 33 days with zero backend development, the project appears to be in a paused state requiring owner attention to either resume active development or formally scope-down.

---

## Issues Found

### HIGH — Unresolved (8 Days, No Code Activity 33 Days)

- **[BUG] DuckDB single-writer violation — `ops/alerts.py:106`**
  `DuckDBAlertSink.send()` calls `self.db_conn.execute(INSERT INTO ops_events ...)` directly, bypassing the `DbWriter` queue. Concurrent alert + queue write will contend for the file lock.
  **Fix:** Inject `DbWriter`, replace direct execute with `await db_writer.enqueue(sql, params)`. ~30 min.

- **[BUG] DuckDB single-writer violation — `backtest/runner.py` lines 290, 308, 329, 356**
  `_persist_backtest_start()`, `_persist_prediction()`, `_update_prediction_resolution()`, `_finalize_result()` all call `self._conn.execute(INSERT/UPDATE ...)` directly.
  **Fix A:** Inject `DbWriter`, make path async. **Fix B:** Require backtest CLI to use a separate DB file (never the production path). ~2 hours.

- **[BUG] DuckDB single-writer violation — `budget/tracker.py:43`**
  `BudgetTracker.record()` calls `self._db_conn.execute(INSERT INTO llm_usage ...)` directly on every LLM call during `cli/brief.py` runs — the most frequently-hit live path.
  **Fix:** Accept `DbWriter` instead of raw connection, make `record()` async. ~30 min.

### MEDIUM — Carry-Over (Unresolved)

- **[TEST] `test_bench_forecast.py` collection error — missing `pandas`**
  `pandas` is `[bench]` optional, not installed by default. `pytest tests/` exits with a collection error.
  **Fix:** Add `pytest.importorskip("pandas")` at top of the file, or add `--ignore` to `pytest.ini`. ~5 min.

- **[TEST] 7 tests skipped in `test_mapping_policy.py`**
  Tagged `_PRE_REFACTOR_REASON` — post-refactor confidence-shrinkage logic has no unit test coverage.

- **[CONFIG] `requires-python = ">=3.11"` but stack targets Python 3.12**
  Permits install on 3.11 where unquoted PEP 604 type hints (`str | None`) fail without `from __future__ import annotations`. Latent, not active.
  **Fix:** Pin to `>=3.12`.

### LOW — Architecture Drift (Intentional Scope Reduction)

- **[ARCH] `simulation/engine.py` and `simulation/circuit_breaker.py` absent**
  The DES engine and escalation limiter from the Phase 1 spec were never built. Product pivoted to prediction-market edge-finder — intentional, not a regression.

- **[ARCH] Dual runtime modules: `db/runtime.py` vs. `ops/runtime.py`**
  Overlapping scope; `db/runtime.py` → `db/paths.py` would clarify.

- **[ARCH] 4 plan-required modules absent: `agents/`, `spatial/`, `api/`, `eval/`**
  Intentional scope reduction. Product implemented as `prediction/`, `scoring/`, `markets/`, `contracts/` instead.

- **[ARCH] Frontend diverges from Phase 1 spec (deck.gl, MapLibre, H3)**
  `frontend/package.json` has only `react`, `react-dom`, `recharts`. Intentional pivot.

---

## Activity Signal

| Period | Backend Code Commits |
|--------|---------------------|
| Oct 10 | Last backend fix (`np.trapezoid`, scikit-learn/numpy deps) |
| Oct 11 – Nov 12 | **0 code commits** — docs + health checks only (33 days) |

---

## Recommendations

1. **Fix the 3 DuckDB write violations** — total estimated effort ~3 hours; prevents a production crash if `cli/brief.py` ever runs while FastAPI is live.
2. **Fix `test_bench_forecast.py` collection** — 5-minute fix restores clean `pytest tests/` output.
3. **Resume development or formally scope-down** — if the product pivot is complete, update CLAUDE.md and the spec to reflect the actual implemented architecture (prediction-market edge-finder, not geopolitical swarm simulator) so future contributors have accurate docs.
