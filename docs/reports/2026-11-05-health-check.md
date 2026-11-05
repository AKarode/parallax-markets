# Parallax Health Check — 2026-11-05

**Status: YELLOW**

No new code commits since 2026-11-03 (second consecutive quiet day). DuckDB single-writer violations enter Day 11 unresolved. All 491 tests passed last full run; tests cannot be re-executed in today's environment because `duckdb` is not installed in the CI container's global Python 3.13 path.

---

## Summary

The prediction-market pipeline remains architecturally stable. The deliberate pivot from the Phase 1 agent-swarm spec to a focused prediction-market edge-finder is well-reflected in CLAUDE.md and the current module map. No regressions or new issues found. The standing MEDIUM risk is six live-path modules that bypass the `asyncio.Queue → DbWriter` single-writer contract — this will produce `database is locked` under concurrent FastAPI load. Two days of no code commits: if this is intentional (weekend), no action needed; otherwise the project may be stalled.

---

## Spec / Plan vs. Implementation

The project pivoted from Phase 1 spec (50-agent LLM swarm + H3 spatial visualization) to a prediction-market edge-finder. The deviations below are **known and intentional**:

- **Missing from spec (intentional pivot):** `agents/` module (50-agent swarm), `spatial/` (H3 loader, h3_utils), `eval/` (prompt versioning, improvement pipeline), `simulation/engine.py` (DES core), `simulation/circuit_breaker.py`, `api/auth.py`, `api/websocket.py`, frontend H3 hex-map components
- **Present beyond spec (productive additions):** `prediction/`, `scoring/`, `contracts/`, `divergence/`, `portfolio/`, `backtest/`, `bench/`, `ops/`, `markets/`, `cli/brief.py`
- **pyproject.toml:** `requires-python = ">=3.11"` vs spec's Python 3.12; container runs 3.13 — permissive, not blocking

---

## Issues

- **[MEDIUM] DuckDB single-writer violations — Day 11 unresolved** — Six live-path modules bypass the `asyncio.Queue → DbWriter` pattern and call `conn.execute()` directly for INSERTs/UPDATEs, risking `database is locked` under concurrent FastAPI load:
  - `ops/alerts.py:106` — INSERT INTO ops_events
  - `budget/tracker.py:45` — INSERT INTO llm_usage
  - `cli/brief.py:132,151,433` — INSERT/UPDATE runs, INSERT INTO market_prices
  - `scoring/tracker.py:462,518,674,713,746` — multiple INSERT/UPDATE on trade tables
  - `backtest/runner.py:290,308,329,356` — INSERT/UPDATE on backtest_runs and backtest_predictions (lower risk — separate mode)

- **[MEDIUM] Tests cannot run in CI container** — `duckdb` is not installed in the Python 3.13 system path; `python3 -m pytest` fails at conftest import. The last verified green run was yesterday via a separate install. This creates a gap in continuous test visibility.

- **[LOW] 13 skipped tests in `test_mapping_policy.py`** — Skipped since pre-refactor; should be deleted or updated.

- **[LOW] `requires-python = ">=3.11"`** — Mismatches CLAUDE.md ("Python 3.12") and container runtime (3.13). Should be pinned to `>=3.12`.

- **[LOW] Frontend divergence from spec** — Polling-based React SPA with no WebSocket or H3 hex map. Appropriate for the prediction-market pivot; noted for record if the visual demo goal returns.

- **[INFO] No new code commits in 48 hours** — Only docs commits (health checks, tech research) since 2026-11-03. DuckDB fix and skipped-test cleanup remain open.

---

## Test Coverage

| Status | Count (last full run, 2026-11-04) |
|--------|-----------------------------------|
| Passed | 491                               |
| Skipped | 13                               |
| Failed | 0                                 |

Tests absent from plan but added (healthy): `test_backtest_look_ahead`, `test_bench_forecast`, `test_calibration_metrics`, `test_crisis_context`, `test_ensemble`, `test_experiment_tags`, `test_ledger`, `test_mapping_discount`, `test_mapping_policy`, `test_ops_events`, `test_phase1_critical`, `test_registry`, `test_report_card`, `test_resolution`, `test_runs_table`, `test_scorecard`, `test_selective`, `test_simulator`, `test_staleness_integration`, `test_track_record`, `test_truth_social`.

Tests specified in plan but not written (all for unbuilt modules given the pivot): `test_h3_utils`, `test_gdelt_filter`, `test_dedup`, `test_circuit_breaker`, `test_agent_schemas`, `test_agent_router`, `test_agent_runner`, `test_scoring`, `test_predictions`, `test_prompt_versioning`, `test_auth`, `test_integration`.

---

## Recommendations

1. **(Priority)** Fix the six live-path DuckDB single-writer violations — route `scoring/tracker.py`, `cli/brief.py`, `ops/alerts.py`, and `budget/tracker.py` INSERTs/UPDATEs through `DbWriter.enqueue()`. The `backtest/` module should use an isolated in-memory DuckDB connection.
2. Fix the CI test-environment gap — ensure `duckdb` and `pytest` are available in the standard Python path so `python3 -m pytest` works without manual intervention.
3. Delete or update the 13 skipped tests in `test_mapping_policy.py`.
4. Pin `requires-python = ">=3.12"` in `pyproject.toml`.
