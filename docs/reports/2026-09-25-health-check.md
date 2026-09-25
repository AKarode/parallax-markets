# Parallax Health Check — 2026-09-25

**Status: YELLOW**

## Summary

The codebase has intentionally pivoted from the Phase 1 spec (geopolitical cascade simulator with ~50 LLM agents and H3 maps) to a prediction market edge-finder for Kalshi/Polymarket. The evolved product is functionally operational with 44 test files covering the new architecture. However, the DuckDB single-writer constraint — the most critical architectural rule in the spec — is violated across 5 modules, creating a latent concurrency bug.

---

## Issues Found

### [HIGH] DuckDB single-writer pattern violated in 5 modules

The spec mandates all writes route through `DbWriter`'s `asyncio.Queue`. None of the live write paths use it:

- `scoring/ledger.py` — `SignalLedger.record_signal()` and `update_execution()` call `conn.execute(INSERT/UPDATE)` directly
- `scoring/prediction_log.py` — `PredictionLogger.log_prediction()` calls `conn.execute(INSERT)` directly
- `budget/tracker.py` — `BudgetTracker.record()` calls `conn.execute(INSERT INTO llm_usage)` directly
- `ingestion/crisis_ingester.py` — `CrisisIngester.ingest_events()` calls `conn.execute(INSERT INTO crisis_events)` directly
- `cli/brief.py` — Run tracking (`INSERT INTO runs`, `UPDATE runs`, `INSERT INTO market_prices`) bypasses the queue

`DbWriter` is implemented correctly but is effectively dead code. While the current CLI flow is sequential so crashes are unlikely today, adding any concurrency (background ingestion, parallel API requests) will trigger `database is locked` errors.

### [HIGH] Entire agent swarm never implemented

The spec's core — the `agents/` package (~12 country agents, ~50 sub-actors, router, runner, prompts/) — does not exist. This is the intended Phase 1 simulation engine. The implemented prediction models (`prediction/oil_price.py`, `prediction/ceasefire.py`, `prediction/hormuz.py`) are 3 direct Claude calls, not an agent swarm.

### [MEDIUM] Spatial layer absent

`spatial/` directory (H3 utilities, `ResolutionBand`, route-to-cell chain generation) was never built. The frontend has no H3 hex map — it uses a KPI/table dashboard instead. The spec's 4-band H3 resolution strategy and shipping lane visualization are not implemented.

### [MEDIUM] Eval framework absent

`eval/` package (structured predictions, direction/magnitude/sequence/calibration scoring, prompt versioning, improvement pipeline) does not exist. The `scoring/` module covers calibration metrics but does not implement the spec's causal attribution, prompt versioning (semver), or A/B comparison pipeline.

### [MEDIUM] Key spec dependencies missing from pyproject.toml

Missing vs spec:
- `h3>=4.1` (spatial layer)
- `searoute>=1.3` (shipping route visualization)
- `shapely>=2.0` (geometric operations)
- `sentence-transformers>=3.4` (semantic GDELT dedup)
- `google-cloud-bigquery>=3.27` (GDELT BigQuery source)
- `websockets>=14.0` (real-time WebSocket to frontend)

Added beyond spec (appropriate for the evolved product):
- `truthbrush>=0.2` (Truth Social POTUS feed)
- `numpy`, `pandas`, `pyarrow`, `scikit-learn`, `matplotlib` (bench extras)

### [MEDIUM] simulation/circuit_breaker.py not implemented

The cascade circuit breaker (max 1 escalation level/tick, 3-tick cooldown, exogenous shock override) specified in Section 4 and planned in Task 7 was never built. `simulation/engine.py` (DES core with heapq priority queue and clock modes) also absent.

### [LOW] Frontend is a different product

Spec calls for 3-column dark dashboard: hex map (center), agent feed (left), live indicators (right), timeline bar (bottom), WebSocket streaming. Actual frontend: KPI cards, markets table, model health cards, portfolio panel, price chart, polling-based (`usePolling.ts`). No WebSocket, no hex map, no agent feed.

### [LOW] Test coverage gaps vs plan

Plan specifies 18 test files. Present and matching: `test_schema.py`, `test_cascade.py`, `test_config.py`, `test_gdelt_doc.py` (partial), `test_prediction.py`. Missing from plan: `test_writer.py`, `test_h3_utils.py`, `test_dedup.py`, `test_world_state.py`, `test_circuit_breaker.py`, `test_agent_schemas.py`, `test_agent_router.py`, `test_agent_runner.py`, `test_prompt_versioning.py`, `test_auth.py`, `test_budget_tracker.py`, `test_integration.py`. The 44 test files that exist cover the evolved prediction market product adequately.

### [LOW] LLM pricing constants may be stale

`budget/tracker.py` hard-codes Haiku input at $0.001/1K and Sonnet at $0.003/1K. These figures roughly match Haiku 3 and Sonnet 3 vintage pricing; Claude 4.x/5.x models have different rates. Verify against current Anthropic pricing before relying on budget cap enforcement.

---

## Recommendations

1. **Immediate: Fix DuckDB write paths** — Route all five direct `conn.execute(INSERT/UPDATE)` callers through `DbWriter.enqueue()`. This is a one-line change per call site and prevents any future concurrency bugs. The `DbWriter` infrastructure is already correct; it just needs to be wired in.

2. **Decide on spec fidelity** — The Phase 1 spec and the implemented product are now two different things. Consider either (a) updating the spec to match the prediction market pivot, or (b) treating the agent swarm as Phase 2. The current CLAUDE.md accurately describes the implemented product; the spec does not.

3. **Update pyproject.toml** — Remove unused spec deps (h3, searoute, shapely, sentence-transformers, google-cloud-bigquery) or add them if the agent swarm is still planned. Prevents confusion about what the project actually needs.

4. **Add `test_writer.py`** — The single-writer pattern is the most critical architectural constraint. It has no tests. Add them so any future regression is caught.

5. **Refresh LLM pricing** — Update `_PRICING` dict in `budget/tracker.py` to current Haiku 4.5 and Sonnet 4.6 rates so the $20/day cap enforces correctly.
