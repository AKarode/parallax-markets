# Parallax Health Check — 2026-09-22

**Status: YELLOW**

## Summary

No code has been committed to `backend/src/` since **2026-08-26** (27 days). All bugs flagged in prior reports remain open with no fixes. Today's test run confirms 433 passed, 13 skipped — core suite is green — but 4 bench test files still fail to collect due to missing `numpy`/`pandas` in the `[dev]` extras group. The project continues in a documentation/observation loop with no active development.

---

## Issues Found

### HIGH Severity — Open 10+ Days (No Change)

- **[BUG] `np.trapz` removed in NumPy 2.x** (`scoring/selective.py:106`)
  `np.trapz(risk, coverage)` raises `AttributeError` in NumPy ≥ 2.0. Replacement: `np.trapezoid`. Latent until `pip install ".[bench]"` is run.
  **Fix:** One-line change: `s/np.trapz/np.trapezoid/` at line 106.

- **[BUG] DuckDB single-writer violation** (`ops/alerts.py:106`)
  `DuckDBAlertSink.send()` calls `conn.execute(INSERT INTO ops_events …)` directly from an `async` method, bypassing the `DbWriter` asyncio.Queue. Risks `database is locked` under live-pipeline concurrency.
  **Fix:** Inject `DbWriter` and replace direct `conn.execute` with `await self._db_writer.enqueue(...)`.

- **[INFRA] 4 bench test files fail to collect** (`test_bench_forecast.py`, `test_calibration_metrics.py`, `test_recalibrators.py`, `test_selective.py`)
  Raise `ModuleNotFoundError` for `pandas`/`numpy`/`sklearn` on plain `pip install -e ".[dev]"`. Blocks clean `pytest tests/` run.
  **Fix:** Add `pytest.importorskip("pandas")` / `pytest.importorskip("numpy")` at top of each affected file.

- **[BUG] Deconfliction DB/memory split** (`cli/brief.py:491,714`)
  `ledger.record_signal()` persists signals before `_deconflict_oil_signals()` mutates them in-memory. The in-memory `.signal = "HOLD"` mutation never writes back to DuckDB. Paper trades may double-enter correlated oil contracts.
  **Fix:** Move deconfliction before `record_signal()` loop, or issue an `UPDATE signal_ledger SET signal = 'HOLD' WHERE signal_id = ?` after mutation.

- **[BUG] TypeError crash on NULL win-rate** (`scoring/ledger.py:283`)
  `int(row[1])` raises `TypeError` when `model_was_correct` is NULL for all rows (before first resolution cycle with 5+ signals).
  **Fix:** Change `int(row[1])` → `int(row[1] or 0)`.

### MEDIUM Severity — Open Carry-Over

- **[BUG] `update_execution()` COALESCE never updates** (`scoring/ledger.py:259–264`)
  `COALESCE(?, trade_id)` receives `None` as first arg, so FK fields are write-once. P&L tracking sync is broken.
  **Fix:** Replace `COALESCE(?, field)` with `CASE WHEN ? IS NOT NULL THEN ? ELSE field END`.

- **[DEP] `streamlit` and `plotly` missing from `pyproject.toml`** (`dashboard/app.py:16–17`)
  Both imported at module-level but absent from all dependency groups. Fresh install raises `ModuleNotFoundError`.
  **Fix:** Add `dashboard = ["streamlit>=1.36", "plotly>=5.22"]` optional group.

- **[BUG] `budget/tracker.py:43` — direct DuckDB write** bypasses `DbWriter` queue. Risks locking on concurrent async runs. Same pattern in `scoring/tracker.py` and `scoring/ledger.py`.

- **[PERF] New `httpx.AsyncClient` per Kalshi request** (`markets/kalshi.py:154`)
  ~12 requests × new TCP+TLS handshake per brief run ≈ 500ms wasted.
  **Fix:** Persistent `AsyncClient` in `__init__`, closed in FastAPI lifespan.

- **[CONFIG] Validation window dates expired** (`portfolio/simulator.py:15–16`)
  `VALIDATION_END = date(2026, 4, 21)` is 154 days past. `days_remaining` always returns 0.
  **Fix:** Update to a rolling 30-day window relative to `date.today()`.

- **[CONFIG] `PRICE_ELASTICITY` and `INSURANCE_THREAT_MULTIPLIER` hardcoded** (`simulation/cascade.py:35,38`)
  Both bypass `ScenarioConfig`. Scenario comparisons silently ignore YAML overrides.

---

## Test Run (2026-09-22)

```
433 passed, 13 skipped in 104.83s
4 collection errors (bench tests — numpy/pandas not installed via [dev])
```

---

## Architecture Drift Summary

The project has fully pivoted from the original Phase 1 spec (50-agent swarm + H3 hex map) to a focused prediction-market edge-finder. This is intentional and well-documented. Key permanent deviations:

- `agents/`, `spatial/`, `eval/` modules from the spec were never built (by design).
- Frontend is Recharts-based, not deck.gl/H3/MapLibre.
- Runtime deps are leaner: no `h3`, `sentence-transformers`, `searoute`, `shapely`.
- Schema is 23 tables (vs 10 in spec) — appropriate growth for the trading pipeline.

---

## Recommendations

1. **Address the 5 HIGH-severity bugs** — all are trivial 1–5 line fixes that have been open 10+ days.
2. **Add `pytest.importorskip` guards** to the 4 bench test files so CI stays clean.
3. **Update validation window dates** in `portfolio/simulator.py` to avoid misleading metrics.
4. **Commit at least one code change** to reset the 27-day stagnation streak and confirm the pipeline is still actively maintained.
