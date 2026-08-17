# Parallax Health Check — 2026-08-17

**Status: YELLOW**

## Summary

No code changes since the 2026-08-15 report (confirmed via `git log --since="2026-08-15"`). All four HIGH issues and all eight MEDIUM issues from prior reports remain unresolved. Test suite is stable at 433 passed / 13 skipped with the same four bench-extra collection errors requiring `--ignore` flags. **This is the 14th consecutive YELLOW day.**

---

## Issues Found

### [HIGH] Missing `cryptography` dependency — `pyproject.toml` *(unresolved, first seen 2026-08-13)*

`KalshiClient` imports `cryptography.hazmat.primitives` for RSA-PSS signing. `cryptography` is absent from `[project.dependencies]`. A clean `pip install -e .` silently omits it; all Kalshi API calls fail with `ImportError` at runtime.

**Fix:** Add `"cryptography>=41.0"` to `[project.dependencies]` in `pyproject.toml`.

---

### [HIGH] No HTTP timeout on Kalshi API requests — `markets/kalshi.py:154` *(unresolved, first seen 2026-08-13)*

`async with httpx.AsyncClient() as client:` has no `timeout=` argument. httpx read timeout defaults to `None`, so a hung Kalshi response blocks the asyncio event loop indefinitely. All other HTTP callers in the codebase set explicit timeouts; this is the only exception.

**Fix:** `async with httpx.AsyncClient(timeout=httpx.Timeout(10.0, read=30.0)) as client:`

---

### [HIGH] `cancel_order()` bare Kalshi call — `scoring/tracker.py:263` *(unresolved, first seen 2026-08-13)*

`await self._kalshi.cancel_order(order.venue_order_id)` has no try/except. On API failure the exception propagates uncaught, `_update_order()` and `_sync_ledger()` are never called, the order stays `resting` in the DB, and `cancel_stale_orders()` retries it on every subsequent poll — an infinite retry loop.

**Fix:** Wrap line 263 in `try/except Exception`; log the failure and return early.

---

### [HIGH] DuckDB single-writer topology violated — `DbWriter` queue unused in production *(unresolved, first seen 2026-08-12)*

`db/writer.py` implements the correct `asyncio.Queue` single-writer pattern but is imported nowhere in production code. All write-side modules receive a raw `duckdb.DuckDBPyConnection` and call `.execute()` directly. The critical manifestation: `cli/brief.py` opens a **second** `duckdb.connect(runtime.db_path)` when invoked via `POST /api/brief/run` — two connections writing to the same file simultaneously, risking `database is locked` errors or silent data corruption.

Write violators (all bypass the queue):
- `scoring/ledger.py` — 6 write executes
- `scoring/tracker.py` — 12 write executes
- `scoring/scorecard.py` — 21 write executes
- `scoring/prediction_log.py` — 3 write executes
- `budget/tracker.py`, `ops/alerts.py`, `ingestion/crisis_ingester.py`, `contracts/registry.py`, `backtest/runner.py`, `cli/brief.py`

**Fix (minimal):** Add a `filelock` in `cli/brief.py` to prevent concurrent CLI + server runs. **Fix (correct):** Wire `DbWriter` into the FastAPI lifespan and inject it into all write-side modules.

---

### [MEDIUM] `_load_private_key()` unguarded — `markets/kalshi.py:121-122` *(unresolved, first seen 2026-08-15)*

`Path(path).read_bytes()` and `load_pem_private_key()` raise bare `FileNotFoundError` / `ValueError`. Called from `__init__`, a bad key path crashes construction with zero diagnostic output.

**Fix:** `try/except (FileNotFoundError, ValueError) as e: raise RuntimeError(f"Kalshi key load failed: {e}") from e`.

---

### [MEDIUM] `_normalize_market()` unguarded in loop — `markets/polymarket.py:269` *(unresolved, first seen 2026-08-15)*

One malformed market entry aborts the entire Polymarket fetch loop, silently losing all previously parsed markets.

**Fix:** Wrap call in `try/except Exception`, `continue` on failure with a logged warning.

---

### [MEDIUM] Calibration bucket query missing `score_date` filter — `scoring/scorecard.py:92-113` *(unresolved, first seen 2026-08-15)*

`signal_calibration_max_gap` and `signal_calibration_buckets` query `signal_quality_evaluation` without a `score_date` filter; all other metrics in the same function are day-scoped. These two metrics always reflect all-time data, making them useless for day-over-day comparison.

**Fix:** Add `WHERE model_was_correct IS NOT NULL AND score_date = ?` with `[score_date]` param.

---

### [MEDIUM] Datetime timezone mismatch — `scoring/scorecard.py:335` *(unresolved, first seen 2026-08-15)*

`datetime.now(timezone.utc) - latest` where `latest` is a `MAX(ended_at)` from DuckDB. A naive `latest` causes `TypeError: can't subtract offset-naive and offset-aware datetimes`.

**Fix:** `latest = latest.replace(tzinfo=timezone.utc) if latest.tzinfo is None else latest` before the subtraction.

---

### [MEDIUM] `compute_downstream_effects()` unit-scale mismatch — `simulation/cascade.py` / `prediction/oil_price.py` *(unresolved, first seen 2026-08-14)*

`cascade.py` expects `price_increase_pct` as a fraction (e.g., 0.30). `oil_price.py` computes it as integer-scale (e.g., 30.0). `impact = min(1.0, dependency * 30.0)` clamps every country with meaningful oil dependency to `1.0`, removing all granularity from the downstream effect model.

**Fix:** Divide `oil_price.py` output by 100 before passing to cascade.

---

### [MEDIUM] Silent $100 Brent fallback — `prediction/oil_price.py:188` *(unresolved, first seen 2026-08-14)*

Returns `100.0` with no log warning when the EIA price feed is empty. Silently corrupts every cascade and LLM prompt during feed outages.

**Fix:** Add `logger.warning("No Brent price data; using fallback $%.1f", 100.0)`.

---

### [MEDIUM] `BudgetTracker` model-ID key mismatch + cold-start bug — `budget/tracker.py:11-14,33` *(unresolved, first seen 2026-08-14)*

`_PRICING` keyed by short names (`"haiku"`, `"sonnet"`) but callers pass full version strings (`"claude-opus-4-20250514"`). Every unmatched key silently falls back to Sonnet pricing. `_spend_today` resets to 0.0 on process restart regardless of prior spending recorded in `llm_usage`.

---

### [MEDIUM] Zero-price orderbook levels — `markets/kalshi.py` *(unresolved, first seen 2026-08-14)*

`_coerce_price()` returning `None` triggers `or 0.0` fallback, creating phantom `OrderbookLevel(price=0.0)` entries that skew spread and edge calculations.

---

### [MEDIUM] `SignalLedger.record_signal()` analytics columns never populated — `scoring/ledger.py` *(unresolved, first seen 2026-08-14)*

`SIGNAL_COLUMNS` omits `net_edge`, `gross_edge`, `fair_value_yes`, `fair_value_no`, `quote_is_stale`, and related columns that exist in the schema. These columns are always NULL, making edge-decay and calibration dashboard views unreliable.

---

### [LOW] Test suite requires `--ignore` flags to collect cleanly *(unresolved, first seen 2026-08-15)*

4 test files (`test_bench_forecast.py`, `test_calibration_metrics.py`, `test_recalibrators.py`, `test_selective.py`) import `numpy`/`pandas` at module level; without the `bench` extra, pytest collection fails with `ModuleNotFoundError`.

**Fix:** Add `pytest.importorskip("numpy")` at the top of each affected file, or add `collect_ignore` to `conftest.py`.

---

### [LOW] `db/schema.py` — migration nesting bug *(unresolved, first seen 2026-08-14)*

The migration adding columns to `contract_registry` is nested inside `if _table_exists(conn, "signal_ledger"):`. If `contract_registry` exists but `signal_ledger` does not, the migration silently skips.

---

### [LOW] Orphaned agent tables — `db/schema.py` *(unresolved, first seen 2026-08-14)*

`agent_memory`, `agent_prompts`, and `decisions` tables exist in the schema but nothing writes to them. They are vestigial from the original Phase 1 swarm design.

---

### [LOW] `requires-python` mismatch — `pyproject.toml` *(unresolved, first seen 2026-08-14)*

Specifies `>=3.11`; deployment target and runtime are Python 3.12.

---

## Spec/Plan Consistency Note

The Phase 1 design spec (`docs/superpowers/specs/2026-03-30-parallax-phase1-design.md`) describes a geopolitical agent swarm simulator with ~50 LLM agents, H3 hex map visualization (deck.gl/MapLibre), and GDELT BigQuery ingestion. The actual implementation is a prediction market edge-finder (3 LLM models vs Kalshi/Polymarket prices). This architectural pivot is intentional and documented in `CLAUDE.md` as the current project definition. The spec docs have not been updated to reflect this, but this is a documentation inconsistency rather than a code issue.

---

## Recommendations (Priority Order)

1. **[P1 — 5 min]** Add `"cryptography>=41.0"` to `pyproject.toml`.
2. **[P1 — 10 min]** Add HTTP timeout to `kalshi.py:154`.
3. **[P1 — 10 min]** Wrap `cancel_order()` call in `scoring/tracker.py:263` in try/except.
4. **[P1 — 30 min]** Add `filelock` in `cli/brief.py` to prevent concurrent server + CLI DB writes (or wire `DbWriter` through the stack — ~2h).
5. **[P2 — 10 min]** Add `score_date` filter to calibration query in `scorecard.py:92`.
6. **[P2 — 5 min]** Fix datetime TZ mismatch in `scorecard.py:335`.
7. **[P2 — 5 min]** Guard `_load_private_key()` in `kalshi.py`.
8. **[P2 — 5 min]** Guard `_normalize_market()` call in `polymarket.py`.
9. **[P2 — 5 min]** Add `pytest.importorskip("numpy")` to 4 bench test files.
10. **[P2 — 15 min]** Fix `BudgetTracker` model-ID key mismatch + cold-start.
11. **[P3 — 15 min]** Fix `compute_downstream_effects()` unit-scale mismatch.
12. **[P3 — 5 min]** Log warning in `_get_current_brent()` before returning fallback.
13. **[P3 — 10 min]** Fix zero-price orderbook levels in `get_orderbook()`.
14. **[P3 — 15 min]** Populate missing analytics columns in `SignalLedger.record_signal()`.
15. **[P4 — 2 min]** Update `requires-python` to `>=3.12`.
16. **[P4 — 10 min]** Fix migration nesting bug in `db/schema.py`.
17. **[P4 — 5 min]** Drop or document orphaned agent tables.

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
| 2026-08-12 | YELLOW | 2 | DbWriter violation added |
| 2026-08-13 | YELLOW | 4 | +5 new findings |
| 2026-08-14 | YELLOW | 4 | No code changes |
| 2026-08-15 | YELLOW | 4 | +4 new medium findings |
| **2026-08-17** | **YELLOW** | **4** | No code changes in 2 days |

**14 consecutive YELLOW days. The four P1 fixes are collectively under 1 hour of work and would clear three of the four HIGH issues immediately.**
