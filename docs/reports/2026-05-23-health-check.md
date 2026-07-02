# Parallax Health Check — 2026-05-23

**Status: YELLOW**

No code changes since the 2026-05-22 health check. All previously identified issues remain open and unactioned. Test results are unchanged at **17 failed, 416 passed, 13 skipped**. The two HIGH-severity issues (missing `pytz` and invalid Claude model ID) have now been open for 38 and 25 days respectively, actively breaking scorecard tests and blocking all live predictions in production.

---

## Test Results

- **17 failed, 416 passed, 13 skipped** — identical to 2026-05-22
- Python 3.11.15 · pytest 8.4.2 · DuckDB 1.5.3 · anthropic 0.104.1 (micro bump from 0.104.0)
- All 17 failures: `_duckdb.InvalidInputException: Required module 'pytz' failed to import`

| Failure Cluster | Count |
|---|---|
| `test_scorecard.py` | 10 |
| `test_crisis_context_db.py` | 4 |
| `test_llm_usage.py` | 1 |
| `test_ops_events.py` | 1 |
| `test_phase1_critical.py` | 1 |

Root cause: `TIMESTAMPTZ` columns trigger a DuckDB internal pytz import that fails on this Python 3.11.15 environment. `pytz` is absent from `pyproject.toml`.

---

## Issues Found

### [HIGH] `pytz` Missing from `pyproject.toml` — *Open 38 days*

DuckDB 1.5.3 raises `InvalidInputException` on any query touching `TIMESTAMPTZ` columns when `pytz` is absent. Blocks 17 tests and breaks `--scorecard` CLI on fresh installs.

**Fix**: Add `"pytz>=2024.1"` to `[project] dependencies` in `backend/pyproject.toml`.

---

### [HIGH] Invalid Claude Model ID Blocks All Live Predictions — *Open 25 days*

`ensemble_predict(model="claude-opus-4-20250514")` is hardcoded in three files:
- `prediction/oil_price.py:143`
- `prediction/ceasefire.py:116`
- `prediction/hormuz.py:118`
- Docstring reference at `prediction/ensemble.py:89`

`claude-opus-4-20250514` is not a valid Anthropic model identifier. Every live prediction call is rejected at the API level. The pipeline produces zero live output in production.

**Fix**: Replace `"claude-opus-4-20250514"` with `"claude-opus-4-7"` in the three prediction files; update `ensemble.py:89` docstring.

---

### [MEDIUM] Staleness Penalty Not Applied to `probability` — *Open*

`ensemble_predict()` (`prediction/ensemble.py:156–169`) scales `confidence` by `penalty_factor` when context is stale but leaves `probability` unchanged. The crisis context was last refreshed ~2026-04-12 (41 days ago), making `penalty_factor` near 0.0. `confidence` is zeroed while `probability` continues to drive divergence detection and trade signals at full strength.

**Fix**: Apply penalty to probability in `ensemble.py:166`:
```python
adjusted_probability = 0.5 + (ensemble_result["probability"] - 0.5) * penalty_factor
```

---

### [MEDIUM] Calibration Predicate Mismatch in `recalibration.py` — *Open*

`recalibrate_probability()` (`scoring/recalibration.py:71`) counts eligible signals with `WHERE model_id = ? AND model_was_correct IS NOT NULL`, but `calibration_curve()` requires `resolution_price IS NOT NULL`. Fixtures that set `model_was_correct` without `resolution_price` pass the gate (≥10 signals) but produce an empty curve — recalibration silently no-ops.

**Fix**: Add `AND resolution_price IS NOT NULL` to the count query at `recalibration.py:71`.

---

### [MEDIUM] Within-Batch Duplicate Bug in `crisis_ingester.py` — *Partially Mitigated*

`CrisisIngester.ingest_events()` (`ingestion/crisis_ingester.py:52–97`): `existing_hashes` is queried from DB before the loop but never updated inside it. The fuzzy headline check (updated after each insert) catches same-title events at similarity ≥ 0.85, covering the identical-hash case in practice. Risk remains for events with the same hash but different text below the 0.85 fuzzy threshold.

**Fix**: Add `existing_hashes.add(headline_hash)` after `inserted += 1` at line 96.

---

### [MEDIUM] Missing Migration for `crisis_events.headline_hash` — *Open*

`headline_hash TEXT` appears in the `CREATE TABLE` DDL (`db/schema.py:491`) but there is no `_add_column_if_missing(conn, "crisis_events", "headline_hash", "TEXT")` call in `_migrate_legacy_tables()`. Databases created before this column was added fail on upgrade.

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

Risk is low while the CLI runs single-threaded; becomes a concurrency hazard if `/api/brief/run` and parallel API requests trigger writes simultaneously.

**Fix**: Wire `DbWriter.enqueue()` at each write site, or add `# SINGLE_PROCESS_ONLY` annotations and a startup concurrency guard in `main.py`.

---

### [LOW] Unpinned Core Dependencies — *Open*

`pyproject.toml` specifies only floor versions. Today's install carries `starlette 1.0.1` (major version), `fastapi 0.136.1`, and `anthropic 0.104.1`. An unreviewed major version of starlette could introduce breaking changes without notice.

**Fix**: Pin upper bounds on `fastapi`, `starlette`, and `anthropic` (e.g., `fastapi>=0.115,<0.137`) until each major upgrade is explicitly reviewed.

---

### [LOW] `backtest/engine.py` and `backtest/runner.py` Have No Test Coverage — *Open*

The `backtest/` module (`engine.py`, `runner.py`) has no tests. `LookAheadGuard` is well-tested (12 passing). `BacktestRunner` and `BacktestEngine` are untested.

**Fix**: Add `test_backtest_engine.py` and `test_backtest_runner.py` covering happy-path simulation and date-boundary logic.

---

### [LOW] Spec/Architecture Divergence — *Informational*

The Phase 1 design spec describes a 50-agent LLM swarm with H3 hex visualization, WebSocket streaming, and GDELT-driven cascade simulation. The implemented codebase is a prediction market edge-finder (3 Claude prediction models, Kalshi/Polymarket API integration, paper trading). This divergence is intentional per `CLAUDE.md`.

The spec modules never implemented include: `agents/`, `spatial/`, `eval/`, `api/routes.py`, `api/websocket.py`, `api/auth.py`, `simulation/engine.py`, `simulation/circuit_breaker.py`. The plan-specified test files `test_agent_schemas.py`, `test_agent_router.py`, `test_agent_runner.py`, `test_h3_utils.py`, `test_dedup.py`, `test_gdelt_filter.py`, `test_circuit_breaker.py`, `test_integration.py`, `test_auth.py`, `test_prompt_versioning.py` are also absent (the implemented codebase has equivalent tests for its actual architecture).

---

## Positive Findings

- **416/446 tests pass** — stable for 38 consecutive days
- `anthropic` 0.104.1 (micro bump) — no regressions
- FastAPI 0.136.1 + Starlette 1.0.1 — all 20 dashboard endpoint tests pass
- `LookAheadGuard` (backtest) is well-architected; all 12 tests pass
- Kalshi RSA-PSS auth, `yes_bid_dollars` field naming, demo/production split are correct
- `AsyncAnthropic` client used consistently — no accidental sync instantiations
- Migration system (`_add_column_if_missing`) provides safe schema evolution
- No secrets in repo — `.env.example` uses placeholder values only
- `requires-python = ">=3.11"` (was `>=3.12` in original spec) — acceptable relaxation

---

## Recommendations — Priority Order

1. **`pytz`** — `"pytz>=2024.1"` in `pyproject.toml`. One-line fix. Unblocks 17 tests. **38 days unactioned.**
2. **Model ID** — Replace `"claude-opus-4-20250514"` with `"claude-opus-4-7"` in `oil_price.py`, `ceasefire.py`, `hormuz.py`; update `ensemble.py:89`. Live predictions are broken. **25 days unactioned.**
3. **Staleness → probability** — Apply `penalty_factor` to `probability` in `ensemble.py` so stale context attenuates signals, not just confidence metadata.
4. **Calibration predicate** — Add `AND resolution_price IS NOT NULL` to `recalibration.py:71`.
5. **`headline_hash` migration** — `_add_column_if_missing(conn, "crisis_events", "headline_hash", "TEXT")` in `_migrate_legacy_tables()`.
6. **Within-batch dedup** — `existing_hashes.add(headline_hash)` after each insert in `crisis_ingester.py`.
7. **Pin dependencies** — Add upper bounds on `fastapi`, `starlette`, `anthropic`.
8. **Single-writer annotation** — Wire `DbWriter` to all write sites or add `# SINGLE_PROCESS_ONLY` guards.
9. **Backtest coverage** — Add `test_backtest_engine.py` and `test_backtest_runner.py`.
