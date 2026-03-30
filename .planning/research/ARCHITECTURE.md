# Architecture Patterns

**Domain:** Real-time geopolitical crisis simulation with AI agent deliberation
**Researched:** 2026-03-30
**Confidence:** MEDIUM (based on codebase analysis + established async/event-driven patterns; no web search available to verify SOTA)

## Executive Summary

Parallax has five major subsystems built on parallel branches: ingestion, agents, simulation engine, database, and frontend. The central challenge is wiring them into a single live pipeline where real-world events flow through agent deliberation, into cascade simulation, out to a persistent world state, and up to the frontend via WebSocket -- all running continuously under a $20/day LLM budget.

The recommended architecture is a **single-process async event bus** (not microservices, not message queues) because this is a single-analyst local tool running in Docker. Simplicity beats distributed systems patterns here.

---

## Recommended Architecture

### High-Level Data Flow

```
GDELT BigQuery (15min poll)          EIA API v2 (hourly poll)
        |                                     |
        v                                     v
  +-----------+                        +------------+
  | Ingestion |  4-stage filter,       | Oil Price  |
  | Pipeline  |  semantic dedup,       | Fetcher    |
  |           |  entity extraction     |            |
  +-----+-----+                        +------+-----+
        |                                     |
        | CuratedEvent                        | PriceUpdate
        v                                     v
  +---------------------------------------------------+
  |              EVENT BUS (asyncio)                   |
  |  In-process pub/sub. Topics:                       |
  |  - ingestion.curated_event                         |
  |  - ingestion.price_update                          |
  |  - agent.decision                                  |
  |  - simulation.cascade_result                       |
  |  - simulation.world_state_delta                    |
  |  - simulation.tick_complete                        |
  |  - eval.prediction_scored                          |
  +--------+----------+----------+----------+----------+
           |          |          |          |
           v          v          v          v
    +----------+ +----------+ +--------+ +----------+
    | Agent    | | Sim      | | DB     | | WebSocket|
    | Router + | | Engine + | | Writer | | Broadcast|
    | Runner   | | Cascade  | |        | | Server   |
    +----------+ +----------+ +--------+ +----------+
                                              |
                                              v
                                        +-----------+
                                        | Frontend  |
                                        | React +   |
                                        | deck.gl   |
                                        +-----------+
```

### Why Single-Process Event Bus (Not Microservices)

| Concern | Microservices | Single-Process Bus | Winner |
|---------|--------------|-------------------|--------|
| Deployment complexity | Multiple containers, networking | One backend process | Bus |
| Latency (event to frontend) | Network hops, serialization | In-memory, zero-copy | Bus |
| Debugging | Distributed tracing needed | Single stack trace | Bus |
| State sharing (WorldState) | Requires shared DB reads | Direct memory reference | Bus |
| Failure modes | Partial failures, retry logic | Process dies = all dies (acceptable for local tool) | Bus |
| Scalability | Horizontal | Vertical only | Microservices |

Scalability does not matter here. This is a single-analyst tool on a laptop. The bus pattern keeps the codebase simple and the latency low.

---

## Component Boundaries

### 1. Event Bus (`parallax/bus.py`)

**Responsibility:** In-process async pub/sub. Components publish typed events; subscribers receive them asynchronously.

**Interface:**
```python
class EventBus:
    async def publish(self, topic: str, payload: Any) -> None
    def subscribe(self, topic: str, handler: Callable) -> None
    def unsubscribe(self, topic: str, handler: Callable) -> None
```

**Implementation:** `asyncio.Queue` per subscriber, or simpler: iterate subscriber list and `asyncio.create_task` each handler call. No external dependencies.

**Communicates with:** Everything. This is the backbone.

**Why not just direct function calls?** Because the pipeline has fan-out (one curated event triggers both agent routing AND database persistence AND frontend push). The bus decouples producers from consumers so modules can be developed and tested independently.

### 2. Ingestion Service (`parallax/ingestion/`)

**Responsibility:** Poll external sources, filter noise, produce curated events.

**Inputs:** GDELT BigQuery (15min), EIA API v2 (hourly)
**Outputs:** Publishes `ingestion.curated_event` and `ingestion.price_update` to bus

**Boundary rules:**
- Ingestion NEVER reads WorldState or agent state
- Ingestion NEVER calls LLMs
- Ingestion is pure data acquisition + filtering
- Runs on a timer (asyncio background task with 15min interval)

**Already built (on branch):** 4-stage noise filter, 30+ named entity extraction, structural dedup, semantic dedup at 0.90 threshold, EIA fetcher.

### 3. Agent Router + Runner (`parallax/agents/`)

**Responsibility:** Receive curated events, route to relevant agents, execute LLM deliberation, produce decisions and predictions.

**Inputs:** Subscribes to `ingestion.curated_event`, `ingestion.price_update`
**Outputs:** Publishes `agent.decision` to bus

**Boundary rules:**
- Agents read WorldState (read-only snapshot) for context in prompts
- Agents NEVER modify WorldState directly
- Agent decisions go through CircuitBreaker before becoming simulation events
- Runner respects BudgetTracker ($20/day cap, model tiering, cooldowns)
- Parallel LLM calls via asyncio.gather with concurrency limit

**Already built (on branch):** 50 agents across 12 countries, Pydantic decision schemas, keyword-based event-to-agent router, parallel runner with Anthropic prompt caching, budget tracker with auto-degrade.

**Data contract (agent.decision):**
```python
@dataclass
class AgentDecision:
    decision_id: str
    agent_id: str
    tick: int
    action_type: str  # "blockade", "deploy", "sanction", "negotiate", etc.
    target_h3_cells: list[int]
    intensity: float  # 0.0 to 1.0
    description: str
    reasoning: str
    confidence: float
    predictions: list[Prediction]  # optional forward-looking claims
```

### 4. Simulation Orchestrator (`parallax/simulation/orchestrator.py`)

**Responsibility:** Convert agent decisions into simulation events, run cascade engine, update world state, emit deltas.

**Inputs:** Subscribes to `agent.decision`
**Outputs:** Publishes `simulation.cascade_result`, `simulation.world_state_delta`, `simulation.tick_complete`

**Boundary rules:**
- Orchestrator owns the WorldState instance (single writer to in-memory state)
- Orchestrator owns the SimulationEngine instance
- CircuitBreaker validates decisions before they become SimEvents
- Cascade rules fire synchronously within a tick (deterministic)
- After processing all events for a tick, orchestrator flushes deltas

**Already built (on current branch):** SimulationEngine with DES, CascadeEngine with 6 rules, CircuitBreaker, WorldState with delta tracking, ScenarioConfig.

**Critical design: Tick lifecycle**
```
1. Tick starts
2. Collect all pending agent decisions for this tick
3. Validate each through CircuitBreaker
4. Convert approved decisions to SimEvents, schedule on engine
5. Also schedule any time-based events (periodic recalculations)
6. Engine processes all events for this tick (cascade rules fire)
7. WorldState has accumulated deltas
8. Flush deltas -> publish world_state_delta to bus
9. Publish tick_complete to bus
10. Advance tick
```

### 5. Database Persistence (`parallax/db/`)

**Responsibility:** Persist all state changes, decisions, predictions, events to DuckDB.

**Inputs:** Subscribes to `simulation.world_state_delta`, `agent.decision`, `ingestion.curated_event`, `eval.prediction_scored`
**Outputs:** None (pure sink). Provides read-only query functions for API endpoints.

**Boundary rules:**
- All writes go through single DbWriter queue (already built)
- Reads bypass the queue (DuckDB allows concurrent reads)
- Snapshots taken every N ticks (from ScenarioConfig)
- DbWriter is a bus subscriber, not called directly by other components

**Already built:** Schema (10 tables), DbWriter (async queue), queries (state reconstruction, recent decisions).

### 6. WebSocket Broadcast (`parallax/api/ws.py`)

**Responsibility:** Push real-time updates to connected frontend clients.

**Inputs:** Subscribes to `simulation.world_state_delta`, `agent.decision`, `ingestion.curated_event`, `simulation.tick_complete`, `ingestion.price_update`
**Outputs:** WebSocket frames to connected clients

**Boundary rules:**
- WebSocket server NEVER modifies any backend state
- Broadcasts are fire-and-forget (dropped if client disconnects)
- Messages are JSON-serialized, batched per tick for efficiency
- Frontend reconnects automatically (already built in frontend hook)

**Message format (recommended):**
```json
{
  "topic": "simulation.world_state_delta",
  "tick": 142,
  "timestamp": "2026-03-30T14:30:00Z",
  "payload": {
    "deltas": [
      {"cell_id": 123456, "flow": 4200000, "status": "restricted", "threat_level": 0.7}
    ]
  }
}
```

### 7. REST API (`parallax/api/routes.py`)

**Responsibility:** Serve initial state, historical queries, and configuration to frontend on page load.

**Inputs:** HTTP requests from frontend
**Outputs:** JSON responses

**Key endpoints:**
- `GET /api/state` -- Current world state snapshot (for initial page load)
- `GET /api/state/{tick}` -- Historical world state at specific tick
- `GET /api/decisions?limit=50` -- Recent agent decisions
- `GET /api/predictions` -- Active predictions
- `GET /api/agents` -- Agent registry (names, countries, roles)
- `GET /api/indicators` -- Current oil price, flow rates, insurance rates
- `GET /health` -- Health check (already expected by docker-compose)

**Boundary rules:**
- REST endpoints are read-only (no mutation via REST)
- All reads go directly to DuckDB (not through DbWriter queue)
- REST is for initial load; WebSocket is for live updates

### 8. Eval Loop (`parallax/eval/`)

**Responsibility:** Score predictions against ground truth, track accuracy, feed back into agent prompt improvement.

**Inputs:** Subscribes to `simulation.tick_complete` (to check for matured predictions), polls external ground truth sources
**Outputs:** Publishes `eval.prediction_scored` to bus

**Boundary rules:**
- Eval runs on a slower cadence (daily, not per-tick)
- Eval NEVER modifies simulation state
- Eval writes scores to predictions table and eval_results table
- Eval can trigger prompt version updates in agent_prompts table

**Not yet built.** Schema tables exist (predictions, eval_results) but no eval logic.

### 9. Frontend (`frontend/`)

**Responsibility:** Render world state on H3 hex map, show agent activity, live indicators, prediction tracking.

**Inputs:** REST API (initial load), WebSocket (live updates)
**Outputs:** User interaction (none for v1 -- read-only dashboard)

**Already built (on branch):** React + Vite + TypeScript, deck.gl + MapLibre H3 hex map, WebSocket hook with auto-reconnect, 3-column dashboard layout.

---

## Component Dependency Map

```
                    Ingestion
                   /         \
                  v           v
            Agent Router    DB Writer  <-- (curated events persisted)
                  |
                  v
            Agent Runner (LLM calls)
                  |
                  v
            Circuit Breaker
                  |
                  v
         Simulation Orchestrator
           /       |        \
          v        v         v
     Cascade   WorldState   DB Writer  <-- (deltas + decisions persisted)
      Engine   (in-memory)
                   |
                   v
            WebSocket Broadcast --> Frontend
```

**Build order implication:** You must wire bottom-up. WorldState and SimEngine already work. The orchestrator that connects agent decisions to SimEvents is the critical missing piece. Then the bus ties everything together.

---

## Data Flow: End-to-End Pipeline

### Happy Path (single GDELT event through entire system)

```
T+0:00  GDELT poller fetches new events from BigQuery
T+0:01  Ingestion pipeline filters: 200 raw -> 12 pass noise filter -> 8 pass dedup
T+0:02  8 CuratedEvents published to bus topic "ingestion.curated_event"

T+0:02  DB subscriber persists curated events to curated_events table
T+0:02  WebSocket subscriber pushes curated events to frontend (news ticker)

T+0:03  Agent Router receives events, keyword-matches to relevant agents
        Example: "IRGC naval exercise" -> routes to IRGC agent, CENTCOM agent, Aramco agent
T+0:04  Agent Runner calls Anthropic API (parallel, budget-checked)
        - IRGC agent (Haiku, routine): "Increase patrol frequency"
        - CENTCOM agent (Sonnet, escalation detected): "Recommend carrier group repositioning"
        - Aramco agent (Haiku, routine): "No action, monitor"
T+0:08  Agent decisions published to bus topic "agent.decision"

T+0:08  DB subscriber persists decisions to decisions table
T+0:08  WebSocket subscriber pushes decisions to frontend (agent activity panel)

T+0:09  Simulation Orchestrator receives decisions
        - CircuitBreaker approves IRGC and CENTCOM actions, cooldown check passes
        - Converts to SimEvents: schedule_blockade(cell_id, reduction=0.15) at current tick
T+0:09  SimEngine processes events for this tick
        - Cascade Rule 1: Blockade reduces flow by 15% in cell
        - Cascade Rule 2: Bypass activates (pipeline at 30% capacity)
        - Cascade Rule 3: Net loss drives price from $82 -> $87
        - Cascade Rule 4: Downstream effects computed per country
        - Cascade Rule 6: Insurance rate increases
T+0:10  WorldState deltas flushed
        - Published to bus: "simulation.world_state_delta"
        - Published to bus: "simulation.tick_complete"

T+0:10  DB subscriber persists deltas to world_state_delta table
T+0:10  WebSocket subscriber pushes deltas to frontend
        - Map updates: hex colors change, threat elevation rises
        - Indicators update: oil price, flow rate, insurance rate
        - Timeline: new event marker

Total latency: ~10 seconds (dominated by LLM API calls at T+0:04 to T+0:08)
```

### Tick Timing

The simulation runs in LIVE mode with 15-minute ticks (configurable via `tick_duration_minutes` in scenario config). Within each tick:

1. **Ingest phase** (0-2s): Poll and filter external events
2. **Deliberation phase** (2-8s): Agent LLM calls (parallelized, biggest latency)
3. **Simulation phase** (<1s): Cascade rules are pure computation, very fast
4. **Broadcast phase** (<1s): Serialize and push via WebSocket

Between ticks, the system is idle. The 15-minute interval gives ample time even if LLM calls are slow.

---

## Patterns to Follow

### Pattern 1: Typed Event Envelope

**What:** Every message on the bus uses a consistent envelope with topic, tick, timestamp, and typed payload.
**When:** Always. Every bus publication.
**Why:** Enables the WebSocket broadcaster to forward messages without understanding their content. Enables DB subscriber to route to correct table. Enables frontend to dispatch to correct panel.

```python
@dataclass
class BusEvent:
    topic: str
    tick: int
    timestamp: datetime
    payload: dict[str, Any]
    source: str  # component that published
```

### Pattern 2: Orchestrator Owns the Tick

**What:** A single orchestrator controls tick advancement. No component independently advances the tick.
**When:** LIVE mode (production). In REPLAY mode the engine controls ticks directly.
**Why:** Prevents race conditions where agents deliberate on stale state. Ensures cascade rules complete before next tick begins.

```python
class TickOrchestrator:
    async def run_tick(self):
        # 1. Collect pending ingested events
        # 2. Route to agents, await decisions
        # 3. Validate through circuit breaker
        # 4. Schedule on sim engine
        # 5. Run sim engine for this tick
        # 6. Flush deltas
        # 7. Broadcast
        # 8. Advance tick
```

### Pattern 3: Read Snapshot, Write via Bus

**What:** Components that need WorldState get a read-only snapshot. Mutations only happen through the orchestrator after bus events.
**When:** Agent prompts need world context. API endpoints need current state.
**Why:** Prevents concurrent mutation of WorldState. Maintains single-writer invariant.

### Pattern 4: Graceful Degradation on LLM Failure

**What:** If agent LLM calls fail (timeout, rate limit, budget exhausted), the tick still completes with whatever decisions were obtained. Missing agents are logged, not fatal.
**When:** Any LLM call failure.
**Why:** The simulation must keep running. A missing agent opinion for one tick is acceptable; a crashed pipeline is not.

```python
results = await asyncio.gather(*agent_tasks, return_exceptions=True)
decisions = [r for r in results if isinstance(r, AgentDecision)]
errors = [r for r in results if isinstance(r, Exception)]
for e in errors:
    logger.warning("Agent call failed: %s", e)
# Continue with partial decisions
```

---

## Anti-Patterns to Avoid

### Anti-Pattern 1: Direct Component Coupling

**What:** Ingestion directly calling `agent_runner.process(event)` or agent runner directly calling `world_state.update_cell()`.
**Why bad:** Creates tight coupling. Cannot test ingestion without agents. Cannot replay events without running the full pipeline. Cannot add new subscribers (like eval) without modifying existing code.
**Instead:** Publish events to bus. Components subscribe independently.

### Anti-Pattern 2: Shared Mutable WorldState

**What:** Multiple components holding references to WorldState and mutating it.
**Why bad:** Race conditions, nondeterministic cascade results, impossible to debug.
**Instead:** Orchestrator is the single owner/writer. Others get read-only snapshots via `world_state.snapshot()`.

### Anti-Pattern 3: Synchronous LLM Calls in Tick Loop

**What:** Calling agent LLMs one at a time, blocking the tick.
**Why bad:** 50 agents * 2-5s per call = 100-250s per tick. Tick interval is 15 minutes, but latency to frontend is terrible.
**Instead:** `asyncio.gather` with concurrency limit (e.g., 10 concurrent calls). Already designed in agent runner.

### Anti-Pattern 4: WebSocket as Source of Truth

**What:** Frontend relying solely on WebSocket for state, with no REST fallback for initial load or reconnection.
**Why bad:** WebSocket disconnects lose state. Page refresh shows empty dashboard until next tick.
**Instead:** REST endpoint serves full current state on page load. WebSocket provides incremental updates. On reconnect, frontend fetches full state via REST, then resumes WebSocket.

### Anti-Pattern 5: Fat Events on the Bus

**What:** Publishing entire WorldState snapshot on every tick.
**Why bad:** WorldState could have thousands of H3 cells. Most don't change each tick. Wastes bandwidth and CPU on serialization.
**Instead:** Publish only deltas (dirty cells). Frontend maintains its own local state and applies deltas incrementally.

---

## The Main Entrypoint (`parallax/main.py`)

This is the critical file that does not yet exist. It wires everything together:

```python
# Pseudocode for main.py

app = FastAPI()
bus = EventBus()

# Initialize core
config = load_scenario_config("config/scenario_hormuz.yaml")
world_state = WorldState()
db_conn = duckdb.connect(os.environ["DUCKDB_PATH"])
create_tables(db_conn)
db_writer = DbWriter(db_conn)

# Initialize components
sim_engine = SimulationEngine(handler=..., clock_mode=ClockMode.LIVE)
cascade = CascadeEngine(config)
circuit_breaker = CircuitBreaker(config.max_escalation_per_tick, ...)
ingestion = IngestionService(bus)
agent_router = AgentRouter(bus)
agent_runner = AgentRunner(bus, budget_tracker)
orchestrator = TickOrchestrator(bus, sim_engine, cascade, circuit_breaker, world_state)

# Wire bus subscribers
bus.subscribe("ingestion.curated_event", agent_router.on_event)
bus.subscribe("ingestion.curated_event", db_writer.on_curated_event)
bus.subscribe("agent.decision", orchestrator.on_decision)
bus.subscribe("agent.decision", db_writer.on_decision)
bus.subscribe("simulation.world_state_delta", db_writer.on_delta)
bus.subscribe("simulation.world_state_delta", ws_broadcaster.on_delta)
bus.subscribe("simulation.tick_complete", ws_broadcaster.on_tick)

# REST endpoints
@app.get("/api/state")
async def get_state(): ...

# WebSocket endpoint
@app.websocket("/ws")
async def websocket_endpoint(ws: WebSocket): ...

# Startup: launch background tasks
@app.on_event("startup")
async def startup():
    asyncio.create_task(db_writer.run())
    asyncio.create_task(ingestion.poll_loop())
    asyncio.create_task(orchestrator.tick_loop())
```

---

## Suggested Build Order

Based on component dependencies, wire in this order:

### Phase 1: Bus + Orchestrator (the spine)

**Build:** EventBus, TickOrchestrator, main.py skeleton
**Why first:** Everything depends on the bus. The orchestrator is the tick heartbeat. Without these, nothing connects.
**Test:** Publish a hardcoded event, verify it flows through bus to a test subscriber.

### Phase 2: Simulation Wiring

**Build:** Connect orchestrator to existing SimEngine + CascadeEngine + WorldState
**Why second:** These components already exist and are tested. Wiring them to the orchestrator proves the tick lifecycle works.
**Test:** Hardcoded agent decision -> cascade fires -> world state updates -> deltas produced.

### Phase 3: WebSocket + REST API

**Build:** FastAPI WebSocket endpoint, REST endpoints for initial state, wire to bus
**Why third:** Once deltas flow, push them to the frontend. REST gives page-load state.
**Test:** Connect frontend, see hex map update on hardcoded events.

### Phase 4: Ingestion Wiring

**Build:** Connect existing ingestion pipeline to bus, add polling loop
**Why fourth:** Real data starts flowing. Agents not wired yet, but events appear in frontend news ticker and DB.
**Test:** GDELT poll -> curated events in DB and on frontend.

### Phase 5: Agent Wiring

**Build:** Connect existing agent router + runner to bus, wire decisions to orchestrator
**Why fifth:** This is the most complex piece (LLM calls, budget tracking, parallel execution). Wire it last so the pipeline is already proven without it.
**Test:** Real GDELT event -> agent deliberation -> decision -> cascade -> frontend update. Full pipeline.

### Phase 6: Eval Loop

**Build:** Prediction scoring, ground truth fetching, daily cron
**Why last:** Eval is orthogonal to the live pipeline. It reads from the database and writes scores. It can be built and tested independently.
**Test:** Insert test predictions, run eval scorer, verify scores written.

---

## Scalability Considerations

| Concern | At 1 User (v1) | At 10 Users | At 100 Users |
|---------|----------------|-------------|--------------|
| WebSocket connections | 1 connection, trivial | 10 connections, still trivial | Need connection manager, backpressure |
| LLM API calls | $20/day budget, ~50 calls/tick | Same (shared simulation) | Same (shared simulation) |
| DuckDB writes | Single-writer queue, fine | Same (reads scale, writes don't) | Need Postgres migration |
| WorldState memory | ~10K H3 cells, <10MB | Same | Same |
| Event bus throughput | ~100 events/tick | Same | Same |

**Bottom line:** The single-process architecture handles the v1 use case (single analyst) with enormous headroom. Do not over-engineer for scale that is explicitly out of scope.

---

## Key Technical Decisions

### DuckDB Single-Writer is the Right Call

DuckDB does not support concurrent writers. The existing DbWriter queue pattern is correct. All bus subscribers that need to persist data should enqueue writes through the DbWriter, not open their own connections.

**Confidence:** HIGH (verified from codebase, matches DuckDB's documented concurrency model)

### FastAPI WebSocket over SSE

FastAPI has native WebSocket support. The frontend already has a WebSocket hook with auto-reconnect. Server-Sent Events (SSE) would be simpler for one-way push, but WebSocket allows future bidirectional communication (e.g., analyst triggering scenario overrides). Stick with WebSocket.

**Confidence:** HIGH (already implemented on frontend branch)

### asyncio Event Bus over Redis/RabbitMQ

For a single-process local tool, an external message broker adds deployment complexity and failure modes with zero benefit. `asyncio` provides everything needed: task scheduling, queues, gather for parallelism.

**Confidence:** HIGH (architectural decision based on constraints)

### Single Orchestrator Process over Worker Pool

All components run in one Python process under one asyncio event loop. No Celery, no worker pools, no process-level parallelism. The only I/O-bound work is LLM API calls (handled by asyncio.gather) and GDELT/EIA polling (handled by httpx async). CPU-bound work (cascade rules) is negligible (<1ms per tick).

**Confidence:** HIGH (validated by examining cascade and engine code -- pure arithmetic, no heavy computation)

---

## Sources

- Codebase analysis: `backend/src/parallax/simulation/` (engine, cascade, world_state, circuit_breaker, config)
- Codebase analysis: `backend/src/parallax/db/` (schema, writer, queries)
- Codebase analysis: `docker-compose.yml`, `backend/pyproject.toml`
- Project context: `.planning/PROJECT.md`, `.planning/codebase/ARCHITECTURE.md`, `.planning/codebase/STRUCTURE.md`
- Confidence limited to MEDIUM overall because web search was unavailable to verify patterns against current community best practices. However, the async event bus pattern for single-process Python applications is well-established and the recommendations are based on direct analysis of the existing codebase constraints.

---

*Architecture research: 2026-03-30*
