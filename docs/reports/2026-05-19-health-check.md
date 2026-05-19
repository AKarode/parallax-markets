# Parallax Health Check — 2026-05-19

**Status: YELLOW**

No commits since the 2026-05-18 health check — all previously identified issues remain open. Test results are unchanged: **17 failed, 416 passed, 13 skipped**. The two HIGH blockers (`pytz` missing and invalid Claude model ID) have been open for 34 and 21 days respectively; production predictions are still broken and 17 tests still fail on fresh installs.

---

## Test Results

- **17 failed, 416 passed, 13 skipped** — identical to 2026-05-17 and 2026-05-18
- Python 3.11.15 · pytest 8.4.2 · DuckDB 1.5.2
- All 17 failures: `_duckdb.InvalidInputException: Required module 'pytz' failed to import`

| Failure Cluster | Count |
|---|---|
| `test_scorecard.py` | 10 |
| `test_crisis_context_db.py` | 4 |
| `test_llm_usage.py` | 1 |
| `test_ops_events.py` | 1 |
| `test_phase1_critical.py` | 1 |

Root cause: `TIMESTAMPTZ` columns (`runs.started_at/ended_at`, `daily_scorecard.computed_at`, `ops_events.created_at`, `llm_usage.created_at`, `crisis_events.inserted_at`) trigger a DuckDB internal pytz import that fails on this Python environment.

---

## Issues Found

### [HIGH] Invalid Claude Model ID Blocks All Live Predictions — *Open 21 days*

`ensemble_predict(model="claude-opus-4-20250514")` hardcoded in:
- `prediction/oil_price.py:143`
- `prediction/ceasefire.py:116`
- `prediction/hormuz.py:118`
- docstring reference at `prediction/ensemble.py:89`

`claude-opus-4-20250514` is not a valid Anthropic model identifier. Every live prediction call to the API is rejected. The pipeline produces no live output in production.

**Fix**: Replace `"claude-opus-4-20250514"` with `"claude-opus-4-7"` in three files; update `ensemble.py:89` docstring.

---

### [HIGH] `pytz` Missing from `pyproject.toml` — *Open 34+ days*

DuckDB 1.5.2 raises `InvalidInputException` on any query touching `TIMESTAMPTZ` columns when `pytz` is absent. Blocks 17 tests and breaks `--scorecard` CLI on fresh installs.

**Fix**: Add `"pytz>=2024.1"` to `[project] dependencies` in `backend/pyproject.toml`.

---

### [MEDIUM] Staleness Penalty Not Applied to `probability`

`ensemble_predict()` (`prediction/ensemble.py:156–168`) scales `confidence` by `penalty_factor` when context is stale but leaves `probability` unchanged. At 35+ days stale (crisis context last refreshed ~2026-04-12), `penalty_factor` → 0.0 so `confidence` is zeroed while `probability` continues to drive divergence detection and trade signals at full strength.

**Fix**: Blend `probability` toward 0.5 proportional to `penalty_factor`:
```python
adjusted_probability = 0.5 + (probability - 0.5) * penalty_factor
```

---

### [MEDIUM] Calibration Predicate Mismatch in `recalibration.py`

`recalibrate_probability()` (`scoring/recalibration.py:71`) counts eligible signals with:
```sql
WHERE model_id = ? AND model_was_correct IS NOT NULL
```
But `calibration_curve()` requires `resolution_price IS NOT NULL`. Fixtures that set `model_was_correct` without `resolution_price` pass the gate (≥10 signals) but produce an empty curve — recalibration silently no-ops.

**Fix**: Add `AND resolution_price IS NOT NULL` to the count query at line 71.

---

### [MEDIUM] Within-Batch Duplicate Bug in `crisis_ingester.py`

`CrisisIngester.ingest_events()` (`ingestion/crisis_ingester.py:52–96`): `existing_hashes` is populated from DB before the loop but never updated inside it. Two events in the same batch sharing a headline hash will both be inserted.

**Fix**: Add `existing_hashes.add(headline_hash)` after `inserted += 1` at line 96.

---

### [MEDIUM] Missing Migration for `crisis_events.headline_hash`

`headline_hash TEXT` appears in the `CREATE TABLE` DDL (`db/schema.py:491`) but there is no `_add_column_if_missing(conn, "crisis_events", "headline_hash", "TEXT")` in `_migrate_legacy_tables()`. Databases created before this column was added fail on upgrade.

**Fix**: Add `_add_column_if_missing(conn, "crisis_events", "headline_hash", "TEXT")` inside `_migrate_legacy_tables()`.

---

### [MEDIUM] Direct DuckDB Writes Bypass Single-Writer Queue

The spec mandates all writes go through `asyncio.Queue → DbWriter`. These modules write directly:

| File | Write Site | Table |
|---|---|---|
| `scoring/ledger.py` | lines 225, 256 | `signal_ledger` |
| `scoring/resolution.py` | lines 60, 124 | `signal_ledger`, `trade_positions` |
| `budget/tracker.py` | line 43 | `llm_usage` |
| `ops/alerts.py` | line 106 | `ops_events` |
| `cli/brief.py` | lines 49, 68, 350 | `runs`, `market_prices` |
| `scoring/prediction_log.py` | line 79 | `prediction_log` |

Risk is low while the CLI runs single-threaded; becomes a concurrency hazard if any write endpoint runs concurrently with the FastAPI server.

**Fix**: Wire `DbWriter.enqueue()` at each write site, or add `# SINGLE_PROCESS_ONLY` annotations and a startup guard in `main.py`.

---

### [LOW] `backtest/engine.py` and `backtest/runner.py` Have No Test Coverage

The `backtest/` module (`engine.py`, `runner.py`) has no tests. `LookAheadGuard` is tested (12 passing). `BacktestRunner` and `BacktestEngine` are untested.

**Fix**: Add `test_backtest_engine.py` and `test_backtest_runner.py` covering at minimum happy-path simulation and date-boundary logic.

---

### [LOW] Spec/Architecture Divergence — Prediction Market Pivot

The Phase 1 design spec (`docs/superpowers/specs/2026-03-30-parallax-phase1-design.md`) describes a 50-agent LLM swarm with H3 hex visualization, WebSocket streaming, and GDELT-driven cascade simulation. The implemented codebase is a prediction market edge-finder (3 Claude prediction models, Kalshi/Polymarket API integration, paper trading). The `docs/superpowers/` spec is now a historical artifact. The frontend uses REST polling (`hooks/usePolling.ts`) rather than the spec's WebSocket architecture; none of the H3/deck.gl/simulation modules exist.

This divergence is intentional per `CLAUDE.md` and not a bug — flagged for documentation hygiene only.

---

## Positive Findings

- **416/446 tests pass** — no regressions
- `LookAheadGuard` (backtest) is well-architected with view-based date bounding; all 12 tests pass
- Kalshi RSA-PSS auth, `yes_bid_dollars` field naming, demo/production split are correct
- `DbWriter` single-writer implementation is correct where used (`db/writer.py`)
- `AsyncAnthropic` client used consistently — no accidental sync instantiations
- `pyproject.toml` requires-python pinned to `>=3.11` (spec said 3.12 — actual runtime is 3.11.15, so this is an intentional correction)
- No secrets in repo — `.env.example` uses placeholder values only
- Migration system (`_add_column_if_missing`) provides safe schema evolution

---

## Dependency Audit

**Backend (`pyproject.toml`):**

| Issue | Detail |
|---|---|
| Missing `pytz` | Required by DuckDB 1.5.2 at runtime for TIMESTAMPTZ queries |
| Missing `h3`, `websockets`, `sentence-transformers`, `searoute`, `shapely`, `google-cloud-bigquery` | Listed in CLAUDE.md stack but absent from `pyproject.toml` — only matters if those code paths are invoked |
| `truthbrush>=0.2` | Added for Truth Social ingestion; not in original spec — intentional addition |
| `cryptography>=44.0` | Added for Kalshi RSA-PSS auth; not in original spec — intentional addition |
| `requires-python = ">=3.11"` | Spec says 3.12; production runs 3.11.15 — deliberate downgrade |

**Frontend (`package.json`):**

| Issue | Detail |
|---|---|
| Missing `deck.gl`, `maplibre-gl`, `react-map-gl`, `h3-js` | Listed in CLAUDE.md stack but absent — consistent with the pivot away from H3 visualization |
| `recharts ^2.15.0` | Not in original spec; used for sparklines/charts — appropriate addition |

No known CVEs in the declared dependency set at current versions.

---

## Recommendations — Priority Order

1. **`pytz`** — `"pytz>=2024.1"` in `pyproject.toml`. One-line fix. Unblocks 17 tests. 34 days unactioned.
2. **Model ID** — Replace `"claude-opus-4-20250514"` with `"claude-opus-4-7"` in `oil_price.py`, `ceasefire.py`, `hormuz.py`; update `ensemble.py:89`. Live predictions are broken without this. 21 days unactioned.
3. **Staleness → probability** — Apply `penalty_factor` to `probability` in `ensemble.py` so stale context attenuates signals, not just metadata.
4. **Calibration predicate** — Add `AND resolution_price IS NOT NULL` to `recalibration.py:71`.
5. **Within-batch dedup** — `existing_hashes.add(headline_hash)` after each insert in `crisis_ingester.py`.
6. **`headline_hash` migration** — `_add_column_if_missing(conn, "crisis_events", "headline_hash", "TEXT")` in `_migrate_legacy_tables()`.
7. **Single-writer annotation** — Wire `DbWriter` to all write sites or add `# SINGLE_PROCESS_ONLY` guards.
8. **Backtest coverage** — Add `test_backtest_engine.py` and `test_backtest_runner.py`.
