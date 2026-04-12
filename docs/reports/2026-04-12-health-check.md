# Parallax Phase 1 — Daily Health Check
**Date:** 2026-04-12
**Status:** YELLOW

---

## Summary

The backend pipeline remains structurally sound with 64 source files, 34 test files, and a 23-table DuckDB schema. Two **new regressions** were discovered today: all three LLM prediction models hardcode `claude-opus-4-20250514` — an invalid model ID that will cause API errors in live mode — and `BudgetTracker` is initialized without a DB connection in `brief.py`, silently dropping all LLM cost records and rendering the scorecard's `ops_llm_cost_usd` metric permanently 0. The nine issues from the April 11 report are all carry-forwards; none were resolved.

---

## Changes Since 2026-04-11

No new commits to the prediction, scoring, or ingestion modules since the April 11 report. Repository tip: `f67cbe3`.

---

## Issues Found

### Critical

- **[CRITICAL] Invalid model IDs in all three predictors — will fail at runtime.**
  `prediction/oil_price.py:129`, `prediction/ceasefire.py:104`, and `prediction/hormuz.py:114` all pass `model="claude-opus-4-20250514"` to the Anthropic API. This is not a valid model ID — the correct IDs (per `agents/runner.py`) are `claude-opus-4-6`, `claude-sonnet-4-6`, and `claude-haiku-4-5-20251001`. Any live run (`--no-trade` or full pipeline) will get an API 400/404 error the moment the first prediction fires. The dry-run path is unaffected.

  ```python
  # WRONG (all three predictors):
  model="claude-opus-4-20250514"
  # CORRECT per agents/runner.py:
  model="claude-opus-4-6"
  ```

  Additionally, `CLAUDE.md` states "3 Sonnet calls ~$0.02/run" but the code calls **Opus**, which is ~5–10× more expensive. If the intent is Opus, update the CLAUDE.md cost estimate; if the intent is Sonnet, change the model ID.

- **[CRITICAL — carry-forward] Single-writer violations — 20 files bypass `DbWriter`.**
  All modules with write paths (`scoring/`, `contracts/`, `cli/brief.py`, `budget/tracker.py`, `ops/alerts.py`) call `conn.execute()` directly rather than `await db_writer.enqueue()`. Sequential CLI usage masks the risk, but the FastAPI `/api/brief/run` endpoint and any future background scheduling will produce WAL contention on the shared DuckDB file. See April 11 report for full table.

### High

- **[HIGH — new] `BudgetTracker` initialized without `db_conn` — LLM cost never persisted.**
  `brief.py:391`:
  ```python
  budget = BudgetTracker(daily_cap_usd=20.0)   # no db_conn kwarg
  ```
  `BudgetTracker.record()` only writes to `llm_usage` when `self._db_conn is not None`. With no connection wired, every LLM call is tracked in-memory only — the cost is discarded at process exit. Consequence: the scorecard's `ops_llm_cost_usd` metric is always 0, the budget cap has no persistence across runs, and cumulative spend is invisible. Fix: pass `db_conn=conn` and `run_id=run_id` when constructing `BudgetTracker` in `run_brief()`.

- **[HIGH — carry-forward] Agent-swarm pivot undocumented.** The Phase 1 design spec still describes 50 LLM agents across 12 countries. The actual implementation uses 3 focused predictors. No ADR or spec update recorded.

- **[HIGH — carry-forward] React/deck.gl frontend is a stub.** Zero `.tsx`/`.ts`/`.jsx`/`.js` files exist under `frontend/`. Nine days remain before the April 21 evaluation deadline. A read-only dashboard (even minimal) is needed for demo credibility.

### Medium

- **[MEDIUM — new] Private API method called externally in `brief.py`.**
  `brief.py:693` calls `client._request("GET", "/markets", params=...)` directly, bypassing `KalshiClient.get_markets()`. This couples `brief.py` to `KalshiClient`'s internal HTTP layer. If `KalshiClient` changes its URL structure, auth headers, or retry logic, `brief.py` silently breaks. Use the public `get_markets(series_ticker=event_ticker)` method instead, or add a `get_markets_by_event()` method to `KalshiClient`.

- **[MEDIUM — carry-forward] End-to-end integration test absent.** No pipeline smoke test covers: ingestion → cascade → prediction → market fetch → signal → trade → scorecard. The 34 unit tests do not catch cross-module wiring failures.

- **[MEDIUM — carry-forward] Prompt versioning infrastructure absent.** Prompt strings are inline in each predictor; no semver versioning, A/B tracking, or drift detection. `experiment_id`/`variant` columns exist in the schema but nothing populates them.

- **[MEDIUM — carry-forward] `duckdb` floor should be `>=1.3`.** Current `>=1.2` permits installing v1.2.x, which lacks `SPATIAL_JOIN` performance improvements validated in prior research.

### Low

- **[LOW — new] `searoute` dependency fails to build in the current environment.**
  `pip install` aborts with a wheel-build failure for `searoute`. This blocks local environment setup and test execution entirely. `searoute` is used only in simulation pathing logic, not in the active prediction pipeline. Consider making it optional (`extras_require`) or pinning to a pre-built wheel until the build issue is resolved.

- **[LOW — carry-forward] `google-cloud-bigquery>=3.27` is unused.** BigQuery GDELT was replaced by the DOC API. The SDK adds ~30 MB of transitive dependencies for zero functional benefit.

- **[LOW — carry-forward] `pytest-httpx` overly narrow pin `>=0.35,<0.36`.** Upper bound will block future upgrades.

- **[LOW — carry-forward] GitHub Actions workflows missing permissions.** `.github/workflows/claude.yml` and `claude-code-review.yml` need `pull-requests: write` and `issues: write`. Eleven-day carry-forward.

---

## Spec / Plan Consistency

| Plan Task | Status | Notes |
|-----------|--------|-------|
| Task 1 — Project scaffold + DuckDB schema | ✓ Complete | 23 tables |
| Task 2 — Single-writer DB layer | ⚠ Partial | `DbWriter` exists; 20 callers bypass it |
| Task 3 — Scenario config loader | ✓ Complete | `simulation/config.py` |
| Task 4 — H3 spatial utilities | ✓ Complete | `spatial/h3_utils.py` |
| Task 5 — In-memory world state | ✓ Complete | `simulation/world_state.py` |
| Task 6 — Cascade rules engine | ✓ Complete | 6-rule `simulation/cascade.py` |
| Task 7 — Circuit breaker | ✓ Complete | `simulation/circuit_breaker.py` |
| Task 8 — DES engine | ✓ Complete | `simulation/engine.py` |
| Task 9 — GDELT ingestion | ⚠ Deviated | DOC API, not BigQuery; functional |
| Task 10 — Semantic deduplication | ✓ Complete | `ingestion/dedup.py` |
| Task 11 — Agent schemas | ⚠ Partial | Models present; no registry or router |
| Task 12 — Agent registry + router | ✗ Pivoted | Replaced by 3 focused predictors |
| Task 13 — Agent runner | ⚠ Partial | `agents/runner.py` not wired |
| Task 14 — Eval framework | ✓ Complete | 25+ scorecard metrics |
| Task 15 — Prompt versioning | ✗ Not built | Schema column exists; no module |
| Task 16 — FastAPI backend | ✓ Complete | 6 endpoints + dashboard |
| Tasks 17–20 — React frontend | ✗ Not built | nginx stub only |
| Task 21 — Integration test | ✗ Not built | No pipeline smoke test |
| Task 22 — .gitignore + env vars | ✓ Complete | |

---

## Dependency Audit

| Package | Floor | Status |
|---------|-------|--------|
| `duckdb` | >=1.2 | Raise to >=1.3 for SPATIAL_JOIN |
| `anthropic` | >=0.52 | OK — model IDs in source are wrong, not the SDK |
| `searoute` | >=1.3 | Build fails; make optional or pin wheel |
| `google-cloud-bigquery` | >=3.27 | Unused — remove |
| `pytest-httpx` | >=0.35,<0.36 | Loosen upper bound |
| `truthbrush` | >=0.2 | Verify Truth Social API compat |
| `cryptography` | >=44.0 | OK |

No new CVEs identified.

---

## Test Coverage

**34 test files — unit coverage strong at module level.**

**Missing (carry-forwards):**
- End-to-end brief pipeline test (Task 21)
- Live model ID validation test (would have caught the `claude-opus-4-20250514` bug)
- `BudgetTracker` DB-persistence integration test
- `agents/runner.py` LLM integration test

---

## Recommendations (Priority Order)

1. **Fix invalid model IDs today (CRITICAL).** Change `claude-opus-4-20250514` → `claude-opus-4-6` (or `claude-sonnet-4-6` if cost is a concern) in all three predictors. Update `CLAUDE.md` cost estimate to match. One-line fix per file; unblocks every live run.

2. **Wire `BudgetTracker` to DB in `run_brief()` (HIGH).** Change `brief.py:391` to `BudgetTracker(daily_cap_usd=20.0, db_conn=conn, run_id=run_id)`. Without this, the budget audit trail is permanently broken.

3. **Replace `client._request()` with public API (MEDIUM).** Add `get_markets_for_event(event_ticker)` to `KalshiClient` or use the existing `get_markets(series_ticker=event_ticker)`. Remove the private call in `brief.py:693`.

4. **Fix `searoute` build issue (LOW).** Make `searoute` an optional dependency (`pip install parallax[spatial]`) or replace with a pure-Python fallback for the Cape of Good Hope penalty — the current cascade engine only uses the reroute penalty as a scalar, not actual routing.

5. **Write an end-to-end dry-run test (MEDIUM).** A single pytest that calls `run_brief(dry_run=True)` and asserts: ≥3 predictions, ≥1 signal, scorecard computable without errors. This would have caught both the model ID bug and the BudgetTracker wiring issue.

6. **Remove `google-cloud-bigquery` from `pyproject.toml` (LOW).**

7. **Raise `duckdb` floor to `>=1.3` (LOW).**

---

*Next check: 2026-04-13. Priority watch: model ID fix (blocks all live runs), BudgetTracker wiring, April 21 evaluation deadline — 9 days.*
