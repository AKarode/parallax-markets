# Parallax Health Check — 2026-05-14

**Status: YELLOW**

Four production commits landed since 2026-05-13 (staleness penalty wiring, batch hash dedup, schema
tightening, test fixture fixes). Test suite improved — two previously-failing clusters are now passing
or skipped — but the two longest-running HIGH issues (deprecated model ID, missing `pytz`) remain
unactioned for 16 and 29 days respectively. Two new MEDIUM bugs were introduced by the batch
dedup optimization.

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
- Subsequent commits (`53f93b1`, `69c5c56`, `3adcf3c`) added ~50 more tests; no failures reported
- Local test runner still blocked: `pip install -e .` fails with `Cannot uninstall cryptography 41.0.7,
  RECORD file not found` (Debian system package conflict); tests cannot be collected in this env

**Resolved since 2026-05-13:**

| Failure Cluster | Fix Applied |
|---|---|
| `test_mapping_policy.py` (11 failures) | Assertions updated to match new `confidence_discount` model |
| `test_recalibration.py` (4 failures) | Test fixtures now default `resolution_price=1.0` |
| `test_google_news.py` (1 failure) | `max_age_hours` expanded to `24 * 365` (workaround, not ideal) |
| `backtest/__init__.py` import error | Module now exists with correct exports |

---

## Issues Found

### HIGH (ESCALATING — 16 days) — Deprecated Claude Model ID Blocks Live Prediction Runs

`oil_price.py:143`, `ceasefire.py:116`, and `hormuz.py:118` all call `ensemble_predict()` with
`model="claude-opus-4-20250514"`. This is not a valid Anthropic model ID. Valid current IDs:
`claude-opus-4-7`, `claude-sonnet-4-6`, `claude-haiku-4-5-20251001`. Every live prediction call is
rejected by the Anthropic API.

The ensemble.py docstring at line 89 also still references the invalid model string.

- **Severity**: HIGH — production blocker; all live runs fail at the API call
- **Fix**: Replace `"claude-opus-4-20250514"` with `"claude-opus-4-7"` in 3 files (5-minute fix)
- **Open since**: 2026-04-28 (16 days unactioned)

---

### HIGH (ESCALATING — 29+ days) — `pytz` Missing from `pyproject.toml`

DuckDB raises `InvalidInputException: Required module 'pytz' failed to import` on any query returning
a `TIMESTAMPTZ` column in clean-install environments. Commit `a5cd92c` claimed "Install pytz for
scorecard ops metrics" but pytz was installed via pip only — it was never added to
`[project] dependencies` in `pyproject.toml`. Confirmed: `python3 -c "import pytz"` fails in the
current environment.

The `--scorecard` CLI path and 11 tests remain broken in any fresh clone.

- **Severity**: HIGH — blocks scorecard pipeline and 11 tests on clean installs
- **Fix**: Add `"pytz>=2024.1"` to `[project] dependencies` in `backend/pyproject.toml` (1-minute fix)
- **Open since**: ~2026-04-15 (29+ days unactioned)

---

### MEDIUM (NEW) — `crisis_ingester.py` Within-Batch Duplicate Bug

`CrisisIngester.ingest_events()` fetches `existing_hashes` from the DB once before the insert loop.
When a batch contains two events with the same headline (same MD5 hash), the second event is not
blocked by the hash check because `existing_hashes` is not updated after the first event is inserted.
Both events are inserted. The fuzzy dedup also can't catch within-batch duplicates since
`fuzzy_candidate_headlines` is similarly fetched once before the loop.

Example failure scenario: a Google News RSS batch with two slightly-different-URL links to the same
story will insert two identical rows.

- **Severity**: MEDIUM — duplicate events skew crisis context and prediction prompts
- **Fix**: Add `existing_hashes.add(headline_hash)` after a successful INSERT at
  `crisis_ingester.py:88`; update `fuzzy_candidate_headlines` similarly after each insert
- **Introduced**: commit `69c5c56` (yesterday)

---

### MEDIUM (NEW) — Missing Migration for `crisis_events.headline_hash`

The `crisis_events` table DDL now includes `headline_hash TEXT` but `_migrate_legacy_tables()` in
`schema.py` has no corresponding `_add_column_if_missing` call for `crisis_events`. Any existing
database created before `headline_hash` was added will fail at runtime when `CrisisIngester` executes
the batch `SELECT headline_hash FROM crisis_events WHERE headline_hash IN (...)` query —
`InvalidInputException: Referenced column "headline_hash" not found`.

All other new columns in this project have migration guards; this one was missed.

- **Severity**: MEDIUM — breaks ingestion on upgrade; new installs are unaffected
- **Fix**: Add to `_migrate_legacy_tables()`:
  ```python
  if _table_exists(conn, "crisis_events"):
      _add_column_if_missing(conn, "crisis_events", "headline_hash", "TEXT")
  ```
- **Introduced**: commit `69c5c56` (yesterday)

---

### MEDIUM (PERSISTENT) — Staleness Penalty Does Not Penalize `probability`

`ensemble_predict()` applies the staleness penalty (`compute_staleness_penalty(context_age_hours)`)
only to `median_parsed["confidence"]` (the model's self-reported confidence). The `probability` field
returned in `ensemble_result["probability"]` is unmodified. In `oil_price.py` and sibling predictors,
`PredictionOutput.probability = ensemble["probability"]` — the raw ensemble mean — is what
`DivergenceDetector` uses to compute edge and generate BUY/SELL signals.

With context 32 days stale (today), `penalty_factor = 0.0`. `confidence` is zeroed out but
`probability` still drives trade signals at full strength. The practical consequence is that stale
predictions produce trade signals as if the context were fresh.

- **Severity**: MEDIUM — signals generated from stale context carry no visible discount in the
  divergence detector; position sizing via Quarter-Kelly is the only mitigation (uses `confidence`)
- **Fix**: In `ensemble_predict()`, also scale or cap `ensemble_result["probability"]` toward 0.5
  when `penalty_factor < 1.0`, or propagate `penalty_factor` into `DivergenceDetector` to suppress
  signals below a threshold
- **Introduced**: commit `53f93b1` (yesterday) — staleness logic added but incomplete

---

### MEDIUM (PERSISTENT) — Calibration Predicate Mismatch (code bug, tests mask it)

`recalibrate_probability()` at `scoring/recalibration.py:71` counts qualifying signals with
`WHERE model_id = ? AND model_was_correct IS NOT NULL`. The `calibration_curve()` function queries
from `signal_quality_evaluation` view, which requires `resolution_price IS NOT NULL`. The mismatch
means the count gate can pass (signals with `model_was_correct` set but `resolution_price = NULL`)
while `calibration_curve()` returns empty buckets, causing recalibration to silently no-op. The
test fixtures now default `resolution_price=1.0` which masks the bug in tests.

- **Severity**: MEDIUM — production recalibration may silently no-op; tests no longer catch it
- **Fix**: Add `AND resolution_price IS NOT NULL` to the count query at `recalibration.py:71`

---

### MEDIUM (PERSISTENT) — Direct DB Writes Bypass `DbWriter` Single-Writer Pattern

Spec mandates all writes go through `asyncio.Queue → DbWriter`. The following modules still write
directly via `conn.execute()`:

| File | Lines | Table(s) |
|---|---|---|
| `ops/alerts.py` | 106 | `ops_events` |
| `scoring/ledger.py` | 225, 256 | `signal_ledger` |
| `scoring/prediction_log.py` | 85 | `prediction_log` |
| `scoring/resolution.py` | 60, 124 | `signal_ledger` |
| `scoring/scorecard.py` | 21 | `daily_scorecard` |
| `budget/tracker.py` | 43 | `llm_usage` |
| `cli/brief.py` | 49, 68, 350 | `runs`, `market_prices` |
| `ingestion/crisis_ingester.py` | 89 | `crisis_events` (new) |

Risk is LOW while CLI runs sequentially, HIGH if any path runs concurrently with FastAPI server.

- **Severity**: MEDIUM (latent HIGH)

---

### LOW (PERSISTENT) — `test_google_news.py` Uses Workaround, Not Root Fix

The test fixture still has hardcoded `pubDate` strings for April 8, 2026. The fix applied was to
expand `max_age_hours` to `24 * 365` rather than replacing hardcoded dates with relative ones. Tests
pass, but the test no longer exercises the realistic default `max_age_hours=24` path used in
production. The 1-hour narrow-window test at line 199 still works.

- **Severity**: LOW — test coverage gap; no production impact
- **Fix**: Replace hardcoded `pubDate` strings with dates computed relative to `datetime.now()` at
  test runtime, and restore `max_age_hours` to realistic values per test case

---

### LOW (PERSISTENT) — Python Version Requirement Weaker Than Spec

`pyproject.toml` declares `requires-python = ">=3.11"`. CLAUDE.md and the Phase 1 design spec state
Python 3.12. System runtime is Python 3.11.15. No current breakage; cosmetic drift.

- **Severity**: LOW
- **Fix**: Update to `requires-python = ">=3.12"`

---

### LOW (PERSISTENT) — `CLAUDE.md` Tech Stack Lists Uninstalled Dependencies

CLAUDE.md lists `deck.gl`, `MapLibre GL`, `h3-js`, `react-map-gl`, `sentence-transformers`,
`searoute`, `shapely`, `google-cloud-bigquery`, and `websockets` as active dependencies. None appear
in `pyproject.toml` or `frontend/package.json`. The frontend is a Recharts REST-polling dashboard.

- **Severity**: LOW — onboarding confusion only
- **Fix**: Rewrite CLAUDE.md Technology Stack section to reflect actual stack

---

## Spec / Plan Consistency

The Phase 1 spec described ~50 LLM agents with H3 spatial visualization. The implementation
deliberately pivoted to 3 Claude prediction models + prediction-market arbitrage. No regression from
prior reports on these items.

| Spec Item | Status |
|---|---|
| `agents/` — 50-agent country/sub-actor swarm | Out of scope (deliberate pivot) |
| `spatial/` — H3 hexagon model, deck.gl | Out of scope (deliberate pivot) |
| `api/auth.py` — invite codes, admin password | Not implemented |
| `api/websocket.py` — real-time push | Not implemented; frontend uses polling |
| `simulation/circuit_breaker.py` | Not implemented |
| `ingestion/dedup.py` — semantic deduplication | Not implemented; fuzzy dedup via SequenceMatcher used |
| Prediction models (oil_price, ceasefire, hormuz) | Implemented; **deprecated model ID blocks live runs** |
| Crisis context staleness tracking | Implemented (new); staleness penalty not applied to `probability` |
| Backtest harness with look-ahead guard | Implemented (new) |
| Kalshi + Polymarket clients | Implemented and tested |
| Signal ledger, paper trading, portfolio allocator | Implemented and tested |
| Divergence detector | Implemented and tested |
| Contract registry + mapping policy | Implemented and tested |
| Daily scorecard ETL | Implemented; `pytz` missing from pyproject.toml breaks clean installs |

---

## Dependency Audit

| Package | `pyproject.toml` | Status | Action |
|---|---|---|---|
| `pytz>=2024.1` | **MISSING** | Not installed in this env | **Add immediately** |
| `fastapi>=0.115` | Present | OK | No action |
| `truthbrush>=0.2` | Present | OK | No action |
| `duckdb>=1.2` | Present | 1.5.2 installed | OK |
| `cryptography>=44.0` | Present | 41.0.7 (Debian system) | Blocks `pip install -e .` in this env; declared minimum not met |
| `anthropic>=0.52` | Present | OK | OK |

Frontend (`react ^18.3.1`, `recharts ^2.15.0`, `vite ^6.0.0`, `typescript ~5.6.2`): current, no
known CVEs.

---

## Positive Findings

- **Backtest harness** fully implemented with `LookAheadGuard` temporal view isolation — well-designed
- **Staleness penalty** end-to-end wired: context age computed from DB, propagated to ensemble,
  logged to `prediction_log` with `context_age_hours`, `penalty_factor`, `staleness_penalty_applied`
- **Crisis ingester** with batch hash dedup (one round-trip for N events) and 21-day fuzzy lookback
- **429 tests passing** (per latest commit) — no regressions from prior stable baseline
- **No secrets in repo** — `.env.example` uses placeholders only
- **`AsyncAnthropic` client** used everywhere; no sync instantiations
- **`DbWriter` single-writer implementation** is correct where it IS used
- **RSA-PSS Kalshi auth** — correct implementation
- **Runtime safety controls** (kill switch, live-execution ACK) — correctly implemented and tested

---

## Recommendations (Priority Order)

1. **[5 min] Fix model ID** — replace `"claude-opus-4-20250514"` with `"claude-opus-4-7"` in
   `oil_price.py:143`, `ceasefire.py:116`, `hormuz.py:118`, and `ensemble.py:89` (docstring). Silent
   production blocker for 16 days.
2. **[1 min] Add `pytz`** — append `"pytz>=2024.1"` to `[project] dependencies` in
   `backend/pyproject.toml`. Unblocks scorecard pipeline on clean installs. 29+ days unactioned.
3. **[15 min] Add `crisis_events.headline_hash` migration** — add
   `_add_column_if_missing(conn, "crisis_events", "headline_hash", "TEXT")` inside
   `_migrate_legacy_tables()` in `schema.py`. Prevents upgrade breakage.
4. **[15 min] Fix within-batch duplicate bug** — in `crisis_ingester.py`, after successful INSERT,
   add `existing_hashes.add(headline_hash)` and append to `fuzzy_candidate_headlines`. Prevents
   duplicate events from same ingestion batch.
5. **[30 min] Apply staleness penalty to `probability`** — in `ensemble_predict()`, when
   `penalty_factor == 0.0`, either clamp `ensemble_result["probability"]` toward 0.5 or propagate
   `staleness_penalty_applied` into `DivergenceDetector` to suppress signal generation.
6. **[30 min] Align `recalibrate_probability()` predicate** — add `AND resolution_price IS NOT NULL`
   to count query at `scoring/recalibration.py:71`.
7. **[2 hrs] Wire `DbWriter` or annotate direct-write sites** — prevents future locking under
   concurrent load; add `crisis_ingester.py` to the list.
8. **[30 min] Fix `test_google_news.py` fixture dates** — use relative dates, restore realistic
   `max_age_hours` per test case.
9. **[5 min] Update `pyproject.toml`** `requires-python` to `>=3.12`.
10. **[30 min] Update `CLAUDE.md`** tech stack to reflect actual Recharts polling frontend.
