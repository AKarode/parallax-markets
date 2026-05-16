# Parallax Health Check — 2026-05-16

**Status: YELLOW**

No code changes since the 2026-05-15 health check. All four open issues persist. The streak of consecutive YELLOW days is now **15** days.

---

## Test Results

- **Status**: No test run available — local test runner blocked by `pip install -e .` failure
- **Last known baseline** (2026-05-14 commit `a5cd92c`): 429 passed, 13 skipped, 0 failed

---

## Issues Found

### HIGH (18 days) — Deprecated Claude Model ID

`ensemble_predict(model="claude-opus-4-20250514")` in `oil_price.py`, `ceasefire.py`, `hormuz.py`.

- **Open since**: 2026-04-28 (18 days unactioned)
- **Five-minute fix**: replace with `"claude-opus-4-7"`

### HIGH (31+ days) — `pytz` Missing from `pyproject.toml`

- **Open since**: ~2026-04-15 (31+ days unactioned)
- **One-minute fix**: add `"pytz>=2024.1"` to `[project] dependencies`

### MEDIUM — Within-Batch Duplicate Bug in `crisis_ingester.py`

`existing_hashes` not updated after insert; within-batch duplicates bypass dedup check.

- **Fix**: `existing_hashes.add(headline_hash)` after each successful INSERT

### MEDIUM — Missing Migration for `crisis_events.headline_hash`

Any DB created before `headline_hash` column was added will fail at runtime on upgrade.

- **Fix**: Add `_add_column_if_missing(conn, "crisis_events", "headline_hash", "TEXT")` in `_migrate_legacy_tables()`

### MEDIUM — Staleness Penalty Not Applied to `probability`

Context is 34 days stale; confidence is zeroed but `probability` still drives trade signals.

- **Fix**: In `ensemble_predict()`, scale `ensemble_result["probability"]` toward 0.5 when `penalty_factor == 0.0`, or propagate `staleness_penalty_applied` into `DivergenceDetector`

### MEDIUM — Calibration Predicate Mismatch

`recalibrate_probability()` count gate: `model_was_correct IS NOT NULL`
Calibration view: `resolution_price IS NOT NULL`

- **Fix**: Add `AND resolution_price IS NOT NULL` to count query at `scoring/recalibration.py:71`

---

## Status

No changes since 2026-05-15. The two HIGH issues (deprecated model ID, missing pytz) have been open for 18 and 31 days with simple fixes identified on day 1. Every live prediction run currently fails at the Anthropic API call. Every fresh clone cannot run `--scorecard` without manual `pip install pytz`.

## Recommendations

Same priority order as 2026-05-14. Both HIGH fixes require less than 5 minutes of engineering time and have been documented in 5 consecutive health check reports.
