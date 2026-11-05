# Parallax Health Check — 2026-08-16

**Status: YELLOW**

The codebase is functional and has strong test coverage for its implemented scope, but the architecture has diverged significantly from the Phase 1 spec/plan, and the spec-required DuckDB single-writer pattern is bypassed by virtually every write path. No data loss has occurred yet because the CLI and server don't run concurrently in normal operation, but the structural violation is a latent risk.

---

## Summary

The project intentionally pivoted from a 50-agent geopolitical cascade simulator (Phase 1 design spec) to a focused prediction market edge-finder (documented in CLAUDE.md). That pivot is coherent and the implemented system — 3 LLM prediction models, Kalshi/Polymarket price comparison, paper trading, scoring/calibration — has ~46 tests and appears operationally functional. The issues below are structural/architectural rather than functional.

---

## Issues Found

### [HIGH] DuckDB Single-Writer Pattern Largely Bypassed

**Spec requirement**: All mutable state must flow through a centralized `asyncio.Queue` (`DbWriter`). `DbWriter` exists and is correctly implemented (`db/writer.py`), but it is used by virtually nothing.

The following modules perform direct `conn.execute(INSERT/UPDATE/DELETE)` calls outside the writer queue:

| Module | Tables Written |
|--------|---------------|
| `scoring/ledger.py:225,256` | `signal_ledger` |
| `scoring/tracker.py:460,516,672,711,744` | `trade_positions`, `trade_orders`, `trade_fills` |
| `scoring/prediction_log.py:79` | `prediction_log` |
| `scoring/resolution.py:60,124` | `signal_ledger`, `trade_positions` |
| `scoring/scorecard.py:21` | `daily_scorecard` |
| `ops/alerts.py:106` | `ops_events` |
| `budget/tracker.py:43` | `llm_usage` |
| `cli/brief.py:130,149,431` | `runs`, `market_prices` |
| `contracts/registry.py:85,105,114,198` | `contract_registry`, `contract_proxy_map` |
| `backtest/runner.py:290,308,329,356` | `backtest_runs`, `backtest_predictions` |

**Risk**: If `cli/brief.py` and the FastAPI server (`/api/brief/run`) overlap on the same DuckDB file, concurrent writes can cause `database is locked` errors. This is currently avoided by convention (run CLI offline; server reads only), but the boundary is not enforced. The `api/brief/run` endpoint could trigger writes from the server process while the CLI also runs.

**Recommendation**: Either route all writes through `DbWriter` in the async server context, or formally accept that the CLI is offline-only and the server is read-only, and document/enforce that boundary with a startup check.

---

### [HIGH] Spec/Plan Document Is Stale — No Agent System Exists

The Phase 1 spec describes a ~50-agent LLM swarm with country→sub-actor hierarchy, H3 geospatial visualization, WebSocket streaming, and an eval framework. None of this was built. The CLAUDE.md correctly describes the current system, but the spec doc misleads any new contributor. The following directories expected by the plan are absent:

- `agents/` — no multi-agent system
- `eval/` — no eval framework (bench/ provides calibration benchmarks only)
- `api/` — all 14 routes crammed into `main.py` (366 lines)
- `spatial/` — no H3 spatial logic despite `h3_cell BIGINT` columns in schema and the DuckDB H3 extension loaded in conftest

**Recommendation**: Update the spec doc header to note the pivot, or add a `docs/architecture-current.md` that reflects what was actually built. Remove the H3 extension loads from `conftest.py` until H3 logic is actually implemented.

---

### [MEDIUM] Missing `__init__.py` in Two Packages

- `backend/src/parallax/config/` — no `__init__.py`. Imports work via Python 3.3+ namespace packages but inconsistent with every other module.
- `backend/src/parallax/portfolio/` — no `__init__.py`. Same issue; used by `main.py:359` and `cli/brief.py:31-32`.

**Recommendation**: Add `__init__.py` to both directories.

---

### [MEDIUM] Missing `db/queries.py` — No Read/Write Boundary Enforced

The plan specified a `queries.py` module for read-only helpers, creating a clear architectural separation between reads and writes. It was never created. Read-side queries are scattered inline across `dashboard/data.py`, `main.py`, `scoring/calibration.py`, etc.

**Recommendation**: This is low-priority since reads are safe concurrent in DuckDB, but extracting a `db/queries.py` would centralize query ownership and make the read/write boundary visible.

---

### [MEDIUM] Test Coverage Gaps for the Plan's Scope

13 of 18 plan-expected test files are missing. The missing tests are for modules that were never built (agents, eval, auth, dedup, h3_utils), which is consistent with the pivot. However, two gaps exist for code that **does** exist:

- `test_budget_tracker.py` — `budget/tracker.py` has no tests; no budget enforcement logic is tested
- `test_integration.py` — no end-to-end test that runs a full brief cycle

**Recommendation**: Add `test_budget_tracker.py` and at least one `test_integration.py` smoke test.

---

### [LOW] Dependency Drift from Plan

Packages specified in the plan but absent from `pyproject.toml`:

| Dependency | Planned Use | Status |
|------------|------------|--------|
| `h3>=4.1` | H3 spatial indexing | Not needed (spatial module never built) |
| `sentence-transformers>=3.4` | Semantic dedup | Not needed (dedup never built) |
| `searoute>=1.3` | Shipping route geometry | Not needed |
| `shapely>=2.0` | Geometric ops | Not needed |
| `google-cloud-bigquery>=3.27` | GDELT BigQuery | Not needed (GDELT DOC API used instead) |
| `websockets>=14.0` | WebSocket dashboard | Not needed (REST polling used instead) |

These absences are **correct** given the pivot — no action needed. However, `pyproject.toml` still says `requires-python = ">=3.11"` while the plan specified `>=3.12`. The codebase uses `str | None` union syntax (3.10+) and `asyncio.Queue[WriteOp | None]` (3.9+), so 3.11 is fine, but worth noting.

---

### [LOW] Frontend Stack Does Not Match Spec

Plan: deck.gl + MapLibre + H3HexagonLayer + WebSocket streaming  
Actual: React 18 + Recharts + REST polling (usePolling.ts)

This is intentional given the pivot — the frontend is a prediction market dashboard, not a geospatial simulator. No action needed, but the spec doc is misleading.

---

## Recommendations (Priority Order)

1. **Clarify the single-writer boundary** — decide whether to route server-initiated writes through DbWriter, or formally enforce CLI-offline / server-readonly separation with a runtime check.
2. **Update or supersede the Phase 1 spec** — the current spec doc describes a system that was never built and is misleading.
3. **Add `__init__.py` to `config/` and `portfolio/`** — trivial fix.
4. **Add `test_budget_tracker.py` and a smoke integration test** — low-effort, covers real gaps.
5. **Remove H3 extension loads from conftest.py** — until H3 spatial code is actually written, these slow down test runs and create false expectations.
