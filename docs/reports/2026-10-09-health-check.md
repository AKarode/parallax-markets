# Parallax Health Check — 2026-10-09

**Status: YELLOW**

The codebase is functional as a prediction-market edge-finder (Kalshi/Polymarket signal generator), but has undergone substantial architecture drift from the Phase 1 design spec. The spec describes a 50-agent LLM swarm driving an H3 spatial simulation; the built system is a 3-model predictor comparing forecasts against market prices and trading on divergences. Core trading/scoring infrastructure is solid with 46 test files. Primary risks are DuckDB single-writer violations in production write paths and several missing spec modules.

---

## Issues Found

### CRITICAL

- **[CRITICAL] DuckDB single-writer constraint violated in 11 production files.**
  The `DbWriter` asyncio.Queue pattern exists (`db/writer.py`) but is unused by all actual write paths. Every module calls `conn.execute()` directly for INSERT/UPDATE/DELETE, bypassing the serialization queue. Concurrent async coroutines writing simultaneously can cause `database is locked` errors or data corruption. Affected files:
  - `scoring/ledger.py` (lines 225, 256)
  - `scoring/prediction_log.py` (line 79)
  - `scoring/resolution.py` (lines 60, 124)
  - `scoring/scorecard.py` (line 21)
  - `scoring/tracker.py` (lines 460, 516, 672, 711, 744)
  - `ops/alerts.py` (line 106)
  - `ingestion/crisis_ingester.py` (line 79)
  - `contracts/registry.py` (lines 85, 105, 114, 198)
  - `cli/brief.py` (lines 130, 149, 431)
  - `budget/tracker.py` (line 43)
  - `backtest/runner.py` (lines 290, 308, 329, 356)

  Immediate risk: the CLI `brief.py` runs multiple async tasks that each write directly; any await-interleaving between them can trigger locking errors under load.

### HIGH

- **[HIGH] Architecture drift: 4 spec-required subpackages entirely absent.**
  The Phase 1 spec's agent swarm, eval framework, spatial model, and WebSocket API have not been built. Missing:
  - `agents/` (runner, country_agent, router, registry, prompts YAMLs, schemas)
  - `eval/` (predictions, scoring, ground_truth, prompt_versioning, improvement)
  - `api/` (websocket.py, auth.py, routes.py)
  - `spatial/` (loader.py, h3_utils.py)
  - `ingestion/dedup.py` (semantic dedup with sentence-transformers)

  The 26-table DuckDB schema includes `agent_memory`, `agent_prompts`, `decisions`, `world_state_delta`, and `eval_results` — all of which remain permanently empty because no code populates them.

- **[HIGH] GET /api/predictions, /api/markets, /api/divergences always return empty.**
  `app.state.last_predictions`, `.last_markets`, `.last_divergences` are initialised as `[]` in `main.py` lifespan and never updated by a background task. The API is live but these three endpoints silently return empty payloads on every request. The brief pipeline only updates these if called via `POST /api/brief/run`, not on a schedule.

### MEDIUM

- **[MEDIUM] Missing dependencies in pyproject.toml.**
  The following packages are referenced in code or schema but not listed as dependencies:
  - `h3` / `h3-js` — referenced in schema (`h3_cell BIGINT`), spec requirement; not in pyproject.toml
  - `sentence-transformers` — required by spec's dedup stage; not listed (dedup.py is also missing)
  - `websockets` — spec requires WebSocket endpoint; absent from pyproject.toml and no websocket support in frontend package.json

- **[MEDIUM] No WebSocket support in either frontend or backend.**
  The spec requires a WebSocket push architecture for real-time hex updates with batched 100ms flushes. The frontend uses `usePolling.ts` (polling only). Neither `package.json` nor `pyproject.toml` includes a WebSocket library. The frontend also has no `HexMap.tsx`, `AgentFeed.tsx`, `Timeline.tsx`, or `PredictionCards.tsx` — the components described in the spec.

- **[MEDIUM] Test coverage gaps for existing production modules.**
  These modules exist but have no dedicated test file:
  - `budget/tracker.py` (cooldown enforcement, cost caps)
  - `portfolio/allocator.py` (Kelly sizing)
  - `prediction/oil_price.py` and `prediction/ceasefire.py`
  - `backtest/engine.py` and `backtest/report.py`
  - `ops/runtime.py`

### LOW

- **[LOW] Python version mismatch: pyproject.toml requires `>=3.11`, CLAUDE.md specifies Python 3.12.**
  Low risk, but inconsistent. The `str | None` union syntax (used throughout) requires >=3.10 so 3.11 is technically fine, but the stated stack is 3.12.

- **[LOW] `main.py` opens DuckDB directly (not via DbWriter) in lifespan.**
  The app stores a raw `duckdb.DuckDBPyConnection` as `app.state.db`. Route handlers that need to write should go through DbWriter; instead several call `conn.execute()` directly. Reads are safe; writes are not.

- **[LOW] Simulation engine (`simulation/engine.py`, `circuit_breaker.py`) implemented but wired to nothing.**
  `cascade.py`, `world_state.py`, `config.py`, and `engine.py` exist and have tests, but are not called from `main.py`, `brief.py`, or any production flow. They are implemented dead code.

- **[LOW] No frontend test setup.**
  `package.json` has no vitest/jest. The spec calls for a WebSocket smoke test; no test infrastructure exists to run one.

---

## Recommendations

1. **Immediate — Fix DuckDB write serialization.** Either thread all writes through the existing `DbWriter.enqueue()` (requires making all write call sites async and accepting a DbWriter instance), or — given the system's actual single-process synchronous CLI architecture — accept direct `conn.execute()` writes but add an explicit architectural note that they are safe only because `brief.py` is not concurrent. The `DbWriter` class should be used or removed to avoid misleading future contributors.

2. **Short-term — Wire up background brief refresh in the API.** Add a `asyncio.create_task` in the FastAPI lifespan that runs the brief pipeline every N minutes and updates `app.state.last_*`. Until this is done the dashboard endpoints silently lie.

3. **Medium-term — Decide on the architecture story.** The spec describes a cascade-driven agent swarm; the built system is a market-price signal finder. Either update the spec to match the implementation or draft a Phase 1b plan to fill the gaps (agents/, eval/, WebSocket, spatial). The dead simulation code (`engine.py`, `circuit_breaker.py`) should either be activated or removed.

4. **Add missing pyproject.toml dependencies** once dedup.py, spatial/, and WebSocket are built.

5. **Add test coverage** for `budget/tracker.py`, `portfolio/allocator.py`, and prediction models — these are the most financially sensitive code paths.
