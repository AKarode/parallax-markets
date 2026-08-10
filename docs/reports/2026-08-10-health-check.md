# Parallax Health Check — 2026-08-10

**Status: YELLOW**

## Summary

The project has intentionally pivoted from the Phase 1 design spec (H3 spatial cascade simulator with ~50 LLM agents and deck.gl frontend) into a focused prediction market edge-finder (3 LLM predictors, Kalshi/Polymarket integration, paper trading, CLI + React signal dashboard). This architectural divergence is by design per CLAUDE.md, but the original Phase 1 spec and plan no longer reflect the actual system. The core concern is that the `DbWriter` single-writer queue — the spec's critical DuckDB safety guarantee — exists but is effectively unused: at least 10 modules bypass it and write directly to DuckDB.

---

## Issues Found

### HIGH — DuckDB Single-Writer Pattern Not Enforced

**Severity: HIGH**

The spec defines an `asyncio.Queue`-based single-writer topology as a hard architectural constraint. `DbWriter` (in `db/writer.py`) implements this correctly, but `enqueue()` is called from nowhere in production code. Every module that writes to DuckDB does so directly via `conn.execute()`, bypassing the queue entirely:

- `scoring/ledger.py` — INSERT/UPDATE to `signal_ledger`
- `scoring/tracker.py` — INSERT/UPDATE to `trade_positions`, `trade_orders`, `trade_fills`
- `scoring/resolution.py` — UPDATE to `signal_ledger`, `trade_positions`
- `scoring/scorecard.py` — INSERT INTO `daily_scorecard`
- `scoring/prediction_log.py` — INSERT INTO `prediction_log`
- `contracts/registry.py` — INSERT/DELETE/UPDATE to `contract_registry`, `contract_proxy_map`
- `ops/alerts.py` — INSERT INTO `ops_events`
- `budget/tracker.py` — INSERT INTO `llm_usage`
- `cli/brief.py` — INSERT/UPDATE to `runs`, `market_prices`
- `ingestion/crisis_ingester.py` — INSERT INTO `crisis_events`

**Risk**: The CLI currently runs synchronously (not concurrent asyncio tasks), so "database is locked" errors may not surface in practice. But if any async paths or concurrent callers are introduced, this will cause hard failures. `DbWriter` is dead code and should either be wired up or removed.

---

### HIGH — Missing Spec-Required Dependencies in pyproject.toml

**Severity: HIGH**

The following packages are required by the Phase 1 spec/plan but absent from `pyproject.toml`:

| Package | Spec Use |
|---------|----------|
| `h3>=4.1` | H3 spatial indexing, resolution bands |
| `sentence-transformers>=3.4` | GDELT semantic dedup (`all-MiniLM-L6-v2`) |
| `searoute>=1.3` | Shipping route visualization geometry |
| `shapely>=2.0` | Geometric operations for spatial analysis |
| `google-cloud-bigquery>=3.27` | GDELT BigQuery feed |
| `websockets>=14.0` | WebSocket support for real-time simulation updates |

These are absent because the project pivoted. The `h3` and `simulation/world_state.py` modules exist in code but `h3` is not installable from the current `pyproject.toml`. If anyone runs `pip install -e .` and then imports `parallax.simulation.world_state`, they will get an `ImportError` on any h3-using path.

---

### MEDIUM — Architecture Drift: Agent Swarm, Spatial Model, and Eval Framework Not Implemented

**Severity: MEDIUM**

Large portions of the Phase 1 spec were never built and no longer appear to be planned:

- **`agents/` directory**: Does not exist. No registry, runner, router, country agent, sub-actor prompts, or 50-agent hierarchy. Replaced by 3 focused `prediction/` models.
- **`spatial/` directory**: Does not exist. No H3 resolution bands, cell chains, or Overture Maps loader.
- **`eval/` directory**: Does not exist. No structured prediction versioning, prompt improvement pipeline, or A/B comparison. Replaced by `scoring/` module with different scope.
- **Simulation engine**: `simulation/engine.py` (DES with heapq) and `simulation/circuit_breaker.py` are absent. `simulation/cascade.py` exists but is a stripped-down version for the prediction models, not the full 6-rule cascade engine.
- **WebSocket frontend**: Frontend uses polling (`hooks/usePolling.ts`) rather than WebSocket connection. No `HexMap.tsx`, `AgentFeed.tsx`, `Timeline.tsx`, or deck.gl H3HexagonLayer components.

This is consistent with the product pivot described in CLAUDE.md, but the spec documents should be updated to reflect the current direction.

---

### MEDIUM — Test Coverage Gaps vs. Plan

**Severity: MEDIUM**

11 of 18 test files specified in the Phase 1 plan are absent:

| Missing Test File | Module it covers |
|------------------|-----------------|
| `test_h3_utils.py` | `spatial/h3_utils.py` (module missing) |
| `test_gdelt_filter.py` | `ingestion/gdelt.py` volume gate (only `test_gdelt_doc.py` exists) |
| `test_dedup.py` | `ingestion/dedup.py` (module missing) |
| `test_circuit_breaker.py` | `simulation/circuit_breaker.py` (module missing) |
| `test_agent_schemas.py` | `agents/schemas.py` (module missing) |
| `test_agent_router.py` | `agents/router.py` (module missing) |
| `test_agent_runner.py` | `agents/runner.py` (module missing) |
| `test_budget_tracker.py` | `budget/tracker.py` (module exists, no unit test) |
| `test_prompt_versioning.py` | `eval/prompt_versioning.py` (module missing) |
| `test_auth.py` | `api/auth.py` (module missing) |
| `test_integration.py` | End-to-end pipeline test |

**Note**: The project has 41 actual test files covering the real implemented code (markets, predictions, scoring, contracts, etc.). Coverage of the current system appears reasonably broad, but the budget tracker and CLI integration paths lack unit tests.

---

### LOW — Python Version Mismatch

**Severity: LOW**

- `pyproject.toml` declares `requires-python = ">=3.11"`
- CLAUDE.md states "Python 3.12"

The lower bound should be tightened to `>=3.12` to match documented constraints and avoid accidental 3.11 deployments.

---

### LOW — `portfolio/` Missing `__init__.py`

**Severity: LOW**

`backend/src/parallax/portfolio/` has no `__init__.py`. It contains `allocator.py`, `schemas.py`, and `simulator.py`. Under Python 3.3+ namespace packages this typically works, but it is inconsistent with every other parallax subpackage and could cause import issues in some tooling.

---

### LOW — Spec Documents Describe Unmbuilt System

**Severity: LOW** (documentation hygiene)

Both `docs/superpowers/specs/2026-03-30-parallax-phase1-design.md` and `docs/superpowers/plans/2026-03-30-parallax-phase1.md` describe the original spatial simulator (H3 hex map, 50 agents, BigQuery GDELT, DES engine). The actual system is a prediction market signal generator. Stale spec documents will mislead any new contributors.

---

## Recommendations

1. **Wire up or remove `DbWriter`**: Either route all writes through `DbWriter.enqueue()` (preferred for safety), or remove the class and accept direct `conn.execute()` writes with a documented note that the process is single-threaded. Do not leave dead safety infrastructure in place.

2. **Reconcile `pyproject.toml` with actual imports**: Run `pip check` and audit which packages are actually imported in production paths. Remove spec-required packages that are never used; add any missing ones that are actually imported. At minimum, bump Python floor to `>=3.12`.

3. **Add `portfolio/__init__.py`**: One-line fix to align with the rest of the package structure.

4. **Update spec documents**: Archive or replace the Phase 1 spec/plan with documents describing the current prediction market signal architecture. The gap between documentation and implementation creates onboarding friction.

5. **Add `test_budget_tracker.py`**: The `BudgetTracker` enforces the $20/day cap — a key operational constraint — but has no unit tests.

6. **Decide on `simulation/` fate**: `cascade.py`, `world_state.py`, and `config.py` remain in `simulation/` but serve the prediction models, not a DES engine. Either rename the module to reflect its actual purpose or complete the DES engine.
