# Parallax

## What This Is

A prediction market edge-finder for the Iran-Hormuz crisis. Ingests real-world events (GDELT, EIA oil prices), runs focused AI prediction models with structured causal reasoning (cascade engine), compares predictions against Kalshi/Polymarket market prices, and flags divergences where the model disagrees with market consensus. Validated via paper trading on Kalshi sandbox. Built for a single trader/analyst exploiting second-order effects that sentiment bots miss.

## Core Value

Find mispriced prediction market contracts on Iran war outcomes by reasoning about second-order cascade effects (blockade → flow → price → insurance) faster and deeper than headline-scraping bots.

## Current Milestone: v1.0 Kalshi Prediction Market Pivot

**Goal:** Ship a prediction market edge-finder validated via paper trading within the 2-week ceasefire window.

**Target features:**
- GDELT ingestion feeding structured event data to prediction models
- Kalshi + Polymarket API integration (read market prices, orderbooks)
- 3 focused prediction models: oil price direction, ceasefire probability, Hormuz reopening timeline
- Cascade reasoning engine generating second-order predictions
- Divergence detection: flag when model predictions disagree with market prices
- Daily intelligence brief output (CLI or simple web view)
- Paper trading via Kalshi sandbox to validate edge
- Scoring loop: track prediction accuracy against market resolution

## Requirements

### Validated

- ✓ DuckDB schema (10 tables) for world state, agents, predictions, eval — existing
- ✓ Single-writer DbWriter with asyncio.Queue → DuckDB — existing
- ✓ YAML scenario config loader for Hormuz cascade parameters — existing
- ✓ H3 spatial utilities with 4 resolution bands (ocean/regional/chokepoint/infrastructure) — existing
- ✓ World state manager with in-memory cache, dirty-set delta tracking, snapshot/restore — existing
- ✓ Simulation engine: DES with heapq, live/replay clock modes — existing
- ✓ Cascade engine: 6 parameterized rules (blockade→flow→bypass→price→downstream→insurance) — existing
- ✓ Circuit breaker: max 1 escalation/tick, 3-tick cooldown, exogenous shock override — existing
- ✓ GDELT ingestion pipeline: 4-stage noise filter, 30+ named entities, structural dedup — existing
- ✓ Semantic dedup with sentence-transformers at 0.90 threshold — existing
- ✓ EIA API v2 oil price fetcher (Brent + WTI) — existing
- ✓ Agent swarm: 50 agents across 12 countries, Pydantic schemas, registry — existing
- ✓ Event→agent router with keyword-based relevance matching — existing
- ✓ Agent runner with parallel LLM calls, Anthropic prompt caching, model tiering — existing
- ✓ Budget tracker with $20/day cap, per-model pricing, cooldown, auto-degrade — existing
- ✓ React + Vite + TypeScript frontend scaffold — existing
- ✓ deck.gl + MapLibre H3 hex map with influence colors, threat elevation — existing
- ✓ WebSocket hook with JSON batch parsing and auto-reconnect — existing
- ✓ 3-column dashboard layout (Agent Activity, Map, Live Indicators) — existing
- ✓ Docker setup: backend + frontend Dockerfiles, docker-compose with DuckDB volume — existing

### Active

- [ ] Kalshi API client: read markets, orderbooks, prices; paper trade via sandbox
- [ ] Polymarket API client: read geopolitical/oil market prices as probability benchmarks
- [ ] 3 focused prediction models: oil price direction, ceasefire probability, Hormuz reopening timeline
- [ ] Cascade reasoning engine adapted for prediction market outputs (probability + confidence)
- [ ] Divergence detector: compare model predictions vs market-implied probabilities, flag mispricing
- [ ] Daily intelligence brief: CLI output comparing model vs market with actionable trade signals
- [ ] Scoring loop: track predictions against market resolution, compute P&L on paper trades
- [ ] GDELT ingestion adapted for prediction model input (event chains, not raw events)

### Out of Scope

- 50-agent swarm — replaced by 3 focused prediction models
- H3 spatial visualization / deck.gl map — not needed for prediction market tool
- Full frontend dashboard — CLI-first, simple web view later
- Multi-scenario support (other conflicts) — Iran/Hormuz only for v1
- User authentication / multi-user — single analyst tool
- Mobile app — desktop web only
- Historical replay UI — backend supports replay mode but no UI needed yet
- Public deployment — runs locally via Docker
- Real-money trading — paper trading only for v1, prove edge first
- Latency arbitrage — competing on speed is not our edge

## Context

- Active US-Iran war (Operation Epic Fury, started Feb 28 2026). Khamenei killed. Strait of Hormuz effectively closed.
- 2-week ceasefire agreed April 7 2026, mediated by Pakistan. Talks in Islamabad Friday. Iran submitted 10-point peace plan.
- Oil prices: Brent hit $118 Q1 2026, currently $96-113. Largest inflation-adjusted spike since 1988.
- Kalshi/Polymarket: $200M+ traded on Iran war outcomes. Active markets on ceasefire, Hormuz reopening, oil prices.
- 30%+ of Polymarket wallets are AI bots. 14/20 most profitable wallets are bots. Edge is in reasoning depth, not speed.
- 10 feature branches exist (feat/01 through feat/10) — reusable: GDELT ingestion, cascade engine, DuckDB, budget tracker
- Kill list: 50-agent swarm, H3 spatial viz, full frontend dashboard — too much infrastructure for the opportunity window
- Kalshi API: full REST + WebSocket, paper trading sandbox at demo-api.kalshi.co, free market data reads
- Polymarket: deeper geopolitical liquidity (5-10x Kalshi), public API, crypto-based (read-only for US)
- Codebase map available at `.planning/codebase/`

## Constraints

- **Budget**: $20/day cap on LLM calls — 3 Sonnet calls ~$0.30/day leaves massive headroom for deeper analysis
- **Tech stack**: Python/FastAPI backend, DuckDB — established. Frontend minimal (CLI-first)
- **Data sources**: GDELT (15min cadence), EIA API v2, Kalshi API, Polymarket API — free reads
- **Deployment**: Docker Compose locally — no cloud infra for v1
- **Timeline**: 2-week ceasefire window (April 7-21 2026) is the validation deadline. Ship or miss the window.
- **Trading**: Paper trading only via Kalshi sandbox. No real money until edge is proven.

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| DuckDB over Postgres | Embedded, zero-config, fast analytical queries, single-writer fits the model | ✓ Good |
| H3 hexagonal grid | Uniform spatial indexing, multi-resolution (ocean→infrastructure), deck.gl native support | ✓ Good |
| 50 agents across 12 countries | Covers major actors in Hormuz crisis (Iran, USA, Saudi, China, UAE, etc.) with sub-actors (IRGC, CENTCOM, Aramco) | ✗ Killed — replaced by 3 focused prediction models |
| Anthropic prompt caching + model tiering | Haiku for routine, Sonnet for escalation — keeps under $20/day | ⚠️ Revisit — Sonnet-only now, 3 deep calls |
| Semantic dedup at 0.90 threshold | Validated over 0.85 — tighter threshold reduces noise without losing distinct events | ✓ Good |
| Parallel feature branches | Each subsystem developed independently — needs integration pass | ⚠️ Revisit — cherry-pick reusable modules only |
| Pivot to prediction markets | 50-agent simulation too slow to ship; Kalshi/Polymarket provide built-in eval (P&L) and the crisis is active NOW | — Pending |
| 3 focused models over swarm | Structured causal reasoning on oil/ceasefire/Hormuz beats shallow sentiment at 1/100th the cost | — Pending |
| Paper trading first | Prove edge before risking capital. Kalshi sandbox is free. | — Pending |

## Evolution

This document evolves at phase transitions and milestone boundaries.

**After each phase transition** (via `/gsd:transition`):
1. Requirements invalidated? → Move to Out of Scope with reason
2. Requirements validated? → Move to Validated with phase reference
3. New requirements emerged? → Add to Active
4. Decisions to log? → Add to Key Decisions
5. "What This Is" still accurate? → Update if drifted

**After each milestone** (via `/gsd:complete-milestone`):
1. Full review of all sections
2. Core Value check — still the right priority?
3. Audit Out of Scope — reasons still valid?
4. Update Context with current state

---
*Last updated: 2026-04-07 after v1.0 Kalshi Prediction Market Pivot*
