# Parallax Health Check — 2026-09-29

**Status: YELLOW**

## Summary

Core test suite remains healthy: 433 passed, 13 skipped, 0 failures in the runnable suite. No code changes since the 2026-09-28 report — only documentation files were added. All three HIGH/MEDIUM issues identified in prior reports remain unaddressed for 3+ consecutive days; they are now classified as persistent blockers.

---

## Issues Found

### [HIGH] 4 test files fail at collection — `numpy`/`pandas` missing from `dev` extra *(persistent — 3+ days)*

`tests/test_bench_forecast.py`, `tests/test_calibration_metrics.py`, `tests/test_recalibrators.py`, `tests/test_selective.py` all fail import with `ModuleNotFoundError: No module named 'numpy'`/`'pandas'`. These 48 tests are silently excluded from every CI run. The `[bench]` optional extras that contain numpy/pandas are not pulled by `pip install -e ".[dev]"`.

**Fix:** Add `numpy>=1.26` and `pandas>=2.0` to `[project.optional-dependencies] dev` in `backend/pyproject.toml` (one line).

### [HIGH] DuckDB single-writer violations in production modules *(persistent — 3+ days)*

Multiple production modules write directly to DuckDB via `conn.execute(INSERT/UPDATE)` bypassing the `asyncio.Queue` pattern mandated by the design spec. These will cause `database is locked` errors under concurrent FastAPI load. Confirmed violations:

- `scoring/ledger.py:225,256` — direct `INSERT`/`UPDATE` into `signal_ledger`
- `scoring/tracker.py` — direct writes to `trade_positions`, `trade_orders`, `trade_fills`
- `scoring/prediction_log.py:79` — direct `INSERT` into `prediction_log`
- `scoring/resolution.py:60,124` — direct writes on settlement
- `ops/alerts.py:106` — direct `INSERT` into `ops_events` via `DuckDBAlertSink`
- `budget/tracker.py:43` — direct write into `llm_usage`

**Fix:** Route all writes through `DbWriter.enqueue()`. The `cli/brief.py` writes are CLI-only and lower priority.

### [MEDIUM] Architecture diverged from Phase 1 spec *(persistent, likely intentional)*

The original spec (50-agent swarm, H3 spatial visualization, GDELT BigQuery, WebSocket) was pivoted to a 3-model prediction-market edge-finder with REST API, Google News RSS + GDELT DOC, and Kalshi/Polymarket comparison. The following spec modules are absent: `agents/`, `spatial/`, `eval/`, `api/websocket.py`, `api/auth.py`. The simulation module is missing `engine.py` and `circuit_breaker.py`.

This pivot appears intentional and the current system is internally consistent. Status will remain YELLOW until the spec is updated to reflect current architecture.

### [LOW] No new test coverage for 7+ days *(persistent)*

Test count stable at 433 pass / 13 skip. Newer `backtest/`, `bench/`, `scoring/recalibrators.py`, and `scoring/selective.py` modules have tests blocked by the numpy issue above (48 tests, ~10% of suite). No net regression.

---

## Test Suite Snapshot

| Result | Count |
|--------|-------|
| Passed | 433 |
| Skipped | 13 |
| Collection errors (`numpy`/`pandas` missing) | 4 files, ~48 tests |
| Failed | 0 |

---

## Changes Since 2026-09-28

- No code changes. Two documentation files added (`docs/reports/2026-09-28-health-check.md`, `docs/reports/2026-09-28-tech-research.md`).
- All issues from prior report carry forward unchanged.

---

## Recommendations

1. **[5 min fix]** Add `numpy>=1.26` and `pandas>=2.0` to `[dev]` extras in `backend/pyproject.toml`. Unblocks 48 tests and restores full calibration/recalibration coverage to CI.
2. **[Medium effort]** Route `scoring/ledger.py` and `scoring/tracker.py` writes through `DbWriter.enqueue()` — these are the hottest paths called from API handlers and most at risk under load.
3. **[Low effort]** Supersede the Phase 1 design spec with a document describing the actual prediction-market architecture to clear the persistent architecture-drift flag.
