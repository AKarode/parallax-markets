# Parallax Health Check — 2026-10-20

**Status: YELLOW**

The project has deliberately pivoted from the Phase 1 spec (LLM agent swarm + H3 map simulator) to a more focused prediction-market edge-finder (Kalshi/Polymarket + 3 prediction models). Core prediction-market pipeline is well-covered by tests and appears stable. However, large spec modules remain unimplemented, multiple modules bypass the mandated single-writer DB pattern, and several spec dependencies are absent from `pyproject.toml`.

---

## Issues Found

### Architecture Drift

- **[HIGH] Intentional pivot not reflected in spec**: The spec describes a 50-agent LLM swarm with H3 spatial simulation; CLAUDE.md describes (and the code implements) a prediction-market edge-finder with 3 focused predictors. These are functionally different products. The spec has not been updated to reflect the pivot.
- **[HIGH] Entire agent swarm layer missing**: `parallax/agents/` (schemas, registry, runner, router, prompts/) do not exist. The spec's country-agent hierarchy, sub-actor conflict resolution, and routing are unimplemented.
- **[HIGH] Simulation engine missing**: `simulation/engine.py` (DES + heapq priority queue) and `simulation/circuit_breaker.py` are absent. `simulation/cascade.py`, `config.py`, and `world_state.py` exist but are not wired to a running engine.
- **[HIGH] Spatial layer missing**: `spatial/` module does not exist — no H3 resolution bands, no route-to-cell conversion, no Overture Maps loader.
- **[HIGH] Eval framework absent**: `eval/` module (predictions.py, scoring.py, ground_truth.py, prompt_versioning.py, improvement.py) is entirely missing. The spec's structured prediction format, calibration scoring, and prompt-versioning A/B pipeline are not implemented.
- **[MEDIUM] API layer absent**: `api/` module (routes.py, websocket.py, auth.py) does not exist. All endpoints live in `main.py` directly. Invite-code auth and admin mode are not implemented.
- **[MEDIUM] Frontend is a different product**: Spec calls for 3-column H3 map dashboard (HexMap, AgentFeed, Timeline, PredictionCards); actual frontend is a prediction-market trading dashboard (KpiBar, MarketsTable, ModelCards, PortfolioPanel). None of the spec's frontend components exist.

### Dependency Audit

- **[HIGH] Missing spec dependencies in `pyproject.toml`**: `h3`, `sentence-transformers`, `searoute`, `shapely`, `google-cloud-bigquery`, `websockets` are specified in the plan but absent from the declared dependencies. Code that imports them will fail at install time in a fresh environment.
- **[MEDIUM] Python version floor too low**: Spec requires Python 3.12+; `pyproject.toml` sets `requires-python = ">=3.11"`. The codebase uses 3.10+ union-type syntax (`str | None`) which is compatible, but misaligns with spec intent.
- **[LOW] `truthbrush` dependency**: `truthbrush>=0.2` is declared but is an unofficial scraper package with no stable API contract. If the Truth Social scraping target changes its HTML, this silently breaks.

### DuckDB Single-Writer Violations

The spec mandates all writes go through `DbWriter`'s `asyncio.Queue`. Multiple modules bypass this and write directly:

- **[HIGH] `scoring/ledger.py`**: Direct `self._conn.execute(INSERT ...)` and `self._conn.execute(UPDATE ...)` calls.
- **[HIGH] `budget/tracker.py`**: Direct `self._db_conn.execute(INSERT INTO llm_usage ...)`.
- **[HIGH] `cli/brief.py`**: Direct `conn.execute(INSERT INTO runs ...)` and `UPDATE runs` — does not use `DbWriter`.
- **[HIGH] `ops/alerts.py`**: Direct `conn.execute(INSERT INTO ops_events ...)`.
- **[MEDIUM] `scoring/tracker.py`, `scoring/prediction_log.py`, `scoring/scorecard.py`, `scoring/recalibration.py`, `scoring/resolution.py`, `scoring/report_card.py`**: All use direct `conn.execute` for writes. In the CLI's sequential single-process context this doesn't cause `database is locked`, but it violates the architectural invariant and will break if any two of these ever run concurrently.

### Test Coverage Gaps

13 test files called for in the plan are absent:

- **[MEDIUM]** `test_h3_utils.py`, `test_gdelt_filter.py`, `test_dedup.py` — spatial and ingestion filter coverage missing.
- **[MEDIUM]** `test_circuit_breaker.py`, `test_agent_schemas.py`, `test_agent_router.py`, `test_agent_runner.py` — agent layer coverage missing (blocked on implementation).
- **[MEDIUM]** `test_scoring.py`, `test_predictions.py`, `test_prompt_versioning.py` — eval framework coverage missing.
- **[MEDIUM]** `test_auth.py`, `test_budget_tracker.py`, `test_integration.py` — auth, budget, and end-to-end coverage missing.

### Code Quality

- **[MEDIUM] `db/queries.py` missing**: The plan specifies read-only query helpers in `db/queries.py`; this file does not exist. Read queries are scattered across modules with no shared read layer.
- **[LOW] `scoring/` module sprawl**: The scorecard/scoring layer has 10+ files (`calibration.py`, `calibration_metrics.py`, `recalibration.py`, `recalibrators.py`, `selective.py`, `track_record.py`). No plan task accounts for these; they appear to be organic additions without documented spec rationale.

---

## Recommendations

1. **Update the spec** to reflect the actual product (prediction-market edge-finder). Either retire the agent-swarm spec or create a Phase 2 doc. The current gap between spec and code causes confusion for health checks and onboarding.
2. **Fix single-writer violations** in `scoring/ledger.py`, `budget/tracker.py`, `cli/brief.py`, and `ops/alerts.py` by routing writes through `DbWriter.enqueue()`. This is the single most dangerous architectural debt — concurrent execution will cause `database is locked` errors.
3. **Add missing deps** (`h3`, `sentence-transformers`, `searoute`, `shapely`, `websockets`) to `pyproject.toml` or remove code paths that reference them.
4. **Add `test_budget_tracker.py` and `test_auth.py`** — these guard budget-cap enforcement and access control, which are prod-critical.
5. **Implement `db/queries.py`** as a shared read layer to consolidate the scattered `conn.execute(SELECT ...)` calls currently duplicated across modules.
