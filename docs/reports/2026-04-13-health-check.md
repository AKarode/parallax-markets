# Parallax Phase 1 — Daily Health Check
**Date:** 2026-04-13
**Status:** YELLOW

---

## Summary

The backend pipeline remains structurally sound with 64 Python source files (~6,400 lines), 34 test modules (~200+ test cases), and a 23-table DuckDB schema covering all functional requirements. **Zero critical bugs were fixed since the April 12 report**: the invalid model IDs (`claude-opus-4-20250514`) persist in all three prediction modules, `BudgetTracker` is still initialized without a DB connection in `brief.py`, and all 9 write-path modules continue to bypass `DbWriter` with direct `conn.execute()` calls. The April 21 evaluation deadline is now 8 days away with no React/deck.gl frontend started.

---

## Changes Since 2026-04-12

No new commits to prediction, scoring, ingestion, or frontend modules since April 12. Repository tip: `45a3cf8`. The three issues flagged as CRITICAL in yesterday's report remain unresolved.

---

## Issues Found

### Critical

- **[CRITICAL — carry-forward] Invalid model IDs in all three predictors — live runs will fail.**
  `prediction/oil_price.py:129`, `prediction/ceasefire.py:104`, and `prediction/hormuz.py:114` all pass `model="claude-opus-4-20250514"` to the Anthropic API. This is not a valid model ID. Correct IDs are `claude-opus-4-6` (or `claude-sonnet-4-6` for cost alignment). Any `--no-trade` or full pipeline run will receive an API 400/404 error on the first prediction call. Dry-run mode is unaffected.

  ```python
  # WRONG (all three predictors):
  model="claude-opus-4-20250514"
  # CORRECT per agents/runner.py and CLAUDE.md:
  model="claude-opus-4-6"   # or claude-sonnet-4-6
  ```

  Note: `CLAUDE.md` states "3 Sonnet calls ~$0.02/run" but code uses Opus (5–10× more expensive). If Opus is the intent, update the cost estimate; if Sonnet is the intent, fix the model IDs.

- **[CRITICAL — carry-forward] Single-writer queue bypassed by 9 production modules.**
  The spec requires all DuckDB writes to go through the `asyncio.Queue`-based `DbWriter`. Nine modules write directly via `conn.execute()` with INSERT/UPDATE/DELETE statements, bypassing the queue:

  | File | Write Operations |
  |------|------------------|
  | `contracts/registry.py` | INSERT OR REPLACE, DELETE, INSERT, UPDATE |
  | `scoring/ledger.py` | INSERT, UPDATE (signal_ledger, trade_positions, trade_orders, trade_fills) |
  | `scoring/tracker.py` | INSERT, UPDATE (trade positions lifecycle) |
  | `scoring/prediction_log.py` | INSERT (prediction_log) |
  | `scoring/scorecard.py` | INSERT + ON CONFLICT UPDATE (daily_scorecard) |
  | `scoring/resolution.py` | INSERT/UPDATE (resolution outcomes) |
  | `cli/brief.py` | INSERT (market_prices, runs table) |
  | `budget/tracker.py` | INSERT (llm_usage) |
  | `ops/alerts.py` | INSERT (ops_events) |

  Sequential CLI usage masks this risk. The FastAPI `/api/brief/run` endpoint and any concurrent requests will produce WAL contention on the shared DuckDB file.

### High

- **[HIGH — carry-forward] `BudgetTracker` initialized without `db_conn` — LLM cost never persisted.**
  `brief.py:391`:
  ```python
  budget = BudgetTracker(daily_cap_usd=20.0)   # no db_conn kwarg
  ```
  `BudgetTracker.record()` only writes to `llm_usage` when `self._db_conn is not None`. With no connection wired, every LLM call is tracked in memory only and discarded at process exit. Consequence: `ops_llm_cost_usd` scorecard metric is always 0, budget cap has no persistence across runs, cumulative spend is invisible.

  Fix: `BudgetTracker(daily_cap_usd=20.0, db_conn=conn, run_id=run_id)` in `run_brief()`.

- **[HIGH — carry-forward] Agent-swarm pivot undocumented.**
  The Phase 1 design spec describes ~50 LLM agents across 12 countries with memory layers and conflict resolution. The actual implementation uses 3 focused predictors (oil_price, ceasefire, hormuz). No ADR or spec update has been recorded; `CLAUDE.md` documents the 3-model approach, but the design spec is stale.

- **[HIGH — carry-forward] React/deck.gl frontend is a stub. Evaluation deadline is 8 days away.**
  `frontend/` contains only `Dockerfile` and `nginx.conf` — zero `.tsx`/`.ts`/`.jsx`/`.js` source files exist. The April 21 ceasefire-window validation deadline requires some form of dashboard for demo credibility. Even a minimal Streamlit or CLI output suffices if React is intentionally deferred, but the current state produces a blank nginx page.

### Medium

- **[MEDIUM — carry-forward] Private Kalshi API method called externally in `brief.py`.**
  `brief.py:693` calls `client._request("GET", "/markets", params=...)` directly, bypassing `KalshiClient.get_markets()`. This couples `brief.py` to the client's internal HTTP layer. Fix: add `get_markets_for_event(event_ticker)` to `KalshiClient` or use the existing public `get_markets()` method.

- **[MEDIUM — carry-forward] `asyncio.gather()` at `brief.py:414` lacks `return_exceptions=True`.**
  The primary data-fetch gather (news events, oil prices, Kalshi markets, Polymarket markets) does not use `return_exceptions=True`. A single fetch failure (e.g., Kalshi 429, EIA timeout) crashes the entire run rather than gracefully degrading. The inner prediction gather at `brief.py:435` has the same problem.

  ```python
  # Current (fragile):
  events, prices, kalshi_markets, poly_markets = await asyncio.gather(
      _fetch_gdelt_events(), _fetch_oil_prices(), ...
  )
  # Fix:
  events, prices, kalshi_markets, poly_markets = await asyncio.gather(
      ..., return_exceptions=True
  )
  # Then check: if isinstance(events, Exception): events = []
  ```

- **[MEDIUM — carry-forward] End-to-end integration test absent.**
  No pipeline smoke test covers the full cycle: ingestion → cascade → prediction → market fetch → signal → trade → scorecard. A single `pytest` calling `run_brief(dry_run=True)` would catch cross-module wiring failures (it would have caught both the model ID bug and the BudgetTracker wiring issue).

- **[MEDIUM — carry-forward] Prompt versioning infrastructure absent.**
  Prompt strings are inline in each predictor. No semver versioning, A/B tracking, or drift detection. The `experiment_id`/`variant` columns exist in the schema but nothing populates them. Prediction-miss attribution is impossible without this.

- **[MEDIUM — carry-forward] `duckdb` floor should be `>=1.3`.**
  Current `pyproject.toml` pins `>=1.2`, permitting v1.2.x which lacks SPATIAL_JOIN performance improvements validated in prior research.

- **[MEDIUM] GitHub Actions workflows missing write permissions.**
  Both `claude.yml` and `claude-code-review.yml` grant only `pull-requests: read` and `issues: read`. For Claude Code Action to post review comments or manage PR labels, `pull-requests: write` and `issues: write` are required. This blocks automated PR feedback from functioning.

  ```yaml
  # Current:
  pull-requests: read
  issues: read
  # Required for comment/label actions:
  pull-requests: write
  issues: write
  ```

### Low

- **[LOW — carry-forward] `cascade_inputs` never populated in prediction log.**
  `brief.py:459–465` passes `None` for `cascade_inputs` in every `pred_logger.log_prediction()` call. The `cascade_inputs` column in `prediction_log` is always NULL — causal attribution on oil_price/hormuz prediction misses is impossible without it.

- **[LOW — carry-forward] `searoute>=1.3` fails to build in the current environment.**
  `searoute` is not installed (`pip show searoute: WARNING: Package(s) not found`). The package is only used for sea-route penalty computation in the cascade engine (a scalar, not actual routing). Consider making it an optional dependency (`extras_require`) or replacing with an inline constant for the Cape of Good Hope detour factor.

- **[LOW — carry-forward] `google-cloud-bigquery>=3.27` is unused.**
  BigQuery GDELT was replaced by the GDELT DOC API. The SDK adds ~30 MB of transitive dependencies. Remove from `pyproject.toml`.

- **[LOW — carry-forward] `pytest-httpx` overly narrow pin `>=0.35,<0.36`.**
  Upper bound will block future upgrades. Loosen to `>=0.35`.

---

## Spec / Plan Consistency

| Plan Task | Status | Notes |
|-----------|--------|-------|
| Task 1 — Project scaffold + DuckDB schema | ✓ Complete | 23 tables |
| Task 2 — Single-writer DB layer | ⚠ Partial | `DbWriter` exists; 9 production modules bypass it |
| Task 3 — Scenario config loader | ✓ Complete | `simulation/config.py` |
| Task 4 — H3 spatial utilities | ✓ Complete | `spatial/h3_utils.py` |
| Task 5 — In-memory world state | ✓ Complete | `simulation/world_state.py` |
| Task 6 — Cascade rules engine | ✓ Complete | 6-rule `simulation/cascade.py` |
| Task 7 — Circuit breaker | ✓ Complete | `simulation/circuit_breaker.py` |
| Task 8 — DES engine | ✓ Complete | `simulation/engine.py` |
| Task 9 — GDELT ingestion | ⚠ Deviated | DOC API, not BigQuery; functionally sound |
| Task 10 — Semantic deduplication | ✓ Complete | `ingestion/dedup.py` |
| Task 11 — Agent schemas | ⚠ Partial | Models present; no registry/router |
| Task 12 — Agent registry + router | ✗ Pivoted | Replaced by 3 focused predictors |
| Task 13 — Agent runner | ⚠ Partial | `agents/runner.py` exists but not wired |
| Task 14 — Eval framework | ✓ Complete | 25+ scorecard metrics |
| Task 15 — Prompt versioning | ✗ Not built | Schema columns exist; no module |
| Task 16 — FastAPI backend | ✓ Complete | 6 REST endpoints + Streamlit dashboard |
| Tasks 17–20 — React frontend | ✗ Not built | nginx stub only |
| Task 21 — Integration test | ✗ Not built | No pipeline smoke test |
| Task 22 — .gitignore + env vars | ✓ Complete | |

---

## Dependency Audit

| Package | Floor in pyproject.toml | Status |
|---------|------------------------|--------|
| `duckdb` | >=1.2 | Raise to >=1.3 |
| `anthropic` | >=0.52 | OK — SDK fine; model IDs in source code are wrong |
| `searoute` | >=1.3 | Not installed; build fails — make optional |
| `google-cloud-bigquery` | >=3.27 | Unused — remove |
| `pytest-httpx` | >=0.35,<0.36 | Loosen upper bound |
| `sentence-transformers` | >=3.4 | OK |
| `truthbrush` | >=0.2 | Verify Truth Social API compat |
| `cryptography` | >=44.0 | OK |

No new CVEs identified.

---

## Test Coverage

**34 test files — unit coverage strong at module level.**

**Missing (all carry-forwards):**
- End-to-end brief pipeline smoke test (Task 21 from plan)
- Live model ID validation test (would have caught `claude-opus-4-20250514` bug)
- `BudgetTracker` DB-persistence integration test
- `agents/runner.py` LLM integration test

---

## Recommendations (Priority Order)

1. **Fix invalid model IDs today (CRITICAL).** One-line fix per file. Change `claude-opus-4-20250514` → `claude-opus-4-6` (or `claude-sonnet-4-6`) in `prediction/oil_price.py:129`, `prediction/ceasefire.py:104`, `prediction/hormuz.py:114`. Update `CLAUDE.md` cost estimate to match chosen model. This unblocks every live run.

2. **Wire `BudgetTracker` to DB in `run_brief()` (HIGH).** Change `brief.py:391` to `BudgetTracker(daily_cap_usd=20.0, db_conn=conn, run_id=run_id)`. Without this, budget audit trail is broken and scorecard LLM cost metric is always 0.

3. **Add `return_exceptions=True` to gather calls (MEDIUM).** Both `brief.py:414` and `:435` need this. Check each result for `isinstance(x, Exception)` and substitute empty defaults. Prevents a single failing API from crashing the entire run.

4. **Replace `client._request()` with public API (MEDIUM).** Add `get_markets_for_event(event_ticker)` to `KalshiClient` and call that from `brief.py:693`.

5. **Write an end-to-end dry-run test (MEDIUM).** A single pytest that calls `run_brief(dry_run=True)` and asserts: ≥3 predictions logged, ≥1 signal recorded, no exceptions. This would have caught both the model ID bug and the BudgetTracker wiring issue when they were introduced.

6. **Fix GitHub Actions permissions (MEDIUM).** Add `pull-requests: write` and `issues: write` to both workflow files.

7. **Decide on frontend strategy and document it (HIGH).** 8 days to deadline. If React is intentionally deferred, update `CLAUDE.md` and spec to say so. If a minimal dashboard is needed, the Streamlit `dashboard/app.py` is the fastest path.

8. **Remove `google-cloud-bigquery` and loosen `pytest-httpx` pin (LOW).**

9. **Raise `duckdb` floor to `>=1.3` (LOW).**

10. **Make `searoute` an optional dependency (LOW).**

---

*Next check: 2026-04-14. Priority watch: model ID fix (blocks all live runs), BudgetTracker wiring, April 21 evaluation deadline — 8 days remaining.*
