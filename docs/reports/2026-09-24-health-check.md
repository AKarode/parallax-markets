# Parallax Health Check — 2026-09-24

**Status: YELLOW**

## Summary

The project has undergone a deliberate architectural pivot from the Phase 1 design spec (geopolitical simulator with ~50 LLM agents and H3 spatial visualization) to a focused prediction market edge-finder targeting Kalshi/Polymarket divergences. This pivot is well-executed and documented in CLAUDE.md, but it means roughly half of the spec's planned modules were never built. Within its current scope the codebase is functional, has solid test coverage (47 tests across all present modules), and is actively used for paper trading. The main technical debt is a widespread pattern of direct DuckDB writes that bypass the single-writer queue, violating the architecture's core safety constraint.

---

## Issues Found

### HIGH — DuckDB single-writer violations
**At least 10 source files write directly to DuckDB without going through `DbWriter`.** These bypass the asyncio.Queue serialization guarantee and can cause `database is locked` errors under concurrent execution.

- `scoring/ledger.py` — INSERT + UPDATE on `signal_ledger`
- `scoring/tracker.py` — INSERT + UPDATE on `trade_positions`
- `scoring/prediction_log.py` — INSERT on `prediction_log`
- `scoring/resolution.py` — UPDATE on `signal_ledger`, `trade_positions`
- `contracts/registry.py` — INSERT OR REPLACE, DELETE, UPDATE on `contract_registry` / `contract_proxy_map`
- `cli/brief.py` — INSERT on `runs`, `market_prices`; UPDATE on `runs`
- `budget/tracker.py` — INSERT on `llm_usage`
- `ingestion/crisis_ingester.py` — INSERT on `crisis_events`
- `ops/alerts.py` — INSERT on `ops_events`
- `backtest/runner.py` — INSERT + UPDATE on `backtest_runs`, `backtest_predictions`

Currently safe only because the CLI runs in a single-process, single-task flow. If any two tasks ever run concurrently (e.g., `brief.py` + a background scorecard), this will corrupt the database.

### MEDIUM — Python version mismatch
`pyproject.toml` declares `requires-python = ">=3.11"` but CLAUDE.md documents the runtime as Python 3.12. This allows inadvertent installs on 3.11 where some 3.12 syntax features may break. Should be pinned to `>=3.12`.

### MEDIUM — Architectural pivot: major spec modules never built
The original Phase 1 plan specified these packages; none have been implemented in any form:

| Missing Module | Spec Purpose |
|---|---|
| `agents/` | ~50 LLM agents (country → sub-actor hierarchy), runner, router, country_agent, prompts |
| `api/` | Separate routes, WebSocket handler, invite-code auth middleware |
| `eval/` | Prediction scoring, prompt versioning, A/B comparison, improvement pipeline |
| `spatial/` | H3 spatial utilities, Overture/Searoute loader |
| `ingestion/dedup.py` | Semantic dedup via sentence-transformers |

The project CLAUDE.md explicitly documents a different architecture (3 prediction models, Kalshi paper trading, divergence detection) — this is an intentional pivot, not drift. Flagged as MEDIUM only because the spec and plan docs remain unrevised and will mislead future contributors.

### MEDIUM — Simulation engine incomplete
`simulation/` exists with `cascade.py`, `config.py`, `world_state.py` but is missing `engine.py` (the DES core with heapq event queue and clock modes) and `circuit_breaker.py`. The cascade and world-state modules are used by prediction models today, but the full simulation engine from the spec was never wired up.

### LOW — Frontend: no WebSocket or H3 map
The React frontend uses HTTP polling (`usePolling.ts`) against REST endpoints only. No WebSocket, no deck.gl, no H3HexagonLayer. The frontend is functional as a prediction market dashboard but does not match the spec's real-time map-driven design. The UI dependencies `h3-js`, `deck.gl`, and `react-map-gl` are absent from `package.json`.

### LOW — Missing spatial dependencies
`h3`, `websockets`, `sentence-transformers`, `searoute`, `shapely`, and `google-cloud-bigquery` are specified in the plan's `pyproject.toml` but absent from the actual one. This is consistent with the pivot but leaves the spec's `pyproject.toml` stale.

### LOW — Test gaps for circuit_breaker and engine
`backend/tests/test_circuit_breaker.py` and `test_engine.py` are listed as plan deliverables; neither exists (the source modules are also absent). All other present modules have corresponding tests.

---

## Recommendations

1. **Fix DuckDB writer violations (HIGH — do now).** Route all writes through `DbWriter.enqueue()`. The `cli/brief.py` path runs synchronously today, masking the risk; any move toward background tasks or concurrent runs will expose it. Priority order: `scoring/ledger.py`, `scoring/tracker.py`, `cli/brief.py`, then the rest.

2. **Update the spec and plan docs to reflect the pivot.** Add a "Phase 1 Actual" section to `docs/superpowers/specs/2026-03-30-parallax-phase1-design.md` documenting what was built. The current docs describing 50-agent swarms and H3 maps will confuse any new contributor.

3. **Pin Python to `>=3.12` in pyproject.toml.** One-line fix.

4. **Decide the fate of the simulation engine.** If the prediction-market path is the product, the Phase 1 DES engine is out of scope — remove `simulation/` or mark it clearly as aspirational. If the cascade simulator is still planned, build `engine.py` and `circuit_breaker.py` next.

5. **Add a DuckDB write audit to CI.** A grep-based test that fails if any file outside `db/writer.py` and `db/schema.py` contains `conn.execute` with DML keywords would prevent future regressions.
