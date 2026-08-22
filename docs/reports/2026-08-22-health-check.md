# Parallax Health Check — 2026-08-22

**Status: RED**

The core prediction pipeline (markets, models, scoring, CLI) is functional and well-tested with 47 test files, well beyond the spec's 18. However, the single-writer DuckDB contract — the most critical architectural invariant — is completely unenforced in production code: `DbWriter` exists but is never started, and ~100+ modules write directly to raw DuckDB connections. Three major spec packages (`agents/`, `eval/`, `spatial/`) are entirely unimplemented. A missing `cryptography` dependency will break Kalshi API auth on a clean install.

---

## Issues Found

### CRITICAL

- **[ARCH] DbWriter is dead code — single-writer contract unenforced**
  `db/writer.py` implements the asyncio.Queue pattern correctly but is never instantiated or started in `main.py` or anywhere else. `app.state.db` is a raw `duckdb.DuckDBPyConnection`. Every write in the system bypasses the queue entirely, making the system vulnerable to `database is locked` errors under any concurrent write load.
  _Files:_ `main.py` (lifespan handler), all modules listed below.

- **[ARCH] ~100+ direct `conn.execute()` write calls outside db/writer.py**
  Every module does direct writes, violating the single-writer topology the spec mandates as a "hard constraint." Major offenders:
  - `scoring/tracker.py` — 12+ direct write sites (heaviest offender)
  - `scoring/scorecard.py` — 21 direct execute calls
  - `cli/brief.py` — 6 direct write sites (run persistence, market writes)
  - `contracts/registry.py` — 9 direct write sites
  - `backtest/runner.py`, `backtest/report.py`, `backtest/look_ahead_guard.py` — 20+ combined
  - `scoring/ledger.py`, `scoring/resolution.py`, `scoring/prediction_log.py`, `dashboard/app.py`, `ops/alerts.py`, `budget/tracker.py`, `portfolio/simulator.py`, `ingestion/crisis_ingester.py` — all direct

- **[DEP] Missing `cryptography` dependency in pyproject.toml**
  `markets/kalshi.py` imports `from cryptography.hazmat.primitives import hashes, serialization` and `from cryptography.hazmat.primitives.asymmetric import padding` for RSA-PSS signing. `cryptography` is not declared in `pyproject.toml`. A clean `pip install -e .` will succeed but Kalshi auth will fail at runtime with `ModuleNotFoundError`.

### HIGH

- **[SPEC] `agents/` package entirely unimplemented**
  The spec calls for `agents/registry.py`, `agents/runner.py`, `agents/router.py`, `agents/schemas.py`, `agents/country_agent.py`, and a `prompts/` directory with one YAML per sub-actor. None exist. The ~50-agent LLM swarm (country → sub-actor hierarchy) is the core differentiator of Phase 1 and is entirely missing.

- **[SPEC] `eval/` package entirely unimplemented**
  `eval/predictions.py`, `eval/scoring.py`, `eval/ground_truth.py`, `eval/prompt_versioning.py`, `eval/improvement.py` — none exist. Prompt versioning, A/B comparison, miss tagging, and the prompt improvement pipeline are all absent.

- **[SPEC] `spatial/` package entirely unimplemented**
  `spatial/h3_utils.py` and `spatial/loader.py` are absent. H3 resolution bands, route-to-cell conversion, and Overture Maps loading are unimplemented. The deck.gl hex map has no data generation pipeline.

- **[SPEC] `simulation/engine.py` and `simulation/circuit_breaker.py` missing**
  The DES event queue (`heapq` + asyncio tick loop) and the cascade circuit breaker (escalation cooldowns, exogenous shock override) are both absent. `cascade.py` has all 6 rules implemented correctly but there is no engine to drive the simulation.

### MEDIUM

- **[CODE] Hardcoded model ID in `prediction/oil_price.py`**
  Line 89 uses `"claude-opus-4-20250514"` as a literal string rather than reading from `ScenarioConfig` or an environment variable. A model rotation or upgrade requires a code change instead of a config change.

- **[CODE] Private method call in `cli/brief.py`**
  Line 930 calls `client._request(...)` on `KalshiClient` directly — a private method. This couples the brief pipeline to the internal implementation and will silently break if `KalshiClient` is refactored.

- **[SPEC] `db/queries.py` missing**
  The plan specifies a `queries.py` for read-only DuckDB helpers (`get_current_tick`, `get_world_state_at_tick`, `get_recent_decisions`). Only `schema.py`, `writer.py`, and `runtime.py` exist under `db/`.

- **[SPEC] `ingestion/dedup.py` missing**
  Stage 3 of the GDELT filter (semantic dedup via `sentence-transformers` cosine similarity) is not implemented. All GDELT events that pass volume gate proceed directly to relevance scoring without dedup.

- **[SPEC] `api/` package not separated from main.py**
  Routes, WebSocket handler, and auth middleware are inlined in `main.py` rather than split into `api/routes.py`, `api/websocket.py`, `api/auth.py` as specified.

- **[TEST] 10 of 18 spec-planned test files missing**
  Missing: `test_h3_utils.py`, `test_gdelt_filter.py`, `test_dedup.py`, `test_circuit_breaker.py`, `test_agent_schemas.py`, `test_agent_router.py`, `test_agent_runner.py`, `test_prompt_versioning.py`, `test_auth.py`, `test_budget_tracker.py`, `test_integration.py`.
  Note: 47 additional tests cover areas beyond the spec (calibration, backtest, contracts, ensembles), so overall test breadth is strong despite the gaps.

### LOW

- **[STRUCT] `portfolio/` missing `__init__.py`** — package is not properly declared.
- **[STRUCT] `config/` missing `__init__.py`** — same issue.
- **[SPEC] Frontend uses polling instead of WebSocket** — `hooks/usePolling.ts` replaces the spec's `useWebSocket.ts` + `useHexData.ts`. No WebSocket connection exists. This is a deliberate simplification but diverges from the spec's render-performance design (mutable `useRef` for hex data, 100ms batched updates).
- **[SPEC] Frontend components diverge from spec layout** — actual components are `KpiBar`, `MarketsTable`, `ModelCards`, `ModelHealth`, `PortfolioPanel`, `PriceChart` rather than the spec's `HexMap`, `AgentFeed`, `LiveIndicators`, `Timeline`, `PredictionCards`. The pivot from a 3-column hex-map dashboard to a markets/prediction dashboard is significant.

---

## Recommendations

1. **Wire DbWriter immediately** — in `main.py` lifespan, instantiate `DbWriter(app.state.db)` and start it as a background task. All write-producing modules should receive the `DbWriter` instance via FastAPI dependency injection and call `await writer.enqueue(sql, params)` instead of `conn.execute()`. This is the single highest-risk open item.

2. **Add `cryptography` to pyproject.toml** — one-line fix, blocks Kalshi auth on clean installs.

3. **Add missing `portfolio/__init__.py` and `config/__init__.py`** — trivial.

4. **Implement `agents/` package** — this is the core Phase 1 differentiator. Start with `agents/registry.py` (port from the plan's roster), then `agents/schemas.py`, then `agents/router.py`. The `runners/` and `country_agent.py` can follow.

5. **Implement `simulation/engine.py` and `simulation/circuit_breaker.py`** — needed to drive the cascade pipeline end-to-end.

6. **Move hardcoded model ID to config** — add `llm_model_sonnet: str` and `llm_model_haiku: str` fields to `ScenarioConfig` / `scenario_hormuz.yaml`.

7. **Implement `ingestion/dedup.py`** — `sentence-transformers` is already in the bench extras; promote to core dependencies and implement the semantic dedup stage.

8. **Fix `brief.py` private method call** — expose a public `request()` method on `KalshiClient` or use existing public methods.
