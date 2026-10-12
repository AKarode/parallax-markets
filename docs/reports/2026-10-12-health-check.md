# Parallax Health Check — 2026-10-12

**Status: YELLOW**

The pipeline remains functional with 47 test files and 375+ passing tests, but two tests are now failing due to dependency-environment mismatches (NumPy 2.x API removal, missing sklearn). The DuckDB single-writer violation (11 production files) and architecture drift from the Phase 1 spec remain unresolved from prior reports.

---

## Issues Found

### CRITICAL

- **[CRITICAL] DuckDB single-writer constraint violated across 11 production files — unresolved for 4 days.**
  The `DbWriter` asyncio.Queue pattern exists in `db/writer.py` but is bypassed by every actual write path. All write-side modules call `conn.execute()` directly for INSERT/UPDATE/DELETE:
  - `scoring/ledger.py`, `scoring/prediction_log.py`, `scoring/resolution.py`, `scoring/scorecard.py`, `scoring/tracker.py`
  - `ops/alerts.py`
  - `ingestion/crisis_ingester.py`
  - `contracts/registry.py`
  - `cli/brief.py`
  - `budget/tracker.py`
  - `backtest/runner.py`

  No change in footprint; no new violations introduced.

### HIGH

- **[HIGH][NEW] `np.trapz` removed in NumPy 2.x — test failure introduced.**
  `scoring/selective.py:106` calls `np.trapz(risk, coverage)`. NumPy 2.0 removed this alias (deprecated since 1.20); the installed version is 2.5.3. The replacement is `np.trapezoid`. This breaks `test_selective.py::test_risk_coverage_perfect_ranking` and means `risk_coverage_auc` silently falls through to an `AttributeError` in production if the selective-trading path is exercised.

  Fix: change `selective.py:106` from `np.trapz` to `np.trapezoid`.

- **[HIGH][NEW] `sklearn.isotonic` import in `scoring/recalibrators.py` fails without `bench` extras.**
  `IsotonicRecalibrator.fit()` does a lazy `from sklearn.isotonic import IsotonicRegression`. `scikit-learn` is only in `pyproject.toml`'s `[bench]` optional group, not `[project]` dependencies. `test_recalibrators.py::test_isotonic_is_monotone_and_improves_calibration` fails accordingly. Any production caller of `IsotonicRecalibrator` without the bench extras installed will get a `ModuleNotFoundError` at runtime.

  Fix: either add `scikit-learn` to core dependencies or guard the import with a helpful error message.

- **[HIGH] Architecture drift: `agents/`, `eval/`, `api/`, `spatial/` subpackages still absent.**
  The Phase 1 spec's 50-agent LLM swarm, eval framework, H3 spatial model, and WebSocket API remain unbuilt. Tables `agent_memory`, `agent_prompts`, `decisions`, `world_state_delta`, and `eval_results` hold no data. `simulation/engine.py` and `simulation/circuit_breaker.py` remain absent. `cascade.py` and `world_state.py` are tested but wired to no production flow.

- **[HIGH] Dashboard prediction endpoints still silently return empty arrays on cold start.**
  `app.state.last_predictions`, `.last_markets`, `.last_divergences` are initialised as `[]` in `main.py` lifespan. No background task updates them on a schedule; only a manual `POST /api/brief/run` triggers a refresh.

### MEDIUM

- **[MEDIUM] Missing pyproject.toml dependencies.**
  `h3`, `sentence-transformers`, and `websockets` are referenced in the spec/schema but absent from `pyproject.toml`. Prerequisites for future `spatial/`, `ingestion/dedup.py`, and WebSocket work.

- **[MEDIUM] No WebSocket real-time push.**
  Frontend uses polling only. Neither backend nor frontend has WebSocket infrastructure.

- **[MEDIUM] Test coverage gaps for financially sensitive modules.**
  No dedicated tests for `portfolio/allocator.py`, `prediction/oil_price.py`, `prediction/ceasefire.py`, `prediction/hormuz.py`, `backtest/engine.py`, `backtest/report.py`, or `ops/runtime.py`.

### LOW

- **[LOW] Python version mismatch: `pyproject.toml` requires `>=3.11`, CLAUDE.md specifies Python 3.12.**

- **[LOW] Missing `__init__.py` in `portfolio/` and `config/` directories.**

---

## Test Summary

| Run | Passed | Failed | Skipped |
|-----|--------|--------|---------|
| Full suite (python3.13) | 375 | 2 | 13 |

Failing tests:
- `tests/test_recalibrators.py::test_isotonic_is_monotone_and_improves_calibration` — `ModuleNotFoundError: No module named 'sklearn'`
- `tests/test_selective.py::test_risk_coverage_perfect_ranking` — `AttributeError: module 'numpy' has no attribute 'trapz'`

---

## Trend

| Date | Status | New Issues | Resolved |
|------|--------|------------|---------|
| 2026-10-08 | RED | DuckDB single-writer violations first identified | — |
| 2026-10-09 | YELLOW | Architecture drift catalogued | None |
| 2026-10-10 | YELLOW | No regressions | None |
| 2026-10-11 | YELLOW | No regressions | None |
| 2026-10-12 | YELLOW | `np.trapz` NumPy 2.x breakage; sklearn missing from core deps | None |

Two new test failures introduced by dependency-environment mismatch. Core issues persist.

---

## Recommendations

1. **Immediate — Fix `np.trapz` → `np.trapezoid` in `scoring/selective.py:106`.** One-line fix; unblocks a currently-failing test and prevents a production crash if the selective-trading path runs.

2. **Immediate — Add `scikit-learn` to core dependencies or add a graceful fallback.** `IsotonicRecalibrator` is referenced from production scoring code; a `ModuleNotFoundError` at runtime is a silent risk.

3. **High — Fix DuckDB write serialization.** Route all writes through `DbWriter.enqueue()` or document explicitly that all callers are safe (serial) and remove the misleading unused `DbWriter`. This is the only issue that can silently corrupt production data under async load.

4. **Short-term — Wire up background brief refresh.** Add an `asyncio.create_task` in FastAPI lifespan that runs the brief pipeline on a schedule; dashboard lies on every cold start until then.

5. **Medium-term — Reconcile spec vs. built system.** Either update the Phase 1 spec/plan to reflect the prediction-market pivot or draft a Phase 1b plan for the missing `agents/`, `eval/`, and `spatial/` packages.
