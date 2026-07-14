# Parallax Repo Health Check — 2026-07-14

**Status: YELLOW**

No code changes have landed since yesterday's check (2026-07-13). All issues documented there persist unchanged. The codebase continues to function for its current product direction (prediction market edge-finder) while carrying the same structural gaps.

---

## Summary

The repo had zero source-code commits since the 2026-07-13 health check (only two report/research docs were added). All YELLOW issues identified yesterday remain open. The codebase is stable but has a persistent gap between its spec's DuckDB single-writer requirement and its implementation, and the original simulation/agent architecture from the Phase 1 spec has not been built (intentional product pivot). Test coverage is strong at 494 tests across 47 test files.

---

## Delta From Yesterday (2026-07-13)

| Area | Change |
|------|--------|
| Source code commits | 0 |
| New issues | 0 |
| Resolved issues | 0 |
| Test count | 494 (unchanged) |

Full issue details are in [2026-07-13-health-check.md](2026-07-13-health-check.md). Summary below for completeness.

---

## Issues Found (Carried Over)

### [HIGH] DuckDB Single-Writer Pattern Violated Across the Codebase

The spec declares the asyncio.Queue single-writer pattern a **hard constraint**. `db/writer.py` implements `DbWriter` correctly but no production code uses it. The following 12 files write directly to DuckDB via `conn.execute()`:

| File | Write Operations |
|------|-----------------|
| `scoring/ledger.py` | INSERT + UPDATE `signal_ledger` |
| `scoring/tracker.py` | INSERT/UPDATE `trade_orders`, `trade_fills`, `trade_positions` |
| `scoring/resolution.py` | UPDATE `signal_ledger`, UPDATE `trade_positions` |
| `scoring/prediction_log.py` | INSERT `prediction_log` |
| `scoring/scorecard.py` | INSERT `daily_scorecard` |
| `contracts/registry.py` | INSERT OR REPLACE + DELETE + UPDATE `contract_registry` / `contract_proxy_map` |
| `ingestion/crisis_ingester.py` | INSERT `crisis_events` |
| `ops/alerts.py` | INSERT `ops_events` |
| `backtest/runner.py` | INSERT/UPDATE `backtest_runs`, `backtest_predictions` |
| `cli/brief.py` | INSERT `runs`, UPDATE `runs`, INSERT `market_prices` |
| `budget/tracker.py` | INSERT `llm_usage` |
| `db/schema.py` | UPDATE `signal_ledger` (migration backfills — intentional) |

The immediate risk is lower than a multi-process deployment because the app is single-process asyncio, but any two coroutines calling `conn.execute()` concurrently without yielding can still contend on DuckDB's per-statement write lock. `DbWriter` is the intended fix and remains unused.

### [HIGH] Core Simulation Infrastructure Not Built (Intentional Pivot)

These planned modules are absent. The product has pivoted, so this is informational, but it means the spec tests are also missing:

- `simulation/engine.py` — DES tick loop
- `simulation/circuit_breaker.py` — escalation limits
- `agents/` package — runner, router, country agent, prompts, registry
- `eval/` package — prediction scoring, ground truth, prompt versioning
- `api/websocket.py` — real-time push
- `api/auth.py` — invite code + admin password
- `spatial/` package — H3 utilities and route loader

### [MEDIUM] Missing Dependencies for Planned Features

These packages are absent from `pyproject.toml` and would fail silently if any of the dormant spec features are revisited:

- `h3>=4.1` (spatial indexing)
- `sentence-transformers>=3.4` (semantic dedup)
- `searoute>=1.3` (shipping route visualization)
- `shapely>=2.0` (geometric operations)
- `google-cloud-bigquery>=3.27` (GDELT BigQuery source)
- `cryptography` (used by `markets/kalshi.py` for RSA-PSS auth — not declared in pyproject.toml)

`requires-python = ">=3.11"` in pyproject.toml conflicts with CLAUDE.md and actual usage (`>=3.12` syntax throughout).

### [MEDIUM] Frontend Architecture Differs from Spec

Spec called for deck.gl + MapLibre H3 hex map with WebSocket-driven real-time updates. Actual frontend is a polling-based REST dashboard using Recharts. No `HexMap`, `AgentFeed`, `Timeline`, or `HexPopover` components exist. The actual set (`KpiBar`, `MarketsTable`, `ModelCards`, `PortfolioPanel`) is appropriate for the new product direction but does not match the spec. No `useWebSocket` hook or batching logic exists.

### [LOW] GDELT BigQuery Replaced With DOC API

Plan: `ingestion/gdelt.py` (BigQuery + 4-stage filter + semantic dedup). Actual: `ingestion/gdelt_doc.py` (GDELT DOC 2.0 HTTP API, no BigQuery). The named-entity override stage and the semantic dedup stage (sentence-transformers cosine similarity) are absent.

---

## Recommendations (Unchanged)

1. **[Immediate]** Either wire `DbWriter.enqueue()` into the write-heavy production paths, or explicitly document that the single-writer constraint is relaxed for the current architecture. The class exists, is tested, but does nothing in production — misleading to future contributors.

2. **[Short-term]** Add `cryptography` to `pyproject.toml` dependencies. It's imported by `markets/kalshi.py` but undeclared — installs as a transitive dep today but can break on a clean install.

3. **[Short-term]** Pin `requires-python = ">=3.12"` to match the codebase and CLAUDE.md.

4. **[Optional]** Add a successor spec document describing the actual prediction-market-edge-finder architecture, so the current spec doesn't confuse future contributors or automated tools.
