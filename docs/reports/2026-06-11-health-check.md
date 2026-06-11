# Parallax Health Check — 2026-06-11

**Status: YELLOW**

## Summary

The backend core (cascade engine, world state, ingestion, 3-model ensemble, market clients, scoring ledger, budget tracker, FastAPI API) is substantially complete and functional. However, the implementation has pivoted significantly from the Phase 1 spec — the project is now a prediction market edge-finder (Kalshi/Polymarket integration + paper trading) rather than the 50-agent LLM swarm with H3 spatial visualization described in the design doc. Two critical simulation components are unimplemented, the entire `agents/` module is absent, and the single-writer DuckDB constraint is systematically violated across 10+ modules.

---

## Issues Found

### [HIGH] DuckDB single-writer constraint violated in 11 locations

The design spec (Section 9) mandates that all DB writes go through the `asyncio.Queue` in `db/writer.py`. The `DbWriter` exists but is unused by production code. Direct `conn.execute()` writes bypass it in:

- `scoring/ledger.py:225,256` — `INSERT INTO signal_ledger`, `UPDATE signal_ledger`
- `scoring/prediction_log.py:79` — `INSERT INTO prediction_log`
- `scoring/tracker.py:460,516,672,711,744` — multiple trade table writes
- `scoring/resolution.py:60,124` — resolution updates
- `scoring/scorecard.py:21` — scorecard inserts
- `cli/brief.py:130,149,431` — run row inserts/updates
- `budget/tracker.py:43` — llm_usage inserts
- `ops/alerts.py:106` — ops_events inserts
- `ingestion/crisis_ingester.py:79` — crisis_events inserts
- `backtest/runner.py:290,308,329,356` — backtest table writes
- `contracts/registry.py:85,105,114,198` — contract registry writes

All of these are subject to `database is locked` errors under concurrent load. The current CLI usage pattern (single sequential run) masks this, but the FastAPI server and any concurrent async tasks will hit it.

### [HIGH] `agents/` module entirely absent

The plan specifies Tasks 11–15 (agent schemas, registry, router, runner, country agent synthesis). None of these files exist. The 50-agent country→sub-actor hierarchy, event routing, and LLM-driven decision loop are not implemented. The current prediction models are standalone LLM calls rather than the routed agent swarm described in the spec.

### [MEDIUM] `simulation/circuit_breaker.py` and `simulation/engine.py` not implemented

Plan Tasks 7 and 8 are missing:
- `circuit_breaker.py` — escalation limits, cooldown enforcement, exogenous shock bypass
- `engine.py` — discrete event simulation (DES) core with heapq priority queue and tick loop

The cascade engine works as a standalone function library but is not wired to a live simulation tick loop. The `CascadeEngine` is called synchronously from prediction models instead.

### [MEDIUM] Architecture pivot: spec describes simulation swarm, code is a market edge-finder

The implemented system is a materially different product from what the Phase 1 spec describes:

| Spec (Phase 1 Design) | Implementation |
|---|---|
| ~50 LLM agents (country → sub-actor hierarchy) | 3 standalone prediction models |
| H3 hexagonal grid spatial visualization (deck.gl) | React + Recharts dashboard |
| GDELT BigQuery 4-stage filter → agent router | Google News RSS + GDELT DOC API |
| Discrete event simulation with tick loop | No simulation loop; synchronous cascade calls |
| WebSocket real-time cell updates | REST API only |
| Invite-code + admin auth | No auth |

The prediction market integration (Kalshi/Polymarket, paper trading, signal ledger, scorecard) is not in the Phase 1 spec at all — it appears to be Phase 2+ functionality built ahead of the simulation layer. This is a product decision, not a bug, but it creates a large spec/plan divergence.

### [MEDIUM] `pyproject.toml` dependency gaps vs spec requirements

`requires-python = ">=3.11"` (spec says 3.12). Not a runtime risk since `str | None` union syntax works from 3.10, but misaligns with spec.

Missing dependencies from spec that would be needed for the unimplemented layers:
- `h3>=4.1` — required for spatial module and H3 hexagonal grids
- `sentence-transformers>=3.4` — required for semantic dedup (`ingestion/dedup.py` referenced in spec but not implemented)
- `searoute>=1.3` — required for shipping route visualization
- `shapely>=2.0` — required for geometric operations
- `google-cloud-bigquery>=3.27` — required for GDELT BigQuery integration

`truthbrush>=0.2` is present in pyproject.toml and code (`ingestion/truth_social.py`) but was not in the original spec.

### [MEDIUM] Test coverage gaps for unimplemented components

Tests from the plan that have no corresponding implementation:
- `test_circuit_breaker.py` — no `simulation/circuit_breaker.py`
- `test_engine.py` — no `simulation/engine.py`
- `test_h3_utils.py` — no `spatial/h3_utils.py`
- `test_gdelt_filter.py` — no BigQuery GDELT pipeline
- `test_dedup.py` — no `ingestion/dedup.py`
- `test_agent_schemas.py`, `test_agent_router.py`, `test_agent_runner.py` — no agents/ module
- `test_auth.py` — no auth middleware
- `test_prompt_versioning.py` — no eval/prompt_versioning.py
- `test_integration.py` — no end-to-end simulation test

44 tests exist and cover the implemented prediction market functionality well.

### [LOW] `ensemble.py` hardcodes `"opus"` model name in budget tracking

`prediction/ensemble.py:129` calls `budget.record(..., "opus")` regardless of which model is passed as the `model` parameter. If a non-Opus model is used, the cost calculation will use Opus pricing, over-counting spend.

### [LOW] Frontend is a stub relative to spec

`frontend/package.json` has only `react`, `react-dom`, and `recharts`. The spec requires `deck.gl`, `MapLibre GL`, `react-map-gl`, and `h3-js` for the H3 hexagonal visualization layer. The 3-panel layout with live indicators, agent feed, timeline scrubber, and H3 hex map is not built.

### [LOW] No WebSocket handler implemented

The spec dedicates Section 5 to WebSocket real-time updates with message batching and mutable `useRef` for H3 data to avoid render thrashing. No WebSocket endpoint exists in `main.py` or the frontend.

---

## Recommendations

1. **Fix single-writer violations immediately** — The safest short-term fix is to document that the current single-process CLI usage is safe (one coroutine writes at a time), but add a `# NOTE: bypasses DbWriter` comment to each site and a tracking issue. The `DbWriter` is only needed when multiple asyncio tasks write concurrently (e.g., background ingestion + API request handlers). For now, enforce the constraint in FastAPI by ensuring only one write path is active at a time, or migrate the top write-heavy modules (`ledger.py`, `prediction_log.py`, `tracker.py`) to use `DbWriter`.

2. **Reconcile spec with actual product direction** — Update `docs/superpowers/specs/` to reflect the prediction-market-edge-finder architecture. The current spec is misleading about what's being built. The plan's Tasks 11–15 (agents) and Tasks 7–8 (DES engine) should be moved to a Phase 2 doc unless the agent swarm is still on the roadmap.

3. **Implement circuit breaker** — Even without the full DES engine, the `CircuitBreaker` is useful for rate-limiting LLM calls in the prediction models. It's a small, self-contained module per the plan.

4. **Add `h3`, `sentence-transformers`, `searoute`, `shapely` to pyproject.toml** if the spatial + dedup layers are still planned, or explicitly remove them from the spec.

5. **Fix ensemble model name in budget tracking** — Pass the actual model string to `budget.record()` in `ensemble.py:129` instead of the hardcoded `"opus"`.
