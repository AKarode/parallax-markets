# Parallax Health Check — 2026-06-29

**Status: YELLOW**

## Summary

No code changes since 2026-06-22 — now the **7th consecutive stale day**. Tests hold at **17 failed, 416 passed, 13 skipped**, identical to all prior runs. Both long-running critical bugs remain unresolved: the missing `pytz` dependency (day 18) and the `scoring/ledger.py` SQL parameter binding error (day 9). All 17 failures trace to pytz; the ledger bug silently corrupts signal P&L records on every live run. Neither requires more than a one-line fix.

---

## Repository State

```
HEAD:         9e84fb9  chore: daily health check 2026-06-28 (YELLOW)
Tests:        17 failed | 416 passed | 13 skipped | 1 warning
              (failure set unchanged across all 7 stale days)
Code changes: NONE since 2026-06-22 (7th consecutive day)
```

---

## Issues Found

### CRITICAL

- **[CRITICAL — day 18] `pytz` absent from `pyproject.toml`**
  `pytz` is not listed in `[project.dependencies]`. DuckDB's Python extension requires it for `TIMESTAMPTZ` columns. In clean environments pytz is absent, causing **17 test failures** across `test_scorecard.py` (10), `test_crisis_context_db.py` (4), `test_llm_usage.py` (1), `test_ops_events.py` (1), `test_phase1_critical.py` (1). The `--scorecard` production CLI path is broken in any clean environment.
  - **Fix (one line):** Add `"pytz>=2024.1"` to `dependencies` in `backend/pyproject.toml`.
  - **Failure sample:** `_duckdb.InvalidInputException: Required module 'pytz' failed to import`

- **[CRITICAL — day 9] `scoring/ledger.py:267` SQL parameter binding bug**
  `update_execution()` passes `position_id` twice — once into the `trade_id = COALESCE(?, trade_id)` slot and again for `position_id`. Every call silently overwrites `trade_id` with the `position_id` value. Multi-leg orders are mis-recorded in the signal ledger.
  ```python
  # Current (bug) — line 267:
  [execution_status, entry_order_id, position_id, position_id, traded, trade_refused_reason, signal_id]
  # Fix: pass None for the trade_id slot:
  [execution_status, entry_order_id, None, position_id, traded, trade_refused_reason, signal_id]
  ```

---

### HIGH

- **[HIGH — escalated] `cryptography>=44.0` blocks fresh `pip install -e ".[dev]"`**
  `pip install -e ".[dev]"` without `--ignore-installed cryptography` fails with `ERROR: Cannot uninstall cryptography 41.0.7, RECORD file not found`. The workaround flag is not documented in the README, Dockerfile, or CI config.
  - **Fix:** Remove `"cryptography>=44.0"` from `pyproject.toml` — no direct import exists in the codebase (transitive dep only, pulled in by `truthbrush`).

- **[HIGH — day 12+] Single-writer pattern violated in 10+ modules**
  `DbWriter` (`db/writer.py`) is correctly implemented but bypassed in all production write paths. Modules with direct `conn.execute()` inserts/updates:
  - `cli/brief.py` — lines 130, 149, 431 (runs table, market_prices)
  - `scoring/ledger.py` — lines 225, 256 (signal_ledger inserts and updates)
  - `scoring/tracker.py` — lines 516, 674, 746 (trade positions, orders, fills)
  - `scoring/prediction_log.py` — line 79 (prediction_log)
  - `scoring/scorecard.py` — line 23 (daily_scorecard)
  - `budget/tracker.py` — line 43 (llm_usage)
  - `ops/alerts.py` — line 106 (ops_events, inside async handler)
  - `ingestion/crisis_ingester.py` — lines 54, 79 (crisis_events)
  - `contracts/registry.py` — lines 106, 116, 199 (contract_proxy_map, contract_registry)
  - `backtest/runner.py` — lines 292, 310 (backtest_runs, backtest_predictions)
  Concurrent FastAPI requests and background tasks race on the shared DuckDB connection.

- **[HIGH — carried] Missing HTTP error handling at market API boundaries**
  `markets/polymarket.py` calls `resp.raise_for_status()` across 5 methods with no surrounding `except`. `ingestion/oil_prices.py` uses `try/finally` but no `except`. Any 429, 5xx, or network timeout aborts the entire brief run with an unhandled exception.

- **[HIGH — carried] Sync DB writes blocking the async event loop in `cli/brief.py`**
  `_persist_run_start()` and `_persist_run_end()` are synchronous, called inside `async run_brief()`. They block the event loop and bypass the single-writer queue.

- **[HIGH — carried] Potential `AttributeError` in `cli/brief.py` ticker mapping**
  `active_contracts.get(mapping.contract_ticker).title` is called without a null guard. If `mapping.contract_ticker` is absent from `active_contracts`, `.title` raises `AttributeError`, crashing the brief run.

---

### MEDIUM

- **[MEDIUM — carried] `PRICE_ELASTICITY = 3.0` hardcoded in `simulation/cascade.py`**
  Spec §4 requires all cascade parameters to be tunable via `scenario_hormuz.yaml`. This constant is not a YAML field and cannot be adjusted without a code change.

- **[MEDIUM — carried] `simulation/circuit_breaker.py` not implemented**
  Spec §4 defines escalation limits (max 1 level/tick, 3-tick cooldown, Goldstein exogenous override). `ScenarioConfig` already carries all three parameters. Neither the module nor `test_circuit_breaker.py` exist.

- **[MEDIUM — carried] 13 mapping-policy tests permanently skipped**
  All 13 are marked `@pytest.mark.skip(reason=_PRE_REFACTOR_REASON)`. The current fair-value / fee-subtraction architecture has no replacement coverage for these contract classes.

- **[MEDIUM — carried] Prediction fallbacks silently mask missing data**
  `oil_price.py` falls back to `$100.0` when EIA data is unavailable; `hormuz.py` defaults `hormuz_daily_flow` via `getattr` with no warning logged. Bad input produces confident-looking predictions with no observability.

- **[MEDIUM — carried] Architectural pivot undocumented in spec**
  The live system is a 3-model prediction-market edge-finder; the Phase 1 spec describes a 50-agent LLM swarm with H3 geospatial visualization. `CLAUDE.md` reflects the current design accurately but the spec has not been updated to match reality.

---

### LOW

- **[LOW — carried] No frontend test infrastructure**
  Zero Jest/Vitest tests for any of the 9 React components or the `usePolling` hook.

- **[LOW — carried] `starlette.testclient` deprecation warning**
  `StarletteDeprecationWarning: Using httpx with starlette.testclient is deprecated; install httpx2 instead` emitted on every test run.

- **[LOW — carried] `requires-python = ">=3.11"` vs spec's Python 3.12**
  `CLAUDE.md` and the plan specify Python 3.12. Looser pin is harmless in practice; no 3.11-incompatible syntax found.

- **[LOW — carried] No linter or formatter enforced**
  No `ruff`, `black`, or `pre-commit` hook. Code style is consistent by convention only.

---

## Spec/Plan Consistency

| Area | Status | Notes |
|---|---|---|
| DB schema (20+ tables) | ✓ Compliant | All plan-spec tables present plus additional trading/backtest tables |
| Single-writer topology | ✗ Violated | `DbWriter` exists but 10+ modules bypass it with direct execute calls |
| Cascade engine (6 rules) | ⚠ Partial | All 6 rules present; `PRICE_ELASTICITY` not YAML-tunable; `circuit_breaker.py` absent |
| GDELT ingestion | ⚠ Partial | Volume gate + entity override present; semantic dedup not implemented |
| Agent swarm (50 agents) | ✗ Deferred | Intentional pivot — 3 monolithic LLM predictors instead |
| Eval framework | ✗ Deferred | `calibration.py` covers scoring metrics; no formal per-agent eval harness |
| Frontend dashboard | ✓ Evolved | React SPA with 9 components; deck.gl/H3 geospatial visualization deferred |
| Paper trading (Kalshi) | ✓ Compliant | Full order lifecycle, RSA-PSS auth, sandbox/production separation |
| Budget cap ($20/day) | ✓ Compliant | `BudgetTracker` functional; writes bypass DbWriter queue |
| `ledger.py` UPDATE correctness | ✗ Bug | `trade_id` receives `position_id` value on every call (day 9) |
| `pyproject.toml` dependencies | ✗ Incomplete | `pytz` missing (day 18); `cryptography>=44.0` blocks fresh install |

---

## Dependency Snapshot

| Package | `pyproject.toml` | Status |
|---|---|---|
| duckdb | `>=1.2` | OK |
| pytz | **MISSING** | Day 18 — 17 test failures in clean envs |
| cryptography | `>=44.0` | Blocks `pip install -e ".[dev]"` without `--ignore-installed` |
| fastapi | `>=0.115` | OK |
| anthropic | `>=0.52` | OK |
| truthbrush | `>=0.2` | OK |

---

## Recommendations (Priority Order)

1. **Immediate (day 18 overdue)** — Add `"pytz>=2024.1"` to `[project.dependencies]` in `backend/pyproject.toml`. Resolves all 17 failing tests in one line.

2. **Immediate (day 9 overdue)** — Fix `scoring/ledger.py:267`: replace the 3rd list element (`position_id`) with `None` to stop overwriting `trade_id` on every `update_execution()` call. Signal P&L records are silently corrupted until this lands.

3. **Immediate** — Remove `"cryptography>=44.0"` from `pyproject.toml`. Fresh `pip install -e ".[dev]"` fails entirely on this conflict, taking all 42 test modules with it.

4. **Short-term** — Add `try/except (httpx.HTTPStatusError, httpx.RequestError)` around the 5 unguarded methods in `markets/polymarket.py` and the EIA fetch path in `ingestion/oil_prices.py`.

5. **Short-term** — In `cli/brief.py`: (a) add a `None` guard before `.title` on the `active_contracts.get()` result; (b) convert `_persist_run_start()` / `_persist_run_end()` to async and route writes through `DbWriter`.

6. **Medium-term** — Write replacement tests for the 13 skipped mapping-policy scenarios, covering the current fair-value / fee-subtraction architecture.

7. **Medium-term** — Wire `DbWriter` into async-path write sites: `ops/alerts.py`, `budget/tracker.py`, `scoring/ledger.py`, `scoring/prediction_log.py`, `ingestion/crisis_ingester.py`.

8. **Medium-term** — Add `price_elasticity` field to `scenario_hormuz.yaml` + `ScenarioConfig`; implement `simulation/circuit_breaker.py` + `test_circuit_breaker.py`.
