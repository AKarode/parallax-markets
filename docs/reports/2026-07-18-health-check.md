# Parallax Repo Health Check — 2026-07-18

**Status: YELLOW**

No source-code changes have landed since the 2026-07-17 check. One documentation commit landed (tech-research report on Claude Batch/Caching, AIS vessel data, GDELT alternatives). All YELLOW issues from yesterday persist unchanged.

---

## Summary

Zero source-code commits between the 2026-07-17 health check and today. The codebase continues to function for its prediction-market edge-finder direction: 433 tests pass, 13 skip, 4 test files fail to collect due to missing `numpy`/`pandas` in the base dependency set. The DuckDB single-writer pattern violation and missing planned spec modules remain standing issues; neither is a runtime blocker given the current single-process CLI architecture.

---

## Delta From Yesterday (2026-07-17)

| Area | Change |
|------|--------|
| Source code commits | 0 |
| Documentation commits | 1 (tech-research: Claude Batch, AIS, GDELT alternatives) |
| New issues | 0 |
| Resolved issues | 0 |
| Tests passing | 433 (unchanged) |
| Tests skipped | 13 (unchanged) |
| Test files failing to collect | 4 (unchanged — numpy/pandas) |

Full issue details carried from [2026-07-17-health-check.md](2026-07-17-health-check.md). Reproduced below for completeness.

---

## Issues Found (Carried Over)

### [HIGH] DuckDB Single-Writer Pattern Violated Across the Codebase

The spec declares the asyncio.Queue single-writer pattern a **hard constraint**. `db/writer.py` implements `DbWriter` correctly and is tested, but no production path routes through it. At least twelve source files write directly to DuckDB via `conn.execute()`:

| File | Write Operations |
|------|-----------------|
| `scoring/ledger.py` | INSERT + UPDATE `signal_ledger` |
| `scoring/tracker.py` | INSERT/UPDATE `trade_orders`, `trade_fills`, `trade_positions` |
| `scoring/resolution.py` | UPDATE `signal_ledger`, `trade_positions` |
| `scoring/prediction_log.py` | INSERT `prediction_log` |
| `scoring/scorecard.py` | INSERT `daily_scorecard` |
| `contracts/registry.py` | INSERT OR REPLACE + DELETE + UPDATE `contract_registry` / `contract_proxy_map` |
| `ingestion/crisis_ingester.py` | INSERT `crisis_events` |
| `ops/alerts.py` | INSERT `ops_events` (inside an `async send()` method — highest risk) |
| `backtest/runner.py` | INSERT/UPDATE `backtest_runs`, `backtest_predictions` |
| `cli/brief.py` | INSERT `runs`, UPDATE `runs`, INSERT `market_prices` |
| `budget/tracker.py` | INSERT `llm_usage` |
| `db/schema.py` | UPDATE `signal_ledger` (migration backfills — one-time, acceptable) |

Immediate risk is bounded because the app runs as single-process asyncio and the CLI is sequential. However, the FastAPI server (`main.py`) shares `app.state.db` across concurrent request handlers; async endpoints that trigger writes (e.g. `DuckDBAlertSink.send()`) could contend on DuckDB's per-statement write lock during peak load. `DbWriter` exists, is tested, and is currently unused in production paths.

**Recommendation:** Wire `DbWriter` into the FastAPI lifespan and route all write-path components through it. CLI can continue using direct writes since it does not run concurrently with the DES engine.

### [HIGH] Core Simulation Infrastructure Not Built (Intentional Pivot)

These modules from the Phase 1 plan are absent. The product has pivoted from geopolitical cascade simulation to prediction-market edge-finding, making these informational rather than blocking:

| Missing Module | Plan Description |
|---------------|-----------------|
| `simulation/engine.py` | DES tick loop (heapq priority queue) |
| `simulation/circuit_breaker.py` | Escalation limits and cooldowns |
| `agents/` package | Runner, router, country agent, prompts, 50-agent roster |
| `spatial/` package | H3 utilities, loader, route-to-cell conversion |
| `eval/` package | Predictions, scoring, ground truth, prompt versioning, improvement pipeline |
| `api/` package | Dedicated routes, websocket handler, auth middleware |

Frontend has also diverged: no deck.gl H3 hex map, no WebSocket connection, no `useHexData.ts` / `HexMap.tsx` / `AgentFeed.tsx`. Current frontend is a trading dashboard using HTTP polling.

**Recommendation:** Update the spec and plan documents to reflect the actual product direction (prediction-market edge-finder). The current `CLAUDE.md` already describes the actual architecture accurately; the Phase 1 design doc is stale.

### [MEDIUM] `numpy` / `pandas` Not in Base Dependencies

Four test files fail to collect because `numpy` is not installed in the base dev environment:

- `tests/test_bench_forecast.py`
- `tests/test_calibration_metrics.py`
- `tests/test_recalibrators.py`
- `tests/test_selective.py`

These modules are listed under the `[bench]` extras in `pyproject.toml` but the tests import them unconditionally. Running `pip install -e ".[dev]"` (the documented workflow) leaves these tests broken.

**Fix options:**
1. Move `numpy`, `pandas`, `scikit-learn` to base `dev` extras
2. Guard test imports with `pytest.importorskip("numpy")` to make them auto-skip gracefully

### [MEDIUM] Architecture Drift vs. Phase 1 Plan File Layout

The implemented structure differs substantially from the plan's prescribed layout:

| Plan Path | Actual Path | Status |
|-----------|-------------|--------|
| `ingestion/gdelt.py` | `ingestion/gdelt_doc.py` | Renamed + different API |
| `ingestion/dedup.py` | (absent) | Spec's semantic dedup not implemented |
| `agents/` | (absent) | Replaced by `prediction/` |
| `eval/` | (absent) | Replaced by `scoring/` |
| `api/routes.py`, `api/websocket.py`, `api/auth.py` | (absent) | Logic folded into `main.py` |
| `simulation/engine.py`, `simulation/circuit_breaker.py` | (absent) | DES not built |
| (not in plan) | `backtest/`, `bench/`, `contracts/`, `divergence/`, `portfolio/`, `markets/` | Added post-pivot |

### [LOW] `requires-python` Drift

`pyproject.toml` specifies `requires-python = ">=3.11"` but the Phase 1 spec and `CLAUDE.md` both reference Python 3.12. The difference is minor but creates confusion about the true minimum.

### [LOW] `pytz` Dependency (Deprecated)

`pytz>=2024.1` is listed as a runtime dependency. The `pytz` library is considered legacy since Python 3.9 introduced `zoneinfo` in the stdlib. Any new code using timezones should use `zoneinfo`; `pytz` can be dropped once all callers are migrated.

### [LOW] No Upper Bounds on Critical Runtime Dependencies

`fastapi`, `duckdb`, `anthropic`, `httpx`, and `pydantic` have no upper bounds in `pyproject.toml`. A breaking change in any of these (e.g., FastAPI 1.0, DuckDB 2.0) could silently break the project during a fresh install.

---

## Recommendations (Priority Order)

1. **(Medium effort)** Wire `DbWriter` into the async production path — primarily `ops/alerts.py` (`DuckDBAlertSink`) and any ingestion paths called from the FastAPI server.
2. **(Low effort)** Fix the `numpy`/`pandas` test collection errors — either add to `dev` extras or add `pytest.importorskip`.
3. **(Low effort)** Update `requires-python` to match the actual minimum tested version.
4. **(Low effort)** Drop `pytz` and migrate any remaining callers to `zoneinfo`.
5. **(Documentation)** Mark the Phase 1 design spec and plan as superseded; add a new spec doc describing the actual prediction-market architecture.
