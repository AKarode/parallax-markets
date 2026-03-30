# Testing Patterns

**Analysis Date:** 2026-03-30

## Test Framework

**Runner:**
- pytest 8.3 - `backend/pyproject.toml` specifies `pytest>=8.3,<9`
- Config: `backend/pytest.ini` with:
  - `asyncio_mode = auto` (automatic async test detection)
  - `testpaths = tests` (test discovery in `backend/tests/` directory)

**Assertion Library:**
- pytest's built-in assertions (no additional libraries)
- Simple `assert` statements: `assert processed == [1, 2, 3]`

**Run Commands:**
```bash
pytest                           # Run all tests
pytest -v                        # Verbose output
pytest backend/tests/            # Run backend tests only
pytest -k "test_engine"          # Run tests matching pattern
pytest --asyncio-mode auto       # For async tests (auto-enabled via pytest.ini)
```

## Test File Organization

**Location:**
- Co-located in dedicated `backend/tests/` directory (not alongside source)
- Mirrors module structure for readability
- Example: `backend/src/parallax/simulation/engine.py` → `backend/tests/test_engine.py`

**Naming:**
- Test files: `test_<module_name>.py`
- Test functions: `test_<specific_behavior>()`
- Async test functions: marked with `@pytest.mark.asyncio`

**Structure:**
```
backend/tests/
├── conftest.py              # Shared fixtures
├── test_engine.py           # SimulationEngine tests (15 tests)
├── test_cascade.py          # CascadeEngine tests (11 tests)
├── test_circuit_breaker.py  # CircuitBreaker tests (11 tests)
├── test_writer.py           # DbWriter tests (3 async tests)
├── test_world_state.py      # WorldState tests (5 tests)
├── test_config.py           # Config loading tests (3 tests)
├── test_h3_utils.py         # H3 spatial tests (4 tests)
└── test_schema.py           # DB schema tests (3 tests)
```

## Test Structure

**Suite Organization:**
```python
# No test classes; tests are module-level functions
# Each test is independent and focused

def test_blockade_reduces_flow():
    config = _config()
    ws = WorldState()
    ws.update_cell(111, flow=20_000_000.0, status="open")
    ws.advance_tick()

    engine = CascadeEngine(config)
    effects = engine.apply_blockade(ws, cell_id=111, reduction_pct=0.5)

    cell = ws.get_cell(111)
    assert cell["flow"] == 10_000_000.0
    assert cell["status"] == "restricted"
    assert effects["supply_loss"] == 10_000_000.0
```

**Patterns:**
- **Setup:** Create objects and set state
- **Action:** Call the function under test
- **Assertion:** Verify outputs and state changes
- **No teardown:** DuckDB in-memory instances auto-cleanup; no manual cleanup needed

## Mocking

**Framework:**
- No mocking library used (no pytest-mock, unittest.mock imports detected)
- Tests use real objects instead

**Patterns - None explicit:**
- Real `WorldState` objects used in cascade tests
- Real `DuckDB` connections (in-memory) for DB tests
- Real async `asyncio.Queue` in writer tests

**What to Mock:**
- External APIs would be mocked (not present yet; no HTTP/Anthropic API calls in test code)

**What NOT to Mock:**
- Internal simulation objects (`WorldState`, `CascadeEngine`)
- Database operations (use in-memory DuckDB instead)
- Async queue behavior (real `asyncio.Queue`)

## Fixtures and Factories

**Test Data:**
```python
# From conftest.py
@pytest.fixture
def db():
    """In-memory DuckDB with extensions for testing."""
    conn = duckdb.connect(":memory:")
    conn.execute("INSTALL spatial; LOAD spatial;")
    conn.execute("INSTALL h3 FROM community; LOAD h3;")
    yield conn
    conn.close()
```

**Usage in Tests:**
```python
@pytest.mark.asyncio
async def test_writer_processes_single_write(db):  # db fixture auto-injected
    writer = DbWriter(db)
    # ... test code
```

**Helper Functions (not fixtures):**
- `_config()` in `test_cascade.py`: `return load_scenario_config(Path(__file__).parent.parent / "config" / "scenario_hormuz.yaml")`
- Repeated fixture, not pytest fixture (called directly)

**Location:**
- Fixtures in `backend/tests/conftest.py` (pytest auto-discovers)
- Helper functions in test modules as private functions with `_` prefix

## Coverage

**Requirements:**
- None enforced (no coverage configuration in pyproject.toml)
- Tests cover major paths but not 100% enforced

**View Coverage:**
```bash
pytest --cov=parallax --cov-report=html
```
(Requires `pytest-cov` dependency; not in current setup)

## Test Types

**Unit Tests:**
- Scope: Individual functions/methods in isolation
- Approach: Real objects, no mocks
- Examples:
  - `test_blockade_reduces_flow()` tests `CascadeEngine.apply_blockade()` in isolation
  - `test_monotonic_counter_tiebreaking()` tests event queue ordering
  - `test_reality_anchor_within_range()` tests `CircuitBreaker.reality_check()`

**Integration Tests:**
- Scope: Multi-component interactions
- Approach: Real objects working together
- Examples:
  - `test_full_cascade_chain()` tests blockade → bypass → price → downstream in sequence
  - `test_handler_can_schedule_new_events()` tests event scheduling during processing
  - `test_writer_processes_batch_of_writes()` tests queue + async processing + DB

**E2E Tests:**
- Not present in codebase
- No HTTP/API tests; no end-to-end scenario simulation tests
- Would be in Playwright browser tests (`.playwright-mcp/` detected but not analyzed here)

## Common Patterns

**Async Testing:**
```python
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
```

**Error Testing:**
```python
def test_blockade_nonexistent_cell():
    config = _config()
    ws = WorldState()
    engine = CascadeEngine(config)
    effects = engine.apply_blockade(ws, cell_id=999, reduction_pct=0.5)
    assert effects["supply_loss"] == 0.0  # Returns default, doesn't raise
```

**State Testing:**
```python
def test_update_cell_tracks_delta():
    ws = WorldState()
    ws.update_cell(123456, influence="iran", threat_level=0.5, status="patrolled")
    ws.advance_tick()

    cell = ws.get_cell(123456)
    assert cell["influence"] == "iran"  # State persisted

    deltas = ws.flush_deltas()
    assert len(deltas) == 1
    assert deltas[0]["cell_id"] == 123456  # Delta tracking works
    assert deltas[0]["tick"] == 1
```

**Parameterization:**
- Not used in current tests
- Could use `@pytest.mark.parametrize` for testing multiple inputs (not implemented)

## Test Statistics

**By Module:**
- `test_engine.py`: 15 tests (event queue, ordering, cancellation, timing modes)
- `test_cascade.py`: 11 tests (blockade, bypass, price, rerouting, insurance)
- `test_circuit_breaker.py`: 11 tests (escalation, cooldown, shocks, reality checks)
- `test_writer.py`: 3 async tests (single write, batch writes, queue depth)
- `test_world_state.py`: 5 tests (delta tracking, snapshots, state loading)
- `test_config.py`: 3 tests (config loading, derived properties)
- `test_h3_utils.py`: 4 tests (H3 cell mapping, route chains)
- `test_schema.py`: 3 tests (table creation, columns)

**Total:** 55 tests across 8 modules

## Known Testing Gaps

**Not Tested:**
- HTTP/API endpoints (no FastAPI test code found)
- External API integration (no Anthropic API mocking)
- Logging behavior (no assertion on log calls)
- Edge cases in large-scale simulations (performance/stress tests missing)

---

*Testing analysis: 2026-03-30*
