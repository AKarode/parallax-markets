# Parallax Health Check — 2026-07-01

**Status: YELLOW**

## Summary

The June 30 fix commit resolved 6 long-running bugs, bringing the test suite from 17 failed to **433 passed / 0 failed / 13 skipped** — the first clean run since early June. However, one fix claimed in that commit's message (`portfolio/simulator.py:85` P&L arithmetic) was **not actually applied**: the file is absent from the diff and the bug is confirmed present in HEAD. 13 mapping-policy tests remain permanently skipped, and the single-writer DuckDB pattern continues to be violated in 10+ production write paths.

---

## Repository State

```
HEAD:         a98b2d4  fix: resolve 6 long-running bugs from health check backlog (2026-06-30)
Tests:        433 passed | 0 failed | 13 skipped | 1 warning
              (was: 17 failed | 416 passed | 13 skipped as of 2026-06-30)
Code changes: 2 fix commits on 2026-06-30, nothing since
```

---

## Changes Since Last Report (2026-06-30)

**Fixed (commit `a98b2d4` + `e1649e4`):**
- `pyproject.toml` — replaced `cryptography>=44.0` (blocked fresh installs) with `pytz>=2024.1` (was missing, caused 17 test failures). All 17 previously-failing tests now pass.
- `scoring/ledger.py:267` — SQL param binding bug fixed: `position_id` was overwriting the `trade_id` COALESCE slot; replaced with `None`. Signal P&L records now record correctly.
- `simulation/cascade.py` — Division-by-zero guard added for `hormuz_daily_flow == 0`.
- `simulation/config.py` — Division-by-zero guard added for `reroute_distance_penalty_pct` property.
- `ingestion/oil_prices.py` — `HTTPStatusError` and `RequestError` now caught; EIA failures return `[]` instead of crashing the brief run.

**Claimed but NOT applied:**
- `portfolio/simulator.py:85` — The commit message states the position-closure arithmetic was fixed, but `portfolio/simulator.py` is absent from the commit's file diff (`a98b2d4 --stat` shows only 4 files changed, none of them `simulator.py`). The bug is confirmed present at HEAD.

---

## Issues Found

### CRITICAL

*(None — all prior CRITICAL items resolved.)*

---

### HIGH

- **[HIGH] `portfolio/simulator.py:85` — P&L arithmetic bug, commit message claimed fixed but NOT applied**
  Line 85: `cash += payout - fees + (pos["quantity"] * pos["entry_price"])`
  This adds back the original entry cost on top of the resolution payout, inflating every closed-trade P&L. The fix is to drop the `+ (pos["quantity"] * pos["entry_price"])` term; that capital was already subtracted when the position was opened.
  ```python
  # Current (bug):
  cash += payout - fees + (pos["quantity"] * pos["entry_price"])
  # Fix:
  cash += payout - fees
  ```
  The `pnl` local variable on line 84 is computed correctly (`payout - fees`); only the `cash` update is wrong. Every backtest and portfolio simulation run since this module was introduced has reported inflated returns.

- **[HIGH] Single-writer pattern violated in 10+ modules**
  `DbWriter` (`db/writer.py`) is correctly implemented with an `asyncio.Queue` but bypassed in all live production write paths. Concurrent writes from two of these callers will cause `database is locked` under any load. Current violators:
  - `ops/alerts.py:106` — synchronous `db_conn.execute()` inside `async DuckDBAlertSink.send()`; also blocks the asyncio event loop
  - `budget/tracker.py` — synchronous write on every LLM call
  - `scoring/ledger.py` — lines 225, 256 (inserts and `update_execution`)
  - `scoring/tracker.py` — lines ~516, 674, 746 (trade positions, orders, fills)
  - `scoring/prediction_log.py` — line 79
  - `scoring/scorecard.py` — line 23
  - `ingestion/crisis_ingester.py` — lines ~54, 79
  - `contracts/registry.py` — lines ~106, 116, 199
  - `backtest/runner.py` — lines 290–356 (backtest_runs and backtest_predictions)

- **[HIGH] 13 mapping-policy tests permanently skipped**
  All 13 skips are in `test_mapping_policy.py` (classes `TestDirectProxyDiscount`, `TestNearProxyDiscount`, `TestLooseProxyDiscount`, `TestProbabilityInversion`, `TestAboveThreshold`, `TestSortedByEffectiveEdge`, `TestDiscountFromHistory`). These cover the core proxy-class discount and edge-computation logic. No skip reason is documented. These tests have been skipped for 10+ days with no explanation or replacement.

---

### MEDIUM

- **[MEDIUM] `ops/alerts.py:106` — blocking DuckDB write inside `async` method**
  `DuckDBAlertSink.send()` is declared `async` but executes `self.db_conn.execute(...)` synchronously. This stalls the asyncio event loop on every alert write. Fix: run via `asyncio.get_event_loop().run_in_executor(None, lambda: self.db_conn.execute(...))` or route through `DbWriter`.

- **[MEDIUM] Staleness penalty not applied in `divergence/detector.py`**
  The `staleness_penalty_applied` and `penalty_factor` columns exist in the DB schema and are mentioned in session notes, but `detector.py` contains no staleness logic. Stale-context predictions (e.g., based on news from 24h ago) generate the same signal strength as fresh ones. This could produce trades on outdated market assessments.

- **[MEDIUM] `requires-python = ">=3.11"` — looser than spec**
  CLAUDE.md and the plan spec both require Python 3.12. The current pin is `>=3.11`. No 3.11-incompatible syntax was found, so this is low-risk, but a discrepancy worth noting for reproducibility.

---

### LOW

- **[LOW] 13 skipped mapping-policy tests need skip reason or replacement**
  Tests are skipped with no `reason=` argument. Either document why they're skipped or restore them. The mapping-policy module is in the critical signal path.

- **[LOW] No linter or formatter enforced**
  No `ruff`, `black`, or `pre-commit` hook. Code style is consistent by convention only. One inconsistency observed: `backtest/runner.py` uses direct `conn.execute()` inserts inside a synchronous class while the rest of the codebase uses async patterns.

- **[LOW] `httpx` / Starlette deprecation warning**
  Tests emit: `StarletteDeprecationWarning: Using httpx with starlette.testclient is deprecated; install httpx2 instead.` Not breaking, but should be tracked.

- **[LOW] `truthbrush>=0.2` unlocked minimum-version pin**
  `truthbrush` is a third-party library with a very loose minimum pin. If the upstream API changes in a minor bump, Truth Social ingestion could silently break.

---

## Spec/Plan Consistency

| Area | Status | Notes |
|---|---|---|
| DB schema (20+ tables) | ✓ Compliant | All plan tables plus trading/backtest tables added |
| Single-writer topology | ✗ Violated | `DbWriter` exists but 10+ modules bypass it |
| Cascade engine (6 rules) | ✓ Improved | Division-by-zero guards now in place; `circuit_breaker.py` still absent (intentional pivot) |
| GDELT ingestion | ⚠ Partial | GDELT DOC API used instead of BigQuery; semantic dedup not implemented |
| Agent swarm (50 agents) | ✗ Deferred | Intentional pivot — 3 monolithic LLM predictors instead |
| Eval framework | ⚠ Partial | `calibration.py` covers metrics; no per-agent eval harness |
| Frontend dashboard | ✓ Evolved | React SPA with 9 components; deck.gl/H3 geospatial deferred |
| Paper trading (Kalshi) | ✓ Compliant | Full order lifecycle, RSA-PSS auth, sandbox/production separation |
| Budget cap ($20/day) | ✓ Compliant | `BudgetTracker` functional |
| `portfolio/simulator.py` P&L | ✗ Bug | Position-closure adds entry capital twice — commit claimed fixed but was not applied |
| `ledger.py` UPDATE correctness | ✓ Fixed | `trade_id` binding bug resolved in June 30 commit |
| `pyproject.toml` dependencies | ✓ Improved | `pytz` added, `cryptography>=44.0` removed; all tests pass |

---

## Dependency Snapshot

| Package | `pyproject.toml` | Status |
|---|---|---|
| duckdb | `>=1.2` | OK |
| pytz | `>=2024.1` | OK — added in June 30 fix |
| fastapi | `>=0.115` | OK |
| anthropic | `>=0.52` | OK |
| truthbrush | `>=0.2` | Loose pin — monitor for upstream changes |
| httpx | `>=0.28` | OK but deprecation warning in tests |

---

## Recommendations (Priority Order)

1. **Immediate** — Fix `portfolio/simulator.py:85`: change `cash += payout - fees + (pos["quantity"] * pos["entry_price"])` to `cash += payout - fees`. Every backtest run is currently reporting inflated P&L. The commit message said this was done; it was not.

2. **Short-term** — Fix `ops/alerts.py:106`: route the synchronous `db_conn.execute()` through `run_in_executor` or `DbWriter` to avoid stalling the event loop on every alert write.

3. **Short-term** — Resolve the 13 skipped mapping-policy tests: either add `reason="..."` documenting why they're deferred, or restore them. They cover the core proxy-class discount logic that drives trade sizing.

4. **Short-term** — Add staleness penalty logic to `divergence/detector.py` so predictions based on stale context generate appropriately discounted signals.

5. **Medium-term** — Wire the 10 single-writer violators through `DbWriter`. Priority order: `ops/alerts.py` (async-blocking), `scoring/ledger.py` (signal integrity), `budget/tracker.py` (called on every LLM call), then the rest.

6. **Medium-term** — Tighten `requires-python` to `>=3.12` to match CLAUDE.md spec and prevent accidental use with 3.11 in CI or deployment.

7. **Low** — Pin `truthbrush` to a specific minor version or add a changelog watch to catch breaking API changes.
