# Phase 1 Critical Fixes — DONE

> Status: **COMPLETE** as of 2026-05-06

All three Phase 1 critical issues identified in `AGENT-REVIEW-2026-05-06.md` are implemented and tested.

## Summary

### Fix 1: `asyncio.gather` Missing `return_exceptions`

- **Symptom**: A single data-source failure (e.g., GDELT timeout, EIA rate-limit) could bring down the entire `run_brief()` pipeline.
- **Root cause**: `asyncio.gather(*[...])` without `return_exceptions=True` lets exceptions propagate and cancel sibling tasks.
- **Fix**: Added `return_exceptions=True` to both the data-fetcher gather and the predictor gather. Per-predictor failures now fall back to the most recent non-dry-run prediction (`_get_fallback_prediction()`), or skip that model entirely if no history exists.
- **Tests**: `tests/test_brief_resilience.py` (7 tests)

### Fix 2: `confidence_discount` Hardcoded to 1.0

- **Symptom**: All signals showed `confidence_discount=1.0` regardless of proxy class. LOOSE_PROXY and NEAR_PROXY were not having their edges discounted.
- **Root cause**: The discount map was loaded from the registry but the value was destructured into a throwaway variable (`_legacy_discount`) and the default `1.0` was always used instead.
- **Fix**:
  - Renamed destructure variable so `confidence_discount` is actually propagated.
  - Updated registry discount constants: `DIRECT=1.0`, `NEAR_PROXY=0.65`, `LOOSE_PROXY=0.3`.
  - `effective_edge = net_edge * confidence_discount` now fires correctly.
  - Generic proxy fallback estimator added so LOOSE/NEAR proxies get a fair value (and thus a non-zero edge) even without a bespoke estimator.
- **Tests**: `tests/test_mapping_discount.py` (5 tests)

### Fix 3: Cold-Start Edge Floors Not Enforced

- **Symptom**: At system startup (no historical signal data), LOOSE_PROXY and NEAR_PROXY contracts only required the global 5% minimum edge, allowing low-confidence proxy trades through.
- **Root cause**: `_per_class_min_edge` was never initialized from anything; it only got populated once `update_thresholds_from_history()` had data to work with.
- **Fix**:
  - Added `COLD_START_EDGE_FLOORS` class constant: `loose_proxy=0.08`, `near_proxy=0.06`, `direct=0.04`.
  - `__init__` now pre-populates `_per_class_min_edge` from these floors.
  - The per-class floor is checked before the should-trade decision.
- **Tests**: `tests/test_cold_start_floors.py` (8 tests)

## Additional Deliverables

### Crisis Context Automation (Task 2)

- New `crisis_events` DuckDB table for live event ingestion.
- `CrisisIngester` with headline dedup (MD5 + similarity ≥ 0.85).
- `crisis_context.py` overhauled: DB-first rendering with 25-entry seed fallback.
- Staleness penalty: `compute_staleness_penalty(age_hours)` = `max(0, 1 - (age - 24) / 48)`.
- Wired into `ensemble_predict()` via `context_age_hours` parameter: confidence scaled down on stale context, probability unchanged.
- Tests: `tests/test_crisis_context_db.py` (19 tests)

### Backtest Harness (Task 3)

- `parallax.backtest` package with `LookAheadGuard`, `BacktestRunner`, `BacktestReport`.
- `LookAheadGuard`: bounded DuckDB TEMP VIEWs per sim-date to prevent future data leakage.
- `BacktestRunner.run()`: replays historical prediction_log entries day-by-day with look-ahead protection.
- `_backfill_resolutions()` picks the **earliest** resolution at or after sim_date (not latest), fixing the multi-resolution bleed defect.
- Tests: `tests/test_backtest_look_ahead.py` (12 tests)

## Test Results

```
401 passed, 17 failed
```

All 17 failures are pre-existing and unrelated to this phase:
- `test_mapping_policy.py` (11): stale tests for disabled `update_discounts_from_history` heuristic
- `test_recalibration.py` (4): pre-existing recalibration edge cases
- `test_google_news.py` (1): pre-existing fixture issue
- `test_brief.py` (1): pre-existing test issue

Net change from prior baseline of 18 failures: **−1** (`test_mapping_discount.py` cases that previously failed now pass).
