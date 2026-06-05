# Parallax Health Check — 2026-06-05

**Status: YELLOW**

## Summary

The codebase is structurally sound and test coverage is broad — 433 tests pass (13 skipped) after installing `pytz`, which is a missing undeclared dependency that causes 17 test failures on a fresh environment. All carry-over HIGH issues from yesterday remain unresolved: the DuckDB single-writer pattern is violated by 7+ modules writing directly, the budget cap is never enforced as a gate, and all three predictors still use the deprecated model ID `claude-opus-4-20250514` at Opus pricing ($0.30–$0.60/run vs the advertised $0.02/run). The one new finding today is that `pytz` is required by DuckDB's `TIMESTAMPTZ` column type at query time but is absent from `pyproject.toml`, causing a deterministic `InvalidInputException` on any environment without `pytz` pre-installed.

---

## Issues Found

### [HIGH] DuckDB Single-Writer Violations *(carry-over, unresolved — day 41+)*

The spec mandates all writes via `DbWriter`'s `asyncio.Queue`. The following modules bypass it with direct `conn.execute()` writes, creating real write-write races when the CLI cron and FastAPI run concurrently:

- **`scoring/ledger.py`** — `INSERT`/`UPDATE signal_ledger` (lines 225, 256)
- **`scoring/tracker.py`** — `INSERT`/`UPDATE trade_positions`, `INSERT trade_orders`, `INSERT trade_fills`
- **`scoring/prediction_log.py`** — `INSERT INTO prediction_log` (line 79)
- **`scoring/scorecard.py`** — `INSERT INTO daily_scorecard` with ON CONFLICT
- **`ops/alerts.py`** — `INSERT INTO ops_events` (line 106)
- **`budget/tracker.py`** — `INSERT INTO llm_usage` (line 43)
- **`backtest/runner.py`** — `INSERT`/`UPDATE backtest_runs`, `INSERT`/`UPDATE backtest_predictions`

Tests use per-test in-memory connections so the violation is invisible in CI. The `DbWriter` class exists in `db/writer.py` but is not injected into any of these modules.

### [HIGH] Budget Cap Not Enforced as a Gate *(carry-over, unresolved — day 43+)*

`BudgetTracker.is_over_budget()` is defined at `budget/tracker.py:61` but is **never called** before making LLM API calls. Searching all of `cli/brief.py` and `prediction/ensemble.py` for `is_over_budget` returns zero matches. The `$20/day` cap is a reporting metric only — repeated cron runs or stuck jobs will burn quota with no enforcement.

### [HIGH] Model Cost Mismatch vs Budget Cap *(carry-over, unresolved)*

All three predictors hardcode `claude-opus-4-20250514`:
- `prediction/oil_price.py:143`
- `prediction/ceasefire.py:116`
- `prediction/hormuz.py:118`

CLAUDE.md states "3 Sonnet calls ~$0.02/run". Each ensemble call makes 3 concurrent LLM calls, so a full run is 9 Opus API calls (3 models × 3 temperatures). At Opus pricing (~$0.03–$0.07/call), actual cost is approximately $0.27–$0.63/run — 15–30× higher than the documented claim.

### [HIGH] `pytz` Missing from `pyproject.toml` — Causes 17 Test Failures on Fresh Environments *(new)*

DuckDB's `TIMESTAMPTZ` type requires `pytz` at query time. Nine columns across `runs`, `daily_scorecard`, `ops_events`, `llm_usage`, `crisis_events`, `backtest_runs` use `TIMESTAMPTZ`. On any environment where `pytz` is not pre-installed, any query touching these tables raises:

```
_duckdb.InvalidInputException: Invalid Input Error: Required module 'pytz' failed to import
```

This causes 17 test failures in `test_scorecard.py`, `test_llm_usage.py`, `test_ops_events.py`, `test_crisis_context_db.py`, and `test_phase1_critical.py`. The fix is a single line in `pyproject.toml`: add `"pytz>=2024"` to the `dependencies` list. The installed version of `cryptography` (41.0.7) also violates the declared `>=44.0` requirement; both are undeclared or mismatched environment-level dependencies.

### [MEDIUM] Silent Per-Source Ingestion Failures *(carry-over — partially improved)*

`_fetch_gdelt_events()` in `cli/brief.py` now logs failures at `ERROR` level for the outer data fetches (line 578: `logger.error("Data fetch %d failed: %s", i, result)`). However, the inner `asyncio.gather()` for Google News, GDELT DOC, and Truth Social (lines 866–884) still silently discards per-source exceptions — when `google_news`, `gdelt_events`, or `truth_events` is an `Exception` instance, the branch `if isinstance(x, list)` simply evaluates to `False` with no log entry. Operators cannot tell which source is degraded during a run.

### [MEDIUM] Architecture Drift — Agent Swarm Not Implemented *(carry-over, unresolved)*

The Phase 1 spec and plan define a `agents/` directory with `schemas.py`, `registry.py`, `router.py`, `runner.py`, and ~50 agent YAML prompts for a country→sub-actor hierarchy. The `agents/` directory is entirely absent. The project has pivoted to a 3-model ensemble approach, which is a sound product decision, but the spec and plan have not been updated to reflect it, causing ongoing confusion for anyone reading the design documents.

### [MEDIUM] Architecture Drift — Spatial Layer Not Implemented *(carry-over, unresolved)*

The spec defines `spatial/h3_utils.py` and a 4-resolution H3 model (`ocean`, `regional`, `chokepoint`, `infrastructure`). The `spatial/` directory is absent. Dependencies `h3`, `searoute`, `shapely` appear in CLAUDE.md's Key Dependencies but are absent from `pyproject.toml`. The frontend's `package.json` lacks `deck.gl`, `maplibre-gl`, `h3-js`, and `react-map-gl` — all listed in CLAUDE.md's Technology Stack. The cascade engine uses abstract integer cell IDs, not real H3 cells.

### [MEDIUM] Missing Simulation Modules from Plan *(carry-over, unresolved)*

- `simulation/engine.py` — Discrete Event Simulation scheduler (asyncio + heapq) not present
- `simulation/circuit_breaker.py` — Threshold-gated LLM activation with escalation cooldown not present

`backtest/engine.py` handles historical replay only and does not substitute for live event-driven simulation as described in the spec.

### [MEDIUM] Risk Limit Inconsistency — $20 vs $50 Daily Cap *(carry-over, unresolved)*

`config/risk.py` sets `daily_loss_limit = 50.0` as the default `RiskLimits`. CLAUDE.md and `BudgetTracker` both reference a $20/day hard cap. The two values govern different things (trading losses vs LLM spend) but are never documented as such. Neither is enforced as a gate.

### [LOW] Deprecated Model ID `claude-opus-4-20250514` *(carry-over, unresolved)*

The `20250514` release-date suffix is a retired identifier. The canonical ID as of June 2026 is `claude-opus-4-8` (or for cost-appropriate use, `claude-sonnet-4-6`). While the old string may still resolve via Anthropic's alias system, it should be migrated to avoid unexpected breakage.

### [LOW] `httpx` / Starlette `TestClient` Deprecation Warning *(new)*

All test runs emit:
```
StarletteDeprecationWarning: Using `httpx` with `starlette.testclient` is deprecated; install `httpx2` instead.
```

This is a non-fatal warning from FastAPI's test client. It does not cause test failures today but will become an error in a future Starlette release. Add `"httpx2"` to `dev` dependencies and remove `"httpx"` from test imports, or pin `starlette` to a compatible version.

### [LOW] CLAUDE.md Key Dependencies Out of Sync *(carry-over, unresolved)*

CLAUDE.md lists `h3 4.1+`, `searoute 1.3+`, `shapely 2.0+`, `sentence-transformers 3.4+`, `websockets 14.0+`, `google-cloud-bigquery 3.27+` as Key Dependencies. None appear in `pyproject.toml`. Conversely, `cryptography>=44.0` and `truthbrush>=0.2` are in `pyproject.toml` but absent from CLAUDE.md. `pytz` is required at runtime but absent from both.

### [LOW] `truthbrush` Module Not Installable in Test Environment *(carry-over)*

`truthbrush>=0.2` is declared in `pyproject.toml` and used in `ingestion/truth_social.py`, but the package is not available in the standard environment (`pip show truthbrush` returns nothing despite the package being listed as installed). `test_truth_social.py` fails with `ModuleNotFoundError` on a fresh install. The library is an unofficial scraper with no stable API contract; it can break silently on site changes.

---

## Test Coverage Assessment

**Passing: 433 tests pass, 13 skipped** (after `pytz` install). Full test suite covers: schema, writer, cascade, world state, config, GDELT, Google News, EIA, Kalshi, Polymarket, prediction ensemble, calibration, recalibration, signal ledger, divergence, paper trade tracker, dashboard, scorecard, report card, backtest look-ahead guard, portfolio simulator, contracts, ops events, truth social (conditional on `truthbrush`), crisis context.

**Gaps:**
- No concurrent-write stress test exposing the single-writer violation under simultaneous CLI + API load
- No test asserting `is_over_budget()` gates LLM calls (the gate does not exist — such a test would fail)
- No test covering `resolution_price = 0.5` boundary behavior in `scoring/resolution.py`
- No test confirming per-source ingestion failures emit individual log entries
- No integration test running `brief.py` + FastAPI simultaneously on the same DuckDB file
- `agents/`, `spatial/`, DES engine unbuilt — no coverage expected there

---

## Recommendations

1. **[URGENT] Add `pytz` to `pyproject.toml` dependencies** — One line: `"pytz>=2024.1"`. Without it, 17 tests fail deterministically on any environment without `pytz` pre-installed. Also declare `cryptography>=41.0` to match the system-installed version or upgrade to `>=44.0`.

2. **[URGENT] Enforce budget cap before LLM calls** — Add `if budget.is_over_budget(): raise RuntimeError("Daily budget exceeded")` or degrade to fallbacks in `brief.py` before invoking the three predictors. The $20/day cap is currently decorative.

3. **[HIGH] Route all writes through `DbWriter`** — Inject `DbWriter` into `SignalLedger`, `PaperTradeTracker`, `PredictionLogger`, `DuckDBAlertSink`, `BudgetTracker`, `compute_daily_scorecard()`, and `BacktestRunner`. The single-writer pattern only protects data integrity if it is universal.

4. **[HIGH] Log per-source ingestion failures individually** — In `_fetch_gdelt_events()`, after the inner `asyncio.gather()`, add: `if not isinstance(google_news, list): logger.warning("Google News failed: %s", google_news)` (and similarly for GDELT and Truth Social). One line per source.

5. **[HIGH] Switch predictors from Opus to Sonnet** — Replace `claude-opus-4-20250514` with `claude-sonnet-4-6` in all three predictors and `ensemble.py`. This reduces per-run cost from $0.27–$0.63 to the ~$0.02 documented in CLAUDE.md and aligns with the stated $20/day budget.

6. **[MEDIUM] Reconcile and document daily caps** — Add a comment in `config/risk.py` clarifying that `daily_loss_limit` is a trading P&L cap, separate from LLM spend. Update CLAUDE.md to reference both caps explicitly.

7. **[MEDIUM] Fix `resolution_price = 0.5` boundary in `scoring/resolution.py`** — Change the `BUY_NO` condition from `<= 0.5` to `< 0.5`, and treat exactly 0.5 as NULL/inconclusive in `model_was_correct` and `proxy_was_aligned`. Add a test.

8. **[LOW] Migrate to current model ID** — Replace `claude-opus-4-20250514` with `claude-opus-4-8` or `claude-sonnet-4-6` to avoid dependency on a retired alias string.

9. **[LOW] Address `httpx` test warning** — Add `httpx2` to dev dependencies or pin `starlette` to suppress the deprecation warning before it becomes a collection error.

10. **[LOW] Update spec/plan to reflect the pivot** — Add a brief note in `docs/superpowers/specs/2026-03-30-parallax-phase1-design.md` and the plan acknowledging the agent-swarm and spatial layer are deferred to Phase 2, and the 3-model ensemble is the Phase 1 prediction layer.
