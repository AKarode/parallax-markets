# Parallax Health Check — 2026-11-14

**Status: YELLOW**

## Summary

The codebase has matured well beyond the original Phase 1 geopolitical cascade simulator spec into a focused prediction-market edge-finder (Kalshi/Polymarket signals), which is documented and intentional per CLAUDE.md. However, the test environment is broken due to a Python/duckdb version mismatch (duckdb 2.0.0 installed under Python 3.13 dist-packages while the runtime is Python 3.11), making the entire test suite un-runnable. Additionally, several scoring and ops modules bypass the mandated DuckDB single-writer pattern with direct synchronous writes that risk database locking under concurrent load.

---

## Issues Found

### [CRITICAL] Test suite cannot run — Python/duckdb version mismatch

- `duckdb 2.0.0` is installed under `/usr/local/lib/python3.13/dist-packages/` but the runtime Python is 3.11.18 (`/usr/local/bin/python3`)
- Running `pytest tests/` fails immediately: `ModuleNotFoundError: No module named 'duckdb'`
- All 47 test files are blocked; no test has run or validated in this environment
- **Fix**: Install duckdb for the Python 3.11 runtime: `pip3.11 install duckdb>=1.2` or add `duckdb` to a 3.11-scoped venv

### [HIGH] DuckDB single-writer topology violated in multiple modules

The spec and CLAUDE.md mandate all writes flow through `DbWriter` / `asyncio.Queue`. The following modules write directly to DuckDB, bypassing the queue:

| File | Location | Write type |
|------|----------|------------|
| `ops/alerts.py` | `DuckDBAlertSink.send()` line 106 | Async direct INSERT into `ops_events` |
| `scoring/ledger.py` | `SignalLedger.record_signal()` line 227 | Synchronous direct INSERT into `signal_ledger` |
| `scoring/tracker.py` | `execute_signal()`, `poll_resting_orders()`, `cancel_order()` lines 518, 674, 746 | Async direct INSERTs into `trade_positions`, `trade_orders`, `trade_fills` |
| `budget/tracker.py` | `BudgetTracker.record()` line 45 | Synchronous direct INSERT into `llm_usage` |
| `scoring/prediction_log.py` | line 81 | Direct INSERT into `prediction_log` |

Concurrent runs (e.g. `run_brief()` + background scorecard) can produce `database is locked` errors. The synchronous writes in `ledger.py` and `budget/tracker.py` are particularly risky — they can block the asyncio event loop while holding the DuckDB connection.

### [HIGH] Multiple `duckdb.connect()` calls in `cli/brief.py`

`cli/brief.py` opens separate DuckDB connections at lines 535, 786, 817, 827, and 837. Each connection can write independently. Under the single-writer topology this should be one shared connection (or read-only connections for reads). Concurrent runs of `brief.py` (e.g. cron overlap) will produce lock contention.

### [MEDIUM] Architecture drift from Phase 1 spec (intentional, needs CLAUDE.md update)

The original spec (`2026-03-30-parallax-phase1-design.md`) describes an H3 hex map dashboard with a 50-agent geopolitical swarm, WebSocket frontend, and GDELT pipeline. The actual codebase implements a prediction-market edge-finder. The following spec modules were never built:

- `simulation/engine.py` (DES core) — absent
- `simulation/circuit_breaker.py` — absent
- `spatial/` module (H3 utilities, route-to-cell) — absent
- `agents/` module (swarm registry, router, runner, country agents) — absent
- `api/websocket.py`, `api/auth.py` — absent
- `ingestion/dedup.py` (semantic dedup) — absent
- `eval/` module (prompt versioning, improvement pipeline) — absent
- Frontend: No HexMap, AgentFeed, Timeline — replaced with KpiBar, MarketsTable, PortfolioPanel, PriceChart

CLAUDE.md documents the new product direction, which is good. The original spec document is now a historical artefact and may confuse future contributors. **Recommendation**: add a brief note at the top of `docs/superpowers/specs/2026-03-30-parallax-phase1-design.md` and the plan file indicating the product pivoted.

### [MEDIUM] `pyproject.toml` missing several Phase-1-spec dependencies

The spec listed `h3>=4.1`, `searoute>=1.3`, `shapely>=2.0`, `google-cloud-bigquery>=3.27`, `websockets>=14.0`, `sentence-transformers>=3.4`. None are in `pyproject.toml`. This is consistent with the product pivot (those packages supported the unbuilt H3/agent/GDELT features), but if any code path still imports them (e.g. `google_news.py` parsing, GDELT helpers) it will fail silently at import time. Verify no remaining code imports these removed packages.

### [LOW] `anthropic` package version pinned too loosely

`pyproject.toml` declares `anthropic>=0.52` but the installed version is `2.8.0` (a major jump). The API surface changed significantly across major versions. Consider pinning to `anthropic>=2.0,<3` to avoid unexpected breaks on a future `3.x` release.

### [LOW] Test files planned in Phase 1 that remain absent

The following test files from the plan were never created (and correspond to unbuilt modules):
`test_h3_utils.py`, `test_gdelt_filter.py`, `test_dedup.py`, `test_agent_schemas.py`, `test_agent_router.py`, `test_agent_runner.py`, `test_prompt_versioning.py`, `test_auth.py`, `test_integration.py`

The existing 47 test files cover the actual implemented modules well. No action needed unless the absent modules are planned.

---

## Recommendations

1. **[Immediate]** Fix the Python/duckdb version mismatch so CI can run. The fastest fix: `pip install duckdb>=1.2` using the same Python binary that runs the tests (verify with `python3 -c "import duckdb"`).

2. **[This sprint]** Route `SignalLedger`, `BudgetTracker`, `DuckDBAlertSink`, and `PredictionLogger` writes through the `DbWriter` queue. For synchronous callers (`BudgetTracker.record`, `SignalLedger.record_signal`), either make them async or use `conn.execute()` on a dedicated write lock. The `tracker.py` async methods can call `await db_writer.enqueue(...)` directly.

3. **[This sprint]** Audit `cli/brief.py` to consolidate DuckDB connections — open one at startup, pass it through, close at the end. Flag overlapping cron runs with a file lock or DB advisory lock.

4. **[Housekeeping]** Add a "Product pivot note" banner to the Phase 1 design spec and plan files so they're clearly historical.

5. **[Low priority]** Tighten the `anthropic` version pin to `>=2.0,<3`.
