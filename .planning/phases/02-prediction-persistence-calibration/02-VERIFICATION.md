---
phase: 02-prediction-persistence-calibration
verified: 2026-04-08T22:00:00Z
status: passed
score: 11/11 must-haves verified
overrides_applied: 0
---

# Phase 2: Prediction Persistence + Calibration Verification Report

**Phase Goal:** Every prediction the system makes is persisted with full context, enabling calibration analysis and model improvement.
**Verified:** 2026-04-08T22:00:00Z
**Status:** passed
**Re-verification:** No -- initial verification

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | Every prediction run persists all 3 predictions with shared run_id | VERIFIED | `brief.py:200` generates `run_id = str(uuid.uuid4())`, `brief.py:255` calls `pred_logger.log_prediction(run_id, pred, ...)` inside loop over all predictions |
| 2 | prediction_log stores probability, reasoning, evidence, news_context, cascade_inputs, timeframe | VERIFIED | `prediction_log.py:46-52` log_prediction() accepts all fields; `schema.py:196-210` DDL has all columns; JSON round-trip via json.dumps/json.loads |
| 3 | Signal ledger entries include run_id for traceability to the prediction run | VERIFIED | `ledger.py:68` record_signal() has `run_id` param; `brief.py:273` passes `run_id=run_id`; `schema.py:215` signal_ledger has `run_id VARCHAR` column |
| 4 | Resolution checker detects settled Kalshi contracts and backfills signal_ledger | VERIFIED | `resolution.py:20-63` _check_market_resolution() checks status in ("determined","finalized"); `resolution.py:66-143` _backfill_signal() UPDATEs resolution columns |
| 5 | Resolved signals have resolution_price, resolved_at, realized_pnl, model_was_correct populated | VERIFIED | `resolution.py:108-129` UPDATE SET with CASE WHEN for P&L (BUY_YES/BUY_NO logic) and model_was_correct |
| 6 | CLI --check-resolutions flag triggers resolution polling | VERIFIED | `brief.py:589-591` argparse flag; `brief.py:604-606` dispatches to `_run_check_resolutions()`; `brief.py:317-343` handler uses production Kalshi URL |
| 7 | Hit rate by proxy class query returns accuracy grouped by DIRECT/NEAR_PROXY/LOOSE_PROXY | VERIFIED | `calibration.py:21-47` hit_rate_by_proxy_class() with GROUP BY proxy_class, returns list[dict] |
| 8 | Calibration curve buckets predictions into 5 probability ranges and compares predicted vs actual | VERIFIED | `calibration.py:50-84` calibration_curve() with 5 CASE WHEN buckets (0-20%, 20-40%, etc.) |
| 9 | Edge decay analysis shows realized P&L and hit rate by edge size bucket | VERIFIED | `calibration.py:87-122` edge_decay() with 4 edge buckets, returns avg_edge, avg_pnl, hit_rate |
| 10 | Calibration report refuses to run with fewer than 7 days of prediction data | VERIFIED | `calibration.py:125-146` _check_minimum_data() with `min_days: int = 7`, returns insufficient message |
| 11 | CLI --calibration flag prints formatted text report | VERIFIED | `brief.py:594-596` argparse flag; `brief.py:608-609` dispatches to `_run_calibration()`; `brief.py:346-355` handler calls calibration_report() |

**Score:** 11/11 truths verified

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `backend/src/parallax/scoring/prediction_log.py` | PredictionLogEntry + PredictionLogger | VERIFIED | 166 lines, PredictionLogEntry(BaseModel), PredictionLogger with log_prediction()/get_predictions(), JSON round-trip |
| `backend/src/parallax/scoring/resolution.py` | check_resolutions() + Kalshi settlement polling | VERIFIED | 206 lines, _check_market_resolution(), _backfill_signal(), check_resolutions() with per-ticker error handling |
| `backend/src/parallax/scoring/calibration.py` | 3 calibration queries + text report + 7-day guard | VERIFIED | 205 lines, 4 exported functions, formatted report with 3 sections |
| `backend/src/parallax/db/schema.py` | prediction_log table DDL + run_id in signal_ledger | VERIFIED | prediction_log table at lines 196-210, signal_ledger has run_id at line 215 |
| `backend/src/parallax/scoring/ledger.py` | run_id in SignalRecord + record_signal() | VERIFIED | run_id field in SignalRecord, run_id param in record_signal(), included in INSERT |
| `backend/src/parallax/cli/brief.py` | Pipeline wiring + CLI flags | VERIFIED | run_id generation, PredictionLogger wiring, --check-resolutions and --calibration handlers |
| `backend/tests/test_prediction_log.py` | Prediction persistence tests | VERIFIED | Tests exist and pass |
| `backend/tests/test_resolution.py` | Resolution checker tests | VERIFIED | Tests exist and pass |
| `backend/tests/test_calibration.py` | Calibration query tests | VERIFIED | Tests exist and pass |

### Key Link Verification

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| brief.py | prediction_log.py | PredictionLogger.log_prediction() | WIRED | Line 255: `pred_logger.log_prediction(run_id, pred, news_ctx, cascade_ctx)` |
| prediction_log.py | schema.py | INSERT INTO prediction_log | WIRED | Line 82: parameterized INSERT with all 12 columns |
| brief.py | ledger.py | record_signal(run_id=run_id) | WIRED | Line 273: `run_id=run_id` passed through |
| resolution.py | kalshi.py | _request('GET', '/markets/{ticker}') | WIRED | Line 32: `await client._request("GET", f"/markets/{ticker}")` |
| resolution.py | schema.py | UPDATE signal_ledger | WIRED | Line 108: parameterized UPDATE with resolution columns |
| calibration.py | schema.py | SELECT from signal_ledger and prediction_log | WIRED | Lines 33, 70, 107 query signal_ledger; line 134 queries prediction_log |
| brief.py | calibration.py | --calibration -> calibration_report() | WIRED | Line 348: import, line 353: call calibration_report(conn) |
| brief.py | resolution.py | --check-resolutions -> check_resolutions() | WIRED | Line 319: import, line 334: call check_resolutions(conn, client) |

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| All phase 2 tests pass | pytest tests/test_prediction_log.py test_resolution.py test_calibration.py test_brief.py test_schema.py -x -q | 46 passed | PASS |
| Full test suite (no regressions) | pytest tests/ -x -q | 192 passed | PASS |
| prediction_log module imports | python -c "from parallax.scoring.prediction_log import PredictionLogEntry, PredictionLogger" | OK | PASS |
| resolution module imports | python -c "from parallax.scoring.resolution import check_resolutions" | OK | PASS |
| calibration module imports | python -c "from parallax.scoring.calibration import hit_rate_by_proxy_class, calibration_curve, edge_decay, calibration_report" | OK | PASS |

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|------------|-------------|--------|----------|
| PERS-01 | 02-01 | Every PredictionOutput persisted in DuckDB with timestamp and run_id | SATISFIED | prediction_log table + PredictionLogger wired into brief.py pipeline |
| PERS-02 | 02-02 | Resolution checker polls Kalshi APIs for settled contracts, backfills signal_ledger | SATISFIED | resolution.py with check_resolutions(), _backfill_signal(), --check-resolutions CLI |
| PERS-03 | 02-03 | Calibration queries: hit rate by proxy class, calibration curve, edge decay | SATISFIED | calibration.py with 3 SQL query functions returning list[dict] |
| PERS-04 | 02-03 | At least 7 days of prediction data before calibration is valid | SATISFIED | _check_minimum_data(min_days=7) guards calibration_report() |

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| None found | - | - | - | - |

No TODOs, FIXMEs, placeholders, or stub implementations detected in phase 2 files.

### Human Verification Required

None. All phase 2 functionality is testable programmatically and verified via automated tests.

### Gaps Summary

No gaps found. All 11 observable truths verified, all 9 artifacts substantive and wired, all 8 key links confirmed, all 4 requirements satisfied, 192 tests passing with no regressions.

---

_Verified: 2026-04-08T22:00:00Z_
_Verifier: Claude (gsd-verifier)_
