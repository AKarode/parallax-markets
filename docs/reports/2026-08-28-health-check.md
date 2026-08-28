# Parallax Health Check — 2026-08-28

**Status: YELLOW**

## Summary

The codebase continues to function as a prediction-market edge-finder (diverged from the original Phase 1 geopolitical cascade simulator spec, but intentionally so). The single-writer DuckDB violations flagged yesterday remain unaddressed and have grown in scope — the full audit found 10+ modules bypassing `DbWriter`, including 5 separate `duckdb.connect()` calls in `cli/brief.py`. The `DbWriter` implementation is correct but effectively unused by all production write paths. No new regressions detected since yesterday's check.

---

## Issues Found

### HIGH — DuckDB Single-Writer Violations (Broader Than Yesterday's Report)

Full audit reveals the problem is more pervasive than the 3 files flagged on 2026-08-27. The `DbWriter` asyncio queue is implemented in `db/writer.py` but bypassed by every production write path:

- **`[HIGH]`** `scoring/ledger.py:225,256` — `self._conn.execute(INSERT/UPDATE …)` — signal ledger writes directly on every signal record and trade execution update.
- **`[HIGH]`** `scoring/tracker.py:460,516,672,711,744,770` — 6 direct write calls across paper trade tracking.
- **`[HIGH]`** `scoring/scorecard.py:21` — direct INSERT for daily scorecard ETL.
- **`[HIGH]`** `scoring/resolution.py:60,124` — direct UPDATEs during settlement polling.
- **`[HIGH]`** `scoring/prediction_log.py:79` — direct INSERT for prediction persistence.
- **`[HIGH]`** `contracts/registry.py:85,105,114,198` — direct INSERT/UPDATEs for contract upserts.
- **`[HIGH]`** `budget/tracker.py:43` — direct INSERT on every LLM call (high frequency).
- **`[HIGH]`** `ingestion/crisis_ingester.py:79` — direct INSERT during ingestion.
- **`[HIGH]`** `ops/alerts.py:106` — direct INSERT for alert logging.
- **`[HIGH]`** `cli/brief.py:535,786,817,827,837` — 5 separate `duckdb.connect()` calls opening independent connections to the same file. This is the most dangerous pattern: multiple writers to the same DuckDB file will produce `database is locked` errors under concurrent access.

Any async workload that interleaves two of these code paths risks corruption or lock errors. The risk is latent while `brief.py` runs sequentially in CLI mode, but real under FastAPI async handlers or if the CLI is ever run concurrently.

### MEDIUM — 4 Test Collection Failures (Bench Dependencies)

Unchanged from yesterday. `test_bench_forecast.py`, `test_calibration_metrics.py`, `test_recalibrators.py`, and `test_selective.py` fail at import with `ModuleNotFoundError` for `pandas`, `numpy`, or `sklearn`. Running the documented `pip install -e ".[dev]"` command breaks suite collection.

**Fix:** Add `pytest.importorskip("pandas")` guards or move bench tests to a `tests/bench/` subdirectory excluded by the default `pytest` config.

### MEDIUM — Architecture Drift from Phase 1 Spec (Intentional Pivot, Spec Now Stale)

Large portions of the spec describe systems that were not built and are not planned:

| Spec Component | Status |
|---|---|
| `agents/` — 50-agent LLM swarm with country→sub-actor hierarchy | Not built |
| `eval/` — prediction eval framework with direction/magnitude/calibration scoring | Not built |
| `spatial/` — H3 utilities, Searoute route visualization | Not built |
| `api/` — structured WebSocket handler + auth middleware | Not built; routes inline in `main.py` |
| `simulation/engine.py` — DES core with heapq priority queue | Not built |
| `simulation/circuit_breaker.py` — escalation limiter | Not built |
| `ingestion/dedup.py` — semantic deduplication via sentence-transformers | Not built |
| Frontend H3 hex map (deck.gl + MapLibre) | Not built; Recharts polling dashboard instead |
| WebSocket streaming (`useWebSocket.ts`) | Not built; `usePolling.ts` used instead |

What _was_ built is coherent and functional as a different product: ingestion → 3 LLM prediction models → Kalshi/Polymarket market comparison → divergence signals → paper trading. The spec document should be updated or superseded to reflect the actual product direction.

### LOW — Missing `websockets` Dependency

The backend has no `websockets` or equivalent (e.g., `python-socketio`) in `pyproject.toml`. The frontend has no WebSocket client library. If WebSocket streaming is ever reinstated, both need new deps.

### LOW — Python Version Mismatch

`pyproject.toml` sets `requires-python = ">=3.11"` while the spec and `CLAUDE.md` specify Python 3.12. Consistent with the actual runtime environment, but diverges from documented intent.

### LOW — Frontend Dependency Footprint Sparse vs. Spec

`frontend/package.json` does not include `deck.gl`, `maplibre-gl`, `react-map-gl`, or `h3-js`. These are consistent with the product pivot but confirm the spec is stale. Current frontend deps: React 18.3.1, Recharts 2.15, Vite 6, TypeScript 5.6.

---

## Recommendations

1. **Fix single-writer violations (HIGH, carry-forward from yesterday).** Refactor all 10+ write sites to use `DbWriter.enqueue()`. Priority order: `cli/brief.py` (5 separate connections — highest risk), then `scoring/ledger.py` and `scoring/tracker.py` (highest write frequency in production). The `DbWriter` class is already implemented correctly — this is a wiring problem, not a design problem.

2. **Fix bench test collection failures (MEDIUM).** Add `pytest.importorskip` guards to the 4 bench test files so `pytest` (without bench extras) doesn't fail to collect them.

3. **Update or supersede the spec document (LOW).** `docs/superpowers/specs/2026-03-30-parallax-phase1-design.md` describes a product that no longer matches the codebase. Update it to reflect the actual architecture or add an ADR documenting the pivot.
