# Codebase Concerns

**Analysis Date:** 2026-03-30

## Tech Debt

**Bare Exception Handling in Database Writer:**
- Issue: Catch-all `except Exception` clause logs errors but swallows them, preventing proper error propagation or circuit breaker activation
- Files: `backend/src/parallax/db/writer.py` (line 45-46)
- Impact: Failed database writes go undetected at the application level. Simulation can continue with stale state without alerting operators. Lost data from failed inserts into critical tables like `decisions`, `predictions`, `world_state_delta`.
- Fix approach: Replace with specific exception handling. Re-raise critical errors after logging, or implement a failed_writes queue for retry/alerting. Track write failures as a metric.

**Implicit State Coupling in WorldState:**
- Issue: `WorldState` tracks dirty cells in memory but has no validation that flushed deltas are actually persisted before accepting new updates
- Files: `backend/src/parallax/simulation/world_state.py` (lines 61-74)
- Impact: If `DbWriter` silently fails, in-memory state diverges from persisted state. Long-running simulations will accumulate divergence and checkpoint/restore operations will use corrupted state from snapshots.
- Fix approach: Add an async confirmation mechanism where `flush_deltas()` only clears dirty set after receiving write confirmation. Consider transaction IDs or callbacks from `DbWriter`.

**Lack of Primary Key Constraints in World State Delta:**
- Issue: `world_state_delta` table has no primary key, allowing duplicate updates for same (cell_id, tick) pair
- Files: `backend/src/parallax/db/schema.py` (lines 5-15)
- Impact: Replay/reconstruction queries can produce incorrect results if cascade rules or other code issues duplicate writes. Query `get_world_state_at_tick()` applies deltas in order but duplicates overwrite each other unpredictably.
- Fix approach: Add `PRIMARY KEY (cell_id, tick)` or use `UNIQUE` constraint with `ON CONFLICT REPLACE` strategy. Validate no duplicates exist in current data.

**Hardcoded Cascade Parameters Not Fully Config-Driven:**
- Issue: `PRICE_ELASTICITY = 3.0` and `INSURANCE_THREAT_MULTIPLIER = 5.0` are hardcoded in `CascadeEngine` instead of loaded from `ScenarioConfig`
- Files: `backend/src/parallax/simulation/cascade.py` (lines 35, 38)
- Impact: Cannot tune cascade behavior across different scenarios without code changes. Scenario config is incomplete, reducing reproducibility and experiment isolation.
- Fix approach: Add `price_elasticity: float` and `insurance_threat_multiplier: float` fields to `ScenarioConfig` dataclass and load them in `CascadeEngine.__init__()`.

## Known Bugs

**Snapshot Reconstruction Missing Empty Cells:**
- Issue: `get_world_state_at_tick()` only returns cells that exist in snapshot or subsequent deltas, not cells that were open but unmodified
- Files: `backend/src/parallax/db/queries.py` (lines 20-68)
- Trigger: Run simulation for 50 ticks, create snapshot at tick 25, query world state at tick 40. Only modified cells appear, not the full grid.
- Workaround: Keep full snapshots at every tick (expensive) or track all initialized cells separately.
- Fix approach: Maintain a `world_state_cells_initialized` or equivalent table tracking all valid cell IDs, then left-join against it to fill missing cells with defaults.

**Circuit Breaker Records Escalation But Doesn't Prevent Multi-Tick Same-Agent:**
- Issue: `allow_escalation()` checks cooldown but doesn't prevent multiple escalations *within the same tick* from the same agent
- Files: `backend/src/parallax/simulation/circuit_breaker.py` (lines 25-58)
- Trigger: Call `allow_escalation("agent_a", levels=1, tick=10)` twice — both return True; record only once, second call should be blocked.
- Workaround: Enforce single escalation per agent per tick at the caller level (not in circuit breaker).
- Fix approach: Add per-agent, per-tick escalation counter: `_escalations_this_tick: dict[str, int]`. Reset at tick boundary. Reject if counter >= max_per_tick.

## Security Considerations

**DuckDB File Persistence Without Access Control:**
- Risk: DuckDB database file written to `DUCKDB_PATH=/app/data/parallax.duckdb` (from docker-compose.yml) with no table-level or row-level access control
- Files: `docker-compose.yml` (line 9), `backend/src/parallax/db/schema.py`
- Current mitigation: Deployed in private Docker network; no exposed endpoints documented for database access
- Recommendations:
  - Add role-based access control (RBAC) at the application layer; validate user identity before query operations
  - Encrypt sensitive fields in `curated_events`, `agent_memory` at rest using DuckDB's encryption (if available in v1.2+) or application-level encryption
  - Audit logging for all mutations to `decisions`, `predictions` tables (agent decision audit trail)
  - Restrict file permissions on the DuckDB file to owner-read-only in deployment

**Missing Input Validation on Config Paths:**
- Risk: `load_scenario_config()` accepts a `Path` argument with no validation; could load arbitrary YAML from user-supplied paths
- Files: `backend/src/parallax/simulation/config.py` (line 55)
- Current mitigation: Config path hard-coded in tests; not exposed via API
- Recommendations:
  - Restrict config loading to a whitelisted directory (e.g., `/app/config/scenarios/`)
  - Validate config file exists and is readable before opening
  - Use `yaml.safe_load()` (currently used — good) but also validate schema with Pydantic validation in `load_scenario_config()`

**Secrets Exposed in Docker Compose:**
- Risk: `ANTHROPIC_API_KEY`, `GOOGLE_APPLICATION_CREDENTIALS`, `EIA_API_KEY`, `PARALLAX_ADMIN_PASSWORD`, `PARALLAX_INVITE_SEED` all in plaintext docker-compose.yml
- Files: `docker-compose.yml` (lines 11-14)
- Current mitigation: File is likely in `.gitignore`, not committed
- Recommendations:
  - Use Docker secrets or `.env` file (with `.env` in `.gitignore`)
  - Document required env vars in README with placeholder values
  - Consider Docker Compose V2 syntax with `.env.example` for safe defaults

## Performance Bottlenecks

**Lazy Deletion in SimulationEngine Causes Unbounded Memory Growth:**
- Problem: Cancelled events remain in `_cancelled` set indefinitely. Long simulations will accumulate thousands of cancelled event IDs.
- Files: `backend/src/parallax/simulation/engine.py` (lines 61, 80, 100)
- Cause: `_cancelled.discard(seq)` removes from set when popped, but if events are cancelled far in the future, set grows without bound.
- Improvement path: Implement periodic cleanup of `_cancelled` entries older than current_tick; add a max-retention policy (e.g., only keep last 10K ticks worth of cancellations).

**World State Snapshots Always Serialize Full Grid:**
- Problem: `snapshot()` method returns list of all cells, even if only 0.1% changed. Large grids (millions of H3 cells) will have expensive serialization.
- Files: `backend/src/parallax/simulation/world_state.py` (lines 76-86)
- Cause: No filtering; snapshot captures entire `_cells` dictionary
- Improvement path: Add optional `full=False` parameter; default to returning only `_dirty` cells plus necessary context for reconstruction.

**DuckDB Query Reconstruction Loads All Deltas:**
- Problem: `get_world_state_at_tick()` fetches all deltas between snapshot and target_tick into memory, applies sequentially. For 10K ticks of history, this is O(ticks) memory + O(ticks) iteration.
- Files: `backend/src/parallax/db/queries.py` (lines 49-66)
- Cause: No indexing on (cell_id, tick); no aggregation at database layer
- Improvement path: Add a `ROW_NUMBER()` window function in DuckDB to fetch only the latest state per cell; use SQL-level aggregation instead of application code.

## Fragile Areas

**Engine Event Handler Can Spawn Unbounded New Events:**
- Files: `backend/src/parallax/simulation/engine.py` (lines 181-190 test, event._engine_ref.schedule)
- Why fragile: Handler has direct access to engine via `_engine_ref`. Handlers can schedule events at tick 0, creating infinite loops or retroactive state mutations.
- Safe modification: Add guard in `schedule()` to reject events with `tick < current_tick`. Document handler contract: events must be >= current_tick.
- Test coverage: Only 1 test covers handler-initiated scheduling (`test_handler_can_schedule_new_events`); need tests for:
  - Retroactive scheduling (tick < current_tick) — should be rejected
  - Handler throws exception — should be caught and logged
  - Handler schedules thousands of events — should not deadlock

**Cascade Engine Applies Rules Statefully Without Rollback:**
- Files: `backend/src/parallax/simulation/cascade.py` (all methods mutate world state)
- Why fragile: Methods like `apply_blockade()` directly call `ws.update_cell()`. If a downstream rule fails, cell is already modified with no rollback mechanism.
- Safe modification: Return delta objects instead of mutating directly; caller assembles full transaction before applying. Or implement explicit rollback method.
- Test coverage: Only forward-path tests; missing:
  - Partial failure scenarios (e.g., price calculation fails after blockade applied)
  - Overlapping blockades on same cell
  - Negative flows resulting from incorrect bypass calculation

**CircuitBreaker Doesn't Persist State Across Restarts:**
- Files: `backend/src/parallax/simulation/circuit_breaker.py` (lines 23, 60-62)
- Why fragile: `_last_escalation` dict lives in memory only. If process restarts, cooldown timer resets, allowing immediate re-escalation.
- Safe modification: Add optional callback to record escalations to database, restore on initialization.
- Test coverage: Missing restart scenario test.

## Scaling Limits

**In-Memory WorldState Cannot Scale Beyond RAM:**
- Current capacity: All cells kept in `_cells` dict. A global 1-million-cell grid at 100 bytes per cell = ~100MB. Manageable for development; untested for production.
- Limit: Will hit memory pressure around 10M cells or 1GB of state data. Beyond that, performance degrades.
- Scaling path:
  - Move to event-sourced model where only recent deltas live in memory; older snapshots queried from database
  - Implement page-out for cells not modified in last N ticks
  - Consider partitioning by geospatial region if simulation supports subregion isolation

**Single-Writer DbWriter Queue Not Horizontal:**
- Current capacity: Single asyncio.Queue processes writes serially. If write latency is 10ms and simulation generates 1000 deltas/tick, queue backs up after ~100 ticks in real-time mode.
- Limit: CPU-bound simulation can outpace database writes; queue grows unbounded until memory exhaustion.
- Scaling path:
  - Batch writes (INSERT 100 deltas in 1 statement) — should reduce write count by 90%
  - Add multiple writers with row-range partitioning (writer1 handles cell_id 0-50M, writer2 handles 50M-100M)
  - Move to async batch writes with bounded queue depth; drop or compress old deltas if queue exceeds threshold

**Configuration Reload Requires Process Restart:**
- Current capacity: ScenarioConfig loaded at startup; no ability to hot-reload or A/B test parameter changes mid-simulation
- Limit: Cannot adjust cascade parameters without stopping simulation
- Scaling path: Add endpoint to load new config, validate against running state, apply prospectively to future events only. Store config versions in database for audit.

## Dependencies at Risk

**H3 Spatial Library Pinned to v4.1:**
- Risk: H3 is actively maintained but major version boundaries could break `lat_lng_to_cell()` signatures
- Files: `backend/pyproject.toml` (line 9: `h3>=4.1`)
- Impact: If H3 releases v5.0 with breaking changes and someone runs `pip install h3>=4.1`, app breaks silently
- Migration plan:
  - Constrain to `h3>=4.1,<5.0` to prevent automatic major upgrades
  - Create integration tests that validate H3 cell conversions against known coordinates
  - Document expected behavior for edge cases (poles, date line)

**Anthropic SDK Version Open-Ended:**
- Risk: `anthropic>=0.52` allows any future version; API changes could break model calls
- Files: `backend/pyproject.toml` (line 10)
- Impact: If Anthropic API changes token counting or response schemas, agent modules break
- Migration plan: Constrain to `anthropic>=0.52,<1.0` or pin to specific minor version. Add integration tests against real API to catch version incompatibilities before deployment.

**DuckDB Pre-Release Dependency:**
- Risk: Version 1.2 is not marked stable in all package managers; could have undiagnosed data corruption or query bugs
- Files: `backend/pyproject.toml` (line 8: `duckdb>=1.2`)
- Impact: Edge case bugs in snapshot reconstruction or delta application could cause silent state divergence
- Migration plan:
  - Monitor DuckDB releases; pin to latest stable point release (e.g., `1.2.7`) once released
  - Run full test suite + property-based tests on snapshot/delta reconstruction before upgrading

## Missing Critical Features

**No State Consistency Checker:**
- Problem: Cannot verify at runtime that in-memory world state matches persisted deltas + snapshots
- Blocks: Detecting silent data corruption, diagnosing divergence after infrastructure failures
- Recommended solution: Add `verify_consistency()` method that reconstructs state from DB and compares with in-memory state. Run on every simulation save/load cycle or every N ticks.

**No Event Replay/Undo for Simulation:**
- Problem: Cannot rewind simulation to a previous tick to test alternate cascade paths
- Blocks: Offline analysis, scenario testing, counterfactual simulations
- Recommended solution: Store complete event journal in DB; implement `rewind_to_tick(target)` that restores snapshot and replays events up to target with optional handler override for what-if analysis.

**No Structured Logging for Cascade Decision Chain:**
- Problem: Cascade rules execute but no audit trail of which rule triggered, what values were used, what changed
- Blocks: Debugging why a price shock occurred; validating cascade logic is correct for a given scenario
- Recommended solution: Add structured logging (JSON) at each cascade rule entry/exit with inputs, outputs, intermediate values. Log to separate table for querying.

**No Dead Letter Queue for Failed Writes:**
- Problem: Failed `DbWriter` inserts are logged but lost
- Blocks: Recovering from transient database issues without losing data
- Recommended solution: Add secondary in-memory queue for failed writes with exponential backoff retry. Persist to disk if queue exceeds size threshold.

## Test Coverage Gaps

**Engine Clock Modes Incomplete:**
- What's not tested: LIVE mode behavior with actual asyncio task cancellation; engine behavior when handler takes longer than tick_duration
- Files: `backend/tests/test_engine.py` (lines 154-177)
- Risk: LIVE mode simulation could skip ticks or hang if handler is slow
- Priority: High — LIVE mode is user-facing feature

**Cascade Rule Ordering Undefined:**
- What's not tested: What happens if two cascade rules modify the same cell in the same tick? Who wins? Is the order deterministic?
- Files: `backend/src/parallax/simulation/cascade.py` (all methods)
- Risk: Non-deterministic simulation outcomes across runs
- Priority: High — fundamental to reproducibility

**World State Concurrent Modification:**
- What's not tested: What if handler calls `update_cell()` while `flush_deltas()` is iterating `_dirty`?
- Files: `backend/src/parallax/simulation/world_state.py`
- Risk: Race condition; lost updates or corrupted deltas under async stress
- Priority: Medium — unlikely in single-threaded context but possible with parallel handlers

**Config Validation Missing:**
- What's not tested: Invalid config values (negative prices, zero flow, missing fields)
- Files: `backend/src/parallax/simulation/config.py`
- Risk: Bad configs silently propagate invalid assumptions through cascade rules
- Priority: Medium — mostly caught by type checking but no semantic validation

**Database Connection Failures:**
- What's not tested: What happens when DuckDB connection is severed mid-simulation? What if a table is dropped?
- Files: `backend/src/parallax/db/writer.py`
- Risk: Silent data loss; simulation continues with stale state
- Priority: High — must handle gracefully in production

---

*Concerns audit: 2026-03-30*
