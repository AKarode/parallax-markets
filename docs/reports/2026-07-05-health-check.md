# Parallax Health Check — 2026-07-05

**Status: YELLOW**

## Summary

No production code changes since `a98b2d4` (2026-06-30). Tests hold at 433 passed / 0 failed / 13 skipped, with 4 unchanged collection errors. Both HIGH issues persist for a 5th consecutive report: the `portfolio/simulator.py:85` P&L double-counting bug and the DuckDB single-writer constraint violated across 13 production files. One new LOW finding added: f-string SQL in `db/schema.py` and `scoring/calibration.py` (internal-only, not a real injection risk, but an anti-pattern).

---

## Repository State

```
HEAD:         080e32f  chore: daily health check 2026-07-04 (YELLOW)
Tests:        433 passed | 0 failed | 13 skipped | 4 collection errors
              (unchanged from 2026-07-04)
Project mode: Research concluded — postmortem committed 2026-07-01
```

---

## Changes Since Last Report (2026-07-04)

No new commits to production code. All issues are carry-forwards.

---

## Issues Found

### HIGH

- **[HIGH] `portfolio/simulator.py:85` — P&L double-counting bug (5th consecutive report)**

  Lines 82–85 (confirmed unchanged at HEAD):
  ```python
  fees = pos["quantity"] * entry_price * FEE_RATE
  pnl = payout - fees                                         # omits entry cost
  cash += payout - fees + (pos["quantity"] * pos["entry_price"])  # restores only entry_price, not cost basis
  ```

  Two compounding errors:
  1. `pnl` omits the cost basis, so every `closed_trades` record overstates profit.
  2. `cash` restores only `quantity × entry_price`, not the effective cost including entry fees/slippage, silently absorbing those costs as phantom profit at close.

  Correct close-out:
  ```python
  cost_basis = pos["quantity"] * pos["entry_price"] * (1 + FEE_RATE + SLIPPAGE_RATE)
  pnl = payout - fees - cost_basis
  cash += payout - fees + cost_basis
  ```

  Impact: the postmortem's −$0.35 backtest figure was computed with this engine. Direction (no edge) is likely correct, but the absolute P&L number is unreliable. Fix is a two-line change.

- **[HIGH] DuckDB single-writer constraint violated across 13 production files**

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
  | `backtest/runner.py` | INSERT to `backtest_runs`, `backtest_predictions` |
  | `db/schema.py` | DDL + data migrations |
  | `contracts/registry.py` | INSERT/UPDATE/DELETE to `contract_registry` |

  Risk is low in archival/single-process mode. Risk resurfaces if any background task or second process is introduced.

### MEDIUM

- **[MEDIUM] 4 test files fail to collect — `numpy`/`pandas` not in `[dev]` extras**

  `test_bench_forecast.py`, `test_calibration_metrics.py`, `test_recalibrators.py`, and `test_selective.py` import `numpy`, `pandas`, and `scikit-learn`, which live in the `[bench]` optional group only. Running `pytest` with `pip install -e ".[dev]"` aborts collection for these files and they are silently excluded from the suite unless `pip install -e ".[dev,bench]"` is used.

  Fix: add `numpy`, `pandas`, `scikit-learn` to `[dev]` extras in `pyproject.toml`, or document clearly that the full suite requires `[dev,bench]`.

### LOW

- **[LOW] F-string SQL construction in `db/schema.py:47` and `scoring/calibration.py:45`**

  `_add_column_if_missing()` builds `ALTER TABLE` SQL via f-string with `table_name`, `column_name`, and `column_type` arguments. `calibration_report()` interpolates a `where_clause` string assembled from internal conditionals. Neither path accepts user input, so there is no injection vector in practice. However, f-string SQL is an anti-pattern that becomes dangerous if the function signatures are ever widened (e.g., to accept caller-supplied column names). Parameterised DDL (using DuckDB's `duckdb_types` or identifier quoting) would be safer.

- **[LOW] `requires-python = ">=3.11"` in `pyproject.toml` vs. spec's `>=3.12`**

  Design spec and CLAUDE.md both specify Python 3.12. Runtime container runs 3.11. Code works due to `from __future__ import annotations` backport for union-type syntax (`X | Y`), but the declared floor is permissive relative to the stated requirement.

- **[LOW] `StarletteDeprecationWarning` on every test run**

  FastAPI's test client (`from starlette.testclient import TestClient`) triggers `httpx2`-related deprecation warnings each run. Not a functional issue but adds noise to CI output.

### INFO

- **[INFO] Architecture drift from original Phase 1 spec is intentional and documented**

  The Phase 1 design spec describes an H3 hex-map cascade simulator with 50 LLM country/sub-actor agents. The implemented system is a 3-model prediction market edge-finder. Modules in the spec but absent from the codebase: `agents/`, `spatial/`, `simulation/engine.py`, `simulation/circuit_breaker.py`, `eval/`, `api/` (websocket + auth), `ingestion/dedup.py`. This pivot is captured in CLAUDE.md and the project postmortem. Not a defect.

- **[INFO] Project is in archival/concluded state**

  Postmortem committed 2026-07-01. Edge thesis falsified across four experiments. No new production code expected. Health checks now serve an archival verification function.

---

## Recommendations

1. **Fix `portfolio/simulator.py:85`** — two-line correction for archival accuracy of the postmortem P&L figure. Has been flagged for 5 consecutive reports.
2. **Add `numpy`/`pandas`/`scikit-learn` to `[dev]`** in `pyproject.toml` so plain `pytest` covers the full test suite without hidden collection failures.
3. **DbWriter wiring** — low-priority in archival mode; document in any future reactivation plan that the single-writer queue was never wired to production write paths.
4. **Replace f-string SQL in `db/schema.py`** with explicit identifier quoting to prevent future injection risk if `_add_column_if_missing` call sites are ever expanded.
