# Parallax Health Check — 2026-06-15

**Status: YELLOW**

## Summary

No commits landed on main since the 2026-06-14 health check (HEAD remains at `b49aadc`). All issues flagged yesterday carry forward unresolved. The `pytz` gap is now on **day 4** — it has blocked the same 17 tests every single run and is a one-line fix. Single-writer violations across async-path modules remain the next highest-leverage item.

---

## Test Run Summary

```
416 passed  |  17 failed  |  13 skipped
```

**All 17 failures share one root cause:**
```
_duckdb.InvalidInputException: Required module 'pytz' failed to import
ModuleNotFoundError: No module named 'pytz'
```

DuckDB 1.5.3 requires `pytz` for `DATE()` / `TIMESTAMPTZ` operations. `pytz` is absent from `backend/pyproject.toml`.

| Failing test file | # failures |
|---|---|
| `test_scorecard.py` | 11 |
| `test_crisis_context_db.py` | 4 |
| `test_llm_usage.py` | 1 |
| `test_ops_events.py` | 1 |
| `test_phase1_critical.py` | 1 (context-age path) |

**Passing**: core cascade, schema, world state, writer, markets (Kalshi, Polymarket), scoring, ledger, calibration, backtest, contracts, registry, divergence, dashboard, mapping policy, recalibration, ensemble — all green.

**Note**: `test_truth_social.py` was collected without error today (truthbrush present in environment), but `--ignore` is still advisable in CI due to the system `cryptography 41.0.7` conflict on some machines.

---

## Issues Found

### CRITICAL

- **[CRITICAL] `pytz` missing from `pyproject.toml`** *(day 4 — first flagged 2026-06-12)*
  DuckDB 1.5.3 requires `pytz` to evaluate any `DATE()` predicate or query a `TIMESTAMPTZ` column. `pytz` is not listed in `backend/pyproject.toml`. Every production `--scorecard` run, budget tracker write, ops alert sink, and crisis context DB path is broken at runtime — not just in tests.
  - **Fix (one line)**: Add `"pytz>=2024.1"` to `dependencies` in `backend/pyproject.toml`.
  - This issue has been flagged for 4 consecutive days with no action. It is the only blocker between YELLOW and GREEN.

---

### HIGH

- **[HIGH] Single-writer pattern violated in async-path modules** *(carried — day 5+)*
  Confirmed `INSERT`/`UPDATE` operations via raw `conn.execute()` outside `db/writer.py` in 10+ modules:
  `scoring/ledger.py`, `ops/alerts.py`, `budget/tracker.py`, `ingestion/crisis_ingester.py`, `contracts/registry.py`, `scoring/prediction_log.py`, `scoring/scorecard.py`, `scoring/tracker.py`, `backtest/runner.py`.
  `DbWriter` exists and is correctly implemented but is not wired to async-path callers. Risk: concurrent FastAPI requests and background brief tasks race on the shared DuckDB connection.
  - **Fix**: Pass the `DbWriter` instance to async-path modules at construction and call `await writer.enqueue(sql, params)`. CLI batch modules (`scorecard.py`) are lower priority.

- **[HIGH] Missing `try/except` on Polymarket HTTP calls** *(carried — day 3)*
  Five methods in `polymarket.py` call `resp.raise_for_status()` with no surrounding exception handler. Any 429, 5xx, or network timeout aborts the entire brief run.
  - **Fix**: Wrap each `async with httpx.AsyncClient()` block in `try/except (httpx.HTTPStatusError, httpx.RequestError)`, log a warning, return `None`/empty.

- **[HIGH] Missing `except` clause in `oil_prices.py`** *(carried — day 3)*
  `fetch_brent()` / `fetch_wti()` use `try/finally` with no `except`. EIA API errors (4xx, timeout, malformed JSON) propagate and crash the brief pipeline.
  - **Fix**: Add `except (httpx.HTTPStatusError, httpx.RequestError, json.JSONDecodeError)` before `finally`, log a warning, return `[]`.

---

### MEDIUM

- **[MEDIUM] `PRICE_ELASTICITY = 3.0` hardcoded in `cascade.py`** *(carried)*
  Spec §4 requires all cascade parameters to be tunable via `scenario_hormuz.yaml`. `PRICE_ELASTICITY` is a module-level constant, not a YAML field.
  - **Fix**: Add `price_elasticity: 3.0` to the YAML; add the field to `ScenarioConfig`; use `self._config.price_elasticity` in `compute_price_shock()`.

- **[MEDIUM] `simulation/circuit_breaker.py` not implemented** *(carried)*
  Spec §4 defines escalation limits (max 1 level/tick, 3-tick cooldown, Goldstein exogenous override). `ScenarioConfig` already carries all three parameters. Module absent; `test_circuit_breaker.py` absent.

- **[MEDIUM] `ingestion/dedup.py` not implemented** *(carried)*
  Semantic dedup (`SemanticDeduplicator` via `all-MiniLM-L6-v2`) is absent; `sentence-transformers` is not in `pyproject.toml`. Duplicate events can reach the prediction models.

- **[MEDIUM] Architectural pivot documented but not reconciled** *(stable — intentional)*
  The live system is a 3-model prediction-market edge-finder; the Phase 1 spec describes a 50-agent LLM swarm with H3 geospatial visualization. `CLAUDE.md` documents the current design. Modules `agents/`, `eval/`, `spatial/`, `api/`, `simulation/engine.py` absent per pivot decision. No operational risk — noting for spec traceability.

---

### LOW

- **[LOW] `starlette.testclient` deprecation warning** *(carried)*
  Test runs emit `StarletteDeprecationWarning: Using httpx with starlette.testclient is deprecated; install httpx2 instead.` No runtime breakage today.

- **[LOW] `requires-python = ">=3.11"` vs spec's Python 3.12** *(carried)*
  No 3.11-incompatible syntax found; looser pin is harmless in practice.

- **[LOW] No linter or formatter enforced** *(carried)*
  No `ruff`, `black`, or `pre-commit` hook configured. Style is consistent by convention only.

- **[LOW] 6 spec-required deps absent from `pyproject.toml`** *(stable — intentional)*
  `h3`, `sentence-transformers`, `searoute`, `shapely`, `google-cloud-bigquery`, `websockets` — all from the unbuilt geospatial pipeline.

---

## Dependency Snapshot

| Package | Installed | In pyproject.toml | Notes |
|---|---|---|---|
| duckdb | 1.5.3 | ≥1.2 ✓ | |
| fastapi | latest | ≥0.115 ✓ | |
| anthropic | latest | ≥0.52 ✓ | |
| pydantic | latest | ≥2.10 ✓ | |
| httpx | latest | ≥0.28 ✓ | |
| cryptography | 41.0.7 (system) | ≥44.0 ✗ | Debian conflict; Docker works |
| **pytz** | **NOT INSTALLED** | **MISSING** | **Blocks 17 tests + production** |
| truthbrush | present | ≥0.2 ✓ | CI install may conflict |

---

## Recommendations (Priority Order)

1. **Immediate (1 line — do it now)**: Add `"pytz>=2024.1"` to `dependencies` in `backend/pyproject.toml`. This is on day 4 with no action and is a one-liner.

2. **Short-term**: Add `try/except (httpx.HTTPStatusError, httpx.RequestError)` to `polymarket.py` (5 methods) and `oil_prices.py`. Prevents brief-run crashes on transient external API failures.

3. **Short-term**: Add `price_elasticity: 3.0` to `scenario_hormuz.yaml` + `ScenarioConfig`; remove the module constant from `cascade.py`.

4. **Medium-term**: Wire `DbWriter` into async-path modules (`ops/alerts.py`, `budget/tracker.py`, `scoring/ledger.py`, `scoring/prediction_log.py`, `ingestion/crisis_ingester.py`, `contracts/registry.py`).

5. **Medium-term**: Implement `simulation/circuit_breaker.py` + `test_circuit_breaker.py`.
