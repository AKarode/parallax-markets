---
phase: 10-prompt-fixes-dependency-cleanup
plan: 01
subsystem: prediction
tags: [llm-prompts, anchoring-bias, crisis-context]

requires: []
provides:
  - "Independent prediction model prompts without market price anchoring"
  - "Clean crisis context with factual events only"
affects: [prediction, backtest]

tech-stack:
  added: []
  patterns: ["crisis context contains only dated facts and resolution criteria"]

key-files:
  created:
    - backend/tests/test_crisis_context.py
  modified:
    - backend/src/parallax/prediction/crisis_context.py
    - backend/src/parallax/prediction/oil_price.py
    - backend/src/parallax/prediction/ceasefire.py
    - backend/src/parallax/prediction/hormuz.py
    - backend/src/parallax/cli/brief.py
    - backend/src/parallax/backtest/engine.py

key-decisions:
  - "Removed Brent current price from crisis context — oil predictor gets it via EIA price_data param"
  - "Kept historical price markers in dated timeline entries per D-03"

patterns-established:
  - "No market prices in prediction prompts: models must produce independent estimates"
  - "Crisis context = dated facts + contract resolution criteria only"

requirements-completed: [PROMPT-01, PROMPT-05]

duration: 8min
completed: 2026-04-12
---

# Plan 10-01: Anchoring Removal + Crisis Context Cleanup Summary

**Stripped editorial sections from crisis context and removed market_prices parameter from all 3 prediction models so Claude produces independent probability estimates**

## Performance

- **Duration:** 8 min
- **Tasks:** 2
- **Files modified:** 7

## Accomplishments
- Removed "What The Market May Be Missing" section, "Key risks/opportunities" bullets, current market percentages, wagered amounts, and Brent price line from crisis_context.py
- Removed market_prices parameter from predict() signatures in oil_price.py, ceasefire.py, hormuz.py
- Deleted _format_market_prices() static methods from all 3 predictors
- Removed market_context wiring from brief.py and backtest/engine.py
- Created 9 verification tests for crisis context cleanliness

## Task Commits

1. **Task 1: Strip editorial content from crisis_context.py** - `487349f` (fix)
2. **Task 2: Remove market_prices anchoring from predictors + callers** - `e0967cd` (fix)

## Files Created/Modified
- `backend/src/parallax/prediction/crisis_context.py` - Stripped editorial sections, kept facts + resolution criteria
- `backend/src/parallax/prediction/oil_price.py` - Removed market_prices param, prompt anchor, _format_market_prices
- `backend/src/parallax/prediction/ceasefire.py` - Same removals
- `backend/src/parallax/prediction/hormuz.py` - Same removals
- `backend/src/parallax/cli/brief.py` - Removed market_context construction and kwargs
- `backend/src/parallax/backtest/engine.py` - Removed market_context construction, _format_market_context function, and kwargs
- `backend/tests/test_crisis_context.py` - 9 tests verifying no editorial content

## Decisions Made
- Removed Brent current price line from crisis context since oil_price predictor already receives EIA prices via its own parameter
- Kept historical price mentions in dated timeline (e.g., "Brent broke $120") per D-03

## Deviations from Plan
None - plan executed exactly as written

## Issues Encountered
None

## Next Phase Readiness
- Models now produce independent estimates, ready for Plan 10-02 (Hormuz dual-probability, bypass_flow fix)

---
*Phase: 10-prompt-fixes-dependency-cleanup*
*Completed: 2026-04-12*
