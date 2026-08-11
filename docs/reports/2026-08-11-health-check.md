# Parallax Health Check — 2026-08-11

**Status: YELLOW**

## Summary

No source code changes since July 17, 2026 — all issues identified in prior health checks persist unchanged. The project has deliberately pivoted from the Phase 1 spec (H3 hex-map agent swarm) to a focused prediction market edge-finder, but four structural defects remain open: the `DbWriter` single-writer queue is implemented but never wired up (dead safety code), 11 modules write directly to DuckDB bypassing it, the backtest module adds additional direct-write exposure not present in earlier reports, and the Python version floor in `pyproject.toml` remains mismatched with the documented runtime. No regressions detected; no improvements landed.

---

## Issues Found

### [HIGH] DuckDB Single-Writer Pattern Unenforced — 11 Files, Including New `backtest/` Module

`DbWriter` (`db/writer.py`) exists and implements the `asyncio.Queue` write-queue correctly, but `enqueue()` is imported and called from **nowhere** in the codebase. Every write-active module bypasses it with direct synchronous `conn.execute()` calls:

| File | Operations |
|------|-----------|
| `scoring/ledger.py` | INSERT/UPDATE → `signal_ledger` |
| `scoring/tracker.py` | INSERT/UPDATE → `trade_positions`, `trade_orders`, `trade_fills` |
| `scoring/resolution.py` | UPDATE → `signal_ledger`, `trade_positions` |
| `scoring/scorecard.py` | INSERT → `daily_scorecard` |
| `scoring/prediction_log.py` | INSERT → `prediction_log` |
| `contracts/registry.py` | INSERT/DELETE/UPDATE → `contract_registry`, `contract_proxy_map` |
| `ops/alerts.py` | INSERT → `ops_events` |
| `budget/tracker.py` | INSERT → `llm_usage` |
| `cli/brief.py` | INSERT/UPDATE → `runs`, `market_prices` |
| `ingestion/crisis_ingester.py` | INSERT → `crisis_events` |
| `backtest/runner.py` | INSERT/UPDATE → `backtest_runs`, `backtest_predictions` |

**Risk**: Concurrent writes from the API server (`main.py`) and the CLI (`python -m parallax.cli.brief`) running simultaneously against the same DuckDB file will trigger `database is locked` errors. The current CLI-primary usage pattern avoids this in practice, but the `/api/brief/run` endpoint calls `run_brief()` synchronously, making it possible for concurrent HTTP requests or a CLI run alongside a running server to collide.

**Recommended action**: Either route all writes through `DbWriter.enqueue()` in the async paths, or document that the system is intentionally single-process / single-connection and delete `DbWriter` to eliminate the false sense of safety.

---

### [HIGH] `backtest/runner.py` Writes DuckDB Directly — First Flagged Today

The `backtest/` module (`engine.py`, `runner.py`, `report.py`, `look_ahead_guard.py`) was part of the July 17 initial commit but was not specifically called out in yesterday's report. `backtest/runner.py` issues 4 direct `conn.execute()` writes (INSERT/UPDATE to `backtest_runs` and `backtest_predictions`). It also has no dedicated test file — only `test_backtest_look_ahead.py` exists, covering the look-ahead guard only.

---

### [MEDIUM] Architecture Drift — Agent Swarm, Spatial Layer, and DES Engine Absent

The following Phase 1 spec components remain unimplemented with no signs of imminent work:

- **`agents/` module**: Does not exist. 3 prediction models (`prediction/oil_price.py`, `ceasefire.py`, `hormuz.py`) replace the 50-agent hierarchy.
- **`spatial/` module**: Does not exist. No H3 resolution bands, cell chains, or Overture Maps loader.
- **`simulation/engine.py`** and **`simulation/circuit_breaker.py`**: Not present. `cascade.py` and `world_state.py` exist but serve the prediction models, not the DES engine.
- **Frontend**: Polling-based REST dashboard (`usePolling.ts`); no WebSocket, no H3HexagonLayer, no `AgentFeed`, `Timeline`, or `PredictionCards`.

This is consistent with the product pivot. The spec documents should be archived or replaced to avoid onboarding confusion.

---

### [MEDIUM] Test Coverage Gaps — 11 Plan-Required Files Missing

| Missing Test | Reason |
|-------------|--------|
| `test_h3_utils.py` | No `spatial/` module |
| `test_gdelt_filter.py` | No GDELT volume-gate module |
| `test_dedup.py` | No `ingestion/dedup.py` |
| `test_circuit_breaker.py` | No `simulation/circuit_breaker.py` |
| `test_agent_schemas.py` | No `agents/` module |
| `test_agent_router.py` | No `agents/` module |
| `test_agent_runner.py` | No `agents/` module |
| `test_budget_tracker.py` | `budget/tracker.py` exists, no unit test |
| `test_prompt_versioning.py` | No prompt versioning module |
| `test_auth.py` | No auth module |
| `test_integration.py` | No end-to-end pipeline test |

The existing 46 test files cover prediction, scoring, markets, contracts, calibration, and dashboard. Missing coverage of the `BudgetTracker` (enforces the $20/day hard cap) and `backtest/runner.py` (direct DB writes) are the most operationally significant gaps.

---

### [LOW] Python Version Floor Mismatch

`pyproject.toml` declares `requires-python = ">=3.11"`. CLAUDE.md and project conventions state Python 3.12. Bump to `>=3.12` to prevent accidental 3.11 installs.

---

### [LOW] `portfolio/` Missing `__init__.py`

`backend/src/parallax/portfolio/` contains `allocator.py`, `schemas.py`, and `simulator.py` but no `__init__.py`. Works under PEP 420 namespace packages but is inconsistent with every other parallax subpackage.

---

### [LOW] Spec Documents Describe Unbuilt System

`docs/superpowers/specs/2026-03-30-parallax-phase1-design.md` and the matching plan describe the H3 spatial simulator with 50 agents and BigQuery GDELT. The current system is a prediction market signal generator. These documents should be archived or updated.

---

## Recommendations

1. **Resolve the `DbWriter` question** (25+ days open): Wire all async write paths through `DbWriter.enqueue()`, or delete the class and add a CLAUDE.md note confirming that the system is single-process. This is the highest-priority structural issue.

2. **Add `test_budget_tracker.py`**: The $20/day cap is an operational constraint with real consequences. It has no unit test.

3. **Add `test_backtest_integration.py`**: `backtest/runner.py` writes to DuckDB and has meaningful state transitions. Only the look-ahead guard is currently tested.

4. **Add `portfolio/__init__.py`**: One-line fix.

5. **Bump `requires-python = ">=3.12"`** in `pyproject.toml`.

6. **Archive Phase 1 spec**: Move or annotate spec/plan docs to prevent misleading future contributors.
