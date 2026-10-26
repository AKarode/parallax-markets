# Parallax Health Check — 2026-10-26

**Status: YELLOW**

The codebase continues to implement a functional prediction market edge-finder that differs from the original Phase 1 spec's LLM agent swarm design — a deliberate, valuable pivot documented in CLAUDE.md. Test suite is largely healthy (485 passing, 13 skipped), but 6 tests are newly failing due to two dependency issues introduced in recent commits: a missing `sklearn` import in `recalibrators.py` and a deprecated `numpy.trapz` call in `selective.py`.

---

## Summary

Core prediction, market integration, scoring, and paper trading pipeline are all well-tested and stable. The two new test failures are both dependency/API-level issues that do not block the main pipeline but will cause runtime errors if those code paths are exercised. Architecture drift from the original spec persists (agent swarm, spatial model, eval framework unbuilt) but is consistent with prior reports — no new drift detected this cycle.

---

## Issues Found

### [HIGH] 6 New Test Failures (regression from yesterday)

**`tests/test_recalibrators.py` — 5 failures: `ModuleNotFoundError: No module named 'sklearn'`**
- `IsotonicRecalibrator.fit()` at `scoring/recalibrators.py:111` lazily imports `from sklearn.isotonic import IsotonicRegression`
- `PlattRecalibrator.fit()` at `scoring/recalibrators.py:70` lazily imports `from sklearn.linear_model import LogisticRegression`
- `scikit-learn` is listed in `pyproject.toml` under `[project.optional-dependencies] bench` but is not in the base `dependencies`, so production installs lack it
- **Fix**: Either move `scikit-learn` to base dependencies, or add a `try/except ImportError` guard with a descriptive error message at the module level

**`tests/test_selective.py::test_risk_coverage_perfect_ranking` — 1 failure: `AttributeError: module 'numpy' has no attribute 'trapz'`**
- `scoring/selective.py:106` calls `np.trapz(risk, coverage)` — `numpy.trapz` was deprecated in NumPy 2.0 and removed; the replacement is `np.trapezoid`
- The environment has NumPy ≥ 2.0 installed, so this fails at runtime
- **Fix**: Replace `np.trapz` with `np.trapezoid` at `selective.py:106`

### [HIGH] Architecture Drift from Spec (Persistent — no change)

- **Spec describes**: ~50-agent LLM swarm (country/sub-actor hierarchy), H3 hexagonal spatial model, WebSocket-driven React/deck.gl dashboard, DES simulation engine, GDELT BigQuery eval framework
- **Code implements**: 3 prediction models (oil price, ceasefire, Hormuz), Kalshi/Polymarket divergence detection, paper trading, signal ledger, scoring/calibration suite
- **Missing spec modules**: `agents/`, `spatial/`, `api/` (routes, websocket, auth), `eval/`, `ingestion/dedup.py`, `simulation/engine.py`, `simulation/circuit_breaker.py`
- Intentional pivot per CLAUDE.md; no action needed unless the spec is being resumed

### [HIGH] Missing Dependencies in pyproject.toml (Persistent)

Packages used in code or referenced in CLAUDE.md tech stack but absent from base `dependencies`:
- `h3>=4.1` — tests import it; h3_utils tests pass because h3 is installed globally, not via package
- `sentence-transformers>=3.4` — spec's GDELT semantic dedup stage
- `searoute>=1.3`, `shapely>=2.0`, `google-cloud-bigquery>=3.27`, `websockets>=14.0`
- `scikit-learn` — needed by `recalibrators.py` (base dep, not just bench)
- **Risk**: Fresh deploy or Docker build will fail at import time for any of these

### [MEDIUM] DuckDB Single-Writer Violations (Persistent)

Multiple modules write directly to DuckDB outside the `asyncio.Queue → db_writer` pattern required by the spec's single-writer topology:
- `ops/alerts.py` — `DuckDBAlertSink` calls `self.db_conn.execute()` directly in the live pipeline
- `backtest/runner.py`, `backtest/look_ahead_guard.py` — direct writes (lower risk; offline, non-concurrent)
- All scoring modules (`ledger.py`, `tracker.py`, `prediction_log.py`, `recalibration.py`, `scorecard.py`, etc.) write directly via `self._conn.execute()` — these are the hot path and are the highest concurrency risk
- **Risk**: Under concurrent FastAPI request load, multiple scoring writes could collide; DuckDB will serialize them but may raise `database is locked` under contention

### [MEDIUM] Python Version Constraint Mismatch (Persistent)

- `pyproject.toml`: `requires-python = ">=3.11"` — CLAUDE.md and spec state Python 3.12 target
- No functional impact yet, but inconsistency between declared and tested versions

### [LOW] Frontend Diverged from Spec Layout

- **Spec**: 3-column deck.gl dashboard with `HexMap.tsx`, `AgentFeed.tsx`, `LiveIndicators.tsx`, `Timeline.tsx`, `PredictionCards.tsx`, `HexPopover.tsx`, WebSocket hook
- **Code**: Polling-based dashboard with `ModelCards.tsx`, `MarketsTable.tsx`, `KpiBar.tsx`, `PortfolioPanel.tsx`; no WebSocket, no H3 map, no agent feed
- Consistent with the prediction-market pivot; no H3 or deck.gl dependencies remain

---

## Test Suite Summary

| Category | Count |
|---|---|
| Passed | 485 |
| Failed | 6 (2 root causes: sklearn missing, numpy.trapz removed) |
| Skipped | 13 |
| **Total** | **504** |

Failed tests (new this cycle):
- `test_recalibrators.py::test_isotonic_is_monotone_and_improves_calibration`
- `test_recalibrators.py::test_platt_is_monotone`
- `test_recalibrators.py::test_isotonic_preserves_auc_bucket_may_not`
- `test_recalibrators.py::test_fit_recalibrator_factory`
- `test_recalibrators.py::test_recalibration_improves_brier_out_of_sample`
- `test_selective.py::test_risk_coverage_perfect_ranking`

---

## Recommendations

1. **[Immediate]** Fix `np.trapz` → `np.trapezoid` in `scoring/selective.py:106`
2. **[Immediate]** Add `scikit-learn>=1.3` to base `dependencies` in `pyproject.toml` (not just `bench` extras)
3. **[Short-term]** Audit scoring modules for `conn.execute()` write calls — wrap in `DbWriter.enqueue()` for the live pipeline path (alert sink is highest priority)
4. **[Housekeeping]** Update `requires-python` to `>=3.12` in `pyproject.toml` to match stated target
5. **[Documentation]** Update spec/plan to reflect prediction-market architecture if the original spec's agent swarm is no longer the target
