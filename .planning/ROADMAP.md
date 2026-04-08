# Roadmap: Parallax

## Overview

Parallax is a working CLI prediction market edge-finder. The pipeline runs end-to-end: news ingestion (Google News RSS + GDELT DOC) -> 3 prediction models (Claude Sonnet) -> market price comparison (Kalshi + Polymarket) -> divergence detection -> paper trading (Kalshi sandbox). 120 tests passing. Dead code pruned April 8 2026.

The roadmap strengthens the pipeline's trustworthiness and expands its scope. Build order: contract alignment first (fixes the biggest structural weakness -- heuristic ticker mapping), then prediction persistence (needed for calibration), then paper trading evaluation (proves edge with P&L), then deployment hardening, then thesis expansion.

## Phases

- [ ] **Phase 1: Contract Registry + Mapping Policy + Evaluation Ledger** - Formal proposition alignment between model predictions and tradeable contracts
- [ ] **Phase 2: Prediction Persistence + Calibration** - Persist every prediction with full context, enable calibration analysis
- [ ] **Phase 3: Paper Trading Evaluation** - Contract-level P&L tracking to prove or disprove edge
- [ ] **Phase 4: Deployment Fixes** - Docker reliability, API hydration, error handling, structured logging
- [ ] **Phase 5: Second Thesis Expansion** - Expand beyond Iran/Hormuz to additional prediction market opportunities

## Phase Details

### Phase 1: Contract Registry + Mapping Policy + Evaluation Ledger
**Goal:** Every trade signal has explicit proposition alignment, proxy quality tracking, and confidence discounting -- replacing the heuristic `_map_predictions_to_markets()`.
**Depends on:** Nothing (first phase)
**Requirements:** REG-01, REG-02, REG-03, REG-04, REG-05
**Success Criteria** (what must be TRUE):
  1. Contract registry in DuckDB stores every Kalshi/Polymarket contract with resolution criteria and proxy classification per model type
  2. Mapping policy replaces `_map_predictions_to_markets()` with explicit proxy-aware decision logic that discounts edge for non-DIRECT mappings
  3. Signal ledger records every signal with full provenance (model claim, contract mapped, proxy class, market state, trade decision)
  4. Pipeline runs end-to-end using new contract-aware mapping instead of heuristic ticker matching
**Plans:** 3 plans
Plans:
- [x] 01-01-PLAN.md — Contract schemas (ProxyClass, ContractRecord, MappingResult) + DuckDB tables + ContractRegistry CRUD + seed data
- [x] 01-02-PLAN.md — MappingPolicy class with proxy-aware confidence discounting and probability inversion
- [x] 01-03-PLAN.md — SignalLedger persistence + rewire brief.py to use MappingPolicy + SignalLedger
**Reference:** .planning/research/contract-mapping/RESEARCH.md

### Phase 2: Prediction Persistence + Calibration
**Goal:** Every prediction the system makes is persisted with full context, enabling calibration analysis and model improvement.
**Depends on:** Phase 1 (needs signal ledger schema)
**Requirements:** PERS-01, PERS-02, PERS-03, PERS-04
**Success Criteria** (what must be TRUE):
  1. Every prediction output (probability, reasoning, news context, cascade state) is persisted in DuckDB
  2. Resolution checker polls Kalshi API for settled contracts and backfills outcomes
  3. Calibration queries work: hit rate by proxy class, model calibration curve (are 70% predictions right 70% of the time?), edge decay analysis
  4. At least one week of prediction history is accumulated and queryable
**Plans:** 3 plans
Plans:
- [x] 02-01-PLAN.md — Prediction persistence: prediction_log table + PredictionLogger + run_id in signal_ledger + brief.py wiring
- [x] 02-02-PLAN.md — Resolution checker: Kalshi settlement polling + signal_ledger backfill + --check-resolutions CLI
- [x] 02-03-PLAN.md — Calibration queries: hit rate by proxy class, calibration curve, edge decay + --calibration CLI + 7-day data guard

### Phase 3: Paper Trading Evaluation + Continuous Improvement
**Goal:** Contract-level P&L tracking proves or disproves the system's edge, then iterates on model parameters and prompts based on calibration data.
**Depends on:** Phase 2 (needs prediction persistence + resolution data)
**Requirements:** TRAD-01, TRAD-02, TRAD-03, TRAD-04, TRAD-05
**Success Criteria** (what must be TRUE):
  1. Paper trades are tracked at contract level with entry price, exit/resolution price, and realized P&L
  2. P&L is segmented by proxy class (DIRECT vs NEAR_PROXY vs LOOSE_PROXY)
  3. Summary report shows total P&L, win rate, average edge at entry, and whether edge is statistically significant
  4. Automated daily pipeline runs (cron/scheduled) accumulate prediction + signal history
  5. Calibration-driven parameter tuning: discount factors, min_edge threshold, and model prompts adjusted based on where predictions were wrong
**Plans:** TBD

### Phase 4: Deployment Fixes
**Goal:** The system runs reliably in Docker with hydrated API endpoints and proper error handling.
**Depends on:** Phase 1 (contract registry needed for API responses)
**Requirements:** DEPLOY-01, DEPLOY-02, DEPLOY-03, DEPLOY-04
**Success Criteria** (what must be TRUE):
  1. `docker compose up` starts the backend and health check passes
  2. FastAPI endpoints return real data (predictions, markets, divergences, trades) not empty responses
  3. Pipeline handles API failures gracefully (Kalshi rate limits, GDELT 429s, network errors) with retry + fallback
  4. Logging provides clear audit trail of each pipeline run
**Plans:** TBD

### Phase 5: Second Thesis Expansion
**Goal:** Expand beyond Iran/Hormuz to additional prediction market opportunities (energy/macro).
**Depends on:** Phase 3 (must prove edge on first thesis before expanding)
**Requirements:** THESIS-01, THESIS-02, THESIS-03
**Success Criteria** (what must be TRUE):
  1. At least one additional thesis domain identified with active Kalshi/Polymarket contracts
  2. New prediction model added for the second thesis using the same pipeline infrastructure
  3. Contract registry expanded with new contracts and proxy classifications
**Plans:** TBD

## Progress

**Execution Order:**
Phases 1 -> 2 -> 3, with Phase 4 parallelizable after Phase 1. Phase 5 after Phase 3.

```
Phase 1 ──> Phase 2 ──> Phase 3 ──> Phase 5
   └──────> Phase 4
```

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 1. Contract Registry + Mapping Policy | 0/3 | Planning complete | - |
| 2. Prediction Persistence + Calibration | 0/3 | Planning complete | - |
| 3. Paper Trading Evaluation | 0/TBD | Not started | - |
| 4. Deployment Fixes | 0/TBD | Not started | - |
| 5. Second Thesis Expansion | 0/TBD | Not started | - |
