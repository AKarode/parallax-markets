# Parallax Health Check — 2026-11-03

**Status: YELLOW**

No new code commits since the last report (2026-11-02). Only a single docs commit landed (`29edc66` — daily tech research). All carry-over issues from previous reports remain unresolved — the MEDIUM DuckDB single-writer violations are now on Day 9.

---

## Summary

The prediction-market pipeline is architecturally stable and all 491 tests pass (13 skipped — intentionally, for pre-refactor assertions in `test_mapping_policy.py`). No regressions were introduced. The primary risk remains the MEDIUM concurrency hazard: six live-path modules write directly to DuckDB via `conn.execute()` outside the `asyncio.Queue → DbWriter` pattern, which will non-deterministically raise `database is locked` under concurrent FastAPI load.

---

## Spec / Plan vs. Implementation

The project deliberately pivoted from the Phase 1 spec's 50-agent LLM swarm + H3 spatial visualization to a focused prediction-market edge-finder. This is documented in CLAUDE.md and is architecturally coherent. Deviations from spec:

- **Missing (intentional pivot):** `agents/` module (50-agent swarm), `spatial/` module (H3 loader/h3_utils), `eval/` module (prompt versioning, improvement pipeline), `api/auth.py`, `api/websocket.py`
- **Present beyond spec (productive additions):** `prediction/`, `scoring/`, `contracts/`, `divergence/`, `portfolio/`, `backtest/`, `bench/`, `ops/`
- **pyproject.toml:** `requires-python = ">=3.11"` vs spec's Python 3.12 — not blocking
- **Missing spec deps (correctly absent given pivot):** `h3`, `searoute`, `shapely`, `sentence-transformers`, `websockets`, `google-cloud-bigquery`

---

## Test Coverage

| Status | Count |
|--------|-------|
| Passed | 491 |
| Skipped | 13 (intentional — pre-refactor mapping_policy assertions) |
| Failed | 0 |
| Test files | 47 |

**Plan-expected tests now present:** `test_schema.py`, `test_writer.py`, `test_cascade.py`, `test_world_state.py`, `test_config.py`

**Plan-expected tests still absent** (acceptable given the pivot — no corresponding modules exist):
`test_h3_utils.py`, `test_gdelt_filter.py`, `test_dedup.py`, `test_circuit_breaker.py`, `test_agent_schemas.py`, `test_agent_router.py`, `test_agent_runner.py`, `test_scoring.py`, `test_predictions.py`, `test_prompt_versioning.py`, `test_auth.py`, `test_budget_tracker.py`, `test_integration.py`

---

## Issues Found

### [MEDIUM] DuckDB single-writer violations — Day 9 (carry-over, unchanged)

Six live-path modules write directly to DuckDB via `conn.execute()` or `_conn.execute()` outside the `asyncio.Queue → DbWriter` pattern. Under concurrent FastAPI requests, or when the CLI and API share the same `.duckdb` file simultaneously, these paths non-deterministically raise `database is locked`.

Confirmed violators (unchanged since 2026-10-26):

- `ops/alerts.py:106` — **highest risk; fires synchronously on every alert event, including error-path alerts**
- `scoring/ledger.py:225,256` — signal INSERT and UPDATE on every brief run
- `scoring/tracker.py:516,672,746` — trade position, order, fill INSERTs
- `budget/tracker.py:43` — LLM usage INSERT on every Claude call
- `scoring/prediction_log.py:81` — prediction INSERT per run
- `contracts/registry.py:105,114,198` — contract upsert and DELETE (called at startup seeding)

**Fix:** Route all live-path writes through `DbWriter.enqueue()`. The `DbWriter` class at `db/writer.py` is correctly implemented; it just needs passing into these modules at construction time (in `cli/brief.py` and `main.py`).

### [LOW] `streamlit` and `plotly` missing from `pyproject.toml` — Day 9 (carry-over)

`dashboard/app.py:16–17` imports both at module level. Neither appears in any dependency group in `pyproject.toml`. A fresh `pip install -e "."` on a clean environment raises `ModuleNotFoundError` when the dashboard is used.

**Fix:** Add `streamlit` and `plotly` to an optional `[project.optional-dependencies]` group (e.g., `dashboard = ["streamlit>=1.30", "plotly>=5.0"]`).

### [LOW] `simulation/` module incomplete (carry-over)

`simulation/engine.py` (DES core) and `simulation/circuit_breaker.py` were specified in the plan but never implemented. Only `cascade.py`, `config.py`, and `world_state.py` exist. The current `cli/brief.py` pipeline does not depend on the DES engine — this is an acceptable incomplete spec deliverable given the pivot, not a runtime bug.

---

## Recommendations

1. **[Day 9 — now overdue] Fix MEDIUM DuckDB writer violations.** Wire `DbWriter.enqueue()` into `ops/alerts.py`, `scoring/ledger.py`, `scoring/tracker.py`, `budget/tracker.py`, `scoring/prediction_log.py`. Pass the `DbWriter` instance at construction in `cli/brief.py` and `main.py`. This is mechanical — each write site replaces `conn.execute(sql, params)` with `await db_writer.enqueue(sql, params)`.

2. **Add `streamlit` and `plotly` to `pyproject.toml`** under `[project.optional-dependencies]` as a `dashboard` group.

3. **No test regressions.** 491/491 tests pass; test suite is healthy.
