# Parallax Health Check — 2026-07-28

**Status: YELLOW**

The core test suite passes (433 tests, 13 skipped). No regressions since 2026-07-27. The single new commit since yesterday is a tech research document. All persistent architectural issues identified yesterday remain open; none have worsened.

---

## Summary

The implementation is a functional prediction market edge-finder. Tests are green. The main risk factors are unchanged from prior reports: `DbWriter` is implemented but not wired into any write path, schema migration backfills run on every startup without versioning, and several test files require optional `numpy`/`pandas` dependencies that fail to import under the default `dev` install.

---

## Issues Found

### [HIGH] `DbWriter` single-writer pattern still not wired up *(persistent)*

`backend/src/parallax/db/writer.py` implements the `asyncio.Queue`-based single-writer pattern specified in the architecture docs. It is not imported or called by any other module. All mutable writes go through direct `conn.execute()` across at least 10 modules:

- `backtest/runner.py` — INSERT into `backtest_runs`, `backtest_predictions`; UPDATE on both tables
- `cli/brief.py` — INSERT into `runs`, `market_prices`; UPDATE `runs`
- `budget/tracker.py` — INSERT into `llm_usage`
- `ops/alerts.py` — INSERT into `ops_events`
- `scoring/ledger.py`, `scoring/prediction_log.py`, `scoring/scorecard.py`, `scoring/tracker.py`, `scoring/resolution.py`, `contracts/registry.py` — various INSERTs/UPDATEs

In the current single-process asyncio model, cooperative scheduling prevents concurrent write interleaving in practice, but the documented invariant is violated and there is no backpressure mechanism.

**Recommendation:** Either wire `DbWriter` into `app.state` and thread it through all write-path modules, or document that the asyncio cooperative model is the actual concurrency guarantee and remove `DbWriter` to eliminate dead-code confusion.

### [HIGH] Spec/Plan docs describe a superseded product *(persistent)*

`docs/superpowers/specs/2026-03-30-parallax-phase1-design.md` and `docs/superpowers/plans/2026-03-30-parallax-phase1.md` describe an H3 hexagonal cascade simulator with 50 LLM agents, GDELT BigQuery, WebSocket frontend, and a DES engine. None of these exist. The following planned modules are absent:

| Planned Module | Status |
|---|---|
| `simulation/engine.py` (DES core) | Not built |
| `simulation/circuit_breaker.py` | Not built |
| `agents/` (registry, router, runner, country_agent) | Not built |
| `eval/` (scoring, ground truth, prompt versioning) | Not built |
| `spatial/` (H3 utils, Overture loader) | Not built |
| `ingestion/dedup.py` (semantic dedup) | Not built |
| `api/` (routes, websocket, auth) | Merged into `main.py` |

Six dependencies in the spec (`h3`, `websockets`, `sentence-transformers`, `searoute`, `shapely`, `google-cloud-bigquery`) are absent from `pyproject.toml`.

**CLAUDE.md already documents the actual product accurately.** The spec/plan docs are now historical artifacts.

### [MEDIUM] Schema migrations run unconditionally on every startup *(persistent)*

`db/schema.py` `_migrate_legacy_tables()` runs `UPDATE` backfill statements on every startup (e.g., `UPDATE signal_ledger SET market_derived_yes_price = ...`). There is no migration tracking table. On large `signal_ledger` tables this adds latency and unnecessary write load.

**Recommendation:** Add a `schema_migrations` table; gate each backfill behind a named migration record.

### [MEDIUM] `test_bench_forecast.py`, `test_calibration_metrics.py`, `test_recalibrators.py`, `test_selective.py` fail to import under default `dev` install

These four test files import `numpy` or `pandas`, which live in the optional `bench` extra. Running `pytest tests/` without `pip install -e ".[bench]"` produces `ModuleNotFoundError` collection errors. CI or a fresh clone will hit these without the bench extras.

**Recommendation:** Either move the numpy/pandas imports inside the tests (deferred import pattern), add `numpy` to the base `dev` extras, or add a pytest marker that skips these tests unless the `bench` extras are installed.

### [LOW] Python version inconsistency *(persistent)*

`pyproject.toml` declares `requires-python = ">=3.11"`. CLAUDE.md states Python 3.12 runtime. The codebase runs on 3.11 in this environment without issues, but the declared minimum should match the intended runtime.

### [LOW] `parallax/config/` missing `__init__.py` *(persistent)*

`backend/src/parallax/config/risk.py` exists but `config/` has no `__init__.py`, making it non-importable as a package.

---

## Test Coverage Summary

| Area | Tests | Status |
|------|-------|--------|
| Core prediction models (oil, ceasefire, Hormuz) | `test_prediction.py`, `test_brief.py` | Passing |
| Market integrations (Kalshi, Polymarket) | `test_kalshi.py`, `test_polymarket.py` | Passing |
| Divergence detection | `test_divergence.py` | Passing |
| Signal ledger + paper trading | `test_ledger.py`, `test_calibration.py` | Passing |
| Scoring / scorecard / resolution | `test_scorecard.py`, `test_resolution.py` | Passing |
| Portfolio simulation + allocator | `test_simulator.py` | Passing |
| Backtest engine | `test_backtest_look_ahead.py` | Passing |
| Contract registry + mapping policy | `test_registry.py`, `test_mapping_policy.py` | Passing |
| Dashboard queries + endpoints | `test_dashboard_*.py` | Passing |
| Bench (requires numpy/pandas) | `test_bench_forecast.py`, `test_calibration_metrics.py` | **Import error** |
| H3 spatial / agents / eval | — | **Not built** |

**Total:** 433 passed, 13 skipped, 1 deprecation warning (`httpx` → `httpx2` in `starlette.testclient`)

---

## Recommendations (Priority Order)

1. **Fix numpy import errors in test suite** — add `numpy` to `dev` extras or gate with a marker. Unblocks clean `pytest tests/` runs.
2. **Audit `DbWriter` usage** — wire it up or remove it. The dead-code state is the highest ambiguity risk.
3. **Add migration versioning** — one `schema_migrations` table, gate UPDATE backfills behind it.
4. **Add `__init__.py` to `parallax/config/`** — one-line fix.
5. **Archive spec/plan docs** — add a superseded header so contributors don't build against them.
