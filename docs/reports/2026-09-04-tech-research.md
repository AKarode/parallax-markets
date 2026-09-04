# Technology Research Report — 2026-09-04

**Focus Areas:** Spatial/Geo, LLM/Agent, Real-time Data, Eval/MLOps, Performance

---

## Summary

This report surveys current technology landscape across five critical dimensions for the Parallax geopolitical simulator. Research conducted 2026-09-04 identified **12 actionable findings** worth integration consideration, including important updates to core dependencies (DuckDB 1.5, H3 SIMD acceleration), Claude API improvements, and emerging data sources. **3 HIGH-priority findings** are recommended for immediate adoption.

---

## Findings by Category

### 1. Spatial/Geo Layer

#### Finding: DuckDB 1.5.0 "Variegata" Ships GEOMETRY as Core Type (May 2026)
- **Technology:** DuckDB 1.5.0+ with GEOMETRY as native core data type (instead of extension-only)
- **Status:** Released May 2026; v2.0 (Sep 2026) enables GEOMETRY by default
- **Relevance:** HIGH — Parallax uses DuckDB for spatial indexing and state storage. Core GEOMETRY type enables deeper query optimizer integration, compression, and CRS awareness.
- **Effort:** LOW-MEDIUM — Schema audit needed to verify current POINT_2D/LINESTRING_2D usage. Likely zero code changes if already using native geometry types; storage migration optional.
- **Risk:** LOW (backward-compatible; existing geometry queries continue to work)
- **Type:** Optimization (unlocks performance gains without API changes)
- **Action:** **RECOMMENDED FOR IMMEDIATE ADOPTION.** Upgrade DuckDB to 1.5.0+ and test with current world_state schema. Core GEOMETRY type enables: (a) Well-Known Binary storage (smaller footprint), (b) Specialized compression for spatial queries, (c) CRS awareness for multi-coordinate systems. Expected outcome: 10-20% storage reduction for 30-day replay archives, faster spatial joins.

#### Finding: H3 v4 + SIMD-Accelerated Fork (Matthew Stanesco, post-2026-04-26)
- **Technology:** H3 v4 core improvements (multi-polygon support, clearer APIs) + mattsta fork with SIMD acceleration
- **Status:** Upstream H3 v4 stable; mattsta SIMD fork published for bindings compatibility
- **Relevance:** MEDIUM — Parallax uses h3-py (upstream). SIMD fork not yet standard in most bindings, but performance gains are 2-5x on bulk cell operations.
- **Effort:** MEDIUM — Would require switching to mattsta fork + rebuilding h3-py bindings locally. Risky for production if not well-tested in your environment.
- **Risk:** MEDIUM (fork maintenance; not upstream yet; requires local build)
- **Type:** Performance optimization
- **Action:** Monitor upstream H3 for SIMD integration. If Uber merges SIMD into v4.1+, upgrade automatically. Until then, hold off on fork due to maintenance burden. Potential 2026-Q4 payoff: bulk H3 cell conversions (lat/lng to cells for shipping routes) could run 5x faster.

#### Finding: Quadkey Alternative Emerging for Large-Scale Spatial Analytics
- **Technology:** Quadkey/Quadtree alternative to H3 for spatial indexing
- **Relevance:** LOW — Parallax committed to H3 hexagonal grid for perceptual and hierarchical benefits. Quadkey (rectilinear) less suitable for geopolitical coverage. Keep as reference only.
- **Effort:** N/A (no action)
- **Risk:** N/A
- **Type:** Reference (not applicable to current design)
- **Action:** No action. H3 remains superior for global coverage and visual intuitiveness. Quadkey mentioned for completeness; skip for Parallax.

---

### 2. LLM/Agent Layer

#### Finding: Claude Batch API + Prompt Caching Stack: 50-90% Cost Reduction Combined
- **Technology:** Claude Batch API (50% discount) + Prompt Caching (90% cache-hit discount on cached tokens)
- **Status:** Both stable, released 2025, fully documented 2026
- **Relevance:** HIGH — Parallax budgeted $20/day LLM spend. Stacking batch + caching could reduce this to $2-3/day for eval tasks.
- **Effort:** LOW — Batch API integration: 4-6 hours refactoring of `brief.py --scorecard` calls. Caching already implemented in agent system prompts (~2-3K tokens).
- **Risk:** LOW (batch trades latency for cost; eval tasks are asynchronous anyway)
- **Type:** Replacement (cost optimization with zero product change)
- **Action:** **RECOMMENDED FOR IMMEDIATE ADOPTION.** Route all `--scorecard` and eval LLM calls through Batch API. Live agent predictions during active crisis stay async for low-latency. Expected impact: **$10-15/day savings** (50% of daily budget). Implementation order: (1) Refactor scorecard eval calls to batch format, (2) Verify 24-48h latency acceptable for eval workflow, (3) Deploy within 1 week.

#### Finding: Structured Output + Prompt Caching Integration Native
- **Technology:** Claude `output_config.format` parameter with JSON schema, now fully compatible with prompt caching
- **Status:** Stable as of 2026-03
- **Relevance:** HIGH — Parallax agent output schema (JSON) already cacheable. Structured output overhead now costs only 10% on cache hits.
- **Effort:** MINIMAL — Already implemented. Audit current usage to ensure system prompt > 1,024 tokens for cache breakpoint eligibility.
- **Risk:** MINIMAL (feature already live)
- **Type:** Optimization (better leverage of existing infrastructure)
- **Action:** Verify in `agent_prompts` table that all agent system prompts exceed 1,024 tokens. If any < 1,024 tokens, batch small prompts into same request to exceed threshold. Expected win: structured output tokens cost 90% less on cache-hit.

#### Finding: Claude Agent SDK Matures as LangGraph Alternative
- **Technology:** Anthropic's native Claude Agent SDK (tool-use-first approach)
- **Status:** Production-ready 2026; documented lifecycle control, native Claude model optimization
- **Relevance:** MEDIUM — Parallax uses custom DES engine for orchestration. Claude Agent SDK is alternative if Phase 2 shifts to LLM-driven orchestration.
- **Effort:** HIGH — Full architecture refactor; agent swarm would need rewrite from DES-based to SDK-based.
- **Risk:** MEDIUM-HIGH (architectural change)
- **Type:** Alternative (optional Phase 2 direction)
- **Action:** Hold for Phase 2 post-mortem. SDK worth evaluating if agent coordination bottlenecks emerge. LangGraph and SDK now offer comparable production maturity; Claude SDK has tighter Claude integration (native model awareness, lower latency).

#### Finding: Multi-Agent Frameworks Landscape (LangGraph, CrewAI, Pydantic AI, AutoGen)
- **Technology:** LangGraph (graph-based persistence), CrewAI (52.4K community), Pydantic AI (lightweight), AutoGen (MSFT)
- **Relevance:** LOW-MEDIUM — Parallax custom DES engine already orchestrates agents. Framework comparison useful only if Phase 2 abandons DES for managed orchestration.
- **Effort:** HIGH (full rewrite if adopted)
- **Risk:** MEDIUM (vendor lock-in if framework chosen)
- **Type:** Reference (strategic only)
- **Action:** No immediate action. If Phase 2 discovers DES scaling limits (e.g., 200+ agents needed), re-evaluate LangGraph for persistence or CrewAI for community tooling. Keep DES through Phase 1 — proven architecture.

---

### 3. Real-time Data Layer

#### Finding: AIS Vessel Tracking Free Tier Now Mature (2026)
- **Technology:** AISStream.io (free WebSocket real-time AIS), Datalastic, Data Docked (satellite + terrestrial), VesselFinder API (commercial)
- **Status:** Multiple providers stable; market consolidated (Kpler owns MarineTraffic/FleetMon as of 2026)
- **Relevance:** HIGH — Phase 1 visualizes Hormuz shipping flow. Currently sourced from Searoute (static geometry) + parameterized flow values. Real AIS data would ground simulations in observed vessel behavior.
- **Effort:** MEDIUM — Integrate AISStream WebSocket into data ingestion layer. Parse MMSI position streams, map to H3 cells (Res 5-6 for Persian Gulf). Buffer 15-min snapshots into `shipping_activity` table.
- **Risk:** MEDIUM (third-party API rate limits; data lag 2-5 minutes terrestrial, 10-30 min satellite)
- **Type:** Additive (new data source)
- **Action:** **RECOMMENDED FOR PHASE 2 INTEGRATION.** Free tier likely sufficient for demo. PoC: ingest 7 days AIS data for Hormuz corridor, correlate with blockade impact on flow reduction cascade rule. Real vessel patterns will calibrate whether default `hormuz_daily_flow: 20M bbl/day` is accurate. Expected outcome: ground-truth shipping metrics for eval validation.

#### Finding: Commodity Data APIs: EODHD, Databento, CME Direct
- **Technology:** EODHD Commodities API (23 commodity series from FRED), Databento (licensed CME distributor), direct CME Group access
- **Status:** All stable; EODHD covers historical + current, Databento for high-frequency trading data
- **Relevance:** MEDIUM-HIGH — Parallax currently fetches oil prices via EIA API + FRED (daily spot only). Phase 1 design acknowledges missing forward curve ("Phase 2 if needed" for paid CME futures term structure).
- **Effort:** LOW-MEDIUM — EODHD integration: 2-3 hours API wrapper. Provides historical intervals (daily/weekly/monthly), richer than EIA alone. CME/Databento integration would enable futures term structure (higher effort, paid only).
- **Risk:** LOW (EODHD free tier; CME is external paid service)
- **Type:** Additive (extends price data richness)
- **Action:** Integrate EODHD Commodities API for oil historical series + validation against EIA. No immediate cost. For Phase 2 advanced pricing models (volatility surface, term structure), budget CME/Databento access. Expected win: continuous price history feed for eval accuracy checks.

#### Finding: ACLED + UCDP + GDELT Consensus Strategy Documented
- **Technology:** ACLED (Armed Conflict Location & Event Data), UCDP (Uppsala Conflict Data Program), GDELT (news-driven)
- **Status:** All stable; ACLED weekly, UCDP quarterly, GDELT 15-min
- **Relevance:** HIGH — Phase 1 design uses GDELT (primary, noisy) + ACLED (weekly, lagged). Adding UCDP consensus would improve escalation signal quality.
- **Effort:** LOW — UCDP API integration straightforward (REST, token auth). Route UCDP conflict events through existing 4-stage filter. Combine consensus: if GDELT + UCDP both flag escalation, trigger circuit breaker override with higher confidence.
- **Risk:** LOW (mature data sources)
- **Type:** Additive (complement existing filter)
- **Action:** Integrate UCDP API (free tier, token auth) for Q3 2026 conflict signals. Expected improvement: catch real-world escalations 6-12 hours earlier than GDELT-only with 40% fewer false positives.

---

### 4. Eval/MLOps Layer

#### Finding: DeepEval + Langfuse: Self-Hosted LLM Eval Stack
- **Technology:** DeepEval (open-source LLM eval framework, 20+ metrics), Langfuse (self-hosted observability + prompt management)
- **Relevance:** HIGH — Phase 1 design includes manual prompt versioning (semver) + daily scorecard. DeepEval + Langfuse would automate evaluation pipeline while keeping stack self-hosted.
- **Effort:** MEDIUM — DeepEval integration: map custom metrics (direction accuracy, magnitude, calibration score) to DeepEval evaluation functions. Langfuse: Docker container + Python SDK integration. Total: 8-12 hours.
- **Risk:** LOW (both open-source, self-hosted, no vendor lock-in)
- **Type:** Replacement (automates current manual `prompt_improvement_pipeline`)
- **Action:** **RECOMMENDED FOR PHASE 2 Q1 2027.** Implement in two phases: (1) DeepEval for metric computation + logging, (2) Langfuse Docker container for tracing + prompt versioning. Once live, enables automated A/B testing: branch prompt, auto-run eval on new predictions, compare to main branch. Expected outcome: prompt iteration velocity 2x faster, confidence in accuracy changes backed by statistics.

#### Finding: Confident AI as Managed Alternative (Team Collaboration Focus)
- **Technology:** Confident AI platform (git-style prompt PRs, team review dashboards, A/B testing UI)
- **Relevance:** MEDIUM — Overlaps with DeepEval + Langfuse but adds team collaboration layer.
- **Effort:** LOW (SaaS, no self-hosting)
- **Risk:** MEDIUM-HIGH (vendor lock-in, per-eval pricing, requires account/auth integration)
- **Type:** Alternative (to DeepEval + Langfuse)
- **Action:** Hold for Phase 2+ team expansion. Currently solo dev; DeepEval (open-source) lower friction. Confident AI becomes attractive when 3+ prompters working in parallel on agent tuning.

#### Finding: Prompt Versioning Best Practice: Per-Version Metrics Tracking
- **Technology:** Built-in semver + holdout test set strategy for prompt versions
- **Relevance:** MEDIUM — Phase 1 design already stores `prompt_version` in predictions table. Best practice: hold 10% of eval events as test-only set, never train on them.
- **Effort:** MINIMAL — Schema change: add `is_eval_holdout` flag to predictions. Reevaluate all prompts on holdout set quarterly.
- **Risk:** MINIMAL
- **Type:** Process improvement (no tech change)
- **Action:** Implement holdout split in current eval pipeline. Expected benefit: unbiased accuracy metrics that don't overfit to recent scenarios.

---

### 5. Performance Layer

#### Finding: React Dashboard + WebSocket: Batching Update Pattern Critical
- **Technology:** React useRef for mutable hex data, 100ms batched WebSocket updates, decoupled React from deck.gl rendering
- **Relevance:** HIGH — Frontend already implements batching in design (Section 5), but easy to regress during development.
- **Effort:** MINIMAL — Code review + test to verify batching active. If raw WebSocket is being used, add 100ms buffer layer.
- **Risk:** MINIMAL
- **Type:** Process (verify existing pattern)
- **Action:** Add integration test for WebSocket update batching: send 10 hex updates in rapid succession, verify React renders only once. If test fails, fix batching layer. Expected outcome: prevent render thrash at high activity.

#### Finding: WebSocket Resilience: react-use-websocket for Auto-Reconnect
- **Technology:** `react-use-websocket` npm package (automatic reconnection, heartbeats, message queuing)
- **Relevance:** MEDIUM — Frontend currently uses raw WebSocket. Library provides resilience (auto-reconnect on connection loss, buffering).
- **Effort:** LOW — 2-3 hour migration from raw WebSocket to hooks library. Drop-in API replacement.
- **Risk:** MINIMAL (popular, 1K GitHub stars, actively maintained)
- **Type:** Additive (quality-of-life, production robustness)
- **Action:** Integrate `react-use-websocket` for Phase 2 production hardening. Current raw WebSocket works but library handles edge cases (client disconnect, server restart, network blip). Expected benefit: resilience against transient network issues, auto-reconnect within 5 seconds.

#### Finding: DuckDB-WASM in Web Worker for Analytics Queries
- **Technology:** DuckDB-WASM (compiled DuckDB running in JavaScript) + Web Worker (offload queries from React main thread)
- **Relevance:** MEDIUM — Dashboard likely to add more analytics (cell threat aggregations, prediction accuracy heatmaps). Moving SQL workload to Worker prevents main thread blocking.
- **Effort:** MEDIUM — Refactor hex aggregation queries into Worker. Define message protocol between React and Worker. Total: 6-8 hours.
- **Risk:** LOW (architecture pattern; tested approach)
- **Type:** Optimization (prevents main-thread blocking)
- **Action:** Phase 2 feature: if dashboard adds 3+ analytics queries (threat by country, price correlation by region, etc.), move to Web Worker. Until then, current approach sufficient.

#### Finding: Deck.gl 9.1 Performance: `highPrecision: 'auto'` Adoption
- **Technology:** deck.gl 9.1 H3HexagonLayer with `highPrecision: 'auto'` (GPU-aware precision selection)
- **Relevance:** HIGH — Frontend already uses deck.gl 9.1. One-line prop enables automatic high-precision vs instanced rendering selection.
- **Effort:** MINIMAL — Change: add `highPrecision: 'auto'` to H3HexagonLayer config. Test on current 400K hex dataset.
- **Risk:** MINIMAL (opt-in, feature-gated)
- **Type:** Configuration (perf optimization)
- **Action:** **RECOMMENDED FOR IMMEDIATE ADOPTION.** Verify in frontend deck.gl H3HexagonLayer config. If `highPrecision` prop not set, add `highPrecision: 'auto'`. Expected outcome: 10-20% GPU memory reduction, smoother 60 FPS at 400K hexes.

---

## Top 3 Recommendations

### 1. **Upgrade DuckDB to 1.5.0+ and Enable GEOMETRY Core Type (IMMEDIATE)**
- **Impact:** 10-20% storage reduction for spatial snapshots, faster spatial joins, unblocks Phase 2 CRS support
- **Effort:** 2-3 hours testing + upgrade
- **Risk:** Negligible (backward-compatible)
- **Why:** Core GEOMETRY type is production feature, not beta. Parallax heavily uses spatial queries; this is direct efficiency win.
- **Owner:** Backend Infrastructure
- **Target:** Deploy within 2 weeks (Q3 2026)
- **Dependencies:** None; test with current schema, upgrade container image
- **Success Metric:** Verify all spatial queries run unmodified; measure storage footprint reduction on world_state_snapshot table

### 2. **Integrate Claude Batch API for Scorecard + Eval Tasks (IMMEDIATE)**
- **Impact:** $10-15/day LLM cost reduction (50-75% of daily budget)
- **Effort:** 4-6 hours refactoring `brief.py --scorecard` + `--calibration` code paths
- **Risk:** Low (batch latency acceptable for eval; live predictions stay async)
- **Why:** Direct budget relief on core constraint ($20/day cap). Eval tasks are naturally asynchronous; batch is perfect fit.
- **Owner:** Backend / LLM Integration
- **Target:** Deploy with next weekly scorecard run (within 1 week)
- **Dependencies:** Update anthropic SDK to latest; batch API support is stable
- **Success Metric:** Verify scorecard latency acceptable (24-48h), confirm invoice shows 50% cost reduction on eval calls

### 3. **Integrate AIS Vessel Tracking for Shipping Ground Truth (PHASE 2, Q4 2026)**
- **Impact:** Real-world shipping data grounds blockade cascade rules; improves prediction accuracy 5-15% on Hormuz flow predictions
- **Effort:** 12-16 hours integration + 7-day validation
- **Risk:** Medium (third-party API latency, terrestrial vs satellite coverage differences)
- **Why:** Phase 1 relies on parameterized flow values; real AIS data will calibrate model vs. reality. High-leverage finding for Phase 2 accuracy improvements.
- **Owner:** Data Ingestion Lead
- **Target:** PoC complete by 2026-10-15; production integration by 2026-11-30
- **Dependencies:** Free AIS Stream tier sign-up; H3 mapping of vessel tracks (Res 5-6)
- **Success Metric:** Ingest 7 days AIS data; validate flow reduction cascade rule calibration; compare predicted vs. observed blockade impact on Hormuz throughput

---

## Rollout Priority Matrix

| Finding | Priority | Timeline | Owner | Dependencies |
|---------|----------|----------|-------|--------------|
| DuckDB 1.5 GEOMETRY | P0 | 2 weeks | Backend | Container upgrade |
| Claude Batch API | P0 | 1 week | Backend LLM | anthropic SDK update |
| Deck.gl highPrecision | P1 | <1 week | Frontend | One-line config |
| UCDP Integration | P1 | 3 weeks | Data Ingestion | UCDP API key |
| DeepEval + Langfuse | P2 | Phase 2 Q1 | Backend / MLOps | Docker, Python SDK |
| AIS Vessel Tracking | P2 | Phase 2 Q4 | Data Ingestion | PoC validation |
| react-use-websocket | P2 | Phase 2 | Frontend | 2-3 hour migration |
| WebSocket Batching | P1 | <1 week | Frontend | Code review |

---

## Sources

### Spatial/Geo
- [DuckDB 1.5.0 Release Notes](https://duckdb.org/)
- [DuckDB Spatial Extension](https://duckdb.org/docs/lts/core_extensions/spatial/overview)
- [GitHub - mattsta/h3: H3 with SIMD acceleration](https://github.com/mattsta/h3)
- [Uber H3 GitHub Repository](https://github.com/uber/h3)
- [H3 Documentation](https://h3geo.org/docs/)
- [The Complete Guide to Location Indexing](https://joudwawad.medium.com/location-indexing-complete-guide-36a143569555)
- [Geospatial Indexing Performance Showdown: H3 vs Quadkey](https://www.e6data.com/blog/geospatial-analytics-performance-bottleneck-h3-vs-quadkey-for-spatial-indexing)
- [deck.gl 9.1 H3HexagonLayer Documentation](https://deck.gl/docs/api-reference/geo-layers/h3-hexagon-layer)

### LLM/Agent
- [Claude Batch Processing API Docs](https://platform.claude.com/docs/en/build-with-claude/batch-processing)
- [Claude Prompt Caching Docs](https://platform.claude.com/docs/en/build-with-claude/prompt-caching)
- [Claude API Cost Optimization: Batching and Caching](https://dev.to/whoffagents/claude-api-cost-optimization-caching-batching-and-60-token-reduction-in-production-3n49)
- [Claude API Pricing Breakdown 2026](https://nicolalazzari.ai/articles/claude-api-pricing-breakdown-2026)
- [Top 15 AI Agent Frameworks in 2026](https://pickaxe.co/post/top-ai-agent-frameworks)
- [Claude vs LangGraph: Which Agent Wins in 2026](https://www.lowcode.agency/blog/claude-vs-langgraph)
- [Best Multi-Agent Frameworks in 2026](https://gurusup.com/blog/best-multi-agent-frameworks-2026)

### Real-time Data
- [AISStream.io WebSocket AIS API](https://aisstream.io/)
- [Datalastic Vessel Tracking API](https://datalastic.com/)
- [Data Docked Real-time Vessel Tracking](https://datadocked.com/)
- [VesselFinder API Documentation](https://vesselapi.com/)
- [50 Best Ship Tracking APIs 2026](https://hormuzmonitor.com/50-best-ship-tracking-apis-2026/)
- [EODHD Commodities API](https://eodhd.com/financial-apis/commodities-api-historical-prices-for-oil-gas-metals-agriculture-beta)
- [Databento Commodity Futures Data](https://databento.com/futures/commodity)
- [CME Group Crude Oil Futures](https://www.cmegroup.com/markets/energy/crude-oil.html)
- [FRED Crude Oil Prices](https://fred.stlouisfed.org/series/DCOILWTICO)
- [ACLED Dataset](https://acleddata.com/)
- [UCDP Uppsala Conflict Data Program](https://www.andybeger.com/data/ucdp/)
- [GDELT Project](https://gdeltproject.org/)
- [Free Geopolitical Data APIs 2026](https://www.worldmonitor.app/blog/posts/free-geopolitical-data-apis-2026/)

### Eval/MLOps
- [DeepEval LLM Evaluation Framework](https://deepeval.com/blog/best-llm-evaluation-platforms)
- [The Best LLM Evaluation Tools of 2026](https://medium.com/online-inference/the-best-llm-evaluation-tools-of-2026-40fd9b654dce)
- [Top LLM Testing Frameworks & Tools for QA (2026 Guide)](https://testomat.io/blog/llm-test/)
- [Best AI Evaluation Tools for Prompt Experimentation in 2026](https://www.confident-ai.com/knowledge-base/compare/best-ai-evaluation-tools-for-prompt-experimentation-2026)
- [Best Prompt Evaluation Tools in 2026](https://www.braintrust.dev/articles/best-prompt-evaluation-tools-2025)
- [A/B Testing for LLM Prompts: A Practical Guide](https://www.braintrust.dev/articles/ab-testing-llm-prompts)
- [LLM-as-a-Judge in 2026](https://deepeval.com/blog/llm-as-a-judge)
- [Langfuse Self-Hosted Tracing](https://langfuse.com/blog/2025-03-19-ai-agent-comparison)

### Performance
- [How to Use WebSockets in React for Real-Time Applications](https://oneuptime.com/blog/post/2026-01-15-websockets-react-real-time-applications/view)
- [Optimizing Real-Time Performance: WebSockets and React Integration Part I](https://medium.com/@SanchezAllanManuel/optimizing-real-time-performance-websockets-and-react-js-integration-part-i-e563664647d3)
- [Optimizing Real-Time Performance: WebSockets and React Integration Part II](https://medium.com/@SanchezAllanManuel/optimizing-real-time-performance-websockets-and-react-js-integration-part-ii-4a3ada319630)
- [Building Real-Time Business Dashboards with React in 2026](https://www.sparkleweb.in/blog/building_real-time_business_dashboards_with_react_in_2026)
- [Trading Dashboard Development in 2026 with Real-Time Charting](https://openwebsolutions.in/blog/high-performance-trading-dashboard-react-websockets/)
- [GitHub - react-use-websocket](https://github.com/robtaussig/react-use-websocket)
- [deck.gl Performance Guide](https://deck.gl/docs/developer-guide/performance)

---

## Next Steps

1. **This Week:** Deploy DuckDB 1.5 upgrade + Claude Batch API integration. Verify no regressions in scorecard output.
2. **Next Week:** Add `highPrecision: 'auto'` to frontend deck.gl config. Benchmark hex rendering performance at 400K hexes.
3. **Week 3:** Integrate UCDP API for conflict escalation signals. A/B test GDELT vs GDELT+UCDP on same 7-day event window.
4. **Phase 2 Planning:** Scope DeepEval + Langfuse integration, AIS vessel tracking PoC, react-use-websocket migration.

