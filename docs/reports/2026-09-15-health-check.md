# Parallax Health Check — 2026-09-15

**Status: YELLOW**

The core test suite remains healthy (433 passed, 13 skipped, 0 failures on runnable tests), but three issues flagged in the Sep 14 report are still unresolved and a new operational finding has appeared: four days of health-check commits (Sep 12–14) landed on a detached HEAD and were never pushed to `main`, creating a gap in the audit trail.

---

## Issues Found

### [HIGH] 4-day commit gap — detached HEAD not pushed to main

- **[HIGH]** The Sep 12, 13, and 14 health-check runs each committed reports to a detached HEAD rather than to `main`. Six commits (`241610e`, `566dd3e`, `b45155c`, `251a753`, `ff73b7d`, `ff73b7d`) are now orphaned and will eventually be garbage-collected. `origin/main` is at the Sep 11 commit (`4e3d5fc`). The reports for Sep 12–14 do not exist on disk on `main`. **This session is the first to write to `main` since Sep 11.**
  - Root cause: the scheduled health-check agent ran in detached HEAD mode instead of on a named branch. The push step still succeeded from the agent's perspective (detached HEAD pushes to `origin/HEAD`), but the remote `main` branch was not updated.
  - Fix: ensure the health-check runner always does `git checkout main && git pull` before committing, or uses `git push origin HEAD:main`.

### [HIGH] 6 test files fail to import (numpy/scikit-learn not in dev extras)

- **[HIGH]** `numpy>=1.26` and `scikit-learn>=1.3` are in `[project.optional-dependencies.bench]` only. A plain `pip install -e ".[dev]"` install cannot import `numpy` or `sklearn`, causing collection errors in:
  - `tests/test_bench_forecast.py` — `ModuleNotFoundError: No module named 'pandas'`
  - `tests/test_recalibrators.py` — `ModuleNotFoundError: No module named 'sklearn'` (5 tests)
  - `tests/test_selective.py` — fails to import due to missing numpy
  - `tests/test_calibration_metrics.py` — `ModuleNotFoundError: No module named 'numpy'`
  - Fix: add `numpy>=1.26`, `scikit-learn>=1.3`, `pandas>=2.0` to `[project.optional-dependencies.dev]` in `pyproject.toml`, or guard with `pytest.importorskip`.

### [HIGH] `np.trapz` removed in NumPy 2.x (scoring/selective.py:106)

- **[HIGH]** `scoring/selective.py:106` calls `np.trapz(risk, coverage)`. `numpy.trapz` was removed in NumPy 2.0; the replacement is `np.trapezoid` (available since NumPy 1.23). This will raise `AttributeError` at runtime in any NumPy 2.x environment. Fix: replace with `np.trapezoid`.

### [HIGH] DuckDB single-writer violation — ops/alerts.py:106

- **[HIGH]** `DuckDBAlertSink.send()` in `ops/alerts.py` calls `self.db_conn.execute("INSERT INTO ops_events …")` directly without going through the `asyncio.Queue`-based `DbWriter`. This is an `async` method and can cause `database is locked` errors under concurrent load. Fix: enqueue through `DbWriter` instead of calling `conn.execute` directly.

### [MEDIUM] backtest/runner.py uses direct DuckDB writes

- **[MEDIUM]** `BacktestRunner` calls `self._conn.execute()` with INSERT/UPDATE for `backtest_runs` and `backtest_predictions` tables (lines 292, 310, 331, 358). While the backtest module is an offline tool with an exclusive connection (not the live pipeline), the pattern is inconsistent with the single-writer convention and could cause issues if the backtest is ever run concurrently with the live system. Not an immediate fire, but worth aligning.

### [LOW] Python version constraint loosened (pyproject.toml)

- **[LOW]** `pyproject.toml` declares `requires-python = ">=3.11"` but the deployment target is Python 3.12 (Docker uses `python:3.12-slim`). Tighten to `>=3.12` to prevent accidental installs on 3.11 that could mask incompatibilities.

### [LOW] Spec/Plan architecture divergence (unchanged, intentional)

- **[LOW]** The Phase 1 design spec (`docs/superpowers/specs/2026-03-30-parallax-phase1-design.md`) describes an LLM agent swarm with H3 spatial layer and BigQuery, none of which is implemented. The actual system is a prediction market edge-finder. This divergence is intentional per CLAUDE.md but the stale spec misleads automated checks. Add a deprecation notice at the top of the spec doc.

---

## Recommendations

1. **Fix the detached HEAD push issue** (operational priority): Update the health-check scheduled task to always checkout `main`, pull, commit, and push to `main` explicitly (`git push origin HEAD:main`). Verify `origin/main` advances after each run.
2. **Fix numpy/sklearn in dev deps**: Add `numpy>=1.26`, `scikit-learn>=1.3`, `pandas>=2.0` to `dev` extras in `pyproject.toml`, or add `pytest.importorskip` guards to bench-specific test files. This resolves 4 import errors and makes the full `pytest tests/` clean.
3. **Fix np.trapz**: Replace `np.trapz` with `np.trapezoid` at `scoring/selective.py:106`.
4. **Fix alerts.py DB write**: Route `DuckDBAlertSink.send()` through `DbWriter.enqueue()` to honour the single-writer constraint.
5. **Archive stale spec**: Add a one-line note at the top of the Phase 1 design spec noting the project pivoted; prevents daily re-flagging.
