# Project Research Summary

**Project:** Parallax — Geopolitical Crisis Simulation Platform
**Domain:** Real-time intelligence platform with LLM agent swarm and prediction evaluation
**Researched:** 2026-03-30
**Confidence:** MEDIUM

## Executive Summary

Parallax is a single-analyst intelligence tool that simulates the live Iran-Hormuz crisis using a 50-agent LLM swarm, a discrete-event simulation engine with cascade rules, GDELT-based ingestion, and DuckDB persistence. All five major subsystems (ingestion, agents, simulation engine, database, frontend) already exist on parallel feature branches. The central challenge is not building new components — it is integration: wiring these subsystems into a single live pipeline where real-world events flow through agent deliberation into cascade simulation, persist durably, and surface on a live React dashboard. The recommended architecture is a single-process asyncio event bus (not microservices) that decouples producers from consumers while keeping deployment, debugging, and latency concerns simple for a local Docker tool.

The core value proposition is "continuously evaluated predictions that improve automatically." This requires three things to exist simultaneously: a live pipeline (events flow end-to-end), an eval loop (Brier scoring against EIA ground truth), and a prompt improvement flywheel (agents that score poorly get their prompts refined). Research strongly recommends building in strict dependency order — pipeline first, then eval, then improvement — because each layer depends on the one below it. The stack is largely locked in; only two new frontend packages (recharts, date-fns) and one dev dependency (freezegun) are needed.

The highest-risk areas are: (1) silent state divergence between in-memory WorldState and DuckDB (the flush-without-acknowledgment pattern is a data integrity bug already visible in the codebase), (2) cascade feedback loops producing runaway scenarios due to PRICE_ELASTICITY=3.0 and a circuit breaker bypass loophole, and (3) the $20/day LLM budget exhausting during crisis spikes before the simulation can be rate-governed. These must be fixed before any live data flows through the system.

## Key Findings

### Recommended Stack

The existing stack (Python 3.12, FastAPI, DuckDB, H3, Anthropic SDK, React, deck.gl) covers everything needed. The eval framework should be custom Python using numpy (already a transitive dependency) rather than any ML eval library — Brier score is three lines of math, not a scikit-learn problem. Pipeline orchestration should use `asyncio.TaskGroup` within FastAPI's lifespan context, not Celery or APScheduler. WebSocket communication should use FastAPI's native `WebSocket` support, not Socket.IO. State management on the frontend should use React Context + useReducer, not Redux or Zustand. The only new additions are recharts for eval charts and date-fns for timeline formatting.

**Core technologies (new decisions only):**
- `asyncio.TaskGroup` (Python 3.11+): pipeline orchestration — structured concurrency, clean error propagation, zero new deps
- `fastapi.WebSocket` (native): real-time push — bidirectional for future scenario commands, already partially wired in frontend
- Custom numpy-based scoring: Brier score, calibration curves — trivial math, schema already built for it
- `recharts` 2.x: eval dashboard charts — React-native, lighter than D3 for standard charts
- `freezegun` 1.4+ (dev only): time mocking in eval tests — predictions resolve at specific timestamps

### Expected Features

**Must have (table stakes):**
- End-to-end data pipeline (GDELT -> agents -> cascade -> world state -> frontend) — subsystems exist, orchestration loop does not
- FastAPI REST endpoints (world state, decisions, predictions, indicators) — wrapping existing `queries.py`
- WebSocket live push (tick summaries, agent decisions, indicator changes) — frontend hook exists, backend emitter does not
- Prediction logging with structured schema (direction, magnitude, timeframe, confidence) — schema exists, agent output parsing does not
- Ground truth fetching (EIA oil prices, GDELT event verification) — EIA fetcher exists, resolver does not
- Prediction scoring with Brier score — schema has `score_direction`, `score_magnitude`, `miss_tag` columns ready
- Daily eval cron — asyncio periodic task, no scheduling library needed
- Frontend panels wired to real data — currently showing placeholders

**Should have (differentiators):**
- Automated prompt improvement loop — worst-performing agents get prompts refined by meta-LLM call; no other tool does this
- Per-agent accuracy leaderboard — reveals which actor models are calibrated; low effort, high insight
- Calibration curve visualization — standard in GJP/Metaculus; shows whether 70% confidence means 70% accuracy
- Cascade trace visualization — the unique simulation value: "tanker seized -> flow -30% -> price +$8 -> pipeline activated"
- Prediction timeline / track record — builds analyst trust in the tool
- Confidence-weighted aggregation — ensemble forecast from all agents, weighted by past accuracy

**Defer to v2+:**
- Counterfactual simulation ("what if Iran blockades tomorrow?") — engine supports it, UI is a rabbit hole
- Scenario comparison dashboard — multiple parallel simulation runs, significant complexity
- Anomaly detection on event streams — nice-to-have alerting, not core to predictions
- Multi-scenario support (Ukraine, Taiwan) — premature abstraction; Hormuz-specific first

**Anti-features (explicitly avoid):**
- Multi-user auth, free-text predictions, real-time LLM streaming to frontend, manual prediction scoring, 200+ agent personas

### Architecture Approach

The recommended architecture is a **single-process asyncio event bus** where all components communicate through typed, enveloped messages. The EventBus (an in-process pub/sub backed by asyncio) decouples ingestion, agents, simulation, persistence, and WebSocket broadcast from each other, enabling independent testing and future subscriber additions (like the eval loop) without modifying existing code. The TickOrchestrator owns the tick lifecycle exclusively — no component independently advances the tick, preventing race conditions on WorldState. All writes flow through the single DbWriter queue (matching DuckDB's single-writer constraint). The frontend uses REST for initial page load and WebSocket for incremental delta updates.

**Major components:**
1. **EventBus** (`parallax/bus.py`) — in-process pub/sub backbone; typed envelope with topic, tick, timestamp, payload
2. **TickOrchestrator** (`parallax/simulation/orchestrator.py`) — tick heartbeat; collects events, routes agents, validates via CircuitBreaker, runs cascade, flushes deltas
3. **IngestionService** (`parallax/ingestion/`) — GDELT + EIA polling; pure data acquisition, never reads WorldState, never calls LLMs
4. **AgentRouter + Runner** (`parallax/agents/`) — keyword routing, parallel LLM calls via asyncio.gather, budget-gated
5. **DbWriter** (`parallax/db/`) — single-writer queue for DuckDB; all components enqueue, none hold their own connections
6. **WebSocket Broadcast** (`parallax/api/ws.py`) — tick-batched messages to frontend; fire-and-forget, frontend maintains local state
7. **REST API** (`parallax/api/routes.py`) — read-only endpoints for page load and historical queries
8. **Eval Loop** (`parallax/eval/`) — daily scoring cron; reads DB, writes scores, triggers prompt version updates

**Critical missing file:** `parallax/main.py` — the wiring entrypoint that instantiates and connects all components does not yet exist.

### Critical Pitfalls

1. **Silent WorldState/DB divergence** — `world_state.py` clears dirty set before `DbWriter` confirms write; `writer.py:45-46` swallows all exceptions. Fix: write-acknowledgment before clearing dirty set; replace bare `except Exception`; add periodic in-memory vs DB consistency check. Must be fixed in the first integration phase.

2. **Cascade feedback loops creating runaway scenarios** — PRICE_ELASTICITY=3.0 with no damping; circuit breaker has an exogenous shock bypass that agent-initiated escalations can exploit; cascade applies rules statefully without rollback. Fix: cumulative damping per escalation tick; separate exogenous bypass from agent escalations; atomic cascade transactions (compute all deltas, validate, apply or reject). Must be fixed before agents are connected to cascade.

3. **LLM budget exhaustion during crisis spikes** — 50 agents, bursty GDELT events, no event-level budget gating. A 4-hour crisis spike can exhaust the $20/day budget by noon. Fix: event-level budget gating at the router; priority tiers (full sweep only for Goldstein > 7 events); hourly budget pacing with spike reserves.

4. **GDELT noise overwhelming signal** — semantic dedup at 0.90 catches paraphrases but not the same incident from different angles (e.g., "Iran seizes tanker" / "UK condemns seizure" / "prices surge after seizure" are three events, one incident). Fix: incident-level clustering by (actor1, actor2, action_category, time_window); one agent activation per incident, not per article.

5. **Prediction eval scoring against missing ground truth** — most geopolitical predictions cannot be auto-scored; GDELT provides media coverage not ground truth; EIA has 1-week lag on some series. Fix: categorize predictions at creation time (auto-scorable/semi-auto/manual-only); start the automated eval loop with oil price predictions only; surface manual predictions in dashboard for analyst scoring.

## Implications for Roadmap

Based on research, the build order is strictly dependency-constrained. Nothing works without the pipeline. Eval cannot score predictions that don't exist. Prompt improvement cannot run without eval scores. Frontend cannot show data without an API.

### Phase 1: Foundation Hardening + Branch Integration

**Rationale:** Ten parallel feature branches exist with no integration contracts. Interface mismatches will emerge at every merge boundary. The WorldState/DB divergence bug and cascade feedback loop vulnerabilities must be fixed before any live data flows — otherwise every downstream phase builds on broken infrastructure.

**Delivers:** A stable, merged codebase with: corrected DbWriter (write acknowledgment, no swallowed exceptions), cascade engine hardening (damping, transaction boundaries), schema versioning (for Docker volume safety), and shared Pydantic contracts that all subsystems import from a common module.

**Addresses:** Table-stakes prerequisite — pipeline wiring, agent logging, eval cron all depend on a reliable persistence layer.

**Avoids:** Silent state divergence (Pitfall 1), cascade runaway (Pitfall 3), nondeterministic cascade ordering (Pitfall 12), Docker volume schema corruption (Pitfall 15), integration nightmare from parallel branches (Pitfall 7).

**Research flag:** Standard patterns — merge strategy and DuckDB write patterns are well-understood. Skip research-phase.

### Phase 2: Live Pipeline (EventBus + Orchestrator + Ingestion)

**Rationale:** The EventBus and TickOrchestrator are the spine of the system. Without them, no component can communicate. This phase wires real GDELT events into the simulation without agent LLM calls — proving the end-to-end flow cheaply before introducing the most expensive and complex component (agents).

**Delivers:** `main.py` entrypoint, EventBus, TickOrchestrator tick lifecycle, GDELT + EIA polling loop connected to the bus, curated events appearing in DuckDB and on frontend news ticker. A running simulation that responds to real-world data, even before agents deliberate.

**Addresses:** End-to-end data pipeline (table stakes), clock drift synchronization (tick-gated ingestion), GDELT noise reduction (incident clustering at the router boundary).

**Avoids:** Clock drift (Pitfall 10), GDELT noise overwhelm (Pitfall 4), fat events on bus (Anti-Pattern 5).

**Research flag:** Standard asyncio patterns — skip research-phase.

### Phase 3: WebSocket + REST API

**Rationale:** Once deltas flow through the bus, push them to the frontend. REST gives page-load state; WebSocket gives live updates. This phase makes the simulation visible before agents are wired in, enabling visual verification of cascade behavior with hardcoded or GDELT-triggered events.

**Delivers:** All REST endpoints (`/api/state`, `/api/decisions`, `/api/predictions`, `/api/indicators`, `/api/agents`, `/health`), WebSocket server with tick-batched messages, frontend panels wired to real data (H3 map colors from world state, oil price indicator, threat level, agent activity feed). Reconnect state sync (catch-up on last-known tick). Server-side tick-summary batching to prevent browser freeze.

**Uses:** `fastapi.WebSocket` (native), Pydantic `WSMessage` envelope, recharts (added to frontend), date-fns (added to frontend).

**Avoids:** WebSocket flooding (Pitfall 5), reconnect desync (Pitfall 13), WebSocket-as-source-of-truth (Architecture Anti-Pattern 4).

**Research flag:** FastAPI WebSocket patterns are well-documented. Skip research-phase.

### Phase 4: Agent Integration

**Rationale:** Agent LLM calls are the most expensive and complex component. Wiring them last means the pipeline is already proven to work end-to-end with hardcoded data — so failures during agent wiring are agent problems, not pipeline problems. This phase introduces the budget gating, event-level priority routing, and API rate limit handling that protect the $20/day constraint.

**Delivers:** Full end-to-end pipeline: real GDELT event -> agent deliberation -> AgentDecision -> cascade -> world state delta -> frontend update. Event-level budget gating (priority tiers by Goldstein score), hourly budget pacing, agent context windowing (sliding window to prevent context overflow), Anthropic API retry with exponential backoff.

**Addresses:** End-to-end pipeline (table stakes), agent prompt versioning (low complexity, schema already supports it).

**Avoids:** Budget exhaustion (Pitfall 2), API rate limits halting sweep (Pitfall 11), context window overflow (Pitfall 9), agent-initiated cascade runaway (Pitfall 3 secondary concern).

**Research flag:** Budget pacing and context windowing patterns are somewhat novel for this domain. Consider research-phase for hourly pacing strategy and context compaction approach.

### Phase 5: Eval Foundation

**Rationale:** With the full pipeline running and predictions being logged, the eval loop can score them. This phase establishes the core value proposition: predictions that are continuously measured against reality. Starting with oil price predictions only (auto-scorable via EIA) avoids the ground truth availability problem for geopolitical predictions.

**Delivers:** Brier score + direction/magnitude scoring engine, EIA ground truth fetcher wired to resolver, daily eval cron, `eval_results` table populated, prediction categorization (auto/semi-auto/manual), miss tagging (timing/magnitude/direction/black_swan). Scenario config hashing stored with simulation runs.

**Addresses:** Prediction scoring, ground truth fetching, daily eval cron (table stakes).

**Avoids:** Stale/missing ground truth (Pitfall 6), unversioned configs corrupting eval comparisons (Pitfall 14).

**Research flag:** Oil price scoring is straightforward. The semi-auto GDELT-based event verification is more ambiguous — flag for research-phase to determine what GDELT fields are reliable proxies for event confirmation.

### Phase 6: Intelligence Flywheel (Eval Visibility + Prompt Improvement)

**Rationale:** With scores accumulating, the differentiating features become buildable: the leaderboard needs scores to display, calibration curves need enough predictions per bucket (30+ per bucket), and the prompt improvement loop needs reliable scores to act on. This is the highest-complexity, highest-value phase.

**Delivers:** Per-agent accuracy leaderboard, calibration curve visualization, prediction timeline/track record, source attribution on predictions. Automated prompt improvement loop: identify worst performers, generate prompt patches via Haiku (budget: ~$3/day), A/B test new vs old prompt version, promote winner.

**Addresses:** All differentiator features. Cascade trace visualization can be added here (cascade effects are already captured in bus events; need persistence and frontend rendering).

**Avoids:** Prompt improvement loop feeding on bad scores (use only auto-scored, high-confidence predictions for tuning). Budget: Haiku for meta-prompting, ~$3/day allocation.

**Research flag:** The LLM-rewrites-its-own-prompts loop is novel and experimental. This phase needs research-phase planning before implementation — specifically around the feedback loop stability, how to detect prompt gaming vs genuine improvement, and the A/B comparison methodology.

### Phase Ordering Rationale

- **Foundation before pipeline:** The DbWriter acknowledgment bug and cascade vulnerability are not edge cases — they will be triggered immediately when real data flows. Fixing them first prevents rework.
- **Pipeline before agents:** Proves the event bus and tick lifecycle cheaply; isolates agent wiring failures from pipeline failures.
- **API before agents:** Frontend visibility into cascade behavior (even without LLM agents) enables faster iteration on map rendering and indicator wiring.
- **Eval before improvement:** Cannot improve prompts without scores. Cannot have meaningful scores without enough predictions. Starting eval early lets scores accumulate while UI work proceeds.
- **Flywheel last:** Depends on all prior phases. The leaderboard, calibration, and prompt improvement loop are only meaningful once the system has been running long enough to generate statistically significant prediction histories.

### Research Flags

Needs `/gsd:research-phase` during planning:
- **Phase 4 (Agent Integration):** Hourly budget pacing strategy and context compaction approach are domain-specific; sparse prior art.
- **Phase 5 (Eval Foundation):** GDELT-based semi-automatic event verification — what fields are reliable proxies; needs validation against real GDELT data.
- **Phase 6 (Intelligence Flywheel):** Prompt improvement loop is experimental; feedback loop stability, gaming detection, and A/B methodology need careful design before coding.

Standard patterns (skip research-phase):
- **Phase 1 (Foundation):** DuckDB write patterns, branch merging — well-documented.
- **Phase 2 (Pipeline):** asyncio.TaskGroup, FastAPI lifespan — Python stdlib patterns.
- **Phase 3 (API/WebSocket):** FastAPI WebSocket, REST endpoints — well-documented.

## Confidence Assessment

| Area | Confidence | Notes |
|------|------------|-------|
| Stack | HIGH | Existing stack is locked in and verified from pyproject.toml. New additions (recharts, date-fns, freezegun) are minimal and low-risk. The only MEDIUM element is frontend package version verification (npm not checked). |
| Features | MEDIUM | Feature categorization is grounded in established forecasting platforms (GJP, Metaculus, IARPA). Effort estimates are uncertain — integration complexity across 10 branches is inherently hard to predict. |
| Architecture | HIGH | Directly derived from codebase analysis. asyncio event bus pattern for single-process Python is well-established. DuckDB single-writer constraint is documented. WebSocket approach is already partially implemented. |
| Pitfalls | HIGH | Six of eight critical/moderate pitfalls are grounded in specific lines of code visible in the current codebase (writer.py, cascade.py, circuit_breaker.py, world_state.py). Two (GDELT noise dedup false-negative rate, Anthropic rate limits) are MEDIUM because they depend on runtime behavior of unmerged branches. |

**Overall confidence:** MEDIUM-HIGH. The architecture and pitfall analysis are high confidence because they derive from direct codebase inspection. Feature scope is well-grounded. The main uncertainty is integration complexity across parallel branches, which is unknowable without actually merging them.

### Gaps to Address

- **Branch interface contracts:** The actual data formats produced by the agents branch and expected by the simulation branch have not been compared directly (agents branch was not inspectable). Expect 1-2 days of contract alignment per merge boundary.
- **Frontend package versions:** recharts and date-fns version compatibility with current React 18.3.1 + Vite 6 setup should be verified against npm before installation.
- **Anthropic rate limits:** The account tier determines actual request-per-minute limits. Budget pacing should be validated against real API behavior in Phase 4, not assumed from documentation.
- **GDELT incident clustering effectiveness:** The false-negative rate of pairwise semantic dedup for incident-level clustering is unknown without testing against a real crisis spike dataset. The clustering strategy in Phase 2 should be validated early with replayed GDELT data.
- **Prompt improvement loop stability:** Whether an LLM-rewrites-its-own-prompts feedback loop converges or diverges is empirically unknown for this domain. Phase 6 should include an explicit stability criterion and kill switch.

## Sources

### Primary (HIGH confidence)
- `backend/src/parallax/db/writer.py` — DbWriter architecture, exception handling pattern
- `backend/src/parallax/db/schema.py` — DuckDB schema, prediction/eval tables
- `backend/src/parallax/simulation/engine.py` — DES engine, tick lifecycle
- `backend/src/parallax/simulation/cascade.py` — cascade rules, PRICE_ELASTICITY constant
- `backend/src/parallax/simulation/circuit_breaker.py` — escalation control, exogenous bypass
- `backend/src/parallax/simulation/world_state.py` — delta tracking, flush pattern
- `backend/src/parallax/simulation/config.py` — ScenarioConfig, hardcoded parameters
- `backend/pyproject.toml` — locked dependency versions
- `.planning/PROJECT.md` — requirements, constraints, active decisions
- `.planning/codebase/CONCERNS.md` — documented tech debt and fragile areas
- `docker-compose.yml` — container setup, volume persistence

### Secondary (MEDIUM confidence)
- Good Judgment Project / Tetlock "Superforecasting" — Brier score, calibration curve methodology
- IARPA ACE/SAGE program design — prediction scoring standards for geopolitical forecasting
- Metaculus scoring rules — direction/magnitude/calibration patterns
- Python 3.11 PEP 654 — asyncio.TaskGroup introduction and semantics
- GDELT data characteristics — 15-minute cadence, BigQuery interface, Goldstein scale (training data, may be stale)

### Tertiary (LOW confidence)
- Anthropic API rate limits — account-tier dependent, should be validated in Phase 4
- Frontend package current versions (recharts 2.x, date-fns 3.x) — not verified against npm; check before installation
- LLM prompt improvement loop convergence — experimental, no prior art for this specific domain

**Note:** WebSearch and Context7 were unavailable during all research sessions. All findings are derived from direct codebase analysis, project documentation, and training data. Version numbers should be verified against live registries before dependency installation.

---
*Research completed: 2026-03-30*
*Ready for roadmap: yes*
