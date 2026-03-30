# Parallax

## What This Is

A live geopolitical intelligence tool that simulates the Iran/Hormuz crisis in real-time. It ingests real-world news (GDELT, EIA oil prices), feeds them to 50 AI agents representing actual decision-makers (IRGC, CENTCOM, MBS/Aramco, CCP/PLA, etc.), models cascade effects (blockade → oil flow → price shock → bypass → insurance), and scores predictions against reality daily. Built for a single analyst tracking the Iran-USA situation as it unfolds.

## Core Value

Predictions that beat human intuition about what happens next in the Iran-Hormuz crisis — continuously evaluated and improved against ground truth.

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

- [ ] Eval framework: prediction logging, ground truth fetching, scoring, prompt improvement pipeline
- [ ] Backend API: FastAPI endpoints wiring simulation engine, agents, and ingestion to frontend
- [ ] WebSocket server pushing live events, agent decisions, and indicator updates to frontend
- [ ] End-to-end pipeline: GDELT → agents → cascade → world state → frontend
- [ ] Continuous eval loop: daily cron scoring predictions against reality, flagging drift
- [ ] Agent prompt refinement based on eval scores
- [ ] Frontend panels wired to real data (agent activity, live indicators, timeline, predictions)
- [ ] Frontend eval dashboard (prediction vs reality accuracy over time, per-agent scores)

### Out of Scope

- Multi-scenario support (other conflicts) — Iran/Hormuz only for v1
- User authentication / multi-user — single analyst tool
- Mobile app — desktop web only
- Historical replay UI — backend supports replay mode but no UI needed yet
- Public deployment — runs locally via Docker

## Context

- Active Iran-USA tensions make this a live, time-sensitive tool — real events are happening daily
- 10 feature branches exist (feat/01 through feat/10) with substantial code, but branches are parallel (not merged together)
- PRs #12-17 are open as drafts, need completion and merging
- Backend has ~51 tests across simulation, spatial, ingestion, and agent modules
- Frontend has the dashboard shell with map but panels show placeholder data
- Eval framework branch exists but has no eval-specific code yet
- Backend API branch exists but has no API-specific code yet
- GDELT BigQuery integration requires Google credentials; EIA requires API key
- Agent LLM calls use Anthropic API with $20/day budget cap
- Codebase map available at `.planning/codebase/`

## Constraints

- **Budget**: $20/day cap on LLM calls for agent swarm — enforced by budget tracker with auto-degrade
- **Tech stack**: Python/FastAPI backend, React/Vite/TypeScript frontend, DuckDB, H3/deck.gl — established
- **Data sources**: GDELT (15min cadence), EIA API v2 — already integrated
- **Deployment**: Docker Compose locally — no cloud infra for v1
- **Timeline**: Crisis is unfolding now — sooner this works end-to-end, the more valuable it is

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| DuckDB over Postgres | Embedded, zero-config, fast analytical queries, single-writer fits the model | ✓ Good |
| H3 hexagonal grid | Uniform spatial indexing, multi-resolution (ocean→infrastructure), deck.gl native support | ✓ Good |
| 50 agents across 12 countries | Covers major actors in Hormuz crisis (Iran, USA, Saudi, China, UAE, etc.) with sub-actors (IRGC, CENTCOM, Aramco) | — Pending |
| Anthropic prompt caching + model tiering | Haiku for routine, Sonnet for escalation — keeps under $20/day | — Pending |
| Semantic dedup at 0.90 threshold | Validated over 0.85 — tighter threshold reduces noise without losing distinct events | ✓ Good |
| Parallel feature branches | Each subsystem developed independently — needs integration pass | ⚠️ Revisit |

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
*Last updated: 2026-03-30 after initialization*
