# Parallax Health Check — 2026-09-12

**Status: RED**

## Summary

No code changes since yesterday's RED report — the same structural gaps and violations persist. The core prediction pipeline, cascade simulation, and scoring infrastructure are implemented and 433 tests pass; however, four major subsystems from the Phase 1 spec (agent swarm, eval framework, spatial layer, API auth) remain entirely unimplemented. The DuckDB single-writer constraint is violated by at least 8 modules that issue direct write operations, creating live concurrency hazards in the FastAPI server.

---

## Issues Found

### Critical

- **[CRITICAL] DuckDB single-writer pattern violated across 8+ modules** — `db/writer.py` implements the correct asyncio queue but is bypassed by `scoring/ledger.py` (INSERT + UPDATE), `scoring/resolution.py` (UPDATE), `budget/tracker.py` (INSERT), `ops/alerts.py` (INSERT), `cli/brief.py` (multiple direct INSERTs on lines 130, 149, 431), and `backtest/runner.py` (INSERT + UPDATE). All issue direct `.execute()` write calls outside the queue. The spec explicitly requires all mutable state to go through a single `asyncio.Queue → db_writer` pattern. Under concurrent async load (e.g. `POST /api/brief/run` overlapping with any other request), DuckDB will raise transaction errors or silently corrupt state.

- **[CRITICAL] `main.py` has no DbWriter in lifespan; `app.state.db` shared across handlers without locking** — The FastAPI lifespan initialises `app.state.db` as a raw `duckdb.DuckDBPyConnection` but never starts a `DbWriter` or wraps the connection. Multiple async endpoint handlers run concurrently on the same connection. Write-path endpoints (`POST /api/brief/run`) trigger the full pipeline while read-only endpoints are active, violating DuckDB's single-writer topology.

- **[CRITICAL] `agents/` subsystem entirely missing** — The spec's 50-agent country→sub-actor hierarchy (the project's core value proposition) has no implementation. The `agents/` directory, all agent YAML prompts, `runner.py`, `country_agent.py`, and `router.py` are absent. The `prediction/` models use direct LLM calls; they are not the agent-swarm architecture in the spec.

- **[CRITICAL] `eval/` subsystem entirely missing** — No `eval/predictions.py`, `eval/scoring.py`, `eval/ground_truth.py`, `eval/prompt_versioning.py`, or `eval/improvement.py`. The spec's continuous eval framework (direction/magnitude/calibration scoring, prompt versioning A/B, miss tagging) has no implementation.

### High

- **[HIGH] `spatial/` subsystem missing** — No H3 spatial layer (`spatial/loader.py`, `spatial/h3_utils.py`). The spec requires 4 H3 resolution bands, shipping routes as cell chains, and per-hex cell attributes for the visualisation. Dependencies `h3`, `searoute`, and `shapely` are absent from `pyproject.toml`.

- **[HIGH] No API auth on any endpoint** — The spec requires invite-code gating and admin password for simulation controls. All 14 FastAPI endpoints in `main.py` are publicly accessible; no auth middleware or guards exist.

- **[HIGH] Module-level monkey-patch in `backtest/engine.py`** — `ctx.get_crisis_context = lambda: context_text` patches a module-level function to inject backtest context, relying on a `finally` block to restore it. If two backtest runs overlap, or if `get_crisis_context()` is called concurrently via `asyncio.gather()`, coroutines will see each other's context text. Fix: pass `context_text` as a parameter to predictors.

### Medium

- **[MEDIUM] `bench` test files fail at import: `numpy`, `pandas` not installed under `[dev]` extras** — `tests/test_bench_forecast.py`, `tests/test_calibration_metrics.py`, `tests/test_recalibrators.py`, and `tests/test_selective.py` all fail collection with `ModuleNotFoundError`. These modules are only available under `[bench]` extras but the tests are in the main `tests/` directory and run by default. Either gate these tests or move the dependencies to `[dev]`.

- **[MEDIUM] Frontend is missing all spec-required components** — The spec requires `HexMap.tsx`, `AgentFeed.tsx`, `LiveIndicators.tsx`, `Timeline.tsx`, `PredictionCards.tsx`, and `HexPopover.tsx`. The `frontend/src/components/` directory contains only dashboard data components (`KpiBar`, `MarketsTable`, `ModelCards`, `PortfolioPanel`, etc). No deck.gl / MapLibre map, no agent feed, no WebSocket layer.

- **[MEDIUM] Python version: spec targets 3.12, repo runs on 3.11** — The plan specifies Python 3.12. `pyproject.toml` requires `>=3.11` and the container runs 3.11.15. No known breakage today, but 3.12 performance improvements and `asyncio` changes are untested.

- **[MEDIUM] Missing `db/queries.py`** — The plan specifies a `queries.py` read-only helper module (`get_current_tick`, `get_world_state_at_tick`, `get_recent_decisions`). This file is absent; query logic is inlined across multiple modules.

### Low

- **[LOW] `simulation/` is missing `engine.py` and `circuit_breaker.py`** — Both files exist in the plan (Tasks 7–8) and in earlier health-check reports as implemented, but neither is present in `backend/src/parallax/simulation/` today. Only `cascade.py`, `config.py`, and `world_state.py` are present. The DES engine and circuit breaker tests still pass, which suggests these modules may have been inadvertently deleted from the source tree while their tests remained.

- **[LOW] `api/` subpackage absent** — The plan specifies `api/routes.py`, `api/websocket.py`, and `api/auth.py` as a dedicated subpackage. All API code is currently inlined in `main.py`, which is over 250 lines. Not a bug but diverges from the plan's modular structure.

- **[LOW] `deck.gl`, `MapLibre`, and `react-map-gl` absent from `package.json`** — The spec's core visualisation stack (H3 hexagon layers, deck.gl) is not installed. `package.json` only lists React, react-dom, and Recharts.

---

## Recommendations

1. **Immediate (blocks correctness):** Route all writes through `DbWriter` or wrap the DuckDB connection with a lock. The simplest fix for the CLI path is to use a single `duckdb.connect()` per process and serialize writes via the existing queue.
2. **Short-term:** Fix the bench test collection failures by adding `pytest.ini` markers or moving bench tests to a separate suite invoked with `pip install -e ".[bench]"`.
3. **Medium-term:** Implement the `agents/` and `eval/` subsystems — these are the core value proposition of the product and have been missing for the entire tracked period.
4. **Architecture:** Start the `api/` refactor and add invite-code auth middleware before any external demo or access.

---

_Report generated by automated daily health check. 433 tests pass, 13 skipped, 4 test files fail at import due to missing `bench` extras._
