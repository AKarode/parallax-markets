# Parallax Health Check — 2026-08-23

**Status: RED**

No code changes since 2026-08-22. All critical issues from yesterday's RED report persist: the single-writer DuckDB contract remains unenforced (`DbWriter` exists but is never started in `main.py`), `cryptography` is still missing from `pyproject.toml` (breaking Kalshi auth on clean installs), and the three major spec packages (`agents/`, `eval/`, `spatial/`) remain unimplemented. The test suite is healthy at 433 passing / 13 skipped (4 test files skipped due to `bench` extras not installed in CI).

---

## Delta Since 2026-08-22

- **No source code changes.** The only commits since yesterday added health check and tech research reports.
- All issues below carry over from the prior report unchanged.

---

## Issues Found

### CRITICAL

- **[ARCH] DbWriter never started — single-writer contract unenforced**
  `db/writer.py` implements the asyncio.Queue pattern correctly but is never instantiated or started anywhere. `app.state.db` in `main.py` is a raw `duckdb.DuckDBPyConnection`. Every write in the system bypasses the queue, making the system vulnerable to `database is locked` under concurrent write load.
  _Files:_ `main.py` (lifespan), `scoring/ledger.py:225,256`, `scoring/resolution.py:60,124`, `scoring/scorecard.py:21`, `ops/alerts.py:106`, `budget/tracker.py:43`, `cli/brief.py:130,149,431`

- **[DEP] `cryptography` not declared in pyproject.toml**
  `markets/kalshi.py` imports `cryptography.hazmat` for RSA-PSS signing. Not declared as a dependency. A clean `pip install -e .` succeeds but Kalshi auth fails at runtime with `ModuleNotFoundError`. Second consecutive day unfixed.

### HIGH

- **[SPEC] `agents/` package entirely unimplemented**
  The 50-agent LLM swarm (country → sub-actor hierarchy) specified in Phase 1 — `agents/registry.py`, `agents/runner.py`, `agents/router.py`, `agents/schemas.py`, `agents/country_agent.py`, and per-actor YAML prompts — are all absent. The codebase has pivoted to a 3-model prediction approach instead.

- **[SPEC] `eval/` package entirely unimplemented**
  Prompt versioning, A/B accuracy comparison, miss tagging (`model_error` / `exogenous_shock`), and the meta-agent prompt improvement pipeline are not implemented.

- **[SPEC] `spatial/` package entirely unimplemented**
  `spatial/h3_utils.py` and `spatial/loader.py` absent. H3 resolution bands, route-to-cell conversion, and the Overture Maps loading pipeline are missing. The deck.gl hex map has no data generation backend.

- **[SPEC] `simulation/engine.py` and `simulation/circuit_breaker.py` missing**
  The DES event queue (`heapq` + asyncio tick loop) and cascade circuit breaker (escalation cooldowns, exogenous shock bypass) are absent. `cascade.py` is correct but there is no engine to drive it.

### MEDIUM

- **[DEP] 6 spec-required packages absent from pyproject.toml**
  `h3`, `searoute`, `shapely`, `sentence-transformers`, `google-cloud-bigquery`, `websockets` are all referenced in the Phase 1 spec but not declared as dependencies. These correspond to unimplemented features (spatial layer, GDELT BigQuery, semantic dedup, WebSocket push). Not blocking for current functionality, but `pip install -e .` will not install them.

- **[DEP] `requires-python = ">=3.11"` conflicts with CLAUDE.md (Python 3.12)**
  CLAUDE.md specifies Python 3.12; pyproject.toml allows 3.11+. Minor inconsistency that could allow a 3.11 install to succeed but fail on 3.12-only syntax.

- **[SPEC] `db/queries.py` missing**
  The plan specifies read-only DuckDB helpers (`get_current_tick`, `get_world_state_at_tick`, `get_recent_decisions`). Read queries are scattered across modules rather than centralized.

- **[SPEC] `ingestion/dedup.py` missing**
  Stage 3 of the GDELT 4-stage filter (semantic dedup via sentence-transformers) is not implemented. Events pass volume gate and proceed directly to relevance scoring without cosine-similarity dedup.

- **[SPEC] `api/` package not separated from main.py**
  Routes, WebSocket handler, and auth middleware are inlined in `main.py` rather than split into `api/routes.py`, `api/websocket.py`, `api/auth.py` as specified.

- **[TEST] 4 test files fail to collect due to missing `bench` extras**
  `test_bench_forecast.py`, `test_calibration_metrics.py`, `test_selective.py`, `test_recalibrators.py` all fail import with `ModuleNotFoundError: No module named 'numpy'/'pandas'`. The `bench` extras group must be installed explicitly (`pip install -e ".[dev,bench]"`). This should be documented or the CI matrix should cover it.

- **[ARCH] Frontend has drifted from spec**
  Phase 1 spec calls for `HexMap.tsx`, `AgentFeed.tsx`, `LiveIndicators.tsx`, `Timeline.tsx`, `PredictionCards.tsx`, `HexPopover.tsx` (H3 hex map + agent feed dashboard). Actual frontend: `ContractDetail.tsx`, `KpiBar.tsx`, `MarketsTable.tsx`, `ModelCards.tsx` (prediction market dashboard). This is a deliberate product pivot, not a bug, but the spec is now stale relative to implementation.

---

## Test Coverage Summary

| Category | Status |
|---|---|
| Core tests (433 passing) | GREEN |
| Bench-extra tests (4 uncollectable) | YELLOW — need `[dev,bench]` install |
| Plan-specified tests missing | `test_h3_utils.py`, `test_gdelt_filter.py`, `test_dedup.py`, `test_circuit_breaker.py`, `test_agent_schemas.py`, `test_agent_router.py`, `test_agent_runner.py`, `test_auth.py`, `test_integration.py` |

---

## Recommendations

1. **[Urgent] Wire up `DbWriter` in `main.py` lifespan** — start it as a background task and pass it to all write-producing modules. This is the single highest-risk open issue; under any concurrent load, raw direct writes will produce `database is locked` errors.

2. **[Urgent] Add `cryptography` to pyproject.toml** — one-line fix. Second day unfixed.

3. **[Planned] Update Phase 1 spec to reflect the prediction-market pivot** — the CLAUDE.md architecture section is already updated, but the design doc and implementation plan still describe the agent swarm. Either update them or create a Phase 1b plan that documents the actual architecture.

4. **[Backlog] Add `cryptography`, `h3`, `searoute`, `shapely` to pyproject.toml** as needed when the corresponding features are built.

5. **[Backlog] Add CI step for `pip install -e ".[dev,bench]"** to catch bench-test collection errors.
