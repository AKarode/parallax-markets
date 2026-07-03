# Parallax Health Check — 2026-07-03

**Status: YELLOW**

## Summary

No production code changes since `a98b2d4` (2026-06-30). Tests hold at 433 passed / 0 failed / 13 skipped, but 4 additional test files fail to collect due to missing `numpy`/`pandas` in `[dev]` extras. The two HIGH issues flagged in the previous two reports remain unresolved: the `portfolio/simulator.py:85` P&L double-counting bug (3rd consecutive report) and the DuckDB single-writer constraint violated across 16 production files.

---

## Repository State

```
HEAD:         e8dfb1e  chore: daily health check 2026-07-02 (YELLOW)
Tests:        433 passed | 0 failed | 13 skipped | 4 collection errors
              (unchanged from 2026-07-02)
Project mode: Research concluded — postmortem committed 2026-07-01
```

---

## Changes Since Last Report (2026-07-02)

No new commits since the July 2 health check report. All issues are carry-forwards.

---

## Issues Found

### HIGH

- **[HIGH] `portfolio/simulator.py:85` — P&L double-counting bug (3rd consecutive report)**

  Line 85:
  ```python
  cash += payout - fees + (pos["quantity"] * pos["entry_price"])
  ```
  Also line 84:
  ```python
  pnl = payout - fees
  ```

  Two problems compound here:
  1. `pnl` at line 84 does not subtract entry cost, so every `closed_trades` record overstates actual profit.
  2. `cash` at line 85 adds back `quantity * entry_price`, but positions were opened at `effective_price = entry_price * (1 + FEE_RATE + SLIPPAGE_RATE)`. Only `entry_price * quantity` is returned, silently absorbing the entry slippage/fee as phantom profit on close.

  Correct close-out:
  ```python
  cost_basis = pos["quantity"] * pos["entry_price"] * (1 + FEE_RATE + SLIPPAGE_RATE)
  pnl = payout - fees - cost_basis
  cash += payout - fees + cost_basis
  ```

  Impact: every closed-position P&L is overstated, inflating the equity curve. The postmortem's −$0.35 backtest result used this engine. The direction (no edge) is likely correct, but the specific number is unreliable.

  The June 30 commit (`a98b2d4`) message claimed this was fixed; the diff did not include `portfolio/simulator.py`. Bug remains at HEAD.

- **[HIGH] DuckDB single-writer constraint violated across 16 production files**

  The spec (Section 9) requires all writes to pass through a single `asyncio.Queue` → `db_writer` task. `DbWriter` exists (`db/writer.py`) and is tested, but is not wired into any production write path. All 16 files below call `conn.execute()` directly with INSERT/UPDATE/DELETE:

  | File | Violation type |
  |------|---------------|
  | `scoring/ledger.py` | INSERT + UPDATE to `signal_ledger` |
  | `scoring/prediction_log.py` | INSERT to `prediction_log` |
  | `scoring/resolution.py` | UPDATE to `signal_ledger`, `trade_positions` |
  | `scoring/scorecard.py` | INSERT/REPLACE to `daily_scorecard` |
  | `scoring/tracker.py` | INSERT to `trade_orders`, `trade_fills`, `trade_positions` |
  | `portfolio/simulator.py` | (reads only; listed for completeness) |
  | `ops/alerts.py` | INSERT to `ops_events` |
  | `ingestion/crisis_ingester.py` | INSERT to `crisis_events` |
  | `cli/brief.py` | INSERT to `runs`, `market_prices`, etc. |
  | `budget/tracker.py` | INSERT to `llm_usage` |
  | `backtest/look_ahead_guard.py` | DDL (CREATE TABLE) |
  | `backtest/runner.py` | INSERT to `backtest_runs`, `backtest_predictions` |
  | `db/schema.py` | DDL + data migrations |
  | `dashboard/app.py` | (reads only) |
  | `contracts/registry.py` | INSERT/UPDATE to `contract_registry` |
  | `main.py` | (reads only) |

  Risk in archival mode is low (single process, no concurrent writers in practice). Risk resurfaces if any background task or second process is added.

### MEDIUM

- **[MEDIUM] 4 test files fail to collect — `numpy`/`pandas` not in `[dev]` extras**

  `test_bench_forecast.py`, `test_calibration_metrics.py`, `test_recalibrators.py`, and `test_selective.py` import `numpy`, `pandas`, and `scikit-learn`, which are in the `[bench]` optional group only. Running `pytest` with a plain `pip install -e ".[dev]"` aborts collection before reaching any test:

  ```
  ERROR tests/test_bench_forecast.py — ModuleNotFoundError: No module named 'pandas'
  ERROR tests/test_calibration_metrics.py — ModuleNotFoundError: No module named 'numpy'
  ERROR tests/test_recalibrators.py — ModuleNotFoundError: No module named 'numpy'
  ERROR tests/test_selective.py — ModuleNotFoundError: No module named 'numpy'
  ```

  Fix: add `numpy`, `pandas`, `scikit-learn` to `[dev]` extras in `pyproject.toml`, or document that CI/test runs require `pip install -e ".[dev,bench]"`.

### LOW

- **[LOW] `requires-python = ">=3.11"` in `pyproject.toml` vs. spec requirement of `>=3.12`**

  The design spec and CLAUDE.md both state Python 3.12. Runtime container uses Python 3.11. The code runs without issue on 3.11 (union type syntax via `from __future__ import annotations` backport), but the version floor in `pyproject.toml` is permissive relative to the stated requirement.

### INFO

- **[INFO] Architecture drift from original spec is intentional and documented**

  The Phase 1 design spec describes an H3 hex-map cascade simulator with 50 LLM country/sub-actor agents. The actual implementation is a 3-model prediction market edge-finder (oil price, ceasefire, Hormuz reopening). Modules planned in the spec but not implemented: `agents/`, `spatial/`, `eval/`, `api/`. This pivot is captured in CLAUDE.md and the project postmortem. Not flagged as a defect.

- **[INFO] Project is in archival/concluded state**

  Postmortem committed 2026-07-01. Edge thesis falsified across four experiments. No new production code expected. Health checks now serve an archival verification function.

---

## Recommendations

1. **Fix `portfolio/simulator.py:85`** — one-line correction (`cost_basis` instead of just `entry_price * quantity`), regardless of project status, for archival accuracy of the postmortem P&L figure.
2. **Add `numpy`/`pandas` to `[dev]`** or update CI instructions to `pip install -e ".[dev,bench]"` so the full test suite is runnable without hidden collection failures.
3. **DbWriter wiring** — low-priority in archival mode, but worth a note in any future reactivation plan: the single-writer queue was never connected to production write paths.
