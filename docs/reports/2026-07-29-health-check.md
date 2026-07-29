# Parallax Health Check — 2026-07-29

**Status: YELLOW**

## Summary

The implemented codebase has diverged significantly from the Phase 1 design spec — the agent swarm (`agents/`), eval framework (`eval/`), and API sub-package (`api/`) are entirely absent, replaced by a prediction-market edge-finder architecture (Kalshi/Polymarket integration, signal ledger, paper trading) that post-dates the original spec. This architectural pivot appears intentional and the market-focused code is functionally solid. However, two actionable bugs and one systemic architectural issue require attention: the `DbWriter` single-writer queue is implemented but never wired into the application, a cost-tracking bug in `ensemble.py` always records `"opus"` pricing regardless of the actual model used, and `app.state` predictions/markets/divergences endpoints always return empty lists in the production cron deployment pattern.

---

## Issues Found

### [HIGH] `DbWriter` is dead code — single-writer invariant not enforced

- **File:** `backend/src/parallax/db/writer.py`
- `DbWriter` exists and has tests, but is never imported by any application module. All 14+ modules (including `scoring/ledger.py`, `scoring/tracker.py`, `budget/tracker.py`, `ops/alerts.py`, `cli/brief.py`, `contracts/registry.py`, `backtest/runner.py`, etc.) write to DuckDB via direct synchronous `conn.execute()` calls.
- **Risk:** Concurrent FastAPI requests and background tasks share a single DuckDB connection with no serialization. Under any real load this will produce write-write conflicts or "database is locked" errors.
- **Recommendation:** Wire `DbWriter` through `main.py` lifespan and convert all write-producing modules to use `writer.enqueue()` — or, if the codebase is effectively single-threaded due to the CLI-only deployment pattern, document that explicitly.

### [HIGH] `ensemble.py` line 128 — hardcoded `"opus"` in budget recording

- **File:** `backend/src/parallax/prediction/ensemble.py`, line 128
- ```python
  budget.record(resp.usage.input_tokens, resp.usage.output_tokens, "opus")
  ```
- `ensemble_predict()` accepts a `model` parameter (Haiku or Sonnet are the typical callers), but `"opus"` is hardcoded in the budget record call. Opus pricing is 15× Haiku and 3× Sonnet, so every call is over-counted in `BudgetTracker`, triggering false `is_over_budget()` responses that degrade the system to rule-based-only mode prematurely.
- **Recommendation:** Replace with `budget.record(..., model)` using the `model` parameter already in scope.

### [MEDIUM] API `/api/predictions`, `/api/markets`, `/api/divergences` always return `[]` in production

- **File:** `backend/src/parallax/main.py`, lines 43–45
- `app.state.last_predictions/markets/divergences` are set only when `POST /api/brief/run` is called through the HTTP API. The production cron (`python -m parallax.cli.brief`) invokes `run_brief()` directly and never updates `app.state`, so the dashboard endpoints always serve empty lists.
- **Recommendation:** Either (a) write brief output to a DB table and have the endpoints query it, or (b) document that `/api/brief/run` must be used instead of the CLI if the API is expected to serve live data.

### [MEDIUM] Blocking synchronous DB writes inside `async` functions

- **Files:** `ops/alerts.py` line 106 (`DuckDBAlertSink.send` is `async` but calls `conn.execute()` synchronously), `budget/tracker.py` line 43 (`record()` is sync and called from async `brief.py` paths)
- This blocks the FastAPI event loop on every alert/budget write, introducing latency spikes under load.
- **Recommendation:** Wrap with `asyncio.to_thread()` or route through `DbWriter` once it's wired in.

### [LOW] Architecture drift — `agents/`, `eval/`, `api/` packages not implemented

- The Phase 1 design spec called for a 50-agent LLM swarm (`agents/`), structured eval framework (`eval/`), and a split API sub-package (`api/routes.py`, `api/websocket.py`, `api/auth.py`). None of these exist.
- The actual implementation took a different, more practical direction: focused prediction models (oil price, ceasefire, Hormuz) + Kalshi/Polymarket market comparison. This is a coherent pivot from simulation to edge-finding.
- **Recommendation:** Update the spec to reflect the actual architecture, or document the divergence decision in a design record. The current implementation is not broken — it just doesn't match the spec.

### [LOW] `portfolio/` and `config/` directories missing `__init__.py`

- **Files:** `backend/src/parallax/portfolio/`, `backend/src/parallax/config/`
- Neither directory has `__init__.py`, so they are not proper Python packages. This currently works with hatchling's auto-discovery but may cause issues with some tooling.
- **Recommendation:** Add empty `__init__.py` to both.

### [LOW] `db/runtime.py` — filesystem side effect on every call

- **File:** `backend/src/parallax/db/runtime.py`, line 27
- `resolve_runtime_config()` calls `mkdir(parents=True, exist_ok=True)` unconditionally, including from tests using in-memory DuckDB. Harmless but pollutes the working directory during test runs.

### [INFO] Test coverage: 50 tests present, focused on the market-edge-finder architecture

- Tests for `budget/tracker.py`, `ops/alerts.py`, `api/auth.py`, and frontend are absent.
- `test_integration.py` from the plan is missing — no end-to-end test covers the full brief → divergence → signal flow.
- The 50 existing tests are well-targeted to the actual codebase (scorecard, calibration, ledger, ensemble, cascade, etc.).

---

## Recommendations (Priority Order)

1. **Fix ensemble.py line 128** — one-line change, eliminates false budget exhaustion signals. `"opus"` → `model`.
2. **Decide on DbWriter fate** — either wire it in or remove it and document the chosen concurrency model.
3. **Fix the API state staleness** — prediction/market endpoints should read from DB, not in-memory lists.
4. **Add `__init__.py`** to `portfolio/` and `config/` directories.
5. **Reconcile spec with implementation** — update `docs/superpowers/specs/2026-03-30-parallax-phase1-design.md` to reflect the edge-finder pivot, or create a Phase 2 spec that describes the current architecture.
