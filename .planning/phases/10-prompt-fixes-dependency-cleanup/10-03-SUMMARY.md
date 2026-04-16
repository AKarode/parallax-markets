---
phase: 10-prompt-fixes-dependency-cleanup
plan: 03
subsystem: build-config
tags: [dependencies, cleanup, supply-chain]
dependency_graph:
  requires: []
  provides: [clean-dependency-list]
  affects: [backend/pyproject.toml]
tech_stack:
  added: []
  patterns: []
key_files:
  created: []
  modified:
    - backend/pyproject.toml
decisions:
  - Removed 6 dead dependencies confirmed by zero-import grep across backend/src/parallax/
metrics:
  duration: 3m
  completed: "2026-04-12"
  tasks_completed: 1
  tasks_total: 1
  files_changed: 1
requirements_completed:
  - ARCH-04
---

# Phase 10 Plan 03: Dead Dependency Cleanup Summary

Removed 6 unused Python packages from pyproject.toml that had zero imports in backend/src/parallax/, reducing production dependencies from 15 to 9 and eliminating heavy transitive pulls (sentence-transformers drags in PyTorch).

## Changes Made

### Task 1: Remove 6 dead dependencies from pyproject.toml

**Commit:** `11a620f`

Removed the following 6 packages from `dependencies` in `backend/pyproject.toml`:

| Package | Reason Dead | Impact of Removal |
|---------|------------|-------------------|
| `h3>=4.1` | H3 hex grid -- now frontend-only (h3-js) | Removes C extension build |
| `sentence-transformers>=3.4` | Embeddings -- never used in pipeline | Removes PyTorch (~2GB) |
| `searoute>=1.3` | Sea route calc -- replaced by static config | Removes geospatial dep |
| `shapely>=2.0` | Geometry ops -- no current importers | Removes GEOS library |
| `google-cloud-bigquery>=3.27` | BigQuery -- replaced by DuckDB | Removes GCP SDK |
| `websockets>=14.0` | WebSocket -- uvicorn has built-in support | Removes redundant dep |

**Remaining 9 dependencies:**
1. fastapi>=0.115
2. uvicorn[standard]>=0.34
3. duckdb>=1.2
4. anthropic>=0.52
5. pydantic>=2.10
6. pyyaml>=6.0
7. httpx>=0.28
8. cryptography>=44.0
9. truthbrush>=0.2

## Verification

- `grep -r` for all 6 removed packages across `backend/src/parallax/` returned zero matches
- `tomllib` parse confirms valid TOML with exactly 9 dependencies
- Test suite: 331 passed, 4 failed (all in `test_recalibration.py` -- pre-existing failures confirmed on base commit without this change)

## Deviations from Plan

None -- plan executed exactly as written.

## Known Stubs

None.

## Pre-existing Issues Observed

- 4 test failures in `tests/test_recalibration.py` exist on the base commit (c200744) and are unrelated to dependency changes. These appear to be a recalibration logic bug, not caused by this plan.

## Commits

| Task | Commit | Message |
|------|--------|---------|
| 1 | `11a620f` | chore(10-03): remove 6 dead dependencies from pyproject.toml |

## Self-Check: PASSED

- backend/pyproject.toml: FOUND
- 10-03-SUMMARY.md: FOUND
- Commit 11a620f: FOUND
