# Parallax Health Check — 2026-08-30

**Status: YELLOW**

## Summary

No code changes landed since yesterday's check (only a tech-research doc was committed). All issues from 2026-08-29 carry forward unchanged for a fourth consecutive day: the DuckDB single-writer violations remain the primary structural risk, the 4 bench test collection failures are still unguarded, and the Phase 1 spec continues to describe a product that no longer exists. Core test suite holds at 433 passed, 13 skipped — clean when bench extras are excluded. No new regressions detected.

---

## Issues Found

### HIGH — DuckDB Single-Writer Violations (Unaddressed, Day 4)

`DbWriter` in `db/writer.py` is correctly implemented but bypassed by every production write path. The violations flagged on 2026-08-28 are confirmed unchanged today:

- **`[HIGH]`** `cli/brief.py:535,786,817,827,837` — 5 separate `duckdb.connect()` calls opening independent connections to the same file. Under concurrent access (FastAPI async, parallel CLI runs) this produces `database is locked` errors.
- **`[HIGH]`** `scoring/ledger.py:225,256` — direct INSERT/UPDATE on every signal record.
- **`[HIGH]`** `scoring/tracker.py:460,516,672,711,744,770` — 6 direct writes across paper trade lifecycle.
- **`[HIGH]`** `scoring/scorecard.py:21` — direct INSERT for daily scorecard ETL.
- **`[HIGH]`** `scoring/resolution.py:60,124` — direct UPDATEs during settlement polling.
- **`[HIGH]`** `scoring/prediction_log.py:79` — direct INSERT for prediction persistence.
- **`[HIGH]`** `contracts/registry.py:85,105,114,198` — direct INSERT/UPDATEs for contract upserts.
- **`[HIGH]`** `budget/tracker.py:43` — direct INSERT on every LLM call (highest frequency).
- **`[HIGH]`** `ingestion/crisis_ingester.py:79` — direct INSERT during ingestion.
- **`[HIGH]`** `ops/alerts.py:106` — direct INSERT for alert logging.

Risk is latent in sequential CLI mode but real under FastAPI async handlers or concurrent invocations.

### MEDIUM — 4 Test Collection Failures (Bench Dependencies, Unaddressed, Day 4)

`test_bench_forecast.py`, `test_calibration_metrics.py`, `test_recalibrators.py`, and `test_selective.py` fail at collection with `ModuleNotFoundError: No module named 'pandas'` / `numpy`. The bench extras are not installed by `pip install -e ".[dev]"`.

**Fix:** Add `pytest.importorskip("numpy")` as the first import guard in each file, or move bench tests to `tests/bench/` and exclude the directory from the default pytest config.

### MEDIUM — Architecture Drift from Phase 1 Spec (Intentional Pivot, Spec Stale)

`docs/superpowers/specs/2026-03-30-parallax-phase1-design.md` describes systems that were not built and are not planned. The spec remains stale for the fourth consecutive week.

| Spec Component | Status |
|---|---|
| `agents/` — 50-agent LLM swarm | Not built |
| `eval/` — prediction eval framework | Not built |
| `spatial/` — H3 / Searoute visualization | Not built |
| `simulation/engine.py` — DES core | Not built |
| Frontend H3 hex map (deck.gl + MapLibre) | Not built; Recharts polling dashboard used instead |
| WebSocket streaming | Not built; `usePolling.ts` used instead |

The actual codebase (ingestion → 3 LLM models → Kalshi/Polymarket comparison → signals → paper trading) is coherent and functional as a different product.

### LOW — Dependency Version Drift

Installed versions diverge from `pyproject.toml` lower bounds, all in the "newer than required" direction — no immediate risk, but worth pinning:

| Package | Spec Requires | Installed |
|---|---|---|
| `duckdb` | `>=1.2` | `1.5.5` |
| `fastapi` | `>=0.115` | `0.141.1` |
| `anthropic` | `>=0.52` | `1.2.0` |

The `anthropic` SDK moved from 0.x to 1.x (breaking changes in that transition). The codebase uses `AsyncAnthropic`, `NOT_GIVEN`, and `anthropic.types` — all confirmed importable at 1.2.0. Tests pass. No action required today, but the lower bound of `>=0.52` should be updated to `>=1.0` to reflect the actual minimum compatible version.

### LOW — Python Version Mismatch

`pyproject.toml` specifies `requires-python = ">=3.11"` while `CLAUDE.md` documents Python 3.12. Actual runtime is Python 3.11. No functional impact but creates documentation confusion.

### LOW — Missing `websockets` Dependency

`pyproject.toml` does not list `websockets`. Frontend has no WebSocket client. Harmless while the polling architecture is in use, but blocks any future real-time stream work.

---

## Recommendations

1. **Fix DuckDB single-writer violations (HIGH, priority order).**
   1. `cli/brief.py` — 5 independent `duckdb.connect()` calls are the highest-risk pattern. Consolidate to one shared connection passed through, or use `DbWriter.enqueue()`.
   2. `scoring/ledger.py` + `scoring/tracker.py` — highest write frequency in production; route through `DbWriter.enqueue()`.
   3. Remaining modules — same fix; low frequency but complete correctness requires all writes through the queue.

2. **Fix bench test collection failures (MEDIUM).** Add `pytest.importorskip("numpy")` at the top of each affected file. Three-line fix, unblocks clean `pytest` runs.

3. **Update the anthropic SDK lower bound (LOW).** Change `anthropic>=0.52` to `anthropic>=1.0` in `pyproject.toml` to reflect the actual minimum-compatible version used in production.

4. **Update or supersede the Phase 1 spec (LOW).** The spec has been stale since April. Either rewrite it to describe the actual prediction-market product, or add an ADR documenting the pivot so the document is no longer misleading.
