# Parallax Health Check — 2026-06-01

**Status: YELLOW**

## Summary

416 of 446 collected tests pass (93.3%), up from 378/408 yesterday — 38 net new passing tests, reflecting continued feature work. The two test-collection errors from the previous report are resolved (`fastapi` and `truthbrush` are now installed in the environment). The `pytz` root cause persists for the **10th consecutive day**, still blocking the same 17 tests. No new regressions were introduced.

---

## Issues Found

### [CRITICAL] `pytz` not declared in `pyproject.toml` — 17 test failures (10th day)

- **Root cause:** `pytz` is not in `pyproject.toml` and is absent from the environment. DuckDB raises `InvalidInputException: Required module 'pytz' failed to import` on any query that reads a `TIMESTAMPTZ` column (`runs`, `llm_usage`, `ops_events`, `crisis_events`).
- **Failing tests (unchanged):** `test_crisis_context_db` (4), `test_llm_usage` (1), `test_ops_events` (1), `test_phase1_critical` (1), `test_scorecard` (10).
- **Fix:** Add `"pytz"` to the `dependencies` list in `backend/pyproject.toml`. One-line change.
- **Escalation note:** This has been flagged CRITICAL for 10 consecutive health-check cycles with no action. A CI `pip check` or `python -c "import pytz"` step would have caught this on day 1.

### [HIGH] DuckDB single-writer pattern not enforced

- **Spec requirement:** All writes must go through the centralized `DbWriter` asyncio queue.
- **Reality:** `DbWriter` is correct but unused in production paths. Modules writing directly:
  - `budget/tracker.py` → `llm_usage`
  - `ops/alerts.py` → `ops_events`
  - `scoring/ledger.py` → `signal_ledger`
  - `scoring/prediction_log.py` → `prediction_log`
  - `scoring/tracker.py` → `trade_orders`, `trade_positions`, `trade_fills`
  - `scoring/scorecard.py` → `daily_scorecard`
  - `scoring/resolution.py` → `signal_ledger`, `trade_positions`
  - `cli/brief.py` → `runs`, `market_prices`
  - `contracts/registry.py` → `contract_proxy_map`, `contract_registry`
  - `ingestion/crisis_ingester.py` → `crisis_events`
  - `backtest/runner.py` → `backtest_runs`, `backtest_predictions`
- **Current risk:** Low — the CLI is synchronous and the FastAPI event loop serializes writes naturally. Risk becomes real if any two async paths write concurrently.
- **Recommended action:** Either route highest-frequency paths (`signal_ledger`, `llm_usage`) through the queue, or add a comment in `db/writer.py` documenting the intentional exception and the safety assumption.

### [MEDIUM] Architecture pivot not reflected in spec/plan docs

- The Phase 1 spec describes a 50-agent LLM swarm with H3 hex map, GDELT BigQuery, WebSocket real-time updates, and a prompt-versioning eval framework. The live system is a prediction market edge-finder with 3 Sonnet prediction models, Kalshi/Polymarket comparison, and REST-polling dashboard.
- `CLAUDE.md` accurately describes the current system. The spec/plan files are historical artifacts.
- **Missing plan modules** (never implemented; not needed by current system): `agents/`, `spatial/`, `eval/`, `api/`, `simulation/engine.py`, `simulation/circuit_breaker.py`.
- **Frontend gap:** `HexMap.tsx`, `AgentFeed.tsx`, `Timeline.tsx`, deck.gl, MapLibre, h3-js are absent — consistent with the pivot away from spatial visualization.
- **Recommended action:** Add a `> **Superseded**` banner to the spec and plan docs pointing to `CLAUDE.md` as the canonical reference.

### [LOW] `httpx` deprecation warning from starlette TestClient

- **New this cycle.** `tests/test_dashboard_endpoints.py` now collects successfully (fastapi installed), but triggers: `StarletteDeprecationWarning: Using 'httpx' with 'starlette.testclient' is deprecated; install 'httpx2' instead.`
- `pyproject.toml` pins `pytest-httpx>=0.35,<0.36`. The fix is to add `httpx2` as a dev dependency and update the pin.
- **Severity:** Low — tests pass, it is a deprecation warning only.

### [LOW] `requires-python` version mismatch

- `pyproject.toml` requires `>=3.11`; `CLAUDE.md` and the original plan reference Python 3.12. Runtime is 3.11.15. The code runs correctly on 3.11, so `>=3.11` is accurate. Documentation inconsistency only.

### [LOW] Budget tracker pricing may be slightly stale

- `budget/tracker.py` prices Haiku at `$0.001/$0.005` per 1K tokens. Current Claude Haiku 4.5 pricing is `$0.0008/$0.004`. Sonnet pricing matches. Impact: minor overestimation of daily cost — safe direction to err.

---

## Test Suite Delta (vs 2026-05-31)

| Metric | 2026-05-31 | 2026-06-01 | Change |
|--------|-----------|-----------|--------|
| Total collected | 408 | 446 | +38 |
| Passing | 378 | 416 | +38 |
| Failing | 17 | 17 | 0 |
| Skipped | 13 | 13 | 0 |
| Pass rate | 92.6% | 93.3% | +0.7pp |
| Collection errors | 2 | 0 | **-2 ✓** |

---

## Recommendations

1. **Fix immediately (day 10):** Add `"pytz"` to `backend/pyproject.toml` dependencies. This resolves all 17 failures with one character change.

2. **Add to CI:** A `python -c "import pytz"` check or `pip check` step in any CI pipeline would catch undeclared runtime deps before they accumulate. The 10-day streak on this same issue illustrates the gap.

3. **Address httpx2 warning:** Replace `pytest-httpx>=0.35,<0.36` with a version that supports `httpx2`, or add `httpx2` as a dev dep, to keep the test suite warning-free.

4. **Document single-writer exception:** Add a comment to `db/writer.py` clarifying the current safety assumption (single asyncio event loop, synchronous CLI), so future contributors don't unknowingly break the invariant by introducing concurrent async writers.

5. **Archive spec docs:** Mark the Phase 1 spec and plan as superseded in their headers. Reduces confusion for new contributors.
