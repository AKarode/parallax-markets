# Requirements: Parallax

**Defined:** 2026-04-09
**Core Value:** Find mispriced prediction market contracts by reasoning about second-order cascade effects -- validated via paper trading P&L.

## v1.4 Requirements

Requirements for milestone v1.4: Model Intelligence + Resolution Validation.

### Prompt Optimization

- [ ] **PROMPT-01**: All prediction model prompts produce probabilities without seeing current market prices (anchoring removal)
- [ ] **PROMPT-02**: Oil price model receives computed bypass flow from cascade engine (not hardcoded 0)
- [ ] **PROMPT-03**: Hormuz model outputs a single well-defined probability matching one contract resolution criterion (fix dual-probability spec)
- [ ] **PROMPT-04**: Track record injection requires minimum sample size (n>=10) before showing hit rate statistics
- [ ] **PROMPT-05**: Crisis context separates verifiable facts from editorial hypotheses — models receive facts only in base context

### Contract Discovery

- [ ] **DISC-01**: System enumerates all child contracts from Kalshi API for all 12 event tickers, persisting resolution criteria, volume, settlement status
- [ ] **DISC-02**: Every discovered contract is classified into a contract family with proxy mappings per model type
- [ ] **DISC-03**: Fair-value estimators exist for each new contract family (IRAN_DEMOCRACY, IRAN_LEADERSHIP, PAHLAVI, IRAN_EMBASSY, OIL_RIG)
- [ ] **DISC-04**: Settled contracts are identified and their settlement outcomes recorded for backtesting

### Context Intelligence

- [ ] **CTX-01**: Pre-crisis context document covers Aug 2025 through Feb 2026 escalation with verifiable events, dates, and data points
- [ ] **CTX-02**: Crisis context loads from files on disk (not hardcoded Python strings), composable for backtests via date gating
- [ ] **CTX-03**: Each cron run appends a structured summary (predictions, market snapshot, key headlines) to rolling context
- [ ] **CTX-04**: Models receive a rolling 5-day context window with previous predictions and outcomes for temporal awareness

### Model Architecture

- [ ] **ARCH-01**: brief.py uses a model registry pattern — adding a new model requires only a predictor class + registry entry, not pipeline surgery
- [ ] **ARCH-02**: Live pipeline and simulator use the same weighted ensemble aggregation logic (unified, not split-brain)
- [ ] **ARCH-03**: New "Iran political transition" model covers regime-change contract families using the standard PredictionOutput interface
- [ ] **ARCH-04**: Dead dependencies removed from pyproject.toml (h3, sentence-transformers, searoute, shapely, google-cloud-bigquery, websockets)

### News Diversification

- [ ] **NEWS-01**: AP News RSS feeds integrated as news source with keyword filtering and dedup against existing Google News events
- [ ] **NEWS-02**: At least 2 additional RSS sources (from: Al Jazeera Middle East, BBC Middle East, EIA weekly petroleum) integrated
- [ ] **NEWS-03**: News ingestion is parameterized — adding a new RSS source requires only a URL + keyword list, not code changes

### Resolution Validation

- [ ] **VALID-01**: Resolution backtest runs models against settled contracts and scores against actual settlement outcomes (not next-day price)
- [ ] **VALID-02**: Settlement-based metrics computed: hit rate, Brier score, fee-adjusted P&L, win rate by proxy class
- [ ] **VALID-03**: Backtest results compared before/after prompt fixes to attribute improvement

## v1.3 Requirements (deprioritized)

Moved from active to deferred. Model intelligence has higher ROI than telemetry at current data sparsity.

### Telemetry Infrastructure

- **TEL-01**: Pipeline persists run-level metadata in a `runs` table
- **TEL-02**: Structured alerts persisted in `ops_events` table
- **TEL-03**: LLM token/cost persisted in `llm_usage` table
- **TEL-04**: "No run in 24h" alert

### Daily Scorecard

- **SCORE-01** through **SCORE-07**: Daily scorecard ETL + metrics across 5 categories

### Alerting + Dashboard

- **ALERT-01** through **ALERT-04**: Threshold alerting, safety halts, API endpoint, minimal dashboard

### Feedback Automation + Experiments

- **EXP-01** through **EXP-06**: Experiment tags, champion/challenger, bounded updates, sequential inference

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

### Deployment

- **DEPLOY-01** through **DEPLOY-04**: Docker hardening, API hydration, error handling, logging

### Expansion

- **THESIS-01** through **THESIS-03**: Multi-domain framework, new thesis, new model

## Out of Scope

| Feature | Reason |
|---------|--------|
| Superforecaster persona prompts | Research shows they reduce accuracy (OSF 2025) |
| DSPy/automated prompt optimization | Insufficient data (n<50), $20/day budget |
| Cross-platform arbitrage | Paper trading only, can't execute real arb |
| Complex ensemble (Bayesian, stacking) | n<50, hit-rate-weighted mean is correct level |
| Active exit/sell trading | Fee math kills it (5.5c round-trip vs 2.8c hold) |
| Multi-scenario expansion (non-Iran) | Prove edge on Iran first |
| Real-time latency optimization | Edge is reasoning depth, not speed |
| Full observability stack (OTel) | Overkill for single-analyst CLI tool |
| 50-agent swarm | Replaced by focused prediction models |
| Contract-first architecture | Deferred to v2.0, model registry sufficient for now |

## Traceability

Updated during roadmap creation.

| Requirement | Phase | Status |
|-------------|-------|--------|
| (populated by roadmapper) | | |

**Coverage:**
- v1.4 requirements: 21 total
- Mapped to phases: TBD
- Unmapped: TBD

---
*Requirements defined: 2026-04-09*
*Last updated: 2026-04-12 after v1.4 milestone requirements defined*
