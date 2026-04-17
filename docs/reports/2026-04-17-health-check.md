# Parallax Health Check — 2026-04-17

**Status: YELLOW**

The implementation is functional for its stated purpose (prediction market edge-finder) but has diverged substantially from the original design spec (geopolitical cascade simulator with 50-agent swarm). Within the actual scope, code quality is solid with several addressable issues — most critically, the DuckDB single-writer pattern is violated in multiple scoring modules.

---

## Spec / Plan Consistency

The original spec (`2026-03-30-parallax-phase1-design.md`) describes a geopolitical cascade simulator with an H3 hexagonal grid, ~50 LLM agents in a country/sub-actor hierarchy, GDELT BigQuery ingestion, deck.gl visualization, and a WebSocket-driven frontend. The actual implementation is a prediction market edge-finder that uses 3 Claude Sonnet prediction models, Kalshi/Polymarket APIs, and a REST-polled React dashboard.

This is a **deliberate product pivot**, not an accident — CLAUDE.md fully documents the new direction. However, the original spec and plan documents are now stale and describe a different product.

- **[HIGH]** Spec documents describe a product that no longer exists. `docs/superpowers/specs/2026-03-30-parallax-phase1-design.md` and `docs/superpowers/plans/2026-03-30-parallax-phase1.md` should be archived or superseded with a Phase 1b spec reflecting actual implementation.
- **[MEDIUM]** Plan tasks are tracked with `- [ ]` checkboxes but none appear checked; the plan can no longer be used as a progress tracker.

---

## Dependency Audit

### Backend (`pyproject.toml`)

| Issue | Severity |
|-------|----------|
| `requires-python = ">=3.11"` but CLAUDE.md specifies Python 3.12 | LOW |
| `truthbrush>=0.2` — niche library with no upper-bound pin; unmaintained risk | LOW |
| Missing `h3>=4.1`, `sentence-transformers>=3.4`, `searoute>=1.3`, `shapely>=2.0`, `google-cloud-bigquery>=3.27`, `websockets>=14.0` (all in CLAUDE.md as key dependencies but absent from `pyproject.toml`) | HIGH |
| `anthropic>=0.52` with no upper bound — breaking changes risk if Anthropic releases SDK v1.x | LOW |
| No `anyio`, `starlette` pins — FastAPI transitive deps left uncontrolled | LOW |

### Frontend (`package.json`)

| Issue | Severity |
|-------|----------|
| Plan required `deck.gl`, `MapLibre GL`, `react-map-gl`, `h3-js` — none present; frontend has pivoted to `recharts` only | INFO (intentional) |
| `recharts@^2.15.0` is current; no known CVEs | OK |
| No `@types/node` pin — Vite may break on Node.js minor updates | LOW |

---

## Code Quality Issues

### DuckDB Single-Writer Violations — HIGH

The spec mandates all writes go through `DbWriter`'s `asyncio.Queue`. The following modules bypass the queue and call `conn.execute()` directly:

- `scoring/prediction_log.py` — inserts prediction records directly
- `scoring/ledger.py` — inserts signal records directly
- `scoring/scorecard.py` — upserts daily scorecard metrics directly
- `scoring/calibration.py` — likely direct (follows same pattern)
- `scoring/tracker.py` — paper trade writes likely direct

**Risk:** Concurrent writes from different asyncio tasks can cause DuckDB `database is locked` errors. This won't fail silently in a load scenario.

### Missing Error Handling at Boundaries — MEDIUM

- `ingestion/google_news.py`: No `timeout=` on RSS HTTP fetch; 7 queries may block indefinitely on network hang
- `ingestion/gdelt_doc.py`: No `httpx.NetworkError` / `httpx.TimeoutException` catch; 429 handling noted in CLAUDE.md but retry logic absent
- `prediction/oil_price.py`, `ceasefire.py`, `hormuz.py`: `build_track_record()` call not wrapped in try/except — a DB error here silently degrades the prediction context without warning
- `db/writer.py:40-46`: Exception logged but no retry; failed writes are silently dropped

### Type Safety / Logic Bugs — MEDIUM

- `markets/kalshi.py`: `_coerce_price()` divides by 100 if value > 1.0, assuming percentage input — if Kalshi ever returns raw cents (non-standard), this silently corrupts prices
- `divergence/detector.py`: `entry_price_is_executable` set to `True` for any signal meeting edge threshold, but no quote depth or staleness validation is performed
- `scoring/scorecard.py` direct writes: no transaction wrapping — a crash mid-scorecard leaves a partial day's metrics

### No Idempotency Constraints — MEDIUM

Running `parallax-brief` twice in the same run creates duplicate records in `prediction_log` and `signal_ledger` (no unique constraint on `run_id + model_id`). Historical metrics in `daily_scorecard` are computed from these tables and will double-count.

---

## Test Coverage Gaps

The actual 35 test files cover the real implementation well. Gaps relative to production risk:

| Missing Test | Reason | Severity |
|---|---|---|
| No end-to-end integration test | `test_integration.py` was planned but not created | HIGH |
| No test for DuckDB writer queue pattern (concurrent writes) | `test_writer.py` exists but tests sequential only | MEDIUM |
| No test for Kalshi price coercion edge cases (cents vs decimal) | `test_kalshi.py` exists but coercion not tested | MEDIUM |
| No test for `entry_price_is_executable` logic in divergence detector | `test_divergence.py` exists; executable flag not tested | MEDIUM |
| No test for `fetch_google_news()` timeout/retry behavior | `test_google_news.py` exists; network error paths not tested | LOW |
| No test for duplicate-run idempotency in signal_ledger | No test file covers this path | MEDIUM |

Tests present but not in original plan (good additions): `test_brief.py`, `test_kalshi.py`, `test_divergence.py`, `test_ensemble.py`, `test_mapping_policy.py`, `test_portfolio_simulator.py`, `test_scorecard.py`.

---

## Architecture Drift

Relative to spec — all intentional pivots:

| Spec | Actual | Impact |
|---|---|---|
| `agents/` module (50 LLM agents, registry, router, prompts/) | `prediction/` (3 Claude Sonnet models) | Intentional scope reduction |
| `spatial/` module (H3 cell chains, Overture Maps, Searoute) | Not present | Intentional |
| `eval/` module (prompt versioning, improvement pipeline) | `scoring/` (calibration, scorecard, resolution) | Partial overlap; eval meta-agent missing |
| `api/` sub-module with WebSocket handler | Routes in `main.py`, no WebSocket | Intentional; REST polling used instead |
| Auth middleware (invite codes, admin password) | Not implemented | Gap — CLAUDE.md mentions admin password env var but no middleware |
| Frontend: deck.gl + H3 map, agent feed, timeline | Recharts dashboard, portfolio panel, markets table | Intentional pivot |
| Deployment: Vercel + Railway/Fly | Docker Compose locally | Intentional for v1 |

One genuine gap (not intentional): **auth middleware is absent**. CLAUDE.md references `PARALLAX_ADMIN_PASSWORD` and `PARALLAX_INVITE_SEED` env vars, and the spec requires invite-code gating and admin mode, but no auth enforcement exists in `main.py`.

---

## Recommendations

1. **[P0] Fix DuckDB writer violations** in `prediction_log.py`, `ledger.py`, `scorecard.py`. These modules receive a `conn` directly — pass `DbWriter` instead and call `enqueue()`. This prevents lock errors under concurrent load.

2. **[P1] Add HTTP timeouts and retry** in `google_news.py` and `gdelt_doc.py`. Use `httpx.AsyncClient(timeout=10.0)` and a simple exponential backoff on 429/5xx.

3. **[P1] Add idempotency guard** in `signal_ledger` and `prediction_log`: add `UNIQUE (run_id, model_id)` constraints or a pre-insert existence check to prevent double-counting on re-runs.

4. **[P2] Add integration test** — one test that exercises the full brief pipeline (dry-run) end to end and asserts that signals and predictions are written exactly once.

5. **[P2] Archive stale spec/plan docs** — add a header note to both documents pointing to the current CLAUDE.md as the authoritative architecture reference.

6. **[P3] Align `pyproject.toml`** — add `h3>=4.1` and `websockets>=14.0` (referenced in CLAUDE.md as key dependencies) and pull `requires-python` up to `>=3.12`.

7. **[P3] Implement minimal auth middleware** — env-var admin password check on `/api/brief/run` and `/api/scorecard` endpoints if these will be exposed externally.
