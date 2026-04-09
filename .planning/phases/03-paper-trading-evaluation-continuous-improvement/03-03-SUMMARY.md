---
phase: 03-paper-trading-evaluation-continuous-improvement
plan: 03
subsystem: prediction-track-record
tags: [track-record, prompt-injection, self-correction, calibration]
dependency_graph:
  requires: [scoring/ledger.py, db/schema.py, prediction/oil_price.py, prediction/ceasefire.py, prediction/hormuz.py, cli/brief.py]
  provides: [scoring/track_record.py, db_conn parameter on all predictors, YOUR TRACK RECORD prompt section]
  affects: [prediction/oil_price.py, prediction/ceasefire.py, prediction/hormuz.py, cli/brief.py]
tech_stack:
  added: []
  patterns: [per-model track record injection, parameterized SQL queries, lazy import for track_record module]
key_files:
  created: [backend/src/parallax/scoring/track_record.py, backend/tests/test_track_record.py]
  modified: [backend/src/parallax/prediction/oil_price.py, backend/src/parallax/prediction/ceasefire.py, backend/src/parallax/prediction/hormuz.py, backend/src/parallax/cli/brief.py]
decisions:
  - "D-10: Track record format uses aggregate stats line + last 3 individual outcomes"
  - "D-11: Per-model only, no cross-model stats"
  - "D-12: Shared build_track_record() utility in scoring/track_record.py"
  - "D-13: db_conn parameter with None default on all predict() methods"
  - "D-14: brief.py moves DuckDB connection before prediction calls"
metrics:
  duration: "4m 45s"
  completed: "2026-04-09T01:48:27Z"
  tasks_completed: 2
  tasks_total: 2
  tests_added: 8
  tests_passing: 253
---

# Phase 3 Plan 3: Prompt Feedback Injection Summary

Per-model track record injection into LLM prompts via shared build_track_record() utility querying signal_ledger with parameterized SQL

## What Was Built

### Task 1: build_track_record() shared utility (TDD)

Created `backend/src/parallax/scoring/track_record.py` with a single function that queries signal_ledger for resolved signals belonging to a specific model_id. Returns:
- Aggregate stats line: "{correct}/{total} correct ({hit_rate}% hit rate)"
- Last 3 resolved signals with ticker, predicted probability, resolution price, CORRECT/WRONG label, and signal direction
- Fallback text "No track record available yet." when no resolved signals exist

8 tests cover: empty data fallback, nonexistent model, aggregate stats accuracy, last 3 signal display, CORRECT/WRONG labels, per-model isolation (D-11), output size limit (<1600 chars), and signal direction display.

### Task 2: Predictor wiring and brief.py integration

Modified all 3 prediction models (oil_price.py, ceasefire.py, hormuz.py):
- Added `db_conn: duckdb.DuckDBPyConnection | None = None` parameter to `predict()`
- Added `## YOUR TRACK RECORD\n{track_record}` section to each system prompt
- Added track record building logic at start of predict() with lazy import

Modified brief.py:
- Moved DuckDB connection creation before prediction calls (was after)
- Passes `db_conn=conn` to all 3 predict() calls in live mode
- Dry-run mode creates its own connection after predictions (no track record needed for mocks)

## Deviations from Plan

None -- plan executed exactly as written.

## Commits

| # | Hash | Type | Description |
|---|------|------|-------------|
| 1 | 8b5bfcb | test | Add failing tests for build_track_record utility |
| 2 | 528e245 | feat | Implement build_track_record() shared utility |
| 3 | 477a475 | feat | Wire track record injection into all 3 predictors and brief.py |

## Threat Surface

T-03-07 mitigated: All SQL queries use parameterized `?` placeholders for model_id -- no string interpolation.

No new threat flags. Track record contains only model performance data (hit rates, probabilities) per T-03-08 acceptance.

## Self-Check: PASSED
