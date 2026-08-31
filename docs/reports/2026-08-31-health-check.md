# Parallax Health Check — 2026-08-31

**Status: YELLOW**

## Summary

No code changes landed since yesterday's check. All HIGH-severity DuckDB single-writer violations carry forward unchanged for a fifth consecutive day — `DbWriter` remains dead code with zero production call sites. Core test suite is clean (433 passed, 13 skipped, excluding bench extras). Today's scan surfaced three previously unreported issues: a hardcoded `dry_run=True` in the API brief endpoint, a missing `portfolio/__init__.py`, and schema migration UPDATEs running unconditionally on every startup.

---

## Issues Found

### HIGH — DuckDB Single-Writer Violations (Unaddressed, Day 5)

`db/writer.py` is correctly implemented but bypassed by every production write path. `DbWriter` has no production call sites. Under concurrent access (FastAPI async handlers, parallel CLI + API runs), DuckDB file locking will produce `database is locked` errors.

- **`[HIGH]`** `cli/brief.py:130,150,432` — direct INSERT/UPDATE into `runs` and `market_prices` tables (`_persist_run_start`, `_persist_run_end`, `_persist_market_prices`)
- **`[HIGH]`** `scoring/ledger.py:225,256` — direct INSERT/UPDATE on every signal record
- **`[HIGH]`** `scoring/tracker.py:460,516,672` — 3 direct writes across paper trade lifecycle
- **`[HIGH]`** `scoring/scorecard.py:21` — direct INSERT/ON CONFLICT for daily scorecard ETL
- **`[HIGH]`** `scoring/resolution.py:60,124` — direct UPDATEs during settlement polling
- **`[HIGH]`** `scoring/prediction_log.py:79` — direct INSERT for prediction persistence
- **`[HIGH]`** `contracts/registry.py:85,105,114,198` — direct INSERT/UPDATEs for contract upserts
- **`[HIGH]`** `budget/tracker.py:43` — direct INSERT on every LLM call (highest frequency writer)
- **`[HIGH]`** `ingestion/crisis_ingester.py:79` — direct INSERT during ingestion
- **`[HIGH]`** `ops/alerts.py:106` — direct INSERT for alert logging

Risk is latent in sequential CLI mode but real under FastAPI async handlers or concurrent invocations.

### MEDIUM — `POST /api/brief/run` Hardcodes `dry_run=True` (Newly Documented)

`main.py:252` forces `dry_run=True, no_trade=True` on every API-triggered brief run, regardless of runtime configuration. The `POST /api/brief/run` endpoint cannot trigger a live prediction run or paper trade from the API. This may be intentional safety behavior but is undocumented.

**Fix:** Add a comment explaining the intent, or accept a `dry_run` query param so callers can opt into live mode when appropriate.

### MEDIUM — 4 Bench Test Collection Failures (Unaddressed, Day 5)

`test_bench_forecast.py`, `test_calibration_metrics.py`, `test_recalibrators.py`, `test_selective.py` fail at collection with `ModuleNotFoundError: No module named 'pandas'` / `numpy`. Bench extras are not installed by `pip install -e ".[dev]"`.

**Fix:** Add `pytest.importorskip("numpy")` as the first import guard in each affected file, or add a `tests/bench/` directory excluded from default pytest runs.

### MEDIUM — Architecture Drift from Phase 1 Spec (Intentional Pivot, Spec Stale, Day 35+)

`docs/superpowers/specs/2026-03-30-parallax-phase1-design.md` and `docs/superpowers/plans/2026-03-30-parallax-phase1.md` describe systems that were never built and are not planned. The actual codebase (3 LLM prediction models → Kalshi/Polymarket divergence → paper trading scorecard) is a coherent different product.

| Spec Component | Status |
|---|---|
| `agents/` — 50-agent LLM swarm | Not built |
| `spatial/` — H3 / Searoute visualization | Not built |
| Frontend H3 hex map (deck.gl + MapLibre) | Not built; Recharts polling dashboard used instead |
| WebSocket streaming | Not built; `usePolling.ts` used instead |
| `eval/` — prediction eval framework | Not built; replaced by `scoring/` pipeline |

### LOW — Schema Migration UPDATEs Run Unconditionally on Every Startup (Newly Documented)

`db/schema.py:605–641` runs data-backfill UPDATE statements inside `_migrate_legacy_tables()` on every `create_tables()` call. On a large database these unconditional UPDATEs add startup latency. They are safe (use `COALESCE`) but should be guarded by a migration version flag to become no-ops after first run.

### LOW — `portfolio/` Missing `__init__.py` (Newly Documented)

`backend/src/parallax/portfolio/` has no `__init__.py`. All other sub-packages have one. Imports work due to `src/` layout discovery by hatchling, but the inconsistency is fragile.

**Fix:** `touch backend/src/parallax/portfolio/__init__.py`

### LOW — Private `KalshiClient._request()` Called from `brief.py`

`cli/brief.py:932` calls `client._request("GET", "/markets", ...)` — a private method on `KalshiClient`. If the internal method signature changes, this call breaks silently with no public contract violation.

**Fix:** Expose a public `get_markets()` method on `KalshiClient` and call that instead.

### LOW — `dashboard/app.py` Opens New DuckDB Connection Per Streamlit Rerun (Newly Documented)

`dashboard/app.py:686` calls `duckdb.connect(db_path, read_only=True)` inside the Streamlit `main()` function, which runs on every user interaction. This creates a new connection object per rerun without explicit cleanup. The `read_only=True` mode prevents write-lock contention, but connection churn adds overhead.

**Fix:** Cache the connection with `@st.cache_resource`.

### LOW — CLAUDE.md Technology Stack Section Stale (Ongoing)

CLAUDE.md lists `deck.gl 9.1.0`, `MapLibre GL 4.7.0`, `h3-js`, `react-map-gl`, `sentence-transformers`, `searoute`, `shapely`, `websockets`, `google-cloud-bigquery` as dependencies. None appear in `frontend/package.json` or `backend/pyproject.toml`. Actual frontend uses only `react`, `react-dom`, and `recharts`.

### LOW — Uncontrolled Files at Repo Root

`interface_out_A.md`, `interface_out_B.md`, `interface_out_C.md`, `interface_out_D.md` exist at the repo root with no apparent ownership or purpose. These appear to be scratchpad artifacts.

### LOW — `anthropic` SDK Lower Bound Stale

`pyproject.toml` specifies `anthropic>=0.52`. Installed version is `1.2.0`. The SDK moved through a major breaking version between 0.x and 1.x. The lower bound should be updated to `>=1.0` to reflect the actual minimum-compatible version.

### LOW — Python Version Mismatch in Docs

`pyproject.toml` specifies `requires-python = ">=3.11"` while CLAUDE.md documents Python 3.12. No functional impact.

---

## Recommendations

1. **Wire DbWriter into production write paths (HIGH, priority 1).** The highest-frequency writers (`budget/tracker.py`, `scoring/ledger.py`, `scoring/tracker.py`) should route through `DbWriter.enqueue()` first. `cli/brief.py`'s 3 direct connection opens are the highest structural risk.

2. **Document or fix the `dry_run=True` lock in `POST /api/brief/run` (MEDIUM).** A comment at minimum; a query param if live API triggering is desired.

3. **Fix bench test collection failures (MEDIUM).** Three-line `pytest.importorskip` guards unblock clean `pytest` runs without installing heavy bench dependencies.

4. **Add `portfolio/__init__.py` (LOW).** One-line fix for package consistency.

5. **Replace `client._request()` with a public method (LOW).** Add `KalshiClient.get_raw_markets()` and update `brief.py:932`.

6. **Cache Streamlit DuckDB connection with `@st.cache_resource` (LOW).** Eliminates per-rerun connection churn in `dashboard/app.py`.

7. **Update or supersede the Phase 1 spec (LOW).** The spec has been stale for five months. An ADR documenting the pivot would prevent future confusion.
