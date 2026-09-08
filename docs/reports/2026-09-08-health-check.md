# Parallax Health Check — 2026-09-08

**Status: YELLOW**

## Summary

No production code changes since the 2026-09-05 check — commits since the last health report are docs only (tech research + health check). With numpy/pandas now installable, the test suite now shows **490 passed, 13 skipped, 1 failed** (up from 433 passed when collection errors masked 57 tests). The one active failure is `test_selective.py::test_risk_coverage_perfect_ranking` due to `np.trapz` removal in NumPy 2.0. All HIGH/URGENT bugs flagged for 13+ days remain unaddressed; the codebase is architecturally stable but correctness and write-safety defects persist.

---

## What Changed Since Yesterday

- `b31c1c0` — Daily tech research report (2026-09-07) (docs only)
- `eef4986` — Daily health check 2026-09-07 (docs only)

No Python or TypeScript files modified.

---

## Test Suite

| Run | Result |
|-----|--------|
| Collected | All 507 (no collection errors with numpy/pandas installed) |
| Passed | 490 |
| Skipped | 13 |
| Failed | **1** (`test_selective.py::test_risk_coverage_perfect_ranking`) |

**Change from yesterday:** With `numpy`/`pandas` installed, 57 previously-masked tests now run. The 4 collection errors are gone. One test actively fails — `np.trapz` removed in NumPy 2.0.

**Trend:** Core suite stable. One confirmed test failure surfaces that was previously hidden behind a collection error.

---

## Issues Found

### HIGH — DuckDB Single-Writer Violations (Unaddressed, Day 13+)

`db/writer.py` implements the correct single-writer queue pattern but has **zero production call sites**. Every write path below uses direct `conn.execute()` calls. Under concurrent FastAPI handlers or simultaneous CLI + API invocations, DuckDB's file lock will produce `database is locked` errors.

- **`[HIGH]`** `cli/brief.py` — `_persist_run_start`, `_persist_run_end`, `_persist_market_prices`
- **`[HIGH]`** `scoring/ledger.py` — every signal record `INSERT`/`UPDATE`
- **`[HIGH]`** `scoring/tracker.py` — 3 direct writes across paper trade lifecycle
- **`[HIGH]`** `scoring/scorecard.py` — `INSERT ON CONFLICT` for daily ETL
- **`[HIGH]`** `scoring/resolution.py` — `UPDATE`s during settlement polling
- **`[HIGH]`** `scoring/prediction_log.py` — `INSERT` for prediction persistence
- **`[HIGH]`** `contracts/registry.py` — `INSERT`/`UPDATE`s for contract upserts
- **`[HIGH]`** `budget/tracker.py` — `INSERT` on every LLM call (highest frequency)
- **`[HIGH]`** `ingestion/crisis_ingester.py` — `INSERT` during ingestion
- **`[HIGH]`** `ops/alerts.py` — `INSERT` for alert logging
- **`[HIGH]`** `backtest/runner.py` — 4 direct writes: `_persist_backtest_start`, `_persist_prediction`, `_update_prediction_resolution`, `_finalize_result`

### HIGH — Deconfliction Write-Back Bug (Unaddressed, Day 13+)

`cli/brief.py:699` calls `ledger.record_signal()` before `_deconflict_oil_signals()` runs at line 714. The in-memory `.signal = "HOLD"` mutation is never written back to DuckDB. Downstream reads from `ledger.get_signals()` (which re-query the DB) return pre-deconfliction `BUY_YES`/`BUY_NO` signals, silently double-entering correlated oil positions.

**Fix:** Move `_deconflict_oil_signals(all_signals)` before the `record_signal()` loop, or issue `UPDATE signal_ledger SET signal = 'HOLD' WHERE signal_id = ?` after mutation.

### HIGH — TypeError Crash on NULL Win-Rate (Unaddressed, Day 13+)

`scoring/ledger.py:283`: `int(row[1])` raises `TypeError` when `model_was_correct` is NULL for all rows — possible before the first resolution cycle when 5+ signals are already recorded.

**Fix:** `int(row[1] or 0)` and `int(row[0] or 0)`.

### MEDIUM — `np.trapz` Removed in NumPy 2.0 (Active Test Failure)

`scoring/selective.py:106` uses `np.trapz(risk, coverage)`, removed in NumPy 2.0 (`AttributeError`). Now confirmed as an **active test failure** (`test_selective.py::test_risk_coverage_perfect_ranking`), not just a risk.

**Fix:** Replace `np.trapz` → `np.trapezoid` (one-line change).

### MEDIUM — `POST /api/brief/run` Hardcodes `dry_run=True` (Unaddressed, Day 13+)

`main.py:252` forces `dry_run=True, no_trade=True` on every API-triggered brief. A live prediction run cannot be initiated via the API endpoint.

**Fix:** Accept `dry_run` as a query parameter and pass through.

### MEDIUM — numpy/pandas Missing from pyproject.toml Dev Deps (Persistent)

`numpy`, `pandas`, and `scikit-learn` are required by `test_bench_forecast.py`, `test_calibration_metrics.py`, `test_recalibrators.py`, and `test_selective.py` but absent from `[project.optional-dependencies.dev]` in `pyproject.toml`. Fresh CI installs will hit collection errors without manual intervention.

**Fix:** Add `numpy`, `pandas`, `scikit-learn` to `[project.optional-dependencies.dev]`.

### MEDIUM — No Test Coverage for `backtest/runner.py` (Persistent)

`backtest/runner.py` (4 write methods, orchestration loop, resolution logic) has no dedicated test file. A runner regression is invisible to the test suite.

### LOW — anthropic SDK Version Drift (Persistent)

Installed SDK is `1.4.0`; `pyproject.toml` lower bound is `>=0.52` — two major versions stale.

**Fix:** Update lower bound to `>=1.0`.

### LOW — Python Version Mismatch (Persistent)

`pyproject.toml` specifies `requires-python = ">=3.11"` but CLAUDE.md documents Python 3.12. Actual runtime is Python 3.11.15.

**Fix:** Align to `">=3.12"` if 3.12 is the target.

### LOW — Spec Modules Not Implemented (Architecture Drift, Acknowledged)

The following Phase 1 spec modules remain absent — confirmed as deliberate pivot to prediction-market product:
- `simulation/engine.py`, `agents/`, `spatial/`, `eval/`, `api/websocket.py`, `api/auth.py`

No action required unless the original spec is reinstated.

---

## Spec / Plan Consistency (Unchanged)

The codebase remains a stable, intentional pivot from the 50-agent simulation vision to a 3-model prediction market signal engine. The architectural gap is known and accepted.

| Component | Spec | Reality |
|-----------|------|---------|
| LLM layer | 50-agent country/sub-actor swarm | 3 predictors (oil, ceasefire, Hormuz) |
| Frontend | deck.gl + MapLibre H3 hex map + WebSocket | React + Recharts polling dashboard |
| Data ingestion | GDELT BigQuery (15 min) + ACLED | GDELT DOC API + Google News RSS + Truth Social |
| Eval framework | Per-agent accuracy + prompt versioning | Signal ledger + scorecard + calibration |
| Markets | Not in spec | Kalshi + Polymarket (core addition) |

---

## Recommendations

**Priority 1 (2-line fixes, unblock correctness):**
1. **Fix TypeError crash** (`scoring/ledger.py:283`): `int(row[1] or 0)` — prevents silent crash before first resolution cycle.
2. **Fix `np.trapz` → `np.trapezoid`** (`scoring/selective.py:106`): one-line fix that unblocks the active test failure and prevents runtime crash in NumPy 2.0.
3. **Fix deconfliction write-back** (`cli/brief.py`): move `_deconflict_oil_signals` before the `record_signal()` loop — prevents silent double-entry of correlated oil positions.

**Priority 2 (this sprint):**
4. **Add numpy/pandas/scikit-learn to dev deps** in `pyproject.toml` — prevents fresh-install CI failures.
5. **Route writes through DbWriter** — adopt the queue pattern across all 11 violating modules before enabling concurrent API + CLI usage.
6. **Add backtest runner tests** — new `test_backtest_runner.py` covering 4 write methods and resolution loop.
7. **Expose `dry_run` param** on `POST /api/brief/run`.

**Priority 3 (backlog):**
8. Update `pyproject.toml` lower bounds: `anthropic>=0.52` → `>=1.0`; `requires-python = ">=3.11"` → `">=3.12"`.
