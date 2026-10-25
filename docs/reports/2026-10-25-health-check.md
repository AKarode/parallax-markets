# Parallax Health Check — 2026-10-25

**Status: YELLOW**

The project has diverged significantly from its Phase 1 design spec. The implementation pivoted from a geopolitical cascade simulator with LLM agent swarm into a prediction market edge-finder (Kalshi/Polymarket divergence detector), which is valuable but is architecturally distinct from the spec. Core simulation modules exist but are incomplete; the agent swarm, WebSocket frontend, and eval framework from the spec have not been built.

---

## Summary

The codebase implements a functional prediction market pipeline (news ingestion → 3 Claude prediction models → market comparison → paper trading) that was not described in the original Phase 1 spec. The spec's core deliverables — H3 spatial simulation, ~50-agent LLM swarm, WebSocket dashboard, and eval framework — are largely absent. The deviation appears intentional (CLAUDE.md describes the current system as the product), but the spec/plan documents describe a different system, creating documentation drift.

---

## Issues Found

### [HIGH] Architecture Drift — Complete Pivot from Spec

- **Spec describes**: LLM agent swarm (~50 agents, country/sub-actor hierarchy), H3 hexagonal spatial model, WebSocket-driven React/deck.gl dashboard, DES simulation engine, GDELT eval framework
- **Code implements**: 3 focused prediction models (oil price, ceasefire, Hormuz reopening), Kalshi/Polymarket market comparison, paper trading, signal ledger, scorecard
- **Missing modules from spec**: `agents/` (entire directory absent), `spatial/` (h3_utils.py, loader.py absent), `api/` (routes.py, websocket.py, auth.py absent), `eval/` (predictions.py, scoring.py, ground_truth.py, improvement.py absent), `ingestion/dedup.py` (semantic dedup absent)
- **Recommendation**: Either update the spec/plan to match the current system, or acknowledge this as Phase 1b and create a new plan for the original spec's deliverables.

### [HIGH] Missing Dependencies in pyproject.toml

The spec and plan require these packages that are **absent** from `pyproject.toml`:
- `h3>=4.1` — H3 geospatial indexing (used in existing `simulation/config.py` implicitly; tests import it)
- `searoute>=1.3` — shipping route visualization
- `shapely>=2.0` — geometric operations
- `sentence-transformers>=3.4` — semantic dedup (referenced in spec's dedup stage)
- `google-cloud-bigquery>=3.27` — GDELT BigQuery integration
- `websockets>=14.0` — WebSocket support
- Present in CLAUDE.md tech stack but missing from `pyproject.toml`; this will cause `ImportError` at runtime for any code that imports them.

### [MEDIUM] DuckDB Single-Writer Violations

The spec mandates all writes go through `asyncio.Queue → db_writer`. Multiple modules bypass this:

- `backend/src/parallax/ops/alerts.py:106` — `DuckDBAlertSink` calls `self.db_conn.execute()` directly
- `backend/src/parallax/backtest/runner.py:290,308,329,356` — direct `conn.execute()` writes in backtest runner
- `backend/src/parallax/backtest/look_ahead_guard.py:96,109` — direct writes in look-ahead guard
- These are acceptable for the backtest module (offline, single-process, no concurrency) but `alerts.py` runs in the live pipeline and violates the topology.

### [MEDIUM] Python Version Constraint Mismatch

- `pyproject.toml` requires `requires-python = ">=3.11"` 
- CLAUDE.md and spec state Python 3.12 is the target
- Some syntax used (e.g., `str | None` union type hints) requires 3.10+, so 3.11 is safe, but the inconsistency with stated requirements could cause subtle issues if Python 3.11 behavior differs from 3.12 in dependencies.

### [MEDIUM] Test Coverage Gaps vs. Plan

Tests specified in the plan that are **absent**:
- `test_schema.py` — present, but tests only the old schema (10 tables); current schema has 20+ tables not all tested
- `test_writer.py` — present ✓
- `test_h3_utils.py` — **absent** (h3_utils.py itself is absent)
- `test_gdelt_filter.py` — **absent** (the current `gdelt_doc.py` diverges from plan's `gdelt.py`)
- `test_dedup.py` — **absent** (dedup.py is absent)
- `test_agent_schemas.py` — **absent** (agents/ directory is absent)
- `test_agent_router.py` — **absent**
- `test_agent_runner.py` — **absent**
- `test_scoring.py` — **absent** (plan's eval scoring functions)
- `test_prompt_versioning.py` — **absent**
- `test_auth.py` — **absent**
- `test_integration.py` — **absent**

Tests present that were **not in the plan** (coverage of the actual implemented system):
- `test_brief.py`, `test_brief_resilience.py`, `test_calibration.py`, `test_dashboard_data.py`, `test_divergence.py`, `test_ensemble.py`, `test_ledger.py`, `test_scorecard.py`, `test_simulator.py`, `test_track_record.py` — good coverage of the actual implementation.

### [MEDIUM] simulation/ Module Incomplete

- `simulation/engine.py` — **absent** (DES engine from plan Task 8 not present)
- `simulation/circuit_breaker.py` — **absent** (circuit breaker from plan Task 7 not present)
- `simulation/cascade.py` — present ✓ (implemented differently — 6-rule cascade for the market predictor)
- `simulation/world_state.py` — present ✓
- `simulation/config.py` — present ✓

### [LOW] Frontend Architecture Mismatch

- **Spec describes**: WebSocket-driven deck.gl map with H3HexagonLayer, AgentFeed, LiveIndicators, Timeline panels
- **Code implements**: REST polling SPA with `usePolling.ts`, MarketsTable, ModelCards, PortfolioPanel — no deck.gl, no map, no H3 visualization
- The frontend pivot is coherent with the backend pivot but diverges from the spec's deck.gl/MapLibre architecture.

### [LOW] pytest Not Installed in Current Environment

- Running `python -m pytest` returns `No module named pytest` — the dev dependencies are not installed in the current container environment.
- This prevents CI validation of the test suite. Run `pip install -e ".[dev]"` to fix.

### [LOW] `pyproject.toml` Missing `bench` Extras from Some Dependencies

- The `bench` extras group requires `numpy`, `pandas`, `scikit-learn`, etc., but `pyproject.toml` doesn't list `numpy` in core dependencies even though `simulation/cascade.py` and other modules may use it indirectly.
- Not a blocker but worth auditing.

---

## Recommendations

1. **Update spec/plan docs** to reflect the current prediction-market system, or create `docs/superpowers/specs/2026-10-XX-parallax-phase1b-design.md` describing the actual built system. The current spec/plan describe a different product.

2. **Fix `pyproject.toml`** — add missing deps (`h3`, `websockets`, `shapely`) or remove references to them from CLAUDE.md if they're no longer needed.

3. **Fix `alerts.py` DuckDB write** — route through the `DbWriter` queue or ensure it only runs in a single-process context with explicit documentation.

4. **Install dev dependencies** in the deployment/CI environment (`pip install -e ".[dev]"`) to unblock test execution.

5. **Add integration test** for the actual pipeline: news ingestion → prediction → divergence → trade signal, with mocked LLM and market API responses.
