# Parallax Health Check — 2026-05-11

**Status: YELLOW**

Test results unchanged at **27 failed, 302 passed** (302/329 = 91.8% in this env; prior full-venv baseline was 340/367 = 92.6%) — zero code changes since the 2026-05-10 health-check commit. All four HIGH issues have aged one more day: `pytz` missing (26+ days), deprecated model ID (13 days), stale crisis context (29 days), broken `test_google_news.py` fixture (3 days). The streak of consecutive YELLOW days is now **10** days.

---

## Test Results

- **27 failed, 302 passed** — identical failure set to 2026-05-02 through 2026-05-10 (10 consecutive days)
- Env note: `fastapi` and `truthbrush` not installed in test runner → `test_dashboard_endpoints.py` and `test_truth_social.py` excluded from collection (both pass in full venv; excluded here only due to missing deps)
- Python: 3.11.15 (system); pytest 8.4.2, pytest-asyncio 0.26.0, pytest-httpx 0.35.0
- DuckDB: 1.5.2 installed; `pyproject.toml` requires `>=1.2`

| Failure Cluster | Count | Root Cause |
|---|---|---|
| `test_scorecard.py` | 9 | Missing `pytz` — DuckDB `TIMESTAMPTZ` queries crash |
| `test_mapping_policy.py` | 11 | Stale assertions expect old proxy-discount model, not cost-aware fair-value model |
| `test_recalibration.py` | 4 | Count gate (`model_was_correct IS NOT NULL`) diverges from calibration view (`resolution_price IS NOT NULL`) |
| `test_ops_events.py` | 1 | Missing `pytz` — `TIMESTAMPTZ` column query crashes |
| `test_llm_usage.py` | 1 | Missing `pytz` — `TIMESTAMPTZ` column query crashes |
| `test_google_news.py` | 1 | Hardcoded April 8 pubDates now 33 days old; 30-day filter returns `[]` |

---

## Issues Found

### HIGH (ESCALATING, 29 days) — `crisis_context.py` Stale; Validation Window Expired

All model reasoning about the ceasefire status, Hormuz conditions, and current Brent pricing is conditioned on fundamentally incorrect market state (last updated 2026-04-12).

- **Severity**: HIGH — all live prediction outputs conditioned on 29-day-stale context
- **Fix**: Update with events from April 12–May 11; revise "Current Market State" section
- **Open since**: 2026-04-13 (29 days unactioned)

### HIGH (13 days) — Deprecated Claude Model ID Blocks Live Prediction Runs

`oil_price.py`, `ceasefire.py`, and `hormuz.py` all call `ensemble_predict()` with `model="claude-opus-4-20250514"`. This is not a valid Anthropic model ID.

- **Severity**: HIGH — silent production blocker; no test validates the model ID string
- **Fix**: Replace `"claude-opus-4-20250514"` with `"claude-opus-4-7"` in all three files
- **Open since**: 2026-04-28 (13 days unactioned)

### HIGH (26+ days) — `pytz` Missing from `pyproject.toml`

DuckDB 1.5.2 raises `InvalidInputException: Required module 'pytz' failed to import` on any query returning a `TIMESTAMPTZ` column.

- **Severity**: HIGH — blocks 11 tests; breaks `--scorecard` pipeline in clean envs
- **Fix**: Add `"pytz>=2024.1"` to `[project] dependencies` in `backend/pyproject.toml`
- **Open since**: ~2026-04-15 (26+ days unactioned)

### HIGH (3 days) — `test_google_news.py` Fixture Returns Empty List

Hardcoded `pubDate` strings reference April 8, 2026 articles. As of May 11, all articles are 33 days old and the `max_age_hours=24*30` filter returns `[]`.

- **Severity**: HIGH — test permanently broken; detonated May 8
- **Fix**: Replace hardcoded `pubDate` strings with relative dates computed at test runtime
- **Open since**: 2026-05-08 (3 days)

### MEDIUM (PERSISTENT) — `test_mapping_policy.py` Stale Assertions (11 failures)

`MappingPolicy.evaluate()` was refactored but test assertions were never updated.

### MEDIUM (PERSISTENT) — Calibration Predicate Mismatch (4 failures)

`recalibrate_probability()` count gate uses `model_was_correct IS NOT NULL` but calibration view requires `resolution_price IS NOT NULL`.

## Recommendations (Priority Order)

1. Fix `test_google_news.py` fixture — replace hardcoded `pubDate` strings with relative dates
2. Update Claude model ID — replace `"claude-opus-4-20250514"` with `"claude-opus-4-7"`
3. Add `pytz>=2024.1` to `pyproject.toml`
4. Update `crisis_context.py` with events from April 12–May 11
5. Fix `test_mapping_policy.py` stale assertions
6. Align `recalibrate_probability()` predicate
