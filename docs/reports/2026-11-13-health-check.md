# Parallax Health Check — 2026-11-13

**Status: YELLOW**

The core prediction market pipeline remains healthy — 473 tests passing, 13 skipped, 0 failing with DuckDB 1.5.6. Two persistent DuckDB single-writer violations carry over from prior reports. A new finding: `pyproject.toml` pins `duckdb>=1.2` but the `DATE()` function used in `scorecard.py` and `backtest/runner.py` only exists in DuckDB 1.3+, creating a silent install-time trap that causes 15 test failures on fresh installs that resolve to DuckDB 1.2.x.

---

## Summary

The prediction-market edge-finder is structurally sound. All 473 executable tests pass against DuckDB 1.5.6. The two previously documented single-writer violations (`ops/alerts.py`, `backtest/runner.py`) remain unaddressed. A dependency lower-bound mismatch (`duckdb>=1.2` vs. the actual minimum of `>=1.3`) was verified this cycle: installing DuckDB 1.2.2 causes 15 failures in `test_scorecard.py` and `test_phase1_critical.py`. No other new issues found.

---

## Issues Found

### HIGH

- **[HIGH][PERSISTENT] DuckDB single-writer violation — `backtest/runner.py` lines 290, 308, 329, 356**
  `BacktestRunner._persist_backtest_start()`, `_persist_prediction()`, `_update_prediction_resolution()`, and `_finalize_result()` all call `self._conn.execute(INSERT/UPDATE ...)` directly, bypassing the `DbWriter` asyncio queue. If the backtest runs against the live production DB while `DbWriter` is active, these writes risk a `database is locked` conflict. Fix: inject `DbWriter` and make `run()` async, or document that the backtest CLI must use a separate DuckDB file.

- **[HIGH][PERSISTENT] DuckDB single-writer violation — `ops/alerts.py` line 106**
  `DuckDBAlertSink.send()` is `async` but calls `self.db_conn.execute(INSERT ...)` synchronously, bypassing `DbWriter`. Fix: replace with `await db_writer.enqueue(sql, params)`.

### MEDIUM

- **[MEDIUM][NEW] `pyproject.toml` lower-bound too permissive: `duckdb>=1.2`**
  `scorecard.py` and `backtest/runner.py` use the `DATE()` scalar function (e.g., `WHERE DATE(resolved_at) = ?`), which does not exist in DuckDB 1.2.x. Installing DuckDB 1.2.2 produces 15 test failures across `test_scorecard.py` (11 failures) and `test_phase1_critical.py` (3 failures). DuckDB 1.3+ has this function. Fix: bump the constraint to `duckdb>=1.3`.

- **[MEDIUM][PERSISTENT] 7 tests skipped in `test_mapping_policy.py`**
  Skipped with `_PRE_REFACTOR_REASON` ("predates confidence-shrinkage on fair-value estimators"). The refactored confidence-shrinkage logic lacks direct unit test coverage and is only exercised indirectly via integration tests.

### LOW

- **[LOW][PERSISTENT] `requires-python = ">=3.11"` in pyproject.toml**
  CLAUDE.md and the deployment stack target Python 3.12. The looser lower bound allows installation on 3.11, where some typing features used in the codebase (`str | None`, `dict[str, Any]` in signatures) require `from __future__ import annotations`. Bump to `>=3.12` to match runtime.

- **[LOW][PERSISTENT] `simulation/engine.py` and `simulation/circuit_breaker.py` absent**
  The DES engine and escalation limiter defined in the Phase 1 plan were never built. `simulation/cascade.py` and `simulation/world_state.py` exist. No active blocker — the product has pivoted away from this.

- **[LOW][PERSISTENT] Dual runtime modules: `db/runtime.py` and `ops/runtime.py`**
  Both exist with different scopes (DuckDB path resolution vs. API/execution environment config). `db/runtime.py` could be renamed `db/paths.py` to reduce confusion.

- **[LOW][PERSISTENT] Frontend deps diverge from spec**
  `frontend/package.json` has only `react`, `react-dom`, `recharts`. The Phase 1 spec called for `deck.gl`, `maplibre-gl`, `react-map-gl`, `h3-js`. Absent by design following the product pivot — noted for spec hygiene.

---

## Spec/Plan Consistency

| Area | Spec | Actual | Verdict |
|------|------|--------|---------|
| Prediction pipeline (oil, ceasefire, hormuz) | Yes | Yes | ✅ |
| Cascade rules engine | Yes | Yes | ✅ |
| DuckDB single-writer topology | Yes | Partial — 2 violations | ⚠️ |
| World state + delta tracking | Yes | Yes | ✅ |
| Scenario config YAML | Yes | Yes | ✅ |
| Agent swarm (~50 agents) | Yes | No — intentional pivot | ℹ️ |
| H3 spatial / deck.gl | Yes | No — intentional pivot | ℹ️ |
| DES simulation engine | Yes | Partial — cascade only | ⚠️ |
| Kalshi/Polymarket market integration | No | Yes | ℹ️ (added value) |
| Scoring/calibration/scorecard | No | Yes | ℹ️ (added value) |
| Backtest engine | No | Yes | ℹ️ (added value) |
| Portfolio allocator | No | Yes | ℹ️ (added value) |

---

## Test Coverage

| Category | Status |
|----------|--------|
| Total passing | 473 (DuckDB 1.5.6) |
| Skipped | 13 (7 mapping_policy, rest low-risk) |
| Failing with DuckDB 1.2.x | 15 — `test_scorecard.py` (11), `test_phase1_critical.py` (3), `test_bench_forecast.py` import error (1 — missing `pandas`) |
| Plan tests present | test_schema, test_writer, test_world_state, test_config, test_cascade ✅ |
| Plan tests absent (unbuilt modules) | test_h3_utils, test_dedup, test_circuit_breaker, test_agent_*, test_auth ℹ️ |
| Actual product coverage | Comprehensive — brief, scoring, calibration, divergence, markets, backtest all tested |

---

## Dependency Audit

| Package | Constraint | Concern |
|---------|------------|---------|
| `duckdb` | `>=1.2` | **Should be `>=1.3`** — `DATE()` function absent in 1.2.x |
| `anthropic` | `>=0.52` | No concern; API stable |
| `fastapi` | `>=0.115` | No concern |
| `httpx` | `>=0.28` | No concern |
| `scikit-learn` | `>=1.3` | Used for calibration; no concern |
| `truthbrush` | `>=0.2` | Third-party Truth Social scraper; no pinned upper bound |
| `h3`, `searoute`, `shapely`, `sentence-transformers` | Absent | Were in Phase 1 spec; removed in product pivot |
| `pandas`, `pyarrow`, `matplotlib` | `bench` optional dep | `test_bench_forecast.py` requires `pandas` but it's not in `dev` extras — bench test will fail in bare dev installs |

---

## Recommendations

1. **[Immediate] Bump `duckdb>=1.3`** in `pyproject.toml` — 1-line fix prevents silent install-time failures on new developer machines or CI runners that resolve to 1.2.x.
2. **Fix `ops/alerts.py` line 106** (30-min effort) — replace `self.db_conn.execute(...)` with `await db_writer.enqueue(...)`. This is the simpler of the two single-writer violations.
3. **Decide on `BacktestRunner` write strategy** — either inject `DbWriter` and make `run()` async, or document that the backtest CLI must open a separate DuckDB file (not the live production DB).
4. **Bump `requires-python = ">=3.12"`** to match runtime.
5. **Add `pandas` to `dev` extras or skip `test_bench_forecast.py`** in the default test run — currently that test file fails to collect on bare `.[dev]` installs.
