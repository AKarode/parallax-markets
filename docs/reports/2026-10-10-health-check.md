# Parallax Health Check — 2026-10-10

**Status: YELLOW**

The codebase remains functional as a prediction-market edge-finder (Kalshi/Polymarket signal pipeline) with 46 test files and solid scoring/calibration infrastructure. No code changes were committed since yesterday's report — all findings from 2026-10-09 carry forward unchanged. The DuckDB single-writer violation remains the highest-priority unresolved risk.

---

## Issues Found

### CRITICAL

- **[CRITICAL] DuckDB single-writer constraint violated across 11 production files — no change since yesterday.**
  The `DbWriter` asyncio.Queue pattern exists in `db/writer.py` but is bypassed by every actual write path. All write-side modules call `conn.execute()` directly for INSERT/UPDATE/DELETE, creating concurrent async write risk (`database is locked` / silent data corruption) in any multi-coroutine execution context. Confirmed affected files (unchanged from 2026-10-09):
  - `scoring/ledger.py`, `scoring/prediction_log.py`, `scoring/resolution.py`, `scoring/scorecard.py`, `scoring/tracker.py`
  - `ops/alerts.py`
  - `ingestion/crisis_ingester.py`
  - `contracts/registry.py`
  - `cli/brief.py`
  - `budget/tracker.py`
  - `backtest/runner.py`

  No DuckDB write violations were introduced by recent commits (grep of `conn.execute(.*INSERT|UPDATE|DELETE` shows the same 11-file footprint — no new violations).

### HIGH

- **[HIGH] Architecture drift: `agents/`, `eval/`, `api/`, `spatial/` subpackages still absent.**
  The Phase 1 spec's 50-agent LLM swarm, eval framework, H3 spatial model, and WebSocket API remain unbuilt. Tables `agent_memory`, `agent_prompts`, `decisions`, `world_state_delta`, and `eval_results` in the schema continue to hold no data. `simulation/engine.py` and `simulation/circuit_breaker.py` remain absent (cascade and world_state modules exist and pass tests but are wired to no production flow).

- **[HIGH] Dashboard prediction endpoints still silently return empty arrays.**
  `app.state.last_predictions`, `.last_markets`, `.last_divergences` are initialised as `[]` in `main.py` lifespan. No background task updates them on a schedule; only a manual `POST /api/brief/run` triggers a refresh. The React dashboard polls these endpoints and shows stale data on every cold start.

### MEDIUM

- **[MEDIUM] Missing pyproject.toml dependencies.**
  `h3`, `sentence-transformers`, and `websockets` are referenced in the spec/schema but absent from `pyproject.toml`. These are prerequisites for future `spatial/`, `ingestion/dedup.py`, and WebSocket work. Current installs succeed only because these modules are not yet imported by any production code.

- **[MEDIUM] No WebSocket real-time push.**
  Frontend uses `usePolling.ts` only. Neither backend nor frontend has WebSocket infrastructure. Spec components `HexMap.tsx`, `AgentFeed.tsx`, `Timeline.tsx`, and `PredictionCards.tsx` do not exist.

- **[MEDIUM] Test coverage gaps for financially sensitive modules.**
  No dedicated test files exist for:
  - `portfolio/allocator.py` (Kelly position sizing)
  - `prediction/oil_price.py`, `prediction/ceasefire.py`, `prediction/hormuz.py`
  - `backtest/engine.py`, `backtest/report.py`
  - `ops/runtime.py`

### LOW

- **[LOW] Python version mismatch: `pyproject.toml` requires `>=3.11`, CLAUDE.md specifies Python 3.12.**

- **[LOW] `requires-python` vs spec mismatch is low-risk since `str | None` union syntax only requires >=3.10, but should be aligned for consistency.**

---

## Trend

| Date | Status | New Issues | Resolved |
|------|--------|------------|---------|
| 2026-10-08 | RED | DuckDB single-writer violations first identified | — |
| 2026-10-09 | YELLOW | Architecture drift catalogued in detail | None |
| 2026-10-10 | YELLOW | No regressions; no improvements | None |

No new regressions introduced. Status is stable-yellow with two high-priority items unaddressed for 2+ days.

---

## Recommendations

1. **Immediate — Fix DuckDB write serialization.** Either route all writes through `DbWriter.enqueue()` (preferred), or document explicitly that `brief.py` is safe because it runs serially (and remove the misleading `DbWriter` class if unused). This is the only issue that can silently corrupt production data under load.

2. **Short-term — Wire up background brief refresh.** Add an `asyncio.create_task` in the FastAPI lifespan that runs the brief pipeline periodically and writes results into `app.state.last_*`. Until then the dashboard lies on cold start.

3. **Medium-term — Decide on architecture direction.** Spec describes an agent swarm; the built system is a market-signal tool. Either update the spec to match what's been built, or draft a Phase 1b plan to build the missing `agents/`, `eval/`, and `spatial/` packages. Remove or activate the dead simulation code (`cascade.py`, `world_state.py` are tested but called from nowhere).

4. **Add test coverage for prediction models and portfolio allocator** — these are the most financially consequential paths and currently have no unit tests.
