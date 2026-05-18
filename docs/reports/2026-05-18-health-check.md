# Parallax Health Check — 2026-05-18

**Status: YELLOW**

Test results are unchanged from yesterday: **17 failed, 416 passed, 13 skipped** (446 total). All 17 failures share the same root cause — `pytz` missing from `pyproject.toml` — which has now been open for 33+ days. The new `backtest/` module (engine, look-ahead guard, runner, report) was added since last check; its 12 look-ahead guard tests all pass, but the engine and runner have no test coverage yet.

---

## Test Results

- **17 failed, 416 passed, 13 skipped** — identical to 2026-05-17
- Python 3.11.15 · pytest 8.4.2 · DuckDB 1.5.2
- All 17 failures: `_duckdb.InvalidInputException: Required module 'pytz' failed to import`

| Failure Cluster | Count |
|---|---|
| `test_scorecard.py` | 10 |
| `test_crisis_context_db.py` | 4 |
| `test_llm_usage.py` | 1 |
| `test_ops_events.py` | 1 |
| `test_phase1_critical.py` | 1 |

---

## Issues Found

### HIGH (20 days) — Invalid Claude Model ID Blocks All Live Predictions

`ensemble_predict(model="claude-opus-4-20250514")` in `prediction/oil_price.py:143`, `prediction/ceasefire.py:116`, `prediction/hormuz.py:118`. This model ID is not a valid Anthropic model; every live prediction call is rejected. The pipeline produces no live output.

- **Fix**: Replace `"claude-opus-4-20250514"` with `"claude-opus-4-7"` in three files. The docstring in `ensemble.py:89` also references the old ID and should be updated.
- **Open since**: 2026-04-28 (20 days)

### HIGH (33+ days) — `pytz` Missing from `pyproject.toml`

DuckDB 1.5.2 raises `InvalidInputException` on any `TIMESTAMPTZ` column query when `pytz` is not installed. Blocks 17 tests; breaks `--scorecard` CLI on fresh installs.

- **Affected tables**: `runs.started_at/ended_at`, `daily_scorecard.computed_at`, `ops_events.created_at`, `llm_usage.created_at`, `crisis_events.inserted_at`
- **Fix**: Add `"pytz>=2024.1"` to `[project] dependencies` in `backend/pyproject.toml`. One-line fix.
- **Open since**: ~2026-04-15 (33+ days)

### MEDIUM — Within-Batch Duplicate Bug in `crisis_ingester.py`

`CrisisIngester.ingest_events()` (`ingestion/crisis_ingester.py:52-96`): `existing_hashes` is pre-populated from the DB before the loop but never updated after a successful insert. Two events in the same batch sharing a headline hash will both be inserted. The fuzzy candidate list (`fuzzy_candidate_headlines`) is updated, partially mitigating headline-level similarity, but the hash guard at line 68 is silently ineffective within a batch.

- **Fix**: Add `existing_hashes.add(headline_hash)` after `inserted += 1` at line 96.

### MEDIUM — Missing Migration for `crisis_events.headline_hash`

`headline_hash TEXT` appears in `CREATE TABLE` DDL (`db/schema.py:491`) but there is no `_add_column_if_missing(conn, "crisis_events", "headline_hash", "TEXT")` call in `_migrate_legacy_tables()`. Databases created before this column was added fail at runtime on upgrade.

- **Fix**: Add `_add_column_if_missing(conn, "crisis_events", "headline_hash", "TEXT")` to `_migrate_legacy_tables()`.

### MEDIUM — Staleness Penalty Not Applied to `probability`

`ensemble_predict()` (`prediction/ensemble.py:156-168`) scales `confidence` by `penalty_factor` when context is stale but leaves `probability` unchanged. At 35+ days stale (crisis context last updated 2026-04-12), `penalty_factor` → 0.0 so `confidence` is zeroed while `probability` continues to drive divergence detection and trade signals at full strength.

- **Fix**: When `penalty_factor < 1.0`, blend `probability` toward 0.5: `adjusted_probability = 0.5 + (probability - 0.5) * penalty_factor`.

### MEDIUM — Calibration Predicate Mismatch in `recalibration.py`

`recalibrate_probability()` (`scoring/recalibration.py:71`) gates recalibration on:
```sql
WHERE model_id = ? AND model_was_correct IS NOT NULL
```
The downstream `calibration_curve()` requires `resolution_price IS NOT NULL`. Fixtures that set `model_was_correct` without `resolution_price` cause the gate to pass (≥10 signals found) but the curve to return empty — recalibration silently no-ops.

- **Fix**: Add `AND resolution_price IS NOT NULL` to the count query at `scoring/recalibration.py:71`.

### MEDIUM (latent HIGH) — Direct DuckDB Writes Bypass Single-Writer Queue

The spec mandates all writes go through `asyncio.Queue → DbWriter`. These modules write directly via `conn.execute()`:

| File | Lines | Tables Written |
|---|---|---|
| `scoring/ledger.py` | 225, 256 | `signal_ledger` |
| `scoring/resolution.py` | 60, 124 | `signal_ledger`, `trade_positions` |
| `budget/tracker.py` | 43 | `llm_usage` |
| `ops/alerts.py` | 106 | `ops_events` |
| `cli/brief.py` | 49, 68, 350 | `runs`, `market_prices` |

Risk is LOW while CLI runs single-threaded; HIGH if any write endpoint runs concurrently with the FastAPI server.

- **Fix**: Wire `DbWriter.enqueue()` to each write site, or annotate with `# SINGLE_PROCESS_ONLY` and add a startup guard in `main.py`.

### LOW (New) — `backtest/engine.py` and `backtest/runner.py` Have No Test Coverage

The new `backtest/` module adds `engine.py` and `runner.py` but only `look_ahead_guard.py` has tests (`test_backtest_look_ahead.py`, 12 tests all passing). `BacktestRunner` and `BacktestEngine` are untested.

- **Fix**: Add `test_backtest_engine.py` and `test_backtest_runner.py` covering at minimum the happy path and edge cases for the simulation date boundary logic.

---

## Positive Findings

- **416/446 tests pass** — no regressions from yesterday
- **New `backtest/` module**: `LookAheadGuard` is well-architected (view-based date bounding instead of SQL regex injection); all 12 tests pass
- **Kalshi auth correct**: RSA-PSS signature, `yes_bid_dollars` field naming, demo/production split verified
- **`DbWriter`** single-writer implementation correct where used (`db/writer.py`)
- **`AsyncAnthropic` client** used everywhere — no accidental sync instantiations
- **No secrets in repo** — `.env.example` uses placeholders only

---

## Recommendations

Priority order:

1. **`pytz`** — `"pytz>=2024.1"` in `pyproject.toml`. One-line fix, unblocks 17 tests. 33+ days unactioned.
2. **Model ID** — Replace `"claude-opus-4-20250514"` with `"claude-opus-4-7"` in `oil_price.py`, `ceasefire.py`, `hormuz.py`; update docstring in `ensemble.py:89`. Production is broken without this. 20 days unactioned.
3. **Staleness → probability** — Apply `penalty_factor` to `probability` in `ensemble.py` so stale context attenuates trade signals, not just confidence metadata.
4. **Calibration predicate** — Add `AND resolution_price IS NOT NULL` to `recalibration.py:71`.
5. **Within-batch dedup** — `existing_hashes.add(headline_hash)` after each successful insert in `crisis_ingester.py`.
6. **headline_hash migration** — `_add_column_if_missing(conn, "crisis_events", "headline_hash", "TEXT")` in `_migrate_legacy_tables()`.
7. **Single-writer annotation** — Wire `DbWriter` to all write sites or add `# SINGLE_PROCESS_ONLY` annotation + startup guard.
8. **Backtest coverage** — Add tests for `BacktestEngine` and `BacktestRunner`.
