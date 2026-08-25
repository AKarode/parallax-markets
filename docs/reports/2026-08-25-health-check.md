# Parallax Health Check — 2026-08-25

**Status: YELLOW**

## Summary

The project has pivoted substantially from the original Phase 1 plan (geospatial agent-swarm simulator with H3 hex visualization) to a focused prediction-market edge-finder with paper trading. The CLAUDE.md accurately reflects the current implementation; the divergence is between the code and the original spec documents. The implemented modules are well-built with ~490 tests across 46 files, but there are confirmed bugs in the core run loop and the DuckDB single-writer pattern exists only on paper — every write in the system bypasses the queue via direct `conn.execute()`.

---

## Architecture Drift

| Plan Expected | Actual |
|---|---|
| `agents/` — 50-agent country/sub-actor swarm | **Absent** — entire module missing |
| `spatial/` — H3 hex grid, searoute, Overture Maps | **Absent** — entire module missing |
| `eval/` — prediction eval, prompt versioning, improvement pipeline | **Absent** — entire module missing |
| `api/` — routes.py, websocket.py, auth.py | **Replaced** by monolithic `main.py` |
| `simulation/engine.py` — DES tick loop | **Missing** |
| `simulation/circuit_breaker.py` | **Missing** |
| `db/queries.py` | **Missing** |
| `ingestion/gdelt.py` | **Renamed** to `gdelt_doc.py` (different implementation) |
| `ingestion/dedup.py` — semantic dedup with sentence-transformers | **Missing** |
| Frontend: deck.gl + MapLibre + H3HexagonLayer | **Replaced** by recharts trading dashboard |
| Frontend: WebSocket live updates | **Replaced** by REST polling (`usePolling.ts`) |

**Substantial new modules not in the plan** (the implemented pivot):
`cli/brief.py`, `markets/`, `prediction/`, `divergence/`, `scoring/`, `contracts/`, `portfolio/`, `backtest/`, `ops/`, `dashboard/`

These represent a complete product re-scope — the CLAUDE.md has been updated to match the actual system, but the spec and plan docs are now describing a different product.

---

## Issues Found

### [HIGH] DuckDB single-writer pattern not enforced

- **`DbWriter` queue exists but is never used** — `db/writer.py` implements the asyncio.Queue pattern correctly, but no production code calls `enqueue()`. All writes go directly via `conn.execute()`.
- **Direct writers (all bypassing the queue):** `cli/brief.py`, `scoring/ledger.py`, `scoring/prediction_log.py`, `scoring/tracker.py`, `scoring/scorecard.py`, `scoring/resolution.py`, `ops/alerts.py`, `budget/tracker.py`, `contracts/registry.py`, `ingestion/crisis_ingester.py`, `backtest/runner.py`
- **Risk:** Low today (single-process CLI), high if the FastAPI server runs background tasks concurrently — `database is locked` errors will appear under concurrent writes, and are hard to reproduce until they happen in production.

### [HIGH] Connection leak in `run_brief()` — no try/finally

- `cli/brief.py`: `conn = duckdb.connect(runtime.db_path)` is opened at the start of `run_brief()` and only closed at the very end. There is no `try/finally` block. Any exception in the 200+ lines between open and close leaves the DuckDB file handle open for the process lifetime.
- Subsequent runs will see `database is locked` until the process exits.

### [MEDIUM] Missing `engine.py` — simulation tick loop not implemented

- `simulation/engine.py` and `simulation/circuit_breaker.py` are called out in the plan as core orchestration components; neither exists. The cascade rules, world state, and config loader are implemented and tested, but the DES engine that would orchestrate them is absent. The system cannot run a live simulation loop.

### [MEDIUM] No indexes on any DuckDB tables

- `db/schema.py` creates 20+ tables (including high-frequency append tables like `signal_ledger`, `prediction_log`, `market_prices`) with zero indexes.
- Query patterns in `dashboard/data.py` and `scoring/calibration.py` filter on `run_id`, `model_id`, `created_at`, `contract_ticker` — all unindexed. Performance will degrade as ledger grows.

### [MEDIUM] `_migrate_legacy_tables()` runs on every startup

- `db/schema.py`: The migration function executes bulk `UPDATE` statements on `signal_ledger` on every `create_tables()` call (i.e., on every `run_brief()` invocation). The updates are idempotent (uses `COALESCE`) but add unnecessary I/O overhead on every run. Should be guarded by a schema-version check.

### [LOW] `_persist_market_prices` writes in a per-row loop without a transaction

- `cli/brief.py`: Market prices are inserted one-by-one in a `for` loop. Each insert is its own implicit transaction. Should be a single `executemany` or wrapped in `BEGIN`/`COMMIT` for correctness and performance.

### [LOW] `_load_portfolio_state` uses `CURRENT_DATE` without timezone

- `cli/brief.py`: `WHERE closed_at >= CURRENT_DATE` compares a timestamp column against the host's local date. Will silently include/exclude records near midnight depending on where the process runs.

### [LOW] `db/queries.py` missing

- The plan specifies a `queries.py` for read-only helpers. It was never created. Query logic is scattered across `dashboard/data.py`, `scoring/calibration.py`, and `cli/brief.py` with no central query layer.

### [INFO] Plan-expected tests that are absent

The following test files from the plan were never created (10 of 18):
`test_h3_utils.py`, `test_gdelt_filter.py`, `test_dedup.py`, `test_circuit_breaker.py`, `test_agent_schemas.py`, `test_agent_router.py`, `test_agent_runner.py`, `test_prompt_versioning.py`, `test_auth.py`, `test_budget_tracker.py`, `test_integration.py`

These cover modules that don't exist in the pivot, so their absence is expected given the scope change. The implemented modules have strong coverage (~490 tests across 46 files).

---

## Recommendations

1. **Fix the connection leak** (HIGH, 30 min): Wrap `run_brief()` body in `try/finally: conn.close()`. This is the highest-impact quick fix.

2. **Add indexes for hot query columns** (MEDIUM, 1 hr): Add indexes on `signal_ledger(run_id, created_at)`, `prediction_log(run_id, model_id)`, `market_prices(contract_ticker, fetched_at)`. DuckDB supports standard `CREATE INDEX`.

3. **Guard migrations with a version check** (MEDIUM, 1 hr): Add a `schema_version` key to `simulation_state` table. Only run `_migrate_legacy_tables()` if the stored version is below the current version, then bump it.

4. **Audit spec/plan docs vs CLAUDE.md** (INFO, 30 min): The spec and plan in `docs/superpowers/` now describe a different product. Either archive them or add a header noting the pivot date and pointing to CLAUDE.md as the authoritative description of what was actually built.

5. **Wire DbWriter or remove it** (MEDIUM, 2-4 hrs): Either connect the DbWriter queue throughout the codebase (correct approach for a long-running server) or remove it and document that the system is CLI-only and single-write-path-safe. Leaving it as dead code creates confusion.
