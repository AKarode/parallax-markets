# Parallax Phase 1 — Design Specification

*Thin vertical slice: Iran/Hormuz scenario, end-to-end*

## Overview

Parallax is a geopolitical cascade simulator that combines live data ingestion, an LLM-powered agent swarm, spatial visualization on H3 hexagonal grids, and a continuous evaluation framework. Phase 1 delivers one complete scenario — an Iran/Strait of Hormuz crisis — as a live dashboard with real-time data, agent-driven predictions, and automated accuracy tracking.

**Goals:**
- Visually compelling live dashboard (interview/demo ready)
- Functional enough to demonstrate real product potential
- Continuous eval framework that tracks prediction accuracy over 30+ days
- Smooth path to improving agent prompts based on real-world outcomes

**Target users:** Gated access via invite links. Admin mode for prompt editing and eval review.

---

## 1. Architecture

Four layers:

```
┌─────────────────────────────────────────────────────┐
│  FRONTEND — React + deck.gl + MapLibre              │
│  Three panels + timeline bar                         │
├─────────────────────────────────────────────────────┤
│  SIMULATION ENGINE — Python asyncio + heapq DES     │
│  Event queue, world state, cascade rules             │
├─────────────────────────────────────────────────────┤
│  AGENT SWARM — ~50 LLM agents (12 countries)        │
│  Country → sub-actor hierarchy                       │
├─────────────────────────────────────────────────────┤
│  DATA LAYER — DuckDB + spatial + H3 community ext.   │
│  Overture Maps, Searoute, GDELT, EIA, ACLED         │
├─────────────────────────────────────────────────────┤
│  EVAL FRAMEWORK — Cron + manual checkpoints         │
│  Prediction log, ground truth, prompt versioning     │
└─────────────────────────────────────────────────────┘
```

**Tech stack:**

| Layer | Technology |
|-------|-----------|
| Frontend | React, deck.gl (H3HexagonLayer), MapLibre GL |
| Backend | Python, FastAPI, asyncio |
| Simulation | Custom DES (asyncio + heapq), no LangGraph |
| Spatial DB | DuckDB + spatial extension + H3 community extension (pinned version in deployment) — single-writer pattern via asyncio.Queue |
| Map data | Overture Maps + Searoute + Natural Earth + NGA WPI |
| Event data | GDELT (BigQuery, 15-min), ACLED (validated, lagged) |
| Economic data | EIA API, Energy Institute Statistical Review, UN COMTRADE |
| LLM | Claude API (Haiku for sub-actors, Sonnet/Opus for country agents) |
| Deployment | Vercel (frontend) + Railway/Fly (backend), gated access |

---

## 2. Spatial Model

### H3 Resolution Strategy (4 bands, 4 deck.gl layers)

| Zone | Resolution | Hex Edge | Use |
|------|-----------|----------|-----|
| Open ocean / distant routes | Res 3-4 | ~12-60km | Cape of Good Hope rerouting, distant shipping |
| Regional (Persian Gulf, Gulf of Oman) | Res 5-6 | ~3-11km | Fleet positions, oil flow corridors |
| Hormuz strait + chokepoints | Res 7-8 | ~0.5-1.2km | Mine placement, patrol zones, vessel lanes, blockade detail |
| Infrastructure (ports, terminals) | Res 9 | ~175m | Bandar Abbas, Fujairah, Ras Tanura, Yanbu |

**Total hex budget:** ~400K hexes across all layers (within deck.gl's 500K comfort zone).

### Shipping Routes as H3 Cells

`searoute` generates realistic-looking sea routes but explicitly states it is **not for routing purposes**. It is used here **only for visualization geometry** — drawing routes on the map. Operational logic (travel time, capacity, rerouting penalties) uses parameterized scenario values, not searoute output.

1. Generate route GeoJSON between port pairs via `searoute` (visualization only)
2. Sample points along LineString at appropriate density per resolution band
3. Convert points to H3 cells
4. Store as ordered cell chains — geometry for rendering, NOT authoritative for travel time or capacity
5. Hormuz corridor gets res 7-8 cells — enough granularity to model eastern vs western shipping lanes

### Cell Attributes

Each H3 cell carries a JSON attribute bag:
- `influence`: which country/actor controls or contests this cell
- `threat_level`: 0.0-1.0 escalation indicator
- `flow`: oil/shipping throughput (bbl/day or vessels/day)
- `status`: open | restricted | blocked | mined | patrolled
- `last_updated`: simulation tick

---

## 3. Agent Swarm

### Hierarchy

~12 country agents, each with 3-5 sub-actors. ~50 agents total.

**Phase 1 roster (Iran/Hormuz focused):**

| Country | Sub-Actors |
|---------|-----------|
| Iran | Supreme Leader/Khamenei, IRGC, IRGC Navy, Foreign Ministry, Oil Ministry |
| USA | Trump/White House, Congress, Pentagon/CENTCOM, State Dept, Treasury (sanctions) |
| Saudi Arabia | MBS/Crown Prince, Aramco, OPEC delegation |
| China | Xi/CCP, PLA Navy, CNOOC/Sinopec |
| Russia | Putin, Rosneft, Foreign Ministry |
| UAE | Leadership, ADNOC, Fujairah port authority |
| India | PMO, Indian Oil Corp, Navy |
| Japan | PM office, JERA/refiners |
| South Korea | Blue House, SK Energy/refiners |
| EU | Commission (as bloc), energy policy |
| Israel | PM office, IDF, Mossad |
| Iraq | PM office, Oil Ministry |

**Non-state actors:** OPEC (institution), Lloyd's/shipping insurers, oil futures market sentiment.

### Agent Memory (3 layers)

1. **Historical baseline** (system prompt): Formal policies, doctrine, treaties, past behavior patterns, known informal practices. Curated per-agent. Examples:
   - IRGC Navy: asymmetric warfare doctrine, fast-boat swarm tactics, history of tanker seizures
   - Trump: "maximum pressure" pattern, transactional deal-making style, sanctions-first approach
   - Aramco: spare capacity strategy, pipeline bypass protocols

2. **Rolling context** (last ~20 decisions + outcomes): Keeps the agent consistent with its own recent simulation behavior. Stored in DuckDB `agent_memory` table.

3. **Eval feedback** (injected corrections): When predictions diverge from reality and the miss is tagged `model_error`, corrections get added to context. E.g., "Your model overestimated Iran's willingness to escalate — real-world signals show restraint."

### Decision Flow Per Tick

1. New events arrive (GDELT ingestion or cascade from other agents)
2. **Three-stage GDELT filter** (see Section 6) produces curated events
3. **Router** determines relevant agents (entity matching + H3 proximity + relevance score)
4. Relevant **sub-actors** evaluate event independently (parallel LLM calls)
5. **Country agent** receives sub-actor recommendations, resolves conflicts via weighted influence model, produces structured decision
6. Decision feeds into cascade engine → H3 cell updates → ripple effects → may trigger other agents

### Sub-Actor Conflict Resolution

- Each sub-actor has a `weight` reflecting real-world influence within the country (e.g., IRGC: 0.7, Foreign Ministry: 0.3 under Khamenei's leadership)
- Country agent prompt explicitly weighs recommendations by influence weight, current political context, and the leader's known decision-making style
- Output: chosen action + which sub-actor's recommendation it aligned with + reasoning
- Dynamic weights: eval framework flags when a country agent consistently overweights one sub-actor vs reality → prompt refinement adjusts

### Agent Output Schema

```json
{
  "agent_id": "iran/irgc_navy",
  "tick": 1042,
  "action_type": "military_deployment",
  "target_h3_cells": ["872a1072fffffff", "872a1073fffffff"],
  "intensity": 0.7,
  "description": "Increased patrol frequency in eastern Hormuz corridor",
  "reasoning": "Response to CENTCOM carrier repositioning. Asymmetric deterrence posture.",
  "confidence": 0.78,
  "prompt_version": "v1.2.0"
}
```

---

## 4. Simulation Engine

Custom Python discrete event simulation. No LangGraph.

### Core Components

- **Event queue**: `heapq` priority queue ordered by simulation tick
- **World state**: H3 cells + attributes in DuckDB, cached in memory for hot path
- **Simulation clock**: Monotonic tick counter. One tick = 15 minutes (aligned with GDELT ingestion cycle). Maps to wall clock in live mode, advances per event in replay mode.
- **Cascade rules**: Deterministic, rule-based propagation (oil flow disruption, price shock, rerouting)

### Cascade Rules (Iran/Hormuz)

All numeric values below are **calibrated scenario parameters** loaded from a config file, not hard-coded constants. Default values are sourced from IEA, EIA, and industry analysis but can be overridden per scenario run.

1. **Hormuz blockade** → shipping flow reduction per affected H3 cell (not binary — partial blockade modeled as % reduction)
2. **Flow reduction** → pipeline bypass activation. Default parameters:
   - `hormuz_daily_flow`: ~20M bbl/day (IEA estimate)
   - `saudi_eastwest_pipeline_capacity`: 5M bbl/day (to Yanbu, Red Sea)
   - `uae_habshan_fujairah_capacity`: 1.5M bbl/day (to Gulf of Oman)
   - `total_bypass_capacity`: 3.5-6.5M bbl/day (range reflects utilization uncertainty; IEA estimates 3.5-5.5M, some sources say up to 6.5M at surge)
   - These are **tunable** — the eval framework can flag when bypass assumptions diverge from observed behavior
3. **Net supply loss** → oil price shock (proportional to deficit after bypass)
4. **Price shock** → downstream effects per country based on energy dependency ratios (EIA data)
5. **Rerouting** → Cape of Good Hope path activation. Default parameters:
   - `hormuz_to_europe_via_suez_nm`: ~6300 NM
   - `cape_reroute_nm`: ~11600 NM
   - `reroute_distance_penalty_pct`: ~84% (derived, not hard-coded — computed from the two distances)
   - `reroute_transit_days_additional`: 10-14 days (range, not fixed)
6. **Insurance/risk** → shipping insurance cost spike in contested cells

**Scenario config** is a YAML/JSON file loaded at simulation start. Changing parameters does not require code changes.

### Cascade Circuit Breaker

- **Max escalation per tick**: No agent can escalate more than 1 level per tick for **agent-initiated** escalations (e.g., "patrol" → "warning shots", never "patrol" → "full blockade")
- **Escalation cooldown**: 3-tick cooldown after a major agent-initiated escalation event (mirrors real-world political/bureaucratic latency)
- **Exogenous shock override**: If an incoming GDELT event has a severity score above a threshold (e.g., GoldsteinScale magnitude > 8, or tagged as armed conflict/military strike), the circuit breaker is bypassed. Agents can "jump" multiple escalation levels to match reality. This prevents the model from lagging behind sudden real-world escalations (e.g., Israel strikes an Iranian facility — reality just jumped 5 levels, agents shouldn't be throttled to 1 level/tick).
- **Reality anchor**: Outputs sanity-checked against historical ranges. Oil clamped to plausible range with a flag if exceeded.
- **Human override**: Pause simulation, roll back cascade, manually inject de-escalation

### Simulation Clock Modes

- **Live mode** (default): 1:1 with wall clock. GDELT events arrive in real-time. Agents react as events happen. LLM calls are active.
- **Replay mode**: Fast-forward through historical data at configurable speed (1x, 10x, 100x). For demos: "show the last week in 30 seconds." **Replay mode NEVER hits the Claude API.** It purely plays back the `world_state_delta`, `world_state_snapshot`, and `decisions` tables that were recorded during live mode. This ensures determinism, zero API cost, and no rate-limit risk.
- **Seamless transition**: Replay catches up to present, then automatically switches to live mode.

---

## 5. Frontend

### Layout

Three-column dark-themed dashboard (navy/slate palette) with bottom timeline bar.

**Left panel — Agent Activity** (280px):
- Scrolling feed of agent decisions
- Color-coded by country
- Shows sub-actor, action summary, confidence, timestamp
- Most recent at top

**Center — H3 Hex Map** (flexible):
- deck.gl with MapLibre GL base map
- 4 H3HexagonLayer instances (one per resolution band)
- Hexes colored by influence/threat/flow
- Shipping routes as cell chains with directional flow indicators
- Smooth transitions via `getFillColor` GPU interpolation (600ms)
- Click hex for detail popover (cell attributes, recent events, controlling actor)

**Right panel — Live Indicators** (320px):
- Brent crude price card with sparkline
- Hormuz traffic (vessel count, % change)
- Pipeline bypass utilization (current vs capacity)
- Escalation index (composite 5-level indicator)
- GDELT news feed (latest filtered events with timestamps)

**Bottom bar — Timeline + Predictions** (180px):
- Simulation timeline with event markers, scrubable for replay
- Active predictions panel: next-7-day forecasts with confidence scores
- Prediction cards: oil price range, Hormuz flow %, escalation level, diplomatic outlook

### WebSocket Connection

- Backend pushes state updates to frontend via WebSocket
- Update types: `cell_update` (hex changes), `agent_decision` (new decisions), `indicator_update` (price/flow changes), `event` (new GDELT events)
- Frontend applies updates incrementally (no full state reload)

### Render Performance (Critical)

Pushing high-frequency WebSocket updates directly into React state causes render thrashing that freezes the deck.gl canvas. The fix is to decouple React UI state from deck.gl data arrays:

- H3 hex data lives in a **mutable `useRef`**, not `useState`. WebSocket `cell_update` messages mutate the ref directly.
- deck.gl pulls from the mutable data structure on its own render cycle (via `DataFilterExtension` or manual `setProps` calls).
- React re-renders are triggered only for UI-level changes (agent feed, indicator cards, timeline scrub) — not hex data.
- WebSocket messages are batched: buffer incoming updates for 100ms, then flush as a single mutation to the ref. This prevents per-message re-renders during high-activity periods.

---

## 6. Data Ingestion

### GDELT Pipeline (15-minute cycle)

**Four-stage noise filter:**
1. **Volume gate**: Default threshold `NumMentions > 3 AND NumSources > 2`, BUT with a **named-entity override list** that bypasses this gate. Events mentioning scenario-critical entities (named actors like IRGC/CENTCOM/Aramco, named ports like Bandar Abbas/Fujairah, chokepoint keywords like "Hormuz"/"strait", sanctions language, naval incident terms) pass through even at low mention counts. This prevents filtering out exactly the kind of weak, early, high-value signals that matter most for geopolitical forecasting — the first report of a tanker seizure won't have 3+ mentions yet.
2. **Structural dedup**: Cluster by actor + action + target within 1-hour window. One representative per cluster.
3. **Semantic dedup**: GDELT often extracts slightly different entities for the same real-world event across articles. For events within a 2-hour window that pass stage 2, embed their summary strings using a local model (`all-MiniLM-L6-v2` via `sentence-transformers`). If cosine similarity > 0.85, drop the duplicate. This runs locally — no API cost.
4. **Relevance scoring**: Keyword + entity match against active scenario actors/locations. Score 0-1. Only events > 0.5 reach the router. Events that entered via the named-entity override in stage 1 get a relevance floor of 0.6 (they already matched critical entities).

Raw GDELT never touches agents. Filtered events write to `curated_events` table.

### Static Data (loaded once, refreshed quarterly)

- Overture Maps: Middle East bounding box (places, transport, admin boundaries, buildings)
- Searoute: shipping route visualization geometry between major port pairs → H3 cell chains (NOT authoritative for travel time or capacity)
- Natural Earth: shipping lane geometry, coastlines
- NGA World Port Index: port metadata
- Energy Institute Statistical Review: energy dependency ratios
- EIA: country-level oil import/export volumes

### Live Data Feeds

| Source | Frequency | Data |
|--------|-----------|------|
| GDELT (BigQuery) | 15 min | Event records, geocoded |
| EIA API | Daily | Crude oil spot prices |
| Oil prices (EIA API + FRED API) | Daily | WTI/Brent daily spot and benchmark series only. Does NOT include a proper futures forward curve — paid provider (CME Group, Nasdaq Data Link) required in Phase 2 if forward term structure is needed. |
| ACLED | Weekly | Validated conflict events (lagged) |

---

## 7. Eval Framework

### Prediction Format

Every prediction is structured:

```json
{
  "prediction_id": "uuid",
  "agent_id": "iran/irgc_navy",
  "prediction_type": "hormuz_traffic_reduction",
  "direction": "decrease",
  "magnitude_range": [30, 50],
  "unit": "percent",
  "timeframe": "7d",
  "confidence": 0.65,
  "reasoning": "...",
  "prompt_version": "v1.2.0",
  "created_at": "2026-03-30T14:00:00Z",
  "resolve_by": "2026-04-06T14:00:00Z"
}
```

### Baselines

Every prediction is compared against:
1. **Naive baseline**: "no change" — yesterday's values persist
2. **Market consensus**: futures prices, analyst consensus where available

The swarm must beat both to demonstrate value.

### Scoring

- **Direction accuracy**: Binary — did the predicted direction match?
- **Magnitude accuracy**: Was the actual value within the predicted range?
- **Sequence accuracy**: Did events unfold in predicted order? (scored across related prediction chains)
- **Calibration score**: Are confidence levels meaningful? A 0.8 prediction should be right ~80% of the time. Measured over rolling 30-day window.

### Causal Attribution on Misses

Every miss is tagged:
- `model_error` — agent reasoning was wrong. Feeds into prompt refinement.
- `exogenous_shock` — unpredicted external event (assassination, natural disaster). Logged as new context for agents.
- `data_lag` — ground truth wasn't available in time. No action.
- `ambiguous` — unclear whether prediction was right or wrong. Manual review.

Only `model_error` triggers the prompt improvement pipeline.

### Prompt Versioning

- Every agent prompt uses semver (e.g., `v1.2.0`)
- Prediction log records the prompt version that generated it
- After a prompt update, accuracy is tracked per-version over a rolling window
- A/B comparison: if new version underperforms old over 7 days, auto-flag for rollback

### Prompt Improvement Pipeline

1. **Daily cron** identifies agents with declining accuracy (7-day rolling window drops below threshold)
2. System pulls the agent's recent `model_error` misses
3. Generates suggested prompt edits with rationale (using a meta-agent or template)
4. Admin reviews and approves/rejects via admin dashboard
5. Approved edits create a new prompt version, deployed immediately
6. New predictions tagged with new version for A/B tracking

### Eval Modes

- **Cron (daily)**: Automated. Snapshots active predictions, fetches ground truth from EIA/GDELT/ACLED, computes scores, updates dashboards.
- **Manual checkpoint**: Admin flags a specific moment ("Iran just seized a tanker"). System captures all active predictions at that instant for later comparison.

---

## 8. Cost Control

### LLM Budget

- **Tiered activation**: Low-relevance events (GDELT relevance < 0.5) handled by rule-based heuristics only. No LLM calls.
- **Model tiering**: Sub-actors use Haiku for initial assessment. Only when a sub-actor flags significance > 0.6 does the country agent fire on Sonnet/Opus.
- **Agent cooldown**: Sub-actors: 30-min minimum between activations. Country agents: 1-hr minimum. Events queue and batch within the cooldown window.
- **Response caching**: Similar events within a time window get deduplicated before reaching agents.
- **Daily budget cap**: Hard limit (configurable, default $20/day). When exceeded, system degrades to rule-based-only mode and alerts admin.
- **Prompt caching**: Use Anthropic's prompt caching for system prompts (historical baseline is static per version). Cached system prompt tokens cost 90% less on subsequent calls.

### Token Ceilings (per call)

Anthropic pricing is token-based. Per-call cost depends on prompt length and output length. Explicit ceilings prevent runaway costs:

| Agent Type | Model | Max Input Tokens | Max Output Tokens | Est. Cost/Call |
|-----------|-------|-----------------|-------------------|---------------|
| Sub-actor | Haiku 4.5 | 4,000 (system: ~2K cached + context: ~2K) | 500 | ~$0.002 |
| Country agent | Sonnet 4.6 | 8,000 (system: ~3K cached + sub-actor recs: ~3K + context: ~2K) | 1,000 | ~$0.025 |
| Eval meta-agent | Sonnet 4.6 | 6,000 (misses + prompt text) | 2,000 | ~$0.035 |

System prompts (historical baseline) are the largest input component. With prompt caching, repeated calls to the same agent version pay full price only on the first call; subsequent calls within the cache TTL (5 min) pay 10% for the cached prefix.

### Estimated Daily Cost

- ~50 agents, ~10-20 significant events/day after filtering
- Sub-actor calls (Haiku): ~200 calls/day × ~$0.002 = ~$0.40
- Country agent calls (Sonnet): ~50 calls/day × ~$0.025 = ~$1.25
- Eval/meta-agent calls: ~10 calls/day × ~$0.035 = ~$0.35
- **Estimated: $2-5/day** under normal conditions. Spikes during high-activity periods (crisis events may double throughput).
- **30-day run cost**: ~$60-150 for continuous eval period.

---

## 9. State Persistence

DuckDB is the single source of truth. All state survives restarts.

### Single-Writer Topology (Critical)

DuckDB only allows one concurrent writer. This is a hard constraint that shapes the entire backend topology.

**Commitment: All mutable simulation state lives in a single OS process.** The FastAPI server, simulation engine, GDELT ingestion, agent swarm, and eval cron all run as asyncio tasks within one process — NOT as separate services or workers writing to a shared DuckDB file over a mounted volume. Separate processes writing to the same DuckDB file will cause `database is locked` errors.

Within that single process, all database writes go through a centralized `asyncio.Queue`. A single dedicated background task (`db_writer`) reads from this queue and executes inserts/updates sequentially. All other components are write producers that enqueue and continue without blocking.

```
┌─────────────── Single Python Process ───────────────┐
│                                                      │
│  GDELT ingestion ──┐                                 │
│  Agent decisions ───┤──→ asyncio.Queue ──→ db_writer ──→ DuckDB
│  Cascade updates ───┤                                 │
│  Eval cron ─────────┘                                 │
│                                                      │
│  WebSocket handler ──→ reads DuckDB (concurrent OK)  │
│  REST API ───────────→ reads DuckDB (concurrent OK)  │
└──────────────────────────────────────────────────────┘
```

Reads remain concurrent (DuckDB handles multiple readers). The write queue provides natural backpressure — if writes are queuing up, it signals the system is overloaded.

**If Phase 2 requires separate services** (e.g., independent worker scaling), move live mutable state to Postgres and keep DuckDB for replay, analytics, and eval queries.

### Tables

### State Growth Management (Critical)

With ~400K hexes and 15-minute ticks, a naive append-only full snapshot every tick would generate ~38.4M rows/day and ~1.15B rows in 30 days. This silently kills Phase 1.

**Solution: Delta table + periodic snapshots.**
- **Hot path**: `world_state_delta` table stores only **changed cells per tick** (typically a small fraction of the total — most hexes don't change every tick).
- **Cold path**: Full `world_state_snapshot` written every 100 ticks (~25 hours). These are the restore points.
- **Reconstruction**: To rebuild state at any tick, load the nearest prior snapshot and apply deltas forward.
- **Retention**: Deltas older than 30 days are compacted into their nearest snapshot and dropped. Snapshots are kept indefinitely (they're infrequent and small relative to raw deltas).

### Tables

| Table | Purpose |
|-------|---------|
| `world_state_delta` | Changed H3 cells per tick (cell_id, tick, changed_fields JSON) |
| `world_state_snapshot` | Full world state at periodic checkpoints (every ~100 ticks) |
| `agent_memory` | agent_id, prompt_version, rolling_context (JSON), weight, last_activated |
| `agent_prompts` | agent_id, version, system_prompt, historical_baseline, created_at |
| `decisions` | All agent decisions with full output schema |
| `predictions` | Structured predictions with ground truth and scores |
| `curated_events` | Filtered GDELT/ACLED events |
| `raw_gdelt` | Raw GDELT data (for reprocessing) |
| `eval_results` | Daily eval scores per agent and per prediction |
| `simulation_state` | Current tick, clock mode, active scenario metadata |

Restart resumes from the last snapshot + deltas applied forward to the most recent tick.

---

## 10. Auth & Access (MVP)

- **Invite codes**: Generate unique invite URLs (`parallax.app/join/{code}`). Code maps to a read-only session. No user accounts.
- **Admin mode**: Env-var password grants access to eval dashboard, prompt editor, simulation controls (pause/resume/replay), manual checkpoints.
- **Session limit**: Max 10 concurrent sessions to control backend cost.
- **No OAuth for MVP.** Add later if needed for product path.

---

## 11. Cold Start Strategy

1. **Historical replay bootstrap**: Pre-computed offline (NOT live LLM calls at 100x). Before first deploy, run a one-time batch job that processes the last 30 days of GDELT events through the agent swarm at normal speed. This produces a populated `world_state_snapshot` (baseline), `world_state_delta`, `decisions`, and `agent_memory` tables. This is expensive (~$30-50 one-time cost) but only runs once. The result is saved as the baseline DB snapshot.
2. **Scenario snapshots**: Pre-built world state snapshots for known starting points. Load a snapshot to skip bootstrap. Multiple snapshots can capture different moments of interest.
3. **Golden demo state**: Ship a curated snapshot that drops into the middle of an active Hormuz scenario. For interviews: load golden state, switch to replay mode (plays back recorded decisions — no LLM calls), show cascading effects, then transition to live.

---

## 12. Deployment

- **Frontend**: Vercel (React SPA)
- **Backend**: Railway or Fly.io (FastAPI + DuckDB + simulation engine)
- **Scheduled tasks**: All periodic work (GDELT ingestion, daily eval) runs as asyncio background tasks inside the main process — NOT as external cron jobs or separate services. An external scheduler (Railway cron or Fly.io machines) may optionally hit an HTTP endpoint on the main process to trigger these tasks on schedule, but it never writes to DuckDB directly.
- **DuckDB file**: Persistent volume on Railway/Fly
- **Environment variables**: Claude API key, GDELT BigQuery credentials, EIA API key, admin password, invite code seed

---

## 13. Testing Strategy

- **Cascade rules**: Unit tests for each rule (blockade → flow reduction → price shock). Deterministic inputs/outputs.
- **Agent output validation**: JSON schema validation on every agent response. Malformed outputs get rejected and logged.
- **Eval scoring**: Unit tests for direction, magnitude, sequence, and calibration scoring functions.
- **GDELT filter**: Tests against known GDELT event samples to verify noise filtering and deduplication.
- **Integration**: End-to-end test that ingests a batch of curated events, runs through agents and cascade, and verifies world state changes are plausible.
- **Frontend**: Smoke test that WebSocket connection works and hex map renders with test data.

---

## Out of Scope (Phase 1)

- Multiple simultaneous scenarios (only Iran/Hormuz)
- User-defined custom scenarios
- LangGraph integration (reserved for Phase 2 agent reasoning upgrades)
- Concordia framework evaluation
- Full ACLED real-time integration (weekly batch only)
- Mobile responsive layout
- User accounts / OAuth
- Multi-tenant isolation
