# Parallax Health Check — 2026-06-19

**Status: YELLOW**

## Summary

No code changes landed on `main` since the 2026-06-18 report (HEAD remains `459adcd`). All critical issues from prior reports remain unresolved. Today's deeper static audit surfaced **one confirmed new bug**: `scoring/ledger.py` line 267 passes `position_id` twice in the SQL parameter list, silently writing `position_id` into the `trade_id` column on every `update_execution()` call. The overall picture is stable but deteriorating: `pytz` has now been missing for **8 days**, and 3 of the 4 critical blockers are one-line fixes that are not being applied.

---

## Repository State

```
HEAD:         459adcd  chore: daily health check 2026-06-18 (YELLOW)
Tests:        Cannot run — pytest/duckdb not installed in this environment
              (Last known: 410 passed | 17 failed | 13 skipped | 6 errors)
Code changes: NONE since 2026-06-18
```

---

## Issues Found

### CRITICAL

- **[CRITICAL — day 8] `pytz` absent from `pyproject.toml`**
  Breaks `--scorecard` CLI path, `BudgetTracker`, `DuckDBAlertSink`, and `crisis_events` DB path in production. In tests: 17 failures across `test_scorecard.py` (10), `test_crisis_context_db.py` (4), `test_llm_usage.py` (1), `test_ops_events.py` (1), `test_phase1_critical.py` (1). DuckDB's `DATE()`/`TIMESTAMPTZ` operations fail at runtime when pytz is absent.
  - **Fix (one line)**: Add `"pytz>=2024.1"` to `dependencies` in `backend/pyproject.toml`.

- **[CRITICAL — day 2] DuckDB 1.5.4 breaks H3 community extension**
  `conftest.py` unconditionally executes `INSTALL h3 FROM community; LOAD h3;` at fixture setup. H3 has no binary for DuckDB 1.5.4 `linux_amd64` (HTTP 404). All tests using the `db` fixture error before running — currently `test_schema.py` (3 errors) and `test_writer.py` (3 errors). These are the foundational DB tests; regressions in schema and write correctness go undetected.
  - **Fix A (immediate)**: Wrap the H3 install in `conftest.py` with `try/except Exception: pass` — most schema and writer tests don't require H3.
  - **Fix B (proper)**: Pin `"duckdb>=1.2,<1.5.4"` in `pyproject.toml` until the H3 community extension publishes a 1.5.4 build.

- **[CRITICAL — NEW] `scoring/ledger.py:267` SQL parameter binding bug**
  `update_execution()` has 7 `?` placeholders in its UPDATE statement but the parameter list passes `position_id` in both the 3rd slot (intended for `trade_id = COALESCE(?, trade_id)`) and the 4th slot (correct for `position_id = COALESCE(?, position_id)`). The method signature has no `trade_id` parameter, so `trade_id` and `position_id` columns always receive the same value. Any signal where `trade_id ≠ position_id` (e.g., multi-leg orders) will be silently mis-recorded.
  ```python
  # line 267 — current (bug):
  [execution_status, entry_order_id, position_id, position_id, traded, trade_refused_reason, signal_id]
  # Fix: add trade_id parameter to method signature and pass it as 3rd element,
  # or pass None to leave trade_id unchanged when not updating it:
  [execution_status, entry_order_id, None, position_id, traded, trade_refused_reason, signal_id]
  ```

---

### HIGH

- **[HIGH — day 7+] Single-writer pattern violated across 10+ modules**
  `DbWriter` is correctly implemented in `db/writer.py` but is wired to zero callers. Static count: **137 direct `conn.execute()` INSERT/UPDATE calls** outside `db/writer.py` and `db/schema.py`. Concurrent FastAPI requests and background brief tasks race on the shared DuckDB connection.
  - Affected modules: `scoring/ledger.py`, `scoring/tracker.py`, `scoring/prediction_log.py`, `scoring/scorecard.py`, `ops/alerts.py`, `budget/tracker.py`, `ingestion/crisis_ingester.py`, `contracts/registry.py`, `cli/brief.py`, `main.py`.

- **[HIGH — day 5] Missing HTTP error handling in `polymarket.py` and `oil_prices.py`**
  Five methods in `markets/polymarket.py` call `resp.raise_for_status()` with no surrounding exception handler. `ingestion/oil_prices.py` uses `try/finally` but no `except`. Any 429, 5xx, or network timeout aborts the entire brief run.

- **[HIGH — NEW] `cli/brief.py` sync helpers called in async context**
  `_persist_run_start()` and `_persist_run_end()` are synchronous functions that contain `conn.execute()` writes. They are called inside the async `run_brief()` coroutine without `await`. This blocks the event loop during DB writes and — because they aren't submitted through `DbWriter` — bypasses the single-writer queue.

- **[HIGH — NEW] Potential `AttributeError` in `cli/brief.py` ticker mapping**
  `active_contracts.get(mapping.contract_ticker).title` is called without a null guard. If `mapping.contract_ticker` is not in `active_contracts` (e.g., a new contract not yet in the registry), `get()` returns `None` and `.title` raises `AttributeError`, crashing the brief run silently.

- **[HIGH — day 2] `cryptography>=44.0` conflicts with system package on non-Docker environments**
  System `cryptography` is 41.0.7 (Debian). Fresh `pip install -e ".[dev]"` fails before registering `parallax`, causing all 42 test files to surface as collection errors. CI environments without Docker are silently blocked.
  - **Fix A**: Drop `"cryptography>=44.0"` from `pyproject.toml` — it is a transitive dependency of `httpx`; no direct import found in the codebase.
  - **Fix B**: Add `--ignore-installed cryptography` to the CI install step.

---

### MEDIUM

- **[MEDIUM — carried] `PRICE_ELASTICITY = 3.0` hardcoded in `simulation/cascade.py`**
  Spec §4 requires all cascade parameters to be tunable via `scenario_hormuz.yaml`. `PRICE_ELASTICITY` is a module-level constant, not a YAML field.
  - **Fix**: Add `price_elasticity: 3.0` to the YAML, add field to `ScenarioConfig`, use `self._config.price_elasticity` in `compute_price_shock()`.

- **[MEDIUM — carried] `simulation/circuit_breaker.py` not implemented**
  Spec §4 defines escalation limits (max 1 level/tick, 3-tick cooldown, Goldstein exogenous override). `ScenarioConfig` carries all three parameters. Neither the module nor `test_circuit_breaker.py` exist.

- **[MEDIUM — carried] GDELT semantic dedup not implemented**
  `sentence-transformers` was removed without a replacement. Duplicate GDELT events can reach prediction models unchanged. URL/title hash dedup is the only filter in place.

- **[MEDIUM — carried] Prediction fallbacks silently mask missing data**
  `oil_price.py` falls back to `$100.0` when EIA data is unavailable; `hormuz.py` defaults `hormuz_daily_flow` to 21,000,000 via `getattr` with no warning logged. Bad data produces confident-looking predictions.

- **[MEDIUM — carried] Architectural pivot undocumented in spec**
  Live system is a 3-model prediction-market edge-finder; Phase 1 spec describes a 50-agent LLM swarm with H3 geospatial visualization. Modules `agents/`, `eval/`, `spatial/`, and `simulation/engine.py` are absent. `CLAUDE.md` accurately reflects the current design but the spec has not been updated. No operational risk — noted for traceability.

---

### LOW

- **[LOW — carried] No frontend test infrastructure**
  Zero Jest/Vitest tests for any of the 9 React components or the `usePolling` hook.

- **[LOW — carried] `starlette.testclient` deprecation warning**
  Emitted on every test run. No runtime breakage.

- **[LOW — carried] `requires-python = ">=3.11"` vs spec's Python 3.12**
  No 3.11-incompatible syntax found; looser pin is harmless in practice.

- **[LOW — carried] No linter or formatter enforced**
  No `ruff`, `black`, or `pre-commit` hook. Style is consistent by convention only.

---

## Dependency Snapshot

| Package | Installed (env) | `pyproject.toml` | Status |
|---|---|---|---|
| duckdb | NOT INSTALLED | `>=1.2` | Last known: 1.5.4 — breaks H3 ext |
| pytz | NOT INSTALLED | **MISSING** | **Day 8 — breaks 17 tests + production paths** |
| cryptography | 41.0.7 (system) | `>=44.0` | Conflict — blocks fresh `pip install` |
| fastapi | NOT INSTALLED | `>=0.115` | Not in this env (Docker-only) |
| anthropic | NOT INSTALLED | `>=0.52` | Not in this env |
| truthbrush | NOT INSTALLED | `>=0.2` | Not in this env |

---

## Spec/Plan Consistency

| Area | Status | Notes |
|---|---|---|
| DB schema (20+ tables) | ✓ Compliant | All plan-spec tables present |
| Single-writer topology | ✗ Violated | `DbWriter` exists; 137 direct execute calls bypass it |
| Cascade engine | ⚠ Partial | 6 rules present; `PRICE_ELASTICITY` not YAML-tunable; `circuit_breaker.py` absent |
| GDELT ingestion | ⚠ Partial | Volume gate + entity override present; semantic dedup absent |
| Agent swarm (50 agents) | ✗ Deferred | Intentional pivot — 3 monolithic LLM models instead |
| Eval framework | ✗ Deferred | `calibration.py` covers scoring; no formal eval harness |
| Frontend dashboard | ✓ Compliant | React SPA with 9 components; geospatial viz deferred |
| Paper trading (Kalshi) | ✓ Compliant | Full order lifecycle, RSA-PSS auth, sandbox separation |
| Budget cap ($20/day) | ✓ Compliant | `BudgetTracker` wired; writes bypass DbWriter queue |
| `ledger.py` UPDATE correctness | ✗ Bug | `trade_id` column receives `position_id` value on every call |
| `conftest.py` H3 fixture | ✗ Broken | Unconditional `INSTALL h3` fails on DuckDB 1.5.4 |

---

## Recommendations (Priority Order)

1. **Immediate (8 days overdue)** — Add `"pytz>=2024.1"` to `backend/pyproject.toml`. Restores 17 failing tests and unblocks the `--scorecard` CLI path in production.

2. **Immediate** — In `conftest.py`, wrap `INSTALL h3 FROM community; LOAD h3;` in `try/except Exception: pass`. Restores 6 erroring tests.

3. **Immediate (NEW)** — Fix `scoring/ledger.py:267`: add a `trade_id: str | None = None` parameter to `update_execution()` and pass it as the 3rd element in the parameter list (or pass `None` to leave `trade_id` unchanged). Corrects silent data corruption on every `update_execution` call.

4. **Short-term** — Fix the two high-severity bugs in `cli/brief.py`: (a) add a `None` guard before accessing `.title` on the `active_contracts.get()` result; (b) convert `_persist_run_start()` and `_persist_run_end()` to async and route their writes through `DbWriter`.

5. **Short-term** — Drop `"cryptography>=44.0"` from `pyproject.toml` (transitive dep, no direct import). Unblocks fresh `pip install` on non-Docker hosts.

6. **Short-term** — Add `try/except (httpx.HTTPStatusError, httpx.RequestError)` to 5 methods in `polymarket.py` and to `oil_prices.py`. Prevents entire brief-run crash on transient API failures.

7. **Medium-term** — Wire `DbWriter` into async-path modules: `ops/alerts.py`, `budget/tracker.py`, `scoring/ledger.py`, `scoring/prediction_log.py`, `ingestion/crisis_ingester.py`, `contracts/registry.py`.

8. **Medium-term** — Move `PRICE_ELASTICITY` to `scenario_hormuz.yaml` + `ScenarioConfig`. Implement `simulation/circuit_breaker.py` + `test_circuit_breaker.py`.
