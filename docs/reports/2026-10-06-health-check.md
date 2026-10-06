# Parallax Health Check — 2026-10-06

**Status: YELLOW**

## Summary

No code changes for a ninth consecutive day; last code commit remains 2026-09-28 (8 days ago). All four tracked issues carry forward unresolved. Both HIGH items have had documented, low-effort fixes available for 24 days with no action taken. Test suite is unchanged at 433 pass / 13 skip with 4 collection errors.

---

## Issues Found

### [HIGH] 4 test files fail at collection — `numpy`/`pandas` missing from `[dev]` extra *(persistent — 24 days, since 2026-09-12)*

`tests/test_bench_forecast.py`, `tests/test_calibration_metrics.py`, `tests/test_recalibrators.py`, and `tests/test_selective.py` fail at import with `ModuleNotFoundError: No module named 'numpy'`/`'pandas'`. ~48 bench/calibration tests are silently excluded from every CI run. `numpy` and `pandas` live under the `[bench]` optional extras; `pip install -e ".[dev]"` does not pull them.

**Fix (5 min):** Add `numpy>=1.26` and `pandas>=2.0` to the `dev` dependency list in `backend/pyproject.toml`.

### [HIGH] DuckDB single-writer violations in production modules *(persistent — 24 days, since 2026-09-12)*

Multiple production modules write directly to DuckDB via `conn.execute(INSERT/UPDATE/DELETE)`, bypassing the `asyncio.Queue` mandated by the design spec. Under concurrent FastAPI load these produce `database is locked` errors. Confirmed write-bypass sites:

- `scoring/ledger.py:225,256` — `INSERT`/`UPDATE` into `signal_ledger`
- `scoring/tracker.py:460,516,672,711,744` — writes to `trade_positions`, `trade_orders`, `trade_fills`
- `scoring/resolution.py` — `UPDATE signal_ledger`, `UPDATE trade_positions` on settlement
- `ops/alerts.py:106` — `INSERT` into `ops_events`
- `budget/tracker.py:43` — `INSERT` into `llm_usage`
- `scoring/prediction_log.py:~81` — `INSERT` into `prediction_log`
- `ingestion/crisis_ingester.py:~81` — `INSERT` into `crisis_events`
- `cli/brief.py:~132,~151,~433` — `INSERT`/`UPDATE` on `runs`, `market_prices`
- `contracts/registry.py:~85,~105,~114,~198` — writes to `contract_registry`
- `backtest/runner.py:290,308,329,356` — direct writes (backtest path, lower live risk)

The `DbWriter` queue exists in `db/writer.py` but is unused for any production writes. `scoring/ledger.py` and `scoring/tracker.py` are the hottest paths (called from live API handlers) and represent the highest production risk.

**Fix:** Route all write calls through `DbWriter.enqueue()`. Start with `scoring/ledger.py` and `scoring/tracker.py`.

### [MEDIUM] Architecture diverged from Phase 1 spec *(persistent — intentional pivot)*

The original Phase 1 spec (50-agent LLM swarm, H3 spatial visualization on deck.gl/MapLibre, GDELT BigQuery, WebSocket push) was pivoted to a 3-model prediction-market edge-finder with REST API, Google News RSS + GDELT DOC API, and Kalshi/Polymarket comparison. Missing spec modules: `agents/`, `spatial/`, `eval/`, `api/websocket.py`, `api/auth.py`, `simulation/engine.py`, `simulation/circuit_breaker.py`. Frontend uses polling with no `deck.gl`, `MapLibre GL`, or H3 visualization.

`CLAUDE.md` reflects the pivoted architecture and is internally consistent. Flag clears once the Phase 1 design spec is updated to document the actual architecture.

### [LOW] No new test coverage for 24+ days *(persistent)*

Test count stable at 433 pass / 13 skip. Newer modules `backtest/`, `bench/`, `scoring/recalibrators.py`, `scoring/selective.py` have partial test coverage blocked by the numpy/pandas issue above.

---

## Test Suite Snapshot

| Result | Count |
|--------|-------|
| Passed | 433 |
| Skipped | 13 |
| Collection errors (`numpy`/`pandas` missing) | 4 files, ~48 tests |
| Failed | 0 |

---

## Changes Since 2026-10-05

No code changes. No documentation changes beyond automated daily reports and tech research. All four issues carry forward unchanged for the 24th consecutive day. Most recent code commit remains 2026-09-28.

---

## Recommendations

1. **[5 min — critically overdue]** Add `numpy>=1.26` and `pandas>=2.0` to `[dev]` extras in `backend/pyproject.toml`. Single-line fix, unblocks ~48 tests.
2. **[Medium effort — overdue]** Route `scoring/ledger.py` and `scoring/tracker.py` writes through `DbWriter.enqueue()`. These are called from live API handlers and are the most likely source of `database is locked` errors under production concurrency.
3. **[Low effort]** Update or supersede the Phase 1 design spec to document the prediction-market pivot, clearing the MEDIUM architecture-drift flag permanently.
