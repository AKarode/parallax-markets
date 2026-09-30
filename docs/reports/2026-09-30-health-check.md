# Parallax Health Check — 2026-09-30

**Status: YELLOW**

## Summary

No code changes for a third consecutive day; the last code commit was 2026-09-28. The test suite holds at 433 pass / 13 skip with 4 collection errors from missing bench dependencies — unchanged since the 2026-09-12 report. All three tracked issues have now been flagged for 18+ days without action, crossing from "known" to "stale-backlog" territory.

---

## Issues Found

### [HIGH] 4 test files fail at collection — `numpy`/`pandas` missing from `[dev]` extra *(persistent — 18 days, since 2026-09-12)*

`tests/test_bench_forecast.py`, `tests/test_calibration_metrics.py`, `tests/test_recalibrators.py`, and `tests/test_selective.py` all fail import with `ModuleNotFoundError: No module named 'numpy'`/`'pandas'`. The ~48 bench/calibration tests are silently excluded from every CI run. `numpy` and `pandas` live under `[bench]` extras which `pip install -e ".[dev]"` does not pull.

**Fix (5 min):** Add `numpy>=1.26` and `pandas>=2.0` to the `dev` list in `backend/pyproject.toml`. No other change needed.

### [HIGH] DuckDB single-writer violations in production modules *(persistent — 18 days, since 2026-09-12)*

Multiple production modules write directly to DuckDB via `conn.execute(INSERT/UPDATE)`, bypassing the `asyncio.Queue` mandated by the design spec. Under concurrent FastAPI load (e.g. `POST /api/brief/run` overlapping with a dashboard poll), these produce `database is locked` errors. Confirmed violations:

- `scoring/ledger.py:225,256` — direct `INSERT`/`UPDATE` into `signal_ledger`
- `scoring/tracker.py:460,516,672,711,744` — direct writes to trade tables
- `scoring/resolution.py` — direct writes on settlement
- `ops/alerts.py:106` — direct `INSERT` into `ops_events`
- `budget/tracker.py:43` — direct `INSERT` into `llm_usage`
- `backtest/runner.py:290,308,329,356` — direct writes (backtest path, lower risk)

**Fix:** Route writes through `DbWriter.enqueue()`. `scoring/ledger.py` and `scoring/tracker.py` are the hottest paths (called from API handlers) and should be prioritised.

### [MEDIUM] Architecture diverged from Phase 1 spec *(persistent — intentional pivot)*

The original spec (50-agent swarm, H3 spatial visualization, GDELT BigQuery, WebSocket push) was pivoted to a 3-model prediction-market edge-finder with REST API, Google News RSS + GDELT DOC API, and Kalshi/Polymarket comparison. Missing spec modules: `agents/`, `spatial/`, `eval/`, `api/websocket.py`, `api/auth.py`, `simulation/engine.py`, `simulation/circuit_breaker.py`. The frontend lacks `deck.gl`, `MapLibre`, and all spec-required map components.

The current system is internally consistent and `CLAUDE.md` reflects the pivoted architecture. Status will remain MEDIUM until the Phase 1 design spec is superseded with a document describing the actual architecture.

### [LOW] No new test coverage for 18+ days *(persistent)*

Test count stable at 433 pass / 13 skip. Newer modules `backtest/`, `bench/`, `scoring/recalibrators.py`, and `scoring/selective.py` have partial test coverage blocked by the numpy/pandas issue. No net regression.

---

## Test Suite Snapshot

| Result | Count |
|--------|-------|
| Passed | 433 |
| Skipped | 13 |
| Collection errors (`numpy`/`pandas` missing) | 4 files, ~48 tests |
| Failed | 0 |

---

## Changes Since 2026-09-29

- No code changes. One documentation file added: `docs/reports/2026-09-29-tech-research.md`.
- All issues from prior report carry forward unchanged.
- The two HIGH issues have now been flagged for 18 consecutive days.

---

## Recommendations

1. **[5 min — overdue]** Add `numpy>=1.26` and `pandas>=2.0` to `[dev]` extras in `backend/pyproject.toml`. This single line unblocks 48 tests and restores full calibration coverage to CI. It has been the easiest open fix for 18 days.
2. **[Medium effort — overdue]** Route `scoring/ledger.py` and `scoring/tracker.py` writes through `DbWriter.enqueue()`. These are the live-path modules called from API handlers and most likely to produce `database is locked` errors in production.
3. **[Low effort]** Update or supersede the Phase 1 design spec to document the prediction-market pivot. This clears the MEDIUM architecture-drift flag permanently.
