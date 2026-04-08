---
phase: 02-prediction-persistence-calibration
plan: 02
subsystem: scoring
tags: [resolution, kalshi, settlement, pnl, backfill]

requires:
  - phase: 02-prediction-persistence-calibration
    provides: signal_ledger with resolution columns, --check-resolutions CLI flag stub
provides:
  - check_resolutions() function for Kalshi settlement polling
  - _backfill_signal() with BUY_YES/BUY_NO P&L computation
  - --check-resolutions CLI flag wired to resolution checker
affects: [02-03-calibration-queries]

tech-stack:
  added: []
  patterns: [Unix epoch to datetime conversion for Kalshi settlement_ts, CASE WHEN SQL for signal-dependent P&L]

key-files:
  created:
    - backend/src/parallax/scoring/resolution.py
    - backend/tests/test_resolution.py
  modified:
    - backend/src/parallax/cli/brief.py
    - backend/tests/test_brief.py

key-decisions:
  - "settlement_value validated as float in 0.0-1.0 range before use (T-02-04 mitigation)"
  - "Per-ticker try/except in check_resolutions prevents single API failure from blocking all resolution checks (T-02-07)"
  - "Backfill count determined via follow-up SELECT query since DuckDB UPDATE does not return rowcount directly"

patterns-established:
  - "Resolution backfill pattern: UPDATE with IS NULL guard prevents double-update"
  - "Unix epoch conversion: int settlement_ts -> datetime.fromtimestamp(ts, tz=utc).isoformat()"

requirements-completed: [PERS-02]

duration: 4min
completed: 2026-04-08
---

# Phase 2 Plan 2: Resolution Checker Summary

**Resolution checker polling Kalshi production API for settled contracts and backfilling signal_ledger with resolution_price, realized_pnl, and model_was_correct using parameterized CASE WHEN SQL**

## Performance

- **Duration:** 4 min
- **Started:** 2026-04-08T21:27:55Z
- **Completed:** 2026-04-08T21:31:42Z
- **Tasks:** 2
- **Files modified:** 4

## Accomplishments
- resolution.py module with _check_market_resolution(), _backfill_signal(), and check_resolutions()
- Kalshi settlement detection via status in ("determined", "finalized") with settlement_value validation
- P&L computation: BUY_YES = resolution_price - market_yes_price, BUY_NO = (1.0 - resolution_price) - market_no_price
- model_was_correct derivation: BUY_YES correct if resolution > 0.5, BUY_NO correct if resolution <= 0.5
- --check-resolutions CLI flag wired to _run_check_resolutions() with credential validation
- 6 resolution tests + 2 CLI flag tests, 208 total tests passing

## Task Commits

Each task was committed atomically:

1. **Task 1 RED: Failing tests for resolution checker** - `52c5c18` (test)
2. **Task 1 GREEN: Resolution checker implementation** - `1b9b1eb` (feat)
3. **Task 2: Wire --check-resolutions CLI flag** - `92a5b81` (feat)

## Files Created/Modified
- `backend/src/parallax/scoring/resolution.py` - Resolution checker module with settlement polling and signal_ledger backfill
- `backend/tests/test_resolution.py` - 6 tests covering detection, backfill, P&L, skip-resolved, end-to-end
- `backend/src/parallax/cli/brief.py` - _run_check_resolutions() helper, check_resolutions flag handling
- `backend/tests/test_brief.py` - 2 CLI flag parsing tests

## Decisions Made
- settlement_value validated as float in 0.0-1.0 range before use (threat model T-02-04)
- Per-ticker try/except prevents single Kalshi API failure from blocking all resolution checks (T-02-07)
- Backfill count via follow-up SELECT since DuckDB UPDATE does not expose rowcount natively

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

None.

## User Setup Required

None - resolution checking uses existing KALSHI_API_KEY and KALSHI_PRIVATE_KEY_PATH env vars.

## Next Phase Readiness
- Resolution data (resolution_price, realized_pnl, model_was_correct) now available in signal_ledger for calibration queries (Plan 03)
- check_resolutions() can be called programmatically or via CLI --check-resolutions

---
*Phase: 02-prediction-persistence-calibration*
*Completed: 2026-04-08*
