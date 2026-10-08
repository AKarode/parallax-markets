# Parallax Health Check — 2026-10-08

**Status: RED**

**Summary:** Three critical blockers prevent the system from functioning as designed: the entire `agents/` module is absent (no LLM agent swarm exists), the `asyncio.Queue` single-writer pattern is architecturally sound but bypassed by virtually all write-path code causing DuckDB write conflicts under concurrency, and three core API endpoints always return empty arrays because in-memory state is never populated from brief runs. The project has been at YELLOW status for 10+ consecutive days with no remediation commits.

---

## Issues Found

### CRITICAL

- **[CRITICAL] `agents/` module entirely missing.** No `agents/` directory exists in the codebase. The schema defines `agent_memory`, `agent_prompts`, and `decisions` tables, and the design spec calls for a 50-agent country→sub-actor swarm, but zero implementation code exists — no `registry.py`, `runner.py`, `router.py`, `country_agent.py`, or prompt YAML files. The system cannot perform agent-based reasoning.

- **[CRITICAL] DbWriter single-writer pattern bypassed everywhere.** `db/writer.py` correctly implements the `asyncio.Queue` pattern required by DuckDB's single-writer constraint. However, 11+ modules bypass it entirely with direct `conn.execute()` INSERT/UPDATE calls: `scoring/ledger.py`, `scoring/tracker.py`, `scoring/resolution.py`, `scoring/scorecard.py`, `contracts/registry.py`, `budget/tracker.py`, `ops/alerts.py`, `backtest/runner.py`, `cli/brief.py`, `ingestion/crisis_ingester.py`, `portfolio/simulator.py`. Concurrent FastAPI requests will produce DuckDB `database is locked` errors or silent state corruption.

- **[CRITICAL] Core API endpoints always return empty arrays.** `app.state.last_predictions`, `app.state.last_markets`, and `app.state.last_divergences` are initialized as empty lists in `main.py` and never populated when a brief run completes via `POST /api/brief/run`. Endpoints `GET /api/predictions`, `GET /api/markets`, and `GET /api/divergences` are permanently broken.

### HIGH

- **[HIGH] No authentication on any API endpoint.** All 14 FastAPI endpoints are open with no auth middleware, API key validation, or invite-code enforcement. The spec requires gated access via invite links and admin-password middleware.

- **[HIGH] `simulation/circuit_breaker.py` missing.** The cascade circuit breaker (escalation limits, cooldowns, exogenous shock override) is called out in both spec and plan but not implemented. The `simulation/` directory has only `cascade.py`, `config.py`, `world_state.py`.

- **[HIGH] `ingestion/dedup.py` missing.** The 4-stage GDELT filter requires a `SemanticDeduplicator` (sentence-transformers, cosine similarity). No such module exists; `gdelt_doc.py` uses a basic hash-set dedup that misses semantically equivalent but textually different events.

- **[HIGH] `h3` not declared as a dependency.** H3 cell IDs appear throughout the data model (`cell_id BIGINT` in `world_state_delta`/`world_state_snapshot`, `h3_cell BIGINT` in `curated_events`, `target_h3_cells JSON` in `decisions`), but `h3` (or `h3-py`) is absent from `pyproject.toml`. The `spatial/` module referenced in the plan also does not exist.

### MEDIUM

- **[MEDIUM] 13 of 18 planned test files missing.** Present: `test_schema.py`, `test_writer.py`, `test_cascade.py`, `test_world_state.py`, `test_config.py`. Missing: `test_h3_utils.py`, `test_gdelt_filter.py`, `test_dedup.py`, `test_circuit_breaker.py`, `test_agent_schemas.py`, `test_agent_router.py`, `test_agent_runner.py`, `test_scoring.py`, `test_predictions.py`, `test_prompt_versioning.py`, `test_auth.py`, `test_budget_tracker.py`, `test_integration.py`. (The codebase has 33 bonus test files for modules added beyond the plan scope.)

- **[MEDIUM] `config/` package has no `__init__.py`.** `backend/src/parallax/config/` contains only `risk.py` with no `__init__.py`, making `parallax.config` unimportable as a package. This will cause `ImportError` if any code attempts `from parallax.config import ...`.

- **[MEDIUM] Status stuck at YELLOW for 10+ consecutive days.** Git log shows every recent commit is a health-check or research report. No feature, fix, or remediation commits have landed since at least 2026-09-29. The recurring YELLOW designation masks what are now RED-severity issues.

### LOW

- **[LOW] `POST /api/brief/run` has `dry_run=True, no_trade=True` hardcoded.** There is no API path to trigger a live-trade brief or even a live no-trade run. Live execution is only accessible via the CLI.

- **[LOW] Frontend missing planned components.** The plan calls for `useWebSocket.ts`, `useHexData.ts`, `HexMap.tsx`, `AgentFeed.tsx`, `LiveIndicators.tsx`, `Timeline.tsx`, `PredictionCards.tsx`, and `HexPopover.tsx`. None of these exist; the frontend has polling-based components (`usePolling.ts`) suited to the current REST-only backend, not the WebSocket + deck.gl architecture in the spec.

---

## Recommendations

1. **Immediate (unblock core functionality):** Fix the three CRITICAL issues. The `app.state` empty-list bug is a one-line fix. The DbWriter bypass requires auditing write paths and either routing them through `DbWriter.enqueue()` or confirming they run in a single-threaded context that prevents concurrency.

2. **Short-term (implement missing spec modules):** Add `agents/` module with registry and runner (start with a stub that calls the Claude API and validates output schema). Add `simulation/circuit_breaker.py`. Add `ingestion/dedup.py` using `sentence-transformers` (already in the bench extras).

3. **Auth:** Add the invite-code + admin-password middleware from the spec before any external access.

4. **Dependency hygiene:** Add `h3>=4.1` to `pyproject.toml` dependencies. Add `__init__.py` to `config/`.

5. **Test gaps:** At minimum add `test_budget_tracker.py`, `test_auth.py`, and `test_integration.py` — these cover security and cross-cutting behavior that unit tests miss.
