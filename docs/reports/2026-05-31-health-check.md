# Parallax Health Check — 2026-05-31

**Status: YELLOW**

## Summary

378 of 408 collected tests pass (92.6%). All 17 failures share a single root cause: `pytz` is not installed but DuckDB requires it to process `TIMESTAMPTZ` column queries. The project has also undergone a substantial, intentional architectural pivot away from the Phase 1 spec (50-agent swarm + H3 hex map) toward a focused prediction market edge-finder — this is reflected in CLAUDE.md but the Phase 1 spec document no longer describes the live system. Two secondary issues are notable: `truthbrush` and `fastapi` (for `TestClient`) are absent from the test environment, and the `DbWriter` single-writer queue exists but is bypassed by most write paths.

---

## Issues Found

### [CRITICAL] Missing `pytz` dependency — 17 test failures
- **Root cause:** `pyproject.toml` does not declare `pytz`, and it is not installed in the environment. DuckDB throws `InvalidInputException: Required module 'pytz' failed to import` whenever it reads a `TIMESTAMPTZ`-typed column (used in `runs`, `llm_usage`, `ops_events`, `crisis_events`).
- **Failing tests:** `test_llm_usage`, `test_ops_events`, `test_crisis_context_db` (4 tests), `test_phase1_critical` (1 test), `test_scorecard` (10 tests).
- **Fix:** Add `pytz` to `pyproject.toml` dependencies.

### [HIGH] DuckDB single-writer not enforced
- **Spec requirement:** All writes must go through a centralized `asyncio.Queue` (`DbWriter`). Concurrent writes to a file-backed DuckDB cause `database is locked`.
- **Reality:** `DbWriter` exists and is correct, but the following modules write directly via `conn.execute(...)`:
  - `budget/tracker.py` → `llm_usage`
  - `ops/alerts.py` → `ops_events`
  - `scoring/ledger.py` → `signal_ledger`
  - `scoring/prediction_log.py` → `prediction_log`
  - `scoring/tracker.py` → `trade_orders`, `trade_positions`, `trade_fills`
  - `scoring/scorecard.py` → `daily_scorecard`
  - `scoring/resolution.py` → `signal_ledger`, `trade_positions`
  - `cli/brief.py` → `runs`, `market_prices`
  - `contracts/registry.py` → `contract_proxy_map`, `contract_registry`
  - `ingestion/crisis_ingester.py` → `crisis_events`
  - `backtest/runner.py` → `backtest_runs`, `backtest_predictions`
- **Current risk:** Low — all paths run within a single asyncio event loop, so writes are naturally serialized. Risk becomes real if any two paths are awaited concurrently (e.g., background tasks + API requests both writing simultaneously).
- **Fix:** Route writes through `DbWriter.enqueue()` or document the intentional deviation from the spec (e.g., "CLI is synchronous; no concurrent writer risk").

### [HIGH] Architecture pivot not reflected in spec documents
- **The Phase 1 spec** (`docs/superpowers/specs/2026-03-30-parallax-phase1-design.md`) describes a 50-agent LLM swarm, H3 hex map (deck.gl/MapLibre), GDELT BigQuery ingestion with 4-stage semantic dedup, discrete event simulation, WebSocket real-time updates, and a prompt versioning/eval framework.
- **The actual product** is a prediction market edge-finder: 3 Claude Sonnet prediction models (oil price, ceasefire, Hormuz reopening), Kalshi/Polymarket market price comparison, signal ledger, paper trading, and a polling-based React dashboard.
- **Modules in plan but absent:**
  - `agents/` (50-agent roster, registry, router, runner, country_agent, YAML prompts)
  - `spatial/` (H3 utilities, Overture Maps/Searoute loader)
  - `eval/` (prediction scoring, ground truth fetcher, prompt versioning, improvement pipeline)
  - `api/` (WebSocket handler, auth middleware)
  - `simulation/circuit_breaker.py`, `simulation/engine.py`
- **Frontend:** Missing `HexMap.tsx`, `AgentFeed.tsx`, `Timeline.tsx`, `PredictionCards.tsx`, `HexPopover.tsx`, `useWebSocket.ts`, `useHexData.ts`. The frontend uses REST polling (`usePolling`) instead of WebSocket. `deck.gl`, `MapLibre`, `h3-js` are absent from `package.json`.
- **Assessment:** CLAUDE.md accurately documents the current system. The spec docs are historical artifacts, not active targets. No code action required, but the spec files are misleading to future readers.

### [MEDIUM] Missing dependencies not declared in `pyproject.toml`
- `pytz` — required by DuckDB for TIMESTAMPTZ (causes 17 test failures)
- `truthbrush` — declared but causes import failure in test collection (`test_truth_social.py` cannot be collected)
- `sentence-transformers`, `h3`, `searoute`, `shapely`, `google-cloud-bigquery` — present in original spec but not in current `pyproject.toml`; only relevant if original plan modules are resumed
- `fastapi` — declared as a runtime dependency but not installed in the test environment, causing `test_dashboard_endpoints.py` to fail collection

### [MEDIUM] Test collection errors (2 test files uncollectable)
- `tests/test_dashboard_endpoints.py` — requires `fastapi.testclient.TestClient` (`fastapi` not installed in test env)
- `tests/test_truth_social.py` — requires `truthbrush` which is not installed

### [LOW] Spec/plan file structure divergence
- Plan specifies `ingestion/gdelt.py`; actual is `ingestion/gdelt_doc.py` (GDELT DOC 2.0 API, not BigQuery)
- Plan specifies `db/queries.py`; file does not exist (query logic is embedded in `dashboard/data.py`)
- `backtest/` module is present in code but not in the Phase 1 plan (added post-plan)
- `prediction/ensemble.py`, `prediction/crisis_context.py`, `contracts/mapping_policy.py`, `portfolio/` — all additions beyond the Phase 1 spec, which is fine given the pivot

### [LOW] `requires-python` version mismatch
- `pyproject.toml` specifies `requires-python = ">=3.11"`, but CLAUDE.md and the original plan specify Python 3.12. The runtime Python is 3.11.15. This is a documentation inconsistency; the code works on 3.11 so `>=3.11` is accurate.

### [LOW] Budget tracker pricing may be stale
- `budget/tracker.py` prices: Haiku `$0.001/$0.005` per 1K tokens, Sonnet `$0.003/$0.015`. Current Claude Haiku 4.5 pricing is `$0.0008/$0.004` — close but not exact. Sonnet 4.6 matches. Impact: minor cost tracking inaccuracy.

---

## Recommendations

1. **Fix immediately:** Add `pytz` to `pyproject.toml` dependencies. This resolves all 17 test failures with one line.

2. **Fix soon:** Install `fastapi` test dependency properly (it should already be a runtime dep — confirm the test environment runs `pip install -e ".[dev]"`) and verify `truthbrush` is installable.

3. **Document the single-writer exception:** Since the CLI is synchronous and the API event loop serializes writes naturally, the direct-write pattern is not causing bugs today. Either add a note to `db/writer.py` explaining why it's unused, or route the highest-frequency write paths (`signal_ledger`, `llm_usage`) through the queue as insurance against future async concurrency.

4. **Archive the Phase 1 spec:** Mark `docs/superpowers/specs/2026-03-30-parallax-phase1-design.md` and `docs/superpowers/plans/2026-03-30-parallax-phase1.md` as historical/superseded to avoid confusion. CLAUDE.md is the authoritative architecture reference.

5. **CI guard:** The missing `pytz` has persisted across multiple health-check cycles (YELLOW since at least 2026-05-20). Add a `pip check` or `python -c "import pytz"` step to any CI pipeline to catch undeclared runtime deps before they accumulate.
