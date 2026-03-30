# Coding Conventions

**Analysis Date:** 2026-03-30

## Naming Patterns

**Files:**
- Lowercase with underscores: `engine.py`, `circuit_breaker.py`, `h3_utils.py`
- Test files follow pattern: `test_<module>.py`
- Module names match concept names (e.g., `cascade.py` for cascade logic)

**Functions:**
- Snake case: `apply_blockade()`, `compute_price_shock()`, `lat_lng_to_cell_for_zone()`
- Descriptive verb-first pattern: `get_`, `compute_`, `apply_`, `activate_`, `allow_`, `record_`
- Private methods prefixed with `_`: `_handler`, `_queue`, `_cells`

**Variables:**
- Snake case for all variables: `cell_id`, `supply_loss`, `threat_level`, `bypass_flow`
- Descriptive names preferred over abbreviations: `shock_threshold` not `sthresh`
- Collection suffixes indicate plurals: `dependencies`, `deltas`, `cells`, `coords`

**Types & Classes:**
- PascalCase for classes: `SimulationEngine`, `CascadeEngine`, `WorldState`, `CircuitBreaker`
- PascalCase for enums: `ClockMode`, `ResolutionBand`
- Frozen dataclasses used for immutable value types: `@dataclass(frozen=True)`

**Constants:**
- SCREAMING_SNAKE_CASE for module-level constants: `PRICE_ELASTICITY`, `RESOLUTION_BANDS`

## Code Style

**Formatting:**
- No explicit formatter configured (no `.prettierrc`, `.black`, `pyproject.toml [tool.black]`)
- Style is clean and consistent: 4-space indentation, PEP 8 compliant
- Line length appears to follow standard conventions (~100-120 chars)

**Linting:**
- No explicit linter configuration detected
- Code follows Python idioms: type hints, docstrings, clean imports
- Type hints present throughout: `def schedule(self, event: SimEvent) -> int:`

**Docstring Style:**
- Module-level docstrings at file head: `"""Discrete Event Simulation (DES) engine."""`
- Function docstrings with Args/Returns when helpful (especially for public APIs)
- Example: `cascade.py` includes detailed docstrings explaining the cascade chain
- Concise docstrings for obvious methods; detailed for complex logic

## Import Organization

**Order:**
1. Standard library imports: `import asyncio`, `import heapq`, `from dataclasses import dataclass`
2. Third-party imports: `import duckdb`, `import h3`, `from pydantic import BaseModel`
3. Local imports: `from parallax.simulation.config import ScenarioConfig`

**Path Aliases:**
- Absolute imports from package root: `from parallax.simulation.config import...`
- No relative imports (no `from ..config import`)
- Imports are explicit, not wildcard: `from dataclasses import dataclass, field`

## Error Handling

**Patterns:**
- Defensive checks return default values rather than raising: `if cell is None: return None`
- Example: `apply_blockade()` returns `{"supply_loss": 0.0}` for nonexistent cells
- Async errors logged via logger: `logger.exception("DB write failed: %s", op.sql[:100])`
- No try-except at function boundary unless needed for recovery

**Logging:**
- Standard `logging` module: `logger = logging.getLogger(__name__)`
- Log exceptions at ERROR level: `logger.exception()` for failures
- Partial info in logs (SQL[:100]) to avoid logging huge payloads

## Comments

**When to Comment:**
- Block comments explain design decisions (e.g., "Lazy deletion: cancelled events are marked...")
- Inline comments rare; code is self-documenting via naming
- Comments appear in docstrings at module and class level, not scattered

**JSDoc/TSDoc:**
- Python uses docstrings, not JSDoc
- Multi-line docstrings follow format: description, then blank line, then Args/Returns/Raises
- Example from `cascade.py`:
  ```python
  def apply_blockade(self, ws: WorldState, cell_id: int, reduction_pct: float) -> dict:
      """Apply a blockade to a cell, reducing its flow.

      Args:
          ws: Current world state.
          cell_id: H3 cell to blockade.
          reduction_pct: Fraction of flow to remove (0.0 to 1.0).

      Returns:
          Dict with 'supply_loss' indicating barrels/day lost.
      """
  ```

## Function Design

**Size:**
- Functions are focused and single-purpose
- Most functions under 30 lines; longest about 50 lines
- Complex logic broken into named steps (e.g., `compute_downstream_effects` has clear phases)

**Parameters:**
- Named parameters preferred over positional: `CascadeEngine(config=config_obj)`
- Optional parameters use defaults: `tick_duration_seconds: float = 900.0`
- Type hints on all parameters: `def __init__(self, conn: duckdb.DuckDBPyConnection)`

**Return Values:**
- Single return type (no union of different structures)
- Dicts used for structured returns with consistent keys: `{"supply_loss": 0.0}`
- Falsy returns for "not found": `None` for missing cell, `False` for queue empty

## Module Design

**Exports:**
- All public classes/functions defined at module level
- Private utilities prefixed with `_` (Python convention)
- No `__all__` declarations; rely on naming convention

**Barrel Files:**
- `__init__.py` files empty or minimal
- Import from specific modules: `from parallax.simulation.engine import SimulationEngine`

## Domain-Specific Patterns

**Dataclass Usage:**
- Frozen dataclasses for immutable configs: `@dataclass(frozen=True) class ScenarioConfig`
- Mutable dataclasses for state: `@dataclass class CellState`
- Field factories for defaults: `payload: dict[str, Any] = field(default_factory=dict)`

**Async Patterns:**
- All DB operations and simulation engine use async/await
- Handlers are async callbacks: `async def handler(event: SimEvent): ...`
- Queue operations: `await self._queue.put()` and `await self._queue.get()`

**Type Hints:**
- Union types use `|` syntax (Python 3.10+): `str | None` not `Optional[str]`
- Dict keys/values typed: `dict[str, float]`, `dict[int, CellState]`
- Full signature typing: `Callable[[SimEvent], Awaitable[None]]`

---

*Convention analysis: 2026-03-30*
