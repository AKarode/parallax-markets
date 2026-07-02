# Parallax Health Check — 2026-06-17

**Status: YELLOW**

## Summary

No commits have landed on main since the 2026-06-16 health check (HEAD remains at `d15fea0`). The `pytz` missing-dependency is now on **day 6** with the same 17 test failures and no resolution. A **new deployment risk** was surfaced today: `pip install -e ".[dev]"` exits with ERROR on this system because the system `cryptography` package (Debian 41.0.7) cannot be uninstalled, leaving the `parallax` package entirely unregistered and all 43 test files failing with `ModuleNotFoundError: No module named 'parallax'` until the flag `--ignore-installed cryptography` is applied. This is a silent failure that looks like "42 errors" in CI/fresh environments. All other issues carry forward unchanged.

---

## Test Run Summary

```
416 passed  |  17 failed  |  13 skipped
```

**Root cause of all 17 failures (unchanged):**
```
_duckdb.InvalidInputException: Required module 'pytz' failed to import
ModuleNotFoundError: No module named 'pytz'
```

DuckDB 1.5.3 requires `pytz` for `DATE()` / `TIMESTAMPTZ` operations. `pytz` is absent from `backend/pyproject.toml`.

| Failing test file | # failures |
|---|---|
| `test_scorecard.py` | 10 |
| `test_crisis_context_db.py` | 4 |
| `test_llm_usage.py` | 1 |
| `test_ops_events.py` | 1 |
| `test_phase1_critical.py` | 1 (context-age path) |

**Passing**: core cascade, schema, world state, writer, markets (Kalshi, Polymarket), scoring, ledger, calibration, backtest, contracts, registry, divergence, dashboard, mapping policy, recalibration, ensemble — all green.

---

## Issues Found

### CRITICAL

- **[CRITICAL] `pytz` missing from `pyproject.toml`** *(day 6 — first flagged 2026-06-12)*
  DuckDB 1.5.3 requires `pytz` to evaluate any `DATE()` predicate or query a `TIMESTAMPTZ` column. `pytz` is not listed in `backend/pyproject.toml`. The `--scorecard` CLI path, budget tracker write, ops alert sink, and crisis context DB path are all broken in production as well as in tests. This has now been flagged for **6 consecutive daily runs** with no remediation.
  - **Fix (one line)**: Add `"pytz>=2024.1"` to `dependencies` in `backend/pyproject.toml`.

---

### HIGH

- **[HIGH — NEW] `pip install -e ".[dev]"` fails silently on non-Docker environments**
  The system has `cryptography 41.0.7` installed by Debian. Running `pip install -e ".[dev]"` exits with `ERROR: Cannot uninstall cryptography 41.0.7, RECORD file not found` before registering the `parallax` package. This leaves the package uninstalled, causing all 43 test files to fail collection with `ModuleNotFoundError: No module named 'parallax'` — which surfaces as "42 errors" rather than "17 failures." CI or any fresh environment without Docker will hit this. The fix requires `--ignore-installed cryptography` or removing the `cryptography>=44.0` pin from `pyproject.toml` (the current code doesn't appear to use it directly).
  - **Fix option A**: Drop `cryptography>=44.0` from `pyproject.toml` (it is pulled in transitively by `httpx`/`kalshi` — no direct import).
  - **Fix option B**: Add `--ignore-installed cryptography` to CI install step and `Dockerfile`.

- **[HIGH] Single-writer pattern violated in async-path modules** *(carried — day 6+)*
  `INSERT`/`UPDATE` operations via raw `conn.execute()` outside `db/writer.py` confirmed in 10+ modules across 25 files (174 total `.execute()` calls). `DbWriter` is correctly implemented but wired to zero callers. Risk: concurrent FastAPI requests and background brief tasks race on the shared DuckDB connection.
  Affected modules: `scoring/ledger.py`, `ops/alerts.py`, `budget/tracker.py`, `ingestion/crisis_ingester.py`, `contracts/registry.py`, `scoring/prediction_log.py`, `scoring/scorecard.py`, `scoring/tracker.py`, `backtest/runner.py`, `main.py`.
  - **Fix**: Pass `DbWriter` instance to async-path modules; call `await writer.enqueue(sql, params)` instead of `conn.execute()`.

- **[HIGH] Missing `try/except` on Polymarket HTTP calls** *(carried — day 4)*
  Five methods in `polymarket.py` call `resp.raise_for_status()` with no surrounding exception handler. Any 429, 5xx, or network timeout aborts the entire brief run.
  - **Fix**: Wrap each `async with httpx.AsyncClient()` block in `try/except (httpx.HTTPStatusError, httpx.RequestError)`, log warning, return `None`/empty.

- **[HIGH] Missing `except` clause in `oil_prices.py`** *(carried — day 4)*
  `fetch_brent()` / `fetch_wti()` use `try/finally` with no `except`. EIA API errors propagate and crash the brief pipeline.
  - **Fix**: Add `except (httpx.HTTPStatusError, httpx.RequestError, json.JSONDecodeError)` before `finally`, log warning, return `[]`.

---

### MEDIUM

- **[MEDIUM] `PRICE_ELASTICITY = 3.0` hardcoded in `cascade.py`** *(carried)*
  Spec §4 requires all cascade parameters to be tunable via `scenario_hormuz.yaml`. `PRICE_ELASTICITY` is a module-level constant, not a YAML field.
  - **Fix**: Add `price_elasticity: 3.0` to the YAML; add field to `ScenarioConfig`; use `self._config.price_elasticity` in `compute_price_shock()`.

- **[MEDIUM] `simulation/circuit_breaker.py` not implemented** *(carried)*
  Spec §4 defines escalation limits (max 1 level/tick, 3-tick cooldown, Goldstein exogenous override). `ScenarioConfig` already carries all three parameters. Module and `test_circuit_breaker.py` are absent.

- **[MEDIUM] `ingestion/dedup.py` not implemented** *(carried)*
  Semantic dedup (`SemanticDeduplicator` via `all-MiniLM-L6-v2`) is absent; `sentence-transformers` not in `pyproject.toml`. Duplicate GDELT events can reach prediction models.

- **[MEDIUM] Architectural pivot documented but not reconciled** *(stable — intentional)*
  The live system is a 3-model prediction-market edge-finder; the Phase 1 spec describes a 50-agent LLM swarm with H3 geospatial visualization. Modules `agents/`, `eval/`, `spatial/`, and `simulation/engine.py` are absent per the pivot decision. `CLAUDE.md` accurately documents the current design. No operational risk — noted for spec traceability.

---

### LOW

- **[LOW] `starlette.testclient` deprecation warning** *(carried)*
  Test runs emit `StarletteDeprecationWarning: Using httpx with starlette.testclient is deprecated; install httpx2 instead.` No runtime breakage.

- **[LOW] `requires-python = ">=3.11"` vs spec's Python 3.12** *(carried)*
  No 3.11-incompatible syntax found; looser pin is harmless in practice.

- **[LOW] No linter or formatter enforced** *(carried)*
  No `ruff`, `black`, or `pre-commit` hook configured. Style is consistent by convention only.

- **[LOW] 6 spec-required deps absent from `pyproject.toml`** *(stable — intentional)*
  `h3`, `sentence-transformers`, `searoute`, `shapely`, `google-cloud-bigquery`, `websockets` — all from the unbuilt geospatial pipeline. No impact given pivot decision.

---

## Dependency Snapshot

| Package | Installed | In pyproject.toml | Notes |
|---|---|---|---|
| duckdb | 1.5.3 | ≥1.2 ✓ | |
| fastapi | latest | ≥0.115 ✓ | |
| anthropic | latest | ≥0.52 ✓ | |
| pydantic | latest | ≥2.10 ✓ | |
| httpx | latest | ≥0.28 ✓ | |
| cryptography | 41.0.7 (system) | ≥44.0 ✗ | Debian conflict; blocks fresh `pip install` |
| **pytz** | **NOT INSTALLED** | **MISSING** | **Blocks 17 tests + production scorecard/alerts/budget** |
| truthbrush | present | ≥0.2 ✓ | CI install may conflict |

---

## Recommendations (Priority Order)

1. **Immediate (1 line — 6 days unresolved)**: Add `"pytz>=2024.1"` to `dependencies` in `backend/pyproject.toml`. Unblocks 17 tests and production scorecard/budget/alerts paths.

2. **Immediate — NEW**: Either drop the `cryptography>=44.0` pin from `pyproject.toml` (not directly imported) or add `--ignore-installed cryptography` to the CI install step. This prevents the silent install failure that turns 17 test failures into 42 collection errors.

3. **Short-term**: Add `try/except (httpx.HTTPStatusError, httpx.RequestError)` to `polymarket.py` (5 methods) and `oil_prices.py`. Prevents brief-run crashes on transient external API failures.

4. **Short-term**: Add `price_elasticity: 3.0` to `scenario_hormuz.yaml` + `ScenarioConfig`; remove the module constant from `cascade.py`.

5. **Medium-term**: Wire `DbWriter` into async-path modules (`ops/alerts.py`, `budget/tracker.py`, `scoring/ledger.py`, `scoring/prediction_log.py`, `ingestion/crisis_ingester.py`, `contracts/registry.py`).

6. **Medium-term**: Implement `simulation/circuit_breaker.py` + `test_circuit_breaker.py`.
