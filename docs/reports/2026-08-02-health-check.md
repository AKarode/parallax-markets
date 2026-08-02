# Parallax Health Check — 2026-08-02

**Status: YELLOW**

## Summary

Zero code commits since the 2026-08-01 check; the three HIGH-severity bugs flagged for 5+ consecutive checks remain unresolved. Test results improved: **490 pass / 1 fail / 13 skip** (up from 485/6/13 yesterday). The 5 `test_recalibrators.py` failures that were reported yesterday no longer reproduce — they pass cleanly with `[dev,bench]` deps installed, indicating yesterday's sklearn "absent" finding was a misread (scikit-learn has been in `[bench]` since the initial commit). One failure remains: `test_selective.py::test_risk_coverage_perfect_ranking` — the `np.trapz` NumPy 2.0 crash, now on its 5th consecutive check without a fix.

---

## Issues Found

### [HIGH] `scoring/selective.py:106` — `np.trapz` removed in NumPy 2.0 *(carry-over ×5)*

- **File:** `backend/src/parallax/scoring/selective.py:106`
- `np.trapz(risk, coverage)` raises `AttributeError: module 'numpy' has no attribute 'trapz'` on NumPy ≥ 2.0. NumPy 2.4.6 is installed. This is the only test failure in today's run.
- The `risk_coverage_auc()` function crashes in production whenever the selective scoring path is exercised.
- **Fix:** Replace `np.trapz(...)` with `np.trapezoid(...)` — a one-liner that resolves the failure immediately.

### [HIGH] `prediction/ensemble.py:128` — hardcoded `"opus"` in budget recording *(carry-over ×5)*

- **File:** `backend/src/parallax/prediction/ensemble.py:128`
- `budget.record(resp.usage.input_tokens, resp.usage.output_tokens, "opus")` ignores the actual `model` parameter. Opus pricing is 15× Haiku and 3× Sonnet, so every ensemble call over-bills, prematurely triggering `is_over_budget()` and degrading the pipeline to rule-based-only mode on live runs.
- **Fix:** `budget.record(resp.usage.input_tokens, resp.usage.output_tokens, model)`

### [HIGH] `DbWriter` is dead code — single-writer invariant unenforced *(carry-over ×5)*

- **File:** `backend/src/parallax/db/writer.py`
- `DbWriter` has passing unit tests but is imported by zero application modules. All write-producing modules call `conn.execute()` directly: `scoring/prediction_log.py` (INSERT into prediction_log), `scoring/resolution.py` (UPDATE signal_ledger, UPDATE trade_positions), `scoring/scorecard.py` (INSERT into daily_scorecard), `ops/alerts.py` (INSERT into ops_events), `budget/tracker.py` (INSERT into llm_usage), `contracts/registry.py` (INSERT OR REPLACE, DELETE), `cli/brief.py` (multiple writes).
- The spec mandates all writes go through `asyncio.Queue → db_writer`. The current pattern will produce write-write conflicts under concurrent FastAPI load.
- **Fix:** Wire `DbWriter` through `main.py` lifespan and migrate write paths, or explicitly document CLI-only scope and remove the dead abstraction.

### [MEDIUM] API state endpoints always return `[]` in CLI-driven deployments *(carry-over ×5)*

- **File:** `backend/src/parallax/main.py:43–45`
- `/api/predictions`, `/api/markets`, `/api/divergences` read from `app.state.last_*` which is only populated by `POST /api/brief/run`. The CLI path (`python -m parallax.cli.brief`) bypasses `app.state`, so the dashboard always serves empty arrays unless triggered via the REST endpoint explicitly.
- **Fix:** Have endpoints query `signal_ledger` / `market_prices` / `prediction_log` from DuckDB directly instead of in-memory state.

### [MEDIUM] Blocking synchronous DB writes inside `async` functions *(carry-over ×5)*

- **Files:** `ops/alerts.py:106` (`DuckDBAlertSink.send` is declared `async` but calls synchronous `conn.execute()`), `budget/tracker.py:43` (synchronous INSERT called from async brief paths).
- Blocks the FastAPI event loop on every alert or budget write. Safe in current CLI-only usage; becomes a latency hazard under any concurrent server load.
- **Fix:** Wrap blocking calls with `asyncio.to_thread()` or route through `DbWriter` once wired.

### [MEDIUM] Bench test files fail on clean `[dev]`-only install *(carry-over ×5)*

- **Files:** `tests/test_bench_forecast.py`, `tests/test_calibration_metrics.py`, `tests/test_recalibrators.py`, `tests/test_selective.py`
- These files import `numpy`, `pandas`, or `sklearn` (all in `[bench]`). Running `pip install -e ".[dev]" && pytest tests/` fails collection on these four files. Today's run used `[dev,bench]` which gives 490/1/13; a clean `[dev]`-only install gives collection errors on ~40 bench tests.
- **Fix:** Add `pytest.importorskip("numpy")` guards at the top of each affected test file, or move `numpy`/`pandas` into `[dev]`.

### [LOW] Missing `__init__.py` in `portfolio/` and `config/` *(carry-over ×5)*

- **Files:** `backend/src/parallax/portfolio/`, `backend/src/parallax/config/`
- Both directories lack `__init__.py`. Hatchling auto-discovery works around this, but type checkers and `--no-build-isolation` editable installs may break.
- **Fix:** `touch backend/src/parallax/portfolio/__init__.py backend/src/parallax/config/__init__.py`

### [LOW] `pyproject.toml` specifies `requires-python = ">=3.11"` but project targets Python 3.12 *(carry-over)*

- **File:** `backend/pyproject.toml:4`
- CLAUDE.md states Python 3.12+. The `>=3.11` floor permits installation on 3.11, which can mask 3.12-specific syntax.
- **Fix:** `requires-python = ">=3.12"`

### [LOW] Stale `BudgetTracker` pricing constants *(carry-over ×5)*

- **File:** `backend/src/parallax/budget/tracker.py:10–13`
- Per-token rates are stale. Minor over/under-counting in budget reports and cost estimates.

---

## Correction to Prior Report

Yesterday's [MEDIUM] finding "sklearn absent from all dependency groups" was inaccurate. `scikit-learn>=1.3` has been present in `[bench]` since the initial commit (2026-07-08). The 5 `test_recalibrators.py` failures reported previously do not reproduce today with `[dev,bench]` installed. The test count improvement (485→490 pass, 6→1 fail) reflects running with both dependency groups, not a code fix.

---

## Architecture Note (informational)

The Phase 1 spec describes a 50-agent geopolitical cascade simulator with H3 spatial visualization, BigQuery/GDELT ingestion, and a structured eval framework. The current implementation is a prediction market edge-finder (3 focused LLM models, Kalshi/Polymarket comparison, paper trading). This is an intentional product pivot documented in CLAUDE.md. Spec-defined modules (`agents/`, `spatial/`, `eval/`, `api/`) were never built; they are not bugs.

---

## Recommendations (priority order)

1. **Fix `np.trapz` → `np.trapezoid` in `scoring/selective.py:106`** — one-liner, clears the only failing test, prevents a production crash.
2. **Fix `"opus"` → `model` in `prediction/ensemble.py:128`** — prevents premature budget exhaustion on every live run.
3. **Formally resolve `DbWriter`** — wire it or remove it; 5 checks without resolution.
4. **Add `pytest.importorskip("numpy")` guards** in bench test files — fixes clean `[dev]` install collection failure.

---

## Metrics

| Metric | Value |
|---|---|
| Tests passing | 490 |
| Tests failing | 1 |
| Tests skipped | 13 |
| Open HIGH issues | 3 (all carry-over) |
| Open MEDIUM issues | 3 (all carry-over) |
| Open LOW issues | 3 (all carry-over) |
| Code commits since last check | 0 |
| Consecutive checks with no code fix | 5+ |
