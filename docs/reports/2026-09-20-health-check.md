# Parallax Health Check — 2026-09-20

**Status: YELLOW**

## Summary

Test suite holds at 433 passed, 13 skipped, 1 warning (~77s). No code commits have landed since Sep 19 — only a tech research doc was added. All three HIGH issues from yesterday are now open for **9 consecutive days** with no fixes. The bench collection errors and DuckDB single-writer violations remain the dominant concerns.

---

## Issues Found

### [HIGH] `np.trapz` removed in NumPy 2.x — `scoring/selective.py:106` (open 9 days)

`scoring/selective.py:106` calls `np.trapz(risk, coverage)`. `numpy.trapz` was removed in NumPy 2.0; the replacement is `np.trapezoid` (available since NumPy 1.23). Raises `AttributeError` at runtime in any NumPy 2.x environment. NumPy is not installed in the base environment; the bug is latent until `pip install ".[bench]"` is run.

- **Fix:** `s/np.trapz/np.trapezoid/` at line 106 of `scoring/selective.py` (1 line, 5 min).

### [HIGH] DuckDB single-writer violation — `ops/alerts.py:106` (open 9 days)

`DuckDBAlertSink.send()` executes `INSERT INTO ops_events …` directly on `self.db_conn` from an `async` method, bypassing the `DbWriter` asyncio.Queue. Concurrent live-pipeline activity risks `database is locked` errors.

- **Fix:** Pass a `DbWriter` instance into `DuckDBAlertSink` and replace the direct `conn.execute` with `await self._db_writer.enqueue(...)`.

### [HIGH] 4 bench test files fail to collect — missing import guards (open 9 days)

`test_bench_forecast.py`, `test_calibration_metrics.py`, `test_recalibrators.py`, and `test_selective.py` raise `ModuleNotFoundError` for `pandas`/`numpy`/`sklearn` on a bare `pip install -e ".[dev]"`. Running `pytest tests/` fails collection for all 4 files, making the suite uncollectable without `--ignore`.

- **Fix:** Add `pytest.importorskip("pandas")` / `pytest.importorskip("numpy")` at the top of each affected file (4 lines, 10 min).

### [MEDIUM] `scoring/tracker.py` + `scoring/ledger.py` — direct DuckDB writes (open 5 days)

Both call `self._conn.execute(INSERT …)` / `self._conn.execute(UPDATE …)` directly, bypassing the `DbWriter` queue. Live-pipeline code paths. Concurrent calls risk locking.

- **Fix:** Inject and use a `DbWriter` in both classes, or verify and document they are always called from a single-threaded context with an exclusive connection.

### [MEDIUM] `contracts/registry.py` — direct DuckDB writes at startup (persistent)

`ContractRegistry` calls `conn.execute(INSERT OR REPLACE INTO contract_registry …)` and `conn.execute(UPDATE contract_registry …)` directly at initialization. Lower risk than live-path writes, but inconsistent with the single-writer convention and a hazard if registry refresh is triggered mid-run.

### [MEDIUM] `backtest/runner.py` — direct DuckDB writes (open 6 days)

`BacktestRunner` executes INSERT/UPDATE into `backtest_runs` and `backtest_predictions` directly. As an offline tool the risk is low, but the pattern diverges from the single-writer convention.

### [LOW] `pyproject.toml` `requires-python = ">=3.11"` (persistent)

Deployment uses `python:3.12-slim`; dev runs Python 3.11. Should be tightened to `>=3.12` to match production.

### [LOW] Phase 1 spec architecture divergence (persistent, intentional)

`docs/superpowers/specs/2026-03-30-parallax-phase1-design.md` describes an LLM agent swarm, H3 spatial layer, BigQuery, and WebSocket dashboard. The actual system is a prediction market edge-finder with none of those modules. Divergence is intentional per CLAUDE.md; the spec has no deprecation notice, causing it to re-trigger on every daily check.

- **Fix (5 min):** Prepend `> **DEPRECATED:** This spec describes the original Phase 1 design. The system pivoted to a prediction market edge-finder; see CLAUDE.md for the current architecture.`

---

## Test Suite

| Metric | 2026-09-19 | 2026-09-20 | Change |
|--------|-----------|-----------|--------|
| Total passed | 433 | 433 | 0 |
| Skipped | 13 | 13 | 0 |
| Warnings | 1 | 1 | 0 |
| Collection errors | 4 | 4 | 0 |
| Duration | ~169s | ~77s | faster (env cached) |

---

## Recommendations (priority order)

1. **Fix `np.trapz`** (5 min, 1 line): `scoring/selective.py:106` — `np.trapz` → `np.trapezoid`. Highest-severity, simplest fix; 9 days unfixed.
2. **Fix `ops/alerts.py` write** (30 min): Pass `DbWriter` into `DuckDBAlertSink`, replace direct `conn.execute` in `send()`. Eliminates the only live-async DuckDB write violation.
3. **Guard bench tests** (10 min, 4 lines): `pytest.importorskip("pandas")` at top of each of the 4 affected files so `pytest tests/` is clean without bench extras.
4. **Audit `scoring/tracker.py` + `scoring/ledger.py`** (30 min): Confirm single-threaded access or route writes through `DbWriter`.
5. **Archive stale spec** (5 min): Prepend deprecation notice to the Phase 1 design spec — stops daily re-flagging.
