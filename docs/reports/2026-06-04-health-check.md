# Parallax Health Check — 2026-06-04

**Status: YELLOW**

## Summary

No code changes since the 2026-06-03 report — the only commit since then was the health check document itself. All HIGH/MEDIUM issues from that report remain unresolved. One new observation is added: `config/risk.py` (`RiskLimits`) hardcodes `daily_loss_limit = 50.0` while CLAUDE.md and the brief CLI advertise a $20/day cap, creating an undocumented discrepancy. The unresolved budget enforcement bug (cap is measured but never checked before LLM calls) makes both values academic.

---

## Issues Found

### [HIGH] DuckDB Single-Writer Violations *(carry-over, unresolved — day 40+)*

The spec mandates all writes via `DbWriter`'s `asyncio.Queue`. The following modules bypass it with direct `conn.execute()` writes:

- **`scoring/ledger.py`** — `INSERT`/`UPDATE signal_ledger` (lines 227, 258)
- **`scoring/tracker.py`** — `INSERT`/`UPDATE trade_positions`, `INSERT`/`UPDATE trade_orders`, `INSERT INTO trade_fills` (lines 518, 462, 674, 713, 746)
- **`scoring/prediction_log.py`** — `INSERT INTO prediction_log` (line 81)
- **`scoring/scorecard.py`** — `INSERT INTO daily_scorecard` with ON CONFLICT (line 21)
- **`ops/alerts.py`** — `INSERT INTO ops_events` (line 106)
- **`budget/tracker.py`** — `INSERT INTO llm_usage` (line 43)
- **`backtest/runner.py`** — `INSERT`/`UPDATE backtest_runs`, `INSERT`/`UPDATE backtest_predictions` (lines 290, 308, 329, 356)

Concurrent CLI (cron) + FastAPI execution creates a real write-write race. Tests use per-test in-memory connections, masking the violation.

### [HIGH] Budget Cap Not Enforced as a Gate *(carry-over, unresolved — day 2)*

`BudgetTracker.is_over_budget()` is defined in `budget/tracker.py:61` but is **never called** before making LLM API calls. Searching `cli/brief.py` for any budget gate (`is_over_budget`, `budget.*check`) returns zero matches. The `$20/day` cap is a reporting metric only — a stuck cron job or repeated manual invocations will burn through the Anthropic quota with no enforcement.

### [HIGH] Risk Limit Inconsistency — $20 vs $50 Daily Cap *(new)*

`config/risk.py:27` sets `daily_loss_limit = 50.0` as the default `RiskLimits`. CLAUDE.md and the `BudgetTracker` both reference a $20/day hard cap. There is no code that ties `RiskLimits.daily_loss_limit` to `BudgetTracker._daily_cap` — they are separate, unlinked values. Neither is enforced as a gate (see above), but they are semantically contradictory: one caps LLM spend, the other caps trading losses, and neither is explicitly documented as such in either file or in CLAUDE.md.

### [HIGH] Model Cost Mismatch vs Budget Cap *(carry-over, unresolved)*

All three predictors hardcode `claude-opus-4-20250514`:
- `prediction/oil_price.py:143`
- `prediction/ceasefire.py:116`
- `prediction/hormuz.py:118`

CLAUDE.md states "3 Sonnet calls ~$0.02/run" — actual cost with Opus is ~$0.30–$0.60/run, roughly 15–30× higher. The claim of "massive headroom" under a $20/day cap is inaccurate at Opus pricing and current call volume.

### [MEDIUM] Silent Ingestion Source Failures *(carry-over, unresolved)*

`cli/brief.py:_fetch_gdelt_events()` uses `asyncio.gather(..., return_exceptions=True)` and silently discards failed sources. No `logger.warning` is emitted when Google News, GDELT, or Truth Social throws an exception. Operators have no visibility into which sources are degraded.

### [MEDIUM] Resolution Edge Case at price=0.5 *(new)*

`scoring/resolution.py:76–77`: `model_was_correct` is evaluated as:

```sql
WHEN signal = 'BUY_YES' AND ? > 0.5 THEN true   -- strict greater-than
WHEN signal = 'BUY_NO'  AND ? <= 0.5 THEN true  -- less-than-or-equal
```

When `resolution_price = 0.5` (a push / no-event outcome): `BUY_NO` signals are marked **correct** and `BUY_YES` signals are marked **incorrect**. A push at 0.5 is ambiguous — both sides were wrong — but this asymmetry favours NO-bias signals in calibration metrics. Kalshi/Polymarket rarely settle at exactly 0.5, but the boundary condition is undocumented and the scoring behaviour is unintuitive.

### [MEDIUM] Architecture Drift — Agent Swarm Not Implemented *(carry-over, unresolved)*

The Phase 1 spec and plan define `agents/schemas.py`, `agents/registry.py`, `agents/router.py`, `agents/runner.py` for a 50-agent hierarchy. The `agents/` directory is entirely absent. The project has sound reasons for the 3-model pivot, but the spec and plan have not been updated to reflect it.

### [MEDIUM] Architecture Drift — Spatial Layer Not Implemented *(carry-over, unresolved)*

The spec defines `spatial/h3_utils.py` and a 4-resolution H3 model. The `spatial/` directory does not exist. Dependencies `h3`, `searoute`, `shapely` appear in CLAUDE.md's Key Dependencies section but are absent from `pyproject.toml`. `frontend/package.json` also lacks `deck.gl`, `maplibre-gl`, `h3-js`, and `react-map-gl` — all listed in CLAUDE.md's Technology Stack. The cascade engine uses abstract string cell identifiers, not real H3 cells.

### [MEDIUM] Missing Simulation Modules from Plan *(carry-over, unresolved)*

- `simulation/engine.py` — Discrete Event Simulation scheduler (asyncio + heapq) not present
- `simulation/circuit_breaker.py` — Threshold-gated LLM activation with cooldown not present

`backtest/engine.py` handles historical replay only, not live event-driven simulation.

### [LOW] Outdated Model ID `claude-opus-4-20250514` *(carry-over, unresolved)*

The `20250514` release-date suffix is a retired identifier. As of June 2026 the canonical ID is `claude-opus-4-8`. Verify the old string still resolves at the Anthropic API, or migrate to `claude-opus-4-8` (or cost-appropriate `claude-sonnet-4-6`).

### [LOW] CLAUDE.md Key Dependencies Out of Sync *(carry-over, unresolved)*

CLAUDE.md lists `h3 4.1+`, `searoute 1.3+`, `shapely 2.0+`, `sentence-transformers 3.4+`, `websockets 14.0+`, `google-cloud-bigquery 3.27+` as Key Dependencies. None appear in `pyproject.toml`. Conversely, `cryptography>=44.0` and `truthbrush>=0.2` are in `pyproject.toml` but missing from CLAUDE.md. The discrepancy has been present since at least 2026-04-01.

### [LOW] `truthbrush` Dependency Fragile *(carry-over, unresolved)*

`truthbrush>=0.2` is an unofficial scraper with no stable API contract. It can break silently on site changes. Combined with the per-source silent failure mode, Truth Social outages will go undetected.

---

## Test Coverage Assessment

**Strong (43 test files):** schema, writer, cascade, world state, config, GDELT, Google News, EIA, Kalshi, Polymarket, prediction ensemble, calibration, recalibration, signal ledger, divergence, paper trade tracker, dashboard, scorecard, report card, backtest look-ahead guard, portfolio simulator, contracts, ops events.

**Gaps:**
- No concurrent-write stress test exposing single-writer violations
- No test asserting `is_over_budget()` gates LLM calls (the gate does not exist — a test would fail)
- No test covering the `resolution_price = 0.5` boundary in `scoring/resolution.py`
- No test confirming per-source ingestion failures are logged
- No integration test running `brief.py` + FastAPI simultaneously
- `agents/`, `spatial/`, and DES engine unbuilt — no coverage needed there
- `test_truth_social.py` exists; `truthbrush` may not be installable in CI

---

## Recommendations

1. **[URGENT] Enforce budget cap before LLM calls** — Add a `budget.is_over_budget()` check in `brief.py` before invoking the three predictors. Degrade to fallback predictions or raise a hard stop. Without this, the $20/day cap is decorative.

2. **[URGENT] Route all writes through `DbWriter`** — Inject `DbWriter` into `SignalLedger`, `PaperTradeTracker`, `PredictionLogger`, `DuckDBAlertSink`, `BudgetTracker`, `compute_daily_scorecard()`, and `BacktestRunner`. The single-writer pattern only protects data integrity if it is universal.

3. **[HIGH] Align and document the two daily caps** — Decide whether `RiskLimits.daily_loss_limit` and `BudgetTracker._daily_cap` are distinct concepts (trading losses vs LLM spend) or redundant. Document the distinction in both files and in CLAUDE.md. Set both to consistent values.

4. **[HIGH] Log per-source ingestion failures** — After `asyncio.gather(..., return_exceptions=True)`, iterate results and emit `logger.warning("Source %s failed: %s", name, exc)` for each `Exception` instance. One line.

5. **[MEDIUM] Fix `resolution_price = 0.5` boundary** — Change `BUY_NO` condition from `<= 0.5` to `< 0.5`, and treat exactly 0.5 as NULL / inconclusive in both `model_was_correct` and `proxy_was_aligned`. Add a test.

6. **[MEDIUM] Reconcile model vs. budget** — Either switch to `claude-sonnet-4-6` (matching CLAUDE.md's cost claim) or update the budget model to Opus pricing and enforce it. Update CLAUDE.md.

7. **[MEDIUM] Update spec/plan to reflect the pivot** — Add a brief note acknowledging the agent-swarm scope was narrowed to a 3-model ensemble and the spatial layer is deferred. Prevents future confusion.

8. **[LOW] Migrate to current model ID** — Replace `claude-opus-4-20250514` with `claude-opus-4-8` (or `claude-sonnet-4-6`) in all three predictor files and `ensemble.py`.

9. **[LOW] Prune CLAUDE.md dependencies** — Remove uninstalled/unbuilt deps (h3, searoute, shapely, sentence-transformers, websockets, google-cloud-bigquery, deck.gl, maplibre-gl, react-map-gl, h3-js). Add actually-used deps (cryptography, truthbrush).
