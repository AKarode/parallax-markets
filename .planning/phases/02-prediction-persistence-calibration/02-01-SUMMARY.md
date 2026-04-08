---
phase: 02-prediction-persistence-calibration
plan: 01
subsystem: database
tags: [duckdb, pydantic, json, prediction-log, persistence]

requires:
  - phase: 01-contract-registry-mapping-policy-evaluation-ledger
    provides: signal_ledger schema, create_tables(), SignalLedger class
provides:
  - prediction_log DuckDB table with full prediction context
  - PredictionLogEntry Pydantic model
  - PredictionLogger class with log_prediction() and get_predictions()
  - run_id correlation between predictions and signal_ledger entries
  - --check-resolutions and --calibration CLI flags (stubs for Plans 02/03)
affects: [02-02-resolution-polling, 02-03-calibration-queries]

tech-stack:
  added: []
  patterns: [JSON column round-trip via json.dumps/json.loads, run_id correlation across tables]

key-files:
  created:
    - backend/src/parallax/scoring/prediction_log.py
    - backend/tests/test_prediction_log.py
  modified:
    - backend/src/parallax/db/schema.py
    - backend/src/parallax/scoring/ledger.py
    - backend/src/parallax/cli/brief.py
    - backend/tests/test_schema.py
    - backend/tests/test_brief.py

key-decisions:
  - "cascade_inputs stored as None for all models in initial wiring -- extracting cascade state from predictors would require modifying predictor APIs, deferred per plan guidance"
  - "news_context is empty list for dry-run mode, populated from events[:20] in live mode"

patterns-established:
  - "JSON column pattern: json.dumps() before INSERT, json.loads() on SELECT for DuckDB JSON columns"
  - "run_id correlation: UUID generated once per run_brief() call, shared across prediction_log and signal_ledger"

requirements-completed: [PERS-01]

duration: 5min
completed: 2026-04-08
---

# Phase 2 Plan 1: Prediction Persistence Summary

**prediction_log DuckDB table with PredictionLogger class persisting all 3 model predictions per run with JSON-serialized evidence, news context, and cascade inputs**

## Performance

- **Duration:** 5 min
- **Started:** 2026-04-08T21:19:59Z
- **Completed:** 2026-04-08T21:25:22Z
- **Tasks:** 2
- **Files modified:** 7

## Accomplishments
- PredictionLogEntry model and PredictionLogger class with log_prediction()/get_predictions() following SignalLedger pattern
- prediction_log table DDL added to create_tables() with JSON columns for evidence, news_context, cascade_inputs
- run_id wired through entire pipeline: generated in run_brief(), passed to PredictionLogger and SignalLedger
- CLI flags --check-resolutions and --calibration added (handlers to be implemented in Plans 02/03)
- 200 tests passing (no regressions)

## Task Commits

Each task was committed atomically:

1. **Task 1: prediction_log table DDL + PredictionLogEntry model + PredictionLogger class** - `e47c615` (feat)
2. **Task 2: Wire prediction persistence + run_id into brief.py and signal_ledger** - `0420729` (feat)

## Files Created/Modified
- `backend/src/parallax/scoring/prediction_log.py` - PredictionLogEntry model + PredictionLogger class with DuckDB persistence
- `backend/src/parallax/db/schema.py` - Added prediction_log table DDL, run_id column to signal_ledger
- `backend/src/parallax/scoring/ledger.py` - Added run_id to SignalRecord, record_signal(), INSERT, _row_to_record()
- `backend/src/parallax/cli/brief.py` - run_id generation, PredictionLogger wiring, CLI flags
- `backend/tests/test_prediction_log.py` - 8 tests covering persistence, JSON round-trip, run_id correlation
- `backend/tests/test_schema.py` - Updated expected table set to include prediction_log
- `backend/tests/test_brief.py` - Added dry-run persistence test

## Decisions Made
- cascade_inputs stored as None for all models initially -- extracting cascade state post-predict would require modifying predictor return values, which is out of scope per plan guidance (D-01 says cascade_inputs is nullable)
- news_context built from events[:20] in live mode (first 20 news events), empty list in dry-run mode

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

None.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness
- prediction_log table ready for resolution polling (Plan 02) to cross-reference predictions with outcomes
- run_id correlation enables calibration queries (Plan 03) to trace signals back to prediction runs
- CLI flags --check-resolutions and --calibration ready for handler implementations

---
*Phase: 02-prediction-persistence-calibration*
*Completed: 2026-04-08*
