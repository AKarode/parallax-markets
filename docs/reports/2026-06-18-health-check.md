# Parallax Health Check — 2026-06-18

**Status: YELLOW**

## Summary

Two persistent regressions and one **new breakage introduced today**. DuckDB silently upgraded from 1.5.3 → 1.5.4 between yesterday and today; the H3 community extension has no v1.5.4 build for `linux_amd64`, converting 6 previously-passing `test_schema.py` / `test_writer.py` tests into ERRORs. The `pytz` missing-dependency issue enters **day 7** with the same 17 failures and no remediation. No code changes landed on `main` since the 2026-06-17 report (HEAD remains `ed7fed9`).

---

## Test Run Summary

```
410 passed  |  17 failed  |  13 skipped  |  6 errors
```

*Yesterday: 416 passed, 17 failed, 13 skipped, 0 errors. The delta is 6 new ERRORs and 6 fewer passes.*

### 6 New ERRORs — DuckDB H3 Extension Missing for v1.5.4

**Root cause:**
```
_duckdb.HTTPException: HTTP Error: Failed to download extension "h3" at URL
"http://community-extensions.duckdb.org/v1.5.4/linux_amd64/h3.duckdb_extension.gz" (HTTP 404)
```

DuckDB 1.5.4 was pulled in by a transitive upgrade. The H3 community extension does not yet have a binary for `linux_amd64` at this version. `conftest.py` unconditionally executes `INSTALL h3 FROM community; LOAD h3;` at fixture setup, causing all tests that use the `db` fixture to error before running.

| Erroring test file | # errors |
|---|---|
| `test_schema.py` | 3 |
| `test_writer.py` | 3 |

### 17 Persistent Failures — `pytz` Missing (Day 7)

**Root cause:**
```
_duckdb.InvalidInputException: Required module 'pytz' failed to import
ModuleNotFoundError: No module named 'pytz'
```

`pytz` is absent from `backend/pyproject.toml`. DuckDB 1.5.x requires it for any `DATE()` / `TIMESTAMPTZ` operation.

| Failing test file | # failures |
|---|---|
| `test_scorecard.py` | 10 |
| `test_crisis_context_db.py` | 4 |
| `test_llm_usage.py` | 1 |
| `test_ops_events.py` | 1 |
| `test_phase1_critical.py` | 1 (context-age path) |

---

## Issues Found

### CRITICAL

- **[CRITICAL — NEW] DuckDB 1.5.4 breaks H3 community extension**
  `conftest.py` tries to `INSTALL h3 FROM community` at test setup. The H3 extension has no binary for DuckDB 1.5.4 `linux_amd64` (404). Breaks all 6 tests using the `db` fixture (`test_schema.py`, `test_writer.py`). These are foundational schema and writer tests — if they can't run, DB regressions go undetected.
  - **Fix A (immediate)**: Pin `"duckdb>=1.2,<1.5.4"` in `pyproject.toml` to hold at 1.5.3 until H3 publishes a 1.5.4 build.
  - **Fix B (proper)**: Update `conftest.py` to skip `INSTALL h3` if the extension fails to load (`try/except`), or lazy-load H3 only in the tests that actually need it. Most schema/writer tests do not use H3 at all.

- **[CRITICAL] `pytz` missing from `pyproject.toml`** *(day 7 — first flagged 2026-06-12)*
  Breaks `--scorecard` CLI path, budget tracker writes, ops alert sink, and crisis context DB path in production — not just in tests.
  - **Fix (one line)**: Add `"pytz>=2024.1"` to `dependencies` in `backend/pyproject.toml`.

---

### HIGH

- **[HIGH] `pip install -e ".[dev]"` fails on non-Docker environments** *(carried — day 2)*
  System `cryptography 41.0.7` (Debian) conflicts with `cryptography>=44.0` pin. Fresh installs fail before registering the `parallax` package, causing 43 test files to surface as "42 collection errors." CI environments without Docker hit this silently.
  - **Fix A**: Drop `"cryptography>=44.0"` from `pyproject.toml` — it is pulled in transitively by `httpx`; no direct import found.
  - **Fix B**: Add `--ignore-installed cryptography` to CI install step and `Dockerfile`.

- **[HIGH] Single-writer pattern violated in async-path modules** *(carried — day 7+)*
  Raw `conn.execute()` INSERT/UPDATE calls outside `db/writer.py` confirmed in 10+ modules (135 total `.execute()` calls; only `backtest/look_ahead_guard.py:109` found to do DDL writes outside schema.py — a `DROP VIEW` — but INSERT/UPDATE violations are extensive in `scoring/`, `ops/`, `budget/`, `cli/`, `ingestion/`). `DbWriter` is correctly implemented but wired to zero callers. Risk: concurrent FastAPI requests and background brief tasks race on the shared DuckDB connection.
  - Affected modules: `scoring/ledger.py`, `scoring/tracker.py`, `scoring/prediction_log.py`, `scoring/scorecard.py`, `ops/alerts.py`, `budget/tracker.py`, `ingestion/crisis_ingester.py`, `contracts/registry.py`, `cli/brief.py`, `main.py`.

- **[HIGH] Missing `try/except` on Polymarket and EIA HTTP calls** *(carried — day 5)*
  Five methods in `markets/polymarket.py` call `resp.raise_for_status()` with no surrounding exception handler. `ingestion/oil_prices.py` uses `try/finally` with no `except`. Any 429, 5xx, or network timeout aborts the entire brief run.

---

### MEDIUM

- **[MEDIUM] `PRICE_ELASTICITY = 3.0` hardcoded in `cascade.py`** *(carried)*
  Spec §4 requires all cascade parameters to be tunable via `scenario_hormuz.yaml`. `PRICE_ELASTICITY` is a module-level constant, not a YAML field.
  - **Fix**: Add `price_elasticity: 3.0` to the YAML; add field to `ScenarioConfig`; use `self._config.price_elasticity` in `compute_price_shock()`.

- **[MEDIUM] `simulation/circuit_breaker.py` not implemented** *(carried)*
  Spec §4 defines escalation limits (max 1 level/tick, 3-tick cooldown, Goldstein exogenous override). `ScenarioConfig` carries all three parameters. Module and `test_circuit_breaker.py` are absent.

- **[MEDIUM] `ingestion/dedup.py` not implemented** *(carried)*
  Semantic dedup (`SemanticDeduplicator` via `all-MiniLM-L6-v2`) is absent; `sentence-transformers` not in `pyproject.toml`. Duplicate GDELT events can reach prediction models.

- **[MEDIUM] Architectural pivot documented but not reconciled** *(stable — intentional)*
  The live system is a 3-model prediction-market edge-finder; the Phase 1 spec describes a 50-agent LLM swarm with H3 geospatial visualization. Modules `agents/`, `eval/`, `spatial/`, and `simulation/engine.py` are absent per the pivot decision. `CLAUDE.md` accurately documents the current design. No operational risk — noted for spec traceability.

---

### LOW

- **[LOW] `starlette.testclient` deprecation warning** *(carried)*
  Test runs emit `StarletteDeprecationWarning`. No runtime breakage.

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
| duckdb | **1.5.4** | ≥1.2 ✓ | **NEW: Breaks H3 community ext — no 1.5.4 linux_amd64 build** |
| fastapi | latest | ≥0.115 ✓ | |
| anthropic | latest | ≥0.52 ✓ | |
| pydantic | latest | ≥2.10 ✓ | |
| httpx | latest | ≥0.28 ✓ | |
| cryptography | 41.0.7 (system) | ≥44.0 ✗ | Debian conflict; blocks fresh `pip install` |
| **pytz** | **NOT INSTALLED** | **MISSING** | **Day 7 — blocks 17 tests + production scorecard/alerts/budget** |
| truthbrush | present | ≥0.2 ✓ | |

---

## Spec/Plan Consistency

| Area | Status | Notes |
|---|---|---|
| DB schema (20+ tables) | ✓ Compliant | All plan-spec tables present |
| Single-writer topology | ✗ Violated | `DbWriter` exists but 10+ modules bypass it |
| Cascade engine | ⚠ Partial | 6 rules present; `PRICE_ELASTICITY` not YAML-tunable; `circuit_breaker.py` absent |
| GDELT ingestion | ⚠ Partial | Volume gate + entity override present; semantic dedup absent |
| Agent swarm (50 agents) | ✗ Deferred | Intentional pivot — 3 monolithic LLM models instead |
| Eval framework | ✗ Deferred | `calibration.py` covers scoring; no formal eval harness |
| Frontend dashboard | ✓ Compliant | React SPA with 9 components, `usePolling` hook |
| Paper trading (Kalshi) | ✓ Compliant | Full order lifecycle, RSA-PSS auth, sandbox separation |
| Budget cap ($20/day) | ✓ Compliant | `BudgetTracker` wired; writes bypass DbWriter queue |
| `conftest.py` H3 fixture | ✗ Broken | Unconditional `INSTALL h3` fails on DuckDB 1.5.4 |

---

## Recommendations (Priority Order)

1. **Immediate — NEW**: Pin `"duckdb>=1.2,<1.5.4"` in `pyproject.toml` OR update `conftest.py` to guard the H3 install with a `try/except` (preferred — most schema/writer tests don't need H3 at all). Restores 6 tests to passing.

2. **Immediate (1 line — day 7 unresolved)**: Add `"pytz>=2024.1"` to `dependencies` in `backend/pyproject.toml`. Unblocks 17 tests and the production scorecard/budget/alerts paths.

3. **Short-term**: Either drop `"cryptography>=44.0"` from `pyproject.toml` or add `--ignore-installed cryptography` to CI/Dockerfile. Prevents silent install failures on fresh environments.

4. **Short-term**: Add `try/except (httpx.HTTPStatusError, httpx.RequestError)` to `polymarket.py` (5 methods) and `oil_prices.py`. Prevents brief-run crashes on transient API failures.

5. **Short-term**: Add `price_elasticity: 3.0` to `scenario_hormuz.yaml` + `ScenarioConfig`; remove the module constant from `cascade.py`.

6. **Medium-term**: Wire `DbWriter` into async-path modules (`ops/alerts.py`, `budget/tracker.py`, `scoring/ledger.py`, `scoring/prediction_log.py`, `ingestion/crisis_ingester.py`, `contracts/registry.py`).

7. **Medium-term**: Implement `simulation/circuit_breaker.py` + `test_circuit_breaker.py`.
