# Parallax Health Check — 2026-11-06

**Status: YELLOW**

The codebase is well-tested (491 passing, 13 skipped) and functionally healthy, but has evolved substantially from the Phase 1 spec/plan into a prediction-market edge-finder rather than the full geopolitical swarm simulator originally designed. Two DuckDB single-writer constraint violations are present in production modules.

---

## Summary

The original Phase 1 spec describes a 50-agent geopolitical swarm simulator with H3 spatial visualization and an eval framework. The actual implementation is a leaner, more practical prediction-market comparator: 3 LLM prediction models (oil price, ceasefire, Hormuz) feed divergence signals against Kalshi/Polymarket prices. This pivot is deliberate (as documented in CLAUDE.md) but means the spec and plan no longer reflect the current architecture. The test suite is comprehensive and all existing tests pass.

---

## Issues Found

### HIGH

- **[HIGH] DuckDB single-writer constraint violated — `backtest/runner.py`**
  `BacktestRunner._conn.execute(INSERT/UPDATE ...)` is called directly (lines 290, 308, 329, 356) without routing through the `DbWriter` asyncio queue. If the backtest runs concurrently with the FastAPI server (both writing to the same DuckDB file), `database is locked` errors will occur.

- **[HIGH] DuckDB single-writer constraint violated — `ops/alerts.py`**
  `DuckDBAlertSink.send()` calls `self.db_conn.execute(INSERT ...)` directly (line 106) without the write queue. Alerts fire from async paths that also run alongside the main server writer, risking lock contention.

### MEDIUM

- **[MEDIUM] Architecture diverged from spec — agents/spatial/eval modules not built**
  `backend/src/parallax/agents/`, `spatial/`, and `eval/` modules specified in the Phase 1 plan do not exist. The 50-agent swarm, H3 hex spatial model, prompt versioning pipeline, and 4-stage GDELT semantic dedup are unimplemented. The current code uses 3 prediction models instead. The spec/plan should be updated to reflect the actual architecture to avoid confusion.

- **[MEDIUM] Python version mismatch — `pyproject.toml` says `>=3.11`, spec says 3.12**
  The plan specifies Python 3.12 and the production environment runs Python 3.13. The `requires-python = ">=3.11"` minimum is permissive. Not a bug today, but a small drift to note.

- **[MEDIUM] Missing dependencies from spec — `h3`, `searoute`, `shapely`, `sentence-transformers`, `websockets`, `google-cloud-bigquery`**
  These were required by the Phase 1 plan for spatial indexing and semantic dedup. They are absent from `pyproject.toml`. Again, this reflects the deliberate pivot, but the dependency list should be audited against CLAUDE.md's stated stack rather than the original spec.

### LOW

- **[LOW] Frontend diverged from spec — no H3 hex map or agent feed**
  Frontend implements `KpiBar`, `MarketsTable`, `ModelCards`, `ModelHealth`, `PortfolioPanel` — none of which are in the original spec's layout. The spec's `HexMap`, `AgentFeed`, `Timeline`, `PredictionCards` components were not built. This is consistent with the pivot, but the spec doc is misleading.

- **[LOW] No `websockets` dependency — WebSocket endpoint present in `main.py`**
  `main.py` exports a WebSocket endpoint but `websockets` is not listed in `pyproject.toml`. FastAPI/uvicorn bundles `websockets` via `uvicorn[standard]`, so it works at runtime but is an implicit dependency.

- **[LOW] `ingestion/gdelt.py` renamed to `gdelt_doc.py` — test file `test_gdelt_filter.py` absent**
  The plan calls for `ingestion/gdelt.py` with a volume-gate function. The actual file is `ingestion/gdelt_doc.py` with a different interface. The planned `test_gdelt_filter.py` and `test_dedup.py` tests were never written.

- **[LOW] 13 skipped tests not documented**
  The 13 skipped tests are not annotated with `reason=` strings in several cases. It is unclear whether these are intentionally skipped (e.g., require live API keys) or represent regressions.

---

## Recommendations

1. **Fix single-writer violations** in `backtest/runner.py` and `ops/alerts.py` — route all INSERT/UPDATE calls through the `DbWriter` queue or open a separate read-only connection. This is the highest-priority correctness issue.

2. **Update or archive the Phase 1 spec** — the current `docs/superpowers/specs/2026-03-30-parallax-phase1-design.md` and plan no longer describe the codebase. Write a brief "as-built" architecture note in `docs/` or update CLAUDE.md to avoid confusion in future sessions.

3. **Add `reason=` to skipped tests** — annotate each `@pytest.mark.skip` or `skipIf` with the reason (e.g., `reason="requires ANTHROPIC_API_KEY"`) so health checks can distinguish expected skips from regressions.

4. **Audit frontend WebSocket usage** — if the WebSocket endpoint in `main.py` is actively used by the frontend, add an explicit `websockets` dependency to `pyproject.toml` to avoid silent breakage on a minimal deploy.
