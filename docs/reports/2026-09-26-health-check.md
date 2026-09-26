# Parallax Health Check — 2026-09-26

**Status: YELLOW**

## Summary

No new feature implementations in the last 20 commits — every commit since at least 2026-09-16 has been a daily health check or tech research report. The codebase remains on the intentional pivot from the Phase 1 spec (geopolitical cascade simulator) to a prediction market edge-finder for Kalshi/Polymarket. Core structural issues from prior reports are unchanged: the DuckDB single-writer constraint is violated across 10 write-path modules (up from 5 identified yesterday — 5 additional were found in contracts, ops, scoring/scorecard, scoring/tracker, and backtest/runner), and the agents/eval/spatial layers from the spec remain unimplemented.

---

## Issues Found

### [HIGH] DuckDB single-writer pattern violated — 10 modules (worsening)

`DbWriter` is implemented correctly in `db/writer.py` and is never instantiated or called anywhere in the codebase. All 10 write-path modules bypass it with direct `conn.execute(INSERT/UPDATE)` calls:

- `scoring/ledger.py` — `signal_ledger` writes
- `scoring/prediction_log.py` — `prediction_log` writes
- `scoring/scorecard.py` — `daily_scorecard` writes
- `scoring/tracker.py` — `trade_positions`, `trade_orders`, `trade_fills` writes
- `budget/tracker.py` — `llm_usage` writes
- `ops/alerts.py` — `ops_events` writes
- `ingestion/crisis_ingester.py` — `crisis_events` writes
- `contracts/registry.py` — `contract_proxy_map`, `contract_registry` writes
- `cli/brief.py` — `runs`, `market_prices` writes
- `backtest/runner.py` — `backtest_runs`, `backtest_predictions` writes

The current CLI is sequential so this is latent rather than active. Any background ingestion, concurrent API requests, or parallel brief runs will produce `database is locked` errors. Previous health checks have flagged this; it has not been addressed.

### [HIGH] agents/ package never implemented

The spec's core — 12 country agents, ~50 sub-actors, router, runner, prompts/, country-level synthesis — does not exist. The 3 direct Claude calls in `prediction/` are a functional replacement for the prediction market use case but are not the multi-agent swarm described in the spec.

### [MEDIUM] simulation/circuit_breaker.py and simulation/engine.py absent

`circuit_breaker.py` (escalation limits, cooldown, exogenous shock override) and `engine.py` (DES heapq priority queue, clock modes) were planned in Tasks 7-8 and never implemented. `cascade.py` and `world_state.py` exist and appear correct.

### [MEDIUM] eval/ package absent

`eval/` (structured prediction format, direction/magnitude/sequence/calibration scoring, prompt versioning, A/B comparison, causal attribution on misses) does not exist. `scoring/` covers calibration metrics but not the spec's full evaluation pipeline.

### [MEDIUM] Spatial layer absent

`spatial/` directory (H3 utilities, `ResolutionBand`, `route_to_h3_chain`) does not exist. No H3 hex map in the frontend.

### [MEDIUM] Key spec dependencies missing from pyproject.toml

Not present: `h3>=4.1`, `searoute>=1.3`, `shapely>=2.0`, `sentence-transformers>=3.4`, `google-cloud-bigquery>=3.27`, `websockets>=14.0`. Also: spec requires `python>=3.12` but `pyproject.toml` declares `python>=3.11`.

### [LOW] Frontend diverged from spec

Spec: 3-column dark dashboard, H3 hex map, agent feed, WebSocket streaming. Actual: KPI cards, markets table, model health, portfolio panel, polling via `usePolling.ts`. No WebSocket, no hex map, no agent feed. This is consistent with the product pivot.

### [LOW] Test coverage gaps — 16 modules uncovered

Modules with no test file: `circuit_breaker.py` (module also missing), `budget/tracker.py`, `ops/runtime.py`, `db/runtime.py`, `backtest/engine.py`, `backtest/runner.py`, `portfolio/allocator.py`, `ingestion/crisis_ingester.py`, `ingestion/oil_prices.py`, `prediction/hormuz.py`, `prediction/ceasefire.py`, `prediction/oil_price.py`, `cli/kalshibench.py`, `bench/kalshibench.py`. The 3 individual predictors (oil_price, ceasefire, hormuz) have no dedicated unit tests despite being the core value-generating components.

### [LOW] No feature velocity for 20+ commits

The last 20 commits are exclusively health checks and tech research reports. No new code has shipped. If the validation deadline in CLAUDE.md (April 7-21 2026) has passed, the project needs a new prioritized roadmap.

---

## Recommendations

1. **Fix single-writer pattern** (or drop it): Either wire `DbWriter` into the 10 write-path modules, or officially drop the pattern and document the rationale. The current state — pattern defined but unused — is the worst of both worlds. For the current sequential CLI flow, dropping it is defensible; if background tasks are added, it becomes mandatory.

2. **Add unit tests for the 3 predictors**: `prediction/oil_price.py`, `prediction/ceasefire.py`, `prediction/hormuz.py` are the core value-generating modules and have zero dedicated tests. This is the highest-leverage testing gap.

3. **Acknowledge the pivot in the spec**: The design spec at `docs/superpowers/specs/2026-03-30-parallax-phase1-design.md` describes a product that no longer exists. Either update the spec to match reality (prediction market edge-finder) or document the architectural decisions that diverged from it. The CLAUDE.md already reflects the actual product — the spec should too.

4. **Resolve the validation timeline**: The ceasefire window (April 7-21 2026) mentioned in CLAUDE.md has passed. If the project is continuing, the next milestone and deadline should be stated.
