# Parallax Health Check — 2026-05-12

**Status: YELLOW**

No code changes since the 2026-05-11 health check commit — all four HIGH issues are now one day older. The streak of consecutive YELLOW days is now **11** days.

---

## Test Results

- **27 failed, 302 passed** — identical failure set to 2026-05-02 through 2026-05-11 (11 consecutive days)
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
| `test_google_news.py` | 1 | Hardcoded April 8 pubDates now 34 days old |

---

## Issues Found

### HIGH (30 days) — `crisis_context.py` Stale

- **Open since**: 2026-04-13 (30 days unactioned)
- Every live prediction run injects a stale crisis context describing conditions from April 12

### HIGH (14 days) — Deprecated Claude Model ID

- **Open since**: 2026-04-28 (14 days unactioned)
- `ensemble_predict(model="claude-opus-4-20250514")` — invalid Anthropic model ID

### HIGH (27+ days) — `pytz` Missing

- **Open since**: ~2026-04-15 (27+ days unactioned)
- Blocks 11 tests and `--scorecard` CLI in clean environments

### HIGH (4 days) — `test_google_news.py` Permanently Broken

- **Open since**: 2026-05-08 (4 days)
- Hardcoded April 8 pubDates; `max_age_hours` filter returns `[]`

### MEDIUM (PERSISTENT) — `test_mapping_policy.py` Stale Assertions (11 failures)

### MEDIUM (PERSISTENT) — Calibration Predicate Mismatch (4 failures)

## Recommendations

Same as 2026-05-11 report. All four HIGH issues remain unactioned after 11 consecutive YELLOW days. The daily brief pipeline is producing zero valid predictions in any clean environment.
