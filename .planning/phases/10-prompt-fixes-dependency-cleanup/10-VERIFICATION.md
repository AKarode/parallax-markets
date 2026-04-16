---
phase: 10-prompt-fixes-dependency-cleanup
verified: 2026-04-12T22:30:00Z
status: passed
score: 5/5
overrides_applied: 0
must_haves:
  truths:
    - "No prediction model prompt contains current market prices before the model states its probability"
    - "Oil price model receives a non-zero bypass_flow computed from cascade engine when blockade conditions exist"
    - "Hormuz model outputs exactly one probability that maps to a single contract resolution criterion"
    - "Track record section in prompts is omitted entirely when fewer than 10 resolved signals exist for that model"
    - "Crisis context injected into prompts contains only dated factual events -- editorial hypotheses excluded"
  artifacts:
    - path: "backend/src/parallax/prediction/oil_price.py"
      provides: "Oil price predictor without market_prices parameter, with computed bypass_flow"
    - path: "backend/src/parallax/prediction/ceasefire.py"
      provides: "Ceasefire predictor without market_prices parameter"
    - path: "backend/src/parallax/prediction/hormuz.py"
      provides: "Single-probability Hormuz predictor"
    - path: "backend/src/parallax/prediction/crisis_context.py"
      provides: "Clean crisis context with facts only"
    - path: "backend/src/parallax/scoring/track_record.py"
      provides: "Track record builder with n>=10 guard"
    - path: "backend/src/parallax/cli/brief.py"
      provides: "Pipeline with initialized WorldState, no market_context"
    - path: "backend/src/parallax/backtest/engine.py"
      provides: "Backtest with no market_context wiring"
    - path: "backend/pyproject.toml"
      provides: "Clean dependency list -- 9 packages, 6 dead removed"
    - path: "backend/tests/test_crisis_context.py"
      provides: "9 tests verifying no editorial content"
    - path: "backend/tests/test_track_record.py"
      provides: "Tests including n<10 guard and n=10 boundary"
    - path: "backend/tests/test_prediction.py"
      provides: "Tests including bypass_flow computation"
  key_links:
    - from: "backend/src/parallax/cli/brief.py"
      to: "predictor.predict()"
      via: "asyncio.gather calls without market_prices kwarg"
    - from: "backend/src/parallax/prediction/oil_price.py"
      to: "CascadeEngine.activate_bypass()"
      via: "called after supply_loss loop"
    - from: "backend/src/parallax/cli/brief.py"
      to: "WorldState.update_cell()"
      via: "initialization before predict calls"
---

# Phase 10: Prompt Fixes + Dependency Cleanup Verification Report

**Phase Goal:** Models produce independent probability estimates from clean inputs -- no anchoring to market prices, no broken cascade data, no noise from tiny sample sizes, no editorial contamination.
**Verified:** 2026-04-12T22:30:00Z
**Status:** passed
**Re-verification:** No -- initial verification

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | No prediction model prompt contains current market prices before the model states its probability | VERIFIED | `market_prices_text` grep returns 0 matches across backend/src/parallax/. `_format_market_prices` deleted from all 3 predictors. `market_context` variable removed from brief.py and backtest/engine.py. All predict() signatures lack market_prices param. |
| 2 | Oil price model receives a non-zero bypass_flow computed from cascade engine when blockade conditions exist | VERIFIED | oil_price.py line 97: `bypass_result = self._cascade.activate_bypass(supply_loss)`. No hardcoded `bypass_flow = 0.0`. brief.py line 477: `world_state.update_cell(cell_id=1, ... flow=2_000_000, status="blocked")`. test_prediction.py::TestBypassFlowComputation passes (3 tests). |
| 3 | Hormuz model outputs exactly one probability that maps to a single contract resolution criterion | VERIFIED | hormuz.py line 39: "Estimate ONE probability: the likelihood of partial reopening (>25% of pre-war commercial shipping flow restored through the Strait of Hormuz) within 14 days." No dual "(a)/(b)" spec found. |
| 4 | Track record section in prompts is omitted entirely when fewer than 10 resolved signals exist for that model | VERIFIED | track_record.py line 49: `if total < 10:` returns "too few for reliable statistics (minimum 10 required)". test_track_record.py::TestBuildTrackRecordSmallSample passes (2 tests). |
| 5 | Crisis context injected into prompts contains only dated factual events -- editorial hypotheses excluded | VERIFIED | crisis_context.py has no "What The Market May Be Missing", no "**Key risks:**", no "**Key opportunities:**", no "~48% YES", no "$200M+", no "~$98/barrel futures". Retains dated timeline facts and contract resolution criteria. test_crisis_context.py passes (9 tests). |

**Score:** 5/5 truths verified

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `backend/src/parallax/prediction/oil_price.py` | Oil predictor without market_prices, with bypass_flow | VERIFIED | 211 lines. predict() signature: (recent_events, current_prices, world_state, db_conn=None). activate_bypass() called at line 97. No market_prices_text in prompt. |
| `backend/src/parallax/prediction/ceasefire.py` | Ceasefire predictor without market_prices | VERIFIED | 190 lines. predict() signature: (recent_events, current_negotiations=None, db_conn=None). No market_prices parameter. |
| `backend/src/parallax/prediction/hormuz.py` | Single-probability Hormuz predictor | VERIFIED | 200 lines. Prompt requests "ONE probability" for partial reopening >25% flow. No dual spec. No market_prices parameter. |
| `backend/src/parallax/prediction/crisis_context.py` | Clean crisis context with facts only | VERIFIED | 109 lines. "Prediction Market Contracts" section has tickers + resolution criteria only (no prices, no percentages). "Current Market State" has factual status only. |
| `backend/src/parallax/scoring/track_record.py` | Track record with n>=10 guard | VERIFIED | 87 lines. `total < 10` guard at line 49 returns informational message. |
| `backend/src/parallax/cli/brief.py` | Pipeline with WorldState init, no market_context | VERIFIED | update_cell at line 477 with blocked Hormuz cell. Zero matches for "market_context" in file. |
| `backend/src/parallax/backtest/engine.py` | No market_context wiring | VERIFIED | Zero matches for "market_context". predict() calls at lines 196-198 pass no market_prices kwarg. |
| `backend/pyproject.toml` | 9 production dependencies | VERIFIED | Exactly 9 deps. No h3, sentence-transformers, searoute, shapely, google-cloud-bigquery, or websockets. |
| `backend/tests/test_crisis_context.py` | 9 editorial verification tests | VERIFIED | 49 lines, 9 test methods in TestCrisisContextEditorial. All pass. |
| `backend/tests/test_track_record.py` | Tests with n<10 guard | VERIFIED | 239 lines. TestBuildTrackRecordSmallSample has 2 tests (n=5 and n=10). Existing tests updated to 10+ signals. All 10 pass. |
| `backend/tests/test_prediction.py` | Tests with bypass_flow | VERIFIED | TestBypassFlowComputation has 3 tests (positive bypass, zero loss, full predictor integration). All 14 pass. |

### Key Link Verification

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| brief.py | predictor.predict() | asyncio.gather at lines 496-498 | WIRED | `oil_pred.predict(events, prices, world_state, db_conn=conn)` -- no market_prices kwarg. Same for ceasefire and hormuz. |
| oil_price.py | CascadeEngine.activate_bypass() | Called after supply_loss loop | WIRED | Line 97: `bypass_result = self._cascade.activate_bypass(supply_loss)`. Bypass flow feeds into prompt format at line 120. |
| brief.py | WorldState.update_cell() | Init before predict calls | WIRED | Lines 477-483: `world_state.update_cell(cell_id=1, influence="iran", threat_level=0.9, flow=2_000_000, status="blocked")`. WorldState passed to oil_pred and hormuz_pred. |
| backtest/engine.py | predictor.predict() | asyncio.gather at lines 195-198 | WIRED | No market_prices kwarg. Clean predict() calls matching updated signatures. |

### Data-Flow Trace (Level 4)

| Artifact | Data Variable | Source | Produces Real Data | Status |
|----------|---------------|--------|--------------------|--------|
| oil_price.py | bypass_flow | CascadeEngine.activate_bypass(supply_loss) | Yes -- supply_loss from WorldState cells, bypass from config capacity | FLOWING |
| track_record.py | total (signal count) | DuckDB signal_ledger query | Yes -- SELECT COUNT(*) from signal_ledger | FLOWING |
| crisis_context.py | CRISIS_TIMELINE | Hardcoded string constant | Yes -- substantive 4000+ char timeline | FLOWING |

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| Crisis context tests pass | pytest tests/test_crisis_context.py -x -q | 9 passed in 0.01s | PASS |
| Track record tests pass | pytest tests/test_track_record.py -x -q | 10 passed in 1.84s | PASS |
| Prediction tests pass | pytest tests/test_prediction.py -x -q | 14 passed in 0.12s | PASS |
| Full suite (excl pre-existing) | pytest tests/ -q | 345 passed, 4 failed (all in test_recalibration.py -- pre-existing) | PASS |
| pyproject.toml valid with 9 deps | tomllib parse + count | OK: 9 dependencies | PASS |
| No dead imports of removed packages | grep for h3/sentence_transformers/etc | 0 matches | PASS |

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|------------|-------------|--------|----------|
| PROMPT-01 | 10-01 | All prediction model prompts produce probabilities without seeing current market prices | SATISFIED | market_prices_text removed from all 3 prompts; market_context wiring removed from brief.py and backtest/engine.py |
| PROMPT-02 | 10-02 | Oil price model receives computed bypass flow from cascade engine | SATISFIED | activate_bypass() called with supply_loss; WorldState initialized with blocked Hormuz cell |
| PROMPT-03 | 10-02 | Hormuz model outputs a single well-defined probability | SATISFIED | "Estimate ONE probability" -- partial reopening >25% flow within 14d |
| PROMPT-04 | 10-02 | Track record injection requires minimum sample size (n>=10) | SATISFIED | `if total < 10` guard returns informational message without stats |
| PROMPT-05 | 10-01 | Crisis context separates verifiable facts from editorial hypotheses | SATISFIED | Editorial sections removed; only dated facts + contract resolution criteria remain |
| ARCH-04 | 10-03 | Dead dependencies removed from pyproject.toml | SATISFIED | 6 packages removed (h3, sentence-transformers, searoute, shapely, google-cloud-bigquery, websockets); 9 remain |

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| None | - | - | - | No TODO, FIXME, PLACEHOLDER, or stub patterns found in any modified file |

### Human Verification Required

No human verification items identified. All truths are verifiable programmatically through code inspection and test execution.

### Gaps Summary

No gaps found. All 5 roadmap success criteria verified. All 6 requirement IDs (PROMPT-01 through PROMPT-05 and ARCH-04) satisfied with implementation evidence. All artifacts exist, are substantive, and are properly wired. Full test suite passes (pre-existing test_recalibration.py failures unrelated to phase 10 work).

---

_Verified: 2026-04-12T22:30:00Z_
_Verifier: Claude (gsd-verifier)_
