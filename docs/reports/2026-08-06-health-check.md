# Parallax Health Check — 2026-08-06

**Status: YELLOW**

## Summary

No code changes since yesterday's report (2026-08-05) — only a tech research document was added. All issues are carryover. The CRITICAL DuckDB single-writer violation has now been flagged in **25 consecutive daily health checks** with no remediation. The main test suite is healthy (433 pass, 13 skip), but 4 bench-module tests fail at collection due to missing optional dependencies (`pandas`, `scikit-learn`, `numpy`). All architectural integrity concerns from the Phase 1 spec remain unaddressed.

---

## Issues Found

### [CRITICAL — 25 days unaddressed] DuckDB single-writer violations

The spec declares the `asyncio.Queue → DbWriter` pattern a **hard constraint** against `database is locked` errors. `DbWriter` (`db/writer.py`) is correctly implemented but is imported only by its own test — never by any production module. Every write in the production system is a direct synchronous `conn.execute()` call, bypassing the queue entirely:

| File | Write targets |
|---|---|
| `scoring/ledger.py` | `signal_ledger` (INSERT, UPDATE) |
| `scoring/tracker.py` | `trade_orders`, `trade_positions`, `trade_fills` (INSERT, UPDATE × 6) |
| `scoring/prediction_log.py` | `prediction_log` (INSERT) |
| `scoring/resolution.py` | `predictions`, `signal_ledger` (UPDATE) |
| `scoring/scorecard.py` | `daily_scorecard` (INSERT OR REPLACE) |
| `ingestion/crisis_ingester.py` | `crisis_events` (INSERT) |
| `contracts/registry.py` | `contract_registry`, `contract_proxy_map` (INSERT, UPDATE, DELETE) |
| `ops/alerts.py` | `ops_events` (INSERT) — additionally blocks the event loop in an `async def` |
| `cli/brief.py` | `runs`, `market_prices` (INSERT, UPDATE) |
| `budget/tracker.py` | `llm_usage` (INSERT) |
| `backtest/runner.py` | `backtest_runs`, `backtest_predictions`, `signal_ledger` (INSERT, UPDATE × 4) |

**Safe today only because `run_brief()` is single-threaded.** The `/api/brief/run` endpoint fires `run_brief()` inline (no background task isolation), and multiple concurrent POST requests would hit simultaneous writes. With the current FastAPI/uvicorn setup this is a latent data-corruption hazard.

**Recommended next action:** Wire `DbWriter` into `main.py` lifespan (`app.state.db_writer`), pass it to `SignalLedger`, `PaperTradeTracker`, `PredictionLogger`, and `BudgetTracker` constructors, and replace their `conn.execute()` INSERT/UPDATE calls with `await writer.enqueue(...)`. Estimated: 2-3 hours.

### [HIGH — new] 4 bench tests fail at collection (missing optional deps)

Running the full test suite (`pytest tests/`) fails to collect 4 modules with `ModuleNotFoundError: No module named 'pandas'`:
- `tests/test_bench_forecast.py`
- `tests/test_calibration_metrics.py`
- `tests/test_recalibrators.py`
- `tests/test_selective.py`

These require the `[bench]` extras (`pip install -e ".[bench]"`). Because pytest aborts collection on error, a naive `pytest tests/` run produces 4 errors and exits with a non-zero code before running any tests — this will fail CI if a clean install (without `[bench]`) is used. Fix: add `pytest.importorskip("pandas")` guards at the top of each file, or split bench tests into a separate directory skipped by default.

### [HIGH — carryover] CLAUDE.md tech stack differs from pyproject.toml

CLAUDE.md documents six dependencies absent from `pyproject.toml`:

| Documented | Status |
|---|---|
| `h3>=4.1` | missing from pyproject.toml |
| `sentence-transformers>=3.4` | missing from pyproject.toml |
| `searoute>=1.3` | missing from pyproject.toml |
| `shapely>=2.0` | missing from pyproject.toml |
| `google-cloud-bigquery>=3.27` | missing from pyproject.toml |
| `websockets>=14.0` | missing from pyproject.toml |

New contributors will install based on pyproject.toml and hit import errors if they use anything documented in CLAUDE.md's stack section.

### [HIGH — carryover] Frontend documentation does not match implementation

CLAUDE.md lists `deck.gl 9.1.0`, `MapLibre GL 4.7.0`, `react-map-gl 7.1.8`, and `h3-js` as frontend dependencies. The actual `frontend/package.json` uses only React + Recharts. The frontend is a polling dashboard with 9 components — no hex map, no WebSocket, no deck.gl.

### [HIGH — carryover] Agent swarm and spatial model absent

The Phase 1 plan's central deliverable — a 50-agent country→sub-actor swarm with H3 hex-map — was replaced by a 3-model prediction pipeline. Missing modules:

- `agents/` (registry, runner, router, country_agent, schemas, prompts/) — **not built**
- `spatial/` (h3_utils.py, loader.py) — **not built**
- `eval/` (scoring, ground_truth, prompt_versioning, improvement) — **not built**
- `simulation/engine.py` (DES core) — **not built**
- `simulation/circuit_breaker.py` — **not built**
- `ingestion/dedup.py` (semantic dedup) — **not built**

The `agent_memory` and `agent_prompts` DuckDB tables are created by `schema.py` and never written to. The pivot to the prediction-market edge-finder is a valid product decision, but the spec gap creates confusion for onboarding.

### [MEDIUM — carryover] Python version pin too loose

`pyproject.toml` declares `requires-python = ">=3.11"` while CLAUDE.md and the project standard is Python 3.12. Should be `">=3.12"`.

### [MEDIUM — carryover] Test coverage gaps for write paths

The following write-heavy modules have no test coverage:

| Module | Write operations | Tests |
|---|---|---|
| `ingestion/crisis_ingester.py` | INSERT into `crisis_events` with fuzzy-dedup | none |
| `backtest/runner.py` | INSERT/UPDATE across 3 tables | none |
| `backtest/look_ahead_guard.py` | Integrity check for backtest inputs | none |
| `portfolio/simulator.py` | Reads + derived P&L logic | none |

`backtest/look_ahead_guard.py` is especially risky — a silent failure there invalidates all backtest results.

### [LOW — carryover] No schema versioning

`schema.py` has grown to 26 tables + 2 views (spec called for 10). The `_migrate_legacy_tables()` function applies ad-hoc `ALTER TABLE` changes with no version tracking.

---

## Test Suite Snapshot

| Metric | Value |
|---|---|
| Tests collected (excluding bench) | 446 |
| Passed | 433 |
| Skipped | 13 |
| Collection errors (bench deps) | 4 |
| Last code change | 2026-08-05 (health check only) |

---

## Recommendations

1. **[Immediate] Wire DbWriter into production write paths.** 25 days flagged with no action. Add `db_writer: DbWriter` to the constructors of `SignalLedger`, `PaperTradeTracker`, `PredictionLogger`, `BudgetTracker`, and `ContractRegistry`; replace their `conn.execute()` INSERT/UPDATE calls with `await self._writer.enqueue(...)`. Estimated: 2-3 hours.

2. **[High] Fix bench test collection failures.** Add `pandas = pytest.importorskip("pandas")` at the top of the 4 affected test files so they skip gracefully on a minimal install instead of crashing collection.

3. **Update CLAUDE.md to match actual stack.** Remove spec-era dependencies (h3, sentence-transformers, searoute, shapely, bigquery, websockets) from the stack section and update the frontend section to reflect the Recharts dashboard.

4. **Tighten Python version pin.** `requires-python = ">=3.12"` in pyproject.toml.

5. **Add schema versioning.** One-row `schema_version` table; increment on each `_migrate_legacy_tables()` pass.

6. **Add tests for crisis_ingester and backtest look-ahead guard.** These are high-value integrity components with zero test coverage.
