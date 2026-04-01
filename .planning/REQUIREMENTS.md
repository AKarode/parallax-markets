# Requirements: Parallax

**Defined:** 2026-04-01
**Core Value:** Predictions that beat human intuition about the Iran-Hormuz crisis — continuously evaluated and improved against ground truth.

## v1 Requirements

Requirements for initial release. Each maps to roadmap phases.

### Foundation Hardening

- [ ] **FOUND-01**: WorldState persistence confirms writes to DuckDB before clearing dirty state
- [ ] **FOUND-02**: Cascade engine has damping factor to prevent runaway price spirals
- [ ] **FOUND-03**: Shared Pydantic contracts defined for cross-module communication (events, decisions, predictions)
- [ ] **FOUND-04**: All 10 feature branches integrated into a single working codebase

### Pipeline Integration

- [ ] **PIPE-01**: Async EventBus decouples all modules via publish/subscribe within single process
- [ ] **PIPE-02**: TickOrchestrator owns tick lifecycle: receive events, route to agents, validate via circuit breaker, run cascade, flush deltas
- [ ] **PIPE-03**: GDELT poller runs on 15-minute cadence, publishes curated events to EventBus
- [ ] **PIPE-04**: EIA oil price poller runs on schedule, publishes price updates to EventBus
- [ ] **PIPE-05**: Agent runner subscribes to events, produces structured decisions and predictions
- [ ] **PIPE-06**: End-to-end flow works: GDELT event arrives → agents deliberate → cascade runs → world state updates → data persisted

### Backend API

- [ ] **API-01**: FastAPI REST endpoints serve current world state, agent decisions, predictions, and indicators on page load
- [ ] **API-02**: WebSocket endpoint pushes tick-batched deltas (world state changes, new decisions, indicator updates) to connected clients
- [ ] **API-03**: Health endpoint reports pipeline status (last GDELT fetch, last tick, agent budget remaining)

### Eval Framework

- [ ] **EVAL-01**: Agent predictions parsed into structured schema (direction, magnitude, timeframe, confidence) and persisted
- [ ] **EVAL-02**: Ground truth fetcher resolves predictions against EIA oil prices and GDELT event outcomes
- [ ] **EVAL-03**: Brier score computed for probabilistic predictions; direction and magnitude accuracy scored separately
- [ ] **EVAL-04**: Daily eval cron automatically scores all predictions past their resolve_by date
- [ ] **EVAL-05**: Agent prompt versions tracked — each prediction linked to the prompt version that produced it
- [ ] **EVAL-06**: Eval results queryable by agent, time range, prediction type

### Prompt Improvement

- [ ] **PROMPT-01**: Automated identification of worst-performing agents based on eval scores
- [ ] **PROMPT-02**: Meta-LLM generates prompt patches for underperforming agents
- [ ] **PROMPT-03**: A/B testing of new prompt vs old prompt with automatic winner promotion
- [ ] **PROMPT-04**: Prompt improvement respects $20/day budget (meta-LLM calls included in budget)

### Frontend Data Binding

- [ ] **FE-01**: Agent Activity panel shows real agent decisions with actor name, reasoning summary, and timestamp
- [ ] **FE-02**: Live Indicators panel shows real oil prices, Hormuz traffic flow, pipeline bypass capacity, escalation index
- [ ] **FE-03**: H3 hex map colors and elevation reflect real world state (influence zones, threat levels)
- [ ] **FE-04**: Timeline panel shows simulation event history with scrubbing
- [ ] **FE-05**: Prediction timeline shows scrollable history of predictions with outcomes and scores
- [ ] **FE-06**: Cascade trace visualization shows effect chains (event → flow change → price impact → bypass activation)

### Anomaly Detection

- [ ] **ANOM-01**: Sliding window z-score on GDELT event frequency by actor pair detects unusual spikes
- [ ] **ANOM-02**: Alert banner surfaces in frontend when anomaly threshold exceeded
- [ ] **ANOM-03**: Anomaly events logged and available in prediction context for agents

### Calibration

- [ ] **CAL-01**: Calibration curve computed: bucket predictions by stated confidence, compute actual hit rate per bucket
- [ ] **CAL-02**: Calibration visualization rendered in frontend eval dashboard

## v2 Requirements

Deferred to future release. Tracked but not in current roadmap.

### Advanced Simulation

- **SIM-01**: Counterfactual simulation — fork current state, inject hypothetical event, run N ticks, diff outcomes
- **SIM-02**: Scenario comparison dashboard — side-by-side view of current trajectory vs escalation vs de-escalation

### Enhanced Intelligence

- **INT-01**: Confidence-weighted ensemble aggregation across agents (Parallax consensus prediction)
- **INT-02**: Per-agent accuracy leaderboard with historical trend
- **INT-03**: Source attribution linking predictions to specific GDELT events that triggered them

### Infrastructure

- **INFRA-01**: Multi-user auth and access control
- **INFRA-02**: Cloud deployment (beyond local Docker Compose)
- **INFRA-03**: Multi-scenario support (Ukraine, Taiwan, etc.)

## Out of Scope

| Feature | Reason |
|---------|--------|
| Multi-user authentication | Single-analyst tool for v1 |
| Free-text predictions | Cannot be scored automatically; structured output only |
| Real-time LLM streaming to frontend | 50 agents creates noise; batch completed decisions instead |
| Manual prediction scoring | Automated ground truth resolution; no human-in-the-loop scoring |
| More than 50 agents | Focus on making existing agents better, not adding more |
| Mobile app | Desktop web only |
| External notifications (email, SMS, push) | Single-user local tool; in-app alerts sufficient |
| Historical backfill UI | REPLAY mode stays as dev/debug tool |
| Explanation generation via separate LLM calls | Agents already provide reasoning; don't double LLM costs |

## Traceability

| Requirement | Phase | Status |
|-------------|-------|--------|
| FOUND-01 | Phase 1 | Pending |
| FOUND-02 | Phase 1 | Pending |
| FOUND-03 | Phase 1 | Pending |
| FOUND-04 | Phase 1 | Pending |
| PIPE-01 | Phase 2 | Pending |
| PIPE-02 | Phase 2 | Pending |
| PIPE-03 | Phase 2 | Pending |
| PIPE-04 | Phase 2 | Pending |
| PIPE-05 | Phase 2 | Pending |
| PIPE-06 | Phase 2 | Pending |
| API-01 | Phase 3 | Pending |
| API-02 | Phase 3 | Pending |
| API-03 | Phase 3 | Pending |
| FE-01 | Phase 4 | Pending |
| FE-02 | Phase 4 | Pending |
| FE-03 | Phase 4 | Pending |
| FE-04 | Phase 4 | Pending |
| EVAL-01 | Phase 5 | Pending |
| EVAL-02 | Phase 5 | Pending |
| EVAL-03 | Phase 5 | Pending |
| EVAL-04 | Phase 5 | Pending |
| EVAL-05 | Phase 5 | Pending |
| EVAL-06 | Phase 5 | Pending |
| FE-05 | Phase 6 | Pending |
| FE-06 | Phase 6 | Pending |
| PROMPT-01 | Phase 7 | Pending |
| PROMPT-02 | Phase 7 | Pending |
| PROMPT-03 | Phase 7 | Pending |
| PROMPT-04 | Phase 7 | Pending |
| ANOM-01 | Phase 8 | Pending |
| ANOM-02 | Phase 8 | Pending |
| ANOM-03 | Phase 8 | Pending |
| CAL-01 | Phase 9 | Pending |
| CAL-02 | Phase 9 | Pending |

**Coverage:**
- v1 requirements: 34 total
- Mapped to phases: 34
- Unmapped: 0

---
*Requirements defined: 2026-04-01*
*Last updated: 2026-03-30 after roadmap creation*
