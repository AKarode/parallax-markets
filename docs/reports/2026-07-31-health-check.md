# Parallax Health Check — 2026-07-31

**Status: YELLOW**

## Summary

No code was committed since yesterday's health check — the two HIGH issues flagged repeatedly (hardcoded `"opus"` in ensemble.py and dead `DbWriter`) remain unaddressed. Two new test failures surfaced when numpy was made available: `np.trapz` was removed in NumPy 2.0 and is used in `scoring/selective.py`, causing one production code bug and one test failure; `sklearn` is absent from all dependency groups, causing 5 test_recalibrators failures. Test suite now stands at **467 pass / 6 fail / 13 skip** (up from 433 pass when bench deps were absent).

---

## Issues Found

### [HIGH] `ensemble.py` line 128 — hardcoded `"opus"` in budget recording *(carry-over x3)*

- **File:** `backend/src/parallax/prediction/ensemble.py`, line 128
- `budget.record(resp.usage.input_tokens, resp.usage.output_tokens, "opus")` uses a hardcoded model string while the function already receives a `model` parameter. Opus pricing is 15× Haiku and 3× Sonnet; every call over-counts cost, triggering a false `is_over_budget()` that degrades the pipeline to rule-based-only mode prematurely.
- **Fix:** `budget.record(resp.usage.input_tokens, resp.usage.output_tokens, model)`

### [HIGH] `DbWriter` is dead code — single-writer invariant unenforced *(carry-over x3)*

- **File:** `backend/src/parallax/db/writer.py`
- `DbWriter` exists and has passing tests but is imported by zero application modules. All write-producing modules (`scoring/ledger.py`, `scoring/tracker.py`, `budget/tracker.py`, `ops/alerts.py`, `cli/brief.py`, `contracts/registry.py`, `backtest/runner.py`, etc.) write to DuckDB via direct synchronous `conn.execute()`, bypassing the queue entirely. This violates the Phase 1 spec single-writer topology and will produce write-write conflicts under concurrent FastAPI load.
- **Fix:** Wire `DbWriter` through `main.py` lifespan and migrate write-producing modules to `writer.enqueue()`, or explicitly document CLI-only single-threaded use and remove the `DbWriter` abstraction.

### [HIGH] `np.trapz` removed in NumPy 2.0, used in production code *(new)*

- **File:** `backend/src/parallax/scoring/selective.py`, line 106
- `np.trapz(risk, coverage)` raises `AttributeError: module 'numpy' has no attribute 'trapz'` on NumPy ≥ 2.0. The function `risk_coverage_auc()` is part of the scoring pipeline and would crash in production if invoked.
- **Confirmed:** numpy 2.4.6 is installed; `test_selective.py::test_risk_coverage_perfect_ranking` fails.
- **Fix:** Replace `np.trapz(...)` with `np.trapezoid(...)` (the NumPy 2.0 replacement).

### [MEDIUM] `sklearn` absent from all dependency groups — 5 test failures *(new)*

- **Files:** `backend/tests/test_recalibrators.py` (5 tests fail with `ModuleNotFoundError: No module named 'sklearn'`)
- `scoring/recalibrators.py` uses scikit-learn for isotonic regression and Platt scaling, but `scikit-learn` is not listed in `[dev]` or `[bench]` extras in `pyproject.toml`.
- **Fix:** Add `scikit-learn>=1.3` to the `[bench]` optional group (it's already used alongside numpy/pandas for calibration work).

### [MEDIUM] API endpoints `/api/predictions`, `/api/markets`, `/api/divergences` always return `[]` in production *(carry-over x3)*

- **File:** `backend/src/parallax/main.py`, lines 43–45
- `app.state.last_predictions/markets/divergences` are only populated via `POST /api/brief/run`. The CLI workflow (`python -m parallax.cli.brief`) calls `run_brief()` directly and never touches `app.state`, so the dashboard endpoints always serve empty lists when the server runs alongside CLI execution.
- **Fix:** Have these endpoints query `signal_ledger`, `market_prices`, and `prediction_log` directly from DuckDB.

### [MEDIUM] Blocking synchronous DB writes inside `async` functions *(carry-over x3)*

- **Files:** `ops/alerts.py` line 106 (`DuckDBAlertSink.send` is `async` but calls `conn.execute()` synchronously), `budget/tracker.py` line 43 (called from async brief paths)
- Blocks the FastAPI event loop on every alert or budget write. Low risk in CLI-only mode but a latency hazard under concurrent server load.
- **Fix:** Wrap with `asyncio.to_thread()` or route through `DbWriter` once wired.

### [MEDIUM] 4 bench test files fail on clean dev install *(carry-over)*

- **Files:** `tests/test_bench_forecast.py`, `tests/test_calibration_metrics.py`, `tests/test_recalibrators.py`, `tests/test_selective.py`
- All import `numpy` or `pandas`, which are only in the optional `[bench]` group. Running `pytest tests/` after `pip install -e ".[dev]"` causes collection interruption unless these files are explicitly excluded.
- **Fix:** Add `pytest.importorskip("numpy")` guards in affected test files, or move `numpy`/`pandas` into `[dev]`.

### [LOW] `portfolio/` and `config/` directories missing `__init__.py` *(carry-over x3)*

- Both directories are importable via hatchling auto-discovery but are not proper Python packages, which can break mypy, pyright, and editable installs with `--no-build-isolation`.
- **Fix:** `touch backend/src/parallax/portfolio/__init__.py backend/src/parallax/config/__init__.py`

### [LOW] Stale `BudgetTracker` pricing constants *(carry-over x3)*

- **File:** `backend/src/parallax/budget/tracker.py`, lines 10–13
- Hardcoded per-1K-token rates do not match current Anthropic API pricing. Causes minor over-counting in budget reports (less severe than the `"opus"` bug).

---

## Recommendations

1. **Fix `np.trapz` → `np.trapezoid` immediately** — this is a production crash waiting to happen if the scoring path is exercised on the current runtime environment.
2. **Fix the `"opus"` budget bug** — after 3 consecutive health checks this remains the most impactful correctness issue; it causes premature pipeline degradation on every run.
3. **Add `scikit-learn` to `[bench]`** in pyproject.toml to resolve the 5 test_recalibrators failures.
4. **Address or explicitly defer `DbWriter` dead code** — 3 checks without resolution suggests the single-writer invariant should be formally scoped out for the current CLI-only deployment mode and the dead code removed to reduce confusion.

---

## Metrics

| Metric | Value |
|---|---|
| Tests passing | 467 |
| Tests failing | 6 |
| Tests skipped | 13 |
| Open HIGH issues | 3 (2 carry-over, 1 new) |
| Open MEDIUM issues | 4 |
| Code commits since last check | 0 |
