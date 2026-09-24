# Parallax Health Check — 2026-09-23

**Status: YELLOW**

## Summary

No code has been committed to `backend/src/` since **2026-08-26** — now 28 days of stagnation. The core test suite remains green (433 passed, 13 skipped) but 4 bench test files still fail at collection time due to missing `numpy`/`pandas` in the `[dev]` extras group. All bugs from prior reports remain open and unaddressed; the project is in a documentation-only loop with no active development.

---

## Issues Found

### HIGH Severity — Unchanged Since Prior Reports

- **[BUG] `np.trapz` removed in NumPy 2.x** (`scoring/selective.py:106`)
  `np.trapz(risk, coverage)` raises `AttributeError` in NumPy ≥ 2.0. Fix: `np.trapezoid`. Latent until `pip install ".[bench]"` is run.

- **[BUG] DuckDB single-writer violation** (`ops/alerts.py:106`, `budget/tracker.py:43`, `scoring/tracker.py`, `scoring/ledger.py`)
  Multiple write sites call `conn.execute(INSERT/UPDATE ...)` directly on the raw DuckDB connection, bypassing the `DbWriter` asyncio queue. Risks `database is locked` or silent corruption under concurrent CLI + API access. `DbWriter` is already implemented — callers just need to be wired to it.

- **[BUG] Deconfliction/DB split** (`cli/brief.py:699,714`)
  `ledger.record_signal()` persists signals to DuckDB inside the loop (line 699), then `_deconflict_oil_signals()` mutates the in-memory signal list (line 714). The suppressed signals remain in DuckDB as `BUY_YES`/`BUY_NO` rather than `HOLD`. Paper trades can double-enter correlated oil contracts. Fix: move deconfliction before the `record_signal()` loop, or issue an `UPDATE signal_ledger SET signal = 'HOLD' WHERE signal_id = ?` after mutation.

- **[BUG] TypeError crash on NULL win-rate** (`scoring/ledger.py:283`)
  `int(row[1])` raises `TypeError` when `model_was_correct` is NULL for all rows (before first resolution cycle reaches 5 signals). Fix: `int(row[1] or 0)`.

- **[INFRA] 4 bench test files fail to collect** (`test_bench_forecast.py`, `test_calibration_metrics.py`, `test_recalibrators.py`, `test_selective.py`)
  All raise `ModuleNotFoundError` for `pandas`/`numpy`/`sklearn` on plain `pip install -e ".[dev]"`. `pytest backend/tests/` is broken for new contributors without the `[bench]` extras. Fix: add `pytest.importorskip("numpy")` / `pytest.importorskip("pandas")` guard at top of each affected file.

### MEDIUM Severity — Unchanged

- **[BUG] `update_execution()` COALESCE never updates** (`scoring/ledger.py:259–264`)
  `COALESCE(?, field)` receives `None` as first arg, so FK fields `trade_id`, `position_id`, `entry_order_id` are write-once. P&L tracking sync is broken. Fix: replace with `CASE WHEN ? IS NOT NULL THEN ? ELSE field END`.

- **[DEP] `streamlit` and `plotly` missing from `pyproject.toml`**
  `dashboard/app.py` imports both at module-level but neither appears in any dependency group. Fresh install raises `ModuleNotFoundError` when running the Streamlit dashboard. Fix: add `dashboard = ["streamlit>=1.36", "plotly>=5.22"]` optional group.

- **[CONFIG] Validation window expired** (`portfolio/simulator.py:16`)
  `VALIDATION_END = date(2026, 4, 21)` is 155 days past. `days_remaining` always returns `0`, making the portfolio simulator's context window metrics misleading. Fix: update to a rolling 30-day window relative to `date.today()`.

- **[PERF] New `httpx.AsyncClient` per Kalshi request** (`markets/kalshi.py:154`)
  ~12 requests × new TCP+TLS handshake per brief run ≈ 500ms wasted. Fix: persistent `AsyncClient` in `__init__`, closed in FastAPI lifespan.

- **[CONFIG] `PRICE_ELASTICITY` and `INSURANCE_THREAT_MULTIPLIER` hardcoded** (`simulation/cascade.py:35,38`)
  Both bypass `ScenarioConfig`. Scenario comparisons silently ignore YAML overrides.

### LOW Severity — Carry-Over

- **[INFRA] `requires-python = ">=3.11"`** (`backend/pyproject.toml:4`)
  Docs and deployment specify Python 3.12; the constraint allows 3.11 builds. Runtime is currently Python 3.11.15 (confirmed). Fix: tighten to `>=3.12`.

- **[DEP] `httpx2` deprecation** — `starlette.testclient` emits `DeprecationWarning` on every test run; will become a hard error in a future Starlette release.

- **[ARCH] `db/queries.py` absent** — planned read-only query helper layer never built. Read queries scattered across `dashboard/data.py`, `main.py`, and CLI.

---

## Test Run (2026-09-23)

```
433 passed, 13 skipped in ~87s
4 collection errors (bench tests — numpy/pandas/sklearn not installed via [dev])
```

No change from 2026-09-22.

---

## Stagnation Summary

| Metric | Value |
|---|---|
| Last `backend/src/` commit | 2026-08-26 (28 days ago) |
| Open HIGH bugs | 5 |
| Open MEDIUM bugs | 5 |
| Open LOW issues | 3 |
| Consecutive YELLOW health checks | 10+ |

---

## Recommendations

1. **One-liners to ship this week** — all HIGH bugs are ≤5 lines each:
   - `s/np.trapz/np.trapezoid/` at `scoring/selective.py:106`
   - `int(row[1] or 0)` at `scoring/ledger.py:283`
   - Add `pytest.importorskip` guards to the 4 bench test files
2. **Deconfliction fix** (`cli/brief.py`) — move `_deconflict_oil_signals()` call before the `record_signal()` loop, or add a follow-up UPDATE. Prevents double-entering correlated oil positions.
3. **Validation date** — update `VALIDATION_END` in `portfolio/simulator.py` to a rolling window so simulator metrics are meaningful.
4. **Wire DbWriter** — route `ops/alerts.py`, `budget/tracker.py`, `scoring/tracker.py`, and `scoring/ledger.py` through `DbWriter.enqueue()`. The queue is already built.
5. **Add `dashboard` optional group** to `pyproject.toml` with `streamlit` and `plotly`.
