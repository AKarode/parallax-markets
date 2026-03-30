# Architecture

**Analysis Date:** 2026-03-30

## Pattern Overview

**Overall:** Layered geopolitical simulation platform with discrete event simulation (DES) engine, spatial indexing via H3, and delta-based world state management.

**Key Characteristics:**
- Event-driven simulation using priority queue with wall-clock anchoring (LIVE mode) or instant playback (REPLAY mode)
- Spatial computation via H3 hexagonal grid at multiple resolutions (ocean, regional, chokepoint, infrastructure)
- Deterministic rule-based cascade propagation for economic effects (blockade → flow loss → price shock → downstream impacts)
- Single-writer queue pattern for DuckDB persistence to prevent race conditions
- Configuration-driven scenario parameters (no hard-coded simulation rules)

## Layers

**Simulation Engine:**
- Purpose: Discrete event simulation core with priority queue, event scheduling, and async event handling
- Location: `backend/src/parallax/simulation/engine.py`
- Contains: `SimulationEngine` class, `SimEvent` dataclass, `ClockMode` enum (LIVE/REPLAY)
- Depends on: asyncio, heapq
- Used by: Cascade engine, world state manager, future agent decision points

**Cascade & Rules:**
- Purpose: Deterministic rule-based event propagation (blockade → flow → price → downstream effects)
- Location: `backend/src/parallax/simulation/cascade.py`
- Contains: `CascadeEngine` class with 6 chained rules, `ReroutePenalty` dataclass
- Depends on: `WorldState`, `ScenarioConfig`
- Used by: Event handlers in simulation loop

**Circuit Breaker:**
- Purpose: Prevents runaway escalation and enforces reality bounds
- Location: `backend/src/parallax/simulation/circuit_breaker.py`
- Contains: `CircuitBreaker` class with escalation rate limiting, cooldown tracking, reality checks
- Depends on: None (pure logic)
- Used by: Agent decision validation (Phase 2)

**World State:**
- Purpose: In-memory representation of geopolitical world with delta tracking for efficient persistence
- Location: `backend/src/parallax/simulation/world_state.py`
- Contains: `WorldState` class with cell-level state, `CellState` dataclass
- Depends on: None (pure datastructures)
- Used by: Cascade engine, database writer

**Scenario Configuration:**
- Purpose: Parameterize all simulation rules without code changes (shipping capacity, price bounds, agent budgets, etc.)
- Location: `backend/src/parallax/simulation/config.py`
- Contains: `ScenarioConfig` frozen dataclass, `load_scenario_config()` loader
- Depends on: YAML parser (pyyaml)
- Used by: Cascade engine, circuit breaker, initialization logic

**Spatial Utilities:**
- Purpose: H3 hexagonal grid operations and multi-resolution handling
- Location: `backend/src/parallax/spatial/h3_utils.py`
- Contains: `ResolutionBand` dataclass, functions for lat/lng→H3 conversion, route→H3 chain conversion
- Depends on: h3 library
- Used by: Ingest pipelines, world state initialization

**Database Schema:**
- Purpose: Define persistent schema for world state, decisions, predictions, events
- Location: `backend/src/parallax/db/schema.py`
- Contains: `create_tables()` function that creates 10 tables (world_state_delta, world_state_snapshot, decisions, predictions, curated_events, raw_gdelt, agent_memory, agent_prompts, eval_results, simulation_state)
- Depends on: duckdb
- Used by: Initialization, queries

**Database Writer:**
- Purpose: Single-writer asynchronous queue pattern for DuckDB to prevent concurrent write contention
- Location: `backend/src/parallax/db/writer.py`
- Contains: `DbWriter` class, `WriteOp` dataclass
- Depends on: asyncio, duckdb
- Used by: Event handlers, state persistence

**Database Queries:**
- Purpose: Read-only query functions for simulation state reconstruction and event history
- Location: `backend/src/parallax/db/queries.py`
- Contains: Functions for current tick, latest snapshot, world state at tick, recent decisions
- Depends on: duckdb
- Used by: API endpoints, state initialization

## Data Flow

**Simulation Loop (Current - Phase 1):**

1. Load scenario config (`load_scenario_config()` from YAML)
2. Initialize world state (`WorldState()` - empty in-memory state)
3. Create simulation engine (`SimulationEngine(handler=event_handler, clock_mode=REPLAY)`)
4. Schedule initial events (blockades, flow changes, price shocks)
5. Run simulation to target tick:
   - Engine pops events from priority queue in (tick, insertion_order) order
   - Handler applies cascade rules (`CascadeEngine.apply_blockade()`, `compute_price_shock()`, etc.)
   - World state updates cells with new values
   - Deltas tracked in `WorldState._dirty` set
6. Flush deltas to database (`world_state.flush_deltas()` → `DbWriter.enqueue()`)
7. Snapshot at intervals (every N ticks)

**State Management:**

- **In-Memory:** `WorldState` tracks all H3 cells with current state (influence, threat_level, flow, status)
- **Persistence Strategy:** Delta-based approach
  - Snapshots taken periodically (`snapshot_interval_ticks` from config)
  - Deltas between snapshots stored in `world_state_delta` table
  - State at arbitrary tick reconstructed from nearest snapshot + deltas via `get_world_state_at_tick()`
  - Reduces storage vs full snapshots while maintaining query performance
- **Write Pattern:** Async single-writer queue (`DbWriter`) ensures no race conditions on DuckDB

**Cascade Propagation (Rule Chain):**

1. **Rule 1 - Blockade:** Iran blockades cell X, reduces flow by Y% → returns `supply_loss` barrels/day
2. **Rule 2 - Bypass:** Supply loss triggers pipeline bypass activation based on loss fraction → returns `bypass_flow`
3. **Rule 3 - Price Shock:** Net loss (loss - bypass) drives oil price up using elasticity model → returns new price
4. **Rule 4 - Downstream:** Price increase distributed to countries based on Hormuz dependency ratios → returns per-country impact scores
5. **Rule 5 - Rerouting:** Computes penalty for Cape of Good Hope reroute (distance %, transit days)
6. **Rule 6 - Insurance:** Threat level raises shipping insurance costs via multiplier

All parameters from `ScenarioConfig` - no hard-coded values.

## Key Abstractions

**SimEvent:**
- Purpose: Represents a single discrete event at a given tick
- Examples: `SimEvent(tick=100, event_type="blockade", payload={"cell_id": 1234, "reduction_pct": 0.95})`
- Pattern: Dataclass with tick, event_type, payload dict, source, engine reference

**WorldState:**
- Purpose: In-memory world model with change tracking
- Examples: `ws.update_cell(cell_id, flow=5000000, status="restricted")` marks cell dirty for later persistence
- Pattern: Dictionary-backed storage with dirty set for delta calculation

**CascadeEngine:**
- Purpose: Pure, stateless rule application
- Examples: `cascade.apply_blockade(ws, cell_id, 0.9)` modifies world state and returns effects
- Pattern: Methods take world state as parameter, return effect dictionaries

**ScenarioConfig:**
- Purpose: Immutable configuration container
- Examples: `config.hormuz_daily_flow`, `config.oil_price_ceiling`, `config.max_escalation_per_tick`
- Pattern: Frozen dataclass loaded from YAML, computed properties for derived values

## Entry Points

**Simulation Initialization:**
- Location: Will be in `backend/src/parallax/main.py` (not yet created)
- Triggers: FastAPI endpoint or CLI command
- Responsibilities: Load config, create engine, schedule events, run simulation, return results

**Event Handler (Async Callback):**
- Location: TBD in main.py
- Triggers: Engine pops each event from queue
- Responsibilities: Apply cascade rules, update world state, potentially schedule follow-up events

**Database Writer Loop:**
- Location: Runs as async task via `DbWriter.run()`
- Triggers: Async queue receives `WriteOp` items
- Responsibilities: Serialize pending writes, execute SQL, handle errors

## Error Handling

**Strategy:** Defensive with logging, no exceptions cross simulation boundaries.

**Patterns:**

- **Cascade operations:** Methods return early with zero impact if inputs invalid (e.g., `apply_blockade()` returns `{"supply_loss": 0.0}` if cell not found)
- **Database writes:** Errors logged but don't stop engine; writes go to error log
- **Circuit breaker:** Returns `False` for disallowed escalations (does not raise)
- **Config loading:** Validation via Pydantic when `ScenarioConfig` is instantiated; invalid YAML fails at load time

## Cross-Cutting Concerns

**Logging:** Python standard `logging` module, module-level loggers per file (e.g., `logger = logging.getLogger(__name__)`)

**Validation:**
- Config validation via Pydantic dataclass defaults and frozen constraint
- World state updates via `WorldState.update_cell()` with optional parameters (NoneType means no change)

**Asynchrony:** AsyncIO for event loop, handler is coroutine, database writer runs as background task. REPLAY mode has no sleeps; LIVE mode uses wall-clock anchoring (not asyncio.sleep which drifts).

**Determinism:** Event queue sorted by (tick, insertion_order); same config + same events = same results every run.

---

*Architecture analysis: 2026-03-30*
