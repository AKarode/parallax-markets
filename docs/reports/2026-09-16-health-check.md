# Parallax Health Check — 2026-09-16

**Status: YELLOW**

The core test suite is healthy (433 passed, 13 skipped), but four issues flagged in the Sep 15 report remain unresolved — no fixes landed in the two commits since then (only report/tech-research additions). Three new findings were surfaced today: `scoring/tracker.py` and `scoring/ledger.py` have direct `conn.execute()` write calls that bypass the `DbWriter` queue, and `contracts/registry.py` similarly performs direct INSERTs/UPDATEs at startup.

---

## Summary

- **Test suite:** 433 passed, 13 skipped, 1 warning in ~82s (4 files excluded due to missing `[bench]` deps)
- **No new regressions** introduced since Sep 15
- **Recurring issues not yet fixed:** `np.trapz`, `ops/alerts.py` write violation, bench test import failures

---

## Issues Found

### [HIGH] `np.trapz` removed in NumPy 2.x — `scoring/selective.py:106` (persisting)

`scoring/selective.py:106` calls `np.trapz(risk, coverage)`. `numpy.trapz` was removed in NumPy 2.0; the replacement is `np.trapezoid` (available since NumPy 1.23). This will raise `AttributeError` at runtime in any NumPy 2.x environment. This has been flagged since Sep 13 with no fix.
- **Fix:** Replace `np.trapz` with `np.trapezoid` on line 106.

### [HIGH] DuckDB single-writer violation — `ops/alerts.py:106` (persisting)

`DuckDBAlertSink.send()` in `ops/alerts.py` calls `self.db_conn.execute("INSERT INTO ops_events …")` directly rather than enqueuing through the `asyncio.Queue`-based `DbWriter`. This is an `async` method in the live pipeline and can cause `database is locked` errors under concurrent load. Flagged since Sep 12 with no fix.
- **Fix:** Route through `DbWriter.enqueue()`.

### [HIGH] 4 bench test files fail to import — missing import guards (persisting)

`test_bench_forecast.py`, `test_calibration_metrics.py`, `test_recalibrators.py`, and `test_selective.py` all fail collection (`ModuleNotFoundError` for `pandas`, `numpy`, `sklearn`) because their required deps are in `[project.optional-dependencies.bench]`, not in `[dev]`. A bare `pip install -e ".[dev]"` cannot collect these tests. No `pytest.importorskip` guards added. Flagged since Sep 12.
- **Fix:** Add `pytest.importorskip("pandas")` / `pytest.importorskip("numpy")` at the top of each file, OR move `numpy`, `pandas`, `scikit-learn` into `[dev]` extras.

### [MEDIUM] `scoring/tracker.py` and `scoring/ledger.py` — direct DuckDB writes (new)

Both files contain direct `self._conn.execute(INSERT …)` and `self._conn.execute(UPDATE …)` calls:
- `scoring/tracker.py`: INSERTs into `trade_positions`, `trade_orders`, `trade_fills` and UPDATEs (lines ~460, 516, 672, 711, 744)
- `scoring/ledger.py`: INSERT/UPDATE into `signal_ledger` (lines 225, 256)

These are live-pipeline writes that bypass the `DbWriter` queue. If the live process (FastAPI + background tasks) ever concurrently hits these paths, `database is locked` errors are possible. Whether these run on an exclusive connection at all times is unclear from the code.
- **Fix:** Inject and use a `DbWriter` instance in both classes, or document that they are always called from a single-threaded context with an exclusive connection.

### [MEDIUM] `contracts/registry.py` — direct DuckDB writes at startup (persisting)

`ContractRegistry` calls `self._conn.execute(INSERT OR REPLACE INTO contract_registry …)` and `self._conn.execute(UPDATE contract_registry …)` directly (lines 85, 105, 114, 198). These are initialization-time writes that happen before the async pipeline starts, which is lower risk — but the pattern diverges from the single-writer convention and could cause issues if the registry is ever refreshed mid-run.
- **Fix:** Route through `DbWriter` or clearly document this is a setup-only path with an exclusive connection.

### [MEDIUM] `backtest/runner.py` — direct DuckDB writes (persisting)

`BacktestRunner` calls `self._conn.execute()` with INSERT/UPDATE into `backtest_runs` and `backtest_predictions` (lines 292, 310, 331, 358). The backtest is an offline tool with its own exclusive connection, so this is not an immediate risk. The pattern is inconsistent with the single-writer convention. Flagged since Sep 15.

### [LOW] `pyproject.toml` `requires-python = ">=3.11"` (persisting)

Deployment target is Python 3.12 (Docker uses `python:3.12-slim`), but the constraint allows 3.11. Current environment is Python 3.11 (`Python 3.11.15`), meaning tests run on a different version than production. Tighten to `>=3.12`.

### [LOW] Phase 1 spec architecture divergence (persisting, intentional)

`docs/superpowers/specs/2026-03-30-parallax-phase1-design.md` describes an LLM agent swarm, H3 spatial layer, BigQuery integration, and WebSocket dashboard. None of this is implemented. The actual system is a prediction market edge-finder. The frontend (`package.json`) has React + Recharts only — no deck.gl, no MapLibre, no WebSocket hooks. This divergence is intentional per CLAUDE.md but the spec remains uncorrected, causing daily re-flagging.
- **Fix:** Add a one-line deprecation note at the top of the spec doc noting the pivot.

---

## Recommendations

1. **Fix `np.trapz`** (5-minute fix): `s/np.trapz/np.trapezoid/` at `scoring/selective.py:106`. Resolves HIGH issue that has been open for 4 days.
2. **Fix `ops/alerts.py` write**: Pass a `DbWriter` instance into `DuckDBAlertSink` and replace the direct `conn.execute` with `await self._db_writer.enqueue(...)`. Resolves HIGH single-writer violation open for 5 days.
3. **Guard bench tests**: Add `pytest.importorskip("pandas")` / `pytest.importorskip("numpy")` at the top of the 4 affected test files. One-line fix per file; unblocks `pytest tests/` running cleanly without bench extras.
4. **Audit `scoring/tracker.py` + `scoring/ledger.py`**: Determine if these are called exclusively single-threaded. If not, route writes through `DbWriter`. This is the most significant new finding today.
5. **Archive stale spec**: Prepend a deprecation notice to the Phase 1 design spec to stop triggering daily re-flags.
