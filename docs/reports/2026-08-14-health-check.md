# Parallax Health Check — 2026-08-14

**Status: YELLOW**

## Summary

No code changes since the 2026-08-13 report (only a tech-research doc added in commit c47efdc). All four HIGH issues from yesterday remain unresolved: missing `cryptography` dependency, missing HTTP timeout on Kalshi requests, unhandled exception in `cancel_order()`, and the DuckDB single-writer topology violation. Test suite is healthy at 433 passed / 13 skipped. This is the 11th consecutive YELLOW day.

---

## Issues Found

### [HIGH] Missing `cryptography` dependency — `pyproject.toml`

`KalshiClient` imports `cryptography.hazmat.primitives` for RSA-PSS signing. `cryptography` is not in `[project.dependencies]`. A clean `pip install -e .` omits it silently; every Kalshi call fails with `ImportError` at runtime. Zero effort to fix.

**Fix:** Add `"cryptography>=41.0"` to `[project.dependencies]` in `pyproject.toml`.

---

### [HIGH] Missing HTTP timeout on all Kalshi API requests

**File:** `backend/src/parallax/markets/kalshi.py:154`

`async with httpx.AsyncClient() as client:` uses no `timeout` argument. httpx default is 5 s connect / `None` read — a slow or hung Kalshi response blocks the asyncio event loop indefinitely. All other HTTP callers (`gdelt_doc.py`, `google_news.py`, `oil_prices.py`, `alerts.py`) pass explicit timeouts; Kalshi is the only exception.

**Fix:** `async with httpx.AsyncClient(timeout=httpx.Timeout(10.0, read=30.0)) as client:`

---

### [HIGH] `cancel_order()` has no exception handling around Kalshi API call

**File:** `backend/src/parallax/scoring/tracker.py:263`

`response = await self._kalshi.cancel_order(order.venue_order_id)` is bare — no try/except. A Kalshi network error or 4xx/5xx propagates uncaught, leaving the order in an indeterminate state. `execute_signal()` wraps its equivalent call in `try/except`; `cancel_order()` is inconsistent.

**Fix:** Wrap line 263 in `try/except Exception` and log the failure; return the order in its current state.

---

### [HIGH] DuckDB single-writer topology violated — `DbWriter` queue never wired in

**Affected files (writes bypass the queue):** `scoring/ledger.py` (6 write executes), `scoring/tracker.py` (12 write executes), `scoring/scorecard.py` (21 write executes), `scoring/prediction_log.py` (3 write executes), `budget/tracker.py` (1 write execute), `ops/alerts.py`, `ingestion/crisis_ingester.py`, `cli/brief.py`, `contracts/registry.py`, `backtest/runner.py`

`db/writer.py` correctly implements the single-writer asyncio.Queue pattern but is never imported or instantiated anywhere. `main.py` distributes a raw `duckdb.DuckDBPyConnection` to all write-side components. Under concurrent API requests, two coroutines can race on the same connection producing `TransactionContext` errors or silent data corruption. Concurrent `uvicorn` + `cli/brief.py` runs open separate connections to the same DuckDB file, causing `database is locked` errors.

**Fix (minimal):** Add a `filelock` in `cli/brief.py` to prevent concurrent CLI + server runs. Full fix: wire `DbWriter` into the FastAPI lifespan and inject it into all write-side modules.

---

### [MEDIUM] `compute_downstream_effects()` unit-scale mismatch

**Files:** `backend/src/parallax/simulation/cascade.py` / `backend/src/parallax/prediction/oil_price.py`

`cascade.py` expects `price_increase_pct` as a fraction (e.g., 0.30 for 30%). `oil_price.py` computes `price_shock_pct` as `((new_price - current_price) / current_price) * 100` — integer-scale percentage (e.g., 30.0). If passed to downstream effects, `impact = min(1.0, dependency * 30.0)` clamps to 1.0 for any country with even marginal oil dependency, flattening all variation to the same maximum impact.

**Fix:** Divide `oil_price.py` output by 100 before passing to cascade, or update cascade to accept the percentage scale.

---

### [MEDIUM] Silent $100 Brent fallback in `_get_current_brent()`

**File:** `backend/src/parallax/prediction/oil_price.py:188`

Returns `100.0` silently when the EIA price feed is empty or misconfigured — no log warning. A stale baseline silently corrupts every cascade and LLM prompt with no observable signal.

**Fix:** Add `logger.warning("No Brent price data; using fallback $%.1f", 100.0)` before the return.

---

### [MEDIUM] `BudgetTracker` model-ID pricing key mismatch + cold-start bug

**File:** `backend/src/parallax/budget/tracker.py:11–14,33`

`_PRICING` is keyed by short names (`"haiku"`, `"sonnet"`, `"opus"`) but callers pass full version strings like `"claude-opus-4-20250514"`. Every unmatched key silently falls back to Sonnet pricing, under-counting Opus costs. Separately, `self._spend_today = 0.0` in `__init__` never seeds from the `llm_usage` table — on process restart the budget counter resets to zero regardless of prior spending.

**Fix:** Normalize model IDs via substring match before pricing lookup; seed `_spend_today` from DB in `__init__`.

---

### [MEDIUM] Zero-price orderbook levels in `get_orderbook()`

**File:** `backend/src/parallax/markets/kalshi.py` — `get_orderbook()`

When `_coerce_price()` returns `None`, the `or 0.0` fallback creates phantom `OrderbookLevel(price=0.0, ...)` entries. These propagate to the ask side as `price=1.0`, silently inflating orderbook depth and skewing spread/edge calculations.

**Fix:** Skip levels where `_coerce_price()` returns `None` rather than substituting 0.0.

---

### [MEDIUM] `SignalLedger.record_signal()` — analytics columns never populated

**File:** `backend/src/parallax/scoring/ledger.py:79–132`

`SIGNAL_COLUMNS` (51 entries) does not include `net_edge`, `gross_edge`, `expected_fee_rate`, `expected_slippage_rate`, `fair_value_yes`, `fair_value_no`, `quote_is_stale`, `staleness_threshold_seconds` — all of which exist in `signal_ledger` schema (`db/schema.py:219–294`). These columns are always NULL in every written record, making edge-decay dashboard and calibration views unreliable.

**Fix:** Populate the missing columns at write time, or remove them from the schema if unused.

---

### [LOW] `db/schema.py` — migration nesting bug

The migration that adds columns to `contract_registry` is nested inside `if _table_exists(conn, "signal_ledger"):`. If `contract_registry` exists but `signal_ledger` does not, the migration never runs and subsequent queries fail with `column not found`.

---

### [LOW] `world_state_delta` / `world_state_snapshot` — no dedup constraint

Neither table has a `PRIMARY KEY` or `UNIQUE (cell_id, tick)` constraint. Duplicate rows accumulate silently, causing incorrect state reconstruction when replaying deltas.

---

### [LOW] `requires-python` mismatch

`pyproject.toml` specifies `>=3.11`; deployment target is Python 3.12.

---

### [LOW] Architecture drift from original spec — intentional and documented

Original Phase 1 design called for a 50-agent LLM swarm, H3 spatial visualization, GDELT BigQuery ingestion, and an eval framework. The project correctly pivoted to a prediction-market edge-finder. `CLAUDE.md` reflects the current architecture. Three orphaned tables (`agent_memory`, `agent_prompts`, `decisions`) exist in the schema but nothing writes to them.

**Recommendation:** Drop the three tables via migration or mark them as reserved.

---

## Recommendations (Priority Order)

1. **[P1 — 5 min]** Add `"cryptography>=41.0"` to `pyproject.toml` — prevents silent `ImportError` on clean install.
2. **[P1 — 10 min]** Add HTTP timeout to `kalshi.py` `_request()` — prevents indefinite event loop hangs.
3. **[P1 — 10 min]** Wrap `cancel_order()` Kalshi call in try/except — prevents uncaught API failures from crashing order operations.
4. **[P1 — 30 min]** Add file lock in `cli/brief.py` against concurrent server + CLI runs, or wire `DbWriter` into the async chain.
5. **[P2 — 15 min]** Fix `BudgetTracker` cold-start + model-ID key mismatch.
6. **[P2 — 15 min]** Fix `compute_downstream_effects()` unit-scale mismatch.
7. **[P2 — 10 min]** Fix zero-price orderbook levels in `get_orderbook()`.
8. **[P3 — 15 min]** Log warning in `_get_current_brent()` before returning fallback.
9. **[P3 — 10 min]** Drop or document orphaned agent tables (`agent_memory`, `agent_prompts`, `decisions`).
10. **[P4 — 2 min]** Update `requires-python` to `>=3.12`.

---

## Test Results

| Metric | Value |
|--------|-------|
| Tests passed | 433 |
| Tests skipped | 13 |
| Tests failed | 0 |
| Import errors (optional deps) | 3 (`numpy`/`pandas` from `bench` extra) |

---

## Trend

| Date | Status | High Issues | Notes |
|------|--------|-------------|-------|
| 2026-08-03 | YELLOW | 2 | — |
| 2026-08-08 | YELLOW | 2 | No change |
| 2026-08-09 | YELLOW | 2 | No change |
| 2026-08-10 | YELLOW | 2 | No change |
| 2026-08-11 | YELLOW | 2 | No change |
| 2026-08-12 | YELLOW | 2 | No change |
| 2026-08-13 | YELLOW | 4 | +5 new findings |
| **2026-08-14** | **YELLOW** | **4** | No code changes; all prior issues unresolved |

11 consecutive YELLOW days. The four HIGH issues have been documented since 2026-08-12/13 with no resolution. The minimal P1 fixes (cryptography dep, HTTP timeout, cancel_order exception handling) are each under 10 minutes of work and would clear two of the four HIGH issues immediately.
