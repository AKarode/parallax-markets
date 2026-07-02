# Parallax Health Check — 2026-05-22

**Status: YELLOW**

No code changes since the 2026-05-21 health check. All previously identified issues remain open. Test results are unchanged at **17 failed, 416 passed, 13 skipped**, but a new operational issue surfaced: the package is not pre-installed in fresh container environments, causing 42 collection errors on bare startup (resolved by running `pip install -e ".[dev]"` from `backend/`). Unpinned dependencies also pulled major version upgrades on install today.

---

## Test Results

- **17 failed, 416 passed, 13 skipped** — identical to 2026-05-21
- Python 3.11.15 · pytest 8.4.2 · DuckDB 1.5.3 (upgraded from 1.5.2)
- All 17 failures: `_duckdb.InvalidInputException: Required module 'pytz' failed to import`

**Fresh-container alert**: Tests produced 42 collection errors (`ModuleNotFoundError: No module named 'parallax'`) before `pip install -e ".[dev]"` was run. This is the first day this session's container was cold.

| Failure Cluster | Count |
|---|---|
| `test_scorecard.py` | 10 |
| `test_crisis_context_db.py` | 4 |
| `test_llm_usage.py` | 1 |
| `test_ops_events.py` | 1 |
| `test_phase1_critical.py` | 1 |

Root cause: `TIMESTAMPTZ` columns trigger a DuckDB internal pytz import that fails on this Python 3.11.15 environment.

---

## Dependency Drift (NEW)

`pip install` on today's fresh container resolved the following upgrades from last-known-good versions:

| Package | Previous | Today | Notes |
|---|---|---|---|
| `duckdb` | 1.5.2 | **1.5.3** | pytz issue persists; no regression observed |
| `anthropic` | ≤0.52 constraint | **0.104.0** | No breaking changes found; tests pass |
| `fastapi` | ~0.115+ | **0.136.1** | Dashboard endpoint tests (20/20) pass |
| `starlette` | ~0.41+ | **1.0.1** | Major version bump — tests pass today, worth pinning |

All 20 dashboard endpoint tests pass under the new FastAPI/Starlette combination. Monitoring recommended given the major starlette version jump.

---

## Issues Found

### [MEDIUM] Package Not Pre-Installed in Fresh Container — *NEW*

On container cold-start, `parallax` is not installed, so every test file that imports from `parallax.*` fails with `ModuleNotFoundError` at collection time (42 errors today). There is no `pip install -e ".[dev]"` step in a devcontainer config, `Makefile`, or CI entrypoint that runs before tests.

**Fix**: Add `RUN pip install -e ".[dev]"` to `backend/Dockerfile`, or add a `Makefile` target `make test` that runs install then pytest. Alternatively add a `conftest.py` root-level fixture that verifies the package is importable.

---

### [HIGH] `pytz` Missing from `pyproject.toml` — *Open 37 days*

DuckDB 1.5.3 still raises `InvalidInputException` on any query touching `TIMESTAMPTZ` columns when `pytz` is absent. Blocks 17 tests and breaks `--scorecard` CLI on fresh installs.

**Fix**: Add `"pytz>=2024.1"` to `[project] dependencies` in `backend/pyproject.toml`.

---

### [HIGH] Invalid Claude Model ID Blocks All Live Predictions — *Open 24 days*

`ensemble_predict(model="claude-opus-4-20250514")` hardcoded in three files:
- `prediction/oil_price.py:143`
- `prediction/ceasefire.py:116`
- `prediction/hormuz.py:118`
- Docstring reference at `prediction/ensemble.py:89`

`claude-opus-4-20250514` is not a valid Anthropic model identifier (confirmed against anthropic SDK 0.104.0). Every live prediction call is rejected. The pipeline produces no live output in production.

**Fix**: Replace `"claude-opus-4-20250514"` with `"claude-opus-4-7"` in the three prediction files; update `ensemble.py:89` docstring.

---

### [MEDIUM] Staleness Penalty Not Applied to `probability` — *Open*

`ensemble_predict()` (`prediction/ensemble.py:156–169`) scales `confidence` by `penalty_factor` when context is stale but leaves `probability` unchanged. At 40+ days stale (crisis context last refreshed ~2026-04-12), `penalty_factor` approaches 0.0, zeroing `confidence` while `probability` continues to drive divergence detection and trade signals at full strength.

**Fix**: Blend `probability` toward 0.5 proportional to `penalty_factor`:
```python
adjusted_probability = 0.5 + (probability - 0.5) * penalty_factor
```

---

### [MEDIUM] Calibration Predicate Mismatch in `recalibration.py` — *Open*

`recalibrate_probability()` (`scoring/recalibration.py:71`) counts eligible signals with:
```sql
WHERE model_id = ? AND model_was_correct IS NOT NULL
```
But `calibration_curve()` requires `resolution_price IS NOT NULL`. Fixtures that set `model_was_correct` without `resolution_price` pass the gate (≥10 signals) but produce an empty curve — recalibration silently no-ops.

**Fix**: Add `AND resolution_price IS NOT NULL` to the count query at `recalibration.py:71`.

---

### [MEDIUM] Within-Batch Duplicate Bug in `crisis_ingester.py` — *Partially Mitigated*

`CrisisIngester.ingest_events()` (`ingestion/crisis_ingester.py:52–97`): `existing_hashes` is queried from DB before the loop but never updated inside it. In practice, the fuzzy check (`fuzzy_candidate_headlines` IS updated after each insert at line 97) catches same-title events with similarity ratio ≥ 0.85, which covers the identical-hash case. Risk remains if two events produce the same hash but fall below the 0.85 fuzzy threshold (very low probability with MD5 on short text).

**Fix**: Add `existing_hashes.add(headline_hash)` after `inserted += 1` at line 96 for defensive correctness.

---

### [MEDIUM] Missing Migration for `crisis_events.headline_hash` — *Open*

`headline_hash TEXT` appears in the `CREATE TABLE` DDL (`db/schema.py:491`) but there is no `_add_column_if_missing(conn, "crisis_events", "headline_hash", "TEXT")` in `_migrate_legacy_tables()`. Databases created before this column was added fail on upgrade.

**Fix**: Add `_add_column_if_missing(conn, "crisis_events", "headline_hash", "TEXT")` inside `_migrate_legacy_tables()`.

---

### [MEDIUM] Direct DuckDB Writes Bypass Single-Writer Queue — *Open*

The spec mandates all writes go through `asyncio.Queue → DbWriter`. `DbWriter` is implemented correctly in `db/writer.py` but is imported and used nowhere in the application. These modules write directly:

| File | Write Site | Table |
|---|---|---|
| `scoring/ledger.py` | lines 225, 256 | `signal_ledger` |
| `scoring/resolution.py` | lines 60, 124 | `signal_ledger`, `trade_positions` |
| `budget/tracker.py` | line 43 | `llm_usage` |
| `ops/alerts.py` | line 106 | `ops_events` |
| `cli/brief.py` | lines 130, 149 | `runs`, `market_prices` |
| `scoring/prediction_log.py` | line 79 | `prediction_log` |

Risk is low while the CLI runs single-threaded; becomes a concurrency hazard if `/api/brief/run` and a parallel API request trigger writes simultaneously.

**Fix**: Wire `DbWriter.enqueue()` at each write site, or add `# SINGLE_PROCESS_ONLY` annotations and a startup concurrency guard in `main.py`.

---

### [LOW] Unpinned Core Dependencies — *Newly Elevated*

`pyproject.toml` specifies only floor versions (`fastapi>=0.115`, `duckdb>=1.2`, etc.). Today's install pulled `starlette 1.0.1` (major version), `fastapi 0.136.1`, and `anthropic 0.104.0`. While tests pass today, an unreviewed major version of starlette could introduce breaking changes without a pin.

**Fix**: Pin upper bounds on `fastapi`, `starlette`, and `anthropic` (e.g., `fastapi>=0.115,<0.137`) until each major upgrade is explicitly reviewed.

---

### [LOW] `backtest/engine.py` and `backtest/runner.py` Have No Test Coverage — *Open*

The `backtest/` module (`engine.py`, `runner.py`) has no tests. `LookAheadGuard` is tested (12 passing). `BacktestRunner` and `BacktestEngine` are untested.

**Fix**: Add `test_backtest_engine.py` and `test_backtest_runner.py` covering happy-path simulation and date-boundary logic.

---

### [LOW] Spec/Architecture Divergence — Prediction Market Pivot — *Informational*

The Phase 1 design spec describes a 50-agent LLM swarm with H3 hex visualization, WebSocket streaming, and GDELT-driven cascade simulation. The implemented codebase is a prediction market edge-finder (3 Claude prediction models, Kalshi/Polymarket API integration, paper trading). The spec is a historical artifact. This divergence is intentional per `CLAUDE.md`.

---

## Positive Findings

- **416/446 tests pass** — stable for 37 consecutive days
- FastAPI 0.136.1 + Starlette 1.0.1 — all 20 dashboard endpoint tests pass on upgraded stack
- DuckDB 1.5.3 upgrade introduced no regressions beyond the pre-existing pytz issue
- `LookAheadGuard` (backtest) is well-architected; all 12 tests pass
- Kalshi RSA-PSS auth, `yes_bid_dollars` field naming, demo/production split are correct
- `AsyncAnthropic` client used consistently — no accidental sync instantiations
- Migration system (`_add_column_if_missing`) provides safe schema evolution for all tracked columns
- No secrets in repo — `.env.example` uses placeholder values only

---

## Recommendations — Priority Order

1. **`pytz`** — `"pytz>=2024.1"` in `pyproject.toml`. One-line fix. Unblocks 17 tests. **37 days unactioned.**
2. **Model ID** — Replace `"claude-opus-4-20250514"` with `"claude-opus-4-7"` in `oil_price.py`, `ceasefire.py`, `hormuz.py`; update `ensemble.py:89`. Live predictions are broken. **24 days unactioned.**
3. **Package install step** — Add `pip install -e ".[dev]"` to Dockerfile or a `Makefile test` target so fresh containers run tests without manual intervention.
4. **Staleness → probability** — Apply `penalty_factor` to `probability` in `ensemble.py` so stale context attenuates signals, not just metadata.
5. **Calibration predicate** — Add `AND resolution_price IS NOT NULL` to `recalibration.py:71`.
6. **`headline_hash` migration** — `_add_column_if_missing(conn, "crisis_events", "headline_hash", "TEXT")` in `_migrate_legacy_tables()`.
7. **Within-batch dedup** — `existing_hashes.add(headline_hash)` after each insert in `crisis_ingester.py`.
8. **Pin dependencies** — Add upper bounds on `fastapi`, `starlette`, `anthropic` to prevent unreviewed major version pulls.
9. **Single-writer annotation** — Wire `DbWriter` to all write sites or add `# SINGLE_PROCESS_ONLY` guards.
10. **Backtest coverage** — Add `test_backtest_engine.py` and `test_backtest_runner.py`.
