# Parallax Phase 1 — Daily Health Check
**Date:** 2026-04-15
**Status:** YELLOW

---

## Summary

No code commits since April 13. All three CRITICAL issues from the previous report remain unresolved: invalid model IDs (`claude-opus-4-20250514`) in all three predictors will crash any live run, `BudgetTracker` is still initialized without a DB connection, and 9 production modules continue to bypass the `DbWriter` queue. The April 21 ceasefire-window evaluation deadline is now **6 days away** with no React/deck.gl frontend started and no progress on blocking bugs.

---

## Changes Since 2026-04-13

Zero code changes. Repository tip is still `ba793c8` (April 13 health-check commit). No fixes, no new features, no test additions. This is the second consecutive no-op day on CRITICAL issues.

---

## Issues Found

### Critical

- **[CRITICAL — day 4 carry-forward] Invalid model IDs in all three predictors — live runs fail immediately.**
  `prediction/oil_price.py:129`, `prediction/ceasefire.py:104`, and `prediction/hormuz.py:114` all pass `model="claude-opus-4-20250514"` to the Anthropic API. This ID does not exist; valid IDs are `claude-opus-4-6` or `claude-sonnet-4-6`. Every `--no-trade` or full pipeline call returns an API 400/404 on the first prediction call. Dry-run mode is unaffected.

  ```python
  # WRONG (all three predictors):
  model="claude-opus-4-20250514"
  # CORRECT (per CLAUDE.md and agents/runner.py):
  model="claude-opus-4-6"   # or claude-sonnet-4-6
  ```

  This has been flagged as CRITICAL for 4 consecutive days. It is a one-line fix per file. **No live prediction has successfully completed since this bug was introduced.**

- **[CRITICAL — day 4 carry-forward] Single-writer queue bypassed by 9 production modules.**
  The spec mandates all DuckDB writes go through the `asyncio.Queue`-based `DbWriter`. The following modules write directly via `conn.execute()`, creating WAL contention risk under any concurrent FastAPI usage:

  | File | Write Operations |
  |------|------------------|
  | `contracts/registry.py` | INSERT OR REPLACE, DELETE, INSERT, UPDATE |
  | `scoring/ledger.py` | INSERT, UPDATE (signal_ledger) |
  | `scoring/tracker.py` | INSERT, UPDATE (trade positions lifecycle) |
  | `scoring/prediction_log.py` | INSERT (prediction_log) |
  | `scoring/scorecard.py` | INSERT + ON CONFLICT UPDATE (daily_scorecard) |
  | `scoring/resolution.py` | INSERT/UPDATE (resolution outcomes) |
  | `cli/brief.py` | INSERT (market_prices, runs table) |
  | `budget/tracker.py` | INSERT (llm_usage) |
  | `ops/alerts.py` | INSERT (ops_events) |

  Sequential CLI usage masks this; the `/api/brief/run` endpoint and concurrent WebSocket traffic will produce `database is locked` errors.

### High

- **[HIGH — day 4 carry-forward] `BudgetTracker` initialized without `db_conn` — LLM cost never persisted.**
  `brief.py:391`:
  ```python
  budget = BudgetTracker(daily_cap_usd=20.0)   # no db_conn kwarg
  ```
  When `db_conn` is `None`, `BudgetTracker.record()` only tracks cost in memory; it discards the record at process exit. Consequence: `ops_llm_cost_usd` scorecard metric is always 0, budget cap has no cross-run persistence, and cumulative spend is invisible.

  Fix: `BudgetTracker(daily_cap_usd=20.0, db_conn=conn, run_id=run_id)`.

- **[HIGH — day 4 carry-forward] React/deck.gl frontend is a stub. Deadline is 6 days away.**
  `frontend/` contains only `Dockerfile` and `nginx.conf`. Zero `.tsx`/`.ts` source files exist. The April 21 ceasefire-window evaluation deadline requires some form of working dashboard. The Streamlit `dashboard/app.py` is functional and is the fastest path to a demo-ready UI — but it is not linked in `docker-compose.yml` or the README as the primary dashboard. Decision and documentation needed today.

- **[HIGH — day 4 carry-forward] Agent-swarm pivot undocumented.**
  The Phase 1 design spec describes ~50 LLM agents across 12 countries with memory layers and conflict resolution. The actual implementation uses 3 focused predictors (oil_price, ceasefire, hormuz). No ADR or spec update has been recorded. The design spec remains stale. Downstream: prediction-miss attribution is still structured around agent IDs that don't exist.

### Medium

- **[MEDIUM — day 4 carry-forward] Private Kalshi API method called externally in `brief.py`.**
  `brief.py:693` calls `client._request("GET", "/markets", params=...)` directly, bypassing `KalshiClient.get_markets()`. This couples `brief.py` to the client's internal HTTP layer and will silently break if `KalshiClient` is refactored.

- **[MEDIUM — day 4 carry-forward] `asyncio.gather()` at `brief.py:414` lacks `return_exceptions=True`.**
  The primary data-fetch gather (news, oil prices, Kalshi markets, Polymarket markets) and the inner prediction gather at `:435` both propagate exceptions instead of degrading gracefully. A single Kalshi 429 or EIA timeout crashes the entire run.

  ```python
  # Current (fragile):
  events, prices, kalshi_markets, poly_markets = await asyncio.gather(
      _fetch_gdelt_events(), _fetch_oil_prices(), ...
  )
  # Fix:
  events, prices, kalshi_markets, poly_markets = await asyncio.gather(
      ..., return_exceptions=True
  )
  # then: if isinstance(events, Exception): events = []
  ```

- **[MEDIUM — day 4 carry-forward] End-to-end integration test absent.**
  No pipeline smoke test covers ingestion → cascade → prediction → market fetch → signal → trade → scorecard. A single `pytest` calling `run_brief(dry_run=True)` would have caught both the model ID bug and the BudgetTracker wiring issue when they were introduced.

- **[MEDIUM — day 4 carry-forward] Prompt versioning infrastructure absent.**
  Prediction strings are inline in each predictor. No semver versioning, A/B tracking, or drift detection. `experiment_id`/`variant` columns exist in the schema but nothing populates them. Prediction-miss attribution is impossible without this.

- **[MEDIUM — day 4 carry-forward] GitHub Actions workflows missing write permissions.**
  Both `claude.yml` and `claude-code-review.yml` grant only `pull-requests: read` and `issues: read`. For Claude Code Action to post review comments or manage PR labels, `pull-requests: write` and `issues: write` are required.

- **[MEDIUM — day 4 carry-forward] `duckdb` floor should be `>=1.3`.**
  `pyproject.toml` pins `>=1.2`, permitting v1.2.x which lacks SPATIAL_JOIN performance improvements.

### Low

- **[LOW — new] `pyproject.toml` Python floor is `>=3.11`; CLAUDE.md and plan specify Python 3.12.**
  `pyproject.toml:4` says `requires-python = ">=3.11"`. The CLAUDE.md stack section, the Dockerfile, and the Phase 1 plan all specify Python 3.12. The environment is running Python 3.11.15. This is a minor inconsistency but should be made consistent — either raise the floor to `>=3.12` to match the stated stack, or update CLAUDE.md to reflect 3.11 support.

- **[LOW — new] `pytest` not installed in the current execution environment.**
  `python3 -m pytest --version` fails: "No module named pytest". Tests cannot run without `pip install -e ".[dev]"`. The health check cron should either install deps before running or verify the environment is primed. No test output is available for this report.

- **[LOW — day 4 carry-forward] `cascade_inputs` never populated in prediction log.**
  `brief.py:459–465` passes `None` for `cascade_inputs` in every `pred_logger.log_prediction()` call. The `cascade_inputs` column in `prediction_log` is always NULL — causal attribution on oil_price/hormuz prediction misses is impossible.

- **[LOW — day 4 carry-forward] `searoute>=1.3` fails to build in the current environment.**
  `searoute` is not installed (`pip show searoute: WARNING: Package(s) not found`). It is only used for the Cape of Good Hope detour scalar in the cascade engine. Consider making it an optional dependency or replacing with an inline constant.

- **[LOW — day 4 carry-forward] `google-cloud-bigquery>=3.27` is unused.**
  BigQuery GDELT was replaced by the GDELT DOC API. The SDK adds ~30 MB of transitive dependencies. Remove from `pyproject.toml`.

- **[LOW — day 4 carry-forward] `pytest-httpx` overly narrow pin `>=0.35,<0.36`.**
  Upper bound blocks future upgrades. Loosen to `>=0.35`.

---

## Spec / Plan Consistency

| Plan Task | Status | Notes |
|-----------|--------|-------|
| Task 1 — Project scaffold + DuckDB schema | ✓ Complete | 23 tables, 2 views |
| Task 2 — Single-writer DB layer | ⚠ Partial | `DbWriter` exists; 9 production modules bypass it |
| Task 3 — Scenario config loader | ✓ Complete | `simulation/config.py` |
| Task 4 — H3 spatial utilities | ✓ Complete | `spatial/h3_utils.py` |
| Task 5 — In-memory world state | ✓ Complete | `simulation/world_state.py` |
| Task 6 — Cascade rules engine | ✓ Complete | 6-rule `simulation/cascade.py` |
| Task 7 — Circuit breaker | ✓ Complete | `simulation/circuit_breaker.py` |
| Task 8 — DES engine | ✓ Complete | `simulation/engine.py` |
| Task 9 — GDELT ingestion | ⚠ Deviated | DOC API not BigQuery; functionally equivalent |
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
| `anthropic` | >=0.52 | SDK OK; model IDs in source code are wrong |
| `searoute` | >=1.3 | Not installed; build fails — make optional |
| `google-cloud-bigquery` | >=3.27 | Unused — remove |
| `pytest-httpx` | >=0.35,<0.36 | Loosen upper bound |
| `sentence-transformers` | >=3.4 | OK |
| `truthbrush` | >=0.2 | OK |
| `cryptography` | >=44.0 | OK |

No new CVEs identified.

---

## Test Coverage

**34 test files — unit coverage strong at module level. Tests cannot be executed: pytest not installed in environment.**

**Present:**
- `test_schema.py`, `test_writer.py`, `test_cascade.py`, `test_circuit_breaker.py`, `test_engine.py`, `test_world_state.py`, `test_config.py`, `test_h3_utils.py` — simulation core
- `test_ledger.py`, `test_prediction_log.py`, `test_scorecard.py`, `test_calibration.py`, `test_recalibration.py`, `test_resolution.py`, `test_report_card.py`, `test_track_record.py` — scoring pipeline
- `test_registry.py`, `test_mapping_policy.py`, `test_contracts_schemas.py`, `test_divergence.py` — contracts
- `test_kalshi.py`, `test_polymarket.py`, `test_gdelt_doc.py`, `test_google_news.py`, `test_truth_social.py` — ingestion/markets
- `test_brief.py`, `test_dashboard_data.py`, `test_llm_usage.py`, `test_ops_events.py`, `test_experiment_tags.py`, `test_edge_decay_over_time.py`, `test_runs_table.py` — CLI/ops

**Missing (all carry-forwards):**
- End-to-end brief pipeline smoke test (calls `run_brief(dry_run=True)`, asserts ≥3 predictions logged, ≥1 signal, no exceptions)
- Live model ID validation test (would have caught `claude-opus-4-20250514` on day 1)
- `BudgetTracker` DB-persistence integration test
- `agents/runner.py` LLM integration test

---

## Recommendations (Priority Order)

1. **Fix invalid model IDs today (CRITICAL — day 4).** One-line fix per file. Change `claude-opus-4-20250514` → `claude-sonnet-4-6` in `prediction/oil_price.py:129`, `prediction/ceasefire.py:104`, `prediction/hormuz.py:114`. This unblocks every live run and is the single highest-leverage action available.

2. **Wire `BudgetTracker` to DB in `run_brief()` (HIGH — day 4).** Change `brief.py:391` to `BudgetTracker(daily_cap_usd=20.0, db_conn=conn, run_id=run_id)`. Without this, the LLM budget audit trail is broken and the `ops_llm_cost_usd` scorecard metric is always 0.

3. **Decide on frontend strategy and document it — deadline is 6 days out (HIGH).** Three options: (a) promote `dashboard/app.py` Streamlit as the demo dashboard, add it to `docker-compose.yml`, update README; (b) scaffold a minimal React/deck.gl shell this week; (c) formally defer to Phase 2. Option (a) is the fastest path to a demo-ready system by April 21.

4. **Add `return_exceptions=True` to gather calls (MEDIUM — day 4).** `brief.py:414` and `:435` both need this plus per-result exception checks. Prevents a single API failure from crashing the entire run.

5. **Replace `client._request()` with a public KalshiClient method (MEDIUM — day 4).** Add `get_markets_for_event(event_ticker)` to `KalshiClient` and use it at `brief.py:693`.

6. **Write an end-to-end dry-run integration test (MEDIUM — day 4).** A single pytest calling `run_brief(dry_run=True)` asserting: ≥3 predictions, ≥1 signal, no exceptions. Would have caught both CRITICAL bugs on introduction.

7. **Fix GitHub Actions permissions (MEDIUM — day 4).** Add `pull-requests: write` and `issues: write` to both workflow files.

8. **Align Python version floor (LOW — new).** Set `requires-python = ">=3.12"` in `pyproject.toml` to match CLAUDE.md, or update CLAUDE.md to reflect actual 3.11 support.

9. **Remove `google-cloud-bigquery` and loosen `pytest-httpx` pin (LOW — day 4).**

10. **Raise `duckdb` floor to `>=1.3` and make `searoute` optional (LOW — day 4).**

---

*Next check: 2026-04-16. Priority watch: model ID fix (CRITICAL, day 4 — blocks all live runs), BudgetTracker wiring (HIGH, day 4), April 21 evaluation deadline — **6 days remaining**.*
