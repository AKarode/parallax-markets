# Parallax Health Check — 2026-09-27

**Status: YELLOW**

## Summary

The core prediction-market pipeline is healthy: 433 tests pass, 13 skipped, 0 failures in the main test suite. However, 4 test files fail to collect due to `numpy` being gated behind the `bench` extra rather than `dev`, and there are widespread DuckDB single-writer violations in production code paths that could surface as `database is locked` errors under concurrent load. The implementation has also substantially diverged from the Phase 1 design spec — a deliberate architectural pivot from a 50-agent geopolitical swarm to a focused 3-model prediction market edge-finder.

---

## Issues Found

### [HIGH] 4 test files fail to collect — numpy missing from `dev` extra
`tests/test_bench_forecast.py`, `tests/test_calibration_metrics.py`, `tests/test_recalibrators.py`, `tests/test_selective.py` all fail with `ModuleNotFoundError: No module named 'numpy'`. These tests live under `tests/` but import `numpy`/`pandas`/`scikit-learn`, which are only in `[bench]` optional dependencies. CI that runs `pip install -e ".[dev]" && pytest` will silently skip collecting these tests or error out, meaning calibration and scoring tests are not exercised in the standard dev workflow.

**Fix:** Move `numpy`, `pandas`, `pyarrow`, `scikit-learn` (or at minimum `numpy`) into `dev` extras, or add a `[dev]` import guard in those test files.

### [HIGH] DuckDB single-writer violations across production modules
Multiple modules write directly to DuckDB outside the `asyncio.Queue` pattern mandated by the spec, creating race conditions when called concurrently from the FastAPI server:

- `backend/src/parallax/scoring/ledger.py:225,256` — direct `INSERT`/`UPDATE`
- `backend/src/parallax/scoring/tracker.py:460,516,672,711,744` — multiple direct writes
- `backend/src/parallax/scoring/prediction_log.py:79` — direct `INSERT`
- `backend/src/parallax/scoring/resolution.py:60,124` — direct writes
- `backend/src/parallax/scoring/scorecard.py:21` — direct write
- `backend/src/parallax/ops/alerts.py:106` — direct write via `DuckDBAlertSink`
- `backend/src/parallax/budget/tracker.py:43` — direct write

The `cli/brief.py` and `backtest/runner.py` direct writes are lower risk (standalone CLI / offline replay), but the `scoring/` and `ops/` writes are called from async API handlers. DuckDB's single-writer constraint means concurrent requests that both trigger writes will race.

**Fix:** Route all writes in `scoring/`, `ops/alerts.py`, and `budget/tracker.py` through `DbWriter.enqueue()`.

### [MEDIUM] Architecture diverged significantly from Phase 1 spec
The Phase 1 spec describes a 50-agent geopolitical swarm with H3 hexagonal grid visualization, WebSocket-based dashboard, GDELT BigQuery ingestion with 4-stage filtering, prompt versioning, and a country→sub-actor hierarchy. The actual implementation is a prediction market edge-finder with 3 Claude models, Google News RSS + GDELT DOC API ingestion, and Kalshi/Polymarket comparison.

Missing spec modules never implemented:
- `agents/` (router, runner, country_agent, prompts/, registry)
- `spatial/` (h3_utils, loader)
- `eval/` (prompt_versioning, improvement, ground_truth)
- `api/websocket.py`, `api/auth.py`

Added modules not in spec (representing the pivot): `backtest/`, `bench/`, `contracts/`, `divergence/`, `markets/`, `portfolio/`, `scoring/`.

This is likely **intentional** — the product pivoted toward a faster validation loop against real markets. The spec should be updated to reflect the current architecture so future health checks can assess accurately.

### [MEDIUM] Missing spec dependencies never added to `pyproject.toml`
The following Phase 1 spec dependencies are referenced in the design but absent from `pyproject.toml`, confirming the pivot is permanent:
- `h3>=4.1`, `sentence-transformers>=3.4`, `searoute>=1.3`, `shapely>=2.0`, `google-cloud-bigquery>=3.27`, `websockets>=14.0`

If H3/spatial features are re-introduced, these will need to be added.

### [LOW] `main.py:35` opens DuckDB directly (acceptable but worth noting)
The FastAPI lifespan opens a raw `duckdb.connect(db_path)` connection and passes it to components. This is fine for read paths (spec allows concurrent readers), but it means writes that bypass `DbWriter` (see HIGH above) will contend on the same file-level lock.

---

## Recommendations

1. **Immediately:** Move `numpy` (and ideally `pandas`) into `[dev]` optional deps so calibration tests run in the standard CI workflow.

2. **Short-term:** Audit the scoring/ops write paths and route them through `DbWriter`. The `brief.py` CLI runs standalone so is lower priority. Focus on `scoring/tracker.py` and `ops/alerts.py` first — they're most likely to be called from concurrent FastAPI handlers.

3. **Medium-term:** Update `docs/superpowers/specs/2026-03-30-parallax-phase1-design.md` (or create a v2 spec) to document the actual prediction-market architecture. The gap between spec and code makes this health check harder to calibrate accurately.

4. **Ongoing:** The 433-test, 13-skipped baseline is healthy. Keep the `--ignore` list in CI narrow — those 4 collection errors should be fixed, not suppressed.
