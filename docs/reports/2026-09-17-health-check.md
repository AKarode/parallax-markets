# Parallax Health Check — 2026-09-17

**Status: YELLOW**

The test suite is identical to yesterday — 433 passed, 13 skipped, 1 warning in ~83s — and no commits have landed since the Sep 16 report that address any of the flagged issues. All HIGH issues are now 6 days old; the escalation risk grows with each day they go unfixed.

---

## Summary

- **Test suite:** 433 passed, 13 skipped, 1 warning in ~82s (4 bench files excluded from collection)
- **No new regressions** since Sep 16
- **No fixes landed:** The only commits since yesterday's report are the Sep 16 tech research file and the Sep 16 health check commit itself

---

## Issues Found

### [HIGH] `np.trapz` removed in NumPy 2.x — `scoring/selective.py:106` (open 6 days)

`scoring/selective.py:106` calls `np.trapz(risk, coverage)`. `numpy.trapz` was removed in NumPy 2.0; the replacement is `np.trapezoid` (available since NumPy 1.23). Raises `AttributeError` at runtime in any NumPy 2.x environment. Open since Sep 12 with no fix.

- **Fix:** `s/np.trapz/np.trapezoid/` at line 106 of `scoring/selective.py`.

### [HIGH] DuckDB single-writer violation — `ops/alerts.py:108` (open 6 days)

`DuckDBAlertSink.send()` executes `INSERT INTO ops_events …` directly on `self.db_conn` from an `async` method, bypassing the `DbWriter` asyncio.Queue. Concurrent live-pipeline activity risks `database is locked` errors. Open since Sep 12 with no fix.

- **Fix:** Pass a `DbWriter` instance into `DuckDBAlertSink` and replace the direct `conn.execute` with `await self._db_writer.enqueue(...)`.

### [HIGH] 4 bench test files fail to collect — missing import guards (open 6 days)

`test_bench_forecast.py`, `test_calibration_metrics.py`, `test_recalibrators.py`, and `test_selective.py` raise `ModuleNotFoundError` for `pandas`/`numpy`/`sklearn` on a bare `pip install -e ".[dev]"`. No `pytest.importorskip` guards have been added. CI or anyone running the full suite without bench extras silently loses these tests. Open since Sep 12.

- **Fix:** Add `pytest.importorskip("pandas")` / `pytest.importorskip("numpy")` at the top of each affected file.

### [MEDIUM] `scoring/tracker.py` + `scoring/ledger.py` — direct DuckDB writes (open 2 days)

Both call `self._conn.execute(INSERT …)` / `self._conn.execute(UPDATE …)` directly, bypassing the `DbWriter` queue:
- `scoring/ledger.py`: INSERT/UPDATE into `signal_ledger`
- `scoring/tracker.py`: INSERTs/UPDATEs into `trade_positions`, `trade_orders`, `trade_fills`

These are live-pipeline code paths. If called concurrently with the background writer they risk locking. Flagged Sep 16.

- **Fix:** Inject and use a `DbWriter` in both classes, or verify and document they are always called from a single-threaded context with an exclusive connection.

### [MEDIUM] `contracts/registry.py` — direct DuckDB writes at startup (persistent)

`ContractRegistry` calls `conn.execute(INSERT OR REPLACE INTO contract_registry …)` and `conn.execute(UPDATE contract_registry …)` directly at initialization time (lines ~85, 105, 114, 198). Lower risk than live-path writes, but inconsistent with the single-writer convention and a hazard if registry refresh is ever triggered mid-run.

- **Fix:** Route through `DbWriter` or add a docstring explicitly stating this is a setup-only exclusive-connection path.

### [MEDIUM] `backtest/runner.py` — direct DuckDB writes (open 3 days)

`BacktestRunner` executes INSERT/UPDATE into `backtest_runs` and `backtest_predictions` directly. As an offline tool with its own exclusive connection the risk is low, but the pattern diverges from the single-writer convention. Flagged Sep 15.

### [LOW] `pyproject.toml` `requires-python = ">=3.11"` (persistent)

Deployment uses `python:3.12-slim`; the dev environment runs Python 3.11. The constraint should be tightened to `>=3.12` to match the production target and catch any 3.11-vs-3.12 behavior differences in CI.

### [LOW] Phase 1 spec architecture divergence (persistent, intentional)

`docs/superpowers/specs/2026-03-30-parallax-phase1-design.md` describes an LLM agent swarm, H3 spatial layer, BigQuery, and WebSocket dashboard. The actual system is a prediction market edge-finder with no agents module, no spatial module, no simulation engine, and a REST-polling React frontend. The divergence is intentional per CLAUDE.md; the spec remains uncorrected and re-triggers on every daily check.

- **Fix (5 min):** Add a deprecation notice at the top of the spec: `> **DEPRECATED:** This spec describes the original Phase 1 design. The system pivoted to a prediction market edge-finder; see CLAUDE.md for the current architecture.`

---

## Recommendations (priority order)

1. **Fix `np.trapz`** (5 min, 1 line): `scoring/selective.py:106` — `np.trapz` → `np.trapezoid`. Highest-severity, simplest fix; 6 days unfixed.
2. **Fix `ops/alerts.py` write** (30 min): Pass `DbWriter` into `DuckDBAlertSink`, replace direct `conn.execute` in `send()`. Eliminates the only live-async DuckDB write violation.
3. **Guard bench tests** (10 min, 4 lines): `pytest.importorskip("pandas")` at top of each of the 4 affected files so `pytest tests/` is clean without bench extras.
4. **Audit `scoring/tracker.py` + `scoring/ledger.py`** (30 min): Confirm single-threaded access or route writes through `DbWriter`.
5. **Archive stale spec** (5 min): Prepend deprecation notice to the Phase 1 design spec — stops daily re-flagging.
