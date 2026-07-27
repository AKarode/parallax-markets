# Parallax Health Check — 2026-07-27

**Status: YELLOW**

The implementation is functional and well-tested for what it actually does (prediction market edge-finder with 3 LLM predictors, Kalshi/Polymarket integration, paper trading, and a scoring framework). However, the founding spec and implementation plan describe a completely different product, the `DbWriter` single-writer pattern exists but is not wired up anywhere, and the schema uses an unversioned migration approach.

---

## Issues Found

### [HIGH] Spec/Plan docs describe a different product

The design spec (`docs/superpowers/specs/2026-03-30-parallax-phase1-design.md`) and implementation plan describe a **geopolitical cascade simulator** with ~50 LLM agents (country + sub-actor hierarchy), an H3 hexagonal map via deck.gl, GDELT BigQuery ingestion with 4-stage noise filter, WebSocket-driven frontend, and a full DES engine. The actual product is a **prediction market edge-finder** with 3 focused LLM predictors (oil price, ceasefire, Hormuz reopening), Kalshi/Polymarket market comparison, paper trading, and a polling-based React dashboard.

The following modules described in the plan **do not exist**: `agents/` (runner, router, country_agent, registry), `eval/`, `api/`, `simulation/engine.py`, `simulation/circuit_breaker.py`, `spatial/` (H3 utilities + Overture loader), `ingestion/dedup.py`. Dependencies listed in the plan but not in `pyproject.toml`: `h3`, `searoute`, `shapely`, `google-cloud-bigquery`, `sentence-transformers`, `websockets`.

**Impact:** Misleading for anyone using the spec docs as a reference. CLAUDE.md already describes the actual product correctly; the spec/plan are now historical artifacts.

### [HIGH] `DbWriter` exists but is never used — single-writer guarantee not enforced

`backend/src/parallax/db/writer.py` implements the `DbWriter` asyncio queue pattern specified in the architecture doc, but it is **never imported or called anywhere else** in the codebase. All database writes go through direct `conn.execute()` calls across at least 10 modules: `scoring/ledger.py`, `scoring/prediction_log.py`, `scoring/resolution.py`, `scoring/scorecard.py`, `scoring/tracker.py`, `cli/brief.py`, `budget/tracker.py`, `ops/alerts.py`, `contracts/registry.py`, `backtest/runner.py`, etc.

In the current single-process asyncio model this is safe in practice (cooperative scheduling serializes writes), but:
- There is no backpressure mechanism or queue depth monitoring
- Any `await` between write operations (e.g., in concurrent API handlers sharing `app.state.db`) could interleave writes if DuckDB's connection is not re-entrant under concurrent asyncio coroutines
- The documented invariant ("all writes go through `asyncio.Queue`") is false, making the architecture harder to reason about

**Impact:** Risk of `database is locked` errors if concurrent request handlers share the DuckDB connection and both reach write code without yielding. Should be audited.

### [MEDIUM] Schema migrations are unversioned — run on every startup

`db/schema.py`'s `_migrate_legacy_tables()` function runs `ALTER TABLE ADD COLUMN IF NOT EXISTS` and `UPDATE` backfill statements on every application startup. While `IF NOT EXISTS` guards prevent duplicate columns, the `UPDATE` backfill statements run unconditionally on every restart (e.g., `UPDATE signal_ledger SET market_derived_yes_price = ...`). There is no migration tracking table, no notion of "already applied", and no way to audit which migrations have run.

**Impact:** Unnecessary write load on every startup; silent partial-migration failures are hard to diagnose; adds startup latency on large tables.

### [MEDIUM] Python version inconsistency

`pyproject.toml` declares `requires-python = ">=3.11"`, but `CLAUDE.md` states the runtime is Python 3.12 and the tech stack section says "Python 3.12+". The `|` union type syntax used throughout (e.g., `str | None`) requires Python 3.10+, so 3.11 works, but the discrepancy creates ambiguity about the intended minimum version.

### [LOW] `scoring/tracker.py` is 34 KB — largest file in the codebase

The paper trade execution and order lifecycle logic is concentrated in a single 34KB module. It is also the most heavily tested file (via `test_calibration.py`, `test_ledger.py`, etc.) but its size makes it hard to audit, maintain, and extend without introducing bugs.

**Impact:** Maintenance risk. No immediate bug, but a prime candidate for decomposition.

### [LOW] `parallax/config/` has no `__init__.py`

`backend/src/parallax/config/risk.py` exists but the `config/` directory has no `__init__.py`. This prevents importing from `parallax.config` as a package. Currently only `from parallax.config.risk import ...` is likely used (which works via the file directly), but it's inconsistent with the rest of the package structure.

### [LOW] Ingestion module naming deviates from spec and from CLAUDE.md

The spec calls for `ingestion/gdelt.py` with BigQuery integration. The actual file is `ingestion/gdelt_doc.py` using the GDELT DOC 2.0 REST API (no BigQuery). CLAUDE.md's module map lists `ingestion/gdelt_doc.py` — so CLAUDE.md is accurate — but the spec/plan naming divergence adds confusion. `ingestion/dedup.py` (semantic dedup via sentence-transformers) is absent entirely; there is no semantic deduplication layer currently.

### [LOW] Test files expected by the plan are missing (all intentional given the pivot)

The plan expects: `test_h3_utils.py`, `test_dedup.py`, `test_circuit_breaker.py`, `test_engine.py`, `test_agent_schemas.py`, `test_agent_router.py`, `test_agent_runner.py`, `test_prompt_versioning.py`, `test_auth.py`. None exist because the corresponding features were not built. The 47 tests that do exist cover the actual implementation thoroughly.

---

## Recommendations

1. **Archive the spec/plan docs** — add a header noting they describe a superseded architecture. Update or replace with a spec matching the current product to avoid confusion for future contributors.

2. **Audit shared `conn.execute()` writes** — either: (a) wire `DbWriter` into the FastAPI lifespan and thread it through modules that write (the intended pattern), or (b) add an `asyncio.Lock` around the shared DuckDB connection in `app.state`, or (c) document explicitly that single-threaded asyncio serialization is sufficient and remove `DbWriter` to avoid dead-code confusion.

3. **Add migration versioning** — introduce a `schema_migrations` table that records applied migration names. Move the one-time `UPDATE` backfills to a named migration that is skipped if already recorded. This removes the per-startup write load and makes DB state auditable.

4. **Add `__init__.py` to `parallax/config/`** — one-line fix.

5. **Split `scoring/tracker.py`** — extract order management, P&L computation, and position tracking into separate modules (≤10KB each) to reduce maintenance surface.

---

## Coverage Summary

| Area | Status |
|------|--------|
| Spec/Plan alignment | Significant drift (architectural pivot) |
| Core prediction models | Implemented and tested |
| Market integrations (Kalshi, Polymarket) | Implemented and tested |
| Paper trading + ledger | Implemented and tested |
| Scoring / scorecard | Implemented and tested |
| Portfolio simulation | Implemented and tested |
| DuckDB single-writer pattern | Built but not wired up |
| H3 spatial model / hex map | Not implemented |
| Agent swarm (50 LLM agents) | Not implemented |
| DES simulation engine | Not implemented |
| GDELT semantic dedup | Not implemented |
| Frontend (polling, recharts) | Implemented (diverged from spec's deck.gl/WS) |
