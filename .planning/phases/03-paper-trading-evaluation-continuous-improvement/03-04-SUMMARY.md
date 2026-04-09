---
phase: 03-paper-trading-evaluation-continuous-improvement
plan: 04
subsystem: scoring/recalibration, contracts/mapping_policy, cli/brief
tags: [recalibration, threshold-tuning, position-sizing, calibration]
dependency_graph:
  requires: [03-03]
  provides: [recalibrate_probability, update_thresholds_from_history, suggested_size]
  affects: [cli/brief.py, scoring/ledger.py, contracts/mapping_policy.py]
tech_stack:
  added: []
  patterns: [bucket-based-recalibration, per-class-threshold-tuning, advisory-sizing]
key_files:
  created:
    - backend/src/parallax/scoring/recalibration.py
    - backend/tests/test_recalibration.py
  modified:
    - backend/src/parallax/scoring/calibration.py
    - backend/src/parallax/scoring/ledger.py
    - backend/src/parallax/db/schema.py
    - backend/src/parallax/contracts/mapping_policy.py
    - backend/src/parallax/cli/brief.py
decisions:
  - Placed raw_probability after model_probability in schema for logical grouping
  - suggested_size computed automatically on actionable signals (BUY_YES/BUY_NO only)
  - Threshold auto-tuning only raises thresholds, never lowers below initial 5% floor
metrics:
  duration: 9 minutes
  completed: 2026-04-09
  tasks_completed: 2
  tasks_total: 2
  files_created: 2
  files_modified: 5
---

# Phase 3 Plan 4: Mechanical Recalibration and Threshold Tuning Summary

Bucket-based probability recalibration with 10-signal gate and 0.15 cap, dynamic per-class edge threshold tuning from win history, and advisory position sizing on signals.

## Completed Tasks

| # | Task | Commit | Key Changes |
|---|------|--------|-------------|
| 1 | Recalibration module + calibration_curve model_id filter + raw_probability column | 9a1775f | New recalibration.py, calibration.py model_id param, raw_probability/suggested_size in schema and ledger |
| 2 | MappingPolicy threshold auto-tuning + suggested_size + brief.py wiring | 74b1d3f | update_thresholds_from_history, _compute_suggested_size, recalibration wired into brief pipeline |

## Implementation Details

### Recalibration Module (recalibration.py)

`recalibrate_probability(raw_prob, model_id, conn)` applies bucket-based correction:
1. Counts resolved signals for model_id -- requires 10+ to activate
2. Calls `calibration_curve(conn, model_id=model_id)` for per-model buckets
3. Finds matching bucket (5 ranges: 0-20%, 20-40%, 40-60%, 60-80%, 80-100%)
4. Computes offset = avg_predicted - actual_rate (positive = overestimating)
5. Caps offset at +/-0.15 to prevent oscillation
6. Returns (calibrated, raw) tuple

### Calibration Curve Model Filter

`calibration_curve(conn, model_id=None)` now accepts optional model_id parameter. When provided, adds `AND model_id = ?` to WHERE clause. Without model_id, returns global curve (backward compatible).

### MappingPolicy Threshold Auto-Tuning

`update_thresholds_from_history(conn)` queries signal_ledger for proxy classes where small edges (<8%) have win_rate < 0.4. Raises min_edge to 8% for those classes. Thresholds only go up (T-03-12 mitigation), never below the initial 5% floor.

### Suggested Size Advisory

`_compute_suggested_size(model_id, proxy_class)` returns "full" when 5+ resolved signals exist with win_rate > 0.5 for the model+proxy combo, "half" otherwise. Displayed as [HALF]/[FULL] in signal audit.

### Pipeline Wiring (brief.py)

Before mapping: recalibrate all predictions, store raw_probability. Before evaluate(): call update_thresholds_from_history(). In record_signal(): pass raw_probability. In format: show size tag.

## Deviations from Plan

None -- plan executed exactly as written.

## Verification

- 261 tests pass (all existing + 8 new recalibration tests)
- `--dry-run` completes successfully with recalibration gracefully skipped (no data)
- Acceptance criteria grep checks all pass

## Self-Check: PASSED
