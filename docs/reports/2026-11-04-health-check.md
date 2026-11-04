# Parallax Health Check — 2026-11-04

**Status: YELLOW**

No new code commits since the last check (2026-11-03). All 491 tests pass (13 skipped). The DuckDB single-writer violation is on Day 10 unresolved.

---

## Summary

The prediction-market pipeline is architecturally stable. All 491 tests pass, 13 are intentionally skipped (pre-refactor assertions in `test_mapping_policy.py`). No regressions. The primary open risk is a MEDIUM concurrency hazard: six live-path modules write directly to DuckDB via `conn.execute()` outside the `asyncio.Queue → DbWriter` pattern, which will non-deterministically produce `database is locked` errors under concurrent FastAPI load.

---

## Spec / Plan vs. Implementation

The project deliberately pivoted from the Phase 1 spec (50-agent LLM swarm + H3 spatial visualization) to a focused prediction-market edge-finder. This is documented in CLAUDE.md and is architecturally coherent. The deviations below are **known and intentional**:

- **Missing from spec (intentional pivot):** `agents/` module (50-agent swarm), `spatial/` (H3 loader/h3_utils), `eval/` (prompt versioning, improvement pipeline), `simulation/engine.py`, `simulation/circuit_breaker.py`, `api/auth.py`, `api/websocket.py`, frontend H3 map components
- **Present beyond spec (productive additions):** `prediction/`, `scoring/`, `contracts/`, `divergence/`, `portfolio/`, `backtest/`, `bench/`, `ops/`, `markets/`
- **pyproject.toml:** `requires-python = ">=3.11"` vs spec's Python 3.12 — not blocking
- **Missing spec deps (correctly absent given pivot):** `h3`, `searoute`, `shapely`, `sentence-transformers`, `websockets`, `google-cloud-bigquery`

---

## Issues

- **[MEDIUM] DuckDB single-writer violations (Day 10 unresolved)** — Six live-path modules bypass the `asyncio.Queue → DbWriter` pattern and call `conn.execute()` directly for INSERT/UPDATE/DELETE:
  - `ops/alerts.py:106` — INSERT INTO ops_events
  - `budget/tracker.py:45` — INSERT INTO llm_usage
  - `cli/brief.py:132,151,433` — INSERT/UPDATE runs, INSERT INTO market_prices
  - `scoring/tracker.py:462,518,674,713,746` — multiple INSERT/UPDATE on trade tables
  - `backtest/runner.py:290,308,329,356` — INSERT/UPDATE on backtest_runs and backtest_predictions
  - Under concurrent FastAPI requests these will race and raise `database is locked`. The `backtest/` violations are lower risk (backtest is a separate mode), but `scoring/tracker.py` and `cli/brief.py` are on the live path.

- **[LOW] pyproject.toml `requires-python = ">=3.11"` but runtime uses Python 3.13** — CLAUDE.md says "Python 3.12", pyproject says >=3.11, and the container runs 3.13. The constraint is permissive enough to not block anything, but it misrepresents the tested version.

- **[LOW] 13 skipped tests** — All in `test_mapping_policy.py`, skipped because they test pre-refactor behavior. These should either be deleted or updated to reflect the current contract mapping logic.

- **[LOW] Frontend divergence from spec** — The dashboard runs a polling-based React SPA (no WebSocket, no H3 hex map) rather than the spec's three-panel deck.gl + MapLibre visualization. This is consistent with the prediction-market pivot and appropriate for the current phase, but the gap is wide if the visual demo goal is ever revisited.

- **[INFO] No new code commits in 24 hours** — Only a docs commit landed since the last health check. If this is deliberate (weekend/holiday), no action needed.

---

## Test Coverage

| Status | Count |
|--------|-------|
| Passed | 491   |
| Skipped | 13  |
| Failed | 0    |

Tests present but not in Phase 1 plan (healthy additions): `test_backtest_look_ahead`, `test_bench_forecast`, `test_calibration_metrics`, `test_crisis_context`, `test_ensemble`, `test_experiment_tags`, `test_ledger`, `test_mapping_discount`, `test_mapping_policy`, `test_ops_events`, `test_phase1_critical`, `test_registry`, `test_report_card`, `test_resolution`, `test_runs_table`, `test_scorecard`, `test_selective`, `test_simulator`, `test_staleness_integration`, `test_track_record`, `test_truth_social`.

Tests specified in plan but not yet written: `test_h3_utils`, `test_gdelt_filter`, `test_dedup`, `test_circuit_breaker`, `test_agent_schemas`, `test_agent_router`, `test_agent_runner`, `test_scoring`, `test_predictions`, `test_prompt_versioning`, `test_auth`, `test_budget_tracker` (now covered by `test_llm_usage`), `test_integration`. These are all for modules that were intentionally not built given the pivot.

---

## Recommendations

1. **Fix single-writer violations in live path** (`scoring/tracker.py`, `cli/brief.py`, `ops/alerts.py`, `budget/tracker.py`) — route their INSERTs/UPDATEs through `DbWriter.enqueue()`. The backtest module (`backtest/runner.py`) should use a separate in-memory DuckDB connection since it does not share the production DB.
2. **Delete or update the 13 skipped tests** in `test_mapping_policy.py` — they create false comfort in the coverage count.
3. **Pin `requires-python = ">=3.12"`** in pyproject.toml to match CLAUDE.md and the container runtime.
