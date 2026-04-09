# Parallax

## What This Is

A prediction market edge-finder for the Iran-Hormuz crisis. Ingests real-world news (Google News RSS, GDELT DOC API, EIA oil prices), runs 3 focused AI prediction models (oil price, ceasefire, Hormuz reopening) with cascade reasoning, compares predictions against Kalshi/Polymarket market prices, and flags divergences as trade signals. Validated via paper trading on Kalshi sandbox. Built for a single trader/analyst exploiting second-order effects that sentiment bots miss.

## Core Value

Find mispriced prediction market contracts on Iran war outcomes by reasoning about second-order cascade effects (blockade -> flow -> price -> insurance) faster and deeper than headline-scraping bots.

## Current Milestone: v1.2 Evaluation + Deployment Hardening

**Goal:** The edge-finder is built and Phase 1-2 trust foundations are in place. Next step is proving edge with contract-level P&L, then hardening deployment and API hydration.

**Target features:**
- Contract registry with proxy classification (DIRECT / NEAR_PROXY / LOOSE_PROXY / NONE) per model type
- Mapping policy replacing heuristic `_map_predictions_to_markets()` with structured proxy-aware decision logic
- Prediction persistence with full provenance (model claim, reasoning, news context, cascade state)
- Signal ledger recording every signal with contract mapping, proxy class, market state, and trade decision
- Resolution polling and calibration reports for feedback-loop analysis
- Paper trading evaluation at contract level with P&L segmented by proxy class
- FastAPI endpoint hydration (return real pipeline data, not empty responses)
- Second thesis expansion (new prediction domains beyond Iran/Hormuz)

## Requirements

### Validated

- DuckDB schema (12 tables) + single-writer DbWriter with asyncio.Queue
- YAML scenario config loader for Hormuz cascade parameters
- Cascade engine: 6 parameterized rules (blockade -> flow -> bypass -> price -> downstream -> insurance)
- Google News RSS poller (primary news source, free, 5-15min)
- GDELT DOC 2.0 API poller (secondary news source, free, 15-60min)
- EIA API v2 oil price fetcher (Brent + WTI)
- 3 prediction models: OilPricePredictor, CeasefirePredictor, HormuzReopeningPredictor (Claude Sonnet)
- Kalshi API client with RSA-PSS auth (production reads, demo paper trades)
- Polymarket read-only client
- DivergenceDetector comparing model vs market-implied probabilities
- PaperTradeTracker for paper trade P&L tracking
- BudgetTracker with $20/day cap, per-model pricing, auto-degrade
- CLI entry point (`parallax.cli.brief`) running full pipeline: news -> predict -> market -> diverge -> trade
- FastAPI server with 6 endpoints (latest-run state + persisted paper trades; historical hydration still incomplete)
- Docker Compose for backend
- Phase 1 completed: contract registry, mapping policy, signal ledger
- Phase 2 completed: prediction persistence, resolution checker, calibration queries
- Phase 3 completed: paper trading evaluation, report card, track record injection, recalibration, discount auto-adjustment
- 241 tests passing

### Active

- [x] Contract registry in DuckDB with proxy classification per model type — Validated in Phase 1
- [x] Mapping policy replacing heuristic ticker matching with structured proxy-aware logic — Validated in Phase 1
- [x] Signal ledger persisting every signal with full provenance — Validated in Phase 1
- [x] Prediction persistence with calibration queries (Phase 2)
- [x] Paper trading evaluation with contract-level P&L by proxy class — Validated in Phase 3
- [ ] Deployment hardening: Docker health checks, API hydration, error handling (Phase 4)
- [ ] Second thesis expansion beyond Iran/Hormuz (Phase 5)

### Out of Scope

- 50-agent swarm (replaced by 3 focused prediction models -- killed April 2026)
- H3 spatial visualization / deck.gl map (deleted -- CLI tool does not need maps)
- Frontend dashboard (deleted -- CLI-first, API endpoints for future UI)
- WebSocket real-time updates (not needed for CLI tool)
- EventBus / TickOrchestrator (never built -- pipeline is sequential)
- Semantic dedup with sentence-transformers (deleted -- Google News RSS provides clean enough input)
- Multi-user authentication (single-analyst tool)
- Mobile app
- Real-money trading (paper trading only until edge is proven via P&L)
- Latency arbitrage (edge is reasoning depth, not speed)
- Multi-scenario support (other conflicts) for v1 -- Phase 5 handles expansion
- Historical replay UI (backend supports replay mode but no UI needed)

## Context

- Active US-Iran war (Operation Epic Fury, started Feb 28 2026). Khamenei killed. Strait of Hormuz effectively closed.
- 2-week ceasefire agreed April 7 2026, mediated by Pakistan. Talks in Islamabad Friday. Iran submitted 10-point peace plan.
- Oil prices: Brent hit $118 Q1 2026, currently $96-113. Largest inflation-adjusted spike since 1988.
- Kalshi/Polymarket: $200M+ traded on Iran war outcomes. Active markets on ceasefire, Hormuz reopening, oil prices.
- 30%+ of Polymarket wallets are AI bots. 14/20 most profitable wallets are bots. Edge is in reasoning depth, not speed.
- Dead code pruning completed April 8 2026: deleted agents/, simulation/engine.py, circuit_breaker.py, spatial/h3_utils.py, ingestion/gdelt.py (BigQuery), ingestion/dedup.py, db/queries.py, frontend/ directory, 3 dead test files. The current suite is 192 passing tests.
- Codebase is now lean: 3 prediction models, 2 market clients, 2 news ingestors, 1 cascade engine, 1 divergence detector, CLI + FastAPI entry points.

## Constraints

- **Budget**: $20/day cap on LLM calls -- 3 Sonnet calls ~$0.02/run, massive headroom
- **Tech stack**: Python/FastAPI backend, DuckDB -- established. CLI-first.
- **Data sources**: Google News RSS (free, 5-15min), GDELT DOC API (free, 15-60min), EIA API v2, Kalshi API, Polymarket API
- **Deployment**: Docker Compose locally -- no cloud infra for v1
- **Timeline**: 2-week ceasefire window (April 7-21 2026) is the validation deadline
- **Trading**: Paper trading only via Kalshi sandbox. No real money until edge is proven.

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| DuckDB over Postgres | Embedded, zero-config, fast analytical queries, single-writer fits the model | Good |
| 3 focused models over 50-agent swarm | Structured causal reasoning on oil/ceasefire/Hormuz beats shallow sentiment at 1/100th the cost | Good -- killed swarm April 2026 |
| CLI-first over frontend dashboard | Ship faster, prove edge via paper trading P&L, defer UI until edge is proven | Good -- deleted frontend April 8 2026 |
| Google News RSS as primary over GDELT BigQuery | Free, faster (5-15min vs 15-60min), no GCP credentials needed, cleaner signal | Good -- deleted BigQuery pipeline April 8 2026 |
| Dead code pruning April 8 2026 | Deleted agents/, simulation/engine.py, circuit_breaker.py, spatial/, ingestion/gdelt.py, ingestion/dedup.py, db/queries.py, frontend/ | Good -- current suite is 192 passing tests and the codebase is focused |
| Kalshi production for reads, demo for trades | Demo sandbox has no geopolitical markets (only sports/crypto) | Good |
| Paper trading first | Prove edge before risking capital. Kalshi sandbox is free. | Good |
| Cascade engine retained | 6-rule parameterized cascade (blockade -> flow -> bypass -> price -> downstream -> insurance) provides second-order reasoning that prediction models use | Good |
| Anthropic prompt caching | Sonnet-only now, 3 deep calls per run. ~$0.02/run vs $20/day budget. | Good |

## Evolution

This document evolves at phase transitions and milestone boundaries.

**After each phase transition** (via `/gsd:transition`):
1. Requirements invalidated? -> Move to Out of Scope with reason
2. Requirements validated? -> Move to Validated with phase reference
3. New requirements emerged? -> Add to Active
4. Decisions to log? -> Add to Key Decisions
5. "What This Is" still accurate? -> Update if drifted

**After each milestone** (via `/gsd:complete-milestone`):
1. Full review of all sections
2. Core Value check -- still the right priority?
3. Audit Out of Scope -- reasons still valid?
4. Update Context with current state

---
*Last updated: 2026-04-09 after Phase 3 completion (paper trading evaluation, report card, track record injection, recalibration, discount auto-adjustment)*
