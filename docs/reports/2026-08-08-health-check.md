# Parallax Health Check — 2026-08-08

**Status: YELLOW**

## Summary

21 of 473 tests are failing due to two confirmed bugs: DuckDB does not support `DATE()` as a scalar function (should be `CAST(x AS DATE)`) breaking all scorecard and backtest queries, and `numpy.trapz` was removed in NumPy 2.0 breaking the selective coverage module. The DbWriter single-writer pattern from the spec remains dead code — all production writes bypass the asyncio queue and go directly to `conn.execute()`, making concurrent-process safety an unresolved architectural gap. The project has clearly and deliberately pivoted from the Phase 1 agent-swarm spec to a lean prediction-market edge-finder; the pivot is coherent but the original spec modules (agents/, spatial/, eval/) were never built.

---

## Test Results

```
21 failed, 452 passed, 13 skipped (83s)
```

**Failing test groups:**
- `test_scorecard.py` — 11 failures (all `DATE()` CatalogException)
- `test_phase1_critical.py` — 3 failures (2 `DATE()` CatalogException, 1 logic regression)
- `test_recalibrators.py` — 5 failures (`scikit-learn` not in core deps, `numpy` version)
- `test_selective.py` — 1 failure (`numpy.trapz` removed in NumPy 2.0)
- `test_bench_forecast.py` — collection error (`pandas` not in core deps)
- `test_calibration_metrics.py` — collection error (`numpy` not in core deps)

---

## Issues Found

### [HIGH] DuckDB `DATE()` function does not exist in DuckDB 1.2

- **Files:** `backend/src/parallax/scoring/scorecard.py` (18 occurrences), `backend/src/parallax/backtest/runner.py` (1 occurrence)
- **Error:** `duckdb.CatalogException: Scalar Function with name date does not exist! Did you mean "datesub"?`
- **Impact:** All 20 scorecard ETL metrics fail at runtime. The `--scorecard` CLI flag is completely broken. Backtest date-filtering is broken.
- **Fix:** Replace `DATE(column)` with `CAST(column AS DATE)` throughout both files.

### [HIGH] `numpy.trapz` removed in NumPy 2.0

- **File:** `backend/src/parallax/scoring/selective.py:106`
- **Code:** `return float(np.trapz(risk, coverage))`
- **Impact:** `aurc()` raises `AttributeError`, breaking selective prediction coverage metrics.
- **Fix:** Replace with `np.trapezoid(risk, coverage)` (NumPy 2.0+).

### [HIGH] DbWriter asyncio queue is dead code — single-writer pattern not enforced

- **File:** `backend/src/parallax/db/writer.py` (implemented, tested in isolation, **never imported**)
- **Impact:** All production writes (`cli/brief.py`, `scoring/ledger.py`, `scoring/tracker.py`, `scoring/resolution.py`, `scoring/prediction_log.py`, `contracts/registry.py`, `ops/alerts.py`, `ingestion/crisis_ingester.py`, `backtest/runner.py`) go directly to `conn.execute()`. Concurrent process access (e.g., CLI brief running alongside API server) risks `IOException: Could not set lock on file`. The spec's architectural commitment to single-writer topology exists only on paper.

### [MEDIUM] Signal deconflict mutates in-memory objects without updating signal_ledger

- **File:** `backend/src/parallax/cli/brief.py` — `_deconflict_oil_signals()`
- **Bug:** `ledger.record_signal()` persists every signal *before* deconfliction; then `_deconflict_oil_signals()` sets `s.signal = "HOLD"` on the Python objects but issues no corresponding `UPDATE signal_ledger SET signal = 'HOLD' WHERE signal_id = ?`. The `signal_ledger` table permanently stores the pre-deconflict signals.
- **Impact:** Scorecard, resolution checker, and dashboard all read stale `BUY_YES`/`BUY_NO` records that the brief itself treated as `HOLD`. P&L attribution is corrupted.

### [MEDIUM] Missing `numpy`, `pandas`, `scikit-learn` from core/dev dependencies

- **File:** `backend/pyproject.toml`
- **Issue:** `scoring/selective.py`, `scoring/recalibrators.py`, `scoring/calibration_metrics.py` use numpy/scikit-learn as production imports but these are declared only under `[bench]` optional extras. The default `pip install -e ".[dev]"` does not install them, so 8 tests in the default suite fail to import.
- **Fix:** Move `numpy>=1.26` and `scikit-learn>=1.3` to core `dependencies`.

### [MEDIUM] `BudgetTracker` never writes to `llm_usage` in the brief pipeline

- **File:** `backend/src/parallax/cli/brief.py:532` — `BudgetTracker(daily_cap_usd=20.0)` (no `db_conn`)
- **Impact:** `llm_usage` table is always empty during normal brief runs. The `ops_llm_cost_usd` scorecard metric is always 0. The $20/day cap check works (in-memory) but costs are invisible in the database.

### [MEDIUM] `PredictionLogger.get_predictions()` silently drops staleness metadata

- **File:** `backend/src/parallax/scoring/prediction_log.py` — `_row_to_entry()`
- **Bug:** SELECT fetches columns 0–12 but the `prediction_log` table has 5 additional staleness columns (`is_fallback`, `fallback_source_run_id`, `staleness_penalty_applied`, `context_age_hours`, `penalty_factor`). All revert to Pydantic defaults on read-back.
- **Impact:** Any analysis of staleness corrections from the dashboard or backtest reads wrong data silently.

### [LOW] `ops/alerts.py` — `DuckDBAlertSink.send()` writes directly without queue

- **File:** `backend/src/parallax/ops/alerts.py:106`
- **Issue:** Direct `INSERT INTO ops_events` outside the writer queue. Acceptable if single-process, risky if multi-process.

### [LOW] `contracts/registry.py` — `upsert()` / `mark_inactive()` bypass writer queue

- **File:** `backend/src/parallax/contracts/registry.py:105, 114, 198`
- **Issue:** `DELETE`, `INSERT`, `UPDATE` on `contract_registry` and `contract_proxy_map` go direct to `conn.execute()`.

### [LOW] `ensemble.py` hardcodes `"opus"` model tag for budget accounting

- **File:** `backend/src/parallax/prediction/ensemble.py`
- **Issue:** `budget.record(resp.usage.input_tokens, resp.usage.output_tokens, "opus")` always uses `"opus"` string regardless of the actual model. Cost calculation in `BudgetTracker` is based on the wrong model tier if model changes.

### [LOW] `mapping_policy.py` — `update_discounts_from_history()` is a no-op

- **File:** `backend/src/parallax/contracts/mapping_policy.py`
- **Issue:** Method logs "Skipping discount update: not yet implemented" and returns. Called in the brief pipeline creating the appearance of a working adaptive-discount feedback loop.

### [LOW] Missing `__init__.py` in `config/` and `portfolio/` subpackages

- **Paths:** `backend/src/parallax/config/` and `backend/src/parallax/portfolio/`
- **Issue:** Every other subpackage has explicit `__init__.py`. These two rely on implicit namespace package behavior, which can produce surprising import resolution in edge cases.

### [LOW] CI-hostile `conftest.py` requires network access for DuckDB extension installs

- **File:** `backend/tests/conftest.py`
- **Issue:** `INSTALL spatial` and `INSTALL h3 FROM community` hit the DuckDB extension registry on every test session start. Any offline or firewalled CI environment will fail all `db`-fixture tests at setup.

---

## Architecture Drift from Spec

The Phase 1 spec describes an LLM agent swarm simulator (~50 agents, H3 spatial model, GDELT pipeline, WebSocket dashboard). The actual codebase is a prediction-market edge-finder: ingests news + EIA prices, runs 3 Claude prediction models, compares against Kalshi/Polymarket prices, flags divergences, paper-trades. The following spec-required modules were never built:

| Spec Module | Status |
|---|---|
| `agents/` — 50-agent country/sub-actor hierarchy | Not built |
| `spatial/` — H3 resolution bands, route-to-cell | Not built |
| `eval/` — prediction scoring, prompt versioning, improvement pipeline | Not built (replaced by `scoring/`) |
| `api/` — separate API layer with WebSocket | Not built (routes in `main.py` inline) |
| `simulation/engine.py` — DES core | Not built (only cascade.py, world_state.py, config.py) |
| `simulation/circuit_breaker.py` | Not built |

This drift is intentional and coherent — the project is building the prediction market trading product rather than the full simulation. The CLAUDE.md documentation reflects the actual system accurately.

---

## Dependency Audit

| Dependency | Declared | Concern |
|---|---|---|
| `duckdb>=1.2` | ✓ core | `DATE()` syntax incompatibility with 1.2.x — regression introduced by a code change, not a version bump |
| `numpy>=1.26` | bench only | `np.trapz` removed in NumPy 2.0; installed 2.x causes failures in production scoring module |
| `scikit-learn>=1.3` | bench only | Used in production `scoring/recalibrators.py` but not in core deps |
| `pandas>=2.0` | bench only | Used in `bench/forecast.py` (OK, bench-only), but test collection pulls it as a hard requirement |
| `pytest>=8.3,<9` | dev | Installed pytest 9.0.2 exceeds upper bound — the constraint is stale |
| `truthbrush>=0.2` | core | Niche Truth Social scraping library; not widely maintained, no upper bound |
| `anthropic>=0.52` | core | No upper bound; Anthropic breaking changes could silently break inference |

---

## Recommendations

1. **[Immediate]** Fix `DATE()` → `CAST(column AS DATE)` in `scorecard.py` and `backtest/runner.py` — unblocks 20 failing tests.
2. **[Immediate]** Fix `np.trapz` → `np.trapezoid` in `selective.py` — unblocks 1 failing test.
3. **[Immediate]** Move `numpy` and `scikit-learn` to core `dependencies` in `pyproject.toml` — unblocks 8 test collection errors.
4. **[High]** Fix `_deconflict_oil_signals()` to `UPDATE signal_ledger SET signal = 'HOLD'` after deconfliction — prevents P&L attribution corruption.
5. **[High]** Wire `DbWriter` into all write paths or explicitly document that the single-writer pattern is only required when multiple processes share the DB file.
6. **[Medium]** Pass `db_conn` to `BudgetTracker` in the brief pipeline so `llm_usage` is populated.
7. **[Medium]** Fix `PredictionLogger._row_to_entry()` to deserialize the 5 staleness columns.
8. **[Low]** Pre-install DuckDB extensions in CI; remove network-required `INSTALL` from `conftest.py`.
9. **[Low]** Add `__init__.py` to `config/` and `portfolio/` subpackages.
10. **[Low]** Update `pytest<9` constraint or remove the upper bound.
