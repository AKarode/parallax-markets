# Parallax Health Check — 2026-05-14

**Status: YELLOW**

Four production commits landed since 2026-05-13 (staleness penalty wiring, batch hash dedup, schema
tightening, test fixture fixes). Test suite improved — two previously-failing clusters are now passing
or skipped — but the two longest-running HIGH issues (deprecated model ID, missing `pytz`) remain
unactioned for 16 and 29 days respectively.

---

## Changes Since Last Report

Four commits since `9ff425a` (2026-05-13 health check):

| Hash | Description |
|---|---|
| `a5cd92c` | fix: fallback prediction defects + test health — backtest harness, crisis ingester, staleness penalty |
| `53f93b1` | feat: wire staleness penalty end-to-end through brief pipeline |
| `69c5c56` | fix: batch crisis_ingester hash check, extend fuzzy dedup to 21d, schema tighten |
| `3adcf3c` | fix: update test fixtures for headline_hash column |

---

## Test Results

- **Baseline from commit `a5cd92c`**: 429 passed, 13 skipped, 0 failed (per commit message)
- Local test runner blocked: `pip install -e .` fails with `Cannot uninstall cryptography 41.0.7` (Debian system package conflict)

**Resolved since 2026-05-13:**

| Failure Cluster | Fix Applied |
|---|---|
| `test_mapping_policy.py` (11 failures) | Assertions updated to match new `confidence_discount` model |
| `test_recalibration.py` (4 failures) | Test fixtures now default `resolution_price=1.0` |
| `test_google_news.py` (1 failure) | `max_age_hours` expanded to `24 * 365` (workaround) |
| `backtest/__init__.py` import error | Module now exists with correct exports |

---

## Issues Found

### HIGH (16 days) — Deprecated Claude Model ID Blocks Live Prediction Runs

`oil_price.py:143`, `ceasefire.py:116`, and `hormuz.py:118` all call `ensemble_predict()` with `model="claude-opus-4-20250514"`. Not a valid Anthropic model ID.

- **Fix**: Replace `"claude-opus-4-20250514"` with `"claude-opus-4-7"` in 3 files
- **Open since**: 2026-04-28 (16 days unactioned)

### HIGH (29+ days) — `pytz` Missing from `pyproject.toml`

Not added to `[project] dependencies` despite pip install in one commit. Breaks clean installs.

- **Fix**: Add `"pytz>=2024.1"` to `[project] dependencies` in `backend/pyproject.toml`
- **Open since**: ~2026-04-15 (29+ days unactioned)

### MEDIUM (NEW) — `crisis_ingester.py` Within-Batch Duplicate Bug

`existing_hashes` fetched once before insert loop; within-batch duplicates bypass dedup.

- **Fix**: Add `existing_hashes.add(headline_hash)` after each successful INSERT
- **Introduced**: commit `69c5c56`

### MEDIUM (NEW) — Missing Migration for `crisis_events.headline_hash`

No `_add_column_if_missing` call for `headline_hash` in `_migrate_legacy_tables()`. Breaks upgrades.

- **Fix**: Add migration guard in `schema.py`
- **Introduced**: commit `69c5c56`

### MEDIUM (PERSISTENT) — Staleness Penalty Does Not Penalize `probability`

Confidence is zeroed at 32 days stale but `probability` still drives trade signals at full strength.

### MEDIUM (PERSISTENT) — Calibration Predicate Mismatch

Count gate uses `model_was_correct IS NOT NULL`; calibration view requires `resolution_price IS NOT NULL`.

## Recommendations (Priority Order)

1. **[5 min] Fix model ID** — replace `"claude-opus-4-20250514"` with `"claude-opus-4-7"`
2. **[1 min] Add `pytz`** — append `"pytz>=2024.1"` to `pyproject.toml`
3. **[15 min] Add `crisis_events.headline_hash` migration**
4. **[15 min] Fix within-batch duplicate bug** in `crisis_ingester.py`
5. **[30 min] Apply staleness penalty to `probability`** in `ensemble_predict()`
6. **[30 min] Align `recalibrate_probability()` predicate**
