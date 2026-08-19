# Parallax Health Check — 2026-08-19

**Status: YELLOW**

The codebase is functionally healthy as a v2 prediction market edge-finder. However, the original Phase 1 spec and implementation plan describe a v1 geopolitical simulator that was never fully built — the project pivoted mid-development to a different architecture. Significant documentation drift exists between the spec/plan, CLAUDE.md, pyproject.toml, and the actual codebase. The primary runtime concern is a pervasive DB writer isolation violation across every module.

---

## Issues Found

### [HIGH] DuckDB single-writer pattern is not enforced

- **Severity: HIGH**
- `db/writer.py` implements an `asyncio.Queue`-based `DbWriter` that serializes writes per the spec's single-writer topology requirement.
- In practice, **every non-db module bypasses it entirely**, calling `conn.execute()` directly. Violations confirmed in: `scoring/scorecard.py`, `scoring/tracker.py`, `scoring/ledger.py`, `scoring/resolution.py`, `scoring/prediction_log.py`, `cli/brief.py`, `main.py`, `ops/alerts.py`, `contracts/registry.py`, `ingestion/crisis_ingester.py`, `backtest/runner.py`, `backtest/look_ahead_guard.py`, `budget/tracker.py`, and others.
- The spec warns explicitly: "Separate processes writing to the same DuckDB file will cause `database is locked` errors." Under async concurrent load (multiple FastAPI requests + background tasks), this pattern risks write conflicts or corruption.
- **Recommendation**: Either enforce DbWriter as the sole write path (breaking change), or document that Parallax v2 operates synchronously enough that contention is not observed in practice (acceptable if single-process with GIL-constrained writes).

### [HIGH] Spec/plan are stale — v1 architecture was never built

- **Severity: HIGH** (documentation risk)
- The Phase 1 spec describes a ~50-agent LLM swarm, H3 hexagonal spatial model, WebSocket streaming, and discrete event simulation. None of this was built.
- What was built instead (v2): 3 Claude Sonnet prediction models, Kalshi/Polymarket API clients, divergence detection, paper trading, portfolio simulation, scoring/calibration infrastructure.
- **Missing from plan, never implemented**: `agents/` directory (country_agent, runner, router), `eval/` directory (predictions, scoring, ground_truth, prompt_versioning), `api/` directory (routes, websocket, auth), `spatial/` directory (h3_utils, loader), `simulation/circuit_breaker.py`.
- The frontend replaced the H3 hex map + WebSocket design with a polling-based markets dashboard (no `useWebSocket.ts`, no `useHexData.ts`, no `HexMap.tsx`).
- **Recommendation**: Archive the Phase 1 spec/plan as historical context and write a v2 design doc that reflects the actual edge-finder architecture. Remove stale module references from CLAUDE.md conventions section.

### [MEDIUM] pyproject.toml missing dependencies listed in CLAUDE.md

- **Severity: MEDIUM**
- CLAUDE.md "Technology Stack" section lists these as key dependencies, but they are absent from `pyproject.toml`: `h3`, `searoute`, `shapely`, `sentence-transformers`, `websockets`, `google-cloud-bigquery`.
- These were part of the v1 spatial + GDELT BigQuery stack. They are not installed and not needed by v2.
- **Recommendation**: Remove these from the CLAUDE.md stack section to prevent developer confusion.

### [MEDIUM] `ingestion/gdelt.py` (BigQuery) never implemented; `gdelt_doc.py` used instead

- **Severity: MEDIUM**
- The plan specifies a `ingestion/gdelt.py` using BigQuery with a 4-stage noise filter (volume gate, structural dedup, semantic dedup, relevance scoring). This was never built.
- What exists: `ingestion/gdelt_doc.py` using the GDELT Document API (REST, not BigQuery). No semantic dedup module exists.
- The `ingestion/dedup.py` (semantic dedup with sentence-transformers) planned in Task 10 was never created.
- **Recommendation**: Document that GDELT DOC API replaced BigQuery. If semantic dedup is needed for signal quality, it's a gap worth revisiting.

### [MEDIUM] `portfolio/` and `config/` packages missing `__init__.py`

- **Severity: MEDIUM**
- `backend/src/parallax/portfolio/` has no `__init__.py` — imports from `parallax.portfolio.*` may fail depending on Python version and build tool behavior.
- `backend/src/parallax/config/` also has no `__init__.py`.
- **Recommendation**: Add empty `__init__.py` files to both.

### [LOW] CLAUDE.md conventions section references non-existent files

- **Severity: LOW**
- The Naming Patterns section in CLAUDE.md cites `circuit_breaker.py` as a naming example. This file was never created.
- **Recommendation**: Update the example to reference an existing file.

### [LOW] `main.py` writes to DuckDB outside lifespan context

- **Severity: LOW**
- `main.py` lines 144, 214, 225 call `conn.execute()` directly inside request handlers (not just reads). Under concurrent FastAPI requests this is safe only because DuckDB serializes at the connection level — but it's architecturally inconsistent with the stated design.

---

## What's Healthy

- **47 test files** covering all major v2 modules. Coverage is good for prediction, scoring, markets, contracts, and backtest layers.
- **Scoring/calibration system** is mature: 13 modules including recalibration, track record, selective filtering, and daily scorecard ETL.
- **Paper trading**: Kalshi sandbox integration, portfolio simulation with quarter-Kelly sizing, and look-ahead guard for backtesting are all in place.
- **`simulation/cascade.py`** and **`simulation/world_state.py`** carry over from v1 and are actively used as the reasoning backbone in `prediction/hormuz.py`.
- **Budget tracking**: $20/day hard cap with per-model cost recording is implemented and tested.
- **Daily reports**: 160+ health check and research reports in `docs/reports/` demonstrate consistent automated monitoring.
- **CLI entry point** (`cli/brief.py`) orchestrates the full pipeline: news ingestion → predictions → market fetch → divergence detection → paper trade.

---

## Recommendations

1. Archive `docs/superpowers/specs/2026-03-30-parallax-phase1-design.md` and `docs/superpowers/plans/2026-03-30-parallax-phase1.md` with a note that Parallax pivoted to a v2 architecture.
2. Add `__init__.py` to `parallax/portfolio/` and `parallax/config/`.
3. Decide on the DbWriter enforcement question — either route all writes through it or explicitly document that the v2 single-process model is safe without it.
4. Update CLAUDE.md to remove v1 stack entries (h3, searoute, shapely, sentence-transformers, websockets, google-cloud-bigquery) and fix the `circuit_breaker.py` naming example.
