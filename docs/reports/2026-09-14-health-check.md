# Parallax Health Check — 2026-09-14

**Status: YELLOW**

The core prediction-market pipeline is stable with 467/473 tests passing. Six tests fail due to missing `sklearn` in dev dependencies and a `numpy.trapz` removal in NumPy 2.x. The codebase has also drifted substantially from the Phase 1 spec (no agent swarm, no H3 spatial layer) though the new direction appears intentional. One DuckDB single-writer violation persists in `ops/alerts.py`.

---

## Issues Found

### [HIGH] 6 test failures blocking CI

- **[HIGH]** `tests/test_recalibrators.py` — 5 tests fail: `ModuleNotFoundError: No module named 'sklearn'`. `scoring/recalibrators.py` imports `sklearn` at runtime but `scikit-learn` is only in the `bench` optional extras, not `dev`. Fix: move `scikit-learn>=1.3` into `[project.optional-dependencies.dev]` in `pyproject.toml`.
- **[HIGH]** `tests/test_selective.py::test_risk_coverage_perfect_ranking` — `AttributeError: module 'numpy' has no attribute 'trapz'`. `numpy.trapz` was removed in NumPy 2.0; the call at `scoring/selective.py:106` must be replaced with `np.trapezoid` (NumPy ≥1.23) or `np.trapz` guarded behind a version check.
- **[MEDIUM]** `tests/test_bench_forecast.py` fails to collect (`ModuleNotFoundError: No module named 'numpy'`) in environments where the `bench` extras are not installed. The test should be guarded with `pytest.importorskip("numpy")` or moved to a `bench` test suite.

### [HIGH] DuckDB single-writer violation

- **[HIGH]** `src/parallax/ops/alerts.py:106` — `DuckDBAlertSink.send()` calls `self.db_conn.execute("INSERT INTO ops_events …")` directly without going through the `asyncio.Queue` writer. This bypasses the single-writer topology and can cause `database is locked` errors under concurrent load. The method is `async`, so it can call `await db_writer.enqueue(…)` instead.

### [MEDIUM] Missing `numpy` in core dependencies

- **[MEDIUM]** `numpy` is used in `scoring/selective.py`, `scoring/recalibrators.py`, and `scoring/calibration_metrics.py` but is absent from both `[project.dependencies]` and `[project.optional-dependencies.dev]`. It only appears under `bench`. Any `dev` install that does not include `bench` will fail at import time for these scoring modules.

### [MEDIUM] Spec/Plan architecture divergence (intentional but undocumented)

- **[MEDIUM]** The Phase 1 design spec describes an LLM agent swarm (~50 agents, H3 hex map, GDELT BigQuery, WebSocket real-time), none of which is implemented. The actual system is a prediction market edge-finder (3 Claude prediction models, Kalshi/Polymarket comparison, paper trading). The `agents/`, `eval/`, and `spatial/` module directories from the plan do not exist.
  - This divergence appears deliberate given the CLAUDE.md rewrite. It is not a bug, but the spec documents are now misleading. **Recommendation:** archive or annotate the old spec and plan to reflect the new direction, so future health checks don't flag this repeatedly.

### [LOW] `simulation/` module is incomplete vs. plan

- **[LOW]** `simulation/engine.py` (DES engine) and `simulation/circuit_breaker.py` are absent. `cascade.py` and `world_state.py` exist but are not wired into the live pipeline. The simulation layer appears unused by the main CLI/API.

### [LOW] Python version constraint loosened

- **[LOW]** `pyproject.toml` declares `requires-python = ">=3.11"` but the spec and plan specify Python 3.12+. Container uses `python:3.12-slim` per CLAUDE.md. The constraint should be tightened to `>=3.12` to match the actual deployment target and prevent accidental 3.11 installs.

---

## Recommendations

1. **Fix test suite immediately**: Add `numpy>=1.26` and `scikit-learn>=1.3` to `[project.optional-dependencies.dev]` in `pyproject.toml`. Replace `np.trapz` with `np.trapezoid` in `scoring/selective.py:106`. This brings CI to 0 failures.
2. **Fix DuckDB writer violation**: Change `DuckDBAlertSink.send()` in `ops/alerts.py` to enqueue through `DbWriter` instead of calling `conn.execute` directly.
3. **Archive stale spec/plan**: Add a note at the top of `docs/superpowers/specs/2026-03-30-parallax-phase1-design.md` indicating the project pivoted to the prediction-market model (see CLAUDE.md). This prevents daily health checks from flagging the same structural drift.
4. **Guard bench tests**: Wrap `test_bench_forecast.py` and the affected scoring tests with `pytest.importorskip` for optional extras so a plain `pip install -e ".[dev]"` doesn't surface collection errors.
