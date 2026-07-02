# Parallax Health Check — 2026-06-06

**Status: YELLOW**

## Summary

No code changes since yesterday's health check (only the prior report commit). All HIGH carry-overs remain unresolved: the DuckDB single-writer pattern is violated by 10 modules (up from 7 previously noted — `contracts/registry.py`, `ingestion/crisis_ingester.py`, and `cli/brief.py` were newly counted), the budget cap is still decorative, and all three predictors still call the retired Opus model ID at 15–30× the documented cost. A new concrete bug was found: `scoring/ledger.py:267` passes `position_id` as the third parameter where `trade_id` is expected, silently poisoning the `trade_id` column in `signal_ledger` on every execution update.

---

## Issues Found

### [HIGH] DuckDB Single-Writer Violations *(carry-over, unresolved — day 42+, scope expanded)*

The spec mandates all writes via `DbWriter`'s `asyncio.Queue`. Ten modules bypass it with direct `conn.execute()` writes, creating write-write race conditions when CLI cron and FastAPI run concurrently. Previously reported as 7 modules; today's audit identified 3 additional violators:

**Previously reported:**
- `scoring/ledger.py` — `INSERT`/`UPDATE signal_ledger` (lines 225, 256)
- `scoring/tracker.py` — `INSERT`/`UPDATE trade_positions`, `INSERT trade_orders`, `INSERT trade_fills`
- `scoring/prediction_log.py` — `INSERT INTO prediction_log` (line 79)
- `scoring/scorecard.py` — `INSERT INTO daily_scorecard` with `ON CONFLICT DO UPDATE`
- `ops/alerts.py` — `INSERT INTO ops_events` (line 106)
- `budget/tracker.py` — `INSERT INTO llm_usage` (line 43)
- `backtest/runner.py` — `INSERT`/`UPDATE backtest_runs`, `INSERT`/`UPDATE backtest_predictions`

**Newly identified:**
- `contracts/registry.py` — `INSERT OR REPLACE INTO contract_registry`, `DELETE FROM contract_proxy_map`, `INSERT INTO contract_proxy_map` (lines 85, 105, 114)
- `ingestion/crisis_ingester.py` — `INSERT INTO crisis_events` (line 79)
- `cli/brief.py` — `INSERT INTO runs`, `UPDATE runs`, `INSERT INTO market_prices` (lines 130, 149, ~433)

`DbWriter` exists in `db/writer.py` but is not injected into any of these modules. Tests use per-test in-memory connections so the violation is invisible in CI.

### [HIGH] Bug: `trade_id` Never Set in `signal_ledger` *(new)*

`scoring/ledger.py` line 267 passes `position_id` as the third positional parameter to the `update_execution()` UPDATE:

```python
# SQL placeholders (lines 258–265):
#   execution_status = ?          ← param 1
#   entry_order_id = COALESCE(?, ...)  ← param 2
#   trade_id = COALESCE(?, ...)        ← param 3  ← WRONG
#   position_id = COALESCE(?, ...)     ← param 4
#   traded = COALESCE(?, ...)          ← param 5
#   trade_refused_reason = COALESCE(?, ...)  ← param 6
#   WHERE signal_id = ?                ← param 7

# Actual params list (line 267):
[execution_status, entry_order_id, position_id, position_id, traded, trade_refused_reason, signal_id]
#                                  ^^^^^^^^^^^^ should be trade_id
```

`trade_id` is silently set to `position_id` on every call. Any downstream query joining on `trade_id` (P&L attribution, trade history) returns stale or wrong data. Fix: replace the third element with the `trade_id` argument (which needs to be added to the function signature if not already present).

### [HIGH] Budget Cap Not Enforced as a Gate *(carry-over, unresolved — day 44+)*

`BudgetTracker.is_over_budget()` is defined at `budget/tracker.py:61` but is **never called** before LLM API calls. Neither `cli/brief.py` nor `prediction/ensemble.py` reference `is_over_budget`. The $20/day cap is a reporting metric only — concurrent or stuck cron runs will exhaust quota without any gate.

### [HIGH] Model Cost 15–30× Above Documented Cap *(carry-over, unresolved)*

All three predictors hardcode the retired Opus model ID `claude-opus-4-20250514`:
- `prediction/oil_price.py:143`
- `prediction/ceasefire.py:116`
- `prediction/hormuz.py:118`

CLAUDE.md states "3 Sonnet calls ~$0.02/run". Each ensemble run makes 9 Opus calls (3 models × 3 temperatures). At current Opus pricing, actual cost is ~$0.27–$0.63/run. The documented budget headroom does not exist.

### [HIGH] `pytz` Missing from `pyproject.toml` *(carry-over, unresolved)*

DuckDB's `TIMESTAMPTZ` type requires `pytz` at query time. Columns in `runs`, `daily_scorecard`, `ops_events`, `llm_usage`, `crisis_events`, `backtest_runs` use `TIMESTAMPTZ`. On any fresh environment without `pytz` pre-installed, these tables raise `InvalidInputException` at query time, causing 17 test failures across `test_scorecard.py`, `test_llm_usage.py`, `test_ops_events.py`, `test_crisis_context_db.py`, and `test_phase1_critical.py`. Fix: add `"pytz>=2024.1"` to `pyproject.toml` dependencies.

### [MEDIUM] Silent Per-Source Ingestion Failures *(carry-over, partially improved)*

The outer `asyncio.gather()` for Google News, GDELT DOC, and Truth Social in `cli/brief.py` (lines ~866–884) still silently discards per-source exceptions — when a source returns an `Exception`, the `if isinstance(x, list)` check evaluates to `False` with no log entry. Operators cannot tell which source is degraded during a run.

### [MEDIUM] Architecture Drift — Agent Swarm Not Implemented *(carry-over, unresolved)*

The Phase 1 spec defines an `agents/` directory with `schemas.py`, `registry.py`, `router.py`, `runner.py`, and ~50 agent YAML prompts for a country→sub-actor hierarchy. The `agents/` directory is entirely absent. The project has pivoted to a 3-model ensemble, which is sound, but the design docs have not been updated, causing confusion for readers of the spec and plan.

### [MEDIUM] Architecture Drift — Spatial Layer Not Implemented *(carry-over, unresolved)*

`spatial/h3_utils.py`, `spatial/loader.py`, and the 4-resolution H3 model are absent. Dependencies `h3`, `searoute`, `shapely`, `sentence-transformers`, `websockets`, `google-cloud-bigquery` appear in CLAUDE.md but not in `pyproject.toml`. Frontend `package.json` has no `deck.gl`, `maplibre-gl`, `h3-js`, or `react-map-gl` (all listed in CLAUDE.md). The cascade engine uses abstract integer cell IDs, not real H3 cells.

### [MEDIUM] Missing Simulation Modules from Plan *(carry-over, unresolved)*

- `simulation/engine.py` (asyncio + heapq DES scheduler) — absent
- `simulation/circuit_breaker.py` (threshold-gated escalation with cooldowns) — absent

`backtest/engine.py` handles historical replay only; it does not replace live event-driven simulation as specified.

### [MEDIUM] Risk Limit $20 vs $50 Undocumented Discrepancy *(carry-over, unresolved)*

`config/risk.py` sets `daily_loss_limit = 50.0`. CLAUDE.md and `BudgetTracker` reference a $20/day cap. These govern different things (trading P&L vs LLM spend) but are never documented as such. Neither is enforced as a runtime gate.

### [LOW] Deprecated Model ID `claude-opus-4-20250514` *(carry-over, unresolved)*

The `20250514` release-date suffix is a retired identifier. The canonical ID is `claude-opus-4-8` (or `claude-sonnet-4-6` for cost-appropriate use). While the alias may still resolve, it should be migrated to avoid unexpected breakage.

### [LOW] `httpx` / Starlette `TestClient` Deprecation Warning *(carry-over)*

All test runs emit `StarletteDeprecationWarning: Using httpx with starlette.testclient is deprecated; install httpx2 instead.` Non-fatal today; will become a collection error in a future Starlette release.

### [LOW] CLAUDE.md Key Dependencies Out of Sync *(carry-over, unresolved)*

CLAUDE.md lists `h3 4.1+`, `searoute 1.3+`, `shapely 2.0+`, `sentence-transformers 3.4+`, `websockets 14.0+`, `google-cloud-bigquery 3.27+` as Key Dependencies — none appear in `pyproject.toml`. Conversely, `cryptography>=44.0` and `truthbrush>=0.2` are in `pyproject.toml` but absent from CLAUDE.md. `pytz` is required at runtime but absent from both.

### [LOW] `truthbrush` Not Installable in Standard Environment *(carry-over)*

`truthbrush>=0.2` is declared in `pyproject.toml` but the package is unavailable via pip. `test_truth_social.py` fails with `ModuleNotFoundError` on a fresh install. The library is an unofficial scraper with no stable API contract.

---

## Test Coverage Assessment

**Passing: 433 tests, 13 skipped** (requires `pytz` pre-installed; 17 tests fail without it). Coverage spans: schema, writer, cascade, world state, config, GDELT, Google News, EIA, Kalshi, Polymarket, prediction ensemble, calibration, recalibration, signal ledger, divergence, paper trade tracker, dashboard, scorecard, report card, backtest look-ahead guard, portfolio simulator, contracts, ops events, crisis context.

**Gaps:**
- No test covering `update_execution()` in `scoring/ledger.py` that would catch the `trade_id` parameter mismatch
- No concurrent-write stress test exposing the single-writer violation under simultaneous CLI + API load
- No test asserting `is_over_budget()` gates LLM calls (the gate does not exist)
- No test confirming per-source ingestion failures emit individual log entries
- No integration test running `brief.py` + FastAPI simultaneously on the same DuckDB file
- `agents/`, `spatial/`, DES engine unbuilt — no coverage expected

---

## Recommendations

1. **[URGENT] Fix `trade_id` parameter bug** — In `scoring/ledger.py:267`, replace the third list element from `position_id` to the `trade_id` local variable. Add a `trade_id` parameter to `update_execution()` if missing, and add a unit test that verifies the column is written correctly.

2. **[URGENT] Add `pytz` to `pyproject.toml`** — Add `"pytz>=2024.1"` to dependencies. Also align `cryptography` declared version with system-installed (`>=41.0` or upgrade to `>=44.0`).

3. **[HIGH] Enforce budget cap before LLM calls** — Add `if budget.is_over_budget(): raise RuntimeError(...)` (or degrade to fallbacks) in `brief.py` before invoking the three predictors.

4. **[HIGH] Switch predictors from Opus to Sonnet** — Replace `claude-opus-4-20250514` with `claude-sonnet-4-6` in `oil_price.py:143`, `ceasefire.py:116`, `hormuz.py:118`. This aligns cost with the $0.02/run documented in CLAUDE.md.

5. **[HIGH] Route all writes through `DbWriter`** — Inject `DbWriter` into the 10 violating modules. Highest-risk are `contracts/registry.py` (upsert on every brief run), `scoring/ledger.py`, and `scoring/tracker.py` (concurrent with FastAPI reads).

6. **[HIGH] Log per-source ingestion failures** — After the inner `asyncio.gather()` in `_fetch_gdelt_events()`, add: `if not isinstance(google_news, list): logger.warning("Google News failed: %s", google_news)` (and similarly for GDELT DOC and Truth Social).

7. **[MEDIUM] Document the $20 vs $50 cap distinction** — Add a comment in `config/risk.py` clarifying `daily_loss_limit` is a trading P&L cap, separate from LLM spend. Update CLAUDE.md to reference both explicitly.

8. **[LOW] Migrate to canonical model IDs** — Replace `claude-opus-4-20250514` with `claude-opus-4-8` or `claude-sonnet-4-6`.

9. **[LOW] Address `httpx` test warning** — Add `httpx2` to dev dependencies.

10. **[LOW] Update spec/plan docs** — Add a brief note acknowledging the agent-swarm and spatial layer are deferred to Phase 2, and the 3-model ensemble is the Phase 1 prediction layer.
