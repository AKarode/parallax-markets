# Parallax Health Check — 2026-06-14

**Status: YELLOW**

## Summary

No commits have landed on main since yesterday's health check (HEAD remains at `4602cef`). All issues flagged on 2026-06-13 carry forward unresolved. The `pytz` gap has now blocked the same 17 tests for three consecutive days and is the single highest-leverage fix in the repo. Single-writer pattern violations across 10+ modules and missing error handling in `polymarket.py` remain the two other open HIGH-severity items.

---

## Test Run Summary

```
398 passed  |  17 failed  |  13 skipped  |  1 collection error
```

- **All 17 failures**: `duckdb.InvalidInputException: Required module 'pytz' failed` — exclusively pytz.
- **1 collection error**: `test_truth_social.py` — `truthbrush` not installed in CI environment (IS listed in `pyproject.toml`; pip conflict with system `cryptography 41.0.7`).
- **Passing suite**: core simulation, cascade, schema, world state, writer, markets, scoring, ledger, calibration, backtest, contracts, dashboard all green.

---

## Issues Found

### CRITICAL

- **[CRITICAL] `pytz` missing from `pyproject.toml`** *(day 3 — first flagged 2026-06-12)*
  DuckDB 1.5.3 (installed) requires `pytz` for `DATE()` / `TIMESTAMPTZ` operations. `pytz` is not in `backend/pyproject.toml`. The same 17 tests fail identically to yesterday, spread across `test_scorecard.py` (11), `test_crisis_context_db.py` (4), `test_llm_usage.py` (1), `test_ops_events.py` (1), `test_phase1_critical.py` (1). Every production `--scorecard` run, budget tracker write, and DuckDB alert sink is broken at runtime.
  - **Fix (one line)**: Add `"pytz>=2024.1"` to the `dependencies` list in `backend/pyproject.toml`.

---

### HIGH

- **[HIGH] Single-writer pattern violated in 10+ modules** *(carried — day 4+)*
  Confirmed write (`INSERT`/`UPDATE`/`DELETE`) operations via raw `conn.execute()` outside `db/writer.py` in:
  `scoring/ledger.py` (lines 225, 258), `ops/alerts.py` (line 108), `budget/tracker.py` (line 45), `ingestion/crisis_ingester.py`, `contracts/registry.py`, `scoring/prediction_log.py`, `scoring/scorecard.py`, `scoring/tracker.py`, `backtest/runner.py`, `backtest/look_ahead_guard.py` (DDL).
  `DbWriter` is correctly implemented but not wired. Risk: concurrent FastAPI requests + background tasks hitting async write paths will race on the DuckDB connection.
  - **Fix**: Pass the `DbWriter` instance at construction time to async-path modules and call `await writer.enqueue(sql, params)` instead of `self._conn.execute(sql, params)`. CLI-only batch modules (`brief.py`, `scorecard.py`) are lower priority.

- **[HIGH] Missing exception handling in `polymarket.py`** *(carried — day 2)*
  Five methods — `search_markets()` (line 92), `get_event()` (line 98), `get_market()` (line 104), `get_price()` (line 113), `get_book()` (line 123) — call `resp.raise_for_status()` with no surrounding `try/except`. Any Polymarket 429, 5xx, or network timeout propagates as an unhandled exception that aborts the entire brief run.
  - **Fix**: Wrap each `async with httpx.AsyncClient()` block in `try/except (httpx.HTTPStatusError, httpx.RequestError)`, log a warning, and return `None` / empty.

- **[HIGH] Missing exception handling in `oil_prices.py`** *(carried — day 2)*
  Lines 49–55 use `try/finally` with no `except`. `httpx.HTTPStatusError` and `json.JSONDecodeError` from EIA API failures propagate uncaught and crash the brief pipeline.
  - **Fix**: Add `except (httpx.HTTPStatusError, httpx.RequestError, json.JSONDecodeError)` before the `finally`, log a warning, and return `[]`.

---

### MEDIUM

- **[MEDIUM] `PRICE_ELASTICITY = 3.0` hardcoded in `cascade.py`** *(carried — day 2)*
  Line 35 of `simulation/cascade.py` defines a module-level constant `PRICE_ELASTICITY = 3.0`. Spec §4 explicitly requires all cascade parameters to be loaded from `scenario_hormuz.yaml`, not hard-coded, so the eval framework can flag when assumptions diverge from observed behavior.
  - **Fix**: Add `price_elasticity: 3.0` to `backend/config/scenario_hormuz.yaml`; add the field to `ScenarioConfig`; replace `self.PRICE_ELASTICITY` with `self._config.price_elasticity` in `compute_price_shock()`.

- **[MEDIUM] `simulation/circuit_breaker.py` not implemented** *(carried)*
  Spec §4 defines escalation limits (max 1 level/tick, 3-tick cooldown, Goldstein exogenous override). `ScenarioConfig` already carries all three parameters. Module and `test_circuit_breaker.py` both absent.

- **[MEDIUM] `ingestion/dedup.py` not implemented** *(carried)*
  Semantic dedup (`SemanticDeduplicator` via `all-MiniLM-L6-v2`) is absent. Google News and GDELT DOC can surface duplicate events to prediction models. `sentence-transformers` is not in `pyproject.toml`.

- **[MEDIUM] Architectural drift: agents/, eval/, spatial/, api/ modules** *(documented, intentional)*
  Original Phase 1 spec described a 50-agent LLM swarm, H3 geospatial dashboard, prompt-versioning eval pipeline, and REST/WebSocket API layer. None exist. The pivot to a prediction-market edge-finder is intentional and documented in `CLAUDE.md`.

---

### LOW

- **[LOW] `test_truth_social.py` collection error in CI environment**
  `truthbrush>=0.2` IS listed in `pyproject.toml` but fails to install in the test environment due to a system `cryptography 41.0.7` (Debian package) conflict with pip. Affects only this one test file; the module itself is functional in Docker. Workaround: use `--ignore=tests/test_truth_social.py` in CI until the environment resolves the conflict, or pin `cryptography` out of Debian's reach via a venv.

- **[LOW] `starlette.testclient` deprecation warning**
  Test runs emit: `StarletteDeprecationWarning: Using httpx with starlette.testclient is deprecated; install httpx2 instead.` FastAPI's `TestClient` is relying on `starlette.testclient` from `httpx` rather than `httpx2`. No runtime breakage today, but will become an import error when `httpx` removes the deprecated interface. Fix: `pip install httpx2` and update `pytest-httpx` pin if needed.

- **[LOW] 6 spec-required deps absent from `pyproject.toml`** *(carried — intentional)*
  `h3`, `sentence-transformers`, `searoute`, `shapely`, `google-cloud-bigquery`, `websockets` — all from the original geospatial pipeline that was not built. No operational risk.

- **[LOW] 13 of 18 plan-specified test files missing** *(carried — intentional)*
  `test_h3_utils`, `test_gdelt_filter`, `test_dedup`, `test_circuit_breaker`, `test_agent_schemas`, `test_agent_router`, `test_agent_runner`, `test_scoring` (generic), `test_prompt_versioning`, `test_auth`, `test_budget_tracker` (standalone), `test_integration`. 43 replacement test files exist for the pivot scope; overall coverage is healthy at 398 passing, but modules carried from Phase 1 (circuit breaker, dedup) have no tests.

- **[LOW] `requires-python = ">=3.11"` vs spec's Python 3.12** *(carried)*
  No 3.11-incompatible syntax found, but the looser pin allows environments where subtle 3.12-only behavior may differ.

- **[LOW] No linter or formatter enforced** *(carried)*
  No `ruff`, `black`, or `pre-commit` hook configured. Style is consistent by convention only.

---

## Dependency Snapshot

| Package | Required by Spec | Actual Status |
|---------|-----------------|---------------|
| fastapi ≥0.115 | ✓ | present |
| uvicorn[standard] ≥0.34 | ✓ | present |
| duckdb ≥1.2 | ✓ | present (1.5.3) |
| anthropic ≥0.52 | ✓ | present |
| pydantic ≥2.10 | ✓ | present |
| pyyaml ≥6.0 | ✓ | present |
| httpx ≥0.28 | ✓ | present |
| h3 ≥4.1 | ✓ | **missing** (not built) |
| websockets ≥14.0 | ✓ | **missing** (not built) |
| sentence-transformers ≥3.4 | ✓ | **missing** (dedup not built) |
| searoute ≥1.3 | ✓ | **missing** (not built) |
| shapely ≥2.0 | ✓ | **missing** (not built) |
| google-cloud-bigquery ≥3.27 | ✓ | **missing** (not built) |
| pytz (runtime req of DuckDB 1.5.x) | implied | **missing — CRITICAL** |
| cryptography ≥44.0 | not in spec | present (Kalshi RSA auth) |
| truthbrush ≥0.2 | not in spec | in pyproject.toml; CI install conflict |

---

## Recommendations (Priority Order)

1. **Immediate (1 line)**: Add `"pytz>=2024.1"` to `dependencies` in `backend/pyproject.toml`. Resolves 17 test failures. This has been open 3 days.

2. **Short-term**: Wrap `polymarket.py` and `oil_prices.py` external HTTP calls in `try/except (httpx.HTTPStatusError, httpx.RequestError)`. Return `None`/`[]` with `logger.warning(...)`. Prevents brief-run crashes on transient API errors.

3. **Short-term**: Add `price_elasticity: 3.0` to `scenario_hormuz.yaml` + `ScenarioConfig`, remove the `PRICE_ELASTICITY` module constant from `cascade.py`. Makes the price model tunable without code changes.

4. **Medium-term**: Wire `DbWriter` into async-path write modules (`ops/alerts.py`, `budget/tracker.py`, `scoring/ledger.py`, `scoring/prediction_log.py`, `ingestion/crisis_ingester.py`, `contracts/registry.py`). Pass writer at construction; `await writer.enqueue(sql, params)`.

5. **Medium-term**: Implement `simulation/circuit_breaker.py` (all config params already in `ScenarioConfig`) and add `test_circuit_breaker.py`.
