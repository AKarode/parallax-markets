---
phase: 03-paper-trading-evaluation-continuous-improvement
plan: 05
subsystem: contracts/mapping_policy, cli/brief
tags: [discount-adjustment, calibration, gap-closure]
dependency_graph:
  requires: [03-04]
  provides: [update_discounts_from_history]
  affects: [contracts/mapping_policy.py, cli/brief.py]
tech_stack:
  added: []
  patterns: [bounded-ema-discount-adjustment, min-signal-gate]
key_files:
  created: []
  modified:
    - backend/src/parallax/contracts/mapping_policy.py
    - backend/src/parallax/cli/brief.py
    - backend/tests/test_mapping_policy.py
decisions:
  - EMA blend factor 0.7/0.3 (default/hit_rate) for conservative adjustment
  - Lazy import of hit_rate_by_proxy_class inside method to match codebase pattern
metrics:
  duration: 3 minutes
  completed: 2026-04-09
  tasks_completed: 2
  tasks_total: 2
  files_created: 0
  files_modified: 3
---

# Phase 3 Plan 5: Discount Factor Auto-Adjustment Summary

Bounded EMA discount adjustment from calibration hit rate data, closing the TRAD-05 gap so all three calibration levers (min_edge thresholds, model prompt track records, discount factors) respond to historical performance.

## Completed Tasks

| # | Task | Commit | Key Changes |
|---|------|--------|-------------|
| 1 | Add update_discounts_from_history() to MappingPolicy with tests | d530413 (RED), 35f57e4 (GREEN) | DISCOUNT_BOUNDS constants, MIN_SIGNALS_FOR_DISCOUNT=5, EMA formula, 7 new tests |
| 2 | Wire update_discounts_from_history() in brief.py pipeline | 56378d8 | Single-line wiring after update_thresholds_from_history() |

## Implementation Details

### update_discounts_from_history() Method

Added to `MappingPolicy` class following the same pattern as `update_thresholds_from_history()`:

1. Calls `hit_rate_by_proxy_class(conn)` from calibration module (lazy import)
2. Skips proxy classes with fewer than 5 resolved signals (`MIN_SIGNALS_FOR_DISCOUNT`)
3. Computes bounded EMA: `new = default * 0.7 + hit_rate * 0.3`
4. Applies hard bounds per proxy class via `DISCOUNT_BOUNDS`:
   - DIRECT: [0.8, 1.0] -- never drops below 0.8
   - NEAR_PROXY: [0.2, 0.8]
   - LOOSE_PROXY: [0.1, 0.5] -- never rises above 0.5
   - NONE: [0.0, 0.0] -- never adjusted
5. Updates `contract_proxy_map.confidence_discount` in DuckDB
6. Logs each adjustment at INFO level

### Pipeline Wiring

In `brief.py`, `update_discounts_from_history(conn)` is called immediately after `update_thresholds_from_history(conn)`, before the `evaluate()` loop. Both calls are grouped under `# Auto-tune from historical performance`.

## Deviations from Plan

None -- plan executed exactly as written.

## Verification

- 268 tests pass (all existing + 7 new discount tests), zero failures
- Acceptance criteria grep checks all pass:
  - `update_discounts_from_history` defined in mapping_policy.py (1)
  - `hit_rate_by_proxy_class` referenced in mapping_policy.py (3)
  - `DISCOUNT_BOUNDS` in mapping_policy.py (2)
  - `MIN_SIGNALS_FOR_DISCOUNT` in mapping_policy.py (3)
  - `TestDiscountFromHistory` in test_mapping_policy.py (1)
  - 17 total test functions in test_mapping_policy.py

## Self-Check: PASSED
