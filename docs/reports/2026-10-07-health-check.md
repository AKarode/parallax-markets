# Parallax Health Check — 2026-10-07

**Status: YELLOW**

The codebase is functional as a prediction-market edge finder and has grown well beyond the original Phase 1 spec (47 test files, rich scoring/calibration subsystem, portfolio simulator, backtest engine). However, one critical architectural constraint from the spec is violated in production code, the original spec's largest subsystems are absent (agent swarm, H3 spatial layer, eval framework), and pyproject.toml is missing several dependencies.

---

## Issues Found

### 🔴 CRITICAL

- **DbWriter single-writer pattern wired nowhere** (`db/writer.py` exists but is dead code). Every module writes directly to DuckDB via raw `.execute()` — `scoring/tracker.py`, `scoring/ledger.py`, `scoring/resolution.py`, `scoring/prediction_log.py`, `contracts/registry.py`, `cli/brief.py`, `budget/tracker.py`, `ops/alerts.py`, `ingestion/crisis_ingester.py`, and `backtest/runner.py` all bypass the queue. The spec explicitly calls this "a hard constraint that shapes the entire backend topology." Under concurrent request load (FastAPI handles requests concurrently) this risks `database is locked` errors and silently dropped writes. `main.py` never creates a `DbWriter` instance or starts the writer task.

### 🟡 HIGH

- **Architecture pivot from spec — major subsystems absent.** The spec describes a geopolitical cascade simulator with an LLM agent swarm and H3 hex map. The actual codebase is a prediction-market edge finder. This is intentional per CLAUDE.md but means these spec modules are entirely absent:
  - `agents/` package (registry, runner, router, schemas, country_agent, prompts/)
  - `eval/` package (predictions, scoring, ground_truth, prompt_versioning, improvement)
  - `spatial/` package (h3_utils, loader)
  - `simulation/engine.py` (DES event queue)
  - `simulation/circuit_breaker.py`
  - `api/` package (auth, websocket) — routes are inline in `main.py`
  - `db/queries.py`
  - `ingestion/dedup.py`

- **No authentication** (`api/auth.py` missing). The spec requires invite-code gating and admin password for the eval dashboard. Currently any caller can hit any endpoint.

- **Missing core dependencies in pyproject.toml** (could break fresh installs):
  - `h3` not listed (H3 was a hard dependency in the spec; `simulation/world_state.py` may reference it)
  - `sentence-transformers` not listed anywhere (dedup module planned in spec never implemented)
  - `websockets` not listed (no WebSocket support; frontend uses REST polling instead)
  - `numpy` only in the `bench` optional group — `scoring/` modules may import it
  - `requires-python = ">=3.11"` but CLAUDE.md specifies Python 3.12+

- **Orphaned schema tables** (schema.py creates them, nothing reads or writes them):
  - `world_state_delta`, `world_state_snapshot` — simulation layer tables with no active writers
  - `agent_memory`, `agent_prompts`, `decisions` — agent swarm tables; agents/ package absent
  - `curated_events`, `raw_gdelt` — GDELT BigQuery pipeline not implemented; actual ingestion uses Google RSS + GDELT DOC API
  - `eval_results` — eval/ package absent

### 🟡 MEDIUM

- **Frontend has diverged significantly from spec.** Spec calls for deck.gl + MapLibre + 4 H3HexagonLayers + WebSocket. Actual frontend uses React + Recharts + REST polling (`usePolling.ts`). No map, no H3 visualization, no WebSocket. This is coherent with the architecture pivot but is a full replacement of the spec's UI layer.

- **`pytest-httpx` version pinned too tightly** (`>=0.35,<0.36`). This will break on Python environments that need a patch release.

- **No frontend tests** — package.json has no test runner configured (no vitest, jest, or playwright). The spec called for a smoke test for WebSocket connection and map rendering.

- **`simulation/circuit_breaker.py` missing** but `simulation/cascade.py` has no escalation guard. If cascade rules are ever called from an async context, there is no rate-limiting on escalation chains.

- **`ingestion/dedup.py` absent** — semantic deduplication of GDELT events (spec stage 3 of 4-stage filter) was never implemented. GDELT events may produce near-duplicate signals.

### 🟢 LOW / INFORMATIONAL

- **`scoring/` module has grown organically and is well-covered** (calibration, recalibration, scorecard, selective, track_record, report_card). 47 test files cover the prediction pipeline reasonably well.
- **`backtest/` and `portfolio/` subsystems are new additions not in spec** — these are positive additions for validating the edge-finding thesis.
- **`bench/` optional group adds NumPy/sklearn** — this is cleanly isolated in an optional dep group.
- **`truthbrush` dependency** (`ingestion/truth_social.py`) fetches Truth Social POTUS feed — not in the original spec, noted as a novel signal source.

---

## Recommendations

1. **Fix DbWriter wiring (critical, ~1 hour):** In `main.py` lifespan, instantiate `DbWriter(conn)` and start `asyncio.create_task(writer.run())`. Store it on `app.state.writer`. Then migrate the top-N highest-concurrency write paths (`scoring/ledger.py`, `scoring/tracker.py`, `cli/brief.py`) to call `await app.state.writer.enqueue(...)`. A full migration across all 11 files can follow incrementally.

2. **Add basic auth to FastAPI (`/api/brief/run`, `/api/scorecard`):** Even a simple `X-Admin-Token` header check using `PARALLAX_ADMIN_PASSWORD` env var would match the spec intent and prevent accidental or malicious trigger of expensive LLM runs.

3. **Add missing deps to pyproject.toml:** At minimum: `numpy` (used by scoring), `websockets` (if WS is added), and verify `h3` is not imported in any current code path.

4. **Document the architecture pivot in the spec.** The spec should reflect the prediction-market-edge-finder design so future health checks do not flag absent simulation/agent layers as regressions.

5. **Prune or migrate orphaned schema tables** (`world_state_delta`, `agent_memory`, `decisions`, etc.) to avoid confusion and schema bloat. Either mark them deprecated in a comment or delete them if the simulation layer is out of scope.
