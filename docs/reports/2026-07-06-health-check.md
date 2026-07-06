# Parallax Health Check — 2026-07-06

**Status: YELLOW**

## Summary

No production code changes since `a98b2d4` (2026-06-30). Tests hold at 433 passed / 0 failed / 13 skipped, with 4 unchanged collection errors. All HIGH/MEDIUM issues from yesterday are carry-forwards. This run's deeper scan surfaced two previously-undocumented bugs worth recording for archival accuracy: a deconflict no-op in `cli/brief.py` that allowed competing oil signals to all execute, and a per-request TLS reconnect in `markets/kalshi.py` that degraded API throughput. Neither changes the postmortem conclusion, but both affect the integrity of the paper-trade data.

---

## Repository State

```
HEAD:         1b9ff08  chore: daily health check 2026-07-05 (YELLOW)
Tests:        433 passed | 0 failed | 13 skipped | 4 collection errors
              (unchanged from 2026-07-05)
Project mode: Archival — postmortem committed 2026-07-01
```

---

## Changes Since Last Report (2026-07-05)

No new commits to production code. All issues are carry-forwards unless marked **[NEW]**.

---

## Issues Found

### CRITICAL

- **[CRITICAL][NEW] `cli/brief.py` — `_deconflict_oil_signals` is a no-op; competing oil signals all execute**

  `_deconflict_oil_signals` (around line 489) attempts to suppress all-but-one competing BUY signal for oil contracts, but contains two compounding bugs:

  1. It sets `s.reason = "..."` on the losing `SignalRecord` objects. `SignalRecord` has no `.reason` field — the correct attribute is `.trade_refused_reason`. The attribute assignment creates an ephemeral instance attribute that is never read and never persisted.
  2. The `signal_ledger` rows for losing signals are written to DuckDB by `ledger.record_signal()` **before** this loop runs. The in-memory mutation does not update those rows. When `ledger.get_actionable_signals()` queries the DB (line ~726), it finds the original `BUY_YES`/`BUY_NO` signal intact and submits every competing signal as a live trade.

  Impact: the intended deconfliction never fired during the entire research period. Multiple oil-direction signals were executed simultaneously, compounding position risk and overstating trade volume in the signal ledger. The postmortem's P&L figures are affected by this inflation.

### HIGH

- **[HIGH] `portfolio/simulator.py:85` — P&L double-counting bug (6th consecutive report)**

  Lines 82–85:
  ```python
  fees = pos["quantity"] * entry_price * FEE_RATE
  pnl = payout - fees                                          # omits cost basis
  cash += payout - fees + (pos["quantity"] * pos["entry_price"])  # restores only entry_price
  ```
  `pnl` omits the cost basis entirely; `cash` restores `quantity × entry_price` without accounting for entry fees/slippage. Every `closed_trades` record overstates profit. Correct close-out:
  ```python
  cost_basis = pos["quantity"] * pos["entry_price"] * (1 + FEE_RATE + SLIPPAGE_RATE)
  pnl = payout - fees - cost_basis
  cash += payout - fees + cost_basis
  ```
  The postmortem's −$0.35 backtest direction (no edge) is likely correct; the absolute magnitude is unreliable.

- **[HIGH][NEW] `markets/kalshi.py` — new `httpx.AsyncClient` opened and torn down per API request; no timeout**

  `_request()` wraps every call in `async with httpx.AsyncClient() as client:`. For a brief run fetching N contract tickers, this means N full TLS handshakes in tight succession. Under the market-fetching loop in `brief.py`, this adds hundreds of milliseconds per ticker and risks ephemeral-port exhaustion. Additionally, no `timeout=` is set; a hung Kalshi endpoint stalls the entire async pipeline indefinitely. A single shared `httpx.AsyncClient` (created at `__init__` and closed at process exit) should be used instead.

- **[HIGH] DuckDB single-writer constraint violated across 13 production files**

  The spec (Section 9) requires all writes to pass through a single `asyncio.Queue` → `db_writer` task. `DbWriter` exists and is tested, but no production write path uses it. Violating files:

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

  Risk is low in single-process archival mode. Would resurface immediately if any background task or second process is introduced.

- **[HIGH][NEW] `scoring/ledger.py` — `update_execution` hardcodes `trade_id = None`, making trade_id permanently un-updatable**

  The `UPDATE signal_ledger` statement uses `COALESCE(?, trade_id)` with the third positional argument hardwired to `None`. `COALESCE(None, trade_id)` always returns the existing value; the `trade_id` column can never be set through this method. The method signature has no `trade_id` parameter.

- **[HIGH][NEW] `scoring/ledger.py` — `_compute_suggested_size` raises `TypeError` when `model_was_correct` is always NULL**

  Line ~282: `int(row[1]) / int(row[0])` where `row[1]` is `SUM(CASE WHEN model_was_correct THEN 1 ELSE 0 END)`. DuckDB returns `None` for a SUM of all-NULL values. `int(None)` raises `TypeError`. Before any signal resolutions are recorded, this method crashes on every call. Should be `int(row[1] or 0)`.

- **[HIGH][NEW] `scoring/tracker.py` — uncaught `ValueError` from `_upsert_position` when fill price is None**

  `_reconcile_order_snapshot` calls `_upsert_position(..., avg_fill_price=order.avg_fill_price)`. `_derive_average_fill_price` can return `None` when the venue order carries no cost fields. `_upsert_position` raises `ValueError("Filled orders must have an average fill price")` in that case. This propagates uncaught, leaving a `trade_orders` row stuck in `"attempted"` status that re-raises on every subsequent poll cycle.

- **[HIGH][NEW] `db/schema.py` — `contract_registry` migration block is nested inside `signal_ledger` guard**

  The `_add_column_if_missing` calls for `contract_registry` (line ~596) sit inside `if _table_exists(conn, "signal_ledger"):`. A database with `contract_registry` but without `signal_ledger` never receives its migration columns, silently leaving the table at an older schema version.

### MEDIUM

- **[MEDIUM] 4 test files fail to collect — `numpy`/`pandas` not in `[dev]` extras**

  `test_bench_forecast.py`, `test_calibration_metrics.py`, `test_recalibrators.py`, and `test_selective.py` require packages that are only in the `[bench]` optional group. Running `pytest` with `pip install -e ".[dev]"` silently excludes these files.

- **[MEDIUM][NEW] `scoring/scorecard.py` — potential `TypeError` on timezone-naive datetime subtraction**

  Lines ~335 and ~397: `datetime.now(timezone.utc) - latest` where `latest` comes from `MAX(ended_at)` on a `TIMESTAMPTZ` column. Depending on DuckDB driver version, the returned object may be timezone-naive. Subtracting a naive datetime from an aware one raises `TypeError`.

- **[MEDIUM][NEW] `scoring/tracker.py` — `get_trade_journal` JOIN produces duplicate rows**

  The `trade_orders LEFT JOIN trade_positions ON p.signal_id = o.signal_id` join (lines ~176–200) multiplies rows when a signal has multiple order attempts (e.g., after rejection/retry). No `DISTINCT` or `LIMIT 1` on the position side. The formatted brief will show duplicate journal lines for the same ticker.

- **[MEDIUM][NEW] `cli/brief.py` — calls private `KalshiClient._request()` directly**

  Line ~931: `await client._request("GET", "/markets", ...)`. The public `get_markets(series_ticker=...)` method exists and should be used. Direct access to `_request` bypasses any retry or error-handling logic added to the public API.

### LOW

- **[LOW] F-string SQL construction in `db/schema.py:47` and `scoring/calibration.py:45`**

  `_add_column_if_missing()` interpolates `table_name`, `column_name`, `column_type` directly into DDL. Internal-only call sites today, but an anti-pattern if the function signatures are ever widened.

- **[LOW] `requires-python = ">=3.11"` in `pyproject.toml` vs. spec's `>=3.12`**

  Design spec and CLAUDE.md both specify Python 3.12. Runtime container runs 3.11. Works via `from __future__ import annotations`, but the declared floor is looser than the stated requirement.

- **[LOW] `StarletteDeprecationWarning` on every test run**

  FastAPI's test client triggers `httpx2`-related deprecation warnings. Not functional, adds noise to CI.

- **[LOW][NEW] `prediction/oil_price.py` — accesses private `WorldState._cells` attribute**

  `_iter_cells()` (line ~181) iterates `ws._cells.keys()` directly. Couples the predictor to the internal storage layout of `WorldState`; a rename silently returns an empty iterator with no error raised.

- **[LOW][NEW] `prediction/oil_price.py` — silent hardcoded fallback of $100/bbl with no warning log**

  `_get_current_brent()` returns `100.0` with no log message when no price data matches. Cascade calculations proceed silently with a stale figure.

- **[LOW][NEW] `scoring/scorecard.py` — calibration bucket label can render as "100%-120%"**

  When `model_probability == 1.0`, `r[0] = 1.0`, and `f"{r[0]+0.2:.0%}"` produces `"120%"`. Should clamp: `min(r[0]+0.2, 1.0)`.

- **[LOW][NEW] `db/writer.py` — sentinel item never calls `task_done()`**

  When the sentinel `None` is received, the loop breaks without `self._queue.task_done()`. Any caller that ever awaits `self._queue.join()` will deadlock. No caller currently does this, but it is a latent trap.

### INFO

- **[INFO] Architecture drift from original Phase 1 spec is intentional and documented**

  The Phase 1 design spec describes an H3 hex-map cascade simulator with ~50 LLM country/sub-actor agents, deck.gl visualization, GDELT BigQuery ingestion, and a WebSocket-driven dashboard. The implemented system is a 3-model prediction market edge-finder (Google News RSS + GDELT DOC API → Claude Sonnet → Kalshi/Polymarket comparison → BUY/SELL/HOLD signals). Absent from codebase: `agents/`, H3 spatial model, deck.gl/MapLibre, `simulation/engine.py`, `simulation/circuit_breaker.py`, `eval/`, WebSocket auth layer, semantic deduplicator. This pivot is captured in CLAUDE.md and the postmortem. Not a defect.

- **[INFO] Project is in archival/concluded state**

  Postmortem committed 2026-07-01. Edge thesis falsified across four experiments. No new production code expected.

---

## Recommendations

1. **Document the deconflict no-op** in the postmortem appendix — it inflated paper-trade volume and should be noted as a caveat on the signal ledger data.
2. **Fix `portfolio/simulator.py:85`** — two-line correction for archival accuracy of the postmortem P&L figure. Flagged 6 consecutive reports.
3. **Add `numpy`/`pandas`/`scikit-learn` to `[dev]`** in `pyproject.toml` so plain `pytest` covers the full suite.
4. **DbWriter wiring and `kalshi.py` client lifecycle** — low-priority in archival mode; note in any reactivation plan.
