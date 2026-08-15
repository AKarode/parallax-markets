# Parallax Health Check — 2026-08-15

**Status: YELLOW**

## Summary

No code changes since the 2026-08-14 report. All four HIGH issues from 2026-08-13/14 remain unresolved. A new environment issue emerged: the test suite now fails to collect without explicit `--ignore` flags for 4 bench-extra files that import `numpy`/`pandas`; with those excluded, 433 pass / 13 skipped (unchanged from yesterday). Four additional MEDIUM bugs were identified by deeper audit today. This is the **12th consecutive YELLOW day** with no code fixes landed.

---

## Issues Found

### [HIGH] Missing `cryptography` dependency — `pyproject.toml` *(unresolved, first seen 2026-08-13)*

`KalshiClient` imports `cryptography.hazmat.primitives` for RSA-PSS signing. `cryptography` is absent from `[project.dependencies]`. A clean `pip install -e .` silently omits it; all Kalshi API calls fail with `ImportError` at runtime.

**Fix:** Add `"cryptography>=41.0"` to `[project.dependencies]` in `pyproject.toml`.

---

### [HIGH] Missing HTTP timeout on Kalshi API requests — `markets/kalshi.py:154` *(unresolved, first seen 2026-08-13)*

`async with httpx.AsyncClient() as client:` uses no `timeout`. httpx read timeout defaults to `None`, so a hung Kalshi response blocks the asyncio event loop indefinitely. All other HTTP callers pass explicit timeouts; Kalshi is the only exception.

**Fix:** `async with httpx.AsyncClient(timeout=httpx.Timeout(10.0, read=30.0)) as client:`

---

### [HIGH] `cancel_order()` bare Kalshi call — `scoring/tracker.py:263` *(unresolved, first seen 2026-08-13)*

`await self._kalshi.cancel_order(order.venue_order_id)` has no try/except. On API failure the exception propagates uncaught, `_update_order()` and `_sync_ledger()` are never called, the order stays `resting` in the DB, and `cancel_stale_orders()` will retry it on every subsequent poll — an infinite retry loop.

**Fix:** Wrap line 263 in `try/except Exception`; log the failure and return early with the order in its current state.

---

### [HIGH] DuckDB single-writer topology violated — `DbWriter` queue never wired in *(unresolved, first seen 2026-08-12)*

`db/writer.py` correctly implements the `asyncio.Queue` single-writer pattern but is imported nowhere in production code. Raw `duckdb.DuckDBPyConnection` objects are passed directly to all write-side modules. The most critical manifestation:

- `cli/brief.py:535` opens a **second** `duckdb.connect(runtime.db_path)` when invoked via `POST /api/brief/run` — two connections writing to the same file simultaneously. DuckDB will raise `database is locked` or cause silent data corruption.

Write violators (all bypass the queue):
- `scoring/ledger.py` — 6 write executes  
- `scoring/tracker.py` — 12 write executes  
- `scoring/scorecard.py` — 21 write executes  
- `scoring/prediction_log.py` — 3 write executes  
- `budget/tracker.py` — 1 write execute  
- `ops/alerts.py`, `ingestion/crisis_ingester.py`, `contracts/registry.py`, `backtest/runner.py`, `cli/brief.py`

**Fix (minimal):** Add a `filelock` in `cli/brief.py` to prevent concurrent CLI + server runs. **Fix (correct):** Wire `DbWriter` into the FastAPI lifespan and inject it into all write-side modules.

---

### [MEDIUM] `_load_private_key()` no error handling — `markets/kalshi.py:121-122` *(new)*

`Path(path).read_bytes()` and `load_pem_private_key()` are bare. A missing key file raises `FileNotFoundError`; malformed PEM raises `ValueError`. Since this is called from `__init__`, a bad key path crashes construction with a bare unhandled exception and zero diagnostic output.

**Fix:** Wrap in `try/except (FileNotFoundError, ValueError) as e: raise RuntimeError(f"Kalshi key load failed: {e}") from e`.

---

### [MEDIUM] `_normalize_market()` unguarded in loop — `markets/polymarket.py:269` *(new)*

Inside `get_iran_markets()`, `_normalize_market(m)` is called without try/except. One malformed market entry (e.g., non-numeric price string) raises an exception that aborts the entire fetch loop, silently losing all previously parsed markets.

**Fix:** Wrap the call in `try/except Exception` and `continue` on failure, logging the malformed entry.

---

### [MEDIUM] Calibration bucket query missing `score_date` filter — `scoring/scorecard.py:92-113` *(new)*

The `signal_calibration_max_gap` and `signal_calibration_buckets` metrics in `_compute_signal_quality()` query `signal_quality_evaluation` with no `score_date` filter, while every other query in the same function is filtered by `score_date`. These metrics always reflect all-time calibration data, not the requested day's data, making them meaningless for day-over-day comparison.

**Fix:** Add `WHERE model_was_correct IS NOT NULL AND score_date = ?` with `[score_date]` param to the query at line 92.

---

### [MEDIUM] Datetime timezone mismatch in scorecard — `scoring/scorecard.py:335` *(new)*

`datetime.now(timezone.utc) - latest` where `latest` is a `MAX(ended_at)` DuckDB timestamp. Whether DuckDB returns this as timezone-aware depends on driver version. A naive `latest` causes `TypeError: can't subtract offset-naive and offset-aware datetimes` at runtime.

**Fix:** `latest = latest.replace(tzinfo=timezone.utc) if latest.tzinfo is None else latest` before the subtraction.

---

### [MEDIUM] `compute_downstream_effects()` unit-scale mismatch — `simulation/cascade.py` / `prediction/oil_price.py` *(unresolved, first seen 2026-08-14)*

`cascade.py` expects `price_increase_pct` as a fraction (e.g., 0.30). `oil_price.py` computes it as an integer-scale percentage (e.g., 30.0). Passing this to downstream effects clamps `impact = min(1.0, dependency * 30.0)` to 1.0 for any country with non-trivial oil dependency, flattening all variation to the same maximum.

**Fix:** Divide `oil_price.py` output by 100 before passing to cascade.

---

### [MEDIUM] Silent $100 Brent fallback — `prediction/oil_price.py:188` *(unresolved, first seen 2026-08-14)*

Returns `100.0` silently when the EIA price feed is empty. No log warning — stale baseline silently corrupts every cascade and LLM prompt.

**Fix:** Add `logger.warning("No Brent price data; using fallback $%.1f", 100.0)`.

---

### [MEDIUM] `BudgetTracker` model-ID key mismatch + cold-start bug — `budget/tracker.py:11-14,33` *(unresolved, first seen 2026-08-14)*

`_PRICING` is keyed by short names (`"haiku"`, `"sonnet"`) but callers pass full version strings like `"claude-opus-4-20250514"`. Every unmatched key silently falls back to Sonnet pricing. Additionally, `_spend_today` resets to 0.0 on process restart regardless of prior spending.

---

### [MEDIUM] Zero-price orderbook levels — `markets/kalshi.py` `get_orderbook()` *(unresolved, first seen 2026-08-14)*

`_coerce_price()` returning `None` triggers `or 0.0` fallback, creating phantom `OrderbookLevel(price=0.0)` entries that skew spread/edge calculations.

---

### [MEDIUM] `SignalLedger.record_signal()` analytics columns never populated — `scoring/ledger.py` *(unresolved, first seen 2026-08-14)*

`SIGNAL_COLUMNS` omits `net_edge`, `gross_edge`, `fair_value_yes`, `fair_value_no`, `quote_is_stale`, and related columns that exist in the schema. These columns are always NULL, making edge-decay and calibration dashboard views unreliable.

---

### [LOW] Test suite requires `--ignore` flags to collect cleanly *(new)*

4 test files (`test_bench_forecast.py`, `test_calibration_metrics.py`, `test_recalibrators.py`, `test_selective.py`) import `numpy`/`pandas` at module level. Without the `bench` extra installed, pytest aborts collection with `ModuleNotFoundError` and zero tests run. Core suite is healthy (433 passed, 13 skipped) when those 4 are ignored.

**Fix:** Add `try/except ImportError: pytest.skip(...)` guards or `pytest.importorskip("numpy")` at the top of each affected file, or add `filterwarnings`/`collect_ignore` to `conftest.py`.

---

### [LOW] `db/schema.py` — migration nesting bug *(unresolved, first seen 2026-08-14)*

The migration adding columns to `contract_registry` is nested inside `if _table_exists(conn, "signal_ledger"):`. If `contract_registry` exists but `signal_ledger` does not, the migration is skipped and subsequent queries fail with `column not found`.

---

### [LOW] Orphaned agent tables — `db/schema.py` *(unresolved, first seen 2026-08-14)*

`agent_memory`, `agent_prompts`, and `decisions` tables exist in the schema; nothing writes to them. They are vestigial from the original Phase 1 swarm design that was replaced by the prediction-market architecture.

**Fix:** Drop via migration or document as reserved.

---

### [LOW] `requires-python` mismatch — `pyproject.toml` *(unresolved, first seen 2026-08-14)*

Specifies `>=3.11`; deployment target and runtime are Python 3.12.

---

## Recommendations (Priority Order)

1. **[P1 — 5 min]** Add `"cryptography>=41.0"` to `pyproject.toml`.
2. **[P1 — 10 min]** Add HTTP timeout to `kalshi.py` `_request()`.
3. **[P1 — 10 min]** Wrap `cancel_order()` Kalshi call in try/except.
4. **[P1 — 30 min]** Add file lock in `cli/brief.py` to prevent concurrent server + CLI DB writes.
5. **[P2 — 10 min]** Add `score_date` filter to calibration bucket query in `scorecard.py:92`.
6. **[P2 — 5 min]** Fix datetime TZ mismatch in `scorecard.py:335`.
7. **[P2 — 5 min]** Add error handling to `_load_private_key()` in `kalshi.py`.
8. **[P2 — 5 min]** Guard `_normalize_market()` call in `polymarket.py` loop.
9. **[P2 — 5 min]** Add `pytest.importorskip("numpy")` to 4 bench test files so pytest collects cleanly.
10. **[P2 — 15 min]** Fix `BudgetTracker` cold-start + model-ID key mismatch.
11. **[P3 — 15 min]** Fix `compute_downstream_effects()` unit-scale mismatch.
12. **[P3 — 10 min]** Log warning in `_get_current_brent()` before returning fallback.
13. **[P3 — 10 min]** Fix zero-price orderbook levels in `get_orderbook()`.
14. **[P3 — 15 min]** Populate missing analytics columns in `SignalLedger.record_signal()`.
15. **[P4 — 2 min]** Update `requires-python` to `>=3.12`.
16. **[P4 — 5 min]** Drop or document orphaned agent tables.

---

## Test Results

| Metric | Value |
|--------|-------|
| Tests passed | 433 |
| Tests skipped | 13 |
| Tests failed | 0 |
| Collection errors (bench extra) | 4 (`numpy`/`pandas`) — requires `--ignore` to collect cleanly |

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
| 2026-08-14 | YELLOW | 4 | No code changes |
| **2026-08-15** | **YELLOW** | **4** | +4 new medium findings; test collection now requires --ignore flags |

**12 consecutive YELLOW days.** The four P1 fixes (cryptography dep, HTTP timeout, cancel_order guard, file lock) are collectively under 1 hour of work and would clear three of the four HIGH issues immediately.
