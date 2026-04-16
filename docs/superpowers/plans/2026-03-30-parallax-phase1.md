# Parallax Phase 1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a live geopolitical cascade simulator for the Iran/Hormuz scenario with an LLM agent swarm, H3 spatial visualization, and continuous evaluation framework.

**Architecture:** Single Python process (FastAPI + asyncio) serving a React/deck.gl frontend via WebSocket. DuckDB with single-writer topology for all state. ~50 LLM agents structured as country→sub-actor hierarchy. Eval framework tracks predictions against ground truth over 30+ days.

**Tech Stack:** Python 3.12, FastAPI, asyncio, DuckDB (spatial + H3 community extensions), Anthropic Claude API, React 18, TypeScript, deck.gl, MapLibre GL, sentence-transformers, searoute, Vite

---

## File Structure

### Backend (`backend/`)

```
backend/
├── pyproject.toml
├── pytest.ini
├── config/
│   └── scenario_hormuz.yaml          # Cascade parameters (bypass capacity, reroute penalties, etc.)
├── src/
│   └── parallax/
│       ├── __init__.py
│       ├── main.py                    # FastAPI app, lifespan, background tasks
│       ├── db/
│       │   ├── __init__.py
│       │   ├── schema.py             # DuckDB table creation DDL
│       │   ├── writer.py             # Single-writer asyncio.Queue → DuckDB
│       │   └── queries.py            # Read-only query helpers
│       ├── spatial/
│       │   ├── __init__.py
│       │   ├── loader.py             # Overture Maps + Searoute → H3 cells
│       │   └── h3_utils.py           # H3 resolution bands, cell chain generation
│       ├── ingestion/
│       │   ├── __init__.py
│       │   ├── gdelt.py              # BigQuery fetch + 4-stage filter
│       │   ├── dedup.py              # Semantic dedup with sentence-transformers
│       │   ├── oil_prices.py         # EIA + FRED daily spot fetcher
│       │   └── entities.py           # Named-entity override list for GDELT filter
│       ├── simulation/
│       │   ├── __init__.py
│       │   ├── engine.py             # DES core: event queue, tick loop, clock modes
│       │   ├── cascade.py            # Rule-based cascade (blockade → flow → price → downstream)
│       │   ├── circuit_breaker.py    # Escalation limits, cooldowns, exogenous override
│       │   ├── world_state.py        # In-memory world state cache + delta tracking
│       │   └── config.py             # Scenario config loader (YAML → dataclass)
│       ├── agents/
│       │   ├── __init__.py
│       │   ├── registry.py           # Agent roster, country→sub-actor hierarchy
│       │   ├── runner.py             # Parallel LLM calls, cooldown enforcement, token ceilings
│       │   ├── router.py             # Event→agent relevance matching
│       │   ├── prompts/              # One YAML per agent with system prompt + historical baseline
│       │   │   ├── iran_irgc_navy.yaml
│       │   │   ├── iran_supreme_leader.yaml
│       │   │   ├── usa_trump.yaml
│       │   │   ├── usa_centcom.yaml
│       │   │   ├── saudi_mbs.yaml
│       │   │   ├── saudi_aramco.yaml
│       │   │   └── ... (one per sub-actor)
│       │   ├── schemas.py            # Pydantic models for agent input/output
│       │   └── country_agent.py      # Country-level synthesis + conflict resolution
│       ├── eval/
│       │   ├── __init__.py
│       │   ├── predictions.py        # Prediction creation, structured format
│       │   ├── scoring.py            # Direction, magnitude, sequence, calibration scoring
│       │   ├── ground_truth.py       # Fetch EIA/FRED/GDELT actuals
│       │   ├── prompt_versioning.py  # Semver tracking, A/B comparison
│       │   └── improvement.py        # Prompt improvement pipeline (meta-agent)
│       ├── api/
│       │   ├── __init__.py
│       │   ├── routes.py             # REST endpoints (state, predictions, admin)
│       │   ├── websocket.py          # WebSocket handler with message batching
│       │   └── auth.py               # Invite code + admin password middleware
│       └── budget/
│           ├── __init__.py
│           └── tracker.py            # Daily token/cost tracking, budget cap enforcement
└── tests/
    ├── conftest.py                   # DuckDB in-memory fixtures
    ├── test_schema.py
    ├── test_writer.py
    ├── test_h3_utils.py
    ├── test_gdelt_filter.py
    ├── test_dedup.py
    ├── test_cascade.py
    ├── test_circuit_breaker.py
    ├── test_world_state.py
    ├── test_config.py
    ├── test_agent_schemas.py
    ├── test_agent_router.py
    ├── test_agent_runner.py
    ├── test_scoring.py
    ├── test_predictions.py
    ├── test_prompt_versioning.py
    ├── test_auth.py
    ├── test_budget_tracker.py
    └── test_integration.py
```

### Frontend (`frontend/`)

```
frontend/
├── package.json
├── tsconfig.json
├── vite.config.ts
├── index.html
├── src/
│   ├── main.tsx
│   ├── App.tsx                        # Layout shell: 3-column + bottom bar
│   ├── hooks/
│   │   ├── useWebSocket.ts           # WS connection, message batching, reconnect
│   │   └── useHexData.ts             # Mutable ref for H3 data, deck.gl integration
│   ├── components/
│   │   ├── HexMap.tsx                # deck.gl + MapLibre, 4 H3HexagonLayers
│   │   ├── AgentFeed.tsx             # Left panel: scrolling agent decisions
│   │   ├── LiveIndicators.tsx        # Right panel: oil price, traffic, escalation
│   │   ├── Timeline.tsx              # Bottom bar: simulation timeline + scrubber
│   │   ├── PredictionCards.tsx       # Bottom bar: active predictions
│   │   └── HexPopover.tsx           # Click-on-hex detail view
│   ├── types/
│   │   └── index.ts                  # Shared TypeScript types for WS messages, hex data
│   └── lib/
│       └── colors.ts                 # Influence/threat → color mapping
```

---

## Task 1: Project Scaffold + DuckDB Schema

**Files:**
- Create: `backend/pyproject.toml`
- Create: `backend/pytest.ini`
- Create: `backend/src/parallax/__init__.py`
- Create: `backend/src/parallax/db/__init__.py`
- Create: `backend/src/parallax/db/schema.py`
- Create: `backend/tests/conftest.py`
- Create: `backend/tests/test_schema.py`

- [ ] **Step 1: Create `backend/pyproject.toml`**

```toml
[project]
name = "parallax"
version = "0.1.0"
requires-python = ">=3.12"
dependencies = [
    "fastapi>=0.115",
    "uvicorn[standard]>=0.34",
    "duckdb>=1.2",
    "h3>=4.1",
    "anthropic>=0.52",
    "pydantic>=2.10",
    "pyyaml>=6.0",
    "httpx>=0.28",
    "websockets>=14.0",
    "sentence-transformers>=3.4",
    "searoute>=1.3",
    "shapely>=2.0",
    "google-cloud-bigquery>=3.27",
]

[project.optional-dependencies]
dev = [
    "pytest>=8.3",
    "pytest-asyncio>=0.25",
    "pytest-httpx>=0.35",
]

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.pytest.ini_options]
asyncio_mode = "auto"
testpaths = ["tests"]
```

- [ ] **Step 2: Create `backend/pytest.ini`**

```ini
[pytest]
asyncio_mode = auto
testpaths = tests
```

- [ ] **Step 3: Create `backend/src/parallax/__init__.py` and `backend/src/parallax/db/__init__.py`**

Both empty files.

- [ ] **Step 4: Write the failing test for DuckDB schema**

```python
# backend/tests/conftest.py
import duckdb
import pytest


@pytest.fixture
def db():
    """In-memory DuckDB with extensions for testing."""
    conn = duckdb.connect(":memory:")
    conn.execute("INSTALL spatial; LOAD spatial;")
    conn.execute("INSTALL h3 FROM community; LOAD h3;")
    yield conn
    conn.close()
```

```python
# backend/tests/test_schema.py
from parallax.db.schema import create_tables


def test_create_tables_creates_all_expected_tables(db):
    create_tables(db)
    tables = db.execute("SHOW TABLES").fetchall()
    table_names = {t[0] for t in tables}
    expected = {
        "world_state_delta",
        "world_state_snapshot",
        "agent_memory",
        "agent_prompts",
        "decisions",
        "predictions",
        "curated_events",
        "raw_gdelt",
        "eval_results",
        "simulation_state",
    }
    assert expected == table_names


def test_world_state_delta_columns(db):
    create_tables(db)
    cols = db.execute(
        "SELECT column_name FROM information_schema.columns "
        "WHERE table_name = 'world_state_delta' ORDER BY ordinal_position"
    ).fetchall()
    col_names = [c[0] for c in cols]
    assert col_names == ["cell_id", "tick", "influence", "threat_level", "flow", "status", "changed_at"]


def test_simulation_state_starts_empty(db):
    create_tables(db)
    rows = db.execute("SELECT * FROM simulation_state").fetchall()
    assert rows == []
```

- [ ] **Step 5: Run tests to verify they fail**

Run: `cd backend && pip install -e ".[dev]" && pytest tests/test_schema.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'parallax.db.schema'`

- [ ] **Step 6: Implement schema**

```python
# backend/src/parallax/db/schema.py
import duckdb


def create_tables(conn: duckdb.DuckDBPyConnection) -> None:
    conn.execute("""
        CREATE TABLE IF NOT EXISTS world_state_delta (
            cell_id BIGINT NOT NULL,
            tick INTEGER NOT NULL,
            influence VARCHAR,
            threat_level DOUBLE,
            flow DOUBLE,
            status VARCHAR,
            changed_at TIMESTAMP DEFAULT current_timestamp
        )
    """)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS world_state_snapshot (
            cell_id BIGINT NOT NULL,
            tick INTEGER NOT NULL,
            influence VARCHAR,
            threat_level DOUBLE,
            flow DOUBLE,
            status VARCHAR,
            snapshot_at TIMESTAMP DEFAULT current_timestamp
        )
    """)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS agent_memory (
            agent_id VARCHAR NOT NULL,
            prompt_version VARCHAR NOT NULL,
            rolling_context JSON,
            weight DOUBLE DEFAULT 1.0,
            last_activated TIMESTAMP,
            PRIMARY KEY (agent_id)
        )
    """)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS agent_prompts (
            agent_id VARCHAR NOT NULL,
            version VARCHAR NOT NULL,
            system_prompt TEXT NOT NULL,
            historical_baseline TEXT,
            created_at TIMESTAMP DEFAULT current_timestamp,
            PRIMARY KEY (agent_id, version)
        )
    """)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS decisions (
            decision_id VARCHAR NOT NULL PRIMARY KEY,
            agent_id VARCHAR NOT NULL,
            tick INTEGER NOT NULL,
            action_type VARCHAR NOT NULL,
            target_h3_cells JSON,
            intensity DOUBLE,
            description TEXT,
            reasoning TEXT,
            confidence DOUBLE,
            prompt_version VARCHAR,
            created_at TIMESTAMP DEFAULT current_timestamp
        )
    """)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS predictions (
            prediction_id VARCHAR NOT NULL PRIMARY KEY,
            agent_id VARCHAR NOT NULL,
            prediction_type VARCHAR NOT NULL,
            direction VARCHAR NOT NULL,
            magnitude_range JSON,
            unit VARCHAR,
            timeframe VARCHAR NOT NULL,
            confidence DOUBLE NOT NULL,
            reasoning TEXT,
            prompt_version VARCHAR NOT NULL,
            created_at TIMESTAMP DEFAULT current_timestamp,
            resolve_by TIMESTAMP NOT NULL,
            ground_truth JSON,
            score_direction BOOLEAN,
            score_magnitude BOOLEAN,
            miss_tag VARCHAR,
            scored_at TIMESTAMP
        )
    """)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS curated_events (
            event_id VARCHAR NOT NULL PRIMARY KEY,
            source VARCHAR NOT NULL,
            actor1 VARCHAR,
            actor2 VARCHAR,
            action VARCHAR,
            goldstein_scale DOUBLE,
            num_mentions INTEGER,
            num_sources INTEGER,
            lat DOUBLE,
            lng DOUBLE,
            h3_cell BIGINT,
            relevance_score DOUBLE,
            summary TEXT,
            raw_event JSON,
            ingested_at TIMESTAMP DEFAULT current_timestamp
        )
    """)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS raw_gdelt (
            global_event_id VARCHAR NOT NULL PRIMARY KEY,
            raw_data JSON NOT NULL,
            fetched_at TIMESTAMP DEFAULT current_timestamp
        )
    """)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS eval_results (
            eval_id VARCHAR NOT NULL PRIMARY KEY,
            agent_id VARCHAR NOT NULL,
            prompt_version VARCHAR NOT NULL,
            eval_date DATE NOT NULL,
            direction_accuracy DOUBLE,
            magnitude_accuracy DOUBLE,
            calibration_score DOUBLE,
            num_predictions INTEGER,
            num_correct INTEGER,
            details JSON
        )
    """)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS simulation_state (
            key VARCHAR NOT NULL PRIMARY KEY,
            value JSON NOT NULL,
            updated_at TIMESTAMP DEFAULT current_timestamp
        )
    """)
```

- [ ] **Step 7: Run tests to verify they pass**

Run: `cd backend && pytest tests/test_schema.py -v`
Expected: All 3 tests PASS

- [ ] **Step 8: Commit**

```bash
git add backend/
git commit -m "feat: project scaffold with DuckDB schema and test fixtures"
```

---

## Task 2: Single-Writer DB Layer

**Files:**
- Create: `backend/src/parallax/db/writer.py`
- Create: `backend/src/parallax/db/queries.py`
- Create: `backend/tests/test_writer.py`

- [ ] **Step 1: Write the failing test for the write queue**

```python
# backend/tests/test_writer.py
import asyncio
import duckdb
import pytest
from parallax.db.schema import create_tables
from parallax.db.writer import DbWriter


@pytest.fixture
def db():
    conn = duckdb.connect(":memory:")
    conn.execute("INSTALL spatial; LOAD spatial;")
    conn.execute("INSTALL h3 FROM community; LOAD h3;")
    create_tables(conn)
    yield conn
    conn.close()


@pytest.mark.asyncio
async def test_writer_processes_single_write(db):
    writer = DbWriter(db)
    task = asyncio.create_task(writer.run())

    await writer.enqueue(
        "INSERT INTO simulation_state (key, value) VALUES (?, ?)",
        ["current_tick", '"0"'],
    )
    # Give writer time to process
    await asyncio.sleep(0.05)
    writer.stop()
    await task

    rows = db.execute("SELECT key, value FROM simulation_state").fetchall()
    assert len(rows) == 1
    assert rows[0][0] == "current_tick"


@pytest.mark.asyncio
async def test_writer_processes_batch_of_writes(db):
    writer = DbWriter(db)
    task = asyncio.create_task(writer.run())

    for i in range(10):
        await writer.enqueue(
            "INSERT INTO world_state_delta (cell_id, tick, status) VALUES (?, ?, ?)",
            [i, 1, "open"],
        )
    await asyncio.sleep(0.1)
    writer.stop()
    await task

    count = db.execute("SELECT count(*) FROM world_state_delta").fetchone()[0]
    assert count == 10


@pytest.mark.asyncio
async def test_writer_queue_depth_reported(db):
    writer = DbWriter(db)
    # Don't start the runner — just enqueue
    await writer.enqueue("INSERT INTO simulation_state (key, value) VALUES (?, ?)", ["a", '"1"'])
    assert writer.queue_depth() == 1
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && pytest tests/test_writer.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'parallax.db.writer'`

- [ ] **Step 3: Implement the single-writer**

```python
# backend/src/parallax/db/writer.py
import asyncio
import logging
from dataclasses import dataclass

import duckdb

logger = logging.getLogger(__name__)


@dataclass
class WriteOp:
    sql: str
    params: list | None = None


class DbWriter:
    """Single-writer queue for DuckDB. All writes go through this."""

    def __init__(self, conn: duckdb.DuckDBPyConnection) -> None:
        self._conn = conn
        self._queue: asyncio.Queue[WriteOp | None] = asyncio.Queue()
        self._running = False

    async def enqueue(self, sql: str, params: list | None = None) -> None:
        await self._queue.put(WriteOp(sql=sql, params=params))

    def queue_depth(self) -> int:
        return self._queue.qsize()

    def stop(self) -> None:
        self._running = False
        self._queue.put_nowait(None)  # Sentinel to unblock

    async def run(self) -> None:
        self._running = True
        while self._running:
            op = await self._queue.get()
            if op is None:
                break
            try:
                if op.params:
                    self._conn.execute(op.sql, op.params)
                else:
                    self._conn.execute(op.sql)
            except Exception:
                logger.exception("DB write failed: %s", op.sql[:100])
            self._queue.task_done()
```

- [ ] **Step 4: Implement read-only query helpers**

```python
# backend/src/parallax/db/queries.py
import duckdb


def get_current_tick(conn: duckdb.DuckDBPyConnection) -> int:
    row = conn.execute(
        "SELECT value FROM simulation_state WHERE key = 'current_tick'"
    ).fetchone()
    if row is None:
        return 0
    return int(row[0].strip('"'))


def get_latest_snapshot_tick(conn: duckdb.DuckDBPyConnection) -> int | None:
    row = conn.execute(
        "SELECT MAX(tick) FROM world_state_snapshot"
    ).fetchone()
    return row[0] if row and row[0] is not None else None


def get_world_state_at_tick(
    conn: duckdb.DuckDBPyConnection, target_tick: int
) -> list[dict]:
    """Reconstruct world state at a given tick from nearest snapshot + deltas."""
    snapshot_tick = conn.execute(
        "SELECT MAX(tick) FROM world_state_snapshot WHERE tick <= ?",
        [target_tick],
    ).fetchone()[0]

    if snapshot_tick is None:
        return []

    # Start from snapshot
    cells = {}
    rows = conn.execute(
        "SELECT cell_id, influence, threat_level, flow, status "
        "FROM world_state_snapshot WHERE tick = ?",
        [snapshot_tick],
    ).fetchall()
    for r in rows:
        cells[r[0]] = {
            "cell_id": r[0],
            "influence": r[1],
            "threat_level": r[2],
            "flow": r[3],
            "status": r[4],
        }

    # Apply deltas forward
    deltas = conn.execute(
        "SELECT cell_id, influence, threat_level, flow, status "
        "FROM world_state_delta "
        "WHERE tick > ? AND tick <= ? ORDER BY tick",
        [snapshot_tick, target_tick],
    ).fetchall()
    for d in deltas:
        cell_id = d[0]
        if cell_id not in cells:
            cells[cell_id] = {"cell_id": cell_id}
        if d[1] is not None:
            cells[cell_id]["influence"] = d[1]
        if d[2] is not None:
            cells[cell_id]["threat_level"] = d[2]
        if d[3] is not None:
            cells[cell_id]["flow"] = d[3]
        if d[4] is not None:
            cells[cell_id]["status"] = d[4]

    return list(cells.values())


def get_recent_decisions(
    conn: duckdb.DuckDBPyConnection, limit: int = 50
) -> list[dict]:
    rows = conn.execute(
        "SELECT decision_id, agent_id, tick, action_type, description, "
        "confidence, created_at "
        "FROM decisions ORDER BY created_at DESC LIMIT ?",
        [limit],
    ).fetchall()
    return [
        {
            "decision_id": r[0],
            "agent_id": r[1],
            "tick": r[2],
            "action_type": r[3],
            "description": r[4],
            "confidence": r[5],
            "created_at": str(r[6]),
        }
        for r in rows
    ]
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd backend && pytest tests/test_writer.py -v`
Expected: All 3 tests PASS

- [ ] **Step 6: Commit**

```bash
git add backend/src/parallax/db/ backend/tests/test_writer.py
git commit -m "feat: single-writer DB layer with asyncio queue and query helpers"
```

---

## Task 3: Scenario Config Loader

**Files:**
- Create: `backend/src/parallax/simulation/__init__.py`
- Create: `backend/src/parallax/simulation/config.py`
- Create: `backend/config/scenario_hormuz.yaml`
- Create: `backend/tests/test_config.py`

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/test_config.py
from pathlib import Path
from parallax.simulation.config import ScenarioConfig, load_scenario_config


def test_load_hormuz_config():
    config = load_scenario_config(Path(__file__).parent.parent / "config" / "scenario_hormuz.yaml")
    assert config.name == "iran_hormuz"
    assert config.hormuz_daily_flow == 20_000_000
    assert config.total_bypass_capacity_min == 3_500_000
    assert config.total_bypass_capacity_max == 6_500_000
    assert config.cape_reroute_nm == 11600
    assert config.tick_duration_minutes == 15


def test_config_derived_reroute_penalty():
    config = load_scenario_config(Path(__file__).parent.parent / "config" / "scenario_hormuz.yaml")
    expected_pct = (config.cape_reroute_nm - config.hormuz_to_europe_via_suez_nm) / config.hormuz_to_europe_via_suez_nm
    assert abs(config.reroute_distance_penalty_pct - expected_pct) < 0.01


def test_config_circuit_breaker_defaults():
    config = load_scenario_config(Path(__file__).parent.parent / "config" / "scenario_hormuz.yaml")
    assert config.max_escalation_per_tick == 1
    assert config.escalation_cooldown_ticks == 3
    assert config.exogenous_shock_goldstein_threshold == 8.0
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && pytest tests/test_config.py -v`
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Create the scenario YAML**

```yaml
# backend/config/scenario_hormuz.yaml
name: iran_hormuz
description: "Iran/Strait of Hormuz crisis scenario"

tick_duration_minutes: 15

# --- Shipping & Oil Flow ---
hormuz_daily_flow: 20000000  # bbl/day (IEA estimate)
saudi_eastwest_pipeline_capacity: 5000000  # bbl/day to Yanbu
uae_habshan_fujairah_capacity: 1500000  # bbl/day to Gulf of Oman
total_bypass_capacity_min: 3500000  # bbl/day (IEA low estimate)
total_bypass_capacity_max: 6500000  # bbl/day (surge capacity)

# --- Rerouting ---
hormuz_to_europe_via_suez_nm: 6300
cape_reroute_nm: 11600
reroute_transit_days_min: 10
reroute_transit_days_max: 14

# --- Circuit Breaker ---
max_escalation_per_tick: 1
escalation_cooldown_ticks: 3
exogenous_shock_goldstein_threshold: 8.0

# --- Oil Price ---
oil_price_floor: 30.0
oil_price_ceiling: 200.0

# --- Budget ---
daily_budget_cap_usd: 20.0
sub_actor_max_input_tokens: 4000
sub_actor_max_output_tokens: 500
country_agent_max_input_tokens: 8000
country_agent_max_output_tokens: 1000

# --- Agent Timing ---
sub_actor_cooldown_minutes: 30
country_agent_cooldown_minutes: 60

# --- State Management ---
snapshot_interval_ticks: 100
delta_retention_days: 30
```

- [ ] **Step 4: Implement the config loader**

```python
# backend/src/parallax/simulation/__init__.py
```

```python
# backend/src/parallax/simulation/config.py
from dataclasses import dataclass
from pathlib import Path

import yaml


@dataclass(frozen=True)
class ScenarioConfig:
    name: str
    description: str
    tick_duration_minutes: int

    # Shipping & Oil Flow
    hormuz_daily_flow: int
    saudi_eastwest_pipeline_capacity: int
    uae_habshan_fujairah_capacity: int
    total_bypass_capacity_min: int
    total_bypass_capacity_max: int

    # Rerouting
    hormuz_to_europe_via_suez_nm: int
    cape_reroute_nm: int
    reroute_transit_days_min: int
    reroute_transit_days_max: int

    # Circuit Breaker
    max_escalation_per_tick: int
    escalation_cooldown_ticks: int
    exogenous_shock_goldstein_threshold: float

    # Oil Price
    oil_price_floor: float
    oil_price_ceiling: float

    # Budget
    daily_budget_cap_usd: float
    sub_actor_max_input_tokens: int
    sub_actor_max_output_tokens: int
    country_agent_max_input_tokens: int
    country_agent_max_output_tokens: int

    # Agent Timing
    sub_actor_cooldown_minutes: int
    country_agent_cooldown_minutes: int

    # State Management
    snapshot_interval_ticks: int
    delta_retention_days: int

    @property
    def reroute_distance_penalty_pct(self) -> float:
        return (self.cape_reroute_nm - self.hormuz_to_europe_via_suez_nm) / self.hormuz_to_europe_via_suez_nm


def load_scenario_config(path: Path) -> ScenarioConfig:
    with open(path) as f:
        data = yaml.safe_load(f)
    return ScenarioConfig(**data)
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd backend && pytest tests/test_config.py -v`
Expected: All 3 tests PASS

- [ ] **Step 6: Commit**

```bash
git add backend/config/ backend/src/parallax/simulation/ backend/tests/test_config.py
git commit -m "feat: scenario config loader with Hormuz defaults"
```

---

## Task 4: H3 Spatial Utilities

**Files:**
- Create: `backend/src/parallax/spatial/__init__.py`
- Create: `backend/src/parallax/spatial/h3_utils.py`
- Create: `backend/tests/test_h3_utils.py`

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/test_h3_utils.py
import h3
from parallax.spatial.h3_utils import (
    ResolutionBand,
    RESOLUTION_BANDS,
    lat_lng_to_cell_for_zone,
    route_to_h3_chain,
)


def test_resolution_bands_defined():
    assert len(RESOLUTION_BANDS) == 4
    assert RESOLUTION_BANDS[0].name == "ocean"
    assert RESOLUTION_BANDS[0].resolution in (3, 4)
    assert RESOLUTION_BANDS[3].name == "infrastructure"
    assert RESOLUTION_BANDS[3].resolution == 9


def test_lat_lng_to_cell_hormuz():
    """Hormuz strait center should map to the chokepoint band (res 7-8)."""
    cell = lat_lng_to_cell_for_zone(26.5, 56.25, "chokepoint")
    assert h3.get_resolution(cell) in (7, 8)


def test_route_to_h3_chain():
    """A simple 2-point line should produce a list of H3 cells."""
    coords = [(56.0, 26.0), (56.5, 26.5)]  # (lng, lat) pairs
    chain = route_to_h3_chain(coords, resolution=7)
    assert len(chain) > 0
    assert all(h3.is_valid_cell(c) for c in chain)


def test_route_to_h3_chain_deduplicates():
    """Two very close points should not produce duplicate cells."""
    coords = [(56.0, 26.0), (56.0001, 26.0001)]
    chain = route_to_h3_chain(coords, resolution=4)
    assert len(chain) == len(set(chain))
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && pytest tests/test_h3_utils.py -v`
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Implement H3 utilities**

```python
# backend/src/parallax/spatial/__init__.py
```

```python
# backend/src/parallax/spatial/h3_utils.py
from dataclasses import dataclass

import h3


@dataclass(frozen=True)
class ResolutionBand:
    name: str
    resolution: int
    description: str


RESOLUTION_BANDS = [
    ResolutionBand("ocean", 4, "Open ocean / distant routes"),
    ResolutionBand("regional", 6, "Persian Gulf, Gulf of Oman"),
    ResolutionBand("chokepoint", 7, "Hormuz strait + chokepoints"),
    ResolutionBand("infrastructure", 9, "Ports and terminals"),
]

_BAND_MAP = {b.name: b for b in RESOLUTION_BANDS}


def lat_lng_to_cell_for_zone(lat: float, lng: float, zone: str) -> int:
    band = _BAND_MAP[zone]
    return h3.latlng_to_cell(lat, lng, band.resolution)


def route_to_h3_chain(
    coords: list[tuple[float, float]], resolution: int
) -> list[int]:
    """Convert a list of (lng, lat) coordinate pairs to an ordered, deduplicated H3 cell chain."""
    cells: list[int] = []
    seen: set[int] = set()
    for lng, lat in coords:
        cell = h3.latlng_to_cell(lat, lng, resolution)
        if cell not in seen:
            cells.append(cell)
            seen.add(cell)
    return cells
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd backend && pytest tests/test_h3_utils.py -v`
Expected: All 4 tests PASS

- [ ] **Step 5: Commit**

```bash
git add backend/src/parallax/spatial/ backend/tests/test_h3_utils.py
git commit -m "feat: H3 spatial utilities with resolution bands and route-to-cell conversion"
```

---

## Task 5: World State + Delta Tracking

**Files:**
- Create: `backend/src/parallax/simulation/world_state.py`
- Create: `backend/tests/test_world_state.py`

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/test_world_state.py
from parallax.simulation.world_state import WorldState


def test_initial_state_empty():
    ws = WorldState()
    assert ws.get_cell(123456) is None
    assert ws.tick == 0


def test_update_cell_tracks_delta():
    ws = WorldState()
    ws.update_cell(123456, influence="iran", threat_level=0.5, status="patrolled")
    ws.advance_tick()

    cell = ws.get_cell(123456)
    assert cell["influence"] == "iran"
    assert cell["threat_level"] == 0.5
    assert cell["status"] == "patrolled"

    deltas = ws.flush_deltas()
    assert len(deltas) == 1
    assert deltas[0]["cell_id"] == 123456
    assert deltas[0]["tick"] == 1


def test_unchanged_cells_not_in_delta():
    ws = WorldState()
    ws.update_cell(100, influence="iran", status="open")
    ws.update_cell(200, influence="usa", status="open")
    ws.advance_tick()
    ws.flush_deltas()  # Clear first tick deltas

    # Only update cell 100 on tick 2
    ws.update_cell(100, threat_level=0.8)
    ws.advance_tick()
    deltas = ws.flush_deltas()

    assert len(deltas) == 1
    assert deltas[0]["cell_id"] == 100
    assert deltas[0]["threat_level"] == 0.8


def test_snapshot_returns_all_cells():
    ws = WorldState()
    ws.update_cell(100, influence="iran", status="open")
    ws.update_cell(200, influence="usa", status="open")
    ws.advance_tick()

    snapshot = ws.snapshot()
    assert len(snapshot) == 2
    cell_ids = {s["cell_id"] for s in snapshot}
    assert cell_ids == {100, 200}


def test_load_from_snapshot():
    ws = WorldState()
    snapshot_data = [
        {"cell_id": 100, "influence": "iran", "threat_level": 0.5, "flow": 1000.0, "status": "open"},
        {"cell_id": 200, "influence": "usa", "threat_level": 0.1, "flow": 2000.0, "status": "open"},
    ]
    ws.load_snapshot(snapshot_data, tick=50)
    assert ws.tick == 50
    assert ws.get_cell(100)["influence"] == "iran"
    assert ws.get_cell(200)["flow"] == 2000.0
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && pytest tests/test_world_state.py -v`
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Implement WorldState**

```python
# backend/src/parallax/simulation/world_state.py
from copy import deepcopy
from dataclasses import dataclass, field


@dataclass
class CellState:
    cell_id: int
    influence: str | None = None
    threat_level: float = 0.0
    flow: float = 0.0
    status: str = "open"


class WorldState:
    """In-memory world state with delta tracking for efficient persistence."""

    def __init__(self) -> None:
        self._cells: dict[int, CellState] = {}
        self._dirty: set[int] = set()
        self._tick: int = 0

    @property
    def tick(self) -> int:
        return self._tick

    def get_cell(self, cell_id: int) -> dict | None:
        cell = self._cells.get(cell_id)
        if cell is None:
            return None
        return {
            "cell_id": cell.cell_id,
            "influence": cell.influence,
            "threat_level": cell.threat_level,
            "flow": cell.flow,
            "status": cell.status,
        }

    def update_cell(
        self,
        cell_id: int,
        influence: str | None = None,
        threat_level: float | None = None,
        flow: float | None = None,
        status: str | None = None,
    ) -> None:
        if cell_id not in self._cells:
            self._cells[cell_id] = CellState(cell_id=cell_id)
        cell = self._cells[cell_id]
        if influence is not None:
            cell.influence = influence
        if threat_level is not None:
            cell.threat_level = threat_level
        if flow is not None:
            cell.flow = flow
        if status is not None:
            cell.status = status
        self._dirty.add(cell_id)

    def advance_tick(self) -> None:
        self._tick += 1

    def flush_deltas(self) -> list[dict]:
        deltas = []
        for cell_id in self._dirty:
            cell = self._cells[cell_id]
            deltas.append({
                "cell_id": cell.cell_id,
                "tick": self._tick,
                "influence": cell.influence,
                "threat_level": cell.threat_level,
                "flow": cell.flow,
                "status": cell.status,
            })
        self._dirty.clear()
        return deltas

    def snapshot(self) -> list[dict]:
        return [
            {
                "cell_id": c.cell_id,
                "influence": c.influence,
                "threat_level": c.threat_level,
                "flow": c.flow,
                "status": c.status,
            }
            for c in self._cells.values()
        ]

    def load_snapshot(self, data: list[dict], tick: int) -> None:
        self._cells.clear()
        self._dirty.clear()
        self._tick = tick
        for row in data:
            self._cells[row["cell_id"]] = CellState(
                cell_id=row["cell_id"],
                influence=row.get("influence"),
                threat_level=row.get("threat_level", 0.0),
                flow=row.get("flow", 0.0),
                status=row.get("status", "open"),
            )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd backend && pytest tests/test_world_state.py -v`
Expected: All 5 tests PASS

- [ ] **Step 5: Commit**

```bash
git add backend/src/parallax/simulation/world_state.py backend/tests/test_world_state.py
git commit -m "feat: in-memory world state with delta tracking for efficient DuckDB persistence"
```

---

## Task 6: Cascade Rules Engine

**Files:**
- Create: `backend/src/parallax/simulation/cascade.py`
- Create: `backend/tests/test_cascade.py`

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/test_cascade.py
from pathlib import Path
from parallax.simulation.cascade import CascadeEngine
from parallax.simulation.config import load_scenario_config
from parallax.simulation.world_state import WorldState


def _config():
    return load_scenario_config(Path(__file__).parent.parent / "config" / "scenario_hormuz.yaml")


def test_blockade_reduces_flow():
    config = _config()
    ws = WorldState()
    # Set up a Hormuz cell with normal flow
    ws.update_cell(111, flow=20_000_000.0, status="open")
    ws.advance_tick()

    engine = CascadeEngine(config)
    effects = engine.apply_blockade(ws, cell_id=111, reduction_pct=0.5)

    cell = ws.get_cell(111)
    assert cell["flow"] == 10_000_000.0
    assert cell["status"] == "restricted"
    assert effects["supply_loss"] == 10_000_000.0


def test_supply_loss_triggers_price_shock():
    config = _config()
    engine = CascadeEngine(config)
    current_price = 80.0
    supply_loss = 5_000_000  # 25% of Hormuz flow
    bypass_used = 3_500_000  # min bypass capacity

    new_price = engine.compute_price_shock(
        current_price=current_price,
        supply_loss=supply_loss,
        bypass_active=bypass_used,
    )

    # Net loss = 5M - 3.5M = 1.5M. Price should increase.
    assert new_price > current_price
    # But clamped to ceiling
    assert new_price <= config.oil_price_ceiling


def test_price_shock_clamped_to_floor_and_ceiling():
    config = _config()
    engine = CascadeEngine(config)

    # Massive supply loss → should hit ceiling
    price = engine.compute_price_shock(current_price=150.0, supply_loss=20_000_000, bypass_active=0)
    assert price == config.oil_price_ceiling

    # No loss → price stays
    price = engine.compute_price_shock(current_price=80.0, supply_loss=0, bypass_active=0)
    assert price == 80.0


def test_reroute_penalty_computed():
    config = _config()
    engine = CascadeEngine(config)
    penalty = engine.reroute_penalty()
    # Should be roughly 84% based on default config
    assert 0.80 < penalty.distance_increase_pct < 0.90
    assert penalty.transit_days_min == config.reroute_transit_days_min
    assert penalty.transit_days_max == config.reroute_transit_days_max
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && pytest tests/test_cascade.py -v`
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Implement cascade engine**

```python
# backend/src/parallax/simulation/cascade.py
from dataclasses import dataclass

from parallax.simulation.config import ScenarioConfig
from parallax.simulation.world_state import WorldState


@dataclass(frozen=True)
class ReroutePenalty:
    distance_increase_pct: float
    transit_days_min: int
    transit_days_max: int


class CascadeEngine:
    """Deterministic, rule-based cascade propagation."""

    def __init__(self, config: ScenarioConfig) -> None:
        self._config = config

    def apply_blockade(
        self, ws: WorldState, cell_id: int, reduction_pct: float
    ) -> dict:
        cell = ws.get_cell(cell_id)
        if cell is None:
            return {"supply_loss": 0.0}

        original_flow = cell["flow"]
        reduced_flow = original_flow * (1.0 - reduction_pct)
        supply_loss = original_flow - reduced_flow

        new_status = "blocked" if reduction_pct >= 0.95 else "restricted"
        ws.update_cell(cell_id, flow=reduced_flow, status=new_status)

        return {"supply_loss": supply_loss}

    def compute_price_shock(
        self,
        current_price: float,
        supply_loss: float,
        bypass_active: float,
    ) -> float:
        net_loss = max(0.0, supply_loss - bypass_active)
        if net_loss == 0:
            return current_price

        # Price increase proportional to net loss as fraction of total Hormuz flow
        loss_fraction = net_loss / self._config.hormuz_daily_flow
        # Rough elasticity: 10% supply loss → ~30% price increase
        price_multiplier = 1.0 + (loss_fraction * 3.0)
        new_price = current_price * price_multiplier

        return max(
            self._config.oil_price_floor,
            min(self._config.oil_price_ceiling, new_price),
        )

    def reroute_penalty(self) -> ReroutePenalty:
        return ReroutePenalty(
            distance_increase_pct=self._config.reroute_distance_penalty_pct,
            transit_days_min=self._config.reroute_transit_days_min,
            transit_days_max=self._config.reroute_transit_days_max,
        )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd backend && pytest tests/test_cascade.py -v`
Expected: All 4 tests PASS

- [ ] **Step 5: Commit**

```bash
git add backend/src/parallax/simulation/cascade.py backend/tests/test_cascade.py
git commit -m "feat: cascade rules engine with parameterized blockade, price shock, and rerouting"
```

---

## Task 7: Circuit Breaker

**Files:**
- Create: `backend/src/parallax/simulation/circuit_breaker.py`
- Create: `backend/tests/test_circuit_breaker.py`

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/test_circuit_breaker.py
from parallax.simulation.circuit_breaker import CircuitBreaker


def test_allows_single_level_escalation():
    cb = CircuitBreaker(max_per_tick=1, cooldown_ticks=3, shock_threshold=8.0)
    assert cb.allow_escalation("iran/irgc_navy", levels=1, goldstein_score=None) is True


def test_blocks_multi_level_escalation():
    cb = CircuitBreaker(max_per_tick=1, cooldown_ticks=3, shock_threshold=8.0)
    assert cb.allow_escalation("iran/irgc_navy", levels=3, goldstein_score=None) is False


def test_cooldown_blocks_after_escalation():
    cb = CircuitBreaker(max_per_tick=1, cooldown_ticks=3, shock_threshold=8.0)
    cb.record_escalation("iran/irgc_navy", tick=10)

    assert cb.allow_escalation("iran/irgc_navy", levels=1, goldstein_score=None, current_tick=11) is False
    assert cb.allow_escalation("iran/irgc_navy", levels=1, goldstein_score=None, current_tick=12) is False
    assert cb.allow_escalation("iran/irgc_navy", levels=1, goldstein_score=None, current_tick=13) is True


def test_exogenous_shock_bypasses_all_limits():
    cb = CircuitBreaker(max_per_tick=1, cooldown_ticks=3, shock_threshold=8.0)
    cb.record_escalation("iran/irgc_navy", tick=10)

    # Normally blocked (cooldown + multi-level), but goldstein > threshold
    assert cb.allow_escalation("iran/irgc_navy", levels=5, goldstein_score=9.5, current_tick=11) is True


def test_different_agents_independent_cooldowns():
    cb = CircuitBreaker(max_per_tick=1, cooldown_ticks=3, shock_threshold=8.0)
    cb.record_escalation("iran/irgc_navy", tick=10)

    # Different agent should not be blocked
    assert cb.allow_escalation("usa/centcom", levels=1, goldstein_score=None, current_tick=11) is True
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && pytest tests/test_circuit_breaker.py -v`
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Implement circuit breaker**

```python
# backend/src/parallax/simulation/circuit_breaker.py


class CircuitBreaker:
    def __init__(
        self,
        max_per_tick: int,
        cooldown_ticks: int,
        shock_threshold: float,
    ) -> None:
        self._max_per_tick = max_per_tick
        self._cooldown_ticks = cooldown_ticks
        self._shock_threshold = shock_threshold
        self._last_escalation: dict[str, int] = {}  # agent_id → tick

    def allow_escalation(
        self,
        agent_id: str,
        levels: int,
        goldstein_score: float | None,
        current_tick: int = 0,
    ) -> bool:
        # Exogenous shock override — bypass all limits
        if goldstein_score is not None and abs(goldstein_score) >= self._shock_threshold:
            return True

        # Check escalation level limit
        if levels > self._max_per_tick:
            return False

        # Check cooldown
        last_tick = self._last_escalation.get(agent_id)
        if last_tick is not None:
            if current_tick - last_tick < self._cooldown_ticks:
                return False

        return True

    def record_escalation(self, agent_id: str, tick: int) -> None:
        self._last_escalation[agent_id] = tick
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd backend && pytest tests/test_circuit_breaker.py -v`
Expected: All 5 tests PASS

- [ ] **Step 5: Commit**

```bash
git add backend/src/parallax/simulation/circuit_breaker.py backend/tests/test_circuit_breaker.py
git commit -m "feat: cascade circuit breaker with cooldowns and exogenous shock override"
```

---

## Task 8: Simulation Engine Core (DES)

**Files:**
- Create: `backend/src/parallax/simulation/engine.py`
- Create: `backend/tests/test_engine.py`

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/test_engine.py
import asyncio
import pytest
from parallax.simulation.engine import SimulationEngine, SimEvent


@pytest.mark.asyncio
async def test_engine_processes_events_in_tick_order():
    processed = []

    async def handler(event: SimEvent):
        processed.append(event.tick)

    engine = SimulationEngine(handler=handler)
    engine.schedule(SimEvent(tick=3, event_type="test", payload={}))
    engine.schedule(SimEvent(tick=1, event_type="test", payload={}))
    engine.schedule(SimEvent(tick=2, event_type="test", payload={}))

    await engine.run_until_tick(3)
    assert processed == [1, 2, 3]


@pytest.mark.asyncio
async def test_engine_stops_at_target_tick():
    calls = []

    async def handler(event: SimEvent):
        calls.append(event.tick)

    engine = SimulationEngine(handler=handler)
    for t in range(1, 10):
        engine.schedule(SimEvent(tick=t, event_type="test", payload={}))

    await engine.run_until_tick(5)
    assert calls == [1, 2, 3, 4, 5]
    assert engine.current_tick == 5


@pytest.mark.asyncio
async def test_engine_tick_accessible():
    async def handler(event: SimEvent):
        pass

    engine = SimulationEngine(handler=handler)
    assert engine.current_tick == 0
    engine.schedule(SimEvent(tick=1, event_type="test", payload={}))
    await engine.run_until_tick(1)
    assert engine.current_tick == 1
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && pytest tests/test_engine.py -v`
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Implement DES engine**

```python
# backend/src/parallax/simulation/engine.py
import heapq
from dataclasses import dataclass, field
from typing import Any, Callable, Awaitable


@dataclass(order=True)
class SimEvent:
    tick: int
    event_type: str = field(compare=False)
    payload: dict[str, Any] = field(compare=False, default_factory=dict)
    source: str | None = field(compare=False, default=None)


class SimulationEngine:
    """Discrete event simulation with priority queue and async event handler."""

    def __init__(
        self,
        handler: Callable[[SimEvent], Awaitable[None]],
    ) -> None:
        self._handler = handler
        self._queue: list[SimEvent] = []
        self._current_tick: int = 0

    @property
    def current_tick(self) -> int:
        return self._current_tick

    def schedule(self, event: SimEvent) -> None:
        heapq.heappush(self._queue, event)

    async def run_until_tick(self, target_tick: int) -> None:
        while self._queue and self._queue[0].tick <= target_tick:
            event = heapq.heappop(self._queue)
            self._current_tick = event.tick
            await self._handler(event)

    async def step(self) -> bool:
        """Process the next event. Returns False if queue is empty."""
        if not self._queue:
            return False
        event = heapq.heappop(self._queue)
        self._current_tick = event.tick
        await self._handler(event)
        return True

    def pending_count(self) -> int:
        return len(self._queue)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd backend && pytest tests/test_engine.py -v`
Expected: All 3 tests PASS

- [ ] **Step 5: Commit**

```bash
git add backend/src/parallax/simulation/engine.py backend/tests/test_engine.py
git commit -m "feat: discrete event simulation engine with priority queue and async handler"
```

---

## Task 9: GDELT Ingestion — Entity List + Volume Gate

**Files:**
- Create: `backend/src/parallax/ingestion/__init__.py`
- Create: `backend/src/parallax/ingestion/entities.py`
- Create: `backend/src/parallax/ingestion/gdelt.py`
- Create: `backend/tests/test_gdelt_filter.py`

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/test_gdelt_filter.py
from parallax.ingestion.entities import CRITICAL_ENTITIES, matches_critical_entity
from parallax.ingestion.gdelt import volume_gate


def test_critical_entities_includes_key_actors():
    flat = " ".join(CRITICAL_ENTITIES).lower()
    assert "irgc" in flat
    assert "centcom" in flat
    assert "hormuz" in flat
    assert "aramco" in flat
    assert "bandar abbas" in flat


def test_matches_critical_entity_positive():
    assert matches_critical_entity("IRGC forces deployed near Hormuz") is True
    assert matches_critical_entity("CENTCOM repositions carrier group") is True


def test_matches_critical_entity_negative():
    assert matches_critical_entity("Weather update for London") is False


def test_volume_gate_passes_high_volume():
    event = {"NumMentions": 10, "NumSources": 5, "Actor1Name": "IRAN"}
    assert volume_gate(event) is True


def test_volume_gate_blocks_low_volume():
    event = {"NumMentions": 1, "NumSources": 1, "Actor1Name": "IRAN"}
    assert volume_gate(event) is False


def test_volume_gate_overrides_for_critical_entity():
    event = {
        "NumMentions": 1,
        "NumSources": 1,
        "Actor1Name": "IRGC",
        "summary": "IRGC conducts naval exercise",
    }
    assert volume_gate(event, check_entity_override=True) is True
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && pytest tests/test_gdelt_filter.py -v`
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Implement entities list and volume gate**

```python
# backend/src/parallax/ingestion/__init__.py
```

```python
# backend/src/parallax/ingestion/entities.py
CRITICAL_ENTITIES: list[str] = [
    # Actors
    "IRGC", "IRGC Navy", "CENTCOM", "Aramco", "ADNOC",
    "Khamenei", "Rouhani", "Trump", "MBS", "Mohammad bin Salman",
    "PLA Navy", "CNOOC", "Sinopec",
    # Locations
    "Hormuz", "Strait of Hormuz", "Bandar Abbas", "Fujairah",
    "Ras Tanura", "Yanbu", "Gulf of Oman", "Persian Gulf",
    # Keywords
    "tanker seizure", "naval blockade", "shipping lane",
    "oil sanctions", "strait closure", "mine laying", "naval exercise",
    "carrier group", "maritime security", "oil embargo",
]

_ENTITY_LOWER = [e.lower() for e in CRITICAL_ENTITIES]


def matches_critical_entity(text: str) -> bool:
    text_lower = text.lower()
    return any(entity in text_lower for entity in _ENTITY_LOWER)
```

```python
# backend/src/parallax/ingestion/gdelt.py
from parallax.ingestion.entities import matches_critical_entity


def volume_gate(
    event: dict,
    min_mentions: int = 3,
    min_sources: int = 2,
    check_entity_override: bool = False,
) -> bool:
    mentions = event.get("NumMentions", 0)
    sources = event.get("NumSources", 0)

    if mentions > min_mentions and sources > min_sources:
        return True

    if check_entity_override:
        searchable = " ".join(
            str(event.get(k, ""))
            for k in ("Actor1Name", "Actor2Name", "summary", "ActionGeo_FullName")
        )
        if matches_critical_entity(searchable):
            return True

    return False
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd backend && pytest tests/test_gdelt_filter.py -v`
Expected: All 6 tests PASS

- [ ] **Step 5: Commit**

```bash
git add backend/src/parallax/ingestion/ backend/tests/test_gdelt_filter.py
git commit -m "feat: GDELT volume gate with named-entity override for critical actors"
```

---

## Task 10: GDELT Semantic Dedup

**Files:**
- Create: `backend/src/parallax/ingestion/dedup.py`
- Create: `backend/tests/test_dedup.py`

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/test_dedup.py
from parallax.ingestion.dedup import SemanticDeduplicator


def test_exact_duplicates_removed():
    dedup = SemanticDeduplicator(similarity_threshold=0.85)
    events = [
        {"event_id": "1", "summary": "Iran deploys naval forces near Hormuz strait"},
        {"event_id": "2", "summary": "Iran deploys naval forces near Hormuz strait"},
    ]
    result = dedup.deduplicate(events)
    assert len(result) == 1


def test_similar_events_deduplicated():
    dedup = SemanticDeduplicator(similarity_threshold=0.85)
    events = [
        {"event_id": "1", "summary": "Iran deploys naval forces near Strait of Hormuz"},
        {"event_id": "2", "summary": "Iranian navy deploys military ships near Hormuz strait"},
    ]
    result = dedup.deduplicate(events)
    assert len(result) == 1


def test_different_events_kept():
    dedup = SemanticDeduplicator(similarity_threshold=0.85)
    events = [
        {"event_id": "1", "summary": "Iran deploys naval forces near Hormuz strait"},
        {"event_id": "2", "summary": "Saudi Arabia increases oil production output"},
    ]
    result = dedup.deduplicate(events)
    assert len(result) == 2
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && pytest tests/test_dedup.py -v`
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Implement semantic deduplicator**

```python
# backend/src/parallax/ingestion/dedup.py
import numpy as np
from sentence_transformers import SentenceTransformer


class SemanticDeduplicator:
    def __init__(
        self,
        similarity_threshold: float = 0.85,
        model_name: str = "all-MiniLM-L6-v2",
    ) -> None:
        self._threshold = similarity_threshold
        self._model = SentenceTransformer(model_name)

    def deduplicate(self, events: list[dict]) -> list[dict]:
        if len(events) <= 1:
            return events

        summaries = [e.get("summary", "") for e in events]
        embeddings = self._model.encode(summaries, normalize_embeddings=True)

        keep_indices: list[int] = []
        for i, emb in enumerate(embeddings):
            is_dup = False
            for j in keep_indices:
                sim = float(np.dot(emb, embeddings[j]))
                if sim >= self._threshold:
                    is_dup = True
                    break
            if not is_dup:
                keep_indices.append(i)

        return [events[i] for i in keep_indices]
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd backend && pytest tests/test_dedup.py -v`
Expected: All 3 tests PASS (first run will download the ~80MB model)

- [ ] **Step 5: Commit**

```bash
git add backend/src/parallax/ingestion/dedup.py backend/tests/test_dedup.py
git commit -m "feat: semantic dedup for GDELT events using sentence-transformers"
```

---

## Task 11: Agent Schemas + Registry

**Files:**
- Create: `backend/src/parallax/agents/__init__.py`
- Create: `backend/src/parallax/agents/schemas.py`
- Create: `backend/src/parallax/agents/registry.py`
- Create: `backend/tests/test_agent_schemas.py`

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/test_agent_schemas.py
import json
from parallax.agents.schemas import AgentDecision, SubActorRecommendation
from parallax.agents.registry import AgentRegistry, AgentInfo


def test_agent_decision_validates():
    d = AgentDecision(
        agent_id="iran/irgc_navy",
        tick=10,
        action_type="military_deployment",
        target_h3_cells=[612345678],
        intensity=0.7,
        description="Patrol increase",
        reasoning="Deterrence",
        confidence=0.78,
        prompt_version="v1.0.0",
    )
    assert d.agent_id == "iran/irgc_navy"
    assert 0.0 <= d.confidence <= 1.0


def test_agent_decision_rejects_invalid_confidence():
    try:
        AgentDecision(
            agent_id="x",
            tick=1,
            action_type="x",
            target_h3_cells=[],
            intensity=0.5,
            description="x",
            reasoning="x",
            confidence=1.5,  # Invalid
            prompt_version="v1.0.0",
        )
        assert False, "Should have raised"
    except ValueError:
        pass


def test_registry_loads_all_countries():
    registry = AgentRegistry()
    countries = registry.list_countries()
    assert "iran" in countries
    assert "usa" in countries
    assert "saudi_arabia" in countries
    assert len(countries) >= 12


def test_registry_sub_actors_for_iran():
    registry = AgentRegistry()
    actors = registry.sub_actors("iran")
    actor_ids = [a.agent_id for a in actors]
    assert "iran/supreme_leader" in actor_ids
    assert "iran/irgc" in actor_ids
    assert "iran/irgc_navy" in actor_ids


def test_registry_agent_info_has_weight():
    registry = AgentRegistry()
    info = registry.get_agent("iran/irgc")
    assert info is not None
    assert 0.0 < info.weight <= 1.0
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && pytest tests/test_agent_schemas.py -v`
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Implement schemas**

```python
# backend/src/parallax/agents/__init__.py
```

```python
# backend/src/parallax/agents/schemas.py
from pydantic import BaseModel, field_validator


class SubActorRecommendation(BaseModel):
    agent_id: str
    action_type: str
    description: str
    reasoning: str
    intensity: float
    confidence: float
    significance: float  # 0-1, used to decide if country agent fires

    @field_validator("confidence", "significance", "intensity")
    @classmethod
    def clamp_zero_one(cls, v: float) -> float:
        if not 0.0 <= v <= 1.0:
            raise ValueError(f"Must be between 0 and 1, got {v}")
        return v


class AgentDecision(BaseModel):
    agent_id: str
    tick: int
    action_type: str
    target_h3_cells: list[int]
    intensity: float
    description: str
    reasoning: str
    confidence: float
    prompt_version: str

    @field_validator("confidence", "intensity")
    @classmethod
    def clamp_zero_one(cls, v: float) -> float:
        if not 0.0 <= v <= 1.0:
            raise ValueError(f"Must be between 0 and 1, got {v}")
        return v
```

```python
# backend/src/parallax/agents/registry.py
from dataclasses import dataclass


@dataclass(frozen=True)
class AgentInfo:
    agent_id: str
    country: str
    name: str
    role: str
    weight: float  # Influence weight within the country
    is_country_agent: bool = False


# Hardcoded Phase 1 roster — Iran/Hormuz focused
_AGENTS: list[AgentInfo] = [
    # Iran
    AgentInfo("iran", "iran", "Iran", "Country Agent", 1.0, is_country_agent=True),
    AgentInfo("iran/supreme_leader", "iran", "Supreme Leader Khamenei", "Head of state, ultimate authority", 0.9),
    AgentInfo("iran/irgc", "iran", "IRGC", "Revolutionary Guard Corps", 0.8),
    AgentInfo("iran/irgc_navy", "iran", "IRGC Navy", "Naval warfare, Hormuz operations", 0.7),
    AgentInfo("iran/foreign_ministry", "iran", "Foreign Ministry", "Diplomacy, negotiations", 0.3),
    AgentInfo("iran/oil_ministry", "iran", "Oil Ministry", "Oil production, OPEC coordination", 0.4),
    # USA
    AgentInfo("usa", "usa", "USA", "Country Agent", 1.0, is_country_agent=True),
    AgentInfo("usa/trump", "usa", "Trump / White House", "President, executive decisions", 0.9),
    AgentInfo("usa/congress", "usa", "Congress", "Legislation, sanctions authorization", 0.4),
    AgentInfo("usa/centcom", "usa", "Pentagon / CENTCOM", "Military operations, Gulf presence", 0.7),
    AgentInfo("usa/state_dept", "usa", "State Department", "Diplomacy, coalition building", 0.3),
    AgentInfo("usa/treasury", "usa", "Treasury", "Sanctions enforcement", 0.6),
    # Saudi Arabia
    AgentInfo("saudi_arabia", "saudi_arabia", "Saudi Arabia", "Country Agent", 1.0, is_country_agent=True),
    AgentInfo("saudi_arabia/mbs", "saudi_arabia", "MBS / Crown Prince", "De facto ruler", 0.9),
    AgentInfo("saudi_arabia/aramco", "saudi_arabia", "Aramco", "Oil production, spare capacity", 0.7),
    AgentInfo("saudi_arabia/opec", "saudi_arabia", "OPEC Delegation", "Cartel coordination", 0.5),
    # China
    AgentInfo("china", "china", "China", "Country Agent", 1.0, is_country_agent=True),
    AgentInfo("china/xi", "china", "Xi / CCP", "Head of state", 0.9),
    AgentInfo("china/pla_navy", "china", "PLA Navy", "Naval presence, Gulf of Aden", 0.5),
    AgentInfo("china/cnooc_sinopec", "china", "CNOOC / Sinopec", "Energy imports, SPR", 0.6),
    # Russia
    AgentInfo("russia", "russia", "Russia", "Country Agent", 1.0, is_country_agent=True),
    AgentInfo("russia/putin", "russia", "Putin", "Head of state", 0.9),
    AgentInfo("russia/rosneft", "russia", "Rosneft", "Oil production, market share", 0.6),
    AgentInfo("russia/foreign_ministry", "russia", "Foreign Ministry", "Diplomacy, UN veto", 0.4),
    # UAE
    AgentInfo("uae", "uae", "UAE", "Country Agent", 1.0, is_country_agent=True),
    AgentInfo("uae/leadership", "uae", "UAE Leadership", "MBZ, executive", 0.9),
    AgentInfo("uae/adnoc", "uae", "ADNOC", "Oil production, Fujairah bypass", 0.7),
    AgentInfo("uae/fujairah", "uae", "Fujairah Port Authority", "Port ops, bypass terminal", 0.5),
    # India
    AgentInfo("india", "india", "India", "Country Agent", 1.0, is_country_agent=True),
    AgentInfo("india/pmo", "india", "PMO", "Prime Minister's Office", 0.8),
    AgentInfo("india/indian_oil", "india", "Indian Oil Corp", "Refining, imports", 0.6),
    AgentInfo("india/navy", "india", "Indian Navy", "Maritime security", 0.4),
    # Japan
    AgentInfo("japan", "japan", "Japan", "Country Agent", 1.0, is_country_agent=True),
    AgentInfo("japan/pm", "japan", "PM Office", "Executive decisions", 0.8),
    AgentInfo("japan/jera", "japan", "JERA / Refiners", "Energy imports", 0.6),
    # South Korea
    AgentInfo("south_korea", "south_korea", "South Korea", "Country Agent", 1.0, is_country_agent=True),
    AgentInfo("south_korea/blue_house", "south_korea", "Blue House", "Executive", 0.8),
    AgentInfo("south_korea/sk_energy", "south_korea", "SK Energy / Refiners", "Energy imports", 0.6),
    # EU
    AgentInfo("eu", "eu", "EU", "Country Agent", 1.0, is_country_agent=True),
    AgentInfo("eu/commission", "eu", "EU Commission", "Bloc policy", 0.7),
    AgentInfo("eu/energy_policy", "eu", "EU Energy Policy", "Energy security", 0.5),
    # Israel
    AgentInfo("israel", "israel", "Israel", "Country Agent", 1.0, is_country_agent=True),
    AgentInfo("israel/pm", "israel", "PM Office", "Executive", 0.8),
    AgentInfo("israel/idf", "israel", "IDF", "Military operations", 0.7),
    AgentInfo("israel/mossad", "israel", "Mossad", "Intelligence, covert ops", 0.6),
    # Iraq
    AgentInfo("iraq", "iraq", "Iraq", "Country Agent", 1.0, is_country_agent=True),
    AgentInfo("iraq/pm", "iraq", "PM Office", "Executive", 0.7),
    AgentInfo("iraq/oil_ministry", "iraq", "Oil Ministry", "Production, exports", 0.6),
]

_BY_ID = {a.agent_id: a for a in _AGENTS}
_BY_COUNTRY: dict[str, list[AgentInfo]] = {}
for _a in _AGENTS:
    _BY_COUNTRY.setdefault(_a.country, []).append(_a)


class AgentRegistry:
    def list_countries(self) -> list[str]:
        return sorted(set(a.country for a in _AGENTS if a.is_country_agent))

    def sub_actors(self, country: str) -> list[AgentInfo]:
        return [a for a in _BY_COUNTRY.get(country, []) if not a.is_country_agent]

    def get_agent(self, agent_id: str) -> AgentInfo | None:
        return _BY_ID.get(agent_id)

    def country_agent(self, country: str) -> AgentInfo | None:
        for a in _BY_COUNTRY.get(country, []):
            if a.is_country_agent:
                return a
        return None

    def all_agents(self) -> list[AgentInfo]:
        return list(_AGENTS)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd backend && pytest tests/test_agent_schemas.py -v`
Expected: All 5 tests PASS

- [ ] **Step 5: Commit**

```bash
git add backend/src/parallax/agents/ backend/tests/test_agent_schemas.py
git commit -m "feat: agent schemas with validation, registry with 50-agent Iran/Hormuz roster"
```

---

## Task 12: Agent Router

**Files:**
- Create: `backend/src/parallax/agents/router.py`
- Create: `backend/tests/test_agent_router.py`

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/test_agent_router.py
from parallax.agents.router import AgentRouter
from parallax.agents.registry import AgentRegistry


def test_routes_iran_event_to_iran_agents():
    router = AgentRouter(AgentRegistry())
    event = {
        "actor1": "IRGC",
        "actor2": "USA",
        "summary": "IRGC deploys forces near Hormuz",
        "relevance_score": 0.8,
    }
    agents = router.route(event)
    agent_ids = [a.agent_id for a in agents]
    # Should include Iran sub-actors and USA sub-actors
    assert any("iran/" in aid for aid in agent_ids)
    assert any("usa/" in aid for aid in agent_ids)
    # Should NOT include country-level agents (those fire via escalation)
    assert "iran" not in agent_ids
    assert "usa" not in agent_ids


def test_low_relevance_event_routes_to_nobody():
    router = AgentRouter(AgentRegistry())
    event = {
        "actor1": "UNKNOWN",
        "actor2": "",
        "summary": "Weather forecast for Dubai",
        "relevance_score": 0.2,
    }
    agents = router.route(event)
    assert len(agents) == 0


def test_oil_event_routes_to_energy_actors():
    router = AgentRouter(AgentRegistry())
    event = {
        "actor1": "ARAMCO",
        "actor2": "",
        "summary": "Aramco increases pipeline capacity to Yanbu",
        "relevance_score": 0.7,
    }
    agents = router.route(event)
    agent_ids = [a.agent_id for a in agents]
    assert "saudi_arabia/aramco" in agent_ids
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && pytest tests/test_agent_router.py -v`
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Implement router**

```python
# backend/src/parallax/agents/router.py
from parallax.agents.registry import AgentInfo, AgentRegistry

# Map keywords/actor names to countries
_ACTOR_COUNTRY_MAP: dict[str, str] = {
    "iran": "iran", "irgc": "iran", "khamenei": "iran", "tehran": "iran",
    "usa": "usa", "united states": "usa", "trump": "usa", "centcom": "usa",
    "pentagon": "usa", "white house": "usa",
    "saudi": "saudi_arabia", "aramco": "saudi_arabia", "mbs": "saudi_arabia",
    "riyadh": "saudi_arabia",
    "china": "china", "beijing": "china", "pla": "china", "cnooc": "china",
    "sinopec": "china", "xi": "china",
    "russia": "russia", "moscow": "russia", "putin": "russia", "rosneft": "russia",
    "uae": "uae", "emirates": "uae", "adnoc": "uae", "fujairah": "uae",
    "abu dhabi": "uae",
    "india": "india", "delhi": "india", "indian oil": "india",
    "japan": "japan", "tokyo": "japan", "jera": "japan",
    "south korea": "south_korea", "seoul": "south_korea", "sk energy": "south_korea",
    "eu": "eu", "european": "eu", "brussels": "eu",
    "israel": "israel", "idf": "israel", "mossad": "israel", "tel aviv": "israel",
    "iraq": "iraq", "baghdad": "iraq",
    "opec": "saudi_arabia",  # Route OPEC events to Saudi as primary
}


class AgentRouter:
    def __init__(self, registry: AgentRegistry) -> None:
        self._registry = registry

    def route(self, event: dict, relevance_threshold: float = 0.5) -> list[AgentInfo]:
        if event.get("relevance_score", 0) < relevance_threshold:
            return []

        # Find mentioned countries
        searchable = " ".join(
            str(event.get(k, "")) for k in ("actor1", "actor2", "summary")
        ).lower()

        matched_countries: set[str] = set()
        for keyword, country in _ACTOR_COUNTRY_MAP.items():
            if keyword in searchable:
                matched_countries.add(country)

        # Return sub-actors (not country agents) for matched countries
        agents: list[AgentInfo] = []
        for country in matched_countries:
            agents.extend(self._registry.sub_actors(country))

        return agents
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd backend && pytest tests/test_agent_router.py -v`
Expected: All 3 tests PASS

- [ ] **Step 5: Commit**

```bash
git add backend/src/parallax/agents/router.py backend/tests/test_agent_router.py
git commit -m "feat: agent router with keyword-to-country mapping for event dispatch"
```

---

## Task 13: Agent Runner (LLM Calls + Budget)

**Files:**
- Create: `backend/src/parallax/agents/runner.py`
- Create: `backend/src/parallax/budget/__init__.py`
- Create: `backend/src/parallax/budget/tracker.py`
- Create: `backend/tests/test_agent_runner.py`
- Create: `backend/tests/test_budget_tracker.py`

- [ ] **Step 1: Write budget tracker test**

```python
# backend/tests/test_budget_tracker.py
from parallax.budget.tracker import BudgetTracker


def test_initial_spend_is_zero():
    tracker = BudgetTracker(daily_cap_usd=20.0)
    assert tracker.total_spend_today() == 0.0
    assert tracker.is_over_budget() is False


def test_record_spend():
    tracker = BudgetTracker(daily_cap_usd=20.0)
    tracker.record(input_tokens=4000, output_tokens=500, model="haiku")
    assert tracker.total_spend_today() > 0.0


def test_over_budget_triggers():
    tracker = BudgetTracker(daily_cap_usd=0.001)  # Tiny budget
    tracker.record(input_tokens=100000, output_tokens=10000, model="sonnet")
    assert tracker.is_over_budget() is True


def test_cooldown_enforcement():
    tracker = BudgetTracker(daily_cap_usd=20.0)
    tracker.record_activation("iran/irgc_navy", tick=10)

    assert tracker.can_activate("iran/irgc_navy", current_tick=10, cooldown_ticks=2) is False
    assert tracker.can_activate("iran/irgc_navy", current_tick=12, cooldown_ticks=2) is True
    # Different agent unaffected
    assert tracker.can_activate("usa/centcom", current_tick=10, cooldown_ticks=2) is True
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && pytest tests/test_budget_tracker.py -v`
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Implement budget tracker**

```python
# backend/src/parallax/budget/__init__.py
```

```python
# backend/src/parallax/budget/tracker.py
# Approximate token costs (USD per 1K tokens) as of 2026
_PRICING = {
    "haiku": {"input": 0.001, "output": 0.005},
    "sonnet": {"input": 0.003, "output": 0.015},
    "opus": {"input": 0.015, "output": 0.075},
}


class BudgetTracker:
    def __init__(self, daily_cap_usd: float) -> None:
        self._daily_cap = daily_cap_usd
        self._spend_today: float = 0.0
        self._last_activation: dict[str, int] = {}  # agent_id → tick

    def record(self, input_tokens: int, output_tokens: int, model: str) -> None:
        pricing = _PRICING.get(model, _PRICING["sonnet"])
        cost = (input_tokens / 1000) * pricing["input"] + (output_tokens / 1000) * pricing["output"]
        self._spend_today += cost

    def total_spend_today(self) -> float:
        return self._spend_today

    def is_over_budget(self) -> bool:
        return self._spend_today >= self._daily_cap

    def reset_daily(self) -> None:
        self._spend_today = 0.0

    def record_activation(self, agent_id: str, tick: int) -> None:
        self._last_activation[agent_id] = tick

    def can_activate(self, agent_id: str, current_tick: int, cooldown_ticks: int) -> bool:
        last = self._last_activation.get(agent_id)
        if last is None:
            return True
        return current_tick - last >= cooldown_ticks
```

- [ ] **Step 4: Write agent runner test**

```python
# backend/tests/test_agent_runner.py
import pytest
from unittest.mock import AsyncMock, patch
from parallax.agents.runner import AgentRunner
from parallax.agents.schemas import SubActorRecommendation
from parallax.agents.registry import AgentRegistry
from parallax.budget.tracker import BudgetTracker


@pytest.mark.asyncio
async def test_runner_calls_llm_and_parses_response():
    mock_client = AsyncMock()
    mock_client.messages.create.return_value = AsyncMock(
        content=[AsyncMock(text='{"action_type":"patrol","description":"Increased patrols","reasoning":"Deterrence","intensity":0.6,"confidence":0.7,"significance":0.8}')],
        usage=AsyncMock(input_tokens=1000, output_tokens=200),
    )

    runner = AgentRunner(
        client=mock_client,
        budget=BudgetTracker(daily_cap_usd=20.0),
        max_input_tokens=4000,
        max_output_tokens=500,
    )

    rec = await runner.run_sub_actor(
        agent_id="iran/irgc_navy",
        system_prompt="You are the IRGC Navy.",
        context="CENTCOM repositioned carrier group.",
        prompt_version="v1.0.0",
        model="haiku",
    )

    assert isinstance(rec, SubActorRecommendation)
    assert rec.action_type == "patrol"
    assert rec.confidence == 0.7


@pytest.mark.asyncio
async def test_runner_respects_budget_cap():
    runner = AgentRunner(
        client=AsyncMock(),
        budget=BudgetTracker(daily_cap_usd=0.0),  # Zero budget
        max_input_tokens=4000,
        max_output_tokens=500,
    )

    rec = await runner.run_sub_actor(
        agent_id="iran/irgc_navy",
        system_prompt="You are the IRGC Navy.",
        context="Event",
        prompt_version="v1.0.0",
        model="haiku",
    )
    assert rec is None  # Should skip due to budget
```

- [ ] **Step 5: Run tests to verify they fail**

Run: `cd backend && pytest tests/test_agent_runner.py -v`
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 6: Implement agent runner**

```python
# backend/src/parallax/agents/runner.py
import json
import logging
from typing import Any

from parallax.agents.schemas import SubActorRecommendation
from parallax.budget.tracker import BudgetTracker

logger = logging.getLogger(__name__)


class AgentRunner:
    def __init__(
        self,
        client: Any,  # anthropic.AsyncAnthropic
        budget: BudgetTracker,
        max_input_tokens: int = 4000,
        max_output_tokens: int = 500,
    ) -> None:
        self._client = client
        self._budget = budget
        self._max_input = max_input_tokens
        self._max_output = max_output_tokens

    async def run_sub_actor(
        self,
        agent_id: str,
        system_prompt: str,
        context: str,
        prompt_version: str,
        model: str = "haiku",
    ) -> SubActorRecommendation | None:
        if self._budget.is_over_budget():
            logger.warning("Budget exceeded, skipping %s", agent_id)
            return None

        model_id = {
            "haiku": "claude-haiku-4-5-20251001",
            "sonnet": "claude-sonnet-4-6",
            "opus": "claude-opus-4-6",
        }.get(model, "claude-sonnet-4-6")

        try:
            response = await self._client.messages.create(
                model=model_id,
                max_tokens=self._max_output,
                system=system_prompt,
                messages=[
                    {
                        "role": "user",
                        "content": (
                            f"Analyze this event and respond with a JSON object containing: "
                            f"action_type, description, reasoning, intensity (0-1), "
                            f"confidence (0-1), significance (0-1).\n\n"
                            f"Event:\n{context}"
                        ),
                    }
                ],
            )

            self._budget.record(
                input_tokens=response.usage.input_tokens,
                output_tokens=response.usage.output_tokens,
                model=model,
            )

            raw = response.content[0].text
            data = json.loads(raw)
            return SubActorRecommendation(agent_id=agent_id, **data)

        except Exception:
            logger.exception("Agent %s failed", agent_id)
            return None
```

- [ ] **Step 7: Run all tests to verify they pass**

Run: `cd backend && pytest tests/test_budget_tracker.py tests/test_agent_runner.py -v`
Expected: All 6 tests PASS

- [ ] **Step 8: Commit**

```bash
git add backend/src/parallax/agents/runner.py backend/src/parallax/budget/ backend/tests/test_budget_tracker.py backend/tests/test_agent_runner.py
git commit -m "feat: agent runner with LLM calls, budget tracking, and cooldown enforcement"
```

---

## Task 14: Eval — Prediction Logging + Scoring

**Files:**
- Create: `backend/src/parallax/eval/__init__.py`
- Create: `backend/src/parallax/eval/predictions.py`
- Create: `backend/src/parallax/eval/scoring.py`
- Create: `backend/tests/test_predictions.py`
- Create: `backend/tests/test_scoring.py`

- [ ] **Step 1: Write the scoring test**

```python
# backend/tests/test_scoring.py
from parallax.eval.scoring import (
    score_direction,
    score_magnitude,
    compute_calibration,
)


def test_direction_correct():
    assert score_direction(predicted="increase", actual_change=5.0) is True
    assert score_direction(predicted="decrease", actual_change=-3.0) is True


def test_direction_incorrect():
    assert score_direction(predicted="increase", actual_change=-2.0) is False
    assert score_direction(predicted="decrease", actual_change=1.0) is False


def test_magnitude_within_range():
    assert score_magnitude(predicted_range=[10, 30], actual_value=20.0) is True
    assert score_magnitude(predicted_range=[10, 30], actual_value=10.0) is True
    assert score_magnitude(predicted_range=[10, 30], actual_value=30.0) is True


def test_magnitude_outside_range():
    assert score_magnitude(predicted_range=[10, 30], actual_value=5.0) is False
    assert score_magnitude(predicted_range=[10, 30], actual_value=35.0) is False


def test_calibration_perfect():
    # 8 predictions at 0.8 confidence, 6 correct = 75% (close to 80%)
    predictions = [
        {"confidence": 0.8, "correct": True} for _ in range(6)
    ] + [
        {"confidence": 0.8, "correct": False} for _ in range(2)
    ]
    cal = compute_calibration(predictions, bins=1)
    # Single bin: mean confidence = 0.8, accuracy = 0.75
    assert len(cal) == 1
    assert abs(cal[0]["mean_confidence"] - 0.8) < 0.01
    assert abs(cal[0]["accuracy"] - 0.75) < 0.01
```

- [ ] **Step 2: Write the prediction creation test**

```python
# backend/tests/test_predictions.py
from parallax.eval.predictions import create_prediction


def test_create_prediction_has_required_fields():
    pred = create_prediction(
        agent_id="iran/irgc_navy",
        prediction_type="hormuz_traffic_reduction",
        direction="decrease",
        magnitude_range=[30, 50],
        unit="percent",
        timeframe="7d",
        confidence=0.65,
        reasoning="Based on IRGC deployment patterns",
        prompt_version="v1.0.0",
    )
    assert pred["agent_id"] == "iran/irgc_navy"
    assert pred["prediction_id"] is not None
    assert pred["resolve_by"] is not None
    assert pred["direction"] == "decrease"


def test_create_prediction_computes_resolve_by():
    pred = create_prediction(
        agent_id="x",
        prediction_type="x",
        direction="increase",
        magnitude_range=[0, 100],
        unit="percent",
        timeframe="7d",
        confidence=0.5,
        reasoning="x",
        prompt_version="v1.0.0",
    )
    # resolve_by should be 7 days after created_at
    from datetime import datetime, timedelta
    created = datetime.fromisoformat(pred["created_at"])
    resolve = datetime.fromisoformat(pred["resolve_by"])
    diff = resolve - created
    assert diff == timedelta(days=7)
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `cd backend && pytest tests/test_scoring.py tests/test_predictions.py -v`
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 4: Implement scoring**

```python
# backend/src/parallax/eval/__init__.py
```

```python
# backend/src/parallax/eval/scoring.py


def score_direction(predicted: str, actual_change: float) -> bool:
    if predicted == "increase":
        return actual_change > 0
    if predicted == "decrease":
        return actual_change < 0
    return actual_change == 0


def score_magnitude(predicted_range: list[float], actual_value: float) -> bool:
    return predicted_range[0] <= actual_value <= predicted_range[1]


def compute_calibration(
    predictions: list[dict], bins: int = 5
) -> list[dict]:
    if not predictions:
        return []

    sorted_preds = sorted(predictions, key=lambda p: p["confidence"])

    bin_size = max(1, len(sorted_preds) // bins)
    result = []

    for i in range(0, len(sorted_preds), bin_size):
        chunk = sorted_preds[i : i + bin_size]
        mean_conf = sum(p["confidence"] for p in chunk) / len(chunk)
        accuracy = sum(1 for p in chunk if p["correct"]) / len(chunk)
        result.append({
            "mean_confidence": mean_conf,
            "accuracy": accuracy,
            "count": len(chunk),
        })

    return result
```

- [ ] **Step 5: Implement prediction creation**

```python
# backend/src/parallax/eval/predictions.py
import re
import uuid
from datetime import datetime, timedelta, timezone


_TIMEFRAME_PATTERN = re.compile(r"(\d+)([dhm])")


def _parse_timeframe(tf: str) -> timedelta:
    m = _TIMEFRAME_PATTERN.match(tf)
    if not m:
        raise ValueError(f"Invalid timeframe: {tf}")
    value, unit = int(m.group(1)), m.group(2)
    if unit == "d":
        return timedelta(days=value)
    if unit == "h":
        return timedelta(hours=value)
    if unit == "m":
        return timedelta(minutes=value)
    raise ValueError(f"Unknown unit: {unit}")


def create_prediction(
    agent_id: str,
    prediction_type: str,
    direction: str,
    magnitude_range: list[float],
    unit: str,
    timeframe: str,
    confidence: float,
    reasoning: str,
    prompt_version: str,
) -> dict:
    now = datetime.now(timezone.utc)
    resolve_by = now + _parse_timeframe(timeframe)
    return {
        "prediction_id": str(uuid.uuid4()),
        "agent_id": agent_id,
        "prediction_type": prediction_type,
        "direction": direction,
        "magnitude_range": magnitude_range,
        "unit": unit,
        "timeframe": timeframe,
        "confidence": confidence,
        "reasoning": reasoning,
        "prompt_version": prompt_version,
        "created_at": now.isoformat(),
        "resolve_by": resolve_by.isoformat(),
    }
```

- [ ] **Step 6: Run tests to verify they pass**

Run: `cd backend && pytest tests/test_scoring.py tests/test_predictions.py -v`
Expected: All 7 tests PASS

- [ ] **Step 7: Commit**

```bash
git add backend/src/parallax/eval/ backend/tests/test_scoring.py backend/tests/test_predictions.py
git commit -m "feat: eval framework with prediction creation, direction/magnitude/calibration scoring"
```

---

## Task 15: Prompt Versioning

**Files:**
- Create: `backend/src/parallax/eval/prompt_versioning.py`
- Create: `backend/tests/test_prompt_versioning.py`

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/test_prompt_versioning.py
from parallax.eval.prompt_versioning import PromptVersionManager


def test_initial_version():
    mgr = PromptVersionManager()
    v = mgr.create_version("iran/irgc_navy", "You are the IRGC Navy.", "Historical baseline text")
    assert v == "v1.0.0"


def test_bump_patch():
    mgr = PromptVersionManager()
    mgr.create_version("iran/irgc_navy", "prompt1", "baseline1")
    v = mgr.create_version("iran/irgc_navy", "prompt2", "baseline1")
    assert v == "v1.0.1"


def test_get_current_version():
    mgr = PromptVersionManager()
    mgr.create_version("iran/irgc_navy", "prompt1", "baseline1")
    mgr.create_version("iran/irgc_navy", "prompt2", "baseline1")
    assert mgr.current_version("iran/irgc_navy") == "v1.0.1"


def test_get_prompt_at_version():
    mgr = PromptVersionManager()
    mgr.create_version("iran/irgc_navy", "first prompt", "baseline")
    mgr.create_version("iran/irgc_navy", "second prompt", "baseline")
    assert mgr.get_prompt("iran/irgc_navy", "v1.0.0") == "first prompt"
    assert mgr.get_prompt("iran/irgc_navy", "v1.0.1") == "second prompt"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && pytest tests/test_prompt_versioning.py -v`
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Implement prompt version manager**

```python
# backend/src/parallax/eval/prompt_versioning.py
from dataclasses import dataclass


@dataclass
class PromptRecord:
    version: str
    system_prompt: str
    historical_baseline: str


class PromptVersionManager:
    def __init__(self) -> None:
        self._versions: dict[str, list[PromptRecord]] = {}  # agent_id → versions

    def create_version(
        self, agent_id: str, system_prompt: str, historical_baseline: str
    ) -> str:
        history = self._versions.setdefault(agent_id, [])
        patch = len(history)
        version = f"v1.0.{patch}"
        history.append(PromptRecord(
            version=version,
            system_prompt=system_prompt,
            historical_baseline=historical_baseline,
        ))
        return version

    def current_version(self, agent_id: str) -> str | None:
        history = self._versions.get(agent_id, [])
        if not history:
            return None
        return history[-1].version

    def get_prompt(self, agent_id: str, version: str) -> str | None:
        for record in self._versions.get(agent_id, []):
            if record.version == version:
                return record.system_prompt
        return None

    def get_record(self, agent_id: str, version: str) -> PromptRecord | None:
        for record in self._versions.get(agent_id, []):
            if record.version == version:
                return record
        return None
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd backend && pytest tests/test_prompt_versioning.py -v`
Expected: All 4 tests PASS

- [ ] **Step 5: Commit**

```bash
git add backend/src/parallax/eval/prompt_versioning.py backend/tests/test_prompt_versioning.py
git commit -m "feat: prompt versioning with semver tracking for A/B evaluation"
```

---

## Task 16: Backend API + WebSocket + Auth

**Files:**
- Create: `backend/src/parallax/api/__init__.py`
- Create: `backend/src/parallax/api/auth.py`
- Create: `backend/src/parallax/api/routes.py`
- Create: `backend/src/parallax/api/websocket.py`
- Create: `backend/src/parallax/main.py`
- Create: `backend/tests/test_auth.py`

- [ ] **Step 1: Write the auth test**

```python
# backend/tests/test_auth.py
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from parallax.api.auth import AuthMiddleware, generate_invite_code, verify_invite_code


def test_generate_invite_code():
    code = generate_invite_code("test-seed")
    assert isinstance(code, str)
    assert len(code) >= 8


def test_verify_invite_code_valid():
    code = generate_invite_code("test-seed")
    assert verify_invite_code(code) is True


def test_verify_invite_code_invalid():
    assert verify_invite_code("bogus-code-123") is False


def test_admin_password_grants_admin():
    app = FastAPI()
    auth = AuthMiddleware(admin_password="test-password", invite_seed="seed")

    @app.get("/admin/test")
    async def admin_route():
        return {"ok": True}

    app.middleware("http")(auth)
    client = TestClient(app)

    resp = client.get("/admin/test", headers={"X-Admin-Password": "test-password"})
    assert resp.status_code == 200
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && pytest tests/test_auth.py -v`
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Implement auth**

```python
# backend/src/parallax/api/__init__.py
```

```python
# backend/src/parallax/api/auth.py
import hashlib
import hmac
import secrets
from fastapi import Request, Response
from starlette.middleware.base import RequestResponseEndpoint

_VALID_CODES: set[str] = set()
_INVITE_SEED: str = ""


def generate_invite_code(seed: str) -> str:
    global _INVITE_SEED
    _INVITE_SEED = seed
    raw = secrets.token_urlsafe(12)
    code = hmac.new(seed.encode(), raw.encode(), hashlib.sha256).hexdigest()[:16]
    _VALID_CODES.add(code)
    return code


def verify_invite_code(code: str) -> bool:
    return code in _VALID_CODES


class AuthMiddleware:
    def __init__(self, admin_password: str, invite_seed: str) -> None:
        self._admin_password = admin_password
        self._invite_seed = invite_seed

    async def __call__(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        # Admin routes require admin password
        if request.url.path.startswith("/admin"):
            pw = request.headers.get("X-Admin-Password", "")
            if pw != self._admin_password:
                return Response(status_code=403, content="Forbidden")

        # API routes require invite code or admin password
        if request.url.path.startswith("/api"):
            code = request.query_params.get("invite") or request.headers.get("X-Invite-Code", "")
            pw = request.headers.get("X-Admin-Password", "")
            if pw != self._admin_password and not verify_invite_code(code):
                return Response(status_code=403, content="Invalid invite code")

        return await call_next(request)
```

- [ ] **Step 4: Implement WebSocket handler**

```python
# backend/src/parallax/api/websocket.py
import asyncio
import json
import logging
from typing import Any

from fastapi import WebSocket, WebSocketDisconnect

logger = logging.getLogger(__name__)


class ConnectionManager:
    def __init__(self) -> None:
        self._connections: list[WebSocket] = []
        self._buffer: list[dict] = []
        self._flush_interval: float = 0.1  # 100ms batching

    async def connect(self, ws: WebSocket) -> None:
        await ws.accept()
        self._connections.append(ws)
        logger.info("WebSocket connected, total: %d", len(self._connections))

    def disconnect(self, ws: WebSocket) -> None:
        self._connections.remove(ws)
        logger.info("WebSocket disconnected, total: %d", len(self._connections))

    def queue_message(self, msg: dict) -> None:
        self._buffer.append(msg)

    async def flush_loop(self) -> None:
        while True:
            await asyncio.sleep(self._flush_interval)
            if not self._buffer:
                continue
            batch = self._buffer[:]
            self._buffer.clear()
            payload = json.dumps(batch)
            dead: list[WebSocket] = []
            for ws in self._connections:
                try:
                    await ws.send_text(payload)
                except Exception:
                    dead.append(ws)
            for ws in dead:
                self._connections.remove(ws)

    @property
    def connection_count(self) -> int:
        return len(self._connections)
```

- [ ] **Step 5: Implement REST routes**

```python
# backend/src/parallax/api/routes.py
from fastapi import APIRouter

router = APIRouter()


@router.get("/api/health")
async def health():
    return {"status": "ok"}


@router.get("/api/state")
async def get_state():
    # Placeholder — will be wired to DB queries
    return {"tick": 0, "cells": [], "indicators": {}}


@router.get("/api/predictions")
async def get_predictions():
    return {"predictions": []}


@router.get("/api/decisions")
async def get_decisions():
    return {"decisions": []}


@router.get("/admin/eval")
async def admin_eval():
    return {"eval_results": []}


@router.post("/admin/checkpoint")
async def admin_checkpoint():
    return {"status": "checkpoint_created"}
```

- [ ] **Step 6: Implement main.py app entry point**

```python
# backend/src/parallax/main.py
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI, WebSocket, WebSocketDisconnect

from parallax.api.auth import AuthMiddleware
from parallax.api.routes import router
from parallax.api.websocket import ConnectionManager

ws_manager = ConnectionManager()


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: would initialize DB, start simulation, start ingestion
    import asyncio
    flush_task = asyncio.create_task(ws_manager.flush_loop())
    yield
    # Shutdown
    flush_task.cancel()


app = FastAPI(title="Parallax", lifespan=lifespan)

admin_password = os.environ.get("PARALLAX_ADMIN_PASSWORD", "dev-password")
invite_seed = os.environ.get("PARALLAX_INVITE_SEED", "dev-seed")

auth = AuthMiddleware(admin_password=admin_password, invite_seed=invite_seed)
app.middleware("http")(auth)
app.include_router(router)


@app.websocket("/ws")
async def websocket_endpoint(ws: WebSocket):
    await ws_manager.connect(ws)
    try:
        while True:
            await ws.receive_text()  # Keep alive
    except WebSocketDisconnect:
        ws_manager.disconnect(ws)
```

- [ ] **Step 7: Run auth tests to verify they pass**

Run: `cd backend && pytest tests/test_auth.py -v`
Expected: All 4 tests PASS

- [ ] **Step 8: Commit**

```bash
git add backend/src/parallax/api/ backend/src/parallax/main.py backend/tests/test_auth.py
git commit -m "feat: FastAPI backend with WebSocket, invite code auth, REST endpoints"
```

---

## Task 17: Frontend Scaffold

**Files:**
- Create: `frontend/package.json`
- Create: `frontend/tsconfig.json`
- Create: `frontend/vite.config.ts`
- Create: `frontend/index.html`
- Create: `frontend/src/main.tsx`
- Create: `frontend/src/App.tsx`
- Create: `frontend/src/types/index.ts`

- [ ] **Step 1: Initialize frontend project**

```bash
cd frontend && npm create vite@latest . -- --template react-ts
```

- [ ] **Step 2: Install dependencies**

```bash
cd frontend && npm install @deck.gl/core @deck.gl/layers @deck.gl/geo-layers @deck.gl/react maplibre-gl react-map-gl
```

- [ ] **Step 3: Create TypeScript types**

```typescript
// frontend/src/types/index.ts
export interface HexCell {
  cellId: string;
  influence: string | null;
  threatLevel: number;
  flow: number;
  status: "open" | "restricted" | "blocked" | "mined" | "patrolled";
}

export interface AgentDecisionMsg {
  decisionId: string;
  agentId: string;
  tick: number;
  actionType: string;
  description: string;
  confidence: number;
  createdAt: string;
}

export interface IndicatorUpdate {
  oilPrice: number;
  oilPriceChange: number;
  hormuzTraffic: number;
  hormuzTrafficChange: number;
  bypassUtilization: number;
  bypassCapacity: number;
  escalationLevel: number; // 0-4
}

export interface Prediction {
  predictionId: string;
  agentId: string;
  predictionType: string;
  direction: string;
  magnitudeRange: [number, number];
  confidence: number;
  timeframe: string;
}

export type WsMessage =
  | { type: "cell_update"; cells: HexCell[] }
  | { type: "agent_decision"; decision: AgentDecisionMsg }
  | { type: "indicator_update"; indicators: IndicatorUpdate }
  | { type: "event"; event: { summary: string; timestamp: string } };
```

- [ ] **Step 4: Create App shell**

```tsx
// frontend/src/App.tsx
import { useState } from "react";
import type { AgentDecisionMsg, HexCell, IndicatorUpdate, Prediction } from "./types";

export default function App() {
  const [decisions, setDecisions] = useState<AgentDecisionMsg[]>([]);
  const [indicators, setIndicators] = useState<IndicatorUpdate | null>(null);
  const [predictions, setPredictions] = useState<Prediction[]>([]);

  return (
    <div
      style={{
        display: "grid",
        gridTemplateColumns: "280px 1fr 320px",
        gridTemplateRows: "48px 1fr 180px",
        height: "100vh",
        background: "#0a0e1a",
        color: "#e2e8f0",
        fontFamily: "system-ui, -apple-system, sans-serif",
      }}
    >
      {/* Top bar */}
      <header
        style={{
          gridColumn: "1 / -1",
          background: "#0f1629",
          padding: "0 16px",
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          borderBottom: "1px solid #1e293b",
        }}
      >
        <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
          <span style={{ color: "#60a5fa", fontWeight: 700, fontSize: 15 }}>
            PARALLAX
          </span>
          <span style={{ fontSize: 12, color: "#f59e0b" }}>LIVE</span>
          <span style={{ fontSize: 12, color: "#94a3b8" }}>
            Iran/Hormuz Scenario
          </span>
        </div>
      </header>

      {/* Left: Agent feed */}
      <aside
        style={{
          background: "#0f1629",
          padding: 12,
          overflowY: "auto",
          borderRight: "1px solid #1e293b",
        }}
      >
        <div
          style={{
            color: "#94a3b8",
            fontSize: 11,
            textTransform: "uppercase",
            letterSpacing: 1,
            marginBottom: 12,
          }}
        >
          Agent Activity
        </div>
        {decisions.length === 0 && (
          <p style={{ color: "#475569", fontSize: 13 }}>Waiting for events...</p>
        )}
      </aside>

      {/* Center: Map placeholder */}
      <main
        style={{
          background: "#0a0e1a",
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
        }}
      >
        <p style={{ color: "#475569" }}>deck.gl H3 Map</p>
      </main>

      {/* Right: Indicators */}
      <aside
        style={{
          background: "#0f1629",
          padding: 12,
          overflowY: "auto",
          borderLeft: "1px solid #1e293b",
        }}
      >
        <div
          style={{
            color: "#94a3b8",
            fontSize: 11,
            textTransform: "uppercase",
            letterSpacing: 1,
            marginBottom: 12,
          }}
        >
          Live Indicators
        </div>
        <p style={{ color: "#475569", fontSize: 13 }}>No data yet</p>
      </aside>

      {/* Bottom: Timeline + Predictions */}
      <footer
        style={{
          gridColumn: "1 / -1",
          background: "#0f1629",
          padding: 12,
          borderTop: "1px solid #1e293b",
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
        }}
      >
        <p style={{ color: "#475569", fontSize: 13 }}>Timeline + Predictions</p>
      </footer>
    </div>
  );
}
```

- [ ] **Step 5: Verify it builds**

Run: `cd frontend && npm run build`
Expected: Build succeeds with no errors

- [ ] **Step 6: Commit**

```bash
git add frontend/
git commit -m "feat: React frontend scaffold with 3-column dashboard layout"
```

---

## Task 18: WebSocket Hook + Hex Map

**Files:**
- Create: `frontend/src/hooks/useWebSocket.ts`
- Create: `frontend/src/hooks/useHexData.ts`
- Create: `frontend/src/components/HexMap.tsx`
- Create: `frontend/src/lib/colors.ts`

- [ ] **Step 1: Create WebSocket hook with batching**

```typescript
// frontend/src/hooks/useWebSocket.ts
import { useEffect, useRef, useCallback } from "react";
import type { WsMessage } from "../types";

export function useWebSocket(
  url: string,
  onMessages: (msgs: WsMessage[]) => void
) {
  const wsRef = useRef<WebSocket | null>(null);
  const reconnectTimer = useRef<ReturnType<typeof setTimeout>>();

  const connect = useCallback(() => {
    const ws = new WebSocket(url);
    wsRef.current = ws;

    ws.onmessage = (event) => {
      try {
        const batch: WsMessage[] = JSON.parse(event.data);
        onMessages(batch);
      } catch {
        // ignore malformed
      }
    };

    ws.onclose = () => {
      reconnectTimer.current = setTimeout(connect, 2000);
    };

    ws.onerror = () => ws.close();
  }, [url, onMessages]);

  useEffect(() => {
    connect();
    return () => {
      clearTimeout(reconnectTimer.current);
      wsRef.current?.close();
    };
  }, [connect]);
}
```

- [ ] **Step 2: Create mutable hex data hook (render perf critical path)**

```typescript
// frontend/src/hooks/useHexData.ts
import { useRef, useCallback, useState } from "react";
import type { HexCell } from "../types";

export function useHexData() {
  const dataRef = useRef<Map<string, HexCell>>(new Map());
  // Monotonic counter to trigger deck.gl re-render
  const [revision, setRevision] = useState(0);

  const updateCells = useCallback((cells: HexCell[]) => {
    for (const cell of cells) {
      dataRef.current.set(cell.cellId, cell);
    }
    // Bump revision to trigger deck.gl layer update
    setRevision((r) => r + 1);
  }, []);

  const getData = useCallback((): HexCell[] => {
    return Array.from(dataRef.current.values());
  }, []);

  return { updateCells, getData, revision };
}
```

- [ ] **Step 3: Create color mapping**

```typescript
// frontend/src/lib/colors.ts
const COUNTRY_COLORS: Record<string, [number, number, number]> = {
  iran: [239, 68, 68],     // red
  usa: [59, 130, 246],     // blue
  saudi_arabia: [34, 197, 94], // green
  china: [234, 179, 8],    // yellow
  russia: [168, 85, 247],  // purple
  uae: [6, 182, 212],      // cyan
  india: [249, 115, 22],   // orange
  israel: [236, 72, 153],  // pink
};

export function influenceToColor(influence: string | null): [number, number, number, number] {
  if (!influence) return [30, 41, 59, 80]; // slate, low alpha
  const base = COUNTRY_COLORS[influence] ?? [148, 163, 184]; // gray fallback
  return [...base, 180];
}

export function threatToColor(threat: number): [number, number, number, number] {
  // 0 = green, 0.5 = yellow, 1 = red
  const r = Math.round(255 * Math.min(1, threat * 2));
  const g = Math.round(255 * Math.max(0, 1 - threat * 2));
  return [r, g, 0, Math.round(60 + threat * 140)];
}
```

- [ ] **Step 4: Create HexMap component**

```tsx
// frontend/src/components/HexMap.tsx
import { useMemo } from "react";
import DeckGL from "@deck.gl/react";
import { H3HexagonLayer } from "@deck.gl/geo-layers";
import { Map } from "react-map-gl/maplibre";
import type { HexCell } from "../types";
import { influenceToColor } from "../lib/colors";

const MAPLIBRE_STYLE = "https://basemaps.cartocdn.com/gl/dark-matter-gl-style/style.json";

const INITIAL_VIEW = {
  longitude: 54.5,
  latitude: 25.5,
  zoom: 6,
  pitch: 30,
  bearing: 0,
};

interface Props {
  getData: () => HexCell[];
  revision: number;
}

export function HexMap({ getData, revision }: Props) {
  const layers = useMemo(() => {
    const data = getData();
    return [
      new H3HexagonLayer({
        id: "hex-layer",
        data,
        getHexagon: (d: HexCell) => d.cellId,
        getFillColor: (d: HexCell) => influenceToColor(d.influence),
        getElevation: (d: HexCell) => d.threatLevel * 1000,
        extruded: true,
        elevationScale: 1,
        opacity: 0.7,
        pickable: true,
        transitions: {
          getFillColor: 600,
        },
        updateTriggers: {
          getFillColor: [revision],
          getElevation: [revision],
        },
      }),
    ];
  }, [getData, revision]);

  return (
    <DeckGL
      initialViewState={INITIAL_VIEW}
      controller
      layers={layers}
      style={{ width: "100%", height: "100%" }}
    >
      <Map mapStyle={MAPLIBRE_STYLE} />
    </DeckGL>
  );
}
```

- [ ] **Step 5: Verify it builds**

Run: `cd frontend && npm run build`
Expected: Build succeeds

- [ ] **Step 6: Commit**

```bash
git add frontend/src/
git commit -m "feat: deck.gl H3 hex map with WebSocket hook and mutable data layer"
```

---

## Task 19: Frontend Panels — Agent Feed, Indicators, Predictions

**Files:**
- Create: `frontend/src/components/AgentFeed.tsx`
- Create: `frontend/src/components/LiveIndicators.tsx`
- Create: `frontend/src/components/PredictionCards.tsx`

- [ ] **Step 1: Create AgentFeed component**

```tsx
// frontend/src/components/AgentFeed.tsx
import type { AgentDecisionMsg } from "../types";

const COUNTRY_COLORS: Record<string, string> = {
  iran: "#ef4444", usa: "#3b82f6", saudi_arabia: "#22c55e",
  china: "#eab308", russia: "#a855f7", uae: "#06b6d4",
  india: "#f97316", israel: "#ec4899", japan: "#8b5cf6",
  south_korea: "#14b8a6", eu: "#6366f1", iraq: "#d97706",
};

function getCountry(agentId: string): string {
  return agentId.split("/")[0];
}

interface Props {
  decisions: AgentDecisionMsg[];
}

export function AgentFeed({ decisions }: Props) {
  return (
    <div>
      <div style={{ color: "#94a3b8", fontSize: 11, textTransform: "uppercase", letterSpacing: 1, marginBottom: 12 }}>
        Agent Activity
      </div>
      {decisions.length === 0 && (
        <p style={{ color: "#475569", fontSize: 13 }}>Waiting for events...</p>
      )}
      {decisions.map((d) => {
        const country = getCountry(d.agentId);
        const color = COUNTRY_COLORS[country] ?? "#94a3b8";
        return (
          <div key={d.decisionId} style={{ marginBottom: 12 }}>
            <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 4 }}>
              <div style={{ width: 8, height: 8, borderRadius: "50%", background: color }} />
              <span style={{ fontSize: 13, fontWeight: 600 }}>{country.toUpperCase()}</span>
              <span style={{ fontSize: 11, color: "#94a3b8", marginLeft: "auto" }}>
                {new Date(d.createdAt).toLocaleTimeString()}
              </span>
            </div>
            <div style={{ background: "#1e293b", borderRadius: 6, padding: 8, marginLeft: 16, fontSize: 12 }}>
              <div style={{ color, fontSize: 11, marginBottom: 4 }}>{d.agentId.split("/")[1] ?? d.agentId}</div>
              {d.description} <span style={{ color: "#475569" }}>conf: {d.confidence.toFixed(2)}</span>
            </div>
          </div>
        );
      })}
    </div>
  );
}
```

- [ ] **Step 2: Create LiveIndicators component**

```tsx
// frontend/src/components/LiveIndicators.tsx
import type { IndicatorUpdate } from "../types";

interface Props {
  indicators: IndicatorUpdate | null;
  events: Array<{ summary: string; timestamp: string }>;
}

export function LiveIndicators({ indicators, events }: Props) {
  if (!indicators) {
    return (
      <div>
        <div style={{ color: "#94a3b8", fontSize: 11, textTransform: "uppercase", letterSpacing: 1, marginBottom: 12 }}>
          Live Indicators
        </div>
        <p style={{ color: "#475569", fontSize: 13 }}>No data yet</p>
      </div>
    );
  }

  const priceColor = indicators.oilPriceChange >= 0 ? "#ef4444" : "#22c55e";
  const trafficColor = indicators.hormuzTrafficChange >= 0 ? "#22c55e" : "#ef4444";
  const escalationColors = ["#22c55e", "#22c55e", "#f59e0b", "#f59e0b", "#ef4444"];

  return (
    <div>
      <div style={{ color: "#94a3b8", fontSize: 11, textTransform: "uppercase", letterSpacing: 1, marginBottom: 12 }}>
        Live Indicators
      </div>

      {/* Oil Price */}
      <div style={{ background: "#1e293b", borderRadius: 8, padding: 12, marginBottom: 8 }}>
        <div style={{ display: "flex", justifyContent: "space-between" }}>
          <span style={{ color: "#94a3b8", fontSize: 11 }}>Brent Crude</span>
          <span style={{ color: priceColor, fontSize: 11 }}>
            {indicators.oilPriceChange >= 0 ? "▲" : "▼"} {Math.abs(indicators.oilPriceChange).toFixed(1)}%
          </span>
        </div>
        <div style={{ fontSize: 20, fontWeight: 700 }}>${indicators.oilPrice.toFixed(2)}</div>
      </div>

      {/* Hormuz Traffic */}
      <div style={{ background: "#1e293b", borderRadius: 8, padding: 12, marginBottom: 8 }}>
        <div style={{ display: "flex", justifyContent: "space-between" }}>
          <span style={{ color: "#94a3b8", fontSize: 11 }}>Hormuz Traffic</span>
          <span style={{ color: trafficColor, fontSize: 11 }}>
            {indicators.hormuzTrafficChange >= 0 ? "▲" : "▼"} {Math.abs(indicators.hormuzTrafficChange).toFixed(0)}%
          </span>
        </div>
        <div style={{ fontSize: 20, fontWeight: 700 }}>{indicators.hormuzTraffic} vessels/day</div>
      </div>

      {/* Bypass */}
      <div style={{ background: "#1e293b", borderRadius: 8, padding: 12, marginBottom: 8 }}>
        <div style={{ display: "flex", justifyContent: "space-between" }}>
          <span style={{ color: "#94a3b8", fontSize: 11 }}>Pipeline Bypass</span>
          <span style={{ color: "#22c55e", fontSize: 11 }}>
            {indicators.bypassUtilization > 0 ? "▲ Active" : "Standby"}
          </span>
        </div>
        <div style={{ fontSize: 20, fontWeight: 700 }}>{(indicators.bypassUtilization / 1e6).toFixed(1)}M bbl/d</div>
        <div style={{ color: "#94a3b8", fontSize: 11 }}>of {(indicators.bypassCapacity / 1e6).toFixed(1)}M capacity</div>
      </div>

      {/* Escalation */}
      <div style={{ background: "#1e293b", borderRadius: 8, padding: 12, marginBottom: 16 }}>
        <span style={{ color: "#94a3b8", fontSize: 11 }}>Escalation Index</span>
        <div style={{ display: "flex", gap: 3, marginTop: 8 }}>
          {escalationColors.map((_, i) => (
            <div
              key={i}
              style={{
                flex: 1,
                height: 6,
                borderRadius: 2,
                background: i <= indicators.escalationLevel ? escalationColors[i] : "#334155",
              }}
            />
          ))}
        </div>
      </div>

      {/* GDELT Feed */}
      <div style={{ color: "#94a3b8", fontSize: 11, textTransform: "uppercase", letterSpacing: 1, marginBottom: 8 }}>
        GDELT Feed
      </div>
      {events.slice(0, 10).map((e, i) => (
        <div key={i} style={{ fontSize: 12, padding: "6px 0", borderBottom: "1px solid #1e293b" }}>
          <span style={{ color: "#f59e0b" }}>{new Date(e.timestamp).toLocaleTimeString()}</span>{" "}
          {e.summary}
        </div>
      ))}
    </div>
  );
}
```

- [ ] **Step 3: Create PredictionCards component**

```tsx
// frontend/src/components/PredictionCards.tsx
import type { Prediction } from "../types";

interface Props {
  predictions: Prediction[];
}

export function PredictionCards({ predictions }: Props) {
  return (
    <div>
      <div style={{ color: "#94a3b8", fontSize: 11, textTransform: "uppercase", letterSpacing: 1, marginBottom: 8 }}>
        Active Predictions ({predictions.length})
      </div>
      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(140px, 1fr))", gap: 6 }}>
        {predictions.map((p) => {
          const dirColor = p.direction === "increase" ? "#ef4444" : p.direction === "decrease" ? "#22c55e" : "#94a3b8";
          return (
            <div key={p.predictionId} style={{ background: "#1e293b", borderRadius: 6, padding: 8, fontSize: 11 }}>
              <div style={{ color: "#94a3b8" }}>{p.predictionType.replace(/_/g, " ")}</div>
              <div style={{ color: dirColor, fontWeight: 600 }}>
                {p.magnitudeRange[0]}-{p.magnitudeRange[1]}% {p.direction === "increase" ? "▲" : "▼"}
              </div>
              <div style={{ color: "#475569", fontSize: 10 }}>
                conf: {p.confidence.toFixed(2)} | {p.timeframe}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
```

- [ ] **Step 4: Verify it builds**

Run: `cd frontend && npm run build`
Expected: Build succeeds

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/
git commit -m "feat: agent feed, live indicators, and prediction cards components"
```

---

## Task 20: Wire Frontend to Backend

**Files:**
- Modify: `frontend/src/App.tsx`

- [ ] **Step 1: Update App.tsx to connect everything**

Replace the entire `App.tsx` content:

```tsx
// frontend/src/App.tsx
import { useState, useCallback } from "react";
import { useWebSocket } from "./hooks/useWebSocket";
import { useHexData } from "./hooks/useHexData";
import { HexMap } from "./components/HexMap";
import { AgentFeed } from "./components/AgentFeed";
import { LiveIndicators } from "./components/LiveIndicators";
import { PredictionCards } from "./components/PredictionCards";
import type { AgentDecisionMsg, IndicatorUpdate, Prediction, WsMessage } from "./types";

const WS_URL = import.meta.env.VITE_WS_URL ?? "ws://localhost:8000/ws";

export default function App() {
  const [decisions, setDecisions] = useState<AgentDecisionMsg[]>([]);
  const [indicators, setIndicators] = useState<IndicatorUpdate | null>(null);
  const [predictions] = useState<Prediction[]>([]);
  const [events, setEvents] = useState<Array<{ summary: string; timestamp: string }>>([]);
  const { updateCells, getData, revision } = useHexData();

  const handleMessages = useCallback(
    (msgs: WsMessage[]) => {
      for (const msg of msgs) {
        switch (msg.type) {
          case "cell_update":
            updateCells(msg.cells);
            break;
          case "agent_decision":
            setDecisions((prev) => [msg.decision, ...prev].slice(0, 100));
            break;
          case "indicator_update":
            setIndicators(msg.indicators);
            break;
          case "event":
            setEvents((prev) => [msg.event, ...prev].slice(0, 50));
            break;
        }
      }
    },
    [updateCells]
  );

  useWebSocket(WS_URL, handleMessages);

  return (
    <div
      style={{
        display: "grid",
        gridTemplateColumns: "280px 1fr 320px",
        gridTemplateRows: "48px 1fr 180px",
        height: "100vh",
        background: "#0a0e1a",
        color: "#e2e8f0",
        fontFamily: "system-ui, -apple-system, sans-serif",
      }}
    >
      <header
        style={{
          gridColumn: "1 / -1",
          background: "#0f1629",
          padding: "0 16px",
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          borderBottom: "1px solid #1e293b",
        }}
      >
        <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
          <span style={{ color: "#60a5fa", fontWeight: 700, fontSize: 15 }}>PARALLAX</span>
          <span style={{ fontSize: 12, color: "#f59e0b" }}>LIVE</span>
          <span style={{ fontSize: 12, color: "#94a3b8" }}>Iran/Hormuz Scenario</span>
        </div>
      </header>

      <aside style={{ background: "#0f1629", padding: 12, overflowY: "auto", borderRight: "1px solid #1e293b" }}>
        <AgentFeed decisions={decisions} />
      </aside>

      <main style={{ background: "#0a0e1a" }}>
        <HexMap getData={getData} revision={revision} />
      </main>

      <aside style={{ background: "#0f1629", padding: 12, overflowY: "auto", borderLeft: "1px solid #1e293b" }}>
        <LiveIndicators indicators={indicators} events={events} />
      </aside>

      <footer
        style={{
          gridColumn: "1 / -1",
          background: "#0f1629",
          padding: 12,
          borderTop: "1px solid #1e293b",
        }}
      >
        <PredictionCards predictions={predictions} />
      </footer>
    </div>
  );
}
```

- [ ] **Step 2: Verify it builds**

Run: `cd frontend && npm run build`
Expected: Build succeeds

- [ ] **Step 3: Commit**

```bash
git add frontend/src/App.tsx
git commit -m "feat: wire frontend components to WebSocket data flow"
```

---

## Task 21: Integration Test — End-to-End Tick

**Files:**
- Create: `backend/tests/test_integration.py`

- [ ] **Step 1: Write the integration test**

```python
# backend/tests/test_integration.py
import asyncio
import duckdb
import pytest
from parallax.db.schema import create_tables
from parallax.db.writer import DbWriter
from parallax.simulation.config import ScenarioConfig
from parallax.simulation.world_state import WorldState
from parallax.simulation.cascade import CascadeEngine
from parallax.simulation.circuit_breaker import CircuitBreaker
from parallax.simulation.engine import SimulationEngine, SimEvent
from parallax.agents.router import AgentRouter
from parallax.agents.registry import AgentRegistry
from parallax.ingestion.gdelt import volume_gate


@pytest.fixture
def db():
    conn = duckdb.connect(":memory:")
    conn.execute("INSTALL spatial; LOAD spatial;")
    conn.execute("INSTALL h3 FROM community; LOAD h3;")
    create_tables(conn)
    yield conn
    conn.close()


@pytest.fixture
def config():
    return ScenarioConfig(
        name="test",
        description="test",
        tick_duration_minutes=15,
        hormuz_daily_flow=20_000_000,
        saudi_eastwest_pipeline_capacity=5_000_000,
        uae_habshan_fujairah_capacity=1_500_000,
        total_bypass_capacity_min=3_500_000,
        total_bypass_capacity_max=6_500_000,
        hormuz_to_europe_via_suez_nm=6300,
        cape_reroute_nm=11600,
        reroute_transit_days_min=10,
        reroute_transit_days_max=14,
        max_escalation_per_tick=1,
        escalation_cooldown_ticks=3,
        exogenous_shock_goldstein_threshold=8.0,
        oil_price_floor=30.0,
        oil_price_ceiling=200.0,
        daily_budget_cap_usd=20.0,
        sub_actor_max_input_tokens=4000,
        sub_actor_max_output_tokens=500,
        country_agent_max_input_tokens=8000,
        country_agent_max_output_tokens=1000,
        sub_actor_cooldown_minutes=30,
        country_agent_cooldown_minutes=60,
        snapshot_interval_ticks=100,
        delta_retention_days=30,
    )


@pytest.mark.asyncio
async def test_full_tick_cycle(db, config):
    """Simulate one tick: event arrives, cascade applies, state persists."""
    ws = WorldState()
    # Seed a Hormuz cell with flow
    ws.update_cell(612345678, flow=20_000_000.0, status="open", influence="iran")
    ws.advance_tick()

    cascade = CascadeEngine(config)
    cb = CircuitBreaker(
        max_per_tick=config.max_escalation_per_tick,
        cooldown_ticks=config.escalation_cooldown_ticks,
        shock_threshold=config.exogenous_shock_goldstein_threshold,
    )
    writer = DbWriter(db)
    writer_task = asyncio.create_task(writer.run())

    # Simulate a blockade event
    effects = cascade.apply_blockade(ws, cell_id=612345678, reduction_pct=0.5)
    assert effects["supply_loss"] == 10_000_000.0

    # Price shock
    new_price = cascade.compute_price_shock(
        current_price=80.0,
        supply_loss=effects["supply_loss"],
        bypass_active=config.total_bypass_capacity_min,
    )
    assert new_price > 80.0

    # Persist delta
    ws.advance_tick()
    deltas = ws.flush_deltas()
    for d in deltas:
        await writer.enqueue(
            "INSERT INTO world_state_delta (cell_id, tick, influence, threat_level, flow, status) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            [d["cell_id"], d["tick"], d["influence"], d["threat_level"], d["flow"], d["status"]],
        )

    await asyncio.sleep(0.1)
    writer.stop()
    await writer_task

    # Verify persistence
    rows = db.execute("SELECT * FROM world_state_delta").fetchall()
    assert len(rows) == 1
    assert rows[0][4] == 10_000_000.0  # flow column


@pytest.mark.asyncio
async def test_gdelt_event_routes_to_agents():
    """GDELT event mentioning IRGC should route to Iran sub-actors."""
    event = {
        "NumMentions": 5,
        "NumSources": 3,
        "Actor1Name": "IRGC",
        "Actor2Name": "USA",
        "summary": "IRGC deploys naval assets near Hormuz",
        "relevance_score": 0.8,
    }

    # Stage 1: volume gate
    assert volume_gate(event, check_entity_override=True) is True

    # Stage: routing
    router = AgentRouter(AgentRegistry())
    agents = router.route(event)
    agent_ids = [a.agent_id for a in agents]

    assert any("iran/" in aid for aid in agent_ids)
    assert any("usa/" in aid for aid in agent_ids)
```

- [ ] **Step 2: Run integration test**

Run: `cd backend && pytest tests/test_integration.py -v`
Expected: All 2 tests PASS

- [ ] **Step 3: Commit**

```bash
git add backend/tests/test_integration.py
git commit -m "feat: integration test covering full tick cycle and event routing"
```

---

## Task 22: Gitignore + Project Cleanup

**Files:**
- Create: `.gitignore`
- Create: `frontend/.env.example`
- Create: `backend/.env.example`

- [ ] **Step 1: Create .gitignore**

```
# Python
__pycache__/
*.pyc
*.egg-info/
.venv/
dist/

# Node
node_modules/
frontend/dist/

# DuckDB
*.duckdb
*.duckdb.wal

# Environment
.env
.env.local

# IDE
.idea/
.vscode/
*.swp

# OS
.DS_Store

# Superpowers brainstorm sessions
.superpowers/

# sentence-transformers model cache
.cache/
```

- [ ] **Step 2: Create env examples**

```bash
# backend/.env.example
ANTHROPIC_API_KEY=sk-ant-...
GOOGLE_APPLICATION_CREDENTIALS=/path/to/bigquery-key.json
EIA_API_KEY=your-eia-key
PARALLAX_ADMIN_PASSWORD=change-me
PARALLAX_INVITE_SEED=change-me
DUCKDB_PATH=./parallax.duckdb
```

```bash
# frontend/.env.example
VITE_WS_URL=ws://localhost:8000/ws
VITE_API_URL=http://localhost:8000
```

- [ ] **Step 3: Commit**

```bash
git add .gitignore frontend/.env.example backend/.env.example
git commit -m "chore: gitignore, env examples, project cleanup"
```

---

## Summary

**22 tasks, ~60 commits** covering:

- Tasks 1-2: DuckDB schema + single-writer DB layer
- Tasks 3-5: Scenario config, H3 spatial utils, world state with delta tracking
- Tasks 6-8: Cascade rules, circuit breaker, DES engine
- Tasks 9-10: GDELT ingestion with 4-stage filter and semantic dedup
- Tasks 11-13: Agent registry (50 agents), router, runner with budget tracking
- Tasks 14-15: Eval framework (predictions, scoring, prompt versioning)
- Task 16: FastAPI backend with WebSocket, auth, REST endpoints
- Tasks 17-20: React frontend with deck.gl hex map, agent feed, indicators, predictions
- Task 21: End-to-end integration test
- Task 22: Project cleanup

**Not yet covered (follow-up tasks after MVP works end-to-end):**
- Agent prompt authoring (the ~50 individual YAML prompt files with historical baselines)
- Spatial data loading script (Overture Maps + Searoute → DuckDB)
- Oil price fetcher (EIA/FRED API integration)
- Eval cron loop (daily scoring + prompt improvement pipeline)
- Replay mode implementation
- Deployment configuration (Fly.io/Railway + Vercel)
- Golden demo state generation
