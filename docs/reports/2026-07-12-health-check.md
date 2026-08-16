# Parallax Health Check — 2026-07-12

**Status: YELLOW**

## Summary

The codebase is healthy and well-tested (433/433 tests passing), but has drifted significantly from the original Phase 1 design spec — a pivot from a geopolitical cascade simulator to a prediction-market edge-finder that appears intentional and is reflected in CLAUDE.md. The most actionable issue is that `DbWriter` (the spec-mandated asyncio.Queue single-writer) is completely dead code: all 62+ DuckDB writes across the scoring modules bypass it and call `conn.execute()` directly. This is safe today under asyncio's single-threaded model but creates a latent `database is locked` risk if any concurrent write path is ever added.

---

## Issues Found

### HIGH

- **`DbWriter` is dead code — single-writer pattern not enforced** (`db/writer.py`)
  The spec (Section 9, "Single-Writer Topology") mandates all writes go through `asyncio.Queue → db_writer`. `DbWriter` is defined and has a passing test (`test_writer.py`) but is never imported or called from any production module. All 62+ writes in `scoring/ledger.py`, `scoring/tracker.py`, `scoring/scorecard.py`, `scoring/prediction_log.py`, `scoring/resolution.py`, `budget/tracker.py`, and others call `conn.execute()` directly. Under asyncio this is safe today, but a single added `await` between competing writes could produce a `database is locked` error that is very hard to reproduce and diagnose.
  **Recommendation:** Either wire `DbWriter` into the async write paths (correct fix) or document a deliberate decision to rely on asyncio single-threading and remove the dead class.

### MEDIUM

- **4 test files fail to collect due to missing `numpy`** (`test_bench_forecast.py`, `test_calibration_metrics.py`, `test_recalibrators.py`, `test_selective.py`)
  These modules import `numpy`/`pandas`/`scikit-learn`, which live only under the `[bench]` optional extras group. Running `pytest tests/` in the default environment silently skips these 4 files with collection errors rather than failures — so CI passes but these tests never run.
  **Recommendation:** Move `numpy` to base dependencies, or guard the imports with `pytest.importorskip("numpy")` in the test files.

- **`httpx` / `httpx2` deprecation warning in all test runs**
  FastAPI's `TestClient` imports from `starlette.testclient`, which warns: *"Using `httpx` with `starlette.testclient` is deprecated; install `httpx2` instead."* Not a bug today, but `httpx` is likely to break on a future FastAPI or Starlette upgrade.
  **Recommendation:** Pin `pytest-httpx>=0.35,<0.36` (already done) and track the httpx2 migration in a follow-up.

### LOW

- **Architecture pivot: agents/, eval/, api/ directories never built**
  The Phase 1 plan called for `parallax/agents/` (~50 LLM agents), `parallax/eval/` (prediction eval framework), and `parallax/api/` (separate route modules). None exist. The project pivoted from a cascade simulator to a prediction-market edge-finder; the scoring/, prediction/, and contracts/ modules implement equivalent functionality under the new design. This is intentional but the plan is now stale.
  **Recommendation:** Archive or update `docs/superpowers/plans/2026-03-30-parallax-phase1.md` to reflect the actual architecture.

- **`ingestion/dedup.py` missing — only structural dedup is active**
  The spec's 4-stage GDELT filter (Section 6) requires semantic dedup via `sentence-transformers` (`all-MiniLM-L6-v2`, cosine similarity > 0.85). The current `crisis_ingester.py` deduplicates only by `headline_hash` (MD5 of the headline string). Near-duplicate headlines from different sources pass through.
  **Recommendation:** Low priority given the project's current focus on Google News RSS + GDELT DOC as news sources rather than raw GDELT BigQuery. Flag for re-evaluation if ingestion volume or noise increases.

- **Frontend pivoted from deck.gl / H3 hex map to recharts dashboard**
  Plan called for a 3-panel deck.gl + MapLibre GL spatial visualization with WebSocket updates and 4 H3HexagonLayer instances. The actual frontend is a polling-based React dashboard using `recharts` for charts, with no map, no WebSocket, and no H3 spatial layer. `deck.gl`, `maplibre-gl`, `react-map-gl`, and `h3-js` are absent from `package.json`. This is clearly intentional.
  **Recommendation:** No action required; document in CLAUDE.md that the spatial visualization layer is deferred.

- **11 plan-specified test files never created** (e.g., `test_gdelt_filter.py`, `test_agent_schemas.py`, `test_budget_tracker.py`, `test_integration.py`)
  The implementation pivoted so the corresponding modules don't exist, except `budget/tracker.py` which is fully implemented but has zero test coverage.
  **Recommendation:** Add `test_budget_tracker.py` — it's the only gap against code that actually exists and is used in production paths.

- **`h3`, `searoute`, `shapely`, `sentence-transformers`, `google-cloud-bigquery` removed from dependencies**
  All were in the Phase 1 plan's `pyproject.toml`. None are in the current one. The spatial simulation layer (H3 routing, Overture Maps, GDELT BigQuery) was not built. Consistent with the pivot.

---

## Recommendations

| Priority | Action |
|----------|--------|
| 1 (HIGH) | Audit all async write paths for `conn.execute()` calls and either route through `DbWriter` or document the decision to rely on asyncio single-threading and delete the dead class |
| 2 (MED) | Fix the numpy collection error: add `pytest.importorskip("numpy")` guards to the 4 affected test files |
| 3 (LOW) | Add `test_budget_tracker.py` — only gap between existing code and test coverage |
| 4 (LOW) | Update the Phase 1 plan doc to reflect the actual prediction-market architecture |

---

## Test Suite Snapshot

| Metric | Value |
|--------|-------|
| Tests collected | 446 (4 collection errors — numpy) |
| Tests passing (exc. numpy files) | 433 |
| Tests skipped | 13 |
| Tests failing | 0 |
| Collection errors | 4 (`test_bench_forecast`, `test_calibration_metrics`, `test_recalibrators`, `test_selective`) |
