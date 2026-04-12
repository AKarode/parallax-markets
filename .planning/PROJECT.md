# Parallax

## What This Is

A prediction market edge-finder for the Iran-Hormuz crisis. Ingests real-world news (Google News RSS, GDELT DOC API, EIA oil prices), runs 3 focused AI prediction models (oil price, ceasefire, Hormuz reopening) with cascade reasoning, compares predictions against Kalshi/Polymarket market prices, and flags divergences as trade signals. Validated via paper trading on Kalshi sandbox. Built for a single trader/analyst exploiting second-order effects that sentiment bots miss.

## Core Value

Find mispriced prediction market contracts on Iran war outcomes by reasoning about second-order cascade effects (blockade -> flow -> price -> insurance) faster and deeper than headline-scraping bots.

## Current Milestone: v1.4 Model Intelligence + Resolution Validation

**Goal:** Discover the full contract landscape, build models that directly map to real contracts, fix prompt issues, fill context gaps, diversify news sources, and validate the hold-to-settlement thesis via resolution backtesting.

**Target features:**
- Contract discovery: pull all child contracts from Kalshi API for 12 event tickers, catalog resolution criteria, settlement status, volume/liquidity
- Model-contract alignment: fix proxy classifications, register all actionable contracts, add "Iran political transition" model for regime-change contracts
- Model registry: refactor brief.py from hardcoded 3-model calls to registry pattern (models as data)
- Prompt optimization: remove market price anchoring, fix Hormuz dual-probability spec, fix bypass_flow=0, separate facts from hypothesis injection, track record sample size guards
- Unified ensemble: live signals and simulator use same weighted aggregation logic
- Pre-crisis context: research and write Aug 2025 → Feb 2026 escalation gap, convert to file-based context system
- Rolling daily context: auto-append structured JSON per cron run, 5-day rolling window with self-correction
- News diversification: Reuters/AP RSS, journalist Twitter/X lists, oil-specific feeds, replace dead GDELT
- Resolution backtest: run improved models against settled contracts, score against actual settlement outcomes

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
- FastAPI server with 6 endpoints
- Docker Compose for backend
- Contract registry in DuckDB with proxy classification per model type — Phase 1
- Mapping policy replacing heuristic ticker matching with structured proxy-aware logic — Phase 1
- Signal ledger persisting every signal with full provenance — Phase 1
- Prediction persistence with calibration queries — Phase 2
- Paper trading evaluation with contract-level P&L by proxy class — Phase 3
- Truth Social ingestion for POTUS signals — v1.2
- Signal integrity fixes: cost model, quote staleness guard, Kelly sizing — v1.2

### Active

(Defined in REQUIREMENTS.md for current milestone)

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
- Deployment hardening / API hydration (deferred from v1.2 -- CLI-first, not serving a frontend)
- Second thesis expansion (deferred from v1.2 -- must prove edge on first thesis before expanding)
- Active exit/sell trading (fee math kills it -- round-trip 5.5c vs hold-to-settlement 2.8c)
- Contract-first architecture (deferred to v2.0 -- current model registry pattern sufficient for Iran domain)
- v1.3 Daily Feedback Loop + Scorecard (deprioritized -- model intelligence has higher ROI than telemetry at current data sparsity)

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
| Hold-to-settlement over active exits | Round-trip fees 5.5c vs 2.8c hold-to-settlement. Fee math kills active trading. | Good |
| v1.3 deprioritized for v1.4 | Model intelligence (context gaps, prompt fixes, contract alignment) has higher ROI than telemetry at current data sparsity | Pending |
| Hybrid model architecture | Keep specialized models (cascade/flow preprocessing) + add generic political model + model registry in brief.py. Contract-first arch deferred to v2.0. | Pending |

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
*Last updated: 2026-04-12 after milestone v1.4 start (model intelligence + resolution validation)*
