# Requirements: Parallax

**Defined:** 2026-04-09
**Core Value:** Find mispriced prediction market contracts by reasoning about second-order cascade effects -- validated via paper trading P&L.

## v1.3 Requirements

Requirements for milestone v1.3: Daily Feedback Loop + Scorecard.

### Telemetry Infrastructure

- [ ] **TEL-01**: Pipeline persists run-level metadata (run_id, started_at, ended_at, status, environment) in a `runs` table
- [ ] **TEL-02**: Structured alerts from AlertDispatcher are persisted in an `ops_events` table
- [ ] **TEL-03**: LLM token counts and costs are persisted per-call in an `llm_usage` table
- [ ] **TEL-04**: "No run in 24h" alert fires when pipeline stops running

### Daily Scorecard

- [ ] **SCORE-01**: `daily_scorecard` table stores computed metrics per day with metric name, value, and dimensions
- [ ] **SCORE-02**: `parallax scorecard --date YYYY-MM-DD` CLI command computes and persists all metrics
- [ ] **SCORE-03**: Signal Quality metrics: resolved volume, counterfactual PnL, hit rate, Brier score, calibration bucket gaps, edge-decay, tradeability funnel
- [ ] **SCORE-04**: Execution Quality metrics: orders attempted/accepted, fill rate, time-to-fill, slippage vs reference, fees per contract
- [ ] **SCORE-05**: Portfolio/Risk metrics: gross exposure, concentration, daily realized PnL, loss-cap utilization
- [ ] **SCORE-06**: Data Quality metrics: executable quote coverage, quote staleness rate, market freshness
- [ ] **SCORE-07**: Ops/Runtime metrics: pipeline run count, run success rate, latest run age

### Alerting + Dashboard

- [ ] **ALERT-01**: Scorecard threshold breaches trigger alerts via AlertDispatcher
- [ ] **ALERT-02**: Hard safety thresholds (loss cap, stale quote spike, fill collapse) automatically halt new execution
- [ ] **ALERT-03**: `/api/scorecard` endpoint serves scorecard data for dashboard consumption
- [ ] **ALERT-04**: Minimal dashboard with KPI tiles, Brier score timeseries, reliability diagram, order funnel

### Feedback Automation + Experiments

- [ ] **EXP-01**: `experiment_id` and `variant` tags added to prediction_log, signal_ledger, trade_orders, trade_positions
- [ ] **EXP-02**: Champion/challenger routing allocates signals between strategy variants
- [ ] **EXP-03**: Bounded parameter update engine: tighten min_edge per proxy class (never loosen automatically)
- [ ] **EXP-04**: Cost model auto-updates from realized slippage/fees (upward only, capped)
- [ ] **EXP-05**: Minimum sample size guards (n>=50 for calibration, n>=30 for thresholds, n>=30 for sizing)
- [ ] **EXP-06**: Sequentially valid inference for online monitoring (always-valid p-values)

## v1.2 Requirements (completed)

### Contract Registry (Phase 1) -- Completed

- [x] **REG-01**: Contract registry in DuckDB with proxy classification
- [x] **REG-02**: Proxy classification per model type (ProxyClass enum)
- [x] **REG-03**: MappingPolicy replaces heuristic ticker matching
- [x] **REG-04**: Signal ledger persists every signal
- [x] **REG-05**: Pipeline integration with MappingPolicy + SignalLedger

### Prediction Persistence (Phase 2) -- Completed

- [x] **PERS-01**: PredictionOutput persisted in DuckDB
- [x] **PERS-02**: Resolution checker polls APIs for settled contracts
- [x] **PERS-03**: Calibration queries: hit rate, calibration curve, edge decay
- [x] **PERS-04**: 7-day data guard for calibration analysis

### Paper Trading Evaluation (Phase 3) -- Completed

- [x] **TRAD-01**: Paper trades tracked at contract level
- [x] **TRAD-02**: P&L segmented by proxy_class
- [x] **TRAD-03**: Summary report with significance test
- [x] **TRAD-04**: Automated daily pipeline runs
- [x] **TRAD-05**: Calibration-driven tuning

## v2 Requirements

Deferred from v1.2. Tracked but not in current roadmap.

### Deployment

- **DEPLOY-01**: Docker health checks and graceful restart
- **DEPLOY-02**: FastAPI endpoints return real pipeline data
- **DEPLOY-03**: Graceful API failure handling with retry + fallback
- **DEPLOY-04**: Structured logging audit trail per pipeline run

### Expansion

- **THESIS-01**: Framework for adding new thesis domains
- **THESIS-02**: At least one additional thesis domain with active contracts
- **THESIS-03**: New model integrated into existing pipeline

## Out of Scope

| Feature | Reason |
|---------|--------|
| Full observability stack (OpenTelemetry/Prometheus) | Overkill for single-analyst CLI tool; DuckDB metrics sufficient |
| Real-time streaming dashboard | CLI-first; batch scorecard is sufficient for daily loop |
| Automated risk increase | Safety principle: auto-actions may tighten but never loosen without human review |
| ML-based model selection | Premature; need statistical significance on base models first |
| Multi-user experiment management | Single analyst; experiment tags are for self-comparison only |
| 50-agent swarm | Replaced by 3 focused prediction models |
| H3 spatial visualization / deck.gl map | Deleted -- CLI tool does not need maps |
| Frontend dashboard (React/Vite) | Deleted -- CLI-first |
| Real-money trading | Paper trading only until edge is proven |
| Latency arbitrage | Edge is reasoning depth, not speed |

## Traceability

| Requirement | Phase | Status |
|-------------|-------|--------|
| TEL-01 | TBD | Pending |
| TEL-02 | TBD | Pending |
| TEL-03 | TBD | Pending |
| TEL-04 | TBD | Pending |
| SCORE-01 | TBD | Pending |
| SCORE-02 | TBD | Pending |
| SCORE-03 | TBD | Pending |
| SCORE-04 | TBD | Pending |
| SCORE-05 | TBD | Pending |
| SCORE-06 | TBD | Pending |
| SCORE-07 | TBD | Pending |
| ALERT-01 | TBD | Pending |
| ALERT-02 | TBD | Pending |
| ALERT-03 | TBD | Pending |
| ALERT-04 | TBD | Pending |
| EXP-01 | TBD | Pending |
| EXP-02 | TBD | Pending |
| EXP-03 | TBD | Pending |
| EXP-04 | TBD | Pending |
| EXP-05 | TBD | Pending |
| EXP-06 | TBD | Pending |

**Coverage:**
- v1.3 requirements: 21 total
- Mapped to phases: 0
- Unmapped: 21

---
*Requirements defined: 2026-04-09*
*Last updated: 2026-04-09 after milestone v1.3 definition*
