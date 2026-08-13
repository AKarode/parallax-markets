# Parallax Health Check — 2026-08-13

**Status: YELLOW**

## Summary

No code changes since yesterday's health check (only a tech-research doc was added in commit cc1fcb1). All issues from the 2026-08-12 report remain unresolved, and this run's deeper code-quality scan surfaced several new findings not previously reported: a missing HTTP timeout on every Kalshi request, an unhandled exception in `cancel_order()`, a unit-scale mismatch between `oil_price.py` and `cascade.py` that clamps all downstream effects to their maximum, and a `BudgetTracker` model-ID key mismatch that silently charges Sonnet pricing for Opus calls. The codebase is in working condition for its primary use case (prediction → market comparison → paper trading) but has unaddressed reliability and correctness gaps. This is the 10th consecutive YELLOW day.

---

## Issues Found

### [HIGH] Missing HTTP timeout on all Kalshi API requests

**File:** `backend/src/parallax/markets/kalshi.py` — `_request()` method

`httpx.AsyncClient()` is instantiated with no `timeout` argument. The httpx default is 5 s connect / `None` read, meaning a slow Kalshi response can hang the asyncio event loop indefinitely. Every other HTTP caller in the codebase (`gdelt_doc.py`, `google_news.py`, `oil_prices.py`, `alerts.py`) uses an explicit timeout; Kalshi is the only exception.

**Fix:** Pass `timeout=httpx.Timeout(10.0, read=30.0)` to `httpx.AsyncClient()`.

---

### [HIGH] `cancel_order()` has no exception handling around Kalshi API call

**File:** `backend/src/parallax/scoring/tracker.py` — `cancel_order()` method

`execute_signal()` wraps the equivalent Kalshi call in `try/except Exception`; `cancel_order()` does not. A network failure or 4xx/5xx from Kalshi propagates as an uncaught exception, crashing the operation and leaving the order in an indeterminate state. The `poll_resting_orders()` method correctly uses try/except — the omission in `cancel_order` is inconsistent.

**Fix:** Wrap `await self._kalshi.cancel_order(order.venue_order_id)` in try/except and log the failure.

---

### [HIGH] DuckDB single-writer topology violated — DbWriter queue unused

**Affected files (confirmed by scan):** `scoring/ledger.py`, `scoring/tracker.py`, `scoring/scorecard.py`, `budget/tracker.py`, `ops/alerts.py`, `ingestion/crisis_ingester.py`, `cli/brief.py`, `contracts/registry.py`, `backtest/runner.py` (9 write-side files + `main.py`)

`db/writer.py` implements the single-writer pattern correctly but is never imported or instantiated anywhere in the codebase. `main.py` stores a raw `duckdb.DuckDBPyConnection` at `app.state.db` and distributes it directly to all write-side components. Under concurrent API requests, two coroutines can race on the same connection and produce DuckDB `TransactionContext` errors or data corruption. Additionally if `uvicorn main:app` and `python -m parallax.cli.brief` run concurrently they open separate connections to the same DuckDB file, causing `database is locked` errors.

**Fix (minimal):** Add a file lock in `cli/brief.py` to prevent concurrent server + CLI runs. Full fix: wire `DbWriter` into the `lifespan` context and inject it into all write-side modules.

---

### [HIGH] Missing `cryptography` dependency

**File:** `backend/pyproject.toml` / `backend/src/parallax/markets/kalshi.py:19–20`

`KalshiClient` imports `cryptography.hazmat.primitives` for RSA-PSS signing. `cryptography` is not listed in `[project.dependencies]`. A clean `pip install -e .` omits it silently; any Kalshi call fails with `ImportError` at runtime.

**Fix:** Add `"cryptography>=41.0"` to `[project.dependencies]`.

---

### [MEDIUM] `compute_downstream_effects()` unit-scale mismatch with `oil_price.py`

**Files:** `backend/src/parallax/simulation/cascade.py` / `backend/src/parallax/prediction/oil_price.py`

`cascade.py`'s `compute_downstream_effects()` docstring specifies `price_increase_pct` as a fraction (e.g., 0.30 for 30%). `oil_price.py` computes `price_shock_pct` as `((new_price - current_price) / current_price) * 100` — an integer-scale percentage (e.g., 30.0). If downstream effects are ever called with this value, the formula `impact = min(1.0, dependency * 30.0)` clamps to 1.0 for any country with even marginal oil dependency, flattening all downstream variation to the same maximum impact. All downstream effect computations would be incorrect.

**Fix:** Standardize the unit — either change `oil_price.py` to divide by 100, or update the cascade docstring and formula to accept the percentage scale.

---

### [MEDIUM] Silent $100 Brent fallback in `_get_current_brent()`

**File:** `backend/src/parallax/prediction/oil_price.py:188`

When no Brent price row is found in the `prices` list, `_get_current_brent()` returns `100.0` with no log warning. A misconfigured or empty EIA price feed silently injects a stale baseline into every cascade and LLM prompt, corrupting predictions without any observable signal in logs.

**Fix:** Log a warning before returning the fallback value.

---

### [MEDIUM] `BudgetTracker` model-ID pricing key mismatch

**File:** `backend/src/parallax/budget/tracker.py:11–14,38`

`_PRICING` is keyed by short names (`"haiku"`, `"sonnet"`, `"opus"`). Model IDs passed at call sites use full version strings (e.g., `"claude-opus-4-20250514"`). `_PRICING.get(model, _PRICING["sonnet"])` silently falls back to Sonnet pricing for every unmatched key, under-accounting Opus call costs and potentially allowing the $20/day cap to be exceeded without triggering.

**Fix:** Normalize model IDs before lookup (e.g., check if `"haiku"`, `"sonnet"`, or `"opus"` appears as a substring of the model ID).

---

### [MEDIUM] BudgetTracker cold-start bug — spend not seeded from DB

**File:** `backend/src/parallax/budget/tracker.py:33`

`self._spend_today = 0.0` is hardcoded in `__init__`. On process restart, the tracker resets to zero even if LLM calls were already made that calendar day. `llm_usage` persists all calls but `is_over_budget()` never queries it.

**Fix:** In `__init__`, when `db_conn` is provided, seed:
```python
row = db_conn.execute(
    "SELECT COALESCE(SUM(cost_usd), 0.0) FROM llm_usage WHERE DATE(created_at) = CURRENT_DATE"
).fetchone()
self._spend_today = float(row[0]) if row else 0.0
```

---

### [MEDIUM] Zero-price orderbook levels silently appended in `get_orderbook()`

**File:** `backend/src/parallax/markets/kalshi.py` — `get_orderbook()` method

When `_coerce_price()` returns `None`, the `or 0.0` fallback creates phantom `OrderbookLevel(price=0.0, ...)` entries. These propagate to ask-side computation as `price=1.0` (via `1.0 - 0.0`), silently inflating orderbook depth and skewing any spread/edge calculation.

**Fix:** Skip levels where `_coerce_price()` returns `None` rather than substituting 0.0.

---

### [MEDIUM] `SignalLedger.record_signal()` — 14 schema columns never populated

**File:** `backend/src/parallax/scoring/ledger.py`

`SIGNAL_COLUMNS` lists 51 columns but `signal_ledger` has 65. Among the missing columns: `net_edge`, `gross_edge`, `expected_fee_rate`, `expected_slippage_rate`, `fair_value_yes`, `fair_value_no`, `quote_is_stale`, `staleness_threshold_seconds`. These columns are core to the analytics (edge decay dashboard, calibration) but will always be NULL in every signal record, making those dashboard views unreliable.

**Fix:** Populate all analytics-relevant columns at signal write time, or remove them from the schema if unused.

---

### [MEDIUM] Agent swarm and circuit breaker absent — 3 DB tables permanently orphaned

**Missing:** `backend/src/parallax/agents/` (entire package), `simulation/circuit_breaker.py`

`agent_memory`, `agent_prompts`, `decisions` tables exist in the schema but nothing writes to them. Consistent with the prediction-market pivot.

**Fix:** Drop the three tables via migration or document them as reserved for a future phase.

---

### [LOW] `db/schema.py` migration nesting bug

**File:** `backend/src/parallax/db/schema.py` — contract_registry migration block

The migration that adds columns to `contract_registry` is nested inside `if _table_exists(conn, "signal_ledger"):`. If `contract_registry` exists but `signal_ledger` does not, the migration columns are never applied. This can cause `column not found` errors in any deployment where `signal_ledger` was dropped or created in a different order.

---

### [LOW] `world_state_delta` / `world_state_snapshot` — no PK or UNIQUE constraint

**File:** `backend/src/parallax/db/schema.py:52,64`

Neither table has a `PRIMARY KEY` or `UNIQUE (cell_id, tick)` constraint. Duplicate delta/snapshot rows for the same cell-tick pair can accumulate silently, causing incorrect world state reconstruction when replaying deltas.

---

### [LOW] `requires-python` mismatch

`pyproject.toml` specifies `>=3.11` but deployment target is Python 3.12.

---

### [LOW] Architecture drift from original spec — intentional

Missing by design vs. original Phase 1 spec: `agents/` (50-agent swarm), `spatial/` (H3 utilities), `api/websocket.py`, `api/auth.py`, `eval/` (prompt versioning, A/B), `ingestion/gdelt.py` (BigQuery), `ingestion/dedup.py` (sentence-transformers). CLAUDE.md correctly documents the pivoted architecture as a prediction market edge-finder.

---

## Recommendations (Priority Order)

1. **[P1 — 5 min] Add `cryptography>=41.0` to `pyproject.toml`** — prevents silent `ImportError` on clean install.
2. **[P1 — 10 min] Add HTTP timeout to `kalshi.py` `_request()`** — prevents indefinite event loop hangs.
3. **[P1 — 10 min] Add try/except to `cancel_order()` in `tracker.py`** — prevents uncaught Kalshi API failures from crashing order operations.
4. **[P1 — 30 min] Add file lock in `cli/brief.py`** against concurrent API server runs, or wire `DbWriter` into the async chain.
5. **[P2 — 15 min] Fix `BudgetTracker` cold-start + model-ID key mismatch** — seed spend from DB and normalize model names before pricing lookup.
6. **[P2 — 15 min] Fix `compute_downstream_effects()` unit-scale** — align `oil_price.py` output (%) with cascade expectation (fraction) to prevent all downstream effects from clamping to 1.0.
7. **[P2 — 10 min] Fix zero-price orderbook levels in `get_orderbook()`** — skip `None` coerce results instead of substituting 0.0.
8. **[P3 — 15 min] Log warning in `_get_current_brent()` before returning fallback** — make silent data gaps observable.
9. **[P3 — 10 min] Drop or document orphaned agent tables** (`agent_memory`, `agent_prompts`, `decisions`).
10. **[P4 — 2 min] Update `requires-python`** to `>=3.12`.

## Trend

| Date | Status | High Issues | New Findings This Day |
|------|--------|-------------|----------------------|
| 2026-08-03 | YELLOW | 2 | — |
| 2026-08-08 | YELLOW | 2 | 0 |
| 2026-08-09 | YELLOW | 2 | 0 |
| 2026-08-10 | YELLOW | 2 | 0 |
| 2026-08-11 | YELLOW | 2 | 0 |
| 2026-08-12 | YELLOW | 2 | 0 |
| **2026-08-13** | **YELLOW** | **4** | **+5 new (timeout, cancel_order, cascade unit mismatch, orderbook corruption, BudgetTracker key mismatch)** |

The two original HIGH issues remain unresolved. This run's deeper code scan surfaced four total HIGH findings (up from 2) and five additional medium findings. The cascade unit-scale mismatch is the highest-priority correctness bug since it silently renders downstream effect computations incorrect.
