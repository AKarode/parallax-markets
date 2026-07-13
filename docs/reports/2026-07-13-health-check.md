# Parallax Repo Health Check — 2026-07-13

**Status: YELLOW**

The codebase is functional for its current product direction (prediction market edge-finder) but has diverged substantially from the Phase 1 design spec. The most actionable concern is a systematic violation of the DuckDB single-writer pattern that the spec marks as a hard constraint.

---

## Summary

The repo has undergone an intentional product pivot from the original spec (50-agent geopolitical cascade simulator + H3 spatial visualization) to a focused prediction market edge-finder that compares Claude-driven predictions against Kalshi/Polymarket prices. Core simulation infrastructure (`agents/`, `api/`, `eval/`, `spatial/` packages; `simulation/engine.py`; `simulation/circuit_breaker.py`) was never built. The evolved codebase is coherent for the new direction and has solid test coverage (47 tests vs 18 planned), but `db/writer.py` — the spec's single-writer queue — is implemented but not wired into any production path: 12 files write directly to DuckDB.

---

## Issues Found

### [HIGH] DuckDB Single-Writer Pattern Violated Across the Codebase

The spec declares the asyncio.Queue single-writer pattern a **hard constraint** to prevent `database is locked` errors. `db/writer.py` implements the correct `DbWriter` class, but no production code uses it. The following files call `conn.execute(INSERT/UPDATE/DELETE)` directly:

| File | Operations |
|------|-----------|
| `scoring/ledger.py` | INSERT + UPDATE signal_ledger |
| `scoring/tracker.py` | INSERT/UPDATE trade_orders, trade_fills, trade_positions |
| `scoring/resolution.py` | UPDATE signal_ledger, UPDATE trade_positions |
| `scoring/prediction_log.py` | INSERT prediction_log |
| `scoring/scorecard.py` | INSERT daily_scorecard |
| `contracts/registry.py` | INSERT OR REPLACE + DELETE + UPDATE contract_registry / contract_proxy_map |
| `ingestion/crisis_ingester.py` | INSERT crisis_events |
| `ops/alerts.py` | INSERT ops_events |
| `backtest/runner.py` | INSERT/UPDATE backtest_runs, backtest_predictions |
| `cli/brief.py` | INSERT runs, UPDATE runs, INSERT market_prices |
| `budget/tracker.py` | INSERT llm_usage |
| `db/schema.py` | UPDATE signal_ledger (migration backfills — intentional) |

In practice the app is single-process asyncio, so concurrent writes from separate threads aren't the immediate risk. The risk is any two coroutines calling `conn.execute()` concurrently without yielding — DuckDB's in-process write lock is still held per-statement. The `db/writer.py` queue is the intended fix and is not used.

### [HIGH] Core Simulation Infrastructure Not Built

The following planned modules do not exist, meaning the spec's DES simulation loop, agent swarm, and cascade circuit breaker are absent:

- `simulation/engine.py` — DES tick loop (heapq priority queue)
- `simulation/circuit_breaker.py` — escalation limits and cooldowns
- `agents/` package — runner, router, country agent, prompts, registry
- `eval/` package — prediction scoring, ground truth fetching, prompt versioning
- `api/websocket.py` — real-time WebSocket push to frontend
- `api/auth.py` — invite code + admin password middleware
- `spatial/` package — H3 utilities, Overture/Searoute loader

These are absent by design (product pivot), but the design spec tests (`test_engine.py`, `test_circuit_breaker.py`, `test_agent_router.py`, `test_agent_runner.py`, `test_dedup.py`, `test_h3_utils.py`, `test_auth.py`) are also missing, so no safety net exists if any of these are revisited.

### [MEDIUM] Missing Dependencies for Planned Features

`pyproject.toml` is missing packages that the spec requires for dedup and spatial work. If any of these features are revisited, installation will fail silently at import time:

- `h3>=4.1` — H3 spatial indexing (used by `simulation/world_state.py` indirectly)
- `sentence-transformers>=3.4` — semantic dedup (GDELT stage 3)
- `searoute>=1.3` — shipping route visualization
- `shapely>=2.0` — geometric operations
- `google-cloud-bigquery>=3.27` — GDELT BigQuery source

`requires-python` is `>=3.11` but the spec and CLAUDE.md say `>=3.12`. Minor inconsistency.

### [MEDIUM] Frontend Architecture Gap

The spec calls for a deck.gl + MapLibre H3 hex map with WebSocket-driven real-time updates and four H3HexagonLayer instances. The actual frontend is a polling-based React dashboard with REST API calls, KPI cards, sparklines, and a markets table — no map, no WebSocket. The frontend components (`HexMap.tsx`, `AgentFeed.tsx`, `Timeline.tsx`, `PredictionCards.tsx`, `HexPopover.tsx`) from the plan don't exist. The actual component set (`KpiBar.tsx`, `MarketsTable.tsx`, `ModelCards.tsx`, `PortfolioPanel.tsx`, etc.) is appropriate for the new product direction.

### [LOW] `ingestion/gdelt.py` Replaced but Renamed

The plan specified `ingestion/gdelt.py` (BigQuery + 4-stage filter) and `ingestion/dedup.py` (semantic dedup). The actual file is `ingestion/gdelt_doc.py` (GDELT DOC 2.0 HTTP API, not BigQuery). The BigQuery dependency and the semantic dedup stage (sentence-transformers similarity) are gone. The DOC API is a practical improvement (no BigQuery credentials needed), but the named-entity override and semantic dedup stages from the spec are absent.

### [LOW] `db/schema.py` Has 26 Tables vs 10 Planned

The spec defined 10 tables. The actual schema has 26 tables plus 2 views. The extras (`market_prices`, `contract_registry`, `signal_ledger`, `trade_orders`, `trade_fills`, `paper_trades`, `daily_scorecard`, `llm_usage`, `crisis_events`, `backtest_runs`, etc.) are all appropriate for the evolved product — this is growth, not bloat. No issues here.

---

## Recommendations

1. **[Immediate]** Wire `db/writer.py` into the hot-path write callers or document that the single-writer constraint is intentionally relaxed for the new architecture. The current state is misleading — `DbWriter` exists but does nothing in production. Either remove it or use it.

2. **[Short-term]** For any new write site added to the codebase, route through `DbWriter.enqueue()`. This is low-friction since the class already exists and the queue pattern prevents any future concurrency footguns.

3. **[Short-term]** Pin `requires-python = ">=3.12"` in pyproject.toml to match CLAUDE.md and the codebase's use of 3.12+ syntax (`str | None` unions, `dict[str, Any]` generics).

4. **[Optional]** If the simulation/agent-swarm path is ever revisited, add the missing `h3`, `sentence-transformers`, `searoute`, `shapely` deps to pyproject.toml before any imports land — a missing dep in a test fixture fails silently until CI is set up.

5. **[Informational]** Update the design spec (`docs/superpowers/specs/2026-03-30-parallax-phase1-design.md`) or add a successor spec to document the current product architecture. The spec describes a product that no longer matches the implementation, which will confuse future contributors and automated health checks.
