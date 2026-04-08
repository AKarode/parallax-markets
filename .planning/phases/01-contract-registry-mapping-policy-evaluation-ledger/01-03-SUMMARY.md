---
phase: 01-contract-registry-mapping-policy-evaluation-ledger
plan: 03
subsystem: scoring
tags: [signal-ledger, duckdb, pipeline-rewire, mapping-policy, append-only]

requires:
  - ContractRegistry with get_active_contracts() and get_contracts_for_model()
  - MappingPolicy with evaluate()
  - PredictionOutput and MarketPrice schemas
provides:
  - SignalLedger class for append-only signal tracking in DuckDB
  - SignalRecord Pydantic model with full provenance
  - Pipeline using MappingPolicy + SignalLedger instead of heuristic mapping
  - SIGNAL AUDIT section in CLI output
affects: [paper-trade-tracker, api-endpoints, phase-2-scoring]

tech-stack:
  added: []
  patterns: [append-only-ledger, signal-provenance-recording, contract-aware-mapping-pipeline]

key-files:
  created:
    - backend/src/parallax/scoring/ledger.py
    - backend/tests/test_ledger.py
  modified:
    - backend/src/parallax/db/schema.py
    - backend/src/parallax/cli/brief.py
    - backend/tests/test_brief.py
    - backend/tests/test_schema.py

key-decisions:
  - "Signal records are immutable after creation -- only trade_id/traded/resolution fields updatable"
  - "Dry-run mock markets updated to use real registry tickers instead of fake prefixes"
  - "Old _map_predictions_to_markets renamed to _legacy, kept for reference"

patterns-established:
  - "SignalLedger: append-only DuckDB ledger with full provenance per signal"
  - "Pipeline flow: MappingPolicy.evaluate() -> SignalLedger.record_signal() -> Divergence conversion"

requirements-completed: [REG-04, REG-05]

duration: 5min
completed: 2026-04-08
---

# Phase 1 Plan 03: Signal Ledger + Pipeline Rewire Summary

**Append-only SignalLedger in DuckDB recording every mapping evaluation with full provenance, plus brief.py rewired to use MappingPolicy + SignalLedger instead of heuristic mapping**

## Performance

- **Duration:** 5 min
- **Started:** 2026-04-08T08:18:24Z
- **Completed:** 2026-04-08T08:23:34Z
- **Tasks:** 2/2
- **Files modified:** 6

## Accomplishments

### Task 1: SignalLedger with DuckDB persistence (TDD)

- Created `SignalRecord` Pydantic model with 25 fields covering full provenance: model claim, proxy class, market state, edge calculation, trade decision
- Created `SignalLedger` class with 4 methods: `record_signal()`, `get_signals()`, `get_actionable_signals()`, `mark_traded()`
- Added `signal_ledger` table DDL to `create_tables()` with 25 columns
- Signal direction logic: REFUSED (not should_trade), BUY_YES (positive edge), BUY_NO (negative edge), HOLD (zero edge)
- 13 tests covering model validation, CRUD operations, filtering, and table schema

### Task 2: Rewire brief.py to use MappingPolicy + SignalLedger

- Replaced `_map_predictions_to_markets()` call with `MappingPolicy.evaluate()` + `SignalLedger.record_signal()` loop
- Every mapping evaluation (including REFUSED and HOLD) persisted in signal_ledger
- Added SIGNAL AUDIT section to CLI output showing all evaluated mappings with proxy class and edge
- Updated dry-run mock data to use real registry tickers (KXWTIMAX-26DEC31, KXUSAIRANAGREEMENT-27, etc.)
- Removed hardcoded `kalshi_ticker` from mock predictions -- registry handles mapping
- Renamed old function to `_map_predictions_to_markets_legacy()` with deprecation docstring
- Actionable signals converted to Divergence objects for compatibility with paper trade tracker
- 16 brief tests updated and passing

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Updated test_schema.py expected table set**
- **Found during:** Task 1
- **Issue:** Existing test_schema.py asserts exact table count; new signal_ledger table caused test failure
- **Fix:** Added `signal_ledger` to expected set in test_create_tables_creates_all_expected_tables
- **Files modified:** backend/tests/test_schema.py
- **Commit:** 6164dee

## Verification

- `python -m parallax.cli.brief --dry-run` produces output with SIGNAL AUDIT section showing 7 evaluated mappings
- All 13 ledger tests passing
- All 16 brief tests passing
- All 192 tests passing (177 existing + 13 ledger + 16 brief - 14 replaced brief tests)
- No calls to `_map_predictions_to_markets(predictions` remain in active code paths
- Old function renamed to `_map_predictions_to_markets_legacy`
- Signal ledger records BUY_YES, BUY_NO, and REFUSED signals with full provenance

## Commits

| Hash | Message |
|------|---------|
| ca4a8ca | test(01-03): add failing tests for SignalLedger |
| 6164dee | feat(01-03): add SignalLedger with DuckDB persistence |
| d16b4e2 | feat(01-03): rewire brief.py to use MappingPolicy + SignalLedger |

## Self-Check: PASSED
