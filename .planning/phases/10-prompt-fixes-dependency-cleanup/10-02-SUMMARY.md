---
phase: 10-prompt-fixes-dependency-cleanup
plan: 02
subsystem: prediction
tags: [llm-prompts, hormuz, bypass-flow, track-record, cascade]

requires:
  - phase: 10-01
    provides: "Prediction models without market_prices anchoring"
provides:
  - "Single-probability Hormuz prompt"
  - "Computed bypass_flow from cascade engine"
  - "Track record n>=10 sample size guard"
affects: [prediction, scoring]

tech-stack:
  added: []
  patterns: ["track record requires n>=10 resolved signals for statistics"]

key-files:
  created: []
  modified:
    - backend/src/parallax/prediction/hormuz.py
    - backend/src/parallax/prediction/oil_price.py
    - backend/src/parallax/scoring/track_record.py
    - backend/src/parallax/cli/brief.py
    - backend/tests/test_track_record.py
    - backend/tests/test_prediction.py

key-decisions:
  - "Hormuz model asks for single probability (partial reopening >25% flow within 14d)"
  - "WorldState cell_id=1 with flow=2M, status=blocked approximates current Hormuz conditions"
  - "Track record threshold set at 10 resolved signals — below returns informational text"

patterns-established:
  - "Track record n>=10 guard: noisy small-sample stats hidden from models"
  - "WorldState must be initialized with current conditions before predict calls"

requirements-completed: [PROMPT-02, PROMPT-03, PROMPT-04]

duration: 10min
completed: 2026-04-12
---

# Plan 10-02: Model Quality Fixes Summary

**Single-probability Hormuz prompt, computed bypass_flow via cascade engine, and track record n>=10 sample guard**

## Performance

- **Duration:** 10 min
- **Tasks:** 2
- **Files modified:** 6

## Accomplishments
- Rewrote HORMUZ_SYSTEM_PROMPT from dual-probability (a)/(b) spec to single probability (>25% flow restored within 14d)
- Added n>=10 guard to build_track_record() — returns informational message instead of noisy stats below threshold
- Fixed oil_price.py to call CascadeEngine.activate_bypass(supply_loss) for computed bypass_flow instead of hardcoded 0
- Initialized WorldState in brief.py with Hormuz blockade cell (2M bbl/day trickle flow)
- Updated all existing track record tests to work with n>=10 guard (inserted 10+ signals)
- Added 2 new small sample tests and 3 bypass_flow tests

## Task Commits

1. **Task 1: Hormuz prompt + track record guard** - `92ab4c4` (fix)
2. **Task 2: bypass_flow fix + WorldState init** - `82eeb2a` (fix)

## Files Created/Modified
- `backend/src/parallax/prediction/hormuz.py` - Single-probability prompt spec
- `backend/src/parallax/prediction/oil_price.py` - activate_bypass() call for bypass_flow
- `backend/src/parallax/scoring/track_record.py` - n>=10 guard before statistics
- `backend/src/parallax/cli/brief.py` - WorldState.update_cell() for Hormuz blockade
- `backend/tests/test_track_record.py` - Updated existing tests + 2 new small sample tests
- `backend/tests/test_prediction.py` - 3 new bypass_flow tests

## Decisions Made
- Used cell_id=1 with 2M bbl/day flow to approximate current Hormuz conditions
- Set threshold at exactly 10 (not 15 or 20) per plan specification

## Deviations from Plan
None - plan executed exactly as written

## Issues Encountered
None

## Next Phase Readiness
- All 3 model quality fixes applied, ready for phase verification

---
*Phase: 10-prompt-fixes-dependency-cleanup*
*Completed: 2026-04-12*
