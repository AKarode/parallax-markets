# Parallax Health Check — 2026-08-12

**Status: YELLOW**

## Summary

The project has undergone a deliberate, well-executed pivot from the original Phase 1 design (geopolitical swarm simulator with 50 LLM agents and H3 spatial visualization) to its current form: a prediction market edge-finder comparing 3 focused LLM models against Kalshi/Polymarket prices. The live codebase is in working condition with 53 test files (~8,700 lines) covering core flows. The main concerns are a systemic single-writer constraint violation, one missing runtime dependency, and a permanently-orphaned database writer queue that provides no protection against concurrent-write errors.

---

## Issues Found

### [HIGH] DuckDB single-writer topology violated — DbWriter queue unused

**Affected files (12+):** `scoring/ledger.py`, `scoring/tracker.py`, `scoring/prediction_log.py`, `scoring/resolution.py`, `scoring/scorecard.py`, `budget/tracker.py`, `ops/alerts.py`, `ingestion/crisis_ingester.py`, `cli/brief.py`, `contracts/registry.py`, `backtest/runner.py`, `db/schema.py`

The spec mandates that all DuckDB writes go through a single `asyncio.Queue` → `DbWriter` consumer. `db/writer.py` implements this correctly but is completely unwired — no module uses it. Every write in the codebase calls `conn.execute()` directly on whatever connection the module received.

In the current single-process asyncio architecture this is functionally safe (DuckDB serializes within one connection, asyncio is single-threaded). However:
- If the FastAPI server (`uvicorn main:app`) and the CLI brief (`python -m parallax.cli.brief`) run concurrently — as they might under cron scheduling — they open **separate** DuckDB connections to the same file and will produce `database is locked` errors.
- The `DuckDBAlertSink` and `BudgetTracker` both write to the DB from within `async def` callbacks, meaning any concurrent await points between writes can interleave in unexpected order.

**Recommendation:** Wire `DbWriter` into the `lifespan` context and have `brief.py`/`scoring`/`ops` receive the writer via dependency injection rather than a raw connection. Alternatively, document a hard constraint that CLI runs and API server must never overlap and enforce with a file lock.

---

### [HIGH] Missing `cryptography` dependency

**File:** `backend/src/parallax/markets/kalshi.py`

`KalshiClient` uses RSA-PSS signing (`from cryptography.hazmat.primitives...`) to authenticate every Kalshi API request. The `cryptography` package is **not listed** in `backend/pyproject.toml`. It works in environments where `cryptography` is already installed (e.g., as a transitive dep of another installed package), but a clean `pip install -e .` will silently omit it, causing an `ImportError` at runtime the moment any Kalshi call is made.

**Recommendation:** Add `"cryptography>=41.0"` to `[project.dependencies]` in `pyproject.toml`.

---

### [MEDIUM] Budget tracker daily cap resets on process restart

**File:** `backend/src/parallax/budget/tracker.py`

`BudgetTracker._spend_today` is accumulated in memory from the moment the process starts. On a process restart, it resets to 0.0 regardless of how many LLM calls were already made that calendar day. The `llm_usage` table records every call persistently, but the `is_over_budget()` check never queries it — it only consults the in-memory counter.

**Consequence:** Multiple brief runs across restarts could collectively exceed the $20/day cap without the circuit breaker triggering. On a cold start, `is_over_budget()` always returns `False` until new spend accumulates in the current process.

**Recommendation:** In `__init__`, query `llm_usage` for today's total cost and seed `_spend_today` from that value:
```python
if db_conn is not None:
    row = db_conn.execute(
        "SELECT COALESCE(SUM(cost_usd), 0.0) FROM llm_usage WHERE DATE(created_at) = CURRENT_DATE"
    ).fetchone()
    self._spend_today = float(row[0]) if row else 0.0
```

---

### [MEDIUM] Agent swarm absent — 3 schema tables permanently orphaned

**Missing package:** `backend/src/parallax/agents/` (entire directory)

The schema creates `agent_memory`, `agent_prompts`, and `decisions` tables, but no code anywhere writes to them. The original plan's `agents/registry.py`, `agents/runner.py`, `agents/router.py`, and `agents/schemas.py` were never implemented. The cascade engine and world state are correctly implemented but exist without the agent layer that was intended to drive them during live simulation.

This is consistent with the intentional project pivot (prediction market edge-finder does not need an agent swarm), but the orphaned tables add schema noise and the `circuit_breaker.py` module referenced throughout the plan was also never implemented.

**Recommendation:** Either implement the agent swarm per the original spec or add a migration that drops the three orphaned tables and updates the schema comment to reflect the current product direction. Remove `simulation/circuit_breaker.py` from any remaining references.

---

### [MEDIUM] `simulation/circuit_breaker.py` missing

The implementation plan specifies `circuit_breaker.py` as a simulation module, and the plan's test suite included `test_circuit_breaker.py`. Neither the module nor its test was ever created. The cascade engine operates without escalation rate limiting or cooldowns.

**Recommendation:** Implement if agent-driven simulation is added in a future phase. If the pivot is permanent, remove references to the circuit breaker from planning docs.

---

### [LOW] `requires-python` mismatch

`pyproject.toml` specifies `requires-python = ">=3.11"` but the design spec and plan both target Python 3.12 (for `str | None` union syntax, which actually works in 3.10+). The code uses `from __future__ import annotations` throughout, so this is safe in practice.

**Recommendation:** Update to `>=3.12` to match the stated target environment, or leave at `>=3.11` if intentional.

---

### [LOW] Architecture drift from spec — noted, not blocking

The spec describes a geopolitical swarm simulator (H3 hex map, 50 agents, GDELT BigQuery, deck.gl, MapLibre). The CLAUDE.md correctly describes the current implementation: a prediction market edge-finder with 3 LLM models, Kalshi/Polymarket integration, and a polling React dashboard. The following spec components are absent by design:

- `agents/` package (swarm of 50 agents)
- `spatial/` package (H3 utilities, Overture Maps loader, searoute)
- `api/websocket.py` (WebSocket push; replaced by REST polling)
- `api/auth.py` (invite codes; not implemented)
- `eval/` package (prompt versioning, A/B comparison, prompt improvement pipeline)
- `ingestion/gdelt.py` (BigQuery GDELT; replaced by `gdelt_doc.py` using free DOC API)
- `ingestion/dedup.py` (semantic dedup via sentence-transformers; not implemented)
- Dependencies: `h3`, `searoute`, `shapely`, `sentence-transformers`, `google-cloud-bigquery`, `websockets`

This drift is intentional and well-documented. The current product is more focused and closer to operational than the original spec would have been at this stage.

---

### [LOW] No missing tests for current (pivoted) architecture

The 53 test files cover all current modules at reasonable depth, including integration tests (`test_phase1_critical.py`, `test_staleness_integration.py`) and resilience tests (`test_brief_resilience.py`, `test_cold_start_floors.py`). Tests for the spec's un-implemented modules (`test_circuit_breaker.py`, `test_dedup.py`, `test_agent_runner.py`, `test_auth.py`) are absent — but those modules themselves are absent, so this is consistent.

---

## Recommendations (Priority Order)

1. **[P1] Add `cryptography` to `pyproject.toml` dependencies** — prevents silent `ImportError` on clean install.
2. **[P1] Add a process-level advisory lock or documented constraint** against running `uvicorn` and `python -m parallax.cli.brief` concurrently, OR wire up `DbWriter` for the modules that write from async contexts (`DuckDBAlertSink`, `BudgetTracker.record`).
3. **[P2] Fix `BudgetTracker` cold-start bug** — seed `_spend_today` from `llm_usage` on init.
4. **[P3] Clean up or implement the orphaned agent tables** — remove or migrate `agent_memory`, `agent_prompts`, `decisions` from the schema if the swarm will not be built.
5. **[P4] Update `requires-python`** to `>=3.12` to match intended deployment environment.
