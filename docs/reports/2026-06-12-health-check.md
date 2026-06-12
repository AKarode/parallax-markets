# Parallax Health Check — 2026-06-12

**Status: YELLOW**

## Summary

The project has successfully pivoted from the original Phase 1 geospatial agent-swarm spec to a focused prediction-market edge-finder, and the implementation within that new scope is solid (416/433 tests passing, 96%). One critical blocking issue was found: `pytz` is not declared as a dependency but is required by DuckDB 1.5.x for TIMESTAMPTZ operations, causing 17 test failures across the scorecard, ops alerting, LLM usage, and crisis context modules. Additionally, the single-writer DuckDB pattern mandated by the spec is violated in 10+ production modules, creating latent `database is locked` risk under concurrent load.

---

## Issues Found

### CRITICAL

- **[CRITICAL] `pytz` missing from `pyproject.toml`**
  DuckDB 1.5.x requires `pytz` for `DATE()` / `TIMESTAMPTZ` comparison operations. The package is not listed as a dependency. This causes `InvalidInputException: Required module 'pytz' failed to import` in `scoring/scorecard.py:328`, `scoring/ledger.py`, `ops/alerts.py`, `budget/tracker.py`, and `prediction/crisis_context.py`. **17 tests fail** as a result: all `test_scorecard.py`, `test_llm_usage.py`, `test_ops_events.py`, and `test_phase1_critical.py::TestPredictorPassesContextAge`. Production `--scorecard` runs and dashboard queries will silently error.
  - **Fix**: Add `pytz>=2024.1` to `dependencies` in `backend/pyproject.toml`.

---

### HIGH

- **[HIGH] Single-writer pattern violated in 10+ modules**
  The spec (`docs/superpowers/specs/2026-03-30-parallax-phase1-design.md`, §9) explicitly requires all writes to flow through the `asyncio.Queue` in `db/writer.py`. Instead, these modules call `.execute(INSERT/UPDATE/DELETE ...)` directly on a raw `duckdb.DuckDBPyConnection`:
  - `ops/alerts.py` (`DuckDBAlertSink.record`)
  - `budget/tracker.py` (`BudgetTracker.record`)
  - `scoring/ledger.py` (`SignalLedger.append`, `SignalLedger.update_outcome`)
  - `scoring/tracker.py` (`PaperTradeTracker` — multiple write methods across ~900 lines)
  - `scoring/resolution.py` (two `UPDATE signal_ledger` / `UPDATE trade_positions` calls)
  - `scoring/prediction_log.py` (`PredictionLogger.log`)
  - `scoring/scorecard.py` (`compute_daily_scorecard` upsert)
  - `ingestion/crisis_ingester.py` (`CrisisIngester.ingest_batch`)
  - `contracts/registry.py` (`ContractRegistry.upsert`, `update_mappings`)
  - `cli/brief.py` (run lifecycle inserts: `runs`, `market_prices`)
  - `backtest/runner.py` (lower risk — isolated batch runner, not part of async event loop)

  In practice, the CLI pipeline is sequential and tests use in-memory DBs, so collisions haven't materialized yet. But any path that runs two of these concurrently (e.g., `main.py` background tasks + a live API request both triggering writes) risks `database is locked`. The `DbWriter` class exists and is correctly implemented but is simply not wired to these modules.

---

### MEDIUM

- **[MEDIUM] Architectural drift: agents/, eval/, spatial/, api/ modules never built**
  The original Phase 1 plan specifies six top-level backend modules that don't exist: `agents/` (50-agent LLM swarm), `eval/` (prompt versioning, scoring, improvement pipeline), `spatial/` (H3 utilities, searoute loader), and `api/` (auth, WebSocket handler). The project pivoted to a prediction-market edge-finder, and `CLAUDE.md` reflects the actual architecture accurately. The drift is intentional and documented — flagging it only because the original spec/plan documents still describe the old design.

- **[MEDIUM] `simulation/circuit_breaker.py` not implemented**
  The spec (§4) and `CLAUDE.md` conventions both reference `circuit_breaker.py` as a named module, and the cascade spec describes the exogenous-shock override logic in detail. Only three files exist in `simulation/`: `cascade.py`, `config.py`, `world_state.py`. The circuit-breaker logic is not implemented anywhere. The test plan (`test_circuit_breaker.py`) is also missing.

- **[MEDIUM] `ingestion/dedup.py` not implemented**
  The spec (§6) and plan (Task 10) call for a `SemanticDeduplicator` using `sentence-transformers` / `all-MiniLM-L6-v2`. Neither the module nor its test (`test_dedup.py`) exist. Deduplication is currently absent from the ingestion pipeline — Google News and GDELT DOC may surface duplicate events to the prediction models.

- **[MEDIUM] `pyproject.toml` missing 6 spec-required dependencies**
  `h3`, `sentence-transformers`, `searoute`, `shapely`, `google-cloud-bigquery`, and `websockets` are listed in the Phase 1 spec and plan but absent from `pyproject.toml` — because those features were never built. The project pivoted. Low operational risk today, but the gap signals how much of the original spec is unimplemented.

- **[MEDIUM] Frontend divergence from plan**
  The plan's deck.gl / MapLibre geospatial visualization (HexMap, AgentFeed, LiveIndicators, Timeline, PredictionCards, HexPopover) was never built. The actual frontend is a prediction-market dashboard (ContractDetail, KpiBar, MarketsTable, ModelCards, PortfolioPanel, PriceChart). No `types/index.ts` or the plan's `useHexData.ts` hook exists; only `usePolling.ts` is present. Again, intentional pivot — documented for completeness.

---

### LOW

- **[LOW] 13 plan-expected test files missing**
  The original plan specifies 17 test files. Only 4 of those were created with the original names (`test_schema.py`, `test_writer.py`, `test_world_state.py`, `test_config.py`). Missing: `test_h3_utils`, `test_gdelt_filter`, `test_dedup`, `test_circuit_breaker`, `test_agent_schemas`, `test_agent_router`, `test_agent_runner`, `test_scoring` (generic), `test_predictions`, `test_prompt_versioning`, `test_auth`, `test_budget_tracker` (standalone), `test_integration` (generic), `test_engine`. Replacement tests exist for the new pivot scope (45 total), so overall coverage is good — but features explicitly in the plan have no tests.

- **[LOW] `pyproject.toml` `requires-python = ">=3.11"` vs spec's 3.12**
  The spec and `CLAUDE.md` specify Python 3.12. The package allows 3.11+. No 3.11-incompatible syntax found in source, but the gap could mask subtle 3.12-only behavior.

- **[LOW] `test_crisis_context_db.py` — 4 test failures unrelated to `pytz` root cause**
  `TestRenderFromDB::test_renders_from_db_when_events_exist` and related tests assert that DB-sourced crisis events appear in prediction context strings. The assertion fails because `render_crisis_context_from_db` catches the `pytz` exception and falls back to the seed context, so the DB path is never exercised. These will auto-fix once `pytz` is added.

- **[LOW] No linter or formatter configured**
  No `.ruff.toml`, `.black`, `.flake8`, or `pyproject.toml [tool.ruff]` section. Style consistency is maintained by convention but not enforced in CI.

---

## Test Suite Summary

```
Total: 433 tests
Passing: 416 (96%)
Failing: 17 (all caused by missing pytz dependency)
Skipped: 13

Root cause of all 17 failures: ModuleNotFoundError: No module named 'pytz'
Affected: test_scorecard (10), test_crisis_context_db (4), test_llm_usage (1),
          test_ops_events (1), test_phase1_critical (1)
```

---

## Recommendations

1. **Immediate**: Add `pytz>=2024.1` to `dependencies` in `backend/pyproject.toml`. Run `pip install -e ".[dev]"` to verify all 17 failures resolve.

2. **Short-term**: Audit single-writer violations. For modules inside the FastAPI async event loop (`ops/alerts.py`, `budget/tracker.py`, `scoring/ledger.py`, `scoring/prediction_log.py`, `ingestion/crisis_ingester.py`, `contracts/registry.py`), pass `DbWriter` at construction time and use `await writer.enqueue(...)` instead of direct `.execute()`. Modules called only from the synchronous CLI pipeline (`cli/brief.py`, `scoring/scorecard.py`) are lower priority but should be consistent.

3. **Medium-term**: Implement `simulation/circuit_breaker.py` per the spec's design (max 1 escalation/tick, 3-tick cooldown, exogenous-shock Goldstein-scale override). Add `test_circuit_breaker.py`. The cascade engine already imports `ScenarioConfig` which carries all the needed parameters.

4. **Medium-term**: Implement `ingestion/dedup.py` (`SemanticDeduplicator` with `all-MiniLM-L6-v2`). Add `sentence-transformers>=3.4` to `pyproject.toml`. Wire it into the Google News and GDELT DOC ingestion paths.

5. **Housekeeping**: Pin lower-bounds on `pyproject.toml` dev deps more tightly (currently `pytest>=8.3,<9` — good; consider pinning `duckdb~=1.5` to avoid future version surprises with timezone behavior). Add `ruff` or `black` as a dev dependency and configure a pre-commit hook.
