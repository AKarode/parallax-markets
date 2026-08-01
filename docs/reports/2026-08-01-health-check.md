# Parallax Health Check — 2026-08-01

**Status: YELLOW**

## Summary

Zero code commits since the 2026-07-31 check — all four HIGH/MEDIUM issues flagged repeatedly remain unaddressed. Test results are effectively unchanged at **485 pass / 6 fail / 13 skip** (yesterday's report showed 467 pass because numpy/pandas were not installed during that collection run; the underlying failures are identical). The three hardest-hitting issues — hardcoded `"opus"` in budget recording, `DbWriter` dead code, and `np.trapz` crash on NumPy ≥ 2.0 — have been open for 4+ consecutive checks with no fix landed.

---

## Issues Found

### [HIGH] `ensemble.py` line 128 — hardcoded `"opus"` in budget recording *(carry-over ×4)*

- **File:** `backend/src/parallax/prediction/ensemble.py:128`
- `budget.record(resp.usage.input_tokens, resp.usage.output_tokens, "opus")` ignores the `model` parameter. Opus pricing is 15× Haiku and 3× Sonnet, so every call over-bills, prematurely triggering `is_over_budget()` and degrading the pipeline to rule-based-only mode.
- **Fix:** `budget.record(resp.usage.input_tokens, resp.usage.output_tokens, model)`

### [HIGH] `DbWriter` is dead code — single-writer invariant unenforced *(carry-over ×4)*

- **File:** `backend/src/parallax/db/writer.py`
- `DbWriter` has passing unit tests but is imported by zero application modules. All write-producing modules (`scoring/ledger.py`, `scoring/tracker.py`, `budget/tracker.py`, `ops/alerts.py`, `cli/brief.py`, `contracts/registry.py`, `backtest/runner.py`) call `conn.execute()` directly, violating the Phase 1 spec single-writer topology. Will cause write-write conflicts under concurrent FastAPI load.
- **Fix:** Wire `DbWriter` through `main.py` lifespan and migrate write paths, or explicitly document CLI-only scope and remove the dead abstraction.

### [HIGH] `np.trapz` removed in NumPy 2.0 — production crash on current runtime *(carry-over ×2)*

- **File:** `backend/src/parallax/scoring/selective.py:106`
- `np.trapz(risk, coverage)` raises `AttributeError: module 'numpy' has no attribute 'trapz'` on NumPy ≥ 2.0. NumPy 2.4.6 is installed. `test_selective.py::test_risk_coverage_perfect_ranking` fails. The `risk_coverage_auc()` function would crash in production if invoked in the scoring path.
- **Fix:** Replace `np.trapz(...)` with `np.trapezoid(...)`.

### [MEDIUM] `sklearn` absent from all dependency groups — 5 test failures *(carry-over ×2)*

- **Files:** `backend/tests/test_recalibrators.py` (5 tests fail: `ModuleNotFoundError: No module named 'sklearn'`)
- `scoring/recalibrators.py` uses scikit-learn for isotonic regression and Platt scaling, but `scikit-learn` appears in neither `[dev]` nor `[bench]` extras in `pyproject.toml`. The `[bench]` group lists `numpy`, `pandas`, `pyarrow`, `matplotlib`, `huggingface_hub` but omits `scikit-learn`.
- **Fix:** Add `scikit-learn>=1.3` to the `[bench]` optional group.

### [MEDIUM] API state endpoints always return `[]` in CLI-driven deployments *(carry-over ×4)*

- **File:** `backend/src/parallax/main.py:43–45`
- `/api/predictions`, `/api/markets`, `/api/divergences` read from `app.state.last_*` which is only populated via `POST /api/brief/run`. The CLI path (`python -m parallax.cli.brief`) bypasses `app.state`, so the dashboard always serves empty data unless triggered via the API endpoint.
- **Fix:** Have endpoints query `signal_ledger` / `market_prices` / `prediction_log` from DuckDB directly.

### [MEDIUM] Blocking synchronous DB writes inside `async` functions *(carry-over ×4)*

- **Files:** `ops/alerts.py:106` (`DuckDBAlertSink.send` is `async` but calls synchronous `conn.execute()`), `budget/tracker.py:43` (called from async brief paths)
- Blocks the FastAPI event loop on every alert or budget write. Safe in CLI-only mode; a latency hazard under concurrent server load.
- **Fix:** Wrap with `asyncio.to_thread()` or route through `DbWriter` once wired.

### [MEDIUM] Bench test files fail on clean `[dev]` install *(carry-over ×4)*

- **Files:** `tests/test_bench_forecast.py`, `tests/test_calibration_metrics.py`, `tests/test_recalibrators.py`, `tests/test_selective.py`
- All import `numpy` or `pandas`, which live in the optional `[bench]` group. `pytest tests/` after `pip install -e ".[dev]"` fails collection on these four files. Yesterday's health check ran without these deps, causing an under-count in the pass total (467 reported vs 485 actual when deps are present).
- **Fix:** Add `pytest.importorskip("numpy")` guards at the top of each affected test file, or move `numpy`/`pandas` into `[dev]`.

### [LOW] Missing `__init__.py` in `portfolio/` and `config/` *(carry-over ×4)*

- **Files:** `backend/src/parallax/portfolio/`, `backend/src/parallax/config/`
- Importable via hatchling auto-discovery but not formal Python packages; can break type checkers and editable installs with `--no-build-isolation`.
- **Fix:** `touch backend/src/parallax/portfolio/__init__.py backend/src/parallax/config/__init__.py`

### [LOW] `pyproject.toml` specifies `requires-python = ">=3.11"` but project targets Python 3.12 *(carry-over)*

- **File:** `backend/pyproject.toml:4`
- CLAUDE.md states Python 3.12+. The `>=3.11` floor allows installation on Python 3.11, which may mask 3.12-specific syntax usage (e.g., `type X = ...`).
- **Fix:** Change to `requires-python = ">=3.12"`.

### [LOW] Stale `BudgetTracker` pricing constants *(carry-over ×4)*

- **File:** `backend/src/parallax/budget/tracker.py:10–13`
- Hardcoded per-1K-token rates are not current. Minor over-counting in budget reports.

---

## Architecture Note (informational)

The Phase 1 spec describes a 50-agent geopolitical cascade simulator with H3 spatial visualization, BigQuery/GDELT ingestion, and a structured eval framework. The current implementation is a prediction market edge-finder (3 focused LLM models, Kalshi/Polymarket market comparison, paper trading). This divergence is intentional and documented in CLAUDE.md — the spec represents the original vision; the codebase reflects a deliberate product pivot. Several spec-defined modules (`agents/`, `spatial/`, `eval/`, `api/`) were never built; they are not bugs but out-of-scope for the current direction.

---

## Recommendations

1. **Fix `np.trapz` → `np.trapezoid`** — one-liner, prevents a production crash if the scoring path is exercised.
2. **Fix `"opus"` budget bug** — 4 consecutive checks without action; causes premature pipeline degradation on every live run.
3. **Add `scikit-learn>=1.3` to `[bench]` in pyproject.toml** — resolves 5 persistent test failures.
4. **Add `pytest.importorskip("numpy")` guards** in `test_bench_forecast.py`, `test_calibration_metrics.py`, `test_recalibrators.py`, `test_selective.py` — fixes clean-install collection interruption.
5. **Formally resolve `DbWriter`** — 4 checks without resolution; either wire it or remove it to eliminate the misleading abstraction.

---

## Metrics

| Metric | Value |
|---|---|
| Tests passing | 485 |
| Tests failing | 6 |
| Tests skipped | 13 |
| Open HIGH issues | 3 (all carry-over) |
| Open MEDIUM issues | 4 (all carry-over) |
| Open LOW issues | 3 (all carry-over) |
| Code commits since last check | 0 |
| Consecutive checks with no code fix | 4+ |
