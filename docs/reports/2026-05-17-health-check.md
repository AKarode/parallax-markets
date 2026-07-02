# Parallax Health Check — 2026-05-17

**Status: YELLOW**

Main branch is at `d48d25f` (2026-05-10 health check) locally, but `origin/main` is at `2013942` — **28 commits of work from prior sessions exist on origin but were not fetched into the local clone at session start**. Those commits contain test additions, documentation, and several bug fixes. The true remote tip includes health checks through 2026-05-16. This report audits the code as it stands on `origin/main`. Test result: **17 failed, 416 passed, 13 skipped** (run from the up-to-date working tree including those commits).

*Correction from prior reports: 2026-05-15 and 2026-05-16 incorrectly stated "four open issues" — there have been six since 2026-05-14.*

---

## Test Results (from origin/main working tree)

- **17 failed, 416 passed, 13 skipped**
- Python 3.11.15; pytest 8.4.2; DuckDB 1.5.2
- All 17 failures trace to a single root cause: `ModuleNotFoundError: No module named 'pytz'`

| Failure Cluster | Count | Root Cause |
|---|---|---|
| `test_scorecard.py` | 10 | `pytz` missing — DuckDB TIMESTAMPTZ queries crash in `_compute_ops_runtime()` |
| `test_crisis_context_db.py` | 4 | `pytz` missing — `render_crisis_context_from_db()` queries `TIMESTAMPTZ` column |
| `test_llm_usage.py` | 1 | `pytz` missing |
| `test_ops_events.py` | 1 | `pytz` missing |
| `test_phase1_critical.py` | 1 | `pytz` missing — `test_predictor_uses_db_age_when_events_present` |

Previous clean baseline: 429 passed / 0 failed (commit `a5cd92c`, 2026-05-14). Delta: 4 new tests added in `a5cd92c` (`test_crisis_context_db.py`) now exposed by the pytz bug, plus 13 previously-passing tests newly failing due to the `--ignore-installed` install path restoring DuckDB 1.5.2's strict pytz requirement.

---

## Issues Found

### HIGH (19 days) — Deprecated Claude Model ID Blocks All Live Prediction Runs

`ensemble_predict(model="claude-opus-4-20250514")` in `prediction/oil_price.py:143`, `prediction/ceasefire.py:116`, `prediction/hormuz.py:118`. This is not a valid Anthropic model ID; every live prediction API call is rejected. The pipeline produces no live output.

- **Fix**: Replace `"claude-opus-4-20250514"` with `"claude-opus-4-7"` in three files. Five-minute fix.
- **Open since**: 2026-04-28 (19 days unactioned)

### HIGH (32+ days) — `pytz` Missing from `pyproject.toml`

DuckDB 1.5.2 raises `InvalidInputException: Required module 'pytz' failed to import` on any `TIMESTAMPTZ` column query. Blocks 17 tests (up from 12 as `test_crisis_context_db.py` was added); breaks `--scorecard` CLI in clean-install environments.

- **Affected tables**: `runs.started_at/ended_at`, `daily_scorecard.computed_at`, `ops_events.created_at`, `llm_usage.created_at`, `crisis_events.inserted_at`
- **Fix**: Add `"pytz>=2024.1"` to `[project] dependencies` in `backend/pyproject.toml`. One-line fix.
- **Open since**: ~2026-04-15 (32+ days unactioned)

### MEDIUM — Within-Batch Duplicate Bug in `crisis_ingester.py`

`CrisisIngester.ingest_events()` (`ingestion/crisis_ingester.py:52-96`): `existing_hashes` is populated from the DB before the insertion loop but never updated after each successful INSERT. Two events in the same batch sharing the same headline hash will both be inserted. Fuzzy dedup at line 72 (updated to 21-day window in `69c5c56`) partially mitigates identical headlines via `fuzzy_candidate_headlines.append()`, but the hash guard itself is silently ineffective within a batch.

- **Fix**: Add `existing_hashes.add(headline_hash)` after line 96 (`inserted += 1`).

### MEDIUM — Missing Migration for `crisis_events.headline_hash`

`headline_hash TEXT` appears in the `CREATE TABLE` DDL (`db/schema.py:491`) but there is no `_add_column_if_missing(conn, "crisis_events", "headline_hash", "TEXT")` call in `_migrate_legacy_tables()`. Databases created before this column was added fail at runtime on upgrade.

- **Fix**: Add `_add_column_if_missing(conn, "crisis_events", "headline_hash", "TEXT")` to `_migrate_legacy_tables()`.

### MEDIUM — Staleness Penalty Not Applied to `probability`

`ensemble_predict()` (`prediction/ensemble.py:151-169`) scales `confidence` by `penalty_factor` when context is stale, but `probability` is not scaled. At 35+ days stale (crisis context last updated 2026-04-12), `penalty_factor` → 0.0, so `confidence` is zeroed but `probability` continues to drive divergence detection and trade signal generation at full strength.

- **Impact**: Trade signals fire on stale model output with no attenuation.
- **Fix**: When `penalty_factor < 1.0`, blend `probability` toward 0.5: `adjusted_probability = 0.5 + (probability - 0.5) * penalty_factor`. Or propagate `staleness_penalty_applied` as a blocking flag into `DivergenceDetector`.

### MEDIUM — Calibration Predicate Mismatch

`recalibrate_probability()` (`scoring/recalibration.py:71`) gates on:
```sql
WHERE model_id = ? AND model_was_correct IS NOT NULL
```
The downstream `calibration_curve()` requires `resolution_price IS NOT NULL` (via `signal_quality_evaluation` view). Fixtures that populate `model_was_correct` without `resolution_price` cause the gate to pass (≥10 signals found) but the curve to return empty — recalibration silently no-ops.

- **Fix**: Add `AND resolution_price IS NOT NULL` to the count query at `scoring/recalibration.py:71`.

### MEDIUM (latent HIGH) — Direct DuckDB Writes Bypass Single-Writer Queue

The spec mandates all writes go through `asyncio.Queue → DbWriter`. These modules write directly via `conn.execute()`, bypassing the queue:

| File | Lines | Tables Written |
|---|---|---|
| `scoring/ledger.py` | 225, 256 | `signal_ledger` |
| `scoring/resolution.py` | 60, 124 | `signal_ledger`, `trade_positions` |
| `budget/tracker.py` | 43 | `llm_usage` |
| `ops/alerts.py` | 106 | `ops_events` |
| `cli/brief.py` | 49, 68, 350 | `runs`, `market_prices` |

Risk is LOW while the CLI runs single-threaded; HIGH if any write endpoint runs concurrently with the FastAPI server.

- **Fix**: Wire `DbWriter.enqueue()` to each write site, or annotate with `# SINGLE_PROCESS_ONLY` and add a startup guard in `main.py`.

---

## Positive Findings

- **416/446 tests pass** — no regressions beyond the known pytz root cause
- **Kalshi auth verified correct**: RSA-PSS signature (`markets/kalshi.py:127-134`), `yes_bid_dollars` field naming (`:187-198`), demo/production split all correct
- **`DbWriter`** single-writer implementation is correct where used (`db/writer.py`)
- **`AsyncAnthropic` client** used everywhere — no accidental sync instantiations
- **Staleness wiring** (`53f93b1`) and **crisis_ingester batch hash fix** (`69c5c56`) are present on origin/main and functioning
- **No secrets in repo** — `.env.example` uses placeholders only
- **Cascade engine + scenario config** fully implemented and unit-tested

---

## Recommendations

Priority order:

1. **`pytz`** — `"pytz>=2024.1"` in `pyproject.toml`. One-line fix, unblocks 17 tests. 32+ days unactioned.
2. **Model ID** — Replace `"claude-opus-4-20250514"` with `"claude-opus-4-7"` in three prediction files. Five-minute fix. 19 days unactioned. Production is broken without this.
3. **Staleness → probability** — Apply `penalty_factor` to `probability`, not just `confidence`, so stale context attenuates trade signals.
4. **Calibration predicate** — Add `AND resolution_price IS NOT NULL` to `recalibration.py:71`.
5. **Within-batch dedup** — `existing_hashes.add(headline_hash)` after each insert.
6. **headline_hash migration** — `_add_column_if_missing(conn, "crisis_events", "headline_hash", "TEXT")` in `_migrate_legacy_tables()`.
7. **Single-writer annotation** — Either wire `DbWriter` to all write sites or annotate and add a startup guard.
