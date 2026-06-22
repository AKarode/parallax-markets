# Parallax Health Check — 2026-06-22

**Status: YELLOW**

## Summary

No code changes since the 2026-06-21 health check (HEAD remains `88da945`). In today's environment all **433 tests pass** (pytz is available system-wide here, and H3 extension now loads successfully on DuckDB 1.5.4), but two long-standing CRITICAL bugs remain unresolved in the source: `pytz` is still absent from `pyproject.toml` (day 11 — breaks scorecard and LLM tracking in any clean environment) and the `scoring/ledger.py:267` parameter binding bug still silently writes `position_id` into the `trade_id` column on every `update_execution()` call (day 4). Architecture and dependency drift versus the Phase 1 spec are documented below for completeness.

---

## Repository State

```
HEAD:         88da945  chore: daily health check 2026-06-21 (YELLOW)
Tests:        433 passed | 0 failed | 13 skipped | 1 warning
              (pytz available in this env; H3 extension loads on DuckDB 1.5.4)
DuckDB:       1.5.4
Python:       3.11.x
Code changes: NONE since 2026-06-21
```

---

## Issues Found

### CRITICAL

- **[CRITICAL — day 11] `pytz` absent from `pyproject.toml`**
  `pytz` is not listed in `[project.dependencies]` yet DuckDB's Python extension requires it to resolve `TIMESTAMPTZ` columns. In this environment pytz (`2026.2`) happened to be present system-wide, masking the problem. In any fresh Docker build or CI environment without pytz pre-installed, 17 tests fail across `test_scorecard.py` (10), `test_crisis_context_db.py` (4), `test_llm_usage.py` (1), `test_ops_events.py` (1), `test_phase1_critical.py` (1). The `--scorecard` production CLI path is broken without it.
  - **Fix (one line):** Add `"pytz>=2024.1"` to `dependencies` in `backend/pyproject.toml`.

- **[CRITICAL — day 4] `scoring/ledger.py:267` SQL parameter binding bug**
  `update_execution()` passes `position_id` twice — once in the `trade_id = COALESCE(?, trade_id)` slot and once in `position_id = COALESCE(?, position_id)`. The method signature has no `trade_id` parameter, so every call overwrites `trade_id` with the `position_id` value. Multi-leg orders with distinct `trade_id` / `position_id` values are silently mis-recorded in the signal ledger.
  ```python
  # line 267 — current (bug):
  [execution_status, entry_order_id, position_id, position_id, traded, trade_refused_reason, signal_id]
  # Fix: pass None for the trade_id slot to leave it unchanged:
  [execution_status, entry_order_id, None, position_id, traded, trade_refused_reason, signal_id]
  ```

---

### HIGH

- **[HIGH — day 9+] Single-writer pattern violated in multiple modules**
  `DbWriter` (`db/writer.py`) is correctly implemented but bypassed in production paths:
  - `backtest/runner.py` — 4 direct `INSERT`/`UPDATE` calls to `backtest_runs` and `backtest_predictions` (lines 290, 308, 329, 356).
  - `ops/alerts.py:106` — `DuckDBAlertSink.send()` does a direct `INSERT` into `ops_events` on every alert, including from async request handlers.
  - Additional violations in `scoring/ledger.py`, `scoring/tracker.py`, `scoring/prediction_log.py`, `scoring/scorecard.py`, `budget/tracker.py`, `cli/brief.py`.
  Concurrent FastAPI requests and background brief tasks race on the shared DuckDB connection.

- **[HIGH — day 7+] Missing HTTP error handling at market API boundary**
  `markets/polymarket.py` calls `resp.raise_for_status()` across 5 methods with no surrounding `except`. `ingestion/oil_prices.py` uses `try/finally` but no `except`. Any 429, 5xx, or network timeout aborts the entire brief run with an unhandled exception.

- **[HIGH — day 4] `cryptography>=44.0` conflicts with system package on non-Docker environments**
  System cryptography is `41.0.7` (Debian). A fresh `pip install -e ".[dev]"` fails with `Cannot uninstall cryptography 41.0.7, RECORD file not found`. Workaround requires `--ignore-installed cryptography`, which is non-obvious and blocks CI.
  - **Fix:** Remove `"cryptography>=44.0"` from `pyproject.toml` — it is a transitive dependency of `httpx` with no direct import in the codebase.

- **[HIGH — carried] `cli/brief.py` sync DB writes in async context**
  `_persist_run_start()` and `_persist_run_end()` are synchronous and call `conn.execute()` directly inside the `async run_brief()` coroutine. This blocks the event loop during writes and bypasses the single-writer queue.

- **[HIGH — carried] Potential `AttributeError` in `cli/brief.py` ticker mapping**
  `active_contracts.get(mapping.contract_ticker).title` is called without a null guard. If `mapping.contract_ticker` is absent from `active_contracts`, `get()` returns `None` and `.title` raises `AttributeError`, crashing the brief run.

---

### MEDIUM

- **[MEDIUM — carried] `PRICE_ELASTICITY = 3.0` hardcoded in `simulation/cascade.py`**
  Spec §4 requires all cascade parameters to be tunable via `scenario_hormuz.yaml`. `PRICE_ELASTICITY` is a module-level constant (`cascade.py:35`), not a YAML field. The `ScenarioConfig` dataclass and YAML have no `price_elasticity` key.

- **[MEDIUM — carried] `simulation/circuit_breaker.py` not implemented**
  Spec §4 defines escalation limits (max 1 level/tick, 3-tick cooldown, Goldstein exogenous override). `ScenarioConfig` carries all three parameters. Neither the module nor `test_circuit_breaker.py` exist.

- **[MEDIUM — carried] 13 mapping-policy tests permanently skipped**
  All 13 are marked `@pytest.mark.skip(reason=_PRE_REFACTOR_REASON)` — they tested pre-refactor edge-multiplied discount behavior that no longer applies. The new fair-value / fee-subtraction architecture has no equivalent coverage for these contract classes.

- **[MEDIUM — carried] Prediction fallbacks silently mask missing data**
  `oil_price.py` falls back to `$100.0` when EIA data is unavailable; `hormuz.py` defaults `hormuz_daily_flow` to `21,000,000` via `getattr` with no warning logged. Bad input produces confident-looking predictions with no observability.

- **[MEDIUM — carried] Architectural pivot undocumented in spec**
  The live system is a 3-model prediction-market edge-finder; Phase 1 spec describes a 50-agent LLM swarm with H3 geospatial visualization. `CLAUDE.md` accurately reflects the current design but the spec (`docs/superpowers/specs/2026-03-30-parallax-phase1-design.md`) has not been updated. No operational risk — noted for traceability.

---

### LOW

- **[LOW — carried] No frontend test infrastructure**
  Zero Jest/Vitest tests for any of the 9 React components or the `usePolling` hook.

- **[LOW — carried] `starlette.testclient` deprecation warning**
  `StarletteDeprecationWarning: Using httpx with starlette.testclient is deprecated; install httpx2 instead` is emitted on every test run. No runtime breakage but signals a pending upgrade.

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
| `ledger.py` UPDATE correctness | ✗ Bug | `trade_id` receives `position_id` value on every call (day 4) |
| `pyproject.toml` dependencies | ✗ Incomplete | `pytz` missing; `cryptography>=44.0` conflicts with system |

---

## Dependency Snapshot

| Package | Installed (this env) | `pyproject.toml` | Status |
|---|---|---|---|
| duckdb | 1.5.4 | `>=1.2` | H3 extension now loads on 1.5.4 ✓ |
| pytz | 2026.2 (system) | **MISSING** | Day 11 — breaks 17 tests in clean environments |
| cryptography | 41.0.7 (system) | `>=44.0` | Version conflict — blocks fresh `pip install` |
| fastapi | ✓ | `>=0.115` | OK |
| anthropic | ✓ | `>=0.52` | OK |
| truthbrush | ✓ | `>=0.2` | OK |

---

## Recommendations (Priority Order)

1. **Immediate (day 11 overdue)** — Add `"pytz>=2024.1"` to `[project.dependencies]` in `backend/pyproject.toml`.

2. **Immediate (day 4 overdue)** — Fix `scoring/ledger.py:267`: replace the 3rd list element from `position_id` to `None` to stop overwriting `trade_id` on every `update_execution()` call.

3. **Short-term** — Remove `"cryptography>=44.0"` from `pyproject.toml`. It is a transitive dep with no direct import; the conflict blocks all non-Docker installs.

4. **Short-term** — Add `try/except (httpx.HTTPStatusError, httpx.RequestError)` to the 5 unguarded methods in `markets/polymarket.py` and the EIA fetch path in `ingestion/oil_prices.py`.

5. **Short-term** — In `cli/brief.py`: (a) add a `None` guard before `.title` on the `active_contracts.get()` result; (b) convert `_persist_run_start()` / `_persist_run_end()` to async and route writes through `DbWriter`.

6. **Medium-term** — Write replacement tests for the 13 skipped mapping-policy scenarios, covering the current fair-value / fee-subtraction architecture.

7. **Medium-term** — Wire `DbWriter` into async-path modules: `ops/alerts.py`, `budget/tracker.py`, `scoring/ledger.py`, `scoring/prediction_log.py`, `ingestion/crisis_ingester.py`.

8. **Medium-term** — Add `price_elasticity` field to `scenario_hormuz.yaml` + `ScenarioConfig`; implement `simulation/circuit_breaker.py` + `test_circuit_breaker.py`.
