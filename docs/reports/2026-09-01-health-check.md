# Parallax Health Check — 2026-09-01

**Status: YELLOW**

## Summary

No code changes landed since yesterday's check — all 20 commits in recent history are automated daily health and tech-research reports. All HIGH-severity DuckDB single-writer violations carry forward unchanged for a sixth consecutive day: `DbWriter` remains correctly implemented but has zero production call sites. Core test suite is clean (bench extras excluded); the 4 bench test collection failures due to missing `pandas`/`numpy` also carry forward. Architecture has durably pivoted from the Phase 1 spec (agent swarm + H3 map) to a prediction-market edge-finder; spec documents remain stale but the actual product is internally consistent.

---

## Issues Found

### HIGH — DuckDB Single-Writer Violations (Unaddressed, Day 6)

`db/writer.py` is correctly implemented but bypassed by every production write path. `DbWriter` has zero production call sites. Under concurrent access (FastAPI async handlers, parallel CLI + API runs), DuckDB file locking will produce `database is locked` errors.

- **`[HIGH]`** `cli/brief.py` — direct `INSERT`/`UPDATE` into `runs` and `market_prices` tables (`_persist_run_start`, `_persist_run_end`, `_persist_market_prices`)
- **`[HIGH]`** `scoring/ledger.py` — direct `INSERT`/`UPDATE` on every signal record
- **`[HIGH]`** `scoring/tracker.py` — 3 direct writes across paper trade lifecycle
- **`[HIGH]`** `scoring/scorecard.py` — direct `INSERT ON CONFLICT` for daily scorecard ETL
- **`[HIGH]`** `scoring/resolution.py` — direct `UPDATE`s during settlement polling
- **`[HIGH]`** `scoring/prediction_log.py` — direct `INSERT` for prediction persistence
- **`[HIGH]`** `contracts/registry.py` — direct `INSERT`/`UPDATE`s for contract upserts
- **`[HIGH]`** `budget/tracker.py` — direct `INSERT` on every LLM call (highest frequency writer)
- **`[HIGH]`** `ingestion/crisis_ingester.py` — direct `INSERT` during ingestion
- **`[HIGH]`** `ops/alerts.py` — direct `INSERT` for alert logging

Risk is latent in sequential CLI mode but real under FastAPI async handlers or concurrent invocations.

### MEDIUM — `POST /api/brief/run` Hardcodes `dry_run=True`

`main.py:252` forces `dry_run=True, no_trade=True` on every API-triggered brief run, regardless of runtime configuration. The endpoint cannot trigger a live prediction run or paper trade from the API. May be intentional but is undocumented.

**Fix:** Add a comment explaining intent, or accept a `dry_run` query param so callers can opt into live mode when appropriate.

### MEDIUM — 4 Bench Test Collection Failures (Unaddressed, Day 6)

`test_bench_forecast.py`, `test_calibration_metrics.py`, `test_recalibrators.py`, `test_selective.py` fail at collection with `ModuleNotFoundError: No module named 'pandas'` / `numpy`. Bench extras not installed by `pip install -e ".[dev]"`.

**Fix:** Add `pytest.importorskip("numpy")` / `pytest.importorskip("pandas")` at the top of each affected file, or move them under a `tests/bench/` directory excluded from default pytest runs via `pytest.ini`.

### MEDIUM — Architecture Drift from Phase 1 Spec (Intentional Pivot, Spec Stale, Day 36)

`docs/superpowers/specs/2026-03-30-parallax-phase1-design.md` and `docs/superpowers/plans/2026-03-30-parallax-phase1.md` describe systems that were never built. The actual codebase is a coherent, different product.

| Spec Component | Status |
|---|---|
| `agents/` — 50-agent LLM swarm (country → sub-actor hierarchy) | Not built; replaced by 3 focused prediction models |
| `spatial/` — H3 hexagonal grid + Searoute visualization | Not built |
| Frontend H3 hex map (deck.gl + MapLibre GL) | Not built; Recharts polling dashboard used instead |
| WebSocket streaming | Not built; `usePolling.ts` used instead |
| `eval/` — GDELT semantic dedup, prediction eval pipeline | Not built; replaced by `scoring/` subsystem |
| `ingestion/dedup.py` — sentence-transformers semantic dedup | Not built |

Actual dependencies missing from pyproject.toml vs spec: `h3`, `sentence-transformers`, `searoute`, `shapely`, `google-cloud-bigquery`, `websockets`. These are simply not part of the current product.

### LOW — Schema Migration UPDATEs Run Unconditionally on Every Startup

`db/schema.py` runs data-backfill `UPDATE` statements inside `_migrate_legacy_tables()` on every `create_tables()` call. Safe (use `COALESCE`) but add startup latency at scale.

**Fix:** Guard with a `schema_version` table and make migrations no-ops after first run.

### LOW — `portfolio/` Missing `__init__.py`

`backend/src/parallax/portfolio/` has no `__init__.py`. Imports work due to `src/` layout, but the inconsistency is fragile.

**Fix:** `touch backend/src/parallax/portfolio/__init__.py`

### LOW — Private `KalshiClient._request()` Called from `cli/brief.py`

`cli/brief.py` calls `client._request("GET", "/markets", ...)` — a private method. If internal signature changes, this silently breaks.

**Fix:** Expose a public `get_markets()` method on `KalshiClient`.

### LOW — `dashboard/app.py` Opens New DuckDB Connection Per Streamlit Rerun

`dashboard/app.py` calls `duckdb.connect(db_path, read_only=True)` inside the Streamlit `main()` function (runs on every user interaction). Creates connection churn without cleanup.

**Fix:** Cache with `@st.cache_resource`.

### LOW — CLAUDE.md Technology Stack Section Stale

CLAUDE.md lists `deck.gl 9.1.0`, `MapLibre GL 4.7.0`, `h3-js`, `react-map-gl`, `sentence-transformers`, `searoute`, `shapely`, `websockets`, `google-cloud-bigquery` as dependencies. None appear in `frontend/package.json` or `backend/pyproject.toml`. Actual frontend uses only `react`, `react-dom`, and `recharts`.

---

## Recommendations

1. **Route all production writes through `DbWriter`** — highest-leverage fix; eliminates the latent concurrency bug. Estimated effort: 2–4 hours touching ~10 call sites.
2. **Fix bench test collection** — add `pytest.importorskip` guards; 10-minute fix.
3. **Document or parameterize `dry_run=True` on the API endpoint** — avoids confusion for anyone attempting live runs via the API.
4. **Update CLAUDE.md** to reflect the actual tech stack (Recharts, polling, 3 LLM prediction models) and retire the stale Phase 1 spec references.
5. **Spec documents** — consider archiving `2026-03-30-parallax-phase1-design.md` and `2026-03-30-parallax-phase1.md` to a `docs/archive/` directory to avoid confusion in future automated checks.
