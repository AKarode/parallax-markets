# Parallax Health Check — 2026-08-03

**Status: YELLOW**

## Summary

No code commits since 2026-08-02 (only a tech research doc was added). All HIGH/MEDIUM/LOW bugs flagged in prior checks remain unresolved — they are now on their 6th consecutive check without a fix. Test results are unchanged: **490 pass / 1 fail / 13 skip** (same count as yesterday). The single test failure is `test_selective.py::test_risk_coverage_perfect_ranking` caused by the `np.trapz` NumPy 2.0 regression.

---

## Issues Found

### [HIGH] `scoring/selective.py:106` — `np.trapz` removed in NumPy 2.0 *(carry-over ×6)*

- **File:** `backend/src/parallax/scoring/selective.py:106`
- `np.trapz(risk, coverage)` raises `AttributeError: module 'numpy' has no attribute 'trapz'` on NumPy ≥ 2.0. NumPy 2.4.6 is installed. This is the only test failure in today's run and also crashes the `risk_coverage_auc()` production path.
- **Fix:** Replace `np.trapz(...)` with `np.trapezoid(...)` — a one-liner.

### [HIGH] `prediction/ensemble.py:128` — hardcoded `"opus"` in budget recording *(carry-over ×6)*

- **File:** `backend/src/parallax/prediction/ensemble.py:128`
- `budget.record(resp.usage.input_tokens, resp.usage.output_tokens, "opus")` ignores the actual `model` parameter. Opus pricing is ~15× Haiku and ~3× Sonnet, so every ensemble call over-bills, prematurely triggering `is_over_budget()` and degrading the pipeline to rule-based-only mode.
- **Fix:** `budget.record(resp.usage.input_tokens, resp.usage.output_tokens, model)`

### [HIGH] `DbWriter` is dead code — single-writer invariant unenforced *(carry-over ×6)*

- **File:** `backend/src/parallax/db/writer.py`
- `DbWriter` has passing unit tests but is imported by zero application modules. All write-producing modules call `conn.execute()` directly: `scoring/prediction_log.py` (INSERT prediction_log), `scoring/resolution.py` (UPDATE signal_ledger, UPDATE trade_positions), `scoring/scorecard.py` (INSERT daily_scorecard), `ops/alerts.py` (INSERT ops_events), `budget/tracker.py` (INSERT llm_usage), `contracts/registry.py` (INSERT OR REPLACE, DELETE), `cli/brief.py` (multiple writes).
- The spec mandates all writes go through `asyncio.Queue → db_writer`. This pattern will produce write-write conflicts under concurrent FastAPI load.
- **Fix:** Wire `DbWriter` through `main.py` lifespan and migrate write paths, or explicitly document CLI-only scope and formally remove the dead abstraction.

### [MEDIUM] API state endpoints always return `[]` in CLI-driven deployments *(carry-over ×6)*

- **File:** `backend/src/parallax/main.py:43–45`
- `/api/predictions`, `/api/markets`, `/api/divergences` read from `app.state.last_*` which is only populated by `POST /api/brief/run`. The CLI path (`python -m parallax.cli.brief`) bypasses `app.state`, so the dashboard always serves empty arrays unless triggered via the REST endpoint.
- **Fix:** Have these endpoints query `signal_ledger` / `market_prices` / `prediction_log` from DuckDB directly instead of in-memory state.

### [MEDIUM] Blocking synchronous DB writes inside `async` functions *(carry-over ×6)*

- **Files:** `ops/alerts.py:106` (`DuckDBAlertSink.send` is declared `async` but calls synchronous `conn.execute()`), `budget/tracker.py:43` (synchronous INSERT called from async brief paths).
- Blocks the FastAPI event loop on every alert or budget write. Safe in current CLI-only usage; becomes a latency hazard under any concurrent server load.
- **Fix:** Wrap blocking calls with `asyncio.to_thread()` or route through `DbWriter` once wired.

### [MEDIUM] Bench test files fail on clean `[dev]`-only install *(carry-over ×6)*

- **Files:** `tests/test_bench_forecast.py`, `tests/test_calibration_metrics.py`, `tests/test_recalibrators.py`, `tests/test_selective.py`
- These files import `numpy`, `pandas`, or `sklearn` (all in `[bench]`). Running `pip install -e ".[dev]" && pytest tests/` fails collection on these four files. Today's run used `[dev,bench]` which gives 490/1/13; a clean `[dev]`-only install gives collection errors on ~40 bench tests.
- **Fix:** Add `pytest.importorskip("numpy")` guards at the top of each affected test file, or move `numpy` into `[dev]`.

### [LOW] Missing `__init__.py` in `portfolio/` and `config/` *(carry-over ×6)*

- **Files:** `backend/src/parallax/portfolio/`, `backend/src/parallax/config/`
- Both directories lack `__init__.py`. Hatchling auto-discovery works around this, but type checkers and `--no-build-isolation` editable installs may break.
- **Fix:** `touch backend/src/parallax/portfolio/__init__.py backend/src/parallax/config/__init__.py`

### [LOW] `pyproject.toml` specifies `requires-python = ">=3.11"` but project targets Python 3.12 *(carry-over)*

- **File:** `backend/pyproject.toml:4`
- CLAUDE.md states Python 3.12+. The `>=3.11` floor permits installation on 3.11, which can mask 3.12-specific syntax.
- **Fix:** `requires-python = ">=3.12"`

### [LOW] Stale `BudgetTracker` pricing constants *(carry-over ×6)*

- **File:** `backend/src/parallax/budget/tracker.py:10–13`
- Per-token rates are stale. Minor over/under-counting in budget reports and cost estimates relative to current Anthropic pricing.

---

## Architecture Note (informational)

The Phase 1 spec describes a 50-agent geopolitical cascade simulator with H3 spatial visualization, BigQuery/GDELT ingestion, and a structured eval framework. The current implementation is a prediction market edge-finder (3 focused LLM models, Kalshi/Polymarket comparison, paper trading). This is an intentional product pivot documented in CLAUDE.md. Spec-defined modules (`agents/`, `spatial/`, `eval/`, `api/`) were never built; they are not bugs. The tech research doc added today (2026-08-02) covers AIS integration, Batch API cost reduction, and H3 optimization — suggesting potential upcoming expansion back toward spatial/fleet-tracking capabilities.

---

## Recommendations (priority order)

1. **Fix `np.trapz` → `np.trapezoid` in `scoring/selective.py:106`** — one-liner, clears the only failing test, prevents a live crash.
2. **Fix `"opus"` → `model` in `prediction/ensemble.py:128`** — one-liner, prevents premature budget exhaustion on every live run.
3. **Formally resolve `DbWriter`** — wire it through `main.py` or delete it. 6 checks without resolution.
4. **Add `pytest.importorskip("numpy")` guards** in bench test files — fixes clean `[dev]` install collection failure.

---

## Metrics

| Metric | Value |
|---|---|
| Tests passing | 490 |
| Tests failing | 1 |
| Tests skipped | 13 |
| Open HIGH issues | 3 (all carry-over ×6) |
| Open MEDIUM issues | 3 (all carry-over ×6) |
| Open LOW issues | 3 (all carry-over) |
| Code commits since last check | 0 |
| Consecutive checks with no code fix | 6 |
