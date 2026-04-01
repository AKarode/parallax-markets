<!-- GSD:project-start source:PROJECT.md -->
## Project

**Parallax**

A live geopolitical intelligence tool that simulates the Iran/Hormuz crisis in real-time. It ingests real-world news (GDELT, EIA oil prices), feeds them to 50 AI agents representing actual decision-makers (IRGC, CENTCOM, MBS/Aramco, CCP/PLA, etc.), models cascade effects (blockade → oil flow → price shock → bypass → insurance), and scores predictions against reality daily. Built for a single analyst tracking the Iran-USA situation as it unfolds.

**Core Value:** Predictions that beat human intuition about what happens next in the Iran-Hormuz crisis — continuously evaluated and improved against ground truth.

### Constraints

- **Budget**: $20/day cap on LLM calls for agent swarm — enforced by budget tracker with auto-degrade
- **Tech stack**: Python/FastAPI backend, React/Vite/TypeScript frontend, DuckDB, H3/deck.gl — established
- **Data sources**: GDELT (15min cadence), EIA API v2 — already integrated
- **Deployment**: Docker Compose locally — no cloud infra for v1
- **Timeline**: Crisis is unfolding now — sooner this works end-to-end, the more valuable it is
<!-- GSD:project-end -->

<!-- GSD:stack-start source:codebase/STACK.md -->
## Technology Stack

## Languages
- Python 3.12 - Backend API, simulation engine, spatial computing
- TypeScript/JavaScript - Frontend visualization (under development)
- YAML - Scenario configuration
- SQL - DuckDB schema and queries
## Runtime
- Python 3.12+ (backend)
- Node.js 22+ (frontend, for build only)
- pip + setuptools/hatchling (Python)
- npm (JavaScript/TypeScript)
## Frameworks
- FastAPI 0.115+ - REST/WebSocket API server
- Uvicorn 0.34+ - ASGI application server
- React 18.3.1 - UI framework
- Vite 6.0.0 - Build tool and dev server
- TypeScript 5.6.2 - Type safety for frontend
- deck.gl 9.1.0 - High-performance visualization (core, geo-layers, layers, react)
- MapLibre GL 4.7.0 - Map rendering (open-source Mapbox alternative)
- react-map-gl 7.1.8 - React wrapper for map rendering
- H3 (h3-js) - Hexagonal hierarchical geospatial indexing (frontend for viz)
- pytest 8.3 - Python test runner
- pytest-asyncio 0.25 - Async test support
- pytest-httpx 0.35 - HTTP mocking
- Vite 6.0.0 - JavaScript bundler and dev server
- @vitejs/plugin-react 4.3.4 - React JSX support in Vite
- Babel 7.29.0 - JavaScript transpilation (indirect dependency)
- Rollup 4+ - Module bundler (indirect dependency)
## Key Dependencies
- duckdb 1.2+ - Embedded OLAP database for world state and deltas
- h3 4.1+ - Hexagonal geospatial indexing for ocean/chokepoint zones
- searoute 1.3+ - Sea route optimization and distance calculations
- shapely 2.0+ - Geometric operations for spatial analysis
- anthropic 0.52+ - Claude API client for agent reasoning
- sentence-transformers 3.4+ - Embedding models for semantic analysis
- pydantic 2.10+ - Data validation and serialization
- websockets 14.0+ - WebSocket support for real-time simulation updates
- httpx 0.28+ - Async HTTP client for external API calls
- pyyaml 6.0+ - YAML scenario configuration parsing
- google-cloud-bigquery 3.27+ - BigQuery integration for historical data
## Configuration
- `ANTHROPIC_API_KEY` - Claude API authentication (required for agents)
- `GOOGLE_APPLICATION_CREDENTIALS` - GCP service account JSON path (optional, for BigQuery)
- `EIA_API_KEY` - Energy Information Administration API key (optional)
- `DUCKDB_PATH` - File path for DuckDB database (default: `/app/data/parallax.duckdb`)
- `PARALLAX_ADMIN_PASSWORD` - Admin authentication password (default: `admin`)
- `PARALLAX_INVITE_SEED` - Seed for invitation token generation (default: `dev-seed`)
- Scenario config: `backend/config/scenario_hormuz.yaml`
- No Vite config file detected in frontend (using defaults)
- No TypeScript config detected (tsconfig.tsbuildinfo present from previous build)
## Platform Requirements
- Docker + Docker Compose (for containerized dev environment)
- Python 3.12 runtime with build tools (gcc, make)
- Node.js 22+ for frontend builds
- curl (for health checks in Docker)
- Docker containers (backend: Python 3.12-slim, frontend: nginx:alpine)
- DuckDB file storage (persistent volume: `duckdb-data`)
- Anthropic API access (Claude 3.x models)
- Optional: Google Cloud BigQuery for data warehousing
## Package Management
- Installation: `pip install -e ".[dev]"` (editable install with dev dependencies)
- Testing: `pytest tests/`
- DuckDB extensions preloaded in Docker build step
- Installation: `npm ci` (clean install from lock file)
- Build: `npm run build` (Vite production build to `/dist`)
- Artifacts served by nginx in production
## Infrastructure Stack
- Docker Compose orchestrates 2 services:
- Backend exposes port 8000 internally
- Frontend proxy layer (nginx) on port 3000 (public)
- WebSocket upgrade support in nginx (for real-time simulation)
- API proxying: `/api/*` routes to backend
- WebSocket proxying: `/ws` routes to backend with connection upgrade headers
- Named volume: `duckdb-data` (mounted at `/app/data` in backend)
- DuckDB file path configurable via env var
<!-- GSD:stack-end -->

<!-- GSD:conventions-start source:CONVENTIONS.md -->
## Conventions

## Naming Patterns
- Lowercase with underscores: `engine.py`, `circuit_breaker.py`, `h3_utils.py`
- Test files follow pattern: `test_<module>.py`
- Module names match concept names (e.g., `cascade.py` for cascade logic)
- Snake case: `apply_blockade()`, `compute_price_shock()`, `lat_lng_to_cell_for_zone()`
- Descriptive verb-first pattern: `get_`, `compute_`, `apply_`, `activate_`, `allow_`, `record_`
- Private methods prefixed with `_`: `_handler`, `_queue`, `_cells`
- Snake case for all variables: `cell_id`, `supply_loss`, `threat_level`, `bypass_flow`
- Descriptive names preferred over abbreviations: `shock_threshold` not `sthresh`
- Collection suffixes indicate plurals: `dependencies`, `deltas`, `cells`, `coords`
- PascalCase for classes: `SimulationEngine`, `CascadeEngine`, `WorldState`, `CircuitBreaker`
- PascalCase for enums: `ClockMode`, `ResolutionBand`
- Frozen dataclasses used for immutable value types: `@dataclass(frozen=True)`
- SCREAMING_SNAKE_CASE for module-level constants: `PRICE_ELASTICITY`, `RESOLUTION_BANDS`
## Code Style
- No explicit formatter configured (no `.prettierrc`, `.black`, `pyproject.toml [tool.black]`)
- Style is clean and consistent: 4-space indentation, PEP 8 compliant
- Line length appears to follow standard conventions (~100-120 chars)
- No explicit linter configuration detected
- Code follows Python idioms: type hints, docstrings, clean imports
- Type hints present throughout: `def schedule(self, event: SimEvent) -> int:`
- Module-level docstrings at file head: `"""Discrete Event Simulation (DES) engine."""`
- Function docstrings with Args/Returns when helpful (especially for public APIs)
- Example: `cascade.py` includes detailed docstrings explaining the cascade chain
- Concise docstrings for obvious methods; detailed for complex logic
## Import Organization
- Absolute imports from package root: `from parallax.simulation.config import...`
- No relative imports (no `from ..config import`)
- Imports are explicit, not wildcard: `from dataclasses import dataclass, field`
## Error Handling
- Defensive checks return default values rather than raising: `if cell is None: return None`
- Example: `apply_blockade()` returns `{"supply_loss": 0.0}` for nonexistent cells
- Async errors logged via logger: `logger.exception("DB write failed: %s", op.sql[:100])`
- No try-except at function boundary unless needed for recovery
- Standard `logging` module: `logger = logging.getLogger(__name__)`
- Log exceptions at ERROR level: `logger.exception()` for failures
- Partial info in logs (SQL[:100]) to avoid logging huge payloads
## Comments
- Block comments explain design decisions (e.g., "Lazy deletion: cancelled events are marked...")
- Inline comments rare; code is self-documenting via naming
- Comments appear in docstrings at module and class level, not scattered
- Python uses docstrings, not JSDoc
- Multi-line docstrings follow format: description, then blank line, then Args/Returns/Raises
- Example from `cascade.py`:
## Function Design
- Functions are focused and single-purpose
- Most functions under 30 lines; longest about 50 lines
- Complex logic broken into named steps (e.g., `compute_downstream_effects` has clear phases)
- Named parameters preferred over positional: `CascadeEngine(config=config_obj)`
- Optional parameters use defaults: `tick_duration_seconds: float = 900.0`
- Type hints on all parameters: `def __init__(self, conn: duckdb.DuckDBPyConnection)`
- Single return type (no union of different structures)
- Dicts used for structured returns with consistent keys: `{"supply_loss": 0.0}`
- Falsy returns for "not found": `None` for missing cell, `False` for queue empty
## Module Design
- All public classes/functions defined at module level
- Private utilities prefixed with `_` (Python convention)
- No `__all__` declarations; rely on naming convention
- `__init__.py` files empty or minimal
- Import from specific modules: `from parallax.simulation.engine import SimulationEngine`
## Domain-Specific Patterns
- Frozen dataclasses for immutable configs: `@dataclass(frozen=True) class ScenarioConfig`
- Mutable dataclasses for state: `@dataclass class CellState`
- Field factories for defaults: `payload: dict[str, Any] = field(default_factory=dict)`
- All DB operations and simulation engine use async/await
- Handlers are async callbacks: `async def handler(event: SimEvent): ...`
- Queue operations: `await self._queue.put()` and `await self._queue.get()`
- Union types use `|` syntax (Python 3.10+): `str | None` not `Optional[str]`
- Dict keys/values typed: `dict[str, float]`, `dict[int, CellState]`
- Full signature typing: `Callable[[SimEvent], Awaitable[None]]`
<!-- GSD:conventions-end -->

<!-- GSD:architecture-start source:ARCHITECTURE.md -->
## Architecture

## Pattern Overview
- Event-driven simulation using priority queue with wall-clock anchoring (LIVE mode) or instant playback (REPLAY mode)
- Spatial computation via H3 hexagonal grid at multiple resolutions (ocean, regional, chokepoint, infrastructure)
- Deterministic rule-based cascade propagation for economic effects (blockade → flow loss → price shock → downstream impacts)
- Single-writer queue pattern for DuckDB persistence to prevent race conditions
- Configuration-driven scenario parameters (no hard-coded simulation rules)
## Layers
- Purpose: Discrete event simulation core with priority queue, event scheduling, and async event handling
- Location: `backend/src/parallax/simulation/engine.py`
- Contains: `SimulationEngine` class, `SimEvent` dataclass, `ClockMode` enum (LIVE/REPLAY)
- Depends on: asyncio, heapq
- Used by: Cascade engine, world state manager, future agent decision points
- Purpose: Deterministic rule-based event propagation (blockade → flow → price → downstream effects)
- Location: `backend/src/parallax/simulation/cascade.py`
- Contains: `CascadeEngine` class with 6 chained rules, `ReroutePenalty` dataclass
- Depends on: `WorldState`, `ScenarioConfig`
- Used by: Event handlers in simulation loop
- Purpose: Prevents runaway escalation and enforces reality bounds
- Location: `backend/src/parallax/simulation/circuit_breaker.py`
- Contains: `CircuitBreaker` class with escalation rate limiting, cooldown tracking, reality checks
- Depends on: None (pure logic)
- Used by: Agent decision validation (Phase 2)
- Purpose: In-memory representation of geopolitical world with delta tracking for efficient persistence
- Location: `backend/src/parallax/simulation/world_state.py`
- Contains: `WorldState` class with cell-level state, `CellState` dataclass
- Depends on: None (pure datastructures)
- Used by: Cascade engine, database writer
- Purpose: Parameterize all simulation rules without code changes (shipping capacity, price bounds, agent budgets, etc.)
- Location: `backend/src/parallax/simulation/config.py`
- Contains: `ScenarioConfig` frozen dataclass, `load_scenario_config()` loader
- Depends on: YAML parser (pyyaml)
- Used by: Cascade engine, circuit breaker, initialization logic
- Purpose: H3 hexagonal grid operations and multi-resolution handling
- Location: `backend/src/parallax/spatial/h3_utils.py`
- Contains: `ResolutionBand` dataclass, functions for lat/lng→H3 conversion, route→H3 chain conversion
- Depends on: h3 library
- Used by: Ingest pipelines, world state initialization
- Purpose: Define persistent schema for world state, decisions, predictions, events
- Location: `backend/src/parallax/db/schema.py`
- Contains: `create_tables()` function that creates 10 tables (world_state_delta, world_state_snapshot, decisions, predictions, curated_events, raw_gdelt, agent_memory, agent_prompts, eval_results, simulation_state)
- Depends on: duckdb
- Used by: Initialization, queries
- Purpose: Single-writer asynchronous queue pattern for DuckDB to prevent concurrent write contention
- Location: `backend/src/parallax/db/writer.py`
- Contains: `DbWriter` class, `WriteOp` dataclass
- Depends on: asyncio, duckdb
- Used by: Event handlers, state persistence
- Purpose: Read-only query functions for simulation state reconstruction and event history
- Location: `backend/src/parallax/db/queries.py`
- Contains: Functions for current tick, latest snapshot, world state at tick, recent decisions
- Depends on: duckdb
- Used by: API endpoints, state initialization
## Data Flow
- **In-Memory:** `WorldState` tracks all H3 cells with current state (influence, threat_level, flow, status)
- **Persistence Strategy:** Delta-based approach
- **Write Pattern:** Async single-writer queue (`DbWriter`) ensures no race conditions on DuckDB
## Key Abstractions
- Purpose: Represents a single discrete event at a given tick
- Examples: `SimEvent(tick=100, event_type="blockade", payload={"cell_id": 1234, "reduction_pct": 0.95})`
- Pattern: Dataclass with tick, event_type, payload dict, source, engine reference
- Purpose: In-memory world model with change tracking
- Examples: `ws.update_cell(cell_id, flow=5000000, status="restricted")` marks cell dirty for later persistence
- Pattern: Dictionary-backed storage with dirty set for delta calculation
- Purpose: Pure, stateless rule application
- Examples: `cascade.apply_blockade(ws, cell_id, 0.9)` modifies world state and returns effects
- Pattern: Methods take world state as parameter, return effect dictionaries
- Purpose: Immutable configuration container
- Examples: `config.hormuz_daily_flow`, `config.oil_price_ceiling`, `config.max_escalation_per_tick`
- Pattern: Frozen dataclass loaded from YAML, computed properties for derived values
## Entry Points
- Location: Will be in `backend/src/parallax/main.py` (not yet created)
- Triggers: FastAPI endpoint or CLI command
- Responsibilities: Load config, create engine, schedule events, run simulation, return results
- Location: TBD in main.py
- Triggers: Engine pops each event from queue
- Responsibilities: Apply cascade rules, update world state, potentially schedule follow-up events
- Location: Runs as async task via `DbWriter.run()`
- Triggers: Async queue receives `WriteOp` items
- Responsibilities: Serialize pending writes, execute SQL, handle errors
## Error Handling
- **Cascade operations:** Methods return early with zero impact if inputs invalid (e.g., `apply_blockade()` returns `{"supply_loss": 0.0}` if cell not found)
- **Database writes:** Errors logged but don't stop engine; writes go to error log
- **Circuit breaker:** Returns `False` for disallowed escalations (does not raise)
- **Config loading:** Validation via Pydantic when `ScenarioConfig` is instantiated; invalid YAML fails at load time
## Cross-Cutting Concerns
- Config validation via Pydantic dataclass defaults and frozen constraint
- World state updates via `WorldState.update_cell()` with optional parameters (NoneType means no change)
<!-- GSD:architecture-end -->

<!-- GSD:workflow-start source:GSD defaults -->
## GSD Workflow Enforcement

Before using Edit, Write, or other file-changing tools, start work through a GSD command so planning artifacts and execution context stay in sync.

Use these entry points:
- `/gsd:quick` for small fixes, doc updates, and ad-hoc tasks
- `/gsd:debug` for investigation and bug fixing
- `/gsd:execute-phase` for planned phase work

Do not make direct repo edits outside a GSD workflow unless the user explicitly asks to bypass it.
<!-- GSD:workflow-end -->



<!-- GSD:profile-start -->
## Developer Profile

> Profile not yet configured. Run `/gsd:profile-user` to generate your developer profile.
> This section is managed by `generate-claude-profile` -- do not edit manually.
<!-- GSD:profile-end -->
