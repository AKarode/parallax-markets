# Parallax Health Check — 2026-09-11

**Status: RED**

## Summary

The core simulation layer (cascade, world state, DES engine, config) and prediction pipeline (oil price, ceasefire, Hormuz) are implemented and have reasonable test coverage. However, four complete subsystems required by the Phase 1 spec are entirely missing — the LLM agent swarm (`agents/`), the eval framework (`eval/`), the H3 spatial layer (`spatial/`), and the API auth layer (`api/auth.py`). The DuckDB single-writer constraint documented in the spec and implemented in `db/writer.py` is violated by at least 10 other modules that write directly to DuckDB, creating live concurrency hazards, and `main.py` shares a single connection across all async FastAPI handlers with no locking.

---

## Issues Found

### Critical

- **[CRITICAL] DuckDB single-writer pattern violated across 10 modules** — `db/writer.py` implements the correct asyncio queue but is bypassed by `scoring/tracker.py`, `scoring/ledger.py`, `scoring/resolution.py`, `scoring/scorecard.py`, `scoring/prediction_log.py`, `budget/tracker.py`, `contracts/registry.py`, `ops/alerts.py`, `ingestion/crisis_ingester.py`, and `backtest/runner.py`. All issue direct `.execute(INSERT/UPDATE)` calls. The spec explicitly states all writes must go through the single-writer queue. Under concurrent async load (e.g. `POST /api/brief/run` while `GET /api/trades` is active), DuckDB raises `TransactionContext Error: cannot start a transaction within a transaction` or silently corrupts state.

- **[CRITICAL] `main.py` shares a raw DuckDB connection across all concurrent async request handlers** — `app.state.db` is a single `duckdb.DuckDBPyConnection` used by every endpoint with no locking. No `DbWriter` is initialized in the FastAPI lifespan. Read-only endpoints are fine; `POST /api/brief/run` triggers the full pipeline, which writes through `scoring/tracker.py` and `scoring/ledger.py` while concurrent read handlers are also executing on the same connection object.

- **[CRITICAL] Entire `agents/` subsystem is missing** — The spec's 50-agent country→sub-actor hierarchy (the project's core value proposition) has no implementation. The `agents/` directory, all agent YAML prompts, `runner.py`, `country_agent.py`, and `router.py` are all absent. The prediction models in `prediction/` use direct LLM calls but are not the agent-swarm architecture described in the spec.

- **[CRITICAL] Entire `eval/` subsystem is missing** — No `eval/predictions.py`, `eval/scoring.py`, `eval/ground_truth.py`, `eval/prompt_versioning.py`, or `eval/improvement.py` exist. The spec's continuous eval framework (direction/magnitude/calibration scoring, prompt versioning, A/B comparison, miss tagging) has no implementation.

### High

- **[HIGH] Module-level monkey-patch race condition in `backtest/engine.py` line ~189** — `ctx.get_crisis_context = lambda: context_text` replaces a module-level function reference to inject backtest context, relying on a `finally` block to restore it. If two backtest runs overlap or if the main brief pipeline calls `get_crisis_context()` concurrently via `asyncio.gather()`, coroutines see each other's context text. This is a classic async safety violation. Fix: pass `context_text` as a parameter to predictors rather than patching the module.

- **[HIGH] Entire `spatial/` subsystem missing** — No H3 spatial layer (`spatial/loader.py`, `spatial/h3_utils.py`). The spec requires 4 H3 resolution bands, shipping routes as cell chains, and per-hex attributes. The dependencies `h3`, `searoute`, `shapely` are all absent from `pyproject.toml`.

- **[HIGH] No auth on any API endpoint** — The spec requires invite-code gating and an admin password for sim controls. `main.py` exposes all 14 endpoints publicly with no middleware or auth checks.

- **[HIGH] `ingestion/dedup.py` missing** — The spec's 4-stage GDELT filter requires semantic deduplication via `sentence-transformers`. The module was never created; `sentence-transformers` is also absent from `pyproject.toml`.

### Medium

- **[MEDIUM] 9 of 18 plan-expected test files missing** — Present: `test_schema.py`, `test_writer.py`, `test_cascade.py`, `test_world_state.py`, `test_config.py`. Missing: `test_h3_utils.py`, `test_gdelt_filter.py`, `test_dedup.py`, `test_circuit_breaker.py`, `test_agent_schemas.py`, `test_agent_router.py`, `test_agent_runner.py`, `test_scoring.py`, `test_predictions.py`, `test_prompt_versioning.py`, `test_auth.py`, `test_budget_tracker.py`, `test_integration.py`.

- **[MEDIUM] `simulation/circuit_breaker.py` missing** — The circuit breaker (max escalation per tick, cooldown, exogenous shock override) was designed and tested in the plan but the source file was never created. `test_circuit_breaker.py` is also missing.

- **[MEDIUM] `db/queries.py` missing** — The plan designated this as the approved location for read-only query helpers. It was never created; query logic is scattered across `dashboard/data.py`, `main.py`, and other modules.

- **[MEDIUM] `config/` subpackage has no `__init__.py`** — `backend/src/parallax/config/` contains only `risk.py` with no `__init__.py`, inconsistent with all other subpackages. Can cause import failures with `pytest`, `mypy`, and the `hatchling` build backend.

- **[MEDIUM] Key dependencies missing from `pyproject.toml`** — `h3>=4.1`, `searoute>=1.3`, `shapely>=2.0`, `sentence-transformers>=3.4`, `google-cloud-bigquery>=3.27`, `websockets>=14.0` are all listed in the spec/plan but absent from the production dependency list. `numpy`, `pandas`, and `scikit-learn` are bench-only optional dependencies but are used in core scoring paths.

- **[MEDIUM] Frontend is a minimal React+Recharts shell** — No `deck.gl`, no `MapLibre GL`, no `react-map-gl`, no `h3-js`, no WebSocket hook, no `useHexData` ref pattern, no `AgentFeed`, `LiveIndicators`, `Timeline`, or `PredictionCards` components. The spec's H3 hex map and WebSocket real-time update architecture are entirely absent from the frontend.

### Low

- **[LOW] Date comparison in `backtest/engine.py` line ~183 is fragile** — `str(date.fromisoformat(test_date) - timedelta(days=2))` produces a bare `YYYY-MM-DD` string. If any `e["date"]` in the timeline is a full ISO datetime string (with time component), the lexicographic comparison silently breaks. Should parse both sides with `date.fromisoformat()`.

- **[LOW] No linter or formatter configuration** — No `.black`, `ruff`, or `pyproject.toml [tool.ruff]` section. Code style is consistent by convention but not enforced.

- **[LOW] No `pytest-cov` or coverage configuration** — Test coverage cannot be measured or gated in CI.

- **[LOW] `portfolio/` has no `__init__.py`** — Similar to `config/`, the `portfolio/` subpackage directory may be missing an `__init__.py` (not confirmed as present).

---

## Recommendations

1. **Immediate (blocking correctness):** Route all writes in `scoring/tracker.py`, `scoring/ledger.py`, `scoring/resolution.py`, `scoring/scorecard.py`, `scoring/prediction_log.py`, `budget/tracker.py`, `contracts/registry.py`, `ops/alerts.py`, `ingestion/crisis_ingester.py`, and `backtest/runner.py` through the `DbWriter` queue — or at minimum add explicit connection-level locking via `asyncio.Lock` if the single-process constraint is honoured. Initialize `DbWriter` in `main.py` lifespan and pass it through `app.state`.

2. **Immediate (correctness):** Fix the monkey-patch race in `backtest/engine.py` — pass `context_text` as a parameter instead of patching the module-level function.

3. **Short-term:** Implement `simulation/circuit_breaker.py` (design is fully specified in the plan). Add `config/__init__.py`. Create `db/queries.py` as a home for scattered read helpers.

4. **Medium-term:** The `agents/` subsystem is the project's core differentiator and is entirely absent. Start with the registry and schemas (Tasks 11-12 in the plan), then the runner with real LLM calls.

5. **Medium-term:** Add missing dependencies (`h3`, `searoute`, `shapely`, `sentence-transformers`, `google-cloud-bigquery`, `websockets`) to `pyproject.toml` production dependencies. Create `ingestion/dedup.py`.

6. **Medium-term:** Add basic auth middleware (invite code + admin password) before any public deployment per the spec's auth requirements.

7. **Long-term:** The frontend needs the full deck.gl + MapLibre + H3HexagonLayer stack and WebSocket integration to match the spec. Current Recharts-only dashboard is a stub.
