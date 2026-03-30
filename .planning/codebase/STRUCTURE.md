# Codebase Structure

**Analysis Date:** 2026-03-30

## Directory Layout

```
Parallax-Geopolitcal-Swarm/
├── backend/                    # Python FastAPI backend (simulation + API)
│   ├── src/parallax/           # Main application source code
│   │   ├── simulation/         # Discrete event simulation engine + rules
│   │   ├── db/                 # DuckDB schema, queries, single-writer queue
│   │   ├── spatial/            # H3 hexagonal grid utilities
│   │   └── __init__.py
│   ├── tests/                  # Pytest test suite
│   ├── config/                 # Scenario configuration files (YAML)
│   ├── pyproject.toml          # Python dependencies and metadata
│   ├── Dockerfile              # Backend container image
│   └── pytest.ini              # Pytest configuration
│
├── frontend/                   # React + deck.gl frontend
│   ├── node_modules/          # NPM dependencies (not in repo)
│   ├── package.json            # Frontend dependencies
│   ├── Dockerfile              # Frontend build + nginx serve
│   └── nginx.conf              # Nginx static serve config
│
├── docker-compose.yml          # Backend + frontend orchestration
├── RESEARCH.md                 # Technology research and decisions
└── .planning/codebase/         # GSD codebase analysis documents
```

## Directory Purposes

**`backend/src/parallax/`:**
- Purpose: Core simulation logic, state management, database persistence
- Contains: Simulation engine, cascade rules, world state, spatial utilities, database layer
- Key files: `engine.py`, `cascade.py`, `world_state.py`, `circuit_breaker.py`, `config.py`

**`backend/src/parallax/simulation/`:**
- Purpose: Discrete event simulation implementation
- Contains: DES engine with priority queue, cascade rule application, world state deltas, circuit breaker, config loading
- Key files:
  - `engine.py` - `SimulationEngine` class (event queue, scheduling, async handler execution)
  - `cascade.py` - `CascadeEngine` class (6 chained rules: blockade → flow → price → downstream)
  - `world_state.py` - `WorldState` class (in-memory cells with delta tracking)
  - `circuit_breaker.py` - `CircuitBreaker` class (escalation limiting, reality checks)
  - `config.py` - `ScenarioConfig` class (YAML config loading)

**`backend/src/parallax/db/`:**
- Purpose: DuckDB persistence layer
- Contains: Schema definition, single-writer queue, query functions
- Key files:
  - `schema.py` - `create_tables()` - 10 tables (world_state_delta, world_state_snapshot, decisions, predictions, curated_events, raw_gdelt, agent_memory, agent_prompts, eval_results, simulation_state)
  - `writer.py` - `DbWriter` class (async queue for writes to prevent contention)
  - `queries.py` - Read functions (current_tick, world_state_at_tick, recent_decisions)

**`backend/src/parallax/spatial/`:**
- Purpose: H3 hexagonal grid operations
- Contains: Multi-resolution band definitions, lat/lng→H3 conversion, route→H3 chain conversion
- Key files:
  - `h3_utils.py` - `ResolutionBand` definitions (ocean res 4, regional res 6, chokepoint res 7, infrastructure res 9), conversion functions

**`backend/tests/`:**
- Purpose: Pytest test suite for backend
- Contains: Tests for engine, cascade, circuit breaker, world state, config loading, H3 utilities, writer
- Key files:
  - `conftest.py` - Pytest fixtures (in-memory DuckDB with spatial/H3 extensions)
  - `test_engine.py` - 12 tests for event scheduling, priority, cancellation, LIVE/REPLAY modes
  - `test_cascade.py` - Tests for blockade→price shock→downstream propagation
  - `test_circuit_breaker.py` - Tests for escalation limiting and reality checks
  - `test_world_state.py` - Tests for cell updates, delta tracking, snapshots
  - `test_config.py` - Config loading tests
  - `test_h3_utils.py` - H3 conversion tests
  - `test_schema.py` - Schema creation tests
  - `test_writer.py` - Database writer tests

**`backend/config/`:**
- Purpose: Scenario parameter files
- Contains: YAML scenario definitions (Iran/Strait of Hormuz crisis)
- Key files:
  - `scenario_hormuz.yaml` - Hormuz blockade scenario with all rule parameters

**`frontend/`:**
- Purpose: React SPA with deck.gl visualization
- Contains: Not yet explored (no source files in repo, build artifacts only)
- Key files:
  - `package.json` - Frontend dependencies (React, deck.gl, MapLibre GL, WebSocket client)
  - `Dockerfile` - Multi-stage build: npm ci → npm run build → nginx serve
  - `nginx.conf` - Static asset serving config

## Key File Locations

**Entry Points:**
- `backend/src/parallax/main.py` (NOT YET CREATED) - Will be FastAPI app entry point, runs `uvicorn parallax.main:app`
- `frontend/` - Build process via `npm run build` produces `dist/` for nginx

**Configuration:**
- `backend/config/scenario_hormuz.yaml` - Scenario parameters (all simulation rules are parameterized here, no hard-coded values)
- `docker-compose.yml` - Service orchestration, environment variables, volume mounting

**Core Logic:**
- `backend/src/parallax/simulation/engine.py` - Event-driven DES with async handler pattern
- `backend/src/parallax/simulation/cascade.py` - Rule-based cascade propagation (6 rules chained)
- `backend/src/parallax/simulation/world_state.py` - In-memory cell state with delta tracking
- `backend/src/parallax/db/writer.py` - Single-writer async queue for DuckDB persistence

**Testing:**
- `backend/tests/conftest.py` - DuckDB test fixture
- `backend/tests/test_engine.py` - Comprehensive engine behavior tests
- `backend/tests/test_cascade.py` - Cascade rule tests
- `backend/pytest.ini` - Pytest asyncio configuration

## Naming Conventions

**Files:**
- Python modules: `snake_case.py` (e.g., `world_state.py`, `circuit_breaker.py`)
- Configuration files: `scenario_<name>.yaml` (e.g., `scenario_hormuz.yaml`)
- Test files: `test_<module>.py` (e.g., `test_engine.py`)
- Dockerfile: `Dockerfile` (no extension, no version suffix)

**Directories:**
- Package directories: `snake_case` (e.g., `parallax`, `simulation`, `spatial`)
- Logical groupings: functional domains (e.g., `simulation`, `db`, `spatial`)

**Python Classes:**
- Engine classes: `PascalCase` suffix with "Engine" (e.g., `SimulationEngine`, `CascadeEngine`)
- Data classes: `PascalCase` (e.g., `SimEvent`, `WorldState`, `CellState`, `ScenarioConfig`)
- Context managers: `PascalCase` (e.g., `DbWriter`)

**Constants/Types:**
- Enums: `PascalCase` (e.g., `ClockMode` with LIVE, REPLAY values)
- Dataclass-frozen config: `ScenarioConfig` (immutable)

## Where to Add New Code

**New Feature (e.g., new cascade rule):**
- Primary code: `backend/src/parallax/simulation/cascade.py` - Add method to `CascadeEngine` class following pattern of existing rules (takes WorldState, params; returns dict of effects)
- Config parameters: `backend/config/scenario_hormuz.yaml` - Add scenario config fields as frozen dataclass properties in `backend/src/parallax/simulation/config.py`
- Tests: `backend/tests/test_cascade.py` - Add pytest test for new rule

**New Module (e.g., agent system):**
- Implementation: `backend/src/parallax/agents/` (new directory)
- Structure: Follow domain split (agents/runners.py, agents/schemas.py, agents/router.py)
- Tests: `backend/tests/test_agent_*.py`

**New Database Table:**
- Schema: Add to `backend/src/parallax/db/schema.py` in `create_tables()` function
- Queries: Add read functions to `backend/src/parallax/db/queries.py`
- Writes: Use `backend/src/parallax/db/writer.py` for persistence (enqueue SQL)

**Utilities:**
- Shared spatial helpers: `backend/src/parallax/spatial/h3_utils.py` - Add functions for H3 operations (follows pattern: `lat_lng_to_cell_for_zone()`, `route_to_h3_chain()`)
- Custom async patterns: `backend/src/parallax/` root level if crosses modules, otherwise in feature domain

**Frontend Components:**
- TBD - Frontend structure not yet established. Convention will follow React patterns (components/, hooks/, utils/) once source code exists.

## Special Directories

**`backend/.pytest_cache/`:**
- Purpose: Pytest internal cache
- Generated: Yes (by pytest)
- Committed: No (in .gitignore)

**`backend/src/parallax/__pycache__/`:**
- Purpose: Python bytecode cache
- Generated: Yes (by Python runtime)
- Committed: No (in .gitignore)

**`frontend/node_modules/`:**
- Purpose: NPM dependencies
- Generated: Yes (by npm ci/install)
- Committed: No (in .gitignore, lockfile is committed)

**`duckdb-data/` (created at runtime):**
- Purpose: Persistent database file
- Generated: Yes (by DuckDB)
- Committed: No (Docker volume, not in repo)

## Module Import Pattern

Python imports follow domain isolation:

```python
# Simulation domain imports
from parallax.simulation.engine import SimulationEngine, SimEvent
from parallax.simulation.cascade import CascadeEngine
from parallax.simulation.world_state import WorldState
from parallax.simulation.circuit_breaker import CircuitBreaker
from parallax.simulation.config import ScenarioConfig, load_scenario_config

# Database imports
from parallax.db.schema import create_tables
from parallax.db.writer import DbWriter
from parallax.db.queries import get_world_state_at_tick

# Spatial imports
from parallax.spatial.h3_utils import lat_lng_to_cell_for_zone, route_to_h3_chain
```

No circular imports. Clean separation: simulation logic → DB persistence, spatial utilities are shared.

---

*Structure analysis: 2026-03-30*
