# Technology Research Report — Parallax Geopolitical Swarm
**Date:** September 9, 2026  
**Scope:** Spatial/Geo, LLM/Agent, Real-time Data, Eval/MLOps, Performance

---

## Executive Summary

Research identified **3 high-priority improvements** and **4 medium-priority opportunities** that could strengthen Parallax's edge-finding capabilities. Most significant findings: (1) Claude API cache TTL change requires cost-control adjustments, (2) deck.gl 2026 delivers H3HexagonLayer performance gains, (3) open AIS data sources provide shipping ground truth without subscription cost.

---

## Findings by Category

### 1. Spatial & Geospatial Visualization

#### 1.1 deck.gl 2026 H3HexagonLayer Performance Improvements
- **Status:** deck.gl released H3HexagonLayer optimizations including `highPrecision: false` flag and 2-3x faster MVT tile parsing via binary attribute paths
- **Relevance:** **HIGH** — Direct improvement to Parallax's core visualization layer
- **Effort:** LOW (update deck.gl package, test rendering on existing H3 data)
- **Risk:** LOW (backward compatible, opt-in via flag)
- **Integration Path:** Test new version in frontend. Measure WebSocket update latency and frame rate on hex cell changes. Compare before/after on live demo scenario.

#### 1.2 DuckDB Spatial Extension Type Specialization
- **Status:** DuckDB spatial extension now offers POINT_2D, LINESTRING_2D, POLYGON_2D types with fixed memory layout, enabling ~3-5x faster geospatial algorithms on geometry-heavy queries
- **Relevance:** **MEDIUM** — Accelerates cell state queries and cascade rule computations
- **Effort:** MEDIUM (refactor cell attribute serialization, migrate schema, benchmark impact)
- **Risk:** MEDIUM (API breakage risk if custom geometry funcs are in use)
- **Recommendation:** Measure current CASCADE rule bottlenecks with `EXPLAIN ANALYZE`. If geometry operations are <10% of runtime, defer. If >20%, prototype POINT_2D variant of H3 cell state table.

#### 1.3 S2/Geohash as H3 Alternatives
- **Status:** S2 geometry library (Google) and Geohash offer different hierarchical indexing. Geohash has broader tool support; S2 has better pole handling
- **Relevance:** **LOW** — H3 is already deeply integrated (deck.gl layer, cascade rules, visualization)
- **Effort:** VERY HIGH (rewrite visualization, cascade, cell indexing)
- **Risk:** HIGH (architectural rewrite, eval framework may not correlate to new grid)
- **Recommendation:** Stick with H3. Cost/benefit strongly negative unless visualization requirements change fundamentally.

---

### 2. LLM & Agent Infrastructure

#### 2.1 Claude API Prompt Caching TTL Change (2026 Impact)
- **Status:** Anthropic reduced prompt cache TTL from 60 minutes → 5 minutes in early 2026. This breaks cache hit rate for burst workloads with inter-burst gaps >5min
- **Relevance:** **HIGH** — Directly impacts Parallax's $20/day LLM budget
- **Effort:** MEDIUM (adjust cascade scheduling to keep agent calls within 5-min windows, implement request batching queue)
- **Risk:** LOW (code change only, no third-party dependency)
- **Impact:** Without adjustment, cache miss rate can double during off-peak hours (cost +30-60%)
- **Recommendation:** **Immediate action required.** Implement request buffering: accumulate agent calls for 4 minutes, then batch submit within 5-min cache window. Use Anthropic's published cache strategies for best practices.

#### 2.2 Claude Batch API + Prompt Caching Combination
- **Status:** Batch processing API (async, 50% cost reduction) now supports prompt caching (~90% reduction for cached segments). Combined potential: ~80-90% cost reduction on bulk prediction workloads
- **Relevance:** **HIGH** — Could reduce eval cost and enable more frequent model experiments
- **Effort:** MEDIUM (refactor daily eval pipeline to use batches instead of real-time LLM calls, implement result polling)
- **Risk:** LOW (batch API is proven, eval can tolerate 1-2 hour latency)
- **Integration Path:** Pilot on daily scorecard computation: collect 50+ eval requests over 1 hour, submit batch, poll results. Measure cost/time tradeoff.

#### 2.3 Structured Output Improvements
- **Status:** Claude API now enforces structured output (JSON schemas, enums) with stricter validation and fallback strategies
- **Relevance:** **MEDIUM** — Parallax agent output validation can be tightened
- **Effort:** LOW (add `schema` param to agent prompt calls, test with sample GDELT events)
- **Risk:** LOW (already doing schema validation post-hoc; moving it into API just tightens the contract)
- **Recommendation:** Adopt on new agents/prompts. Existing agents can migrate on version bump (v1.2.0 → v1.3.0).

---

### 3. Real-time Data Ingestion

#### 3.1 Open-Source AIS Shipping Data (Free Alternative to Kpler)
- **Status:** AISHub (free aggregate feed, JSON/XML API) and AISstream.io (free WebSocket) provide real-time vessel positions at no cost. Market consolidated under Kpler/MarineTraffic but open APIs persist.
- **Relevance:** **HIGH** — Provides ground truth for Hormuz traffic modeling without subscription
- **Effort:** MEDIUM (add AIS feed ingester, parse MMSI/position/speed, join with existing shipping route model)
- **Risk:** MEDIUM (data quality varies; free feeds lag premium by 5-15 min; MMSI → vessel metadata requires external lookup)
- **Integration Path:** Ingest AISHub feed (15-min polling) as backup to searoute geometry. Use AIS vessel count + speeds to validate cascade model predictions of "flow reduction under blockade." Flag divergences.
- **Estimated Cost:** $0 (free tier) vs. $100-500/mo (commercial AIS APIs)

#### 3.2 GDELT Complementary Datasets
- **Status:** ACLED (validated conflict events), UCDP (Uppsala Conflict Data Program), WorldMonitor all address GDELT's known weakness: inability to capture multi-actor coordination (e.g., US + Israel + Arab states response to Iran)
- **Relevance:** **MEDIUM** — Reduces false negatives on escalation scenarios
- **Effort:** MEDIUM (add ACLED weekly batch ingestion, semantic dedup with GDELT, merge into curated_events)
- **Risk:** MEDIUM (new data source = new schema, potential for duplicate events post-merge)
- **Integration Path:** Test ACLED feed on historical Iran events (2015-2025). Measure: (1) does it catch events GDELT misses? (2) does it correlate with known escalations? (3) cost of semantic dedup?

#### 3.3 Specialized Geopolitical Satellites
- **Status:** NASA FIRMS (active fires, high-res), USGS (earthquakes), Cloudflare Radar (internet outages) provide exogenous shocks not in news
- **Relevance:** **LOW** — Useful for Phase 2 (broader geopolitical scenarios). For Iran/Hormuz, news + oil prices already cover most shocks.
- **Effort:** HIGH (add satellite imagery ingestion, trained models for infrastructure damage detection, integrate with cascade)
- **Risk:** MEDIUM (model accuracy risk; requires domain expertise)
- **Recommendation:** Defer to Phase 2.

---

### 4. Evaluation & MLOps

#### 4.1 Prompt Versioning & Traceability Tools
- **Status:** Langfuse (self-hosted), Lilypad, PromptLayer all provide automatic prompt versioning, run tracing, and A/B evaluation frameworks. As of 2026, traceability (linking scores → prompt version → dataset version) is standard practice.
- **Relevance:** **MEDIUM** — Parallax already implements versioning in `agent_prompts` table. Tools add observability/UI.
- **Effort:** MEDIUM (adopt Langfuse as optional sidecar; new eval pipeline queries it for scoring dashboards)
- **Risk:** LOW (additive, no code change required to existing eval logic)
- **Recommendation:** Pilot on admin dashboard. Integrate Langfuse read-only queries to show which prompts (versions) drove which predictions (scores). Optional upgrade for Phase 2 production.

#### 4.2 LLM Evaluation Frameworks
- **Status:** DeepEval (open-source, unit-test style LLM metrics), Confident AI (platform with dataset + A/B + observability), LangSmith (LangChain-native playground)
- **Relevance:** **MEDIUM** — Parallax's eval is hand-rolled (direction/magnitude/calibration scoring). Frameworks can add rigor.
- **Effort:** MEDIUM (audit Parallax's existing scoring functions against DeepEval metrics; where gaps exist, add integrations)
- **Risk:** LOW (complementary, no replacement needed immediately)
- **Integration Path:** Use DeepEval's calibration_score metric on predictions table. Compare output to Parallax's rolling-window calibration. If consistent, adopt for consistency.

#### 4.3 Regression Testing for Prompts
- **Status:** A/B testing frameworks (Confident AI, Langfuse) now support automated regression tests: new prompt must not drop accuracy >5% on holdout eval set or previous version is restored.
- **Relevance:** **MEDIUM** — Parallax has manual "7-day A/B window" logic. Automation can tighten guardrails.
- **Effort:** MEDIUM (implement via `predictions` table query: holdout set is events from 7 days prior; reject new version if calibration drops)
- **Risk:** LOW (code change, no external dependency)
- **Recommendation:** Implement in Phase 1.5 after initial prompt stabilization (week 2 of eval). Prevents prompt regressions during high-velocity iteration.

---

### 5. Performance & Real-time Rendering

#### 5.1 React Dashboard Rendering Optimization Patterns (2026)
- **Status:** Best practice (confirmed across 2026 sources): decouple React state from high-frequency WebSocket data. Use `useRef` for mutable data arrays; re-render UI only for low-frequency changes (agent feed, indicator cards). Batch WebSocket updates every 100ms.
- **Relevance:** **HIGH** — **Parallax frontend already implements this** (per design spec: H3 hex data in useRef, UI state separate). No change needed.
- **Effort:** NONE (already in place)
- **Risk:** NONE
- **Note:** Current implementation matches 2026 best practices. Confirms design is sound.

#### 5.2 Virtualization for Large Agent Feed
- **Status:** React Virtualized and TanStack Virtual enable rendering only visible rows of scrolling lists. For 1000+ agent decisions per day, virtualization can prevent DOM bloat.
- **Relevance:** **MEDIUM** — Agent activity feed (left panel) may grow large over a 30-day run
- **Effort:** LOW (integrate react-virtual or TanStack Virtual, replace scrolling div)
- **Risk:** LOW (well-established libraries)
- **Recommendation:** Implement if left panel becomes sluggish after 1+ week of continuous run. Otherwise defer.

#### 5.3 Web Workers for Cascade Computation
- **Status:** Heavy cascade rule computation can be offloaded to a Web Worker to keep UI thread responsive
- **Relevance:** **LOW** — Cascade runs in backend (Python), not frontend
- **Effort:** N/A (architecture already correct)
- **Risk:** N/A
- **Note:** No action needed; cascade is backend-resident by design.

#### 5.4 DuckDB Query Performance
- **Status:** DuckDB query performance remains strong for Parallax's workload (state reconstruction, eval queries). No urgent optimizations needed. Batched delta + snapshot architecture already optimal.
- **Relevance:** **MEDIUM** — Continual tuning opportunity
- **Effort:** LOW (run EXPLAIN ANALYZE on slow eval queries, add indexes if needed)
- **Risk:** LOW (read-only tuning)
- **Recommendation:** Profile eval pipeline on week 1 of live run. If scorecard queries exceed 5s, prioritize index on `predictions.prompt_version` and `decisions.tick`.

---

## Top 3 Recommendations

### 1. **Claude API Prompt Caching TTL Adjustment (IMMEDIATE)**
- **Why:** Cache TTL reduction (60m → 5m) directly impacts $20/day budget by 30-60% if not addressed
- **Action:** Implement 4-minute request buffering in agent swarm to keep calls within cache window
- **Owner:** Backend (cascade/agent scheduler)
- **Timeline:** Week 1 (before eval period)
- **Benefit:** Preserve or reduce LLM costs; improve cache hit rate

### 2. **Adopt Claude Batch API for Daily Eval (PHASE 1.5)**
- **Why:** 50-90% cost reduction on prediction eval workload; eval can tolerate async latency
- **Action:** Refactor daily scorecard pipeline to batch 50+ eval calls, submit async, poll results
- **Owner:** Backend (scoring/scorecard)
- **Timeline:** Week 2-3 (after initial eval runs)
- **Benefit:** Reduce daily cost by ~$1-2; enable more frequent model experiments

### 3. **Integrate AIS Shipping Data as Ground Truth (MEDIUM PRIORITY)**
- **Why:** Free, real-time vessel position data validates cascade model predictions of Hormuz traffic reduction
- **Action:** Ingest AISHub or AISstream.io feed; join with existing route model; flag divergences between predicted flow and observed vessel behavior
- **Owner:** Backend (ingestion)
- **Timeline:** Week 2-3 (after core ingestion pipeline stable)
- **Benefit:** Improved edge detection (spot when flow drops faster/slower than predicted); zero cost alternative to paid AIS subscriptions

---

## Sources

### Spatial & Geospatial
- [deck.gl What's New](https://deck.gl/docs/whats-new)
- [deck.gl H3HexagonLayer Docs](https://deck.gl/docs/api-reference/geo-layers/h3-hexagon-layer)
- [deck.gl Performance Guide](https://deck.gl/docs/developer-guide/performance)
- [Awesome DuckDB Spatial](https://github.com/alperdincer/Awesome-DuckDB-Spatial)
- [DuckDB Spatial Extension Docs](https://duckdb.org/docs/current/core_extensions/spatial/functions)
- [Geospatial Indexing Comparison](https://benfeifke.com/posts/geospatial-indexing-explained/)

### LLM & Agent
- [Claude Prompt Caching TTL Change 2026 (DEV Community)](https://dev.to/whoffagents/claude-prompt-caching-in-2026-the-5-minute-ttl-change-thats-costing-you-money-4363)
- [Anthropic Batch Processing Docs](https://platform.claude.com/docs/en/build-with-claude/batch-processing)
- [Prompt Caching Cost Optimization 2026](https://www.aimagicx.com/blog/prompt-caching-claude-api-cost-optimization-2026)
- [Claude Batch API Cost Optimization](https://claudeapi.com/en/blog/dev-guides/claude-batch-api-cost-optimization/)

### Real-time Data
- [AISHub Free AIS Feed](https://www.aishub.net/)
- [Best Ship Tracking APIs 2026](https://hormuzmonitor.com/50-best-ship-tracking-apis-2026/)
- [VesselAPI AIS Tracking](https://vesselapi.com/)
- [GDELT Project](https://www.gdeltproject.org/)
- [Free Geopolitical Data APIs 2026](https://www.worldmonitor.app/blog/posts/free-geopolitical-data-apis-2026/)
- [GDELT Alternatives & Comparisons](https://dataresearchtools.com/gdelt-project-for-news-data-2026-free-alternative-to-newsapi/)

### Eval & MLOps
- [Best LLM Evaluation Tools 2026 (Medium)](https://medium.com/online-inference/the-best-llm-evaluation-tools-of-2026-40fd9b654dce)
- [A/B Testing LLM Applications 2026](https://atlan.com/know/ab-testing-llm-applications/)
- [Best Prompt Evaluation Tools 2026 (Braintrust)](https://www.braintrust.dev/articles/best-prompt-evaluation-tools-2025)
- [LLM Testing Frameworks & Tools (2026)](https://testomat.io/blog/llm-test/)
- [Best AI Evaluation Tools for Prompt Experimentation 2026](https://www.confident-ai.com/knowledge-base/compare/best-ai-evaluation-tools-for-prompt-experimentation-2026)
- [A/B Testing Prompts Comprehensive Guide](https://www.getmaxim.ai/articles/how-to-perform-a-b-testing-with-prompts-a-comprehensive-guide-for-ai-teams/)

### Performance & Rendering
- [Building Real-Time Dashboards with React and WebSockets](https://www.wildnetedge.com/blogs/building-real-time-dashboards-with-react-and-websockets)
- [React Real-Time Dashboard WebSocket Optimization (Medium)](https://medium.com/@SanchezAllanManuel/optimizing-real-time-performance-websockets-and-react-js-integration-part-ii-4a3ada319630)
- [Building Real-Time Dashboards React 2026](https://www.sparkleweb.in/blog/building_real-time_business_dashboards_with_react_in_2026)
- [Optimize Web Dashboards for Faster Data Rendering](https://dohost.us/index.php/2026/08/25/10-proven-ways-to-optimize-web-dashboards-for-faster-data-rendering/)
- [Sencha Real-Time Dashboards](https://www.sencha.com/blog/building-real-time-dashboards-with-websockets-and-frontend-frameworks/)

---

## Next Steps

1. **Week 1:** Implement Claude cache TTL workaround (request buffering)
2. **Week 2:** Pilot AIS feed ingestion on historical data
3. **Week 2-3:** Refactor eval pipeline for batch API
4. **Ongoing:** Monitor performance on live run; profile slow queries

---

**Report compiled by:** Claude Code Tech Scout  
**Status:** Ready for review by project team
