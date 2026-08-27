# Parallax Health Check — 2026-08-27

**Status: YELLOW**

## Summary

The core test suite passes cleanly (433 passed, 13 skipped) but four test files fail to collect due to `bench` optional dependencies (`numpy`, `pandas`, `sklearn`) not being installed in the default `dev` environment. The codebase has intentionally pivoted far from the Phase 1 spec — from a geopolitical cascade simulator with H3 hex visualization and a ~50-agent LLM swarm to a focused prediction-market edge-finder — which is architecturally sound but leaves large spec sections unimplemented. Three DuckDB single-writer violations exist where code bypasses the `asyncio.Queue` pattern and writes directly to the connection.

---

## Issues Found

### HIGH — DuckDB Single-Writer Violations

The spec mandates all writes go through the `DbWriter` `asyncio.Queue`. Three modules break this contract and write directly, risking `database is locked` errors under concurrent async load:

- **`[HIGH]`** `budget/tracker.py:43` — `self._db_conn.execute(INSERT INTO llm_usage …)` — writes directly on every LLM call. Under high-frequency runs this fires from multiple async tasks simultaneously.
- **`[HIGH]`** `contracts/registry.py:105, 114, 198` — `self._conn.execute(INSERT/UPDATE …)` — registry mutation methods write directly.
- **`[HIGH]`** `ingestion/crisis_ingester.py:79` — `self._conn.execute(INSERT INTO crisis_events …)` — ingestion writes directly rather than enqueueing.

### MEDIUM — 4 Test Collection Failures (Missing `bench` deps)

`test_bench_forecast.py`, `test_calibration_metrics.py`, `test_recalibrators.py`, and `test_selective.py` all fail at import with `ModuleNotFoundError` for `pandas`, `numpy`, or `sklearn`. These modules are gated under `[bench]` extras but the tests are in the main `tests/` directory and collected unconditionally by `pytest`. Running `pip install -e "."` or `pip install -e ".[dev]"` (the documented install command) breaks the suite.

**Fix options:** move bench tests to a subdirectory excluded by default, add `pytest.importorskip` guards, or add `numpy`/`pandas` to `[dev]` deps.

### MEDIUM — Architecture Drift from Phase 1 Spec (Intentional Pivot)

The implementation has substantially departed from the spec. Noting for documentation purposes — not bugs, but unimplemented spec sections:

- **Missing entire subsystems:** `agents/` (50-agent swarm), `eval/` (prediction eval framework), `spatial/` (H3 utilities, Searoute), `api/` (WebSocket + auth middleware)
- **Missing simulation components:** `simulation/circuit_breaker.py`, `simulation/engine.py` (DES core)
- **Frontend pivot:** Spec required `deck.gl` + `H3HexagonLayer` hex map with WebSocket streaming. Actual frontend is a Recharts polling dashboard — no map, no WebSocket, no deck.gl
- **GDELT source renamed:** Spec expects `ingestion/gdelt.py`; actual file is `ingestion/gdelt_doc.py` (Google News RSS is primary source instead of BigQuery)

### LOW — Python Version Mismatch

`pyproject.toml` specifies `requires-python = ">=3.11"` but the spec and `CLAUDE.md` both state Python 3.12. The runtime appears to use 3.11 (`/usr/lib/python3.11`). This is consistent with the actual runtime but diverges from spec intent.

### LOW — Missing Spec-Required Dependencies

Several spec-required packages are absent from `pyproject.toml`:
- `h3>=4.1` — removed (no spatial layer)
- `searoute>=1.3` — removed (no route visualization)
- `shapely>=2.0` — removed
- `sentence-transformers>=3.4` — removed (semantic dedup not implemented)
- `google-cloud-bigquery>=3.27` — removed (GDELT BigQuery not used; DOC API used instead)
- Frontend: `deck.gl`, `maplibre-gl`, `react-map-gl`, `h3-js` — absent; `recharts` replaces them

These are consistent with the product pivot and not bugs, but the spec document is now stale.

### LOW — `BudgetTracker` Pricing Comment Drift

`budget/tracker.py` comment says "Haiku ~$0.005/call, Sonnet ~$0.031/call" but the `_PRICING` dict uses `haiku.input=$0.001/1K` and `sonnet.input=$0.003/1K` — per-call estimates in the comment don't align with the per-token rates in code. Minor documentation inconsistency.

---

## Recommendations

1. **Fix DuckDB writer violations (HIGH, immediate).** Refactor `BudgetTracker`, `ContractRegistry`, and `CrisisIngester` to accept a `DbWriter` and call `await writer.enqueue(...)` instead of calling `conn.execute()` directly. This is the highest-risk issue under concurrent async operation.

2. **Fix bench test collection (MEDIUM).** Add `import pytest; pytest.importorskip("numpy")` at the top of the four failing bench test files. This converts collection errors to skips and restores a clean `pytest` run without requiring `[bench]` extras.

3. **Update the Phase 1 spec or create a Phase 1B spec (LOW).** The product has pivoted successfully to a prediction market edge-finder. The original Phase 1 design doc no longer describes the running system. Consider either archiving the old spec or writing a brief update that documents the actual architecture (3 LLM predictors, Kalshi/Polymarket API, divergence detector, paper trading, DuckDB scoring layer).

4. **Resolve Python version target (LOW).** Decide between 3.11 (runtime) and 3.12 (spec). If 3.11 is intentional, update `CLAUDE.md`; if 3.12 is required, update the Dockerfile/environment.
