---
phase: 01-contract-registry-mapping-policy-evaluation-ledger
plan: 02
subsystem: contracts
tags: [mapping-policy, proxy-discounting, edge-calculation, probability-inversion]

requires:
  - ContractRegistry with get_contracts_for_model()
  - ProxyClass enum and MappingResult model
  - PredictionOutput and MarketPrice schemas
provides:
  - MappingPolicy class with evaluate() method
  - Proxy-aware confidence discounting (DIRECT=1.0, NEAR=0.6, LOOSE=0.3)
  - Probability inversion for inverted contracts
  - Threshold-based trade filtering
affects: [01-03-signal-ledger, cli-brief-integration]

tech-stack:
  added: []
  patterns: [proxy-discount-multiplication, probability-inversion-for-inverted-contracts, sorted-audit-trail]

key-files:
  created:
    - backend/src/parallax/contracts/mapping_policy.py
    - backend/tests/test_mapping_policy.py
  modified: []

key-decisions:
  - "Registry filters NONE proxy contracts before MappingPolicy sees them, keeping policy logic clean"
  - "Missing market prices are skipped gracefully with debug logging rather than raising errors"

patterns-established:
  - "MappingPolicy: stateless evaluator taking prediction + market prices, returning sorted MappingResult list"

requirements-completed: [REG-03]

duration: 2min
completed: 2026-04-08
---

# Phase 1 Plan 02: Mapping Policy Summary

**Proxy-aware mapping policy that evaluates predictions against all registry contracts with confidence discounting, probability inversion, and threshold filtering**

## Performance

- **Duration:** 2 min
- **Started:** 2026-04-08T08:13:04Z
- **Completed:** 2026-04-08T08:15:20Z
- **Tasks:** 1/1
- **Files created:** 2

## Accomplishments

### Task 1: MappingPolicy class (TDD)

- Created `MappingPolicy` class with `evaluate()` method that replaces heuristic `_map_predictions_to_markets()`
- Evaluates all active contracts from registry for each prediction model type
- Applies confidence discount by proxy class: DIRECT=1.0, NEAR_PROXY=0.6, LOOSE_PROXY=0.3
- Inverts model probability when contract proposition is inverted (e.g., Hormuz closure vs reopening)
- Filters by configurable `min_effective_edge_pct` threshold (default 5%)
- Returns all evaluated mappings sorted by abs(effective_edge) descending for audit
- Skips contracts without market price data gracefully (debug log, no crash)
- 10 test classes covering all proxy classes, inversion, thresholds, audit trail, missing data, sorting

## Deviations from Plan

None - plan executed exactly as written.

## Verification

- All 10 mapping policy tests passing
- All 177 tests passing (167 existing + 10 new)
- Import verified: `from parallax.contracts.mapping_policy import MappingPolicy`
- DIRECT proxy gets full edge (discount=1.0)
- NEAR_PROXY gets 60% edge (discount=0.6)
- LOOSE_PROXY gets 30% edge (discount=0.3)
- NONE proxy contracts excluded by registry (not evaluated)
- Inverted contracts flip probability before edge calculation
- Below-threshold mappings have should_trade=False with reason string
- Results sorted by abs(effective_edge) descending

## Commits

| Hash | Message |
|------|---------|
| 4d06e51 | test(01-02): add failing tests for MappingPolicy decision logic |
| dcc3055 | feat(01-02): implement MappingPolicy with proxy-aware edge discounting |

## Self-Check: PASSED
