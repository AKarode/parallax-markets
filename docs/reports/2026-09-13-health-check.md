# Parallax Health Check — 2026-09-13

**Status: RED**

## Summary

No production code changes since yesterday's RED report — both commits since the 2026-09-12 check are docs-only (tech research + health check). With `bench` extras installed the test suite shows **490 passed, 13 skipped, 1 failed**; without bench extras the standard `pip install -e ".[dev]"` path produces 4 collection errors. All HIGH/URGENT bugs flagged for 14+ days remain unaddressed; the codebase is architecturally stable but the correctness, write-safety, and concurrency defects are now in their third week without any fix.

---

## What Changed Since Yesterday

- `f0ee091` — Daily tech research: Stack improvements for Q3 2026 (docs only)
- `ff73b7d` — chore: daily health check 2026-09-12 (RED) (docs only)

No Python or TypeScript files modified.

---

## Test Suite

| Run | Result |
|-----|--------|
| Collected (with `[bench]` extras) | 504 tests |
| Passed | 490 |
| Skipped | 13 |
| Failed | **1** (`test_selective.py::test_risk_coverage_perfect_ranking`) |
| Collected (without `[bench]` extras) | 4 collection errors |

**Root cause of 4 collection errors:** `numpy`, `pandas`, `scikit-learn` are in `[bench]` extras but the test files live in the main `tests/` directory, so `pytest` tries to import them on every run. A fresh `pip install -e ".[dev]"` (CI default) fails immediately.

**Active test failure:** `np.trapz` was removed in NumPy 2.0; installed version is 2.4.6. `scoring/selective.py:106` still calls `np.trapz(risk, coverage)`.

---

## Issues Found

### HIGH — DuckDB Single-Writer Violations (Unaddressed, Day 14+)

`db/writer.py` implements the correct single-writer queue pattern but has **zero production call sites**. Every write path below uses direct `conn.execute()` calls. Under concurrent FastAPI handlers or simultaneous CLI + API invocations, DuckDB's file lock will produce `database is locked` errors or silent state corruption.

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

### HIGH — Deconfliction Write-Back Bug (Unaddressed, Day 14+)

`cli/brief.py:699` calls `ledger.record_signal()` before `_deconflict_oil_signals()` runs at line 714. The in-memory `.signal = "HOLD"` mutation is never written back to DuckDB. Downstream reads from `ledger.get_signals()` (which re-query the DB) return pre-deconfliction `BUY_YES`/`BUY_NO` signals, silently double-entering correlated oil positions.

**Fix:** Move `_deconflict_oil_signals(all_signals)` before the `record_signal()` loop, or issue `UPDATE signal_ledger SET signal = 'HOLD' WHERE signal_id = ?` after mutation.

### HIGH — TypeError Crash on NULL Win-Rate (Unaddressed, Day 14+)

`scoring/ledger.py:283`: `int(row[1])` raises `TypeError` when `model_was_correct` is NULL for all rows — possible before the first resolution cycle when 5+ signals are already recorded.

**Fix:** `int(row[1] or 0)` and `int(row[0] or 0)`.

### MEDIUM — `np.trapz` Removed in NumPy 2.0 (Active Test Failure, Day 14+)

`scoring/selective.py:106` uses `np.trapz(risk, coverage)`, removed in NumPy 2.0 (now 2.4.6 installed). Confirmed active test failure: `test_selective.py::test_risk_coverage_perfect_ranking`.

**Fix:** Replace `np.trapz` → `np.trapezoid` (one-line change).

### MEDIUM — `POST /api/brief/run` Hardcodes `dry_run=True` (Unaddressed, Day 14+)

`main.py:252` forces `dry_run=True, no_trade=True` on every API-triggered brief. A live prediction run cannot be initiated via the API endpoint.

**Fix:** Accept `dry_run` / `no_trade` as query parameters and pass through.

### MEDIUM — numpy/pandas Missing from pyproject.toml Dev Deps (Persistent, Day 14+)

`numpy`, `pandas`, and `scikit-learn` are required by 4 test files in `tests/` but absent from `[project.optional-dependencies.dev]`. A standard `pip install -e ".[dev]"` on a fresh CI clone hits 4 collection errors immediately.

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

These are the same 8 recommendations from prior reports — none have been actioned.

**Priority 1 (2-line fixes, unblock correctness):**
1. **Fix `np.trapz` → `np.trapezoid`** (`scoring/selective.py:106`): one-line fix, unblocks active test failure.
2. **Fix TypeError crash** (`scoring/ledger.py:283`): `int(row[1] or 0)` — prevents silent crash before first resolution cycle.
3. **Fix deconfliction write-back** (`cli/brief.py`): move `_deconflict_oil_signals` before the `record_signal()` loop.

**Priority 2 (this sprint):**
4. **Add numpy/pandas/scikit-learn to dev deps** in `pyproject.toml` — prevents fresh-install CI failures.
5. **Route writes through DbWriter** — adopt the queue pattern across all 11 violating modules before enabling concurrent API + CLI usage.
6. **Add backtest runner tests** — new `test_backtest_runner.py` covering 4 write methods and resolution loop.
7. **Expose `dry_run` param** on `POST /api/brief/run`.

**Priority 3 (backlog):**
8. Update `pyproject.toml` lower bounds: `anthropic>=0.52` → `>=1.0`; `requires-python = ">=3.11"` → `">=3.12"`.

---

*Report generated by automated daily health check. 490 tests pass (bench extras), 13 skipped, 1 active failure. Without bench extras: 4 collection errors.*
