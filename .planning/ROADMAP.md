# Roadmap: Parallax

## Overview

Parallax has five major subsystems (ingestion, agents, simulation, database, frontend) built across 10 parallel feature branches. The roadmap integrates these into a single live pipeline, adds prediction evaluation and prompt improvement, then wires everything to a real-time dashboard. The build order is strictly dependency-constrained: foundation fixes before pipeline, pipeline before API, API before frontend panels, eval before prompt improvement, and calibration last (needs accumulated prediction history).

## Phases

**Phase Numbering:**
- Integer phases (1, 2, 3): Planned milestone work
- Decimal phases (2.1, 2.2): Urgent insertions (marked with INSERTED)

Decimal phases appear between their surrounding integers in numeric order.

- [ ] **Phase 1: Foundation Hardening** - Merge 10 branches, fix data integrity bugs, establish shared contracts
- [ ] **Phase 2: Live Pipeline** - Wire EventBus, TickOrchestrator, ingestion pollers, and agent runner into end-to-end flow
- [ ] **Phase 3: Backend API** - FastAPI REST + WebSocket endpoints serving world state and pushing live deltas
- [ ] **Phase 4: Frontend Core Panels** - Wire real pipeline data to agent activity, indicators, map, and timeline panels
- [ ] **Phase 5: Eval Framework** - Structured prediction logging, ground truth resolution, Brier scoring, daily eval cron
- [ ] **Phase 6: Frontend Intelligence Views** - Prediction timeline with outcomes and cascade trace visualization
- [ ] **Phase 7: Prompt Improvement** - Automated worst-performer identification, meta-LLM prompt patches, A/B testing
- [ ] **Phase 8: Anomaly Detection** - Sliding window z-score on GDELT event frequency with frontend alert banner
- [ ] **Phase 9: Calibration** - Calibration curve computation and frontend visualization in eval dashboard

## Phase Details

### Phase 1: Foundation Hardening
**Goal**: A single merged codebase with verified data integrity and shared contracts across all modules
**Depends on**: Nothing (first phase)
**Requirements**: FOUND-01, FOUND-02, FOUND-03, FOUND-04
**Success Criteria** (what must be TRUE):
  1. All 10 feature branches are merged into one branch with all existing tests passing
  2. WorldState dirty-set clearing only happens after DbWriter confirms the write succeeded
  3. Cascade engine applies cumulative damping that prevents price values from exceeding configurable bounds over multiple ticks
  4. A shared Pydantic contracts module exists and is imported by simulation, agents, ingestion, and API modules
**Plans**: TBD

### Phase 2: Live Pipeline
**Goal**: Real-world events flow end-to-end through the system: GDELT ingestion to agent deliberation to cascade simulation to persisted world state
**Depends on**: Phase 1
**Requirements**: PIPE-01, PIPE-02, PIPE-03, PIPE-04, PIPE-05, PIPE-06
**Success Criteria** (what must be TRUE):
  1. Running `docker compose up` starts the pipeline and within 15 minutes a GDELT event appears in DuckDB
  2. Agent decisions are produced in response to ingested events and persisted with structured schemas
  3. Cascade rules fire after agent decisions, updating world state variables (oil flow, prices, escalation index)
  4. The TickOrchestrator completes full tick cycles (ingest, route, deliberate, cascade, flush) without manual intervention
  5. All module communication goes through the EventBus -- no direct cross-module function calls
**Plans**: TBD

### Phase 3: Backend API
**Goal**: Frontend can load current state on page open and receive live updates as ticks complete
**Depends on**: Phase 2
**Requirements**: API-01, API-02, API-03
**Success Criteria** (what must be TRUE):
  1. GET requests to REST endpoints return current world state, recent agent decisions, predictions, and indicator values
  2. A WebSocket connection receives tick-batched delta messages within seconds of each tick completing
  3. Health endpoint reports last GDELT fetch timestamp, last tick number, and remaining agent budget for the day
**Plans**: TBD

### Phase 4: Frontend Core Panels
**Goal**: The dashboard shows real live data from the running pipeline -- not placeholders
**Depends on**: Phase 3
**Requirements**: FE-01, FE-02, FE-03, FE-04
**Success Criteria** (what must be TRUE):
  1. Agent Activity panel displays real agent decisions with actor name, reasoning summary, and timestamp updating live
  2. Live Indicators panel shows current oil prices (Brent/WTI), Hormuz traffic flow percentage, pipeline bypass capacity, and escalation index -- all from real data
  3. H3 hex map renders influence zones and threat levels from actual world state, with colors and elevation changing as ticks progress
  4. Timeline panel shows a scrollable history of simulation events that updates as new events arrive
**Plans**: TBD
**UI hint**: yes

### Phase 5: Eval Framework
**Goal**: Every agent prediction is scored against reality, building the data foundation for prompt improvement and analyst trust
**Depends on**: Phase 2
**Requirements**: EVAL-01, EVAL-02, EVAL-03, EVAL-04, EVAL-05, EVAL-06
**Success Criteria** (what must be TRUE):
  1. Agent predictions are parsed into structured records (direction, magnitude, timeframe, confidence) and persisted in DuckDB
  2. Oil price predictions are automatically resolved against EIA data and scored with Brier score, direction accuracy, and magnitude accuracy
  3. A daily eval cron scores all predictions past their resolve_by date without manual trigger
  4. Each prediction is linked to the prompt version that produced it
  5. Eval results can be queried by agent name, time range, and prediction type via the eval query interface
**Plans**: TBD

### Phase 6: Frontend Intelligence Views
**Goal**: The analyst can see prediction track records and understand how cascade effects chain together
**Depends on**: Phase 5, Phase 4
**Requirements**: FE-05, FE-06
**Success Criteria** (what must be TRUE):
  1. Prediction timeline shows a scrollable history of predictions with their outcomes (hit/miss) and numerical scores
  2. Cascade trace visualization shows readable effect chains (e.g., "tanker seized -> flow -30% -> price +$8 -> pipeline activated") for recent simulation events
**Plans**: TBD
**UI hint**: yes

### Phase 7: Prompt Improvement
**Goal**: Underperforming agents automatically get better prompts, closing the intelligence flywheel
**Depends on**: Phase 5
**Requirements**: PROMPT-01, PROMPT-02, PROMPT-03, PROMPT-04
**Success Criteria** (what must be TRUE):
  1. The system identifies the N worst-performing agents by eval score and flags them for prompt revision
  2. A meta-LLM generates candidate prompt patches for flagged agents without human intervention
  3. New prompts are A/B tested against old prompts, and the winner is automatically promoted
  4. All meta-LLM calls for prompt improvement are tracked within the $20/day budget (no budget overruns from improvement loop)
**Plans**: TBD

### Phase 8: Anomaly Detection
**Goal**: The analyst is alerted when unusual patterns appear in the event stream before agents even process them
**Depends on**: Phase 2
**Requirements**: ANOM-01, ANOM-02, ANOM-03
**Success Criteria** (what must be TRUE):
  1. A sliding window z-score detector identifies unusual spikes in GDELT event frequency grouped by actor pair
  2. An alert banner appears in the frontend within one tick of an anomaly threshold being exceeded
  3. Detected anomalies are logged and included in the context window provided to agents for their next deliberation
**Plans**: TBD
**UI hint**: yes

### Phase 9: Calibration
**Goal**: The analyst can assess whether agent confidence levels are meaningful (does 70% confidence mean 70% accuracy?)
**Depends on**: Phase 5
**Requirements**: CAL-01, CAL-02
**Success Criteria** (what must be TRUE):
  1. Predictions are bucketed by stated confidence level and actual hit rates are computed per bucket
  2. A calibration curve chart is rendered in the frontend eval dashboard showing ideal vs actual calibration
**Plans**: TBD
**UI hint**: yes

## Progress

**Execution Order:**
Phases execute in numeric order: 1 -> 2 -> 3 -> 4 -> 5 -> 6 -> 7 -> 8 -> 9
Note: Phases 5, 8, 9 depend on Phase 2 (not Phase 4), so 5 could theoretically parallel 3/4. However, sequential execution is simpler for a solo developer.

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 1. Foundation Hardening | 0/TBD | Not started | - |
| 2. Live Pipeline | 0/TBD | Not started | - |
| 3. Backend API | 0/TBD | Not started | - |
| 4. Frontend Core Panels | 0/TBD | Not started | - |
| 5. Eval Framework | 0/TBD | Not started | - |
| 6. Frontend Intelligence Views | 0/TBD | Not started | - |
| 7. Prompt Improvement | 0/TBD | Not started | - |
| 8. Anomaly Detection | 0/TBD | Not started | - |
| 9. Calibration | 0/TBD | Not started | - |
