# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-04-08)

**Core value:** Find mispriced prediction market contracts on Iran war outcomes by reasoning about second-order cascade effects.
**Current focus:** Phase 1: Contract Registry + Mapping Policy + Evaluation Ledger

## Current Position

Phase: 1 - Contract Registry + Mapping Policy + Evaluation Ledger
Plan: Not started
Status: Planning
Last activity: 2026-04-08 - Rewrote planning docs to reflect post-pruning architecture

Progress: [░░░░░░░░░░] 0%

## Performance Metrics

**Velocity:**
- Total plans completed: 0
- Average duration: -
- Total execution time: 0 hours

**By Phase:**

| Phase | Plans | Total | Avg/Plan |
|-------|-------|-------|----------|
| - | - | - | - |

**Recent Trend:**
- Last 5 plans: none
- Trend: N/A

*Updated after each plan completion*

## Accumulated Context

### Decisions

Decisions are logged in PROJECT.md Key Decisions table.
Recent decisions affecting current work:

- Pivot: Kill 50-agent swarm, replace with 3 focused prediction models (oil, ceasefire, Hormuz)
- Pivot: Kalshi/Polymarket integration for market consensus benchmarks and paper trading
- Pivot: P&L is the eval -- prediction market resolution replaces manual ground truth scoring
- Pivot: Ship in days not months -- 2-week ceasefire window is validation deadline
- Retained: GDELT DOC ingestion, cascade engine, DuckDB, budget tracker from prior branches
- Dead code pruning April 8 2026: deleted agents/, simulation/engine.py, circuit_breaker.py, spatial/h3_utils.py, ingestion/gdelt.py (BigQuery), ingestion/dedup.py, db/queries.py, frontend/ directory, 3 dead test files. 120 tests still passing.
- CLI-first over frontend dashboard -- deleted React/Vite/deck.gl frontend
- Google News RSS as primary news source over GDELT BigQuery pipeline

### Pending Todos

None yet.

### Blockers/Concerns

- Ceasefire window: 2 weeks from April 7 -- must have paper trading running before it expires
- Kalshi API auth requires RSA key pair generation from account settings
- Polymarket technically restricted for US users -- read-only data access is fine
- Contract mapping is heuristic (`_map_predictions_to_markets()`) -- Phase 1 fixes this

### Quick Tasks Completed

| # | Description | Date | Commit | Directory |
|---|-------------|------|--------|-----------|
| 260408-0ez | Build Kalshi prediction market edge-finder | 2026-04-08 | 600f21d | [260408-0ez-build-kalshi-prediction-market-edge-find](./quick/260408-0ez-build-kalshi-prediction-market-edge-find/) |
| 260408-4ys | Rewrite planning docs to reflect post-pruning architecture | 2026-04-08 | pending | [260408-4ys-rewrite-planning-docs-to-reflect-archite](./quick/260408-4ys-rewrite-planning-docs-to-reflect-archite/) |

## Session Continuity

Last session: 2026-04-08
Stopped at: Planning docs rewritten to match post-pruning codebase. Ready for Phase 1 planning.
Resume file: None
