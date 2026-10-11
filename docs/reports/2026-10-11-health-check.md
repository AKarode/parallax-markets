# Parallax Health Check — 2026-10-11

**Status: YELLOW**

No code changes since yesterday's report (2026-10-10). The prediction-market edge-finder pipeline remains functional with 47 test files and a solid scoring/calibration layer. All findings from 2026-10-10 carry forward. The DuckDB single-writer violation is the standing highest-priority risk.

---

## Issues Found

### CRITICAL

- **[CRITICAL] DuckDB single-writer constraint violated across 11 production files — unchanged for 3 days.**
  The `DbWriter` asyncio.Queue pattern exists in `db/writer.py` but is bypassed by every actual write path. All write-side modules call `conn.execute()` directly for INSERT/UPDATE/DELETE, creating concurrent async write risk (`database is locked` / silent data corruption) in any multi-coroutine execution context. Confirmed affected files (unchanged from 2026-10-09):
  - `scoring/ledger.py`, `scoring/prediction_log.py`, `scoring/resolution.py`, `scoring/scorecard.py`, `scoring/tracker.py`
  - `ops/alerts.py`
  - `ingestion/crisis_ingester.py`
  - `contracts/registry.py`
  - `cli/brief.py`
  - `budget/tracker.py`
  - `backtest/runner.py`

  No new DuckDB write violations introduced (same 11-file footprint — no regressions).

### HIGH

- **[HIGH] Architecture drift: `agents/`, `eval/`, `api/`, `spatial/` subpackages still absent.**
  The Phase 1 spec's 50-agent LLM swarm, eval framework, H3 spatial model, and WebSocket API remain unbuilt. Tables `agent_memory`, `agent_prompts`, `decisions`, `world_state_delta`, and `eval_results` in the schema continue to hold no data. `simulation/engine.py` and `simulation/circuit_breaker.py` remain absent. `cascade.py` and `world_state.py` are tested but wired to no production flow.

- **[HIGH] Dashboard prediction endpoints still silently return empty arrays on cold start.**
  `app.state.last_predictions`, `.last_markets`, `.last_divergences` are initialised as `[]` in `main.py` lifespan. No background task updates them on a schedule; only a manual `POST /api/brief/run` triggers a refresh. The React dashboard shows stale/empty data on every cold start.

### MEDIUM

- **[MEDIUM] Missing pyproject.toml dependencies.**
  `h3`, `sentence-transformers`, and `websockets` are referenced in the spec/schema but absent from `pyproject.toml`. These are prerequisites for future `spatial/`, `ingestion/dedup.py`, and WebSocket work.

- **[MEDIUM] No WebSocket real-time push.**
  Frontend uses `usePolling.ts` only. Neither backend nor frontend has WebSocket infrastructure. Spec components `HexMap.tsx`, `AgentFeed.tsx`, `Timeline.tsx`, and `PredictionCards.tsx` do not exist.

- **[MEDIUM] Test coverage gaps for financially sensitive modules.**
  No dedicated tests for:
  - `portfolio/allocator.py` (Kelly position sizing)
  - `prediction/oil_price.py`, `prediction/ceasefire.py`, `prediction/hormuz.py`
  - `backtest/engine.py`, `backtest/report.py`
  - `ops/runtime.py`

### LOW

- **[LOW] Python version mismatch: `pyproject.toml` requires `>=3.11`, CLAUDE.md specifies Python 3.12.**

- **[LOW] Missing `__init__.py` in `portfolio/` and `config/` directories.**

---

## Trend

| Date | Status | New Issues | Resolved |
|------|--------|------------|---------|
| 2026-10-08 | RED | DuckDB single-writer violations first identified | — |
| 2026-10-09 | YELLOW | Architecture drift catalogued | None |
| 2026-10-10 | YELLOW | No regressions; no improvements | None |
| 2026-10-11 | YELLOW | No regressions; no improvements | None |

Stable-yellow for the third consecutive day. The two high-priority items (DuckDB write serialization, dashboard cold-start staleness) remain unaddressed.

---

## Recommendations

1. **Immediate — Fix DuckDB write serialization.** Route all writes through `DbWriter.enqueue()`, or document explicitly that `brief.py` is safe because it runs serially and remove the misleading unused `DbWriter`. This is the only issue that can silently corrupt production data under load.

2. **Short-term — Wire up background brief refresh.** Add an `asyncio.create_task` in the FastAPI lifespan that runs the brief pipeline on a schedule and writes results into `app.state.last_*`. Until then the dashboard lies on cold start.

3. **Medium-term — Reconcile spec vs. built system.** Either update the Phase 1 spec/plan to reflect the prediction-market pivot, or draft a Phase 1b plan for the missing `agents/`, `eval/`, and `spatial/` packages. Remove or activate the dead simulation code.

4. **Add tests for prediction models and portfolio allocator** — the most financially consequential paths currently have no unit tests.
