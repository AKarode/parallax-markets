# Parallax Health Check — 2026-08-04

**Status: YELLOW**

## Summary

The project has undergone a significant architectural pivot from the Phase 1 spec (50-agent geopolitical swarm with H3 hex-map visualization) to a focused prediction market edge-finder (3 LLM prediction models vs. Kalshi/Polymarket prices → divergence signals → paper trading). The pivot is intentional and documented in CLAUDE.md, but creates cascading drift: missing dependencies listed in CLAUDE.md aren't in pyproject.toml, the frontend stack described in CLAUDE.md doesn't match package.json, and ~10 modules bypass the spec's "critical" DuckDB single-writer pattern.  The core simulation primitives (cascade engine, world state, circuit breaker) were implemented correctly; the prediction/scoring/divergence pipeline is well-covered by 47 tests.

---

## Issues Found

### [CRITICAL] DuckDB single-writer violations — 10+ modules

The spec designates the `asyncio.Queue` → `DbWriter` pattern as a **hard constraint** to prevent `database is locked` errors under concurrent writes. `DbWriter` is correctly implemented in `db/writer.py`, but is bypassed by:

- `scoring/ledger.py` — direct `INSERT INTO signal_ledger` (lines 225–234) and `UPDATE` calls
- `scoring/tracker.py` — 5 direct `INSERT/UPDATE` operations for trade orders, fills, positions
- `scoring/prediction_log.py` — direct `INSERT INTO prediction_log` (line 79)
- `scoring/resolution.py` — direct `UPDATE` on `signal_ledger` and `prediction_log` (lines 105, 124, 163)
- `ingestion/crisis_ingester.py` — direct `INSERT INTO crisis_events` (lines 54, 79, 133)
- `contracts/registry.py` — direct `INSERT/UPDATE` on `contract_registry` and `contract_proxy_map` (lines 85–236)
- `ops/alerts.py` — direct `INSERT INTO ops_events` (line 106)
- `cli/brief.py` — direct writes to multiple tables (lines 130, 149, 431, 504, 517)
- `budget/tracker.py` — direct `INSERT INTO llm_usage` (line 43)
- `main.py` — direct writes during startup (lines 144, 214, 225)

These are safe today because all writes occur from a single FastAPI process running async handlers, but any future parallelism (background tasks, concurrent requests) or SQLite-style WAL contention can cause silent data corruption or lock errors. The pattern also makes it impossible to add write backpressure monitoring.

### [HIGH] CLAUDE.md tech stack lists dependencies not in pyproject.toml

The CLAUDE.md technology section documents these as part of the stack, but none appear in `backend/pyproject.toml`:

| Listed in CLAUDE.md | pyproject.toml status |
|---|---|
| `h3>=4.1` | **missing** |
| `sentence-transformers>=3.4` | **missing** |
| `searoute>=1.3` | **missing** |
| `shapely>=2.0` | **missing** |
| `google-cloud-bigquery>=3.27` | **missing** |
| `websockets>=14.0` | **missing** |

These were carried over from the original spec. Since the project pivoted, CLAUDE.md documentation should be updated to reflect the actual dependencies, or the modules that need them should declare them.

### [HIGH] Frontend stack in CLAUDE.md does not match package.json

CLAUDE.md lists `deck.gl 9.1.0`, `MapLibre GL 4.7.0`, `react-map-gl 7.1.8`, and `h3-js` as frontend dependencies. None of these are in `frontend/package.json`. The actual frontend uses only `react`, `react-dom`, and `recharts`. This is either stale documentation or planned future work that is not yet underway.

### [HIGH] Architecture drift: agent swarm and spatial model never implemented

The Phase 1 plan's central deliverable — a 50-agent country→sub-actor swarm with H3 hex visualization — was not built. Missing modules vs. the plan:

- `agents/` (registry, runner, router, country_agent, schemas, prompts/) — **absent**
- `spatial/` (h3_utils.py, loader.py) — **absent**
- `eval/` (scoring, ground_truth, prompt_versioning, improvement) — **absent**
- `api/` (routes.py, websocket.py, auth.py) — **replaced by monolithic main.py**
- `ingestion/dedup.py` — **absent** (semantic dedup with sentence-transformers)

The project replaced this with a 3-model prediction pipeline (`prediction/oil_price.py`, `prediction/ceasefire.py`, `prediction/hormuz.py`) calling Claude Sonnet directly — a valid simplification for the 2-week deadline, but the spec gap should be acknowledged.

### [MEDIUM] Python version mismatch

CLAUDE.md states "Python 3.12" as the runtime. `pyproject.toml` declares `requires-python = ">=3.11"`. This is a loose lower bound, not a pinned version — any CI or deployment targeting 3.11 may surface subtle behavior differences from 3.12. Should be tightened to `>=3.12`.

### [MEDIUM] Test coverage gaps for plan-specified tests

The plan specified 18 test files; the repo has 47, which is positive. However, several plan-specified tests were replaced rather than augmented:

| Plan test | Status |
|---|---|
| `test_h3_utils.py` | **missing** (no spatial module) |
| `test_gdelt_filter.py` | **missing** (gdelt_doc.py is a different shape) |
| `test_dedup.py` | **missing** (SemanticDeduplicator never built) |
| `test_agent_schemas.py` | **missing** |
| `test_agent_router.py` | **missing** |
| `test_agent_runner.py` | **missing** |
| `test_scoring.py` | **present** (as test_calibration.py + test_calibration_metrics.py) |
| `test_budget_tracker.py` | **present** |
| `test_writer.py` | **present** |

No tests exist for `ingestion/crisis_ingester.py`, `backtest/look_ahead_guard.py` (critical for data integrity), or `portfolio/simulator.py`'s DuckDB writes.

### [LOW] DB schema has grown beyond spec without a migration strategy

The spec defined 10 tables; the implementation has 26 tables + 2 views. Growth is expected, but `db/schema.py` uses `CREATE TABLE IF NOT EXISTS` plus ad-hoc `ALTER TABLE` migration blocks in `_migrate_legacy_tables()`. There is no versioned migration system (e.g., Alembic or a version table). Schema drift between environments will be hard to detect and diagnose.

### [LOW] `engine.py` from plan is absent from simulation/

`simulation/engine.py` (the DES engine with `SimulationEngine`, `SimEvent`, `heapq` priority queue) was specified in Task 8 of the plan. The file does not exist in the current repo. `cascade.py`, `world_state.py`, and `config.py` are present and match plan implementations. The engine is only needed if live simulation mode is ever activated.

---

## Recommendations

1. **Fix DuckDB write bypass (CRITICAL):** Audit `scoring/ledger.py`, `scoring/tracker.py`, `cli/brief.py`, and `ingestion/crisis_ingester.py` to route all `INSERT`/`UPDATE` calls through `DbWriter.enqueue`. The payoff is immediate: concurrent request safety, write backpressure monitoring, and cleaner error attribution.

2. **Reconcile CLAUDE.md tech stack with pyproject.toml:** Either remove the spec-era dependencies from CLAUDE.md (h3, sentence-transformers, searoute, shapely, bigquery, websockets) or add them back if H3 spatial features or semantic dedup are still planned.

3. **Update frontend docs:** CLAUDE.md's frontend section should reflect Recharts-only stack, not deck.gl/MapLibre. If the hex map is a future milestone, move it to an explicit "Phase 2" section.

4. **Tighten Python version pin:** Change `requires-python = ">=3.11"` to `">=3.12"` to match the stated runtime and avoid 3.11 compatibility surprises.

5. **Add schema versioning:** Add a `schema_version` table (a single row with a monotonic integer) and track `_migrate_legacy_tables()` applications against it. Prevents silent schema drift between dev/prod.

6. **Add tests for backtest look-ahead guard and crisis ingester:** `backtest/look_ahead_guard.py` is the integrity fence for the backtest pipeline — it should have dedicated unit tests. `ingestion/crisis_ingester.py` performs direct DB writes with no test coverage.
