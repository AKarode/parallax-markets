# Parallax Health Check — 2026-09-05

**Status: YELLOW**

## Summary

No production code changes since the 2026-09-04 check — the two commits since then are automated health reports and a tech research document only. All known bugs carry forward unchanged for Day 10+. Test suite: **433 passed, 13 skipped** from the main suite; 4 test files fail at collection due to `numpy`/`pandas` not installed. The `anthropic` SDK bumped to 1.4.0 (was 1.2.0 in the 2026-08-29 baseline); tests continue to pass with no import errors.

---

## Issues Found

### HIGH — DuckDB Single-Writer Violations (Unaddressed, Day 10+)

`db/writer.py` is correctly implemented but has zero production call sites. Every write path executes direct `conn.execute()` calls instead of routing through `DbWriter.enqueue()`. Under concurrent FastAPI async handlers or parallel CLI + API invocations, DuckDB file locking will produce `database is locked` errors.

- **`[HIGH]`** `cli/brief.py` — direct `INSERT`/`UPDATE` in `_persist_run_start`, `_persist_run_end`, `_persist_market_prices`
- **`[HIGH]`** `scoring/ledger.py` — direct `INSERT`/`UPDATE` on every signal record
- **`[HIGH]`** `scoring/tracker.py` — 3 direct writes across paper trade lifecycle
- **`[HIGH]`** `scoring/scorecard.py` — direct `INSERT ON CONFLICT` for daily ETL
- **`[HIGH]`** `scoring/resolution.py` — direct `UPDATE`s during settlement polling
- **`[HIGH]`** `scoring/prediction_log.py` — direct `INSERT` for prediction persistence
- **`[HIGH]`** `contracts/registry.py` — direct `INSERT`/`UPDATE`s for contract upserts
- **`[HIGH]`** `budget/tracker.py` — direct `INSERT` on every LLM call (highest frequency)
- **`[HIGH]`** `ingestion/crisis_ingester.py` — direct `INSERT` during ingestion
- **`[HIGH]`** `ops/alerts.py` — direct `INSERT` for alert logging

### HIGH — Deconfliction Write-Back Bug (Unaddressed, Day 10+)

`cli/brief.py:699` calls `ledger.record_signal()` before `_deconflict_oil_signals()` runs at line 714. The in-memory `.signal = "HOLD"` mutation is never written back to DuckDB. Downstream reads from `ledger.get_signals()` (which re-query the DB) return pre-deconfliction `BUY_YES`/`BUY_NO` signals, silently double-entering correlated oil positions.

**Fix:** Move `_deconflict_oil_signals(all_signals)` before the `record_signal()` loop, or issue `UPDATE signal_ledger SET signal = 'HOLD' WHERE signal_id = ?` after mutation.

### HIGH — TypeError Crash on NULL Win-Rate (Unaddressed, Day 10+)

`scoring/ledger.py:283`: `int(row[1])` raises `TypeError` when `model_was_correct` is NULL for all rows — possible before the first resolution cycle when 5+ signals are already recorded.

**Fix:** `int(row[1] or 0)` and `int(row[0] or 0)`.

### MEDIUM — numpy/pandas Not Installed — 4 Test Collection Failures (Persistent)

`numpy` and `pandas` are absent from the environment, causing collection failures for:
- `test_bench_forecast.py` — `ModuleNotFoundError: No module named 'pandas'`
- `test_calibration_metrics.py` — `ModuleNotFoundError: No module named 'numpy'`
- `test_recalibrators.py` — `ModuleNotFoundError: No module named 'numpy'`
- `test_selective.py` — `ModuleNotFoundError: No module named 'numpy'`

**Fix:** Add `numpy>=1.26`, `pandas>=2.0`, `scikit-learn>=1.3` to `[project.dependencies]` (or a `[extras]` group that dev depends on).

### MEDIUM — `np.trapz` Removed in NumPy 2.0 (Unaddressed)

`scoring/selective.py:106` uses `np.trapz(risk, coverage)`, which was removed in NumPy 2.0 (`AttributeError`).

**Fix:** Replace with `np.trapezoid`.

### MEDIUM — `scikit-learn` Not Declared in `pyproject.toml` (Unaddressed)

`scoring/recalibrators.py:111` does a deferred `from sklearn.isotonic import IsotonicRegression`. `scikit-learn` is not in `pyproject.toml`. Clean installs will fail at runtime.

**Fix:** Add `scikit-learn>=1.3` to dependencies.

### MEDIUM — `POST /api/brief/run` Hardcodes `dry_run=True` (Unaddressed, Day 10+)

`main.py:252` forces `dry_run=True, no_trade=True` on every API-triggered brief. A live prediction run cannot be initiated via the API.

### LOW — anthropic SDK Version Drift

SDK bumped to `1.4.0` (was `1.2.0` in the 2026-08-29 baseline). Tests continue to pass; no import or API errors detected. `pyproject.toml` lower bound (`>=0.52`) is now two major versions stale and should be updated to `>=1.0`.

### LOW — Python Version Mismatch

`pyproject.toml` specifies `requires-python = ">=3.11"` but CLAUDE.md documents Python 3.12. Actual runtime is Python 3.11.15. No functional breakage; documentation is misleading.

### LOW — Spec Modules Not Implemented (Architecture Drift, Acknowledged)

The following Phase 1 spec modules remain absent — confirmed as a deliberate pivot to the prediction-market product:
- `simulation/engine.py`, `agents/`, `spatial/`, `eval/`, `api/websocket.py`, `api/auth.py`

No action required unless the original spec is reinstated.

---

## Recommendations

1. **[URGENT] Fix TypeError crash** (`scoring/ledger.py:283`) — 2-line change, prevents silent crash in production after first day of signals before any resolution cycle completes.
2. **[URGENT] Fix deconfliction write-back** (`cli/brief.py`) — move deconfliction before `record_signal()` loop to prevent double-entered correlated oil positions.
3. **[HIGH] Route writes through DbWriter** — adopt the queue pattern in the 10 violating modules before enabling concurrent API + CLI usage.
4. **[MEDIUM] Add `numpy`/`scikit-learn` to `pyproject.toml` deps** and replace `np.trapz` → `np.trapezoid` to restore 4 failing test collection files.
5. **[LOW] Update `POST /api/brief/run`** to accept a `dry_run` query param rather than hardcoding it.
6. **[LOW] Update `pyproject.toml` lower bounds** — `anthropic>=0.52` → `>=1.0`; `requires-python = ">=3.11"` → `">=3.12"`.
