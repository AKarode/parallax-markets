# Parallax Tech Stack Research Report
**Date:** 2026-04-05  
**Focus Areas:** Spatial/Geo, LLM/Agent, Real-time Data, Eval/MLOps, Performance

---

## Executive Summary

Research identified several high-impact opportunities for strengthening Parallax's tech stack, with emphasis on cost optimization (Claude API), real-time data enrichment (AIS shipping), and evaluation infrastructure. Most recommendations are additive rather than disruptive replacements.

---

## Findings by Category

### 1. SPATIAL / GEO

#### H3 Library & Ecosystem (Status: Stable + Expanding)
- **Finding:** H3 4.4.2 released Jan 2026 with Python 3.8-3.14 support. Continued enterprise adoption (Snowflake GA, ArcGIS Pro 3.1+).
- **Relevance:** MEDIUM – Parallax already uses H3 heavily. Current pinned version in deployment working well.
- **Effort to integrate:** LOW – Already integrated. Optional: consider using workspace-level H3 operations in MotherDuck for cross-region analysis.
- **Risk/Maturity:** LOW – H3 is mature and stable.
- **Type:** Additive (optional expansion)
- **Recommendation:** Monitor for H3 4.5 release for performance improvements. No immediate action needed.

#### DuckDB Spatial Performance (Status: Significant Improvements)
- **Finding:** DuckDB v1.3.0 introduced dedicated SPATIAL_JOIN operator delivering **58× performance improvement** over previous versions. R-tree indexing for spatial queries now built-in. Analysis from March 2025 shows H3 indexing effectively optimizes large-scale queries (31M row test case: 1km radius selection).
- **Relevance:** HIGH – Parallax heavily relies on spatial queries for H3 cell lookups and filtering.
- **Effort to integrate:** MEDIUM – Requires benchmark of current query patterns, potential schema adjustments (explicit R-tree indexes on cold-path tables).
- **Risk/Maturity:** LOW – DuckDB spatial extension is production-ready.
- **Type:** Replacement (upgrade existing spatial query strategy)
- **Recommendation:** Benchmark current GDELT filtering + agent routing queries against v1.3.0+ SPATIAL_JOIN. Likely quick win for cascade engine performance. Priority: Medium.

#### deck.gl H3HexagonLayer with GPU Aggregation (Status: Recent Enhancement)
- **Finding:** deck.gl now supports GPU aggregation on HexagonLayer (enable with `gpuAggregation: true`). MapLibre GL v5 globe view fully compatible. WeatherLayers upgraded to deck.gl 9.2.6 (Feb 2026).
- **Relevance:** MEDIUM – Parallax uses H3HexagonLayer for visualization. GPU aggregation could smooth updates at high event frequency.
- **Effort to integrate:** LOW – Single flag toggle in layer props.
- **Risk/Maturity:** LOW – Stable feature, no breaking changes.
- **Type:** Additive (optimization)
- **Recommendation:** Test `gpuAggregation: true` on H3HexagonLayer in next sprint. Expect smoother rendering during high-velocity updates. Priority: Low (nice-to-have).

---

### 2. LLM / AGENT

#### Claude API Prompt Caching: Workspace Isolation & Automatic Caching (Status: Deployment Change Live)
- **Finding:** As of Feb 5, 2026, prompt caching uses workspace-level isolation (not org-level). Automatic caching available via single `cache_control` field. Cache hit costs **10% of input tokens**. Combined with Batch API (50% discount), achieves up to 95% cost reduction vs standard pricing.
- **Relevance:** HIGH – Parallax budgets ~$2-5/day under current model tiering. Prompt caching already mentioned in design but not fully exploited.
- **Effort to integrate:** LOW – Implement automatic caching in agent system prompts (largest input component, ~2-3K tokens cached, ~5-min TTL). Requires flag in request builder.
- **Risk/Maturity:** LOW – Feature live, workspace isolation ensures no data bleed.
- **Type:** Optimization (reduction in existing spend)
- **Recommendation:** **PRIORITY: HIGH.** Implement automatic prompt caching for all agent system prompts (v1.2.0+). Expected savings: ~40-60% reduction in input token costs for repeat-activation agents. Estimated monthly impact: $25-40 savings.

#### Batch API for Eval Meta-Agent (Status: Cost-Saving Feature Available)
- **Finding:** Claude Batch API available with 50% discount on input/output tokens. Suitable for async tasks (eval meta-agent prompt refinement, overnight calibration checks).
- **Relevance:** MEDIUM – Eval pipeline currently runs cron-based once/day. Batch API perfect for non-urgent eval jobs.
- **Effort to integrate:** MEDIUM – Requires async job queue for batch submissions. Wrapper around batch API endpoints.
- **Risk/Maturity:** LOW – Batch API stable, widely adopted.
- **Type:** Additive (new optimization path)
- **Recommendation:** Route daily eval meta-agent calls (prompt suggestions) through Batch API instead of on-demand. Estimated savings: ~$0.15-0.25/day. Priority: Medium (low effort, modest savings).

#### Alternative LLM Models for Cost Reduction (Status: Viable Options Exist)
- **Finding:** DeepSeek V3.2 costs $0.14/$0.28 per 1M tokens (100x cheaper than GPT-5 output). Gemini 2.0 Flash-Lite at $0.075/$0.30. Qwen2.5-Coder-32B (open-source, local) competitive on coding tasks. Claude Haiku 4.5 still strong for sub-actor tasks.
- **Relevance:** MEDIUM-LOW – Parallax already uses Claude API strategically (Haiku for sub-actors, Sonnet/Opus for country agents). Full migration to alternative models carries risk of behavioral degradation.
- **Effort to integrate:** HIGH – Requires testing alternative models on prediction accuracy, prompt adaptation.
- **Risk/Maturity:** MEDIUM – DeepSeek/Gemini work but haven't been A/B tested on geopolitical forecasting tasks. Behavioral characteristics differ significantly from Claude.
- **Type:** Potential replacement (exploratory)
- **Recommendation:** Do NOT migrate to cheaper alternatives for main agent swarm yet. Instead: **A/B test DeepSeek V3.2 or Gemini 2.5 Flash on a subset of sub-actors (Iran/IRGC Navy only) in isolated sandbox mode**. Measure prediction accuracy vs current Haiku baseline. If parity achieved, can roll out to remaining sub-actors. Priority: Low (exploratory, requires A/B framework to be mature first).

---

### 3. REAL-TIME DATA

#### AIS (Automatic Identification System) Shipping Data Integration (Status: Mature Ecosystem)
- **Finding:** Multiple real-time AIS providers: MarineTraffic (largest network, 13k+ receivers), VesselFinder, aisstream.io (WebSocket), Datalastic, NavAPI. All offer JSON/XML APIs with live vessel positions, ETA, speed, cargo data.
- **Relevance:** HIGH – Hormuz corridor is critical to scenario. Live AIS data complements GDELT (text events) with actual vessel movements. Searoute is visualization-only; real AIS adds operational ground truth.
- **Effort to integrate:** MEDIUM – Add new data ingestion pipeline (separate from GDELT). Map vessel tracks to H3 cells. Requires schema change (vessel_movements table in DuckDB).
- **Risk/Maturity:** LOW – AIS is stable, widely used. Cost: typically $100-500/month for API access.
- **Type:** Additive (new data source)
- **Recommendation:** **PRIORITY: HIGH.** Integrate aisstream.io (WebSocket-native, real-time, good for live mode). Use vessel positions in Hormuz resolution band (Res 7-8 cells) to feed into cascade engine. Triggers for: vessel seizures (speed drop to 0), rerouting around strait (direction change), insurance impact (proximity to conflict zones). Phase 1 Phase 2: ingest full AIS, train classifier for "blocked vessel" detection. Priority: High (strong signal for prediction accuracy).

#### Oil Price API Diversification (Status: Multiple Options)
- **Finding:** EIA API reliable but subject to lag/outages during government reporting. OilPriceAPI provides real-time spot prices as alternative (guaranteed SLA). FRED offers clean historical WTI/Brent. Combined approach recommended: OilPriceAPI for real-time spot, EIA for official benchmarks + inventory data.
- **Relevance:** MEDIUM – Current design uses EIA/FRED. OilPriceAPI as fallback improves reliability during crises (when data matters most).
- **Effort to integrate:** LOW – Add secondary API call in price feed pipeline. Fallback logic if EIA latency > threshold.
- **Risk/Maturity:** LOW – OilPriceAPI widely used, mature service.
- **Type:** Additive (redundancy + latency improvement)
- **Recommendation:** Add OilPriceAPI as fallback for real-time oil prices. Falls back to EIA if OilPriceAPI unavailable. Low effort, improves reliability. Priority: Low (nice-to-have, EIA is adequate for Phase 1).

---

### 4. EVAL / MLOPS

#### LLM Evaluation Frameworks & Prompt Versioning (Status: Mature Ecosystem)
- **Finding:** Braintrust, Langfuse, ZenML offer A/B testing, prompt versioning, and evaluation tracking. Key patterns: golden test set (50-200 cases), automated format assertions, semantic metrics, offline evaluation before production, canary deployment (5-10% traffic), rollback on metric regression. 2025 best practice: compare prompt versions over 7-day rolling window.
- **Relevance:** HIGH – Parallax design spec includes prompt versioning (semver) and A/B comparison, but no external eval framework. Langfuse/Braintrust could formalize this.
- **Effort to integrate:** MEDIUM – Parallax already has `predictions` table with ground truth and scores. Could export to external tool or build minimal in-house wrapper (more practical for closed scenario).
- **Risk/Maturity:** LOW – These frameworks are stable, widely adopted.
- **Type:** Additive (infrastructure standardization)
- **Recommendation:** **PRIORITY: MEDIUM.** Before Phase 1 eval cron goes live, implement in-house eval dashboard that replicates Langfuse/Braintrust features: (1) prompt version comparison table with accuracy metrics per version, (2) rolling 7-day window decision, (3) manual rollback UI. Can be minimal (read `eval_results` + `agent_prompts` tables, render in React panel). Enables data-driven prompt refinement. Priority: Medium (required for feedback loop, can be built in-house cheaply).

#### Evaluation Metrics: Calibration Scoring (Status: Defined in Design)
- **Finding:** Parallax design mentions calibration score ("0.8 confidence should be right ~80% of the time") but implementation not detailed. Best practice: Brier score, Expected Calibration Error (ECE), log-loss for probabilistic predictions. These are standard metrics across Braintrust/Langfuse.
- **Relevance:** MEDIUM – Already planned in design. Implementation detail.
- **Effort to integrate:** LOW – Standard ML metrics, easy to compute from prediction_id + actual outcome.
- **Risk/Maturity:** LOW – Well-established metrics.
- **Type:** Implementation detail
- **Recommendation:** Use Brier score + ECE for calibration assessment. Compute daily in eval cron. Alert admin if ECE exceeds 0.15 (agent is overconfident/underconfident). No code change needed until eval cron is built. Priority: Low (covered by Phase 1 eval framework).

---

### 5. PERFORMANCE

#### WebSocket Batching & React State Decoupling (Status: Known Pattern, Already Designed)
- **Finding:** 2025 best practices: batch WebSocket updates (100ms buffer), decouple hex data (useRef) from React state, virtualize large lists, sample real-time streams (human perception ~200ms floor). Parallax design doc already includes batching and useRef strategy.
- **Relevance:** MEDIUM – Already specified in design (Section 5, render performance). Confirms approach is sound.
- **Effort to integrate:** LOW – Already designed, verification during implementation.
- **Risk/Maturity:** LOW – Pattern proven across multiple dashboards.
- **Type:** Confirmation (no change)
- **Recommendation:** Stick with design. No changes. Priority: None.

#### React 19 + Vite Optimization (Status: Latest Available)
- **Finding:** React 19 includes compiler-driven optimizations. Vite 6 released with faster dependency pre-bundling. 2025 guidance: use TanStack Query for data fetching, Zustand for state, virtualization library (react-window) for lists.
- **Relevance:** LOW – Current stack (React + Vite) is already optimized. Incremental improvements only.
- **Effort to integrate:** LOW – Update React + Vite to latest versions, test.
- **Risk/Maturity:** LOW – Stable releases.
- **Type:** Additive (incremental optimization)
- **Recommendation:** Update to React 19 + Vite 6 during Phase 1 finalization if schedule permits. Otherwise, Phase 2. Priority: Low.

---

## Top 3 Recommendations (Ranked by Impact + Effort)

### 1. **Implement Prompt Caching for Claude API (HIGH IMPACT, LOW EFFORT)**
**What:** Enable automatic prompt caching on all agent system prompts.  
**Why:** System prompts are the largest input component (~2-3K tokens, repeated every sub-actor call). With caching, repeated calls pay 10% of token cost. Estimated monthly savings: $25-40 (reduces $2-5/day budget to ~$1-3/day).  
**How:** Add `cache_control: {"type": "ephemeral"}` to request body in agent caller. Requires 1-2 hours of dev work.  
**Risk:** None. Feature live, fully supported.  
**Timeline:** Implement before Phase 1 launch. Quick ROI.

### 2. **Integrate Real-Time AIS Data (Shipping Movements) via aisstream.io (HIGH IMPACT, MEDIUM EFFORT)**
**What:** Ingest live vessel positions and movements for Hormuz corridor. Map to H3 cells (Res 7-8). Feed into cascade engine.  
**Why:** Complements GDELT (text events) with ground truth. Adds precision to blockade/rerouting predictions. Example: detect vessel speed anomaly (possible seizure/forced reroute) before GDELT picks it up.  
**How:** Add WebSocket connection to aisstream.io. Parse vessel JSON. Map positions to H3. Insert into new `vessel_movements` table. Trigger agent rules: if vessel_speed_anomaly → escalation signal.  
**Cost:** ~$100-200/month for aisstream API.  
**Risk:** Medium. New ingestion pipeline, potential data schema complexity. Mitigate: start with Gulf of Oman bounding box only (100-200 vessels), expand after validation.  
**Timeline:** 2-3 weeks (data pipeline + schema + integration tests). Phase 1 Phase 2.

### 3. **Build In-House Eval Dashboard for Prompt Versioning & A/B Comparison (MEDIUM IMPACT, MEDIUM EFFORT)**
**What:** React dashboard that compares agent prompt versions side-by-side: accuracy, calibration, trending over 7-day rolling window, manual rollback UI.  
**Why:** Closes feedback loop for prompt refinement. Enables data-driven A/B testing (new version vs incumbent). Parallax design specifies this but no implementation yet.  
**How:** Read `eval_results` + `agent_prompts` + `predictions` tables. Group by agent_id + prompt_version. Compute metrics (direction accuracy, magnitude accuracy, Brier score, ECE). Display as comparison table + sparklines. Add "Rollback" button (update `agent_prompts.active_version`).  
**Risk:** Low. All data already in schema.  
**Timeline:** 1-2 weeks (mostly React UI work). Can be built in parallel with eval cron (depend on same schema).

---

## Sources

### Spatial / Geospatial
- [H3 Official](https://h3geo.org/)
- [H3 GitHub](https://github.com/uber/h3)
- [H3 PyPI (v4.4.2, Jan 2026)](https://pypi.org/project/h3/)
- [DuckDB Spatial Queries + R-tree & H3 Indexing (Mar 2025)](https://aetperf.github.io/2025/03/04/Spatial_queries_in_DuckDB_with_R-tree_and_H3_indexing.html)
- [DuckDB Ecosystem Newsletter (Sep 2025)](https://motherduck.com/blog/duckdb-ecosystem-newsletter-september-2025/)
- [deck.gl What's New](https://deck.gl/docs/whats-new)
- [deck.gl MapLibre Integration](https://deck.gl/docs/developer-guide/base-maps/using-with-maplibre)

### LLM / API
- [Claude API Prompt Caching Docs](https://platform.claude.com/docs/en/build-with-claude/prompt-caching)
- [Claude API Pricing 2026](https://platform.claude.com/docs/en/about-claude/pricing)
- [Claude Batch API Cost Optimization Guide](https://claudelab.net/en/articles/api-sdk/claude-api-batch-processing-cost-optimization)
- [Local LLMs & Alternatives to Claude (2026)](https://agentnativedev.medium.com/local-llms-that-can-replace-claude-code-6f5b6cac93bf)
- [LLM Pricing Comparison 2026](https://costgoat.com/compare/llm-api)
- [DeepSeek & Open-Source Alternatives (2026)](https://www.bitdoze.com/best-open-source-llms-claude-alternative/)

### Real-Time Data
- [MarineTraffic AIS API](https://www.kpler.com/product/maritime/data-services)
- [VesselFinder Real-Time AIS Data](https://www.vesselfinder.com/realtime-ais-data)
- [aisstream.io WebSocket AIS](https://aisstream.io/)
- [Datalastic Vessel Tracking](https://datalastic.com/)
- [NavAPI AIS Positions](https://navapi.com/ais-positions-api/)
- [Vessel Tracking API Integration 2025](https://www.seavantage.com/blog/vessel-tracking-api-integration-guide)
- [EIA Open Data](https://www.eia.gov/opendata/)
- [OilPriceAPI as EIA Alternative](https://docs.oilpriceapi.com/compare/eia-alternative)
- [FRED WTI Crude Oil](https://fred.stlouisfed.org/series/DCOILWTICO)

### Eval / MLOps
- [Braintrust A/B Testing](https://www.braintrust.dev/articles/ab-testing-llm-prompts)
- [Langfuse Prompt Management & A/B Testing](https://langfuse.com/docs/prompt-management/features/a-b-testing)
- [Best LLM Evaluation Tools 2025](https://www.zenml.io/blog/best-llm-evaluation-tools)
- [Top 5 Prompt Versioning Tools 2025](https://www.braintrust.dev/articles/best-prompt-versioning-tools-2025)
- [Evaluation-Driven Iteration for LLM Apps](https://arxiv.org/html/2601.22025v1)
- [A/B Testing LLM Models in Production](https://www.traceloop.com/blog/the-definitive-guide-to-a-b-testing-llm-models-in-production)

### Performance
- [WebSocket Optimization for Real-Time Dashboards](https://www.segevsinay.com/blog/real-time-dashboard-performance)
- [React Performance Best Practices 2025](https://dev.to/alex_bobes/react-performance-optimization-15-best-practices-for-2025-17l9)
- [Building Real-Time Dashboards with React & WebSockets](https://www.wildnetedge.com/blogs/building-real-time-dashboards-with-react-and-websockets)

---

## Next Steps

1. **This week:** Implement prompt caching (Rec #1). Code change is trivial; impact is substantial.
2. **Next week:** Prototype AIS data ingestion (Rec #2). Evaluate aisstream.io in test environment. Cost-benefit analysis.
3. **During eval cron build:** Implement eval dashboard (Rec #3). Minimal scope: version comparison table + rollback button.

**Report compiled:** 2026-04-05 14:30 UTC
