# Parallax Health Check — 2026-07-11

**Status: YELLOW**

The core prediction-market pipeline is healthy: 433/433 tests pass, the three prediction models and Kalshi integration are functional, and the daily scorecard ETL is well-covered. However, a hard architectural constraint from the original spec — the DuckDB single-writer pattern — is violated in 10+ production write sites across 4 files, creating a latent race condition under concurrent API + CLI access. Additionally, 4 test files fail to import at collection time due to missing optional `bench` dependencies, breaking `pytest tests/` for new developers.

---

## Spec / Plan Consistency

The codebase has intentionally pivoted from the original Phase 1 spec (50-agent geopolitical simulator with H3 visualization and a DES engine) to a prediction market edge-finder with 3 focused Claude prediction models (oil price, ceasefire, Hormuz reopening), Kalshi/Polymarket integration, divergence detection, and paper trading. This pivot is fully reflected in `CLAUDE.md` and is the authoritative current direction.

**What remains from the original spec:** `db/schema.py` (extended to 26 tables), `db/writer.py`, `simulation/cascade.py`, `simulation/world_state.py`, `simulation/config.py`, and `ingestion/entities.py` are all implemented and tested.

**What was deliberately dropped:** The ~50-agent swarm (`agents/` module), the DES engine (`simulation/engine.py`, `simulation/circuit_breaker.py`), H3 spatial layer (`spatial/`), deck.gl/MapLibre frontend, WebSocket push, and the GDELT BigQuery integration.

---

## Issues Found

### [CRITICAL] DuckDB single-writer constraint violated in 10+ production write sites

The spec's single-writer topology requirement is not met. `db/writer.py`'s `DbWriter` asyncio queue exists but is dead code — no production path routes through it. All four write-path modules call `conn.execute(INSERT/UPDATE)` synchronously on the raw connection:

| File | Violation count | Tables written |
|---|---|---|
| `cli/brief.py` | 3 | `runs` (INSERT, UPDATE), `market_prices` (INSERT) |
| `scoring/ledger.py` | 2 | `signal_ledger` (INSERT, UPDATE) |
| `scoring/tracker.py` | 5 | `trade_positions`, `trade_orders`, `trade_fills` (INSERT, UPDATE) |
| `scoring/scorecard.py` | 1 | `daily_scorecard` (UPSERT) |

**Risk:** When `/api/brief/run` fires while a CLI `parallax-brief` cron is also running against the same DuckDB file, concurrent writes can produce `database is locked` errors or silent data corruption. This is a hard DuckDB constraint, not just a style issue.

**Fix:** Route all write operations in these four files through `DbWriter.enqueue()`. The queue is already implemented — the callers just need to be wired to it.

### [HIGH] `bench` test files fail to collect under `pytest tests/`

Four test files import `numpy`/`pandas` which live only in the `bench` extras group, not in `dev`:

- `tests/test_bench_forecast.py` → `import pandas`
- `tests/test_calibration_metrics.py` → `import numpy`
- `tests/test_recalibrators.py` → `import numpy`
- `tests/test_selective.py` → `import numpy`

Running `pytest tests/` (the documented command) fails with `ModuleNotFoundError` at collection time, not as a skip. CI and new developers will see a broken test suite without understanding why.

**Fix (option A):** Move bench tests into `tests/bench/` and configure `testpaths = ["tests"]` to exclude them unless `[bench]` extras are installed, or use a conftest skip marker. **Fix (option B):** Move `numpy`/`pandas` into the `dev` extras group.

### [HIGH] Python version mismatch: `>=3.11` vs required 3.12

`pyproject.toml` declares `requires-python = ">=3.11"` but `CLAUDE.md`, the spec, and all deployment docs specify Python 3.12. The codebase uses `str | None` union syntax (3.10+) so it works on 3.11, but the mismatch creates confusion and could allow a 3.11 build to ship that diverges from the validated deployment environment.

**Fix:** Tighten to `requires-python = ">=3.12"`.

### [MEDIUM] `scoring/tracker.py` — synchronous DB writes in async context

`PaperTradeTracker._upsert_position`, `_insert_order`, `_update_order`, and `_insert_fill` are called from async code paths but execute synchronous `conn.execute()` writes directly. This blocks the event loop during each trade operation. Under the current single-session usage this is low-risk, but any burst of trade signals will stall all concurrent FastAPI request handling.

**Fix:** Wire through `DbWriter.enqueue()` alongside the broader single-writer fix.

### [MEDIUM] Missing `ingestion/dedup.py` — semantic deduplication not implemented

The spec requires a four-stage GDELT filter including semantic dedup using `all-MiniLM-L6-v2` (stage 3). `ingestion/entities.py` (volume gate + entity override) is implemented, but the semantic dedup stage is absent. Neither `sentence-transformers` nor the dedup module exists. GDELT events with near-duplicate summaries (common in breaking news) will each reach the prediction models, inflating LLM cost and potentially double-counting signals.

### [MEDIUM] `httpx2` deprecation warning in test suite

FastAPI's `TestClient` emits a `StarletteDeprecationWarning: Using httpx with starlette.testclient is deprecated; install httpx2 instead` on every test run. While currently just a warning, this will become an error in a future FastAPI/Starlette release and will break the entire test suite when it does.

**Fix:** Add `httpx2` as a dev dependency, or pin `httpx` to a version compatible with the current `starlette.testclient`.

### [LOW] `db/queries.py` absent — planned read-only helper layer missing

The plan specified `db/queries.py` with helpers for `get_current_tick`, `get_latest_snapshot_tick`, and `get_world_state_at_tick`. These are not present; read queries are scattered across `dashboard/data.py`, `main.py`, and the CLI. Not a bug today, but increases surface area for duplicate query logic as the codebase grows.

### [LOW] Missing `simulation/engine.py` and `simulation/circuit_breaker.py`

The DES simulation engine and cascade circuit breaker are planned components that were not built as part of the pivot. The cascade rules (`cascade.py`) and world state (`world_state.py`) are implemented and tested. If the simulation path is ever revived, these are blocking gaps.

### [LOW] Frontend missing deck.gl / H3 / WebSocket dependencies

`frontend/package.json` has only `recharts` for visualization and no WebSocket implementation. All four spec-required packages (`deck.gl`, `maplibre-gl`, `react-map-gl`, `h3-js`) are absent. The current polling-based React dashboard is intentional for the pivot, but means the original H3 geospatial visualization spec is entirely unimplemented. Flag if the simulation path is ever revisited.

---

## Recommendations

1. **Immediately:** Wire `cli/brief.py`, `scoring/ledger.py`, `scoring/tracker.py`, and `scoring/scorecard.py` through `DbWriter.enqueue()`. The queue is already built; this is a wiring task. Until fixed, do not run the API `/api/brief/run` endpoint concurrently with a CLI cron job against the same DB file.

2. **This sprint:** Fix the `bench` test collection failure — either move bench tests to a subdirectory with a marker or add `numpy`/`pandas` to dev extras. `pytest tests/` must pass cleanly for new contributors.

3. **This sprint:** Tighten `requires-python = ">=3.12"` and update the `httpx`/`httpx2` deprecation in the test client.

4. **Backlog:** Implement `ingestion/dedup.py` with `all-MiniLM-L6-v2` semantic dedup to avoid double-counting near-duplicate GDELT events before they reach prediction models.

5. **Backlog:** Consolidate repeated read query patterns into `db/queries.py`.

---

## Test Coverage Summary

| Area | Tests | Status |
|---|---|---|
| Core pipeline (brief, predictions, ledger, tracker, scorecard) | 433 | **All pass** |
| Skipped (requires live API keys) | 13 | Skipped |
| `bench` extras (calibration metrics, recalibrators, selective) | 4 files | **Collection ERROR** |
| Agent swarm, H3 spatial, DES engine, semantic dedup | — | **Not implemented** |
