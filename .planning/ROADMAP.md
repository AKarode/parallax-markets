# Roadmap: Parallax

## Milestones

- ✅ **v1.2 Contract Alignment + Paper Trading** - Phases 1-3 (shipped 2026-04-09)
- 📋 **v1.2 Expansion** - Phases 4-5 (deferred)
- 📋 **v1.3 Daily Feedback Loop + Scorecard** - Phases 6-9 (deprioritized)
- 🚧 **v1.4 Model Intelligence + Resolution Validation** - Phases 10-14 (in progress)

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
**Reference:** .planning/research/contract-mapping/RESEARCH.md

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

<details>
<summary>v1.3 Daily Feedback Loop + Scorecard (Phases 6-9) - DEPRIORITIZED</summary>

- [ ] **Phase 6: Telemetry Foundation** - Schema + wiring for runs, ops_events, llm_usage, daily_scorecard tables and experiment tags
- [ ] **Phase 7: Scorecard CLI + Metrics** - CLI command computing and persisting all scorecard metrics across 5 metric categories
- [ ] **Phase 8: Alerting + Dashboard** - Threshold-based alerting, safety halts, API endpoint, and minimal dashboard
- [ ] **Phase 9: Feedback Automation + Experiments** - Champion/challenger routing, bounded parameter updates, and statistically valid online monitoring

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

</details>

### v1.4 Model Intelligence + Resolution Validation (In Progress)

**Milestone Goal:** Fix structural flaws in how models see data (anchoring, context gaps, single news source) and what they predict against (4 of 12+ event tickers), then validate the hold-to-settlement thesis by scoring against actual settlement outcomes.

- [ ] **Phase 10: Prompt Fixes + Dependency Cleanup** - Remove anchoring, fix bypass flow, guard sample sizes, separate facts from hypotheses, clean dead deps
- [ ] **Phase 11: Context Foundation + Model Registry** - File-based context system, pre-crisis gap fill, model registry pattern in brief.py
- [ ] **Phase 12: Contract Discovery + Alignment** - Enumerate all Kalshi child contracts, classify into families, build fair-value estimators, record settlements
- [ ] **Phase 13: New Capabilities** - Political transition model, rolling daily context, news source diversification
- [ ] **Phase 14: Unified Ensemble + Resolution Validation** - Single aggregation path for live and backtest, settlement-scored backtest, before/after comparison

## Phase Details

### Phase 10: Prompt Fixes + Dependency Cleanup
**Goal**: Models produce independent probability estimates from clean inputs -- no anchoring to market prices, no broken cascade data, no noise from tiny sample sizes, no editorial contamination.
**Depends on**: Phase 3 (extends existing prediction pipeline)
**Requirements**: PROMPT-01, PROMPT-02, PROMPT-03, PROMPT-04, PROMPT-05, ARCH-04
**Success Criteria** (what must be TRUE):
  1. Running `parallax brief` produces predictions where no model prompt contains current market prices before the model states its probability estimate
  2. Oil price model receives a non-zero bypass_flow value computed from the cascade engine when blockade conditions exist
  3. Hormuz model outputs exactly one probability that maps to a single contract resolution criterion (not two conflicting specs)
  4. Track record section in prompts is omitted entirely when fewer than 10 resolved signals exist for that model
  5. Crisis context injected into prompts contains only dated factual events -- editorial hypotheses are separated and excluded from base context
**Plans**: 3 plans
Plans:
- [ ] 10-01-PLAN.md — Anchoring removal + editorial cleanup: strip market prices from 3 prompts, clean crisis_context.py, remove market_context wiring from brief.py and backtest
- [ ] 10-02-PLAN.md — Hormuz single probability spec, track record n>=10 guard, bypass_flow fix with WorldState initialization
- [ ] 10-03-PLAN.md — Remove 6 dead dependencies from pyproject.toml

### Phase 11: Context Foundation + Model Registry
**Goal**: Crisis context is composable and complete (no 6-month gap), and adding a new prediction model requires only a class + registry entry instead of pipeline surgery.
**Depends on**: Phase 10 (clean prompts before expanding context and model infrastructure)
**Requirements**: CTX-01, CTX-02, ARCH-01
**Success Criteria** (what must be TRUE):
  1. A pre-crisis context document exists covering Aug 2025 through Feb 2026 with dated, verifiable events filling the current 3-bullet-point gap
  2. `get_crisis_context()` loads context from files on disk (not Python string literals), and context can be date-gated for backtests (e.g., "only events before March 15")
  3. brief.py discovers and runs prediction models via a registry dict -- adding a fourth model requires only a new predictor class and one registry entry, no changes to pipeline orchestration
**Plans**: TBD

### Phase 12: Contract Discovery + Alignment
**Goal**: The system sees the full contract landscape (not just 4 of 12+ event tickers) and knows which contracts each model can price.
**Depends on**: Phase 11 (needs model registry to map discovered contracts to models)
**Requirements**: DISC-01, DISC-02, DISC-03, DISC-04
**Success Criteria** (what must be TRUE):
  1. Running contract discovery enumerates all child contracts from Kalshi API for all 12 event tickers, persisting ticker, resolution criteria, volume, and settlement status in DuckDB
  2. Every discovered contract has a proxy classification mapping it to a model type (or marking it as UNMODELED)
  3. Fair-value estimator functions exist for each new contract family (IRAN_DEMOCRACY, IRAN_LEADERSHIP, PAHLAVI, IRAN_EMBASSY, OIL_RIG) even if the estimator is a simple prior
  4. All settled contracts have their actual settlement outcome (YES/NO) recorded and are available as ground truth for backtesting
**Plans**: TBD

### Phase 13: New Capabilities
**Goal**: The system covers political transition contracts, remembers what it predicted yesterday, and draws from multiple news sources instead of relying solely on Google News RSS.
**Depends on**: Phase 11 (needs file-based context for rolling context, model registry for political model), Phase 12 (needs discovered political contracts for alignment)
**Requirements**: ARCH-03, CTX-03, CTX-04, NEWS-01, NEWS-02, NEWS-03
**Success Criteria** (what must be TRUE):
  1. A new "Iran political transition" model runs within the pipeline via the model registry and produces PredictionOutput for regime-change contract families
  2. After each cron run, a structured JSON summary (predictions made, market snapshot, key headlines) is appended to a rolling context store
  3. Models receive a 5-day rolling context window showing previous predictions and their outcomes, enabling self-correction and temporal awareness
  4. AP News RSS and at least 2 other sources (from: Al Jazeera, BBC Middle East, EIA weekly petroleum) are integrated with keyword filtering and dedup against existing Google News events
  5. Adding a new RSS news source requires only a URL and keyword list in configuration, not code changes to the ingestion pipeline
**Plans**: TBD

### Phase 14: Unified Ensemble + Resolution Validation
**Goal**: Live pipeline and backtest use identical signal aggregation, and the hold-to-settlement thesis is tested against actual contract outcomes -- not next-day price movement.
**Depends on**: Phase 12 (needs settled contracts with outcomes), Phase 13 (needs all models running for complete ensemble), Phase 10 (VALID-03 needs before/after prompt comparison)
**Requirements**: ARCH-02, VALID-01, VALID-02, VALID-03
**Success Criteria** (what must be TRUE):
  1. Live pipeline (brief.py) and portfolio simulator use the exact same weighted ensemble aggregation function -- no split-brain divergence between what backtest predicts and what live produces
  2. Resolution backtest runs improved models against settled contracts and scores predictions against actual YES/NO settlement outcomes (not next-day price movement)
  3. Settlement-based metrics are computed: hit rate, Brier score, fee-adjusted P&L, and win rate segmented by proxy class
  4. A before/after comparison exists showing prediction quality with old prompts vs new prompts on the same settled contracts, attributing improvement to specific fixes
**Plans**: TBD

## Progress

**Execution Order:**
Phase 10 → 11 → 12 → 13 → 14 (mostly linear, 13 depends on both 11 and 12)

```
Phase 10 (Prompt Fixes + Dep Cleanup)
    → Phase 11 (Context Foundation + Model Registry)
        → Phase 12 (Contract Discovery + Alignment)
            → Phase 13 (New Capabilities)  ← also depends on Phase 11
                → Phase 14 (Unified Ensemble + Resolution Validation)
```

| Phase | Milestone | Plans Complete | Status | Completed |
|-------|-----------|----------------|--------|-----------|
| 1. Contract Registry + Mapping Policy | v1.2 | 3/3 | Complete | 2026-04-08 |
| 2. Prediction Persistence + Calibration | v1.2 | 3/3 | Complete | 2026-04-08 |
| 3. Paper Trading Evaluation | v1.2 | 5/5 | Complete | 2026-04-09 |
| 4. Deployment Fixes | v1.2 | TBD | Deferred | - |
| 5. Second Thesis Expansion | v1.2 | TBD | Deferred | - |
| 6. Telemetry Foundation | v1.3 | 0/TBD | Deprioritized | - |
| 7. Scorecard CLI + Metrics | v1.3 | 0/TBD | Deprioritized | - |
| 8. Alerting + Dashboard | v1.3 | 0/TBD | Deprioritized | - |
| 9. Feedback Automation + Experiments | v1.3 | 0/TBD | Deprioritized | - |
| 10. Prompt Fixes + Dep Cleanup | v1.4 | 0/3 | Planned | - |
| 11. Context Foundation + Model Registry | v1.4 | 0/TBD | Not started | - |
| 12. Contract Discovery + Alignment | v1.4 | 0/TBD | Not started | - |
| 13. New Capabilities | v1.4 | 0/TBD | Not started | - |
| 14. Unified Ensemble + Resolution Validation | v1.4 | 0/TBD | Not started | - |
