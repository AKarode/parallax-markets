# Parallax Repo Health Check — 2026-07-15

**Status: YELLOW**

No source-code changes have landed since the 2026-07-14 check. All YELLOW issues documented there persist unchanged. The codebase continues to function for its prediction-market edge-finder direction; structural gaps are stable and non-regressing.

---

## Summary

Zero source-code commits between the 2026-07-14 health check and today. The two commits that landed were documentation only (tech-research report + health-check report). All issues from yesterday remain open with no new issues introduced. Test count is unchanged at 494 tests across 47 test files.

---

## Delta From Yesterday (2026-07-14)

| Area | Change |
|------|--------|
| Source code commits | 0 |
| New issues | 0 |
| Resolved issues | 0 |
| Test count | 494 (unchanged) |

Full issue details are in [2026-07-14-health-check.md](2026-07-14-health-check.md). Summary below for completeness.

---

## Issues Found (Carried Over)

### [HIGH] DuckDB Single-Writer Pattern Violated Across the Codebase

The spec declares the asyncio.Queue single-writer pattern a **hard constraint**. `db/writer.py` implements `DbWriter` correctly but no production path uses it. Twelve files write directly to DuckDB via `conn.execute()`:

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
| `db/schema.py` | UPDATE `signal_ledger` (migration backfills — intentional one-time) |

Immediate risk is bounded because the app is single-process asyncio, but concurrent coroutines calling `conn.execute()` without yielding can still contend on DuckDB's per-statement write lock. `DbWriter` exists, is tested, but does nothing in production.

### [HIGH] Core Simulation Infrastructure Not Built (Intentional Pivot)

These planned modules are absent. The product has pivoted from simulation to prediction-market edge-finding, so this is informational rather than blocking, but spec tests are also absent:

- `simulation/engine.py` — DES tick loop
- `simulation/circuit_breaker.py` — escalation limits
- `agents/` package — runner, router, country agent, prompts, registry
- `eval/` package — prediction scoring, ground truth, prompt versioning
- `api/websocket.py` — real-time push
- `api/auth.py` — invite code + admin password
- `spatial/` package — H3 utilities and route loader

### [MEDIUM] Missing Dependencies for Planned Features

These packages are absent from `pyproject.toml` and would fail on a clean install if any dormant spec features are revisited:

- `h3>=4.1` (spatial indexing)
- `sentence-transformers>=3.4` (semantic dedup)
- `searoute>=1.3` (shipping route visualization)
- `shapely>=2.0` (geometric operations)
- `google-cloud-bigquery>=3.27` (GDELT BigQuery source)
- `cryptography` (used by `markets/kalshi.py` for RSA-PSS auth — not declared, installed only as a transitive dep)

`requires-python = ">=3.11"` in `pyproject.toml` conflicts with CLAUDE.md (`>=3.12`) and actual code (`str | None` union syntax throughout).

### [MEDIUM] Frontend Architecture Differs from Spec

Spec called for deck.gl + MapLibre H3 hex map with WebSocket-driven real-time updates. Actual frontend is a polling-based REST dashboard (Recharts, `usePolling` hook). No `HexMap`, `AgentFeed`, `Timeline`, or `HexPopover` components exist. The actual component set (`KpiBar`, `MarketsTable`, `ModelCards`, `PortfolioPanel`) fits the new product direction but does not match the spec.

### [LOW] GDELT BigQuery Replaced With DOC API

Plan called for `ingestion/gdelt.py` with BigQuery + 4-stage filter + sentence-transformers semantic dedup. Actual: `ingestion/gdelt_doc.py` using the GDELT DOC 2.0 HTTP API. Named-entity override stage and semantic dedup stage are absent. `ingestion/crisis_ingester.py` uses `SequenceMatcher` (stdlib) in place of embedding-based cosine similarity.

### [LOW] `portfolio/` Missing `__init__.py`

`backend/src/parallax/portfolio/` has no `__init__.py`, making it a namespace package rather than a regular package. Works on CPython 3.3+ but can cause import surprises with some tooling and is inconsistent with every other package in the project.

---

## Recommendations (Unchanged)

1. **[Immediate]** Either wire `DbWriter.enqueue()` into write-heavy production paths, or explicitly document in code that the single-writer constraint is relaxed for this single-process asyncio topology. The class exists, is tested, and is misleadingly unused.

2. **[Short-term]** Add `cryptography` to `pyproject.toml` dependencies. Currently installed only as a transitive dep of another package — can break on a clean install ordering change.

3. **[Short-term]** Pin `requires-python = ">=3.12"` to match the codebase and CLAUDE.md.

4. **[Short-term]** Add `backend/src/parallax/portfolio/__init__.py` (empty file) for consistency.

5. **[Optional]** Add a successor spec document describing the actual prediction-market edge-finder architecture, so `docs/superpowers/specs/2026-03-30-parallax-phase1-design.md` doesn't confuse future contributors.
