# Parallax Repo Health Check — 2026-07-16

**Status: YELLOW**

No source-code changes have landed since the 2026-07-15 check. One documentation commit (tech-research report) landed. All YELLOW issues from yesterday persist unchanged.

---

## Summary

Zero source-code commits between the 2026-07-15 health check and today. The codebase continues to function for its prediction-market edge-finder direction: 433 tests pass, 13 skip, 4 test files fail to collect due to missing `numpy`/`pandas` in the base dependency set. All structural gaps identified in previous checks remain open and stable.

---

## Delta From Yesterday (2026-07-15)

| Area | Change |
|------|--------|
| Source code commits | 0 |
| Documentation commits | 1 (tech-research report) |
| New issues | 0 |
| Resolved issues | 0 |
| Tests passing | 433 (unchanged) |
| Tests skipped | 13 (unchanged) |
| Test files failing to collect | 4 (unchanged) |

Full issue details carried from [2026-07-15-health-check.md](2026-07-15-health-check.md). Reproduced below for completeness.

---

## Issues Found (Carried Over)

### [HIGH] DuckDB Single-Writer Pattern Violated Across the Codebase

The spec declares the asyncio.Queue single-writer pattern a **hard constraint**. `db/writer.py` implements `DbWriter` correctly and is tested, but no production path uses it. Twelve files write directly to DuckDB via `conn.execute()`:

| File | Write Operations |
|------|-----------------|
| `scoring/ledger.py` | INSERT + UPDATE `signal_ledger` |
| `scoring/tracker.py` | INSERT/UPDATE `trade_orders`, `trade_fills`, `trade_positions` |
| `scoring/resolution.py` | UPDATE `signal_ledger`, UPDATE `trade_positions` |
| `scoring/prediction_log.py` | INSERT `prediction_log` |
| `scoring/scorecard.py` | INSERT `daily_scorecard` |
| `contracts/registry.py` | INSERT OR REPLACE + DELETE + UPDATE `contract_registry` / `contract_proxy_map` |
| `ingestion/crisis_ingester.py` | INSERT `crisis_events` |
| `ops/alerts.py` | INSERT `ops_events` (inside an async method) |
| `backtest/runner.py` | INSERT/UPDATE `backtest_runs`, `backtest_predictions` |
| `cli/brief.py` | INSERT `runs`, UPDATE `runs`, INSERT `market_prices` |
| `budget/tracker.py` | INSERT `llm_usage` |
| `db/schema.py` | UPDATE `signal_ledger` (migration backfills — one-time) |

Immediate risk is bounded because the app is single-process asyncio with `asyncio.run()` in the CLI. However, the FastAPI server (`main.py`) shares a single `app.state.db` connection across concurrent request handlers; concurrent writes from async endpoints could contend on DuckDB's per-statement write lock. `DbWriter` exists, is tested, and is misleadingly unused.

### [HIGH] Core Simulation Infrastructure Not Built (Intentional Pivot)

These planned modules are absent. The product has pivoted from geopolitical cascade simulation to prediction-market edge-finding, so this is informational rather than blocking:

- `simulation/engine.py` — DES tick loop (heapq priority queue)
- `simulation/circuit_breaker.py` — escalation limits and cooldowns
- `agents/` package — runner, router, country agent, prompts, 50-agent registry
- `eval/` package — prediction scoring, ground truth, prompt versioning pipeline
- `api/websocket.py` — real-time push channel
- `api/auth.py` — invite code + admin password middleware
- `spatial/` package — H3 utilities and Overture/Searoute route loader

The spec tests for these modules (`test_h3_utils.py`, `test_dedup.py`, `test_agent_schemas.py`, `test_agent_router.py`, `test_agent_runner.py`, `test_circuit_breaker.py`, `test_prompt_versioning.py`, `test_auth.py`, `test_integration.py`) do not exist. New tests covering the actual pivot architecture are comprehensive.

### [MEDIUM] 4 Test Files Fail to Collect — Missing `numpy`/`pandas` in Base Deps

`test_bench_forecast.py`, `test_calibration_metrics.py`, `test_recalibrators.py`, and `test_selective.py` import `numpy` / `pandas` at module level, but those packages are only in the `[bench]` optional extras group. Running `pytest tests/` on a clean `pip install -e ".[dev]"` produces 4 import errors, interrupting collection before any tests run. These files need either a `pytest.importorskip("numpy")` guard or the packages need to move to core deps.

### [MEDIUM] Missing Dependencies for Planned Features

These packages are absent from `pyproject.toml` and would fail on a clean install:

- `cryptography` — used by `markets/kalshi.py` for RSA-PSS auth; currently works only as a transitive dependency of another package, which is fragile
- `h3>=4.1` — spatial indexing (spec feature, not yet built)
- `sentence-transformers>=3.4` — semantic dedup (spec feature)
- `searoute>=1.3` — shipping route visualization (spec feature)
- `shapely>=2.0` — geometric operations (spec feature)
- `google-cloud-bigquery>=3.27` — GDELT BigQuery source (replaced by DOC API)
- `websockets>=14.0` — WebSocket support (spec feature, frontend uses polling instead)

`requires-python = ">=3.11"` in `pyproject.toml` conflicts with CLAUDE.md (`>=3.12`) and actual code using `str | None` union syntax throughout.

### [MEDIUM] Frontend Architecture Differs from Spec

Spec called for deck.gl + MapLibre H3 hex map with WebSocket-driven real-time updates. Actual frontend is a polling-based REST dashboard (`usePolling.ts`, Recharts). No `HexMap`, `AgentFeed`, `Timeline`, or `HexPopover` components exist. The actual component set (`KpiBar`, `MarketsTable`, `ModelCards`, `PortfolioPanel`) fits the new product direction but does not match the spec.

### [LOW] GDELT BigQuery Replaced With DOC API

Plan called for `ingestion/gdelt.py` using BigQuery with a 4-stage filter including sentence-transformers semantic dedup. Actual implementation: `ingestion/gdelt_doc.py` using the GDELT DOC 2.0 HTTP API. Named-entity override stage and embedding-based semantic dedup are absent; `ingestion/crisis_ingester.py` uses `SequenceMatcher` (stdlib) for dedup instead.

### [LOW] `portfolio/` Missing `__init__.py`

`backend/src/parallax/portfolio/` has no `__init__.py`, making it a namespace package rather than a regular package. Works on CPython 3.3+ but inconsistent with every other sub-package in the project.

---

## Recommendations (Unchanged from 2026-07-14)

1. **[Immediate]** Either wire `DbWriter.enqueue()` into write-heavy production paths, or explicitly document in code that the single-writer constraint is relaxed for this single-process asyncio topology. The class exists, is tested, and is misleadingly unused.

2. **[Short-term]** Add `cryptography` to `pyproject.toml` core dependencies. Currently installed only as a transitive dep — can break on a clean install ordering change.

3. **[Short-term]** Add `pytest.importorskip("numpy")` guards (or move `numpy`/`pandas` to dev deps) to fix the 4 test files that fail to collect.

4. **[Short-term]** Pin `requires-python = ">=3.12"` to match the codebase and CLAUDE.md.

5. **[Short-term]** Add `backend/src/parallax/portfolio/__init__.py` (empty file) for consistency.

6. **[Optional]** Add a successor spec document describing the actual prediction-market edge-finder architecture, so the original Phase 1 spec does not confuse future contributors.
