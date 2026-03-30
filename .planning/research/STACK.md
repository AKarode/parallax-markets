# Technology Stack

**Project:** Parallax - Geopolitical Crisis Simulation Platform
**Researched:** 2026-03-30
**Focus:** Eval framework, backend API, end-to-end pipeline wiring
**Overall Confidence:** MEDIUM (based primarily on training data + codebase analysis; WebSearch/Context7 unavailable this session)

## Existing Stack (Locked In)

These are already in the codebase and should NOT change. Listed for completeness.

| Technology | Version | Purpose |
|------------|---------|---------|
| Python | 3.12 | Backend runtime |
| FastAPI | 0.115+ | REST/WebSocket API server |
| Uvicorn | 0.34+ | ASGI server |
| DuckDB | 1.2+ | Embedded OLAP database |
| H3 | 4.1+ | Hexagonal geospatial indexing |
| Anthropic SDK | 0.52+ | Claude API for agent reasoning |
| sentence-transformers | 3.4+ | Semantic dedup embeddings |
| Pydantic | 2.10+ | Data validation and serialization |
| httpx | 0.28+ | Async HTTP client |
| websockets | 14.0+ | WebSocket support |
| React | 18.3.1 | Frontend UI framework |
| Vite | 6.0.0 | Frontend build tool |
| TypeScript | 5.6.2 | Frontend type safety |
| deck.gl | 9.1.0 | Geospatial visualization |
| MapLibre GL | 4.7.0 | Map rendering |
| Docker Compose | -- | Container orchestration |

## New Stack Recommendations

### 1. Eval Framework

#### Scoring Engine: Custom (No External Library)

**Recommendation:** Implement Brier score, calibration, and direction/magnitude scoring directly. Do NOT add a prediction-market or ML-eval library.

**Confidence:** HIGH

**Rationale:**
- The predictions table already has `score_direction`, `score_magnitude`, `miss_tag`, `ground_truth`, `confidence` fields -- the schema is purpose-built for custom scoring
- Brier score is `(confidence - outcome)^2` -- 3 lines of Python, no library needed
- Calibration curves are binning + averaging -- trivially implementable with numpy (already a transitive dependency via sentence-transformers)
- ML eval frameworks (scikit-learn metrics, Weights & Biases) are overkill for ~50 agents making ~10-20 predictions/day
- Domain-specific scoring (direction accuracy, magnitude range hit, timeliness) cannot be captured by generic frameworks

| Component | Technology | Why |
|-----------|-----------|-----|
| Brier scoring | Custom Python | 3 lines, no dependency warranted |
| Calibration curves | numpy | Already transitive dep; bin predictions by confidence, compare to hit rate |
| Direction accuracy | Custom Python | Boolean: predicted direction matches actual |
| Magnitude scoring | Custom Python | Check if actual value falls in predicted `magnitude_range` |
| Ground truth fetching | httpx (existing) | EIA API for oil prices, GDELT for event verification |
| Eval persistence | DuckDB (existing) | `eval_results` table already in schema |
| Eval scheduling | asyncio + cron pattern | Daily eval loop as async task in the main event loop |

**What NOT to use:**
- `scikit-learn` metrics -- pulls in heavy ML stack for simple math; you already have numpy
- `Weights & Biases` / `MLflow` -- designed for ML experiment tracking, not geopolitical prediction scoring; adds infra complexity
- `Metaculus API` / prediction market APIs -- interesting for benchmarking later, but not for core scoring
- `promptfoo` / `ragas` -- LLM eval frameworks test prompt quality, not prediction accuracy; different problem

#### Prompt Improvement Pipeline

**Recommendation:** Store eval scores per (agent_id, prompt_version) in DuckDB. Use a simple "promote/demote" loop: if agent accuracy drops below threshold, generate a revised system prompt via Claude and store it as a new version.

| Component | Technology | Why |
|-----------|-----------|-----|
| Prompt versioning | DuckDB `agent_prompts` table | Already exists with (agent_id, version) PK |
| Score aggregation | DuckDB SQL | Aggregate eval_results by agent_id, prompt_version |
| Prompt generation | Anthropic SDK (existing) | Use Claude to rewrite underperforming prompts based on miss patterns |
| A/B comparison | Custom Python | Compare eval scores across prompt versions for same agent |

**Confidence:** MEDIUM -- the prompt-improvement-via-LLM approach is experimental. The storage and scoring parts are straightforward.

---

### 2. Backend API Layer

#### WebSocket: Use FastAPI's Built-in WebSocket Support

**Recommendation:** Use `fastapi.WebSocket` directly. Do NOT add Socket.IO or a separate WebSocket server.

**Confidence:** HIGH

**Rationale:**
- FastAPI has native WebSocket support via Starlette -- no additional dependency
- The project already has `websockets>=14.0` in deps (used by Uvicorn for WS protocol handling)
- Socket.IO adds a compatibility layer + client library for features you don't need (rooms, namespaces, fallback polling) -- this is a single-analyst tool
- The nginx config already proxies `/ws` to the backend

| Component | Technology | Why |
|-----------|-----------|-----|
| WebSocket endpoint | `fastapi.WebSocket` | Native, zero new deps, Starlette-backed |
| Connection management | Custom `ConnectionManager` class | Track active connections, broadcast to all |
| Message serialization | Pydantic models + `.model_dump_json()` | Type-safe messages, already using Pydantic everywhere |
| Heartbeat/keepalive | Ping/pong frames | Built into websockets protocol, Uvicorn handles it |
| Client reconnection | Frontend `useWebSocket` hook (existing) | Already built with auto-reconnect |

**Message types to define (Pydantic models):**

```python
class WSMessage(BaseModel):
    type: Literal["event", "decision", "indicator", "world_state", "eval"]
    payload: dict
    tick: int
    timestamp: datetime
```

**What NOT to use:**
- `python-socketio` -- adds rooms/namespaces/polling fallback, none needed for single-analyst tool
- `channels` (Django) -- wrong framework
- Separate WebSocket process -- unnecessary complexity; FastAPI handles WS and REST in same process
- `sse-starlette` (Server-Sent Events) -- one-directional; you need bidirectional for simulation control commands (start/pause/step)

#### REST API: FastAPI with Standard Patterns

**Recommendation:** Use FastAPI dependency injection for shared state (DuckDB connection, simulation engine, world state). Use `APIRouter` for modular organization.

**Confidence:** HIGH

| Component | Technology | Why |
|-----------|-----------|-----|
| Route organization | `fastapi.APIRouter` | Group by domain: `/api/simulation`, `/api/agents`, `/api/eval`, `/api/indicators` |
| Shared state | FastAPI `Depends()` + app.state | DI for DbWriter, WorldState, SimulationEngine |
| Request validation | Pydantic v2 models | Already the project standard |
| Response serialization | Pydantic `.model_dump()` | Consistent with rest of codebase |
| Background tasks | `fastapi.BackgroundTasks` + asyncio tasks | For long-running ops like "run eval now" |
| Error handling | FastAPI exception handlers | Structured error responses |

**API route structure:**

```
GET  /api/simulation/status      -- current tick, clock mode, queue depth
POST /api/simulation/start       -- start live mode
POST /api/simulation/pause       -- pause
POST /api/simulation/step        -- advance one tick (replay)
GET  /api/agents                 -- list all agents with latest scores
GET  /api/agents/{id}/decisions  -- decision history
GET  /api/agents/{id}/predictions -- predictions with scores
GET  /api/eval/scores            -- aggregated eval scores
GET  /api/eval/calibration       -- calibration curve data
POST /api/eval/run               -- trigger eval cycle
GET  /api/indicators             -- oil price, flow, threat levels
GET  /api/events                 -- recent curated events
WS   /ws                         -- real-time event stream
```

---

### 3. End-to-End Pipeline Wiring

#### Pipeline Orchestrator: asyncio Task Group

**Recommendation:** Use Python's `asyncio.TaskGroup` (Python 3.11+) to run the pipeline stages as concurrent tasks within the FastAPI lifespan.

**Confidence:** HIGH

**Rationale:**
- All pipeline components are already async (DbWriter.run, SimulationEngine.run_until_tick, GDELT fetching via httpx)
- FastAPI's `lifespan` context manager is the standard place to start/stop background tasks
- `asyncio.TaskGroup` (available since Python 3.11, project requires 3.11+) provides structured concurrency with proper error propagation
- No external task queue (Celery, Dramatiq) needed -- this is a single-machine, single-user tool

| Component | Technology | Why |
|-----------|-----------|-----|
| Task lifecycle | FastAPI `lifespan` + `asyncio.TaskGroup` | Start all pipeline tasks at startup, clean shutdown |
| GDELT polling | asyncio periodic task (15min interval) | Fetch → filter → dedup → enqueue events |
| EIA polling | asyncio periodic task (daily) | Fetch oil prices → update indicators |
| Event processing | SimulationEngine (existing) | Events dispatched to agents via DES |
| Agent execution | Parallel async via `asyncio.gather` | Already designed for parallel LLM calls |
| State broadcasting | WorldState → WebSocket broadcast | On each tick, flush deltas and push to connected clients |
| Eval scheduling | asyncio periodic task (daily) | Score matured predictions against ground truth |
| DB persistence | DbWriter (existing) | Single-writer queue, already async |

**Pipeline flow:**

```
GDELT Poller (15min) ──┐
EIA Poller (daily) ────┤
                       ▼
              Event Router
                       │
              ┌────────┴────────┐
              ▼                 ▼
        Agent Runner      Cascade Engine
              │                 │
              └────────┬────────┘
                       ▼
               WorldState Update
                       │
              ┌────────┴────────┐
              ▼                 ▼
         DB Writer         WS Broadcast
                                │
                           Frontend
```

**What NOT to use:**
- `Celery` / `Dramatiq` -- requires Redis/RabbitMQ broker; massive overkill for single-machine tool
- `APScheduler` -- adds dependency for something asyncio handles natively with `asyncio.sleep` loops
- `Prefect` / `Airflow` -- workflow orchestration platforms for data teams, not real-time simulation
- `asyncio.create_task` without TaskGroup -- no structured concurrency, errors can be silently lost

#### Periodic Task Pattern

**Recommendation:** Simple async loop pattern, no scheduling library needed.

```python
async def periodic_task(fn, interval_seconds: float, name: str):
    """Run fn every interval_seconds. For use inside TaskGroup."""
    while True:
        try:
            await fn()
        except Exception:
            logger.exception(f"Periodic task {name} failed")
        await asyncio.sleep(interval_seconds)
```

**Confidence:** HIGH -- this is standard Python async pattern. No library needed.

---

### 4. Testing Additions

| Component | Technology | Version | Why |
|-----------|-----------|---------|-----|
| WebSocket testing | `httpx` + `starlette.testclient` | (existing) | FastAPI's TestClient supports WebSocket testing natively |
| Async test fixtures | `pytest-asyncio` | 0.25+ (existing) | Already in dev deps |
| Time mocking | `freezegun` | 1.4+ | Mock `datetime.now()` for eval scoring tests (predictions resolve at specific times) |
| API integration tests | `httpx.AsyncClient` | 0.28+ (existing) | Test REST endpoints with async client |

**New dev dependency to add:**

```toml
[project.optional-dependencies]
dev = [
    "pytest>=8.3,<9",
    "pytest-asyncio>=0.25,<1",
    "pytest-httpx>=0.35,<0.36",
    "freezegun>=1.4,<2",       # NEW: time mocking for eval tests
]
```

**What NOT to add:**
- `factory-boy` -- useful for complex ORM models, overkill for DuckDB raw SQL
- `hypothesis` -- property-based testing is valuable but not priority for wiring phase
- `playwright` -- already mentioned in project memory for browser tests, add when frontend panels have real data

---

### 5. Frontend Additions (Minimal)

The frontend already has React, Vite, deck.gl, MapLibre, and a WebSocket hook. For wiring real data:

| Component | Technology | Why |
|-----------|-----------|-----|
| State management | React Context + useReducer | Sufficient for single-user tool; no Redux/Zustand needed |
| Data fetching | Native `fetch` + custom hooks | No need for React Query/SWR -- data comes via WebSocket, REST is infrequent |
| Chart library | `recharts` 2.x | Lightweight, React-native charts for eval dashboard (calibration curves, accuracy over time) |
| Date formatting | `date-fns` 3.x | Lightweight date utils for timeline display |

**New frontend dependencies:**

```bash
npm install recharts date-fns
```

**What NOT to add:**
- `@tanstack/react-query` -- most data arrives via WebSocket push, not REST polling; React Query's cache invalidation model doesn't fit
- `Redux` / `Zustand` -- single analyst, ~5 state slices; Context + useReducer is sufficient
- `D3.js` directly -- deck.gl already handles the geo viz; recharts wraps D3 for standard charts
- `ag-grid` / data table libraries -- agent list and predictions are small enough for simple HTML tables

**Confidence:** MEDIUM -- frontend package versions not verified against current releases.

---

## Full Dependency Summary

### Backend: New Dependencies

| Package | Version | Purpose | New? |
|---------|---------|---------|------|
| `freezegun` | >=1.4 | Time mocking in eval tests | YES (dev only) |
| `numpy` | (transitive) | Calibration math | NO (via sentence-transformers) |

**That is it.** The existing stack covers everything needed. The eval framework, API layer, and pipeline wiring are all achievable with what is already installed.

### Frontend: New Dependencies

| Package | Version | Purpose | New? |
|---------|---------|---------|------|
| `recharts` | ^2.12 | Charts for eval dashboard | YES |
| `date-fns` | ^3.6 | Date formatting for timelines | YES |

### Infrastructure: No Changes

Docker Compose, nginx proxy, DuckDB volume -- all unchanged.

---

## Alternatives Considered

| Category | Recommended | Alternative | Why Not |
|----------|-------------|-------------|---------|
| Eval scoring | Custom Python | scikit-learn metrics | Pulls heavy ML deps for simple math |
| Eval tracking | DuckDB tables | MLflow / W&B | Adds infrastructure for 50-agent tool |
| WebSocket | FastAPI native | Socket.IO | Unnecessary abstraction for single-client |
| Task scheduling | asyncio loops | APScheduler / Celery | External deps for something asyncio does natively |
| Pipeline orchestration | asyncio.TaskGroup | Prefect / Airflow | Cloud orchestrators for a local Docker tool |
| State management | React Context | Redux / Zustand | Over-engineered for single-analyst UI |
| Charts | recharts | D3.js / Chart.js / Plotly | recharts is React-native, simpler API, sufficient for eval dashboards |
| Data fetching | Native fetch + WS | React Query / SWR | Data is push-based via WebSocket, not pull-based |
| Prompt eval | Custom scoring | promptfoo / ragas | Those eval prompt quality, not prediction accuracy |

---

## Installation Changes

### Backend

```bash
# No new production dependencies
# Dev only:
pip install -e ".[dev]"  # freezegun added to dev deps
```

### Frontend

```bash
cd frontend
npm install recharts date-fns
```

---

## Architecture Implications for Stack

The stack choices reinforce a **monolithic async** architecture:

1. **Single Python process** runs FastAPI (REST + WS), simulation engine, pipeline tasks, and eval -- all via asyncio
2. **No message broker** -- events flow through in-memory asyncio queues and the DES engine
3. **No external scheduler** -- periodic tasks are asyncio loops within the FastAPI lifespan
4. **No separate eval service** -- scoring runs as a periodic task in the same process
5. **DuckDB single-writer** constraint is satisfied by the existing DbWriter queue pattern

This is correct for v1: single analyst, local Docker, $20/day budget. Scaling to multi-user would require splitting into services, but that is explicitly out of scope.

---

## Confidence Assessment

| Area | Confidence | Rationale |
|------|------------|-----------|
| Eval scoring approach | HIGH | Schema already designed for it; Brier score is trivial math |
| FastAPI WebSocket | HIGH | Native Starlette support, well-documented, already partially wired |
| asyncio.TaskGroup pipeline | HIGH | Standard Python 3.11+ pattern, all components already async |
| No new backend deps needed | HIGH | Verified against existing pyproject.toml and component requirements |
| recharts for frontend charts | MEDIUM | Not verified against latest release; may need version check |
| Prompt improvement via LLM | MEDIUM | The storage/scoring is standard; the "LLM rewrites its own prompts" loop is experimental |
| Frontend state management | MEDIUM | Context + useReducer is sufficient assumption based on single-user; may need reassessment if UI complexity grows |

---

## Sources

- Codebase analysis: `backend/pyproject.toml`, `backend/src/parallax/db/schema.py`, `backend/src/parallax/simulation/engine.py`
- Project context: `.planning/PROJECT.md`, `.planning/codebase/STACK.md`
- FastAPI WebSocket documentation (training data, may be 6-18 months stale -- flag for verification)
- asyncio.TaskGroup introduced in Python 3.11 PEP 654 (training data, verified by project's `requires-python >= 3.11`)
- Brier score definition: standard statistical scoring rule (not library-dependent)

**Note:** WebSearch and Context7 were unavailable during this research session. Version numbers for new frontend deps (recharts, date-fns) should be verified against npm before installation. All backend recommendations use existing dependencies and are HIGH confidence.
