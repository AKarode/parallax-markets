---
phase: 02-prediction-persistence-calibration
plan: 03
subsystem: scoring
tags: [calibration, duckdb, sql, hit-rate, edge-decay, cli]

requires:
  - phase: 02-prediction-persistence-calibration
    provides: signal_ledger with resolution columns (model_was_correct, realized_pnl), prediction_log table
provides:
  - hit_rate_by_proxy_class() query for accuracy by proxy class
  - calibration_curve() query for predicted vs actual probability buckets
  - edge_decay() query for P&L analysis by edge size
  - calibration_report() formatted text output with 7-day data guard
  - --calibration CLI flag wired to calibration report
affects: []

tech-stack:
  added: []
  patterns: [literal SQL queries against DuckDB for analytics, 7-day minimum data guard pattern]

key-files:
  created:
    - backend/src/parallax/scoring/calibration.py
    - backend/tests/test_calibration.py
  modified:
    - backend/src/parallax/cli/brief.py
    - backend/tests/test_brief.py

key-decisions:
  - "calibration_report returns insufficient data message as string rather than raising exception -- CLI-friendly design per plan guidance"
  - "All queries use literal SQL with no parameterization -- tiny data volume, no user input (T-02-08 accept)"

patterns-established:
  - "Analytics query pattern: literal SQL returning list[dict] for easy formatting and testing"
  - "Data guard pattern: _check_minimum_data() validates data span before running analysis"

requirements-completed: [PERS-03, PERS-04]

duration: 3min
completed: 2026-04-08
---

# Phase 2 Plan 3: Calibration Queries Summary

**3 calibration SQL queries (hit rate by proxy class, calibration curve, edge decay) with 7-day minimum data guard and --calibration CLI flag for formatted report output**

## Performance

- **Duration:** 3 min
- **Started:** 2026-04-08T21:33:56Z
- **Completed:** 2026-04-08T21:37:23Z
- **Tasks:** 2
- **Files modified:** 4

## Accomplishments
- calibration.py module with 3 SQL analytics queries returning list[dict] for easy testing and formatting
- 7-day minimum data guard prevents premature calibration analysis (checks prediction_log date span)
- calibration_report() generates formatted text with HIT RATE BY PROXY CLASS, CALIBRATION CURVE, and EDGE DECAY sections
- --calibration CLI flag wired via _run_calibration() helper (synchronous, no async needed)
- 219 tests passing (11 new calibration + CLI tests, no regressions)

## Task Commits

Each task was committed atomically:

1. **Task 1 RED: Failing tests for calibration queries** - `3e37e92` (test)
2. **Task 1 GREEN: Calibration queries module implementation** - `1b61b3a` (feat)
3. **Task 2: Wire --calibration CLI flag** - `93e5c80` (feat)

## Files Created/Modified
- `backend/src/parallax/scoring/calibration.py` - 3 SQL queries + text report formatter + 7-day data guard
- `backend/tests/test_calibration.py` - 9 tests covering all 3 queries, data guard, report format, empty results
- `backend/src/parallax/cli/brief.py` - _run_calibration() helper, args.calibration handler
- `backend/tests/test_brief.py` - 2 CLI flag parsing tests for --calibration

## Decisions Made
- calibration_report returns insufficient data message as string rather than raising -- keeps CLI output clean without try/except
- All queries use literal SQL (no parameterization needed) per threat model T-02-08

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

None.

## User Setup Required

None - calibration queries operate on existing DuckDB data.

## Next Phase Readiness
- Calibration analysis available via `python -m parallax.cli.brief --calibration`
- All 3 Phase 2 plans complete: prediction persistence, resolution checker, calibration queries
- System now has full feedback loop: predict -> trade -> resolve -> calibrate

---
*Phase: 02-prediction-persistence-calibration*
*Completed: 2026-04-08*
