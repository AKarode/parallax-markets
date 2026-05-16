# Parallax Health Check — 2026-05-15

**Status: YELLOW**

No code changes since the 2026-05-14 health check. The four open issues from yesterday persist. The streak of consecutive YELLOW days is now **14** days.

---

## Test Results

- **Status**: No test run available — local test runner blocked by `pip install -e .` failure (`Cannot uninstall cryptography 41.0.7, RECORD file not found`)
- **Last known baseline** (2026-05-14 commit `a5cd92c`): 429 passed, 13 skipped, 0 failed

---

## Issues Found

### HIGH (17 days) — Deprecated Claude Model ID

`ensemble_predict(model="claude-opus-4-20250514")` in `oil_price.py`, `ceasefire.py`, `hormuz.py`.

- **Open since**: 2026-04-28 (17 days unactioned)

### HIGH (30+ days) — `pytz` Missing from `pyproject.toml`

- **Open since**: ~2026-04-15 (30+ days unactioned)

### MEDIUM — Within-Batch Duplicate Bug in `crisis_ingester.py`

Within-batch duplicates bypass dedup; `existing_hashes` not updated after insert.

### MEDIUM — Missing Migration for `crisis_events.headline_hash`

Upgrade path from pre-`headline_hash` schemas will break at runtime.

### MEDIUM — Staleness Penalty Not Applied to `probability`

At 32+ days stale, confidence is zeroed but probability still drives signals at full strength.

### MEDIUM — Calibration Predicate Mismatch

`recalibrate_probability()` count gate diverges from `calibration_curve()` view predicate.

---

## Status

All issues carry forward from 2026-05-14. No new issues identified. No new code to review. The two HIGH bugs have been open for 17 and 30 days with simple one-line/five-line fixes available.

## Recommendations

Same as 2026-05-14. No changes to priority order.
