# Roadmap: Parallax

## Milestones

- ✅ **v1.2 Contract Alignment + Paper Trading** - Phases 1-3 (shipped 2026-04-09)
- 📋 **v1.2 Expansion** - Phases 4-5 (deferred)
- 🚧 **v1.3 Daily Feedback Loop + Scorecard** - Phases 6-9 (in progress)

## Phases

<details>
<summary>v1.2 Contract Alignment + Paper Trading (Phases 1-3) - SHIPPED 2026-04-09</summary>

- [x] **Phase 1: Contract Registry + Mapping Policy + Evaluation Ledger** - Formal proposition alignment between model predictions and tradeable contracts
- [x] **Phase 2: Prediction Persistence + Calibration** - Persist every prediction with full context, enable calibration analysis
- [x] **Phase 3: Paper Trading Evaluation** - Contract-level P&L tracking, Portfolio Allocator, and Risk controls

### Phase 1: Contract Registry + Mapping Policy + Evaluation Ledger
**Goal**: Every trade signal has explicit proposition alignment, proxy quality tracking, and confidence discounting -- replacing the heuristic `_map_predictions_to_markets()`.
**Depends on**: Nothing (first phase)
**Requirements**: REG-01, REG-02, REG-03, REG-04, REG-05
**Success Criteria** (what must be TRUE):
  1. Contract registry in DuckDB stores every Kalshi/Polymarket contract with resolution criteria and proxy classification per model type
  2. Mapping policy replaces `_map_predictions_to_markets()` with explicit proxy-aware decision logic that discounts edge for non-DIRECT mappings
  3. Signal ledger records every signal with full provenance (model claim, contract mapped, proxy class, market state, trade decision)
  4. Pipeline runs end-to-end using new contract-aware mapping instead of heuristic ticker matching
**Plans**: 3 plans
Plans:
- [x] 01-01-PLAN.md — Contract schemas (ProxyClass, ContractRecord, MappingResult) + DuckDB tables + ContractRegistry CRUD + seed data
- [x] 01-02-PLAN.md — MappingPolicy class with proxy-aware confidence discounting and probability inversion
- [x] 01-03-PLAN.md — SignalLedger persistence + rewire brief.py to use MappingPolicy + SignalLedger
**Reference:** .planning/research/contract-mapping/RESEARCH.md

### Phase 2: Prediction Persistence + Calibration
**Goal**: Every prediction the system makes is persisted with full context, enabling calibration analysis and model improvement.
**Depends on**: Phase 1 (needs signal ledger schema)
**Requirements**: PERS-01, PERS-02, PERS-03, PERS-04
**Success Criteria** (what must be TRUE):
  1. Every prediction output (probability, reasoning, news context, cascade state) is persisted in DuckDB
  2. Resolution checker polls Kalshi API for settled contracts and backfills outcomes
  3. Calibration queries work: hit rate by proxy class, model calibration curve (are 70% predictions right 70% of the time?), edge decay analysis
  4. At least one week of prediction history is accumulated and queryable
**Plans**: 3 plans
Plans:
- [x] 02-01-PLAN.md — Prediction persistence: prediction_log table + PredictionLogger + run_id in signal_ledger + brief.py wiring
- [x] 02-02-PLAN.md — Resolution checker: Kalshi settlement polling + signal_ledger backfill + --check-resolutions CLI
- [x] 02-03-PLAN.md — Calibration queries: hit rate by proxy class, calibration curve, edge decay + --calibration CLI + 7-day data guard

### Phase 3: Paper Trading Evaluation + Continuous Improvement
**Goal**: Contract-level P&L tracking proves or disproves the system's edge, then iterates on model parameters and prompts based on calibration data.
**Depends on**: Phase 2 (needs prediction persistence + resolution data)
**Requirements**: TRAD-01, TRAD-02, TRAD-03, TRAD-04, TRAD-05
**Success Criteria** (what must be TRUE):
  1. Paper trades are tracked at contract level with entry price, exit/resolution price, and realized P&L
  2. P&L is segmented by proxy class (DIRECT vs NEAR_PROXY vs LOOSE_PROXY)
  3. Summary report shows total P&L, win rate, average edge at entry, and whether edge is statistically significant
  4. Automated daily pipeline runs (cron/scheduled) accumulate prediction + signal history
  5. Calibration-driven parameter tuning: discount factors, min_edge threshold, and model prompts adjusted based on where predictions were wrong
**Plans**: 5 plans
Plans:
- [x] 03-01-PLAN.md — Automated operations: --scheduled CLI flag with JSON output, cron wrapper script, health check, crontab installer
- [x] 03-02-PLAN.md — Report card CLI (P&L by proxy class, significance test), proxy_was_aligned backfill, Streamlit dashboard with reusable data layer
- [x] 03-03-PLAN.md — Track record injection: build_track_record() utility, db_conn on predictors, {track_record} prompt placeholder
- [x] 03-04-PLAN.md — Mechanical recalibration: bucket-based probability adjustment, MappingPolicy threshold auto-tuning, suggested_size advisory
- [x] 03-05-PLAN.md — Gap closure: discount factor auto-adjustment from hit_rate_by_proxy_class calibration data

</details>

<details>
<summary>v1.2 Expansion (Phases 4-5) - DEFERRED</summary>

- [x] **Phase 4: Deployment Fixes** - Ops routing, Docker reliability, robust execution environment rules
- [ ] **Phase 5: Second Thesis Expansion** - Expand beyond Iran/Hormuz to additional prediction market opportunities

### Phase 4: Deployment Fixes
**Goal**: The system runs reliably in Docker with hydrated API endpoints and proper error handling.
**Depends on**: Phase 1 (contract registry needed for API responses)
**Requirements**: DEPLOY-01, DEPLOY-02, DEPLOY-03, DEPLOY-04
**Success Criteria** (what must be TRUE):
  1. `docker compose up` starts the backend and health check passes
  2. FastAPI endpoints return real data (predictions, markets, divergences, trades) not empty responses
  3. Pipeline handles API failures gracefully (Kalshi rate limits, GDELT 429s, network errors) with retry + fallback
  4. Logging provides clear audit trail of each pipeline run
**Plans:** TBD

### Phase 5: Second Thesis Expansion
**Goal**: Expand beyond Iran/Hormuz to additional prediction market opportunities (energy/macro).
**Depends on**: Phase 3 (must prove edge on first thesis before expanding)
**Requirements**: THESIS-01, THESIS-02, THESIS-03
**Success Criteria** (what must be TRUE):
  1. At least one additional thesis domain identified with active Kalshi/Polymarket contracts
  2. New prediction model added for the second thesis using the same pipeline infrastructure
  3. Contract registry expanded with new contracts and proxy classifications
**Plans:** TBD

</details>

### 🚧 v1.3 Daily Feedback Loop + Scorecard (In Progress)

**Milestone Goal:** Build automated daily telemetry, scoring, and feedback so the system can measure and improve its own forecasting and trading performance -- safely, with statistical rigor.

- [ ] **Phase 6: Telemetry Foundation** - Schema + wiring for runs, ops_events, llm_usage, daily_scorecard tables and experiment tags
- [ ] **Phase 7: Scorecard CLI + Metrics** - CLI command computing and persisting all scorecard metrics across 5 metric categories
- [ ] **Phase 8: Alerting + Dashboard** - Threshold-based alerting, safety halts, API endpoint, and minimal dashboard
- [ ] **Phase 9: Feedback Automation + Experiments** - Champion/challenger routing, bounded parameter updates, and statistically valid online monitoring

## Phase Details

### Phase 6: Telemetry Foundation
**Goal**: Every pipeline run, LLM call, ops event, and experiment variant is tracked in DuckDB -- giving the scorecard and alerting phases a complete data foundation to query against.
**Depends on**: Phase 3 (extends existing DuckDB schema and pipeline)
**Requirements**: TEL-01, TEL-02, TEL-03, SCORE-01, EXP-01
**Success Criteria** (what must be TRUE):
  1. `parallax brief` persists a row in `runs` table with run_id, timestamps, status, and environment for every execution
  2. AlertDispatcher writes structured events (severity, category, message, context) to `ops_events` table
  3. Every Claude API call logs token counts and dollar cost to `llm_usage` table, queryable by run_id and model
  4. `daily_scorecard` table exists with schema: date, metric_name, metric_value, dimensions (JSON), ready for ETL population
  5. `experiment_id` and `variant` columns exist on prediction_log, signal_ledger, trade_orders, and trade_positions tables
**Plans**: TBD

### Phase 7: Scorecard CLI + Metrics
**Goal**: A single CLI command computes all performance metrics for a given day and persists them, so the operator can assess signal quality, execution quality, portfolio risk, data quality, and ops health at a glance.
**Depends on**: Phase 6 (needs runs, llm_usage, ops_events, daily_scorecard tables populated)
**Requirements**: TEL-04, SCORE-02, SCORE-03, SCORE-04, SCORE-05, SCORE-06, SCORE-07
**Success Criteria** (what must be TRUE):
  1. `parallax scorecard --date 2026-04-09` computes all metrics and writes them to daily_scorecard table
  2. Signal Quality section shows: resolved volume, counterfactual PnL, hit rate, Brier score, calibration bucket gaps, edge-decay half-life, tradeability funnel conversion
  3. Execution Quality section shows: orders attempted vs accepted, fill rate, median time-to-fill, slippage vs reference price, fees per contract
  4. Portfolio/Risk section shows: gross exposure, max single-contract concentration, daily realized PnL, loss-cap utilization percentage
  5. Data Quality section shows: executable quote coverage (% of markets with live bid/ask), quote staleness rate, market data freshness
  6. Ops/Runtime section shows: pipeline run count, run success rate, latest run age -- and "no run in 24h" alert fires when pipeline stops
**Plans**: TBD

### Phase 8: Alerting + Dashboard
**Goal**: Metric threshold breaches trigger automated alerts and safety halts, and a minimal dashboard makes the scorecard data visually accessible without leaving the terminal workflow.
**Depends on**: Phase 7 (needs scorecard metrics computed and persisted)
**Requirements**: ALERT-01, ALERT-02, ALERT-03, ALERT-04
**Success Criteria** (what must be TRUE):
  1. Scorecard computation triggers AlertDispatcher when any metric breaches its configured threshold (e.g., Brier > 0.35, hit_rate < 40%)
  2. Hard safety thresholds (daily loss cap exceeded, stale quote rate > 50%, fill rate collapse < 20%) automatically halt new trade execution until human review
  3. `/api/scorecard` endpoint returns scorecard data as JSON (latest day by default, date range queryable)
  4. Minimal dashboard renders KPI tiles, Brier score timeseries, reliability diagram, and order funnel -- accessible via browser at localhost
**Plans**: TBD
**UI hint**: yes

### Phase 9: Feedback Automation + Experiments
**Goal**: The system can run controlled experiments comparing strategy variants and safely auto-tune parameters based on statistically valid evidence -- tightening gates only, never loosening without human approval.
**Depends on**: Phase 8 (needs alerting for safety gates), Phase 6 (needs experiment tags on tables)
**Requirements**: EXP-02, EXP-03, EXP-04, EXP-05, EXP-06
**Success Criteria** (what must be TRUE):
  1. Champion/challenger routing splits signals between two strategy variants (e.g., current vs tighter-edge), tagged with experiment_id and variant throughout the pipeline
  2. Bounded parameter update engine can tighten min_edge per proxy class based on observed hit rates -- but never loosens automatically
  3. Cost model auto-updates slippage and fee estimates upward from realized trade data (upward only, capped at 2x current estimate)
  4. Minimum sample size guards prevent any auto-adjustment from firing until n>=50 for calibration metrics, n>=30 for threshold changes, n>=30 for sizing changes
  5. Sequentially valid inference (always-valid p-values / confidence sequences) enables continuous monitoring of experiment outcomes without inflating false positive rates
**Plans**: TBD

## Progress

**Execution Order:**
Phase 6 → 7 → 8 → 9 (linear dependency chain)

```
Phase 6 (Telemetry Foundation)
    → Phase 7 (Scorecard CLI + Metrics)
        → Phase 8 (Alerting + Dashboard)
            → Phase 9 (Feedback Automation + Experiments)
```

| Phase | Milestone | Plans Complete | Status | Completed |
|-------|-----------|----------------|--------|-----------|
| 1. Contract Registry + Mapping Policy | v1.2 | 3/3 | Complete | 2026-04-08 |
| 2. Prediction Persistence + Calibration | v1.2 | 3/3 | Complete | 2026-04-08 |
| 3. Paper Trading Evaluation | v1.2 | 5/5 | Complete | 2026-04-09 |
| 4. Deployment Fixes | v1.2 | TBD | Deferred | - |
| 5. Second Thesis Expansion | v1.2 | TBD | Deferred | - |
| 6. Telemetry Foundation | v1.3 | 0/TBD | Not started | - |
| 7. Scorecard CLI + Metrics | v1.3 | 0/TBD | Not started | - |
| 8. Alerting + Dashboard | v1.3 | 0/TBD | Not started | - |
| 9. Feedback Automation + Experiments | v1.3 | 0/TBD | Not started | - |
