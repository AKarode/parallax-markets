# Parallax Health Check — 2026-09-06

**Status: YELLOW**

## Summary

No production code changes since the 2026-09-04 check — all commits since then are automated health reports and tech research documents only. Test suite: **433 passed, 13 skipped** (identical to 2026-09-05). All HIGH/URGENT bugs flagged over the past 10+ days remain unaddressed. A new observation this cycle: `backtest/runner.py` adds 4 more direct DuckDB writes not listed in previous reports, and has no dedicated test file.

---

## Issues Found

### HIGH — DuckDB Single-Writer Violations (Unaddressed, Day 11+)

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
- **`[HIGH]`** `backtest/runner.py` — 4 direct writes: `_persist_backtest_start`, `_persist_prediction`, `_update_prediction_resolution`, `_finalize_result` (not listed in prior reports; confirmed this cycle)

### HIGH — Deconfliction Write-Back Bug (Unaddressed, Day 11+)

`cli/brief.py:699` calls `ledger.record_signal()` before `_deconflict_oil_signals()` runs at line 714. The in-memory `.signal = "HOLD"` mutation is never written back to DuckDB. Downstream reads from `ledger.get_signals()` (which re-query the DB) return pre-deconfliction `BUY_YES`/`BUY_NO` signals, silently double-entering correlated oil positions.

**Fix:** Move `_deconflict_oil_signals(all_signals)` before the `record_signal()` loop, or issue `UPDATE signal_ledger SET signal = 'HOLD' WHERE signal_id = ?` after mutation.

### HIGH — TypeError Crash on NULL Win-Rate (Unaddressed, Day 11+)

`scoring/ledger.py:283`: `int(row[1])` raises `TypeError` when `model_was_correct` is NULL for all rows — possible before the first resolution cycle when 5+ signals are already recorded.

**Fix:** `int(row[1] or 0)` and `int(row[0] or 0)`.

### MEDIUM — numpy/pandas Not Installed — 4 Test Collection Failures (Persistent)

`numpy` and `pandas` are absent from the environment (not installed in dev or CI by default — `bench` extras not enabled), causing collection failures for:
- `test_bench_forecast.py` — `ModuleNotFoundError: No module named 'pandas'`
- `test_calibration_metrics.py` — `ModuleNotFoundError: No module named 'numpy'`
- `test_recalibrators.py` — `ModuleNotFoundError: No module named 'numpy'`
- `test_selective.py` — `ModuleNotFoundError: No module named 'numpy'`

**Fix:** Either add `numpy`, `pandas`, `scikit-learn` to `[project.optional-dependencies.dev]` so `pip install -e ".[dev]"` picks them up, or guard imports in the test files with `pytest.importorskip`.

### MEDIUM — `np.trapz` Removed in NumPy 2.0 (Unaddressed)

`scoring/selective.py:106` uses `np.trapz(risk, coverage)`, which was removed in NumPy 2.0 (`AttributeError`).

**Fix:** Replace with `np.trapezoid`.

### MEDIUM — `POST /api/brief/run` Hardcodes `dry_run=True` (Unaddressed, Day 11+)

`main.py:252` forces `dry_run=True, no_trade=True` on every API-triggered brief. A live prediction run cannot be initiated via the API.

### MEDIUM — No Test Coverage for `backtest/runner.py` (New Observation)

`backtest/runner.py` (4 write methods, orchestration loop, resolution logic) has no dedicated test file. `test_backtest_look_ahead.py` covers `look_ahead_guard.py` only. A runner regression would not be caught by the suite.

### LOW — anthropic SDK Version Drift

Installed SDK is `1.4.0`; `pyproject.toml` lower bound is `>=0.52` — now two major versions stale. Tests pass with no import or API errors.

**Fix:** Update lower bound to `>=1.0`.

### LOW — Python Version Mismatch

`pyproject.toml` specifies `requires-python = ">=3.11"` but CLAUDE.md documents Python 3.12. Actual runtime is Python 3.11.15.

### LOW — Spec Modules Not Implemented (Architecture Drift, Acknowledged)

The following Phase 1 spec modules remain absent — confirmed as deliberate pivot to prediction-market product:
- `simulation/engine.py`, `agents/`, `spatial/`, `eval/`, `api/websocket.py`, `api/auth.py`

No action required unless the original spec is reinstated.

---

## Recommendations

1. **[URGENT] Fix TypeError crash** (`scoring/ledger.py:283`) — 2-line change, prevents silent crash before first resolution cycle.
2. **[URGENT] Fix deconfliction write-back** (`cli/brief.py`) — move `_deconflict_oil_signals` call before the `record_signal()` loop to prevent double-entered correlated oil positions.
3. **[HIGH] Route writes through DbWriter** — adopt the queue pattern across all 11 violating modules before enabling concurrent API + CLI usage; add `backtest/runner.py` to the list.
4. **[MEDIUM] Fix test collection failures** — add `numpy`/`pandas`/`scikit-learn` to `[dev]` extras or use `pytest.importorskip` guards; replace `np.trapz` → `np.trapezoid` in `scoring/selective.py`.
5. **[MEDIUM] Add backtest runner tests** — cover the 4 write methods and the resolution loop in a new `test_backtest_runner.py`.
6. **[MEDIUM] Expose `dry_run` param on `POST /api/brief/run`** — accept as query parameter rather than hardcoding.
7. **[LOW] Update `pyproject.toml` lower bounds** — `anthropic>=0.52` → `>=1.0`; `requires-python = ">=3.11"` → `">=3.12"`.
