# Parallax Health Check — 2026-05-13

**Status: YELLOW**

No code changes since the 2026-05-12 health check commit — all four HIGH issues are now one day older. The streak of consecutive YELLOW days is now **12** days.

---

## Test Results

- **27 failed, 302 passed** — identical failure set to 2026-05-02 through 2026-05-12 (12 consecutive days)
- Env note: `fastapi` and `truthbrush` not installed in test runner → `test_dashboard_endpoints.py` and `test_truth_social.py` excluded from collection
- Python: 3.11.15 (system); pytest 8.4.2, pytest-asyncio 0.26.0, pytest-httpx 0.35.0
- DuckDB: 1.5.2 installed

| Failure Cluster | Count | Root Cause |
|---|---|---|
| `test_scorecard.py` | 9 | Missing `pytz` — DuckDB `TIMESTAMPTZ` queries crash |
| `test_mapping_policy.py` | 11 | Stale assertions expect old proxy-discount model |
| `test_recalibration.py` | 4 | Predicate mismatch between count gate and calibration view |
| `test_ops_events.py` | 1 | Missing `pytz` |
| `test_llm_usage.py` | 1 | Missing `pytz` |
| `test_google_news.py` | 1 | Hardcoded April 8 pubDates now 35 days old |

---

## Issues Found

### HIGH (31 days) — `crisis_context.py` Stale

- **Open since**: 2026-04-13 (31 days unactioned)

### HIGH (15 days) — Deprecated Claude Model ID

- **Open since**: 2026-04-28 (15 days unactioned)

### HIGH (28+ days) — `pytz` Missing

- **Open since**: ~2026-04-15 (28+ days unactioned)

### HIGH (5 days) — `test_google_news.py` Permanently Broken

- **Open since**: 2026-05-08 (5 days)

### MEDIUM (PERSISTENT) — `test_mapping_policy.py` Stale Assertions (11 failures)

### MEDIUM (PERSISTENT) — Calibration Predicate Mismatch (4 failures)

## Status

All four HIGH issues remain unactioned after 12 consecutive YELLOW days. No changes to recommend beyond those in the 2026-05-11 report. The codebase is stable but stale.
