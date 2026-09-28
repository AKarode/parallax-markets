# Parallax Health Check — 2026-09-28

**Status: YELLOW**

## Summary

The core prediction-market pipeline remains healthy: 433 tests pass, 13 skipped, 0 failures in the runnable test suite. No code changes have been merged since the 2026-09-26 report (only documentation/research files added). The two HIGH-severity issues flagged in prior reports — missing `numpy`/`pandas` in `dev` extras blocking 4 test files, and widespread DuckDB single-writer violations in scoring/ops modules — remain unaddressed and are now persistent for 2+ weeks.

---

## Issues Found

### [HIGH] 4 test files blocked from collection — `numpy`/`pandas` missing from `dev` extra *(persistent)*
`tests/test_bench_forecast.py`, `tests/test_calibration_metrics.py`, `tests/test_recalibrators.py`, `tests/test_selective.py` all fail at import with `ModuleNotFoundError: No module named 'numpy'`/`'pandas'`. These modules are in the `[bench]` optional extra, not `[dev]`. Standard CI (`pip install -e ".[dev]" && pytest`) hits a hard collection error and aborts before running any tests. The fix is one line in `pyproject.toml`.

**Fix:** Add `numpy>=1.26` and `pandas>=2.0` to `[project.optional-dependencies] dev` in `backend/pyproject.toml`.

### [HIGH] DuckDB single-writer violations across production modules *(persistent)*
Multiple production modules write directly to DuckDB via `conn.execute(INSERT/UPDATE/DELETE)` outside the `asyncio.Queue` pattern. This violates the architecture contract in the design spec and will cause `database is locked` errors under concurrent FastAPI load:

- `scoring/ledger.py:225,256` — direct `INSERT`/`UPDATE` to `signal_ledger`
- `scoring/tracker.py:460,518,674,713,746` — direct writes to `trade_positions`, `trade_orders`, `trade_fills`
- `scoring/prediction_log.py:79` — direct `INSERT` to `prediction_log`
- `scoring/resolution.py:60,124` — direct writes
- `ops/alerts.py:106` — direct `INSERT` to `ops_events` via `DuckDBAlertSink`
- `budget/tracker.py:43` — direct write to `llm_usage`
- `cli/brief.py:130,149,431` — direct writes (CLI-only, lower risk, but inconsistent)

**Fix:** Route all writes in `scoring/`, `ops/alerts.py`, and `budget/tracker.py` through `DbWriter.enqueue()`. The `cli/brief.py` writes are lower priority since CLI runs are single-process.

### [MEDIUM] Architecture diverged from Phase 1 design spec *(persistent, likely intentional)*
The original spec (50-agent geopolitical swarm, H3 spatial visualization, GDELT BigQuery, WebSocket dashboard) was never implemented. The actual system is a 3-model prediction market edge-finder with REST API, Google News RSS + GDELT DOC, and Kalshi/Polymarket comparison. The following spec modules are entirely absent: `agents/`, `spatial/`, `eval/`, `api/websocket.py`, `api/auth.py`.

The pivot appears intentional and the current implementation is internally consistent. The spec document should be updated to reflect current architecture so health checks can evaluate against the correct baseline.

### [LOW] No new test coverage added in past 7 days
The test count has been stable at 433 pass / 13 skip for multiple weeks. The newer `backtest/`, `bench/`, `scoring/recalibrators.py`, and `scoring/selective.py` modules added tests that are blocked by the numpy issue above. No net regression, but blocked tests represent dead coverage.

---

## Test Suite Snapshot

| Result | Count |
|--------|-------|
| Passed | 433 |
| Skipped | 13 |
| Collection errors (numpy/pandas missing) | 4 files |
| Failed | 0 |

---

## Recommendations

1. **Fix `pyproject.toml` today** — add `numpy` to `dev` extras. One-line change, unblocks 4 test files and restores calibration test coverage to CI.
2. **Route scoring writes through `DbWriter`** — the `scoring/ledger.py` and `scoring/tracker.py` paths are hot and called from API handlers; these are the highest-risk concurrent write sites.
3. **Update the spec** — replace or supersede `docs/superpowers/specs/2026-03-30-parallax-phase1-design.md` with a document describing the actual prediction-market architecture. Daily health checks will remain "YELLOW" on architecture drift until this is done.
