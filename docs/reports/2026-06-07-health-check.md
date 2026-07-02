# Parallax Health Check — 2026-06-07

**Status: YELLOW**

The codebase is functional and covers the core prediction-market use case, but diverges substantially from the Phase 1 design spec (deliberate product pivot), contains widespread single-writer DuckDB violations that could cause `database is locked` crashes under concurrency, and has 6 permanently-skipped tests signalling incomplete refactor work.

---

## Summary

The project pivoted from the original spec (50-agent geopolitical swarm + H3 hex dashboard) to a focused prediction-market edge-finder (3 LLM models + Kalshi/Polymarket comparison + paper trading). CLAUDE.md reflects the current product correctly. The pivot itself is a reasonable product decision; the health risks are in the DB layer and test coverage gaps that followed.

---

## Issues Found

### [HIGH] DuckDB Single-Writer Pattern Violated in 7+ Modules

The spec and plan are explicit: *all mutable writes must go through a single `asyncio.Queue → DbWriter` task.* This is violated in at least 7 files that call `conn.execute()` directly for INSERT/UPDATE operations:

- `scoring/ledger.py` — INSERT into `signal_ledger`, UPDATE `signal_ledger`
- `scoring/resolution.py` — UPDATE `signal_ledger`, UPDATE `trade_positions`
- `scoring/prediction_log.py` — INSERT into `prediction_log`
- `scoring/tracker.py` — INSERT/UPDATE `trade_positions`, `trade_orders`, `trade_fills`
- `ops/alerts.py` — INSERT into `ops_events`
- `backtest/runner.py` — INSERT/UPDATE `backtest_runs`, `backtest_predictions`
- `ingestion/crisis_ingester.py` — INSERT into `crisis_events`

Under concurrent FastAPI request handling or simultaneous background tasks, these direct writes contend with each other and with `DbWriter`, risking `database is locked` errors. DuckDB enforces single-writer at the OS level — concurrent write attempts from multiple asyncio coroutines will fail non-deterministically.

**Recommendation:** Route all of these through `DbWriter.enqueue()`. For synchronous contexts (e.g. CLI), ensure they run in the same event loop as `DbWriter.run()`, or use a dedicated sync connection if the process is not multi-tasking.

---

### [MEDIUM] Significant Architecture Drift from Phase 1 Spec

The spec describes a 50-agent LLM swarm with:
- Country → sub-actor hierarchy (`agents/` module with registry, router, runner, YAML prompts)
- H3 hexagonal spatial visualization (deck.gl + MapLibre + H3HexagonLayer)
- GDELT BigQuery pipeline with 4-stage semantic dedup
- Discrete Event Simulation engine with tick loop
- WebSocket push to frontend

The implementation delivers:
- 3 prediction models (`OilPricePredictor`, `CeasefirePredictor`, `HormuzReopeningPredictor`)
- Polling REST API frontend (Recharts, no deck.gl/MapLibre/H3)
- Google News RSS + GDELT DOC API (not BigQuery)
- No DES engine; no spatial layer; no agent swarm; no WebSocket

This is a **product pivot**, not implementation lag. CLAUDE.md documents the current system correctly. The risk is that the spec-linked plan documents (`docs/superpowers/plans/2026-03-30-parallax-phase1.md`) are now misleading as implementation guidance — any future work spawned from that plan will create dead-end modules.

**Recommendation:** Archive the Phase 1 plan with a pivot note, or create a `docs/superpowers/plans/2026-06-07-parallax-current.md` that reflects the actual architecture.

---

### [MEDIUM] Missing pyproject.toml Dependencies (Spec Requirements)

The following packages are called out in the plan but absent from `pyproject.toml`:

| Package | Spec Requirement | Impact |
|---------|-----------------|--------|
| `h3>=4.1` | H3 spatial indexing | Imported in `simulation/` files; will `ImportError` if used |
| `sentence-transformers>=3.4` | Semantic dedup | Referenced in plan; not needed post-pivot |
| `searoute>=1.3` | Shipping route geometry | Not needed post-pivot |
| `shapely>=2.0` | Geometric operations | Not needed post-pivot |
| `google-cloud-bigquery>=3.27` | GDELT via BigQuery | Not needed post-pivot |
| `websockets>=14.0` | WebSocket push | Not needed post-pivot |

Most omissions are safe (post-pivot). The `h3` package is a latent risk — `simulation/world_state.py` and `simulation/cascade.py` reference H3 cell IDs (`cell_id: BIGINT`) but the library may not be installed, so any future work that imports `h3` directly will fail.

**Recommendation:** Remove unused spec dependencies from consideration; explicitly add `h3>=4.1` to `pyproject.toml` since the DB schema and world state types use H3 cell IDs.

---

### [MEDIUM] Frontend Missing Spec Visualization Stack

The spec requires deck.gl, MapLibre GL, H3-js. The frontend `package.json` has only React + Recharts. The current UI is a polling dashboard, not the interactive hex map.

This is part of the deliberate pivot, but means the "visually compelling live dashboard (interview/demo ready)" goal from the spec is unmet.

**Recommendation:** If the hex-map demo is still a goal (e.g., for fundraising/interviews), this represents a large build gap. If the pivot is permanent, update the project goals doc.

---

### [LOW] 6 Tests Permanently Skipped (Pre-Refactor Marker)

`backend/tests/test_mapping_policy.py` has 6+ tests marked `@pytest.mark.skip(reason=_PRE_REFACTOR_REASON)`. These represent a stale/incomplete refactor of `MappingPolicy`. Skipped tests silently erode coverage without alerting CI.

**Recommendation:** Either complete the refactor and re-enable these tests, or delete them if the old behavior is intentionally removed.

---

### [LOW] Plan Test Files Never Created

The Phase 1 plan specified the following test files, none of which exist:

- `test_h3_utils.py` (no spatial module)
- `test_gdelt_filter.py` (GDELT volume gate — `test_gdelt_doc.py` exists but covers a different module)
- `test_dedup.py` (semantic dedup — no `dedup.py` module)
- `test_circuit_breaker.py` (no `circuit_breaker.py` module)
- `test_engine.py` (no DES engine)
- `test_agent_schemas.py`, `test_agent_router.py`, `test_agent_runner.py` (no agents module)
- `test_prompt_versioning.py` (no eval/prompt_versioning module)
- `test_auth.py` (no auth module)
- `test_integration.py` (`test_phase1_critical.py` is a partial substitute)

These are largely irrelevant post-pivot, but the gap matters for any modules that do exist (e.g., cascade, world_state, circuit_breaker logic embedded elsewhere).

**Recommendation:** Accept as non-issues given the pivot, but note that `test_cascade.py` and `test_world_state.py` do exist and should be maintained.

---

### [LOW] Agent Prompts Hardcoded as Python Strings

The spec calls for YAML prompt files (`agents/prompts/*.yaml`) with semver versioning. Implemented prompts are Python string constants inside `prediction/*.py`. No version tracking exists — if a prompt is changed, there's no A/B comparison mechanism.

**Recommendation:** Not urgent for a 3-model system, but if prediction accuracy regresses, diagnosing prompt vs. data changes will be difficult without versioning.

---

## What's Working Well

- **DbWriter pattern is correctly implemented** in `db/writer.py` — the architecture is right; the violation is in consumers not using it.
- **Schema is comprehensive** — 26 tables with clean DDL, migration helpers, and views. Covers the full prediction market lifecycle.
- **42 test files** with good coverage of the new prediction/scoring/market modules.
- **Budget tracking** (`BudgetTracker`) and runtime kill-switch (`ops/runtime.py`) are implemented.
- **Signal ledger + scorecard ETL** provides the core eval loop the spec envisioned.
- **scenario_hormuz.yaml** exists and matches spec parameters exactly.
- **Paper trading** via Kalshi sandbox is wired up.

---

## Recommendations (Priority Order)

1. **[HIGH]** Route all direct `conn.execute()` writes in `scoring/`, `ops/`, `backtest/`, `ingestion/` through `DbWriter.enqueue()` — or explicitly document which components are designed to run in a single-threaded context where concurrent writes are impossible.
2. **[MEDIUM]** Add `h3>=4.1` to `pyproject.toml` to prevent latent `ImportError` in simulation modules.
3. **[MEDIUM]** Add a pivot note to `docs/superpowers/plans/2026-03-30-parallax-phase1.md` so future contributors aren't misled.
4. **[LOW]** Delete or fix the 6 skipped tests in `test_mapping_policy.py`.
5. **[LOW]** Add prompt version metadata to `PredictionOutput` schema to enable future A/B tracking.
