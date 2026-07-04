# Parallax Health Check — 2026-07-04

**Status: YELLOW**

## Summary

No production code changes since `a98b2d4` (2026-06-30). Tests hold at 433 passed / 0 failed / 13 skipped, with 4 collection errors unchanged from yesterday. The two HIGH issues persist for a 4th consecutive report: the `portfolio/simulator.py:85` P&L double-counting bug and the DuckDB single-writer constraint violated across 16 files. No new issues found.

---

## Repository State

```
HEAD:         0822414  chore: daily health check 2026-07-03 (YELLOW)
Tests:        433 passed | 0 failed | 13 skipped | 4 collection errors
              (unchanged from 2026-07-03)
Project mode: Research concluded — postmortem committed 2026-07-01
```

---

## Changes Since Last Report (2026-07-03)

No new commits since the July 3 health check report. All issues are carry-forwards.

---

## Issues Found

### HIGH

- **[HIGH] `portfolio/simulator.py:85` — P&L double-counting bug (4th consecutive report)**

  Lines 82–85 (confirmed unchanged at HEAD):
  ```python
  fees = pos["quantity"] * entry_price * FEE_RATE
  pnl = payout - fees                                         # line 84: omits entry cost
  cash += payout - fees + (pos["quantity"] * pos["entry_price"])  # line 85: returns only entry_price, not effective cost
  ```

  Two compounding errors:
  1. `pnl` does not subtract the cost basis, so every `closed_trades` record overstates profit.
  2. `cash` restores only `quantity × entry_price`, not the effective cost including entry fees/slippage, silently absorbing those as phantom profit at close.

  Correct close-out:
  ```python
  cost_basis = pos["quantity"] * pos["entry_price"] * (1 + FEE_RATE + SLIPPAGE_RATE)
  pnl = payout - fees - cost_basis
  cash += payout - fees + cost_basis
  ```

  Impact: postmortem's −$0.35 backtest figure was computed with this engine. The direction (no edge) is likely correct, but the absolute P&L number is unreliable. Fix is a two-line change.

- **[HIGH] DuckDB single-writer constraint violated across 16 production files**

  The spec (Section 9) requires all writes to pass through a single `asyncio.Queue` → `db_writer` task. `DbWriter` exists and is tested, but no production write path uses it. The following files call `conn.execute()` with INSERT/UPDATE/DELETE or DDL directly:

  | File | Violation |
  |------|-----------|
  | `scoring/ledger.py` | INSERT + UPDATE to `signal_ledger` |
  | `scoring/prediction_log.py` | INSERT to `prediction_log` |
  | `scoring/resolution.py` | UPDATE to `signal_ledger`, `trade_positions` |
  | `scoring/scorecard.py` | INSERT/REPLACE to `daily_scorecard` |
  | `scoring/tracker.py` | INSERT to `trade_orders`, `trade_fills`, `trade_positions` |
  | `ops/alerts.py` | INSERT to `ops_events` |
  | `ingestion/crisis_ingester.py` | INSERT to `crisis_events` |
  | `cli/brief.py` | INSERT to `runs`, `market_prices` |
  | `budget/tracker.py` | INSERT to `llm_usage` |
  | `backtest/look_ahead_guard.py` | DDL (CREATE/DROP VIEW) |
  | `backtest/runner.py` | INSERT to `backtest_runs`, `backtest_predictions` |
  | `db/schema.py` | DDL + data migrations |
  | `contracts/registry.py` | INSERT/UPDATE to `contract_registry` |

  Risk is low in archival/single-process mode. Risk resurfaces if any background task or second process is introduced.

### MEDIUM

- **[MEDIUM] 4 test files fail to collect — `numpy`/`pandas` not in `[dev]` extras**

  `test_bench_forecast.py`, `test_calibration_metrics.py`, `test_recalibrators.py`, and `test_selective.py` import `numpy`, `pandas`, and `scikit-learn`, which live in the `[bench]` optional group only. Running `pytest` with `pip install -e ".[dev]"` aborts collection before any test runs.

  Fix: add `numpy`, `pandas`, `scikit-learn` to `[dev]` extras in `pyproject.toml`, or document that the full suite requires `pip install -e ".[dev,bench]"`.

### LOW

- **[LOW] `requires-python = ">=3.11"` in `pyproject.toml` vs. spec's `>=3.12`**

  Design spec and CLAUDE.md both specify Python 3.12. Runtime container runs 3.11. Code works due to `from __future__ import annotations` backport for union-type syntax, but the declared floor is permissive relative to the stated requirement.

### INFO

- **[INFO] Architecture drift from original Phase 1 spec is intentional and documented**

  The Phase 1 design spec describes an H3 hex-map cascade simulator with 50 LLM country/sub-actor agents. The implemented system is a 3-model prediction market edge-finder. Modules in the spec but absent from the codebase: `agents/`, `spatial/`, `eval/`, `api/`. This pivot is captured in CLAUDE.md and the project postmortem. Not a defect.

- **[INFO] Project is in archival/concluded state**

  Postmortem committed 2026-07-01. Edge thesis falsified across four experiments. No new production code expected. Health checks now serve an archival verification function only.

---

## Recommendations

1. **Fix `portfolio/simulator.py:85`** — two-line correction for archival accuracy of the postmortem P&L figure. Clears the longest-running HIGH finding.
2. **Add `numpy`/`pandas`/`scikit-learn` to `[dev]`** in `pyproject.toml` so plain `pytest` covers the full test suite without hidden collection failures.
3. **DbWriter wiring** — low-priority in archival mode, but document in any future reactivation plan: the single-writer queue was never connected to production write paths.
