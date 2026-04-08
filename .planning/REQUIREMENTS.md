# Requirements: Parallax

**Defined:** 2026-04-08
**Core Value:** Find mispriced prediction market contracts by reasoning about second-order cascade effects -- validated via paper trading P&L.

## v1 Requirements

Requirements for initial release. Each maps to roadmap phases.

### Contract Registry (Phase 1)

- [ ] **REG-01**: Contract registry in DuckDB stores ticker, source, event_ticker, title, resolution_criteria, resolution_date, is_active for every tracked contract
- [ ] **REG-02**: Proxy classification per model type (ProxyClass enum: DIRECT, NEAR_PROXY, LOOSE_PROXY, NONE) stored in contract_proxy_map table
- [ ] **REG-03**: MappingPolicy replaces `_map_predictions_to_markets()` -- evaluates all contracts for each prediction, applies confidence discount by proxy class, refuses NONE mappings
- [ ] **REG-04**: Signal ledger persists every signal (model claim, contract mapped, proxy class, market state, trade decision, resolution outcome) as append-only records
- [ ] **REG-05**: Pipeline integration -- `brief.py` uses MappingPolicy + SignalLedger instead of heuristic ticker matching

### Prediction Persistence (Phase 2)

- [ ] **PERS-01**: Every PredictionOutput (probability, reasoning, news context, cascade inputs) persisted in DuckDB with timestamp and run_id
- [ ] **PERS-02**: Resolution checker polls Kalshi/Polymarket APIs for settled contracts, backfills signal_ledger with resolution_price and realized_pnl
- [ ] **PERS-03**: Calibration queries: hit rate by proxy class, calibration curve by probability bucket, edge decay by effective_edge bucket
- [ ] **PERS-04**: At least 7 days of prediction data accumulated before calibration analysis is considered valid

### Paper Trading Evaluation (Phase 3)

- [ ] **TRAD-01**: Paper trades tracked at contract level with entry_price, resolution_price, realized_pnl, hold_duration
- [ ] **TRAD-02**: P&L segmented by proxy_class -- DIRECT, NEAR_PROXY, LOOSE_PROXY reported separately
- [ ] **TRAD-03**: Summary report: total P&L, win rate, avg edge at entry, Sharpe-like ratio, statistical significance test
- [ ] **TRAD-04**: Automated daily pipeline runs (cron/scheduled) accumulate prediction + signal history without manual intervention
- [ ] **TRAD-05**: Calibration-driven tuning: adjust discount_map values, min_edge threshold, and model prompts based on accumulated calibration data (hit rate by proxy class, edge decay)

### Deployment Fixes (Phase 4)

- [ ] **DEPLOY-01**: `docker compose up` starts backend, health check passes within 30 seconds
- [ ] **DEPLOY-02**: FastAPI GET endpoints (`/api/predictions`, `/api/markets`, `/api/divergences`, `/api/trades`) return real pipeline data
- [ ] **DEPLOY-03**: API failure handling: retry with exponential backoff for Kalshi/GDELT/EIA rate limits, fallback to cached data
- [ ] **DEPLOY-04**: Structured logging (JSON) with run_id correlation across pipeline stages

### Second Thesis (Phase 5)

- [ ] **THESIS-01**: Framework for adding new thesis domains: new prediction model + contract registry entries + proxy classifications
- [ ] **THESIS-02**: At least one additional thesis domain (e.g., energy macro, US election, crypto regulation) with active contracts
- [ ] **THESIS-03**: New model integrated into existing pipeline (brief.py, divergence detector, paper trader)

## Out of Scope

| Feature | Reason |
|---------|--------|
| 50-agent swarm | Replaced by 3 focused prediction models -- killed April 2026 |
| H3 spatial visualization / deck.gl map | Deleted -- CLI tool does not need maps |
| Frontend dashboard | Deleted -- CLI-first, API endpoints for future UI |
| WebSocket real-time updates | Not needed for CLI tool |
| EventBus / TickOrchestrator | Never built -- pipeline is sequential |
| Multi-user authentication | Single-analyst tool |
| Real-money trading | Paper trading only until edge is proven via P&L |
| Mobile app | Desktop CLI only |
| More than 3 prediction models for Iran thesis | Focus on quality over quantity |
| Free-text predictions | Cannot be scored automatically; structured output only |
| Latency arbitrage | Edge is reasoning depth, not speed |

## Traceability

| Requirement | Phase | Status |
|-------------|-------|--------|
| REG-01 | Phase 1 | Pending |
| REG-02 | Phase 1 | Pending |
| REG-03 | Phase 1 | Pending |
| REG-04 | Phase 1 | Pending |
| REG-05 | Phase 1 | Pending |
| PERS-01 | Phase 2 | Pending |
| PERS-02 | Phase 2 | Pending |
| PERS-03 | Phase 2 | Pending |
| PERS-04 | Phase 2 | Pending |
| TRAD-01 | Phase 3 | Pending |
| TRAD-02 | Phase 3 | Pending |
| TRAD-03 | Phase 3 | Pending |
| TRAD-04 | Phase 3 | Pending |
| TRAD-05 | Phase 3 | Pending |
| DEPLOY-01 | Phase 4 | Pending |
| DEPLOY-02 | Phase 4 | Pending |
| DEPLOY-03 | Phase 4 | Pending |
| DEPLOY-04 | Phase 4 | Pending |
| THESIS-01 | Phase 5 | Pending |
| THESIS-02 | Phase 5 | Pending |
| THESIS-03 | Phase 5 | Pending |

**Coverage:**
- v1 requirements: 19 total
- Mapped to phases: 19
- Unmapped: 0

---
*Requirements defined: 2026-04-08*
*Last updated: 2026-04-08 after architecture pivot and dead code pruning*
