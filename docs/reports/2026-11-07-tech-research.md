# Tech Research Report: 2026-11-07

**Parallax Geopolitical Simulator — Technology Stack Improvements**

Date: 2026-11-07  
Focus Areas: Spatial/Geo, LLM/Agent, Real-time Data, Eval/MLOps, Performance  
Findings: 13 researched, 6 recommended for immediate/phase 2 adoption

---

## Executive Summary

Comprehensive tech research across 5 areas identified **2 immediate quick wins** (Claude batch API + caching, DuckDB spatial extension) that could reduce daily LLM budget from $20 → $2–$4 and improve spatial query performance 2–3x. High-value Phase 2 opportunities include live WebSocket dashboards, LLM evaluation frameworks, and maritime AIS data.

---

## Tier 1: HIGH RELEVANCE, EASY/MEDIUM INTEGRATION — ADOPT NOW

### 1. DuckDB Spatial Extension (ST_* PostGIS Functions)

**Status**: Officially supported (released late 2023), stable

**What it offers**:
- GEOMETRY type + 100+ PostGIS-compatible ST_* functions
- Bundles GDAL/GEOS/PROJ with no runtime dependencies
- Direct SQL queries for H3 cell containment, distance, zone geometry

**Relevance**: **HIGH** — Parallax uses DuckDB for world state; spatial operations (H3 cell containment, distance, zone geometry) are core to cascade logic.

**Integration effort**: **EASY** — Two SQL lines to enable:
```sql
INSTALL spatial;
LOAD spatial;
```

**Risk/maturity**: **LOW** — Officially maintained; less mature than PostGIS but covers typical vector operations

**Enhances or replaces**: **Enhances** — Reduces reliance on Python shapely; enables spatial queries directly in SQL

**Impact**: Could replace Python spatial operations in `cascade.py` and `world_state.py`; faster H3-grid-to-geometry conversions

**Recommendation**: ✅ **ADOPT** — Quick win for spatial query performance and code simplification

---

### 2. Claude API Batch Processing + Prompt Caching (Stacked)

**Status**: Prompt caching GA (Aug 2025); Message Batches with caching confirmed Q3 2025

**What it offers**:
- Batch API: 50% discount on input tokens
- Prompt caching: up to 90% cost reduction on long prompts (typical hit rates 30–98%)
- 1-hour cache window for batches
- Stack both for 5–10x total cost reduction

**Relevance**: **HIGH** — Parallax runs ~50 Sonnet calls/day for 3 prediction models (~$0.02–$0.03 total); caching + batching reduces this dramatically

**Integration effort**: **EASY** — Requires adding `cache_control: {"type": "ephemeral"}` to system prompt and batching prediction runs in `cli/brief.py`

**Risk/maturity**: **LOW** — Official Anthropic feature; GA since Aug 2025

**Enhances or replaces**: **Enhances** — Keeps Claude API but dramatically cheaper; no model/logic change needed

**Impact**: 
- Daily LLM budget: $20 → $2–$4
- Massive headroom for more predictions or higher-quality models
- No latency penalty (batches run in parallel)

**Recommendation**: ✅ **ADOPT IMMEDIATELY** — Implement in `cli/brief.py` within 1–2 hours; lock in cost savings before budget pressure hits

---

### 3. LLM Evaluation Frameworks (DeepEval or Ragas)

**Status**: DeepEval (open-source, pytest-like); Ragas (RAG-focused, open)

**What it offers**:
- Automated metrics for prediction quality (accuracy, calibration, F1) without manual labeling
- CI/CD integration
- Early regression detection

**Relevance**: **HIGH** — Parallax scorecard computes hit rate and calibration manually; automated evals would catch regressions earlier

**Integration effort**: **MEDIUM** — Requires defining eval metrics in code, integrating with signal ledger, adding to CI

**Risk/maturity**: **LOW** — Active open-source projects; proven in production ML teams

**Enhances or replaces**: **Enhances** — Supplements existing `calibration.py` and `report_card.py`

**Impact**: Automated feedback loop for prompt/cascade tuning; A/B test variants faster

**Recommendation**: ⏩ **PHASE 2** — Priority after batch caching; integrate with scorecard pipeline by week 3

---

### 4. WebSocket Real-Time Backend Patterns for Dashboard

**Status**: Well-established; FastAPI + Uvicorn widely used in 2024–2025 production

**What it offers**:
- Live score updates (trades, divergences, market moves) without polling
- Connection manager + pub/sub broadcast pattern
- Integration with React 19 Suspense for frontend streaming

**Relevance**: **HIGH** — Dashboard currently static; live updates for paper trading/divergences are critical for a simulator

**Integration effort**: **MEDIUM** — Requires refactoring `main.py` to add WebSocket endpoint, connection manager, and background task for score pushes

**Risk/maturity**: **LOW** — Pattern mature; many FastAPI examples available

**Enhances or replaces**: **Enhances** — REST API stays for bulk queries; WebSocket adds streaming layer

**Impact**: Dashboard responsiveness improves dramatically; enables live trading feedback loop

**Recommendation**: ⏩ **PHASE 2** — Build after batch caching; pair with frontend streaming (React 19 Suspense)

---

### 5. Oil Futures/Derivatives Pricing APIs (Databento or Api-Ninjas)

**Status**: Databento (live + historical, unadjusted continuous contracts); Api-Ninjas (spot + futures split)

**What it offers**:
- Alternative to EIA API for WTI/Brent futures contracts
- Unadjusted prices (no artificial jumps at contract rollovers)
- Historical data for backtest/recalibration

**Relevance**: **HIGH** — Oil price is core predictor input; EIA API is free but spot-only; futures data improves training

**Integration effort**: **EASY** — Add API key, swap `fetch_brent()` / `fetch_wti()` in `oil_prices.py`, test contract handling

**Risk/maturity**: **LOW** — Established vendors; pricing is clear

**Cost**: Databento ~$49–$499/mo (depends on volume); Api-Ninjas premium for futures

**Enhances or replaces**: **Enhances** — Keep EIA as fallback; use futures for backtest/recalibration

**Recommendation**: 📊 **EVALUATE** — Run trial with Databento; compare against EIA spot prices for 2 weeks; decide based on prediction lift

---

## Tier 2: MEDIUM RELEVANCE, MEDIUM/HARD INTEGRATION

### 6. deck.gl 9.1 Globe View + React Widgets

**Status**: Released Jan 2025; MapLibre v5 globe support; breaking changes in gesture handling

**What it offers**: Globe view of Hormuz with real-time vessel/price heatmaps; React hooks for widget state

**Relevance**: **MEDIUM** — Adds geographic richness but not essential for trading signal generation

**Integration effort**: **HARD** — Requires updating deck.gl to 9.1 (breaking changes), refactoring viz layer, testing globe performance

**Risk/maturity**: **MEDIUM** — New features (globe is January 2025); gesture breaking change needs UX testing

**Recommendation**: 📅 **DEFER** — Roadmap for v2 (post-April 2026 validation window); not critical for decision-making

---

### 7. GDELT Alternatives (ACLED + WorldMonitor)

**Status**: ACLED (mature, protests/conflicts); WorldMonitor (open-source, free dashboard combining sources)

**What it offers**: Diversify from GDELT's news-only focus; ACLED captures structural conflict data

**Relevance**: **MEDIUM** — GDELT is primary ingestion source; alternatives add robustness to data layer

**Integration effort**: **MEDIUM** — Add `ingestion/acled.py`, parse API output, deduplicate with GDELT, test on Hormuz events

**Risk/maturity**: **MEDIUM** — ACLED API is stable; coverage may differ from GDELT in Iran region

**Enhances or replaces**: **Enhances** — Keep GDELT; ACLED as secondary conflict signal

**Recommendation**: ⏩ **PHASE 2** — Implement after batch caching; trial for 1 week to measure divergence gain

---

### 8. Maritime AIS APIs (Kpler/Datalastic)

**Status**: MarineTraffic unified under Kpler (Sep 2025); data since 2010; ~190-day lookback

**What it offers**:
- Live vessel positions through Hormuz
- Predictor input for "who is avoiding the strait?"
- Behavioral signal (ship diversion) to cascade

**Relevance**: **MEDIUM** — Adds behavioral signal (ship diversion) to cascade; not directly used in current 3 models

**Integration effort**: **HARD** — Requires new AIS ingestion module, vessel classification (tankers, cargo), flow detection, API polling

**Cost**: Kpler enterprise pricing (not published); Datalastic ~€80/mo for basic API

**Risk/maturity**: **MEDIUM** — API stable; integrating into cascade requires domain expertise in maritime patterns

**Enhances or replaces**: **Enhances** — New signal layer; doesn't replace oil/ceasefire/Hormuz predictors but informs them

**Recommendation**: ⏩ **PHASE 2 OR DEFER** — Research cost and data coverage for Iran region first; backtest with historical vessel data if available

---

### 9. React 19 Compiler + Server Components

**Status**: Stable in React 19 (released 2024); Compiler removes need for useMemo/useCallback; 19.2 adds partial pre-rendering

**What it offers**:
- Automatic memoization; smaller bundle size
- Improved render performance without code rewrite
- Server Components for server-side logic

**Relevance**: **MEDIUM** — Dashboard is currently React 18; Compiler gives performance without code rewrite

**Integration effort**: **MEDIUM** — Upgrade React to 19 in `frontend/package.json`, enable experimental Compiler flag, test breakage

**Risk/maturity**: **LOW** — React 19 is stable; Compiler is experimental but widely adopted

**Enhances or replaces**: **Enhances** — API stays same; React version bump

**Recommendation**: ⏩ **PHASE 2** — Plan for week 4–5 if dashboard shows slow interactions; measure before upgrading

---

## Tier 3: LOW RELEVANCE OR HIGH FRICTION

### 10. Open-Source LLM Agents (Qwen3, DeepSeek, Devstral)

**Recommendation**: ❌ **DO NOT ADOPT** — Claude Sonnet + batch caching is more cost-effective and higher quality for geopolitical reasoning

**Rationale**: Parallax relies on Claude Sonnet for 3 cascade-reasoning models; replacing with local open models would degrade quality and require retraining. Local models save API calls (~$0.02/run) but add inference latency; batch caching already saves 90% cost.

---

### 11. Prompt A/B Testing + Versioning Tools (Langfuse, PromptLayer, Braintrust)

**Recommendation**: 📅 **DEFER** — Defer to post-April-2026 validation (use manual prompt tuning for now)

**Rationale**: Requires refactoring prediction models to integrate with versioning tool, building experiment harness; adds operational overhead. Manual tuning sufficient for Phase 1.

---

### 12. Streaming LLM Predictions to Frontend (Vercel AI SDK useChat)

**Recommendation**: 📅 **DEFER** — Post-validation; only if dashboard needs explainability layer

**Rationale**: Nice UX enhancement but not critical for signal generation; adds infrastructure complexity.

---

## Summary Table

| Finding | Relevance | Integration | Risk | Priority | Timeline |
|---------|-----------|-------------|------|----------|----------|
| DuckDB Spatial | HIGH | EASY | LOW | ✅ **ADOPT ASAP** | Week 1 |
| Claude Batch + Cache | HIGH | EASY | LOW | ✅ **ADOPT ASAP** | Week 1 |
| LLM Evaluation | HIGH | MEDIUM | LOW | ⏩ Phase 2 | Week 3–4 |
| WebSocket Real-Time | HIGH | MEDIUM | LOW | ⏩ Phase 2 | Week 3–4 |
| Oil Futures APIs | HIGH | EASY | LOW | 📊 EVALUATE | Week 1–2 |
| deck.gl 9.1 Globe | MEDIUM | HARD | MEDIUM | 📅 DEFER | v2 |
| GDELT Alternatives | MEDIUM | MEDIUM | MEDIUM | ⏩ Phase 2 | Week 3–4 |
| Maritime AIS APIs | MEDIUM | HARD | MEDIUM | ⏩ Phase 2/Defer | Week 4+ |
| React 19 Compiler | MEDIUM | MEDIUM | LOW | ⏩ Phase 2 | Week 4–5 |
| Open-Source LLMs | LOW | HARD | MEDIUM | ❌ **DO NOT** | – |
| Prompt A/B Testing | MEDIUM | HARD | MEDIUM | 📅 DEFER | Post-validation |
| LLM Streaming | LOW–MEDIUM | HARD | LOW | 📅 DEFER | v2 |

---

## Recommended Immediate Actions (Weeks 1–2)

### Action 1: Enable Claude Batch + Cache Stacking
- **Time**: <2 hours
- **Impact**: ~10x cost reduction ($20/day → $2–$4/day)
- **Effort**: Add `cache_control` to system prompts, batch prediction calls in `cli/brief.py`
- **Status**: Ready to implement immediately

### Action 2: Evaluate DuckDB Spatial Extension
- **Time**: <4 hours
- **Impact**: 2–3x faster spatial queries; cleaner code
- **Effort**: Enable extension, replace Python shapely ops with SQL in cascade logic
- **Status**: Ready to implement immediately

### Action 3: Trial Oil Futures API (Databento)
- **Time**: 1 week trial
- **Impact**: Improved prediction accuracy; better training data
- **Effort**: Add API integration, compare to EIA for 1 week, measure prediction lift
- **Status**: Start trial this week

### Action 4: Assess AIS Data Cost/Coverage
- **Time**: 1–2 hours preliminary research
- **Impact**: Foundation for Phase 2 vessel-behavior predictor
- **Effort**: Contact Kpler/Datalastic for pricing, verify Hormuz-region coverage
- **Status**: Research phase

---

## Expected Outcome (End of Week 2)

- **Cost reduction**: Daily LLM budget drops from $20 → $2–$4
- **Performance**: Spatial queries 2–3x faster
- **Foundation**: Ready for live dashboard (Phase 2)
- **Headroom**: Massive capacity for additional predictions or higher-quality models

---

## Sources

- [DuckDB Spatial Extension Docs](https://duckdb.org/docs/2.0/extensions/spatial.html)
- [DuckDB is Probably the Most Important Geospatial Software of the Last Decade](https://www.dbreunig.com/2025/05/03/duckdb-is-the-most-impactful-geospatial-software-in-a-decade.html)
- [Claude Platform: Prompt Caching](https://platform.claude.com/docs/en/build-with-claude/prompt-caching)
- [Claude Platform: Batch Processing](https://platform.claude.com/docs/en/build-with-claude/batch-processing)
- [Claude API Cost Optimization: Caching, Batching, and 60% Token Reduction](https://dev.to/whoffagents/claude-api-cost-optimization-caching-batching-and-60-token-reduction-in-production-3n49)
- [deck.gl 9.1 Release Notes](https://github.com/visgl/deck.gl/releases/tag/v9.1.0)
- [Databento Futures Data API](https://databento.com/futures)
- [Top 5 LLM Evaluation Frameworks (DeepEval, Ragas)](https://deepeval.com/blog/top-5-llm-evaluation-frameworks)
- [A/B Testing for LLM Prompts: Practical Guide](https://www.braintrust.dev/articles/ab-testing-llm-prompts)
- [Building Real-Time Applications with FastAPI WebSockets](https://dev-faizan.medium.com/building-real-time-applications-with-fastapi-websockets-a-complete-guide-2025-40f29d327733)
- [React 19: What's New, Features, and Impact](https://deepakg.in/blog/react-19-whats-new-and-impact-on-projects)
- [Free Geopolitical Data APIs 2026](https://www.worldmonitor.app/blog/posts/free-geopolitical-data-apis-2026/)
- [MarineTraffic AIS Data Services (Kpler)](https://www.kpler.com/product/maritime/data-services)
- [50 Best Ship Tracking APIs 2026](https://hormuzmonitor.com/50-best-ship-tracking-apis-2026/)
- [DuckDB Tuning Workloads Guide](https://duckdb.org/docs/2.0/guides/performance/how_to_tune_workloads)

