# Parallax Health Check — 2026-10-24

**Status: YELLOW**

## Summary

485/504 tests pass; 6 tests are actively failing — 5 due to `sklearn` not being installed in the base environment (only in `bench` extras), and 1 due to a NumPy 2.0 API break (`np.trapz` removed → `np.trapezoid`). The codebase has deliberately diverged from the Phase 1 spec (H3 geospatial agent swarm) into a prediction market edge-finder, which is fine, but the spec hasn't been updated to reflect this. Multiple non-trivial DuckDB single-writer violations remain unaddressed across several modules.

---

## Issues Found

### 🔴 HIGH — 6 Failing Tests

- **[HIGH]** `test_recalibrators.py` (5 tests): `ModuleNotFoundError: No module named 'sklearn'`. `scoring/recalibrators.py` imports `sklearn.isotonic` and `sklearn.linear_model` at call time, but `scikit-learn` is in the `bench` extras group, not in core deps. Tests fail in a clean install. Fix: move `scikit-learn` to core deps or add lazy-import guard with a clear `pip install "parallax[bench]"` error message.
- **[HIGH]** `test_selective.py::test_risk_coverage_perfect_ranking`: `AttributeError: module 'numpy' has no attribute 'trapz'`. NumPy 2.0 removed `np.trapz` — use `np.trapezoid` instead. One-line fix in `scoring/selective.py:106`.

### 🔴 HIGH — DuckDB Single-Writer Violations

The spec requires all writes to go through the `asyncio.Queue` in `db/writer.py`. The following modules write directly to DuckDB, bypassing this pattern:

- **[HIGH]** `scoring/ledger.py:225,256` — `INSERT` and `UPDATE` to `signal_ledger` directly
- **[HIGH]** `scoring/resolution.py:60,124` — `UPDATE` to `signal_ledger` and `trade_positions` directly
- **[HIGH]** `scoring/prediction_log.py:79` — `INSERT` into `prediction_log` directly
- **[HIGH]** `scoring/tracker.py:462,518,674,713,746` — multiple `INSERT`/`UPDATE` to trade tables directly
- **[HIGH]** `budget/tracker.py:43` — `INSERT INTO llm_usage` directly
- **[HIGH]** `ops/alerts.py:106` — `INSERT INTO ops_events` directly
- **[MEDIUM]** `cli/brief.py:130,149,431` — direct writes acceptable in CLI context (single process, no concurrency) but inconsistent with server architecture

Risk: under concurrent load (multiple API requests + background ingestion), these bypass the single-writer guarantee and can cause `database is locked` errors.

### 🟡 MEDIUM — Spec/Architecture Drift

The Phase 1 spec describes an H3 geospatial agent swarm with deck.gl visualization. The implementation has pivoted to a Kalshi/Polymarket prediction market edge-finder. This is a coherent product in its own right, but the gap is wide:

- **[MEDIUM]** `spatial/`, `agents/`, `eval/`, `api/` modules are entirely absent (specified in plan, never built)
- **[MEDIUM]** `simulation/engine.py` (DES core) and `simulation/circuit_breaker.py` are missing
- **[MEDIUM]** Frontend has no deck.gl, no MapLibre, no H3HexagonLayer, no WebSocket hook — it is a polling-based trading dashboard, not the geospatial visualization specified
- **[LOW]** `CLAUDE.md` still describes the prediction market pivot accurately — no documentation gap there

### 🟡 MEDIUM — Dependency Gaps

- **[MEDIUM]** `scoring/recalibrators.py` uses `sklearn` but it is not in core deps — runtime import error in production unless `bench` extras are installed
- **[LOW]** `pyproject.toml` sets `requires-python = ">=3.11"` but spec calls for 3.12
- **[LOW]** 6 packages from the spec (`h3`, `websockets`, `sentence-transformers`, `searoute`, `shapely`, `google-cloud-bigquery`) are absent — acceptable since the H3/agent swarm pivot never happened, but worth noting

### 🟡 MEDIUM — No Feature Code Commits in Recent History

Last 20 git commits are exclusively automated health check reports and tech research scout reports. No feature or bugfix code changes visible. The 6 failing tests and DuckDB violations from previous reports have not been addressed.

---

## Recommendations

1. **Fix `np.trapz` → `np.trapezoid`** in `scoring/selective.py:106` — one-line fix, unblocks CI green.
2. **Fix `sklearn` import** — either add `scikit-learn` to core deps in `pyproject.toml`, or wrap the import in `recalibrators.py` with a helpful `ImportError` message pointing to `pip install "parallax[bench]"`.
3. **Audit DuckDB write paths** — the scoring/ledger, resolution, prediction_log, tracker, budget tracker, and alerts modules all write directly. Either route them through `DbWriter.enqueue()` or document explicitly that these modules are only called from the single CLI process (not from concurrent async handlers).
4. **Update the Phase 1 spec** to reflect the prediction market pivot — or archive it and create a new spec for the current architecture. The current CLAUDE.md is accurate but the docs/superpowers/specs/ document describes a different product.
5. **Address 6 failing tests** before the next feature push — CI should be green before new features land.

---

## Test Summary

| Category | Count |
|---|---|
| Passed | 485 |
| Failed | 6 |
| Skipped | 13 |
| Total | 504 |

Failed: `test_recalibrators.py` (5) + `test_selective.py` (1)

Root causes: missing `scikit-learn` in base deps; `np.trapz` removed in NumPy 2.0.
