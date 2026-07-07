# Parallax Health Check — 2026-07-07

**Status: YELLOW**

## Summary

No production code changes since `a98b2d4` (2026-06-30). Tests hold at 433 passed / 0 failed / 13 skipped, with 4 unchanged collection errors (numpy-dependent bench tests). All issues are carry-forwards from the 2026-07-06 report; none of the flagged bugs have been fixed. Project remains in archival mode following the 2026-07-01 postmortem.

---

## Repository State

```
HEAD:         3b80249  chore: daily health check 2026-07-06 (YELLOW)
Tests:        433 passed | 0 failed | 13 skipped | 4 collection errors
              (unchanged from 2026-07-06)
Project mode: Archival — postmortem committed 2026-07-01
```

---

## Changes Since Last Report (2026-07-06)

No new commits to production code. All issues are carry-forwards.

---

## Issues Found

### CRITICAL

- **[CRITICAL] `cli/brief.py` — `_deconflict_oil_signals` is a no-op; competing oil signals all execute**

  `_deconflict_oil_signals` (line 472) sets `s.reason = "..."` on losing `SignalRecord` objects. `SignalRecord` has no `.reason` field — the correct attribute is `.trade_refused_reason`. The ephemeral attribute is never persisted. Signal ledger rows are written to DuckDB before this loop runs, so every competing BUY_YES/BUY_NO signal executes as a live trade. This inflated paper-trade volume throughout the research period and affects postmortem P&L figures.

### HIGH

- **[HIGH] `portfolio/simulator.py:85` — P&L double-counting bug (7th consecutive report)**

  Lines 82–85 omit cost basis from `pnl` while restoring `quantity × entry_price` in `cash` without accounting for entry fees/slippage. Every `closed_trades` record overstates profit. Correct close-out:
  ```python
  cost_basis = pos["quantity"] * pos["entry_price"] * (1 + FEE_RATE + SLIPPAGE_RATE)
  pnl = payout - fees - cost_basis
  cash += payout - fees + cost_basis
  ```
  The postmortem direction (no edge) is likely correct; absolute magnitudes are unreliable.

- **[HIGH] DuckDB single-writer constraint violated across 13 production files**

  The spec (Section 9) requires all writes to pass through a single `asyncio.Queue` → `db_writer` task. `DbWriter` exists and is tested, but no production write path uses it. Violating files:

  | File | Violation |
  |------|----------|
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

  Risk is low in single-process archival mode. Would resurface immediately with any background task or second writer.

- **[HIGH] `markets/kalshi.py` — new `httpx.AsyncClient` per API request; no timeout**

  `_request()` wraps every call in `async with httpx.AsyncClient() as client:`. N contract tickers = N full TLS handshakes. No `timeout=` set; a hung endpoint stalls the entire async pipeline indefinitely.

- **[HIGH] `scoring/ledger.py` — `update_execution` hardcodes `trade_id = None`**

  The `UPDATE signal_ledger` uses `COALESCE(?, trade_id)` with the `trade_id` argument hardwired to `None`. `COALESCE(None, trade_id)` always returns the existing value; the column can never be updated through this method.

- **[HIGH] `scoring/ledger.py` — `_compute_suggested_size` raises `TypeError` when `model_was_correct` is all NULL**

  Line 283: `int(row[1]) / int(row[0])` — DuckDB returns `None` for `SUM(CASE WHEN model_was_correct ...)` when no resolutions exist. `int(None)` raises `TypeError`. Should be `int(row[1] or 0)`.

- **[HIGH] `scoring/tracker.py` — uncaught `ValueError` from `_upsert_position` when fill price is None**

  `_reconcile_order_snapshot` calls `_upsert_position` with `avg_fill_price=None` when the venue order carries no cost fields. `_upsert_position` raises `ValueError("Filled orders must have an average fill price")`, leaving the `trade_orders` row stuck in `"attempted"` status that re-raises on every poll cycle.

- **[HIGH] `db/schema.py` — `contract_registry` migration block nested inside `signal_ledger` guard**

  `_add_column_if_missing` calls for `contract_registry` (line ~596) sit inside `if _table_exists(conn, "signal_ledger"):`. A database with `contract_registry` but not `signal_ledger` never receives its migration columns.

### MEDIUM

- **[MEDIUM] 4 test files fail to collect — `numpy`/`pandas` not in `[dev]` extras**

  `test_bench_forecast.py`, `test_calibration_metrics.py`, `test_recalibrators.py`, `test_selective.py` require `numpy`/`pandas`/`scikit-learn` from the `[bench]` optional group. Running `pytest` with `pip install -e ".[dev]"` silently excludes these 4 files.

- **[MEDIUM] `scoring/scorecard.py` — potential `TypeError` on timezone-naive datetime subtraction**

  `datetime.now(timezone.utc) - latest` where `latest` from `MAX(ended_at)` may be timezone-naive depending on DuckDB driver version. Subtracting naive from aware raises `TypeError`.

- **[MEDIUM] `scoring/tracker.py` — `get_trade_journal` JOIN produces duplicate rows**

  `trade_orders LEFT JOIN trade_positions ON p.signal_id = o.signal_id` multiplies rows when a signal has multiple order attempts. No `DISTINCT` or position-side `LIMIT 1`.

- **[MEDIUM] `cli/brief.py` — calls private `KalshiClient._request()` directly**

  Public `get_markets(series_ticker=...)` exists and should be used. Direct `_request` access bypasses retry/error-handling logic.

### LOW

- **[LOW] F-string SQL construction in `db/schema.py:47` and `scoring/calibration.py:45`**

  `table_name`, `column_name`, `column_type` interpolated directly into DDL. Internal-only today, but an anti-pattern if signatures are widened.

- **[LOW] `requires-python = ">=3.11"` in `pyproject.toml` vs. spec's `>=3.12`**

  Design spec and CLAUDE.md specify Python 3.12; declared floor is 3.11.

- **[LOW] `StarletteDeprecationWarning` on every test run**

  FastAPI test client triggers httpx2-related deprecation warning. Adds noise to CI output.

- **[LOW] `prediction/oil_price.py` — accesses private `WorldState._cells` attribute**

  `_iter_cells()` iterates `ws._cells.keys()` directly. A rename silently returns an empty iterator with no error.

- **[LOW] `prediction/oil_price.py` — silent hardcoded fallback of $100/bbl with no warning log**

  `_get_current_brent()` returns `100.0` with no log message when no price data matches. Cascade calculations proceed silently with a stale figure.

- **[LOW] `scoring/scorecard.py` — calibration bucket label can render as "100%-120%"**

  When `model_probability == 1.0`, `f"{r[0]+0.2:.0%}"` produces `"120%"`. Should clamp to `min(r[0]+0.2, 1.0)`.

- **[LOW] `db/writer.py` — sentinel item never calls `task_done()`**

  When sentinel `None` is received, the loop breaks without `self._queue.task_done()`. Any caller awaiting `self._queue.join()` would deadlock. No caller currently does this.

### INFO

- **[INFO] Architecture drift from original Phase 1 spec is intentional and documented**

  The Phase 1 design spec describes an H3 hex-map cascade simulator with ~50 LLM country/sub-actor agents, deck.gl visualization, GDELT BigQuery ingestion, and a WebSocket-driven dashboard. The implemented system is a 3-model prediction market edge-finder (Google News RSS + GDELT DOC API → Claude Sonnet → Kalshi/Polymarket comparison → BUY/SELL/HOLD signals). Absent from codebase: `agents/`, H3 spatial model, deck.gl/MapLibre, `simulation/engine.py`, `simulation/circuit_breaker.py`, `eval/`, WebSocket auth layer, semantic deduplicator. This pivot is captured in CLAUDE.md and the postmortem.

- **[INFO] pyproject.toml missing spec-specified dependencies**

  Six dependencies in the Phase 1 plan are absent from the actual `pyproject.toml`: `h3>=4.1`, `websockets>=14.0`, `sentence-transformers>=3.4`, `searoute>=1.3`, `shapely>=2.0`, `google-cloud-bigquery>=3.27`. These correspond to the pivoted-away H3/GDELT/spatial subsystems; omission is consistent with the documented architecture pivot.

- **[INFO] Project is in archival/concluded state**

  Postmortem committed 2026-07-01. Edge thesis falsified across four experiments. No new production code expected.

---

## Recommendations

1. **Fix `scoring/ledger.py:283`** — one-line change (`int(row[1] or 0)`) prevents a `TypeError` crash on the first call before any resolutions are recorded.
2. **Fix `portfolio/simulator.py:85`** — two-line P&L correction for archival accuracy. Flagged 7 consecutive reports.
3. **Document the `_deconflict_oil_signals` no-op** in the postmortem appendix as a caveat on signal-ledger trade volume and P&L figures.
4. **Add `numpy`/`pandas`/`scikit-learn` to `[dev]` extras** in `pyproject.toml` so plain `pytest` covers the full suite.
