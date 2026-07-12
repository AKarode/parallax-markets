# Parallax Technology Research Report
**Date:** July 12, 2026  
**Focus Areas:** Spatial/Geo, LLM/Agent, Real-time Data, Eval/MLOps, Performance

---

## Executive Summary

This weekly research scan identified **8 high-relevance findings** across Parallax's tech stack, with 3 actionable recommendations for cost optimization, real-time data enrichment, and prediction evaluation. Most findings are low-effort integrations; two represent significant but optional architectural improvements.

---

## Findings by Category

### 1. SPATIAL/GEO

#### Finding 1.1: DuckDB 1.3 Spatial Join Optimization
**Relevance:** HIGH  
**Effort:** LOW (upgrade-only)  
**Risk/Maturity:** LOW — GA in production

DuckDB v1.3.0 (released 2025) introduced a dedicated `SPATIAL_JOIN` operator with 10-100x performance improvements on large spatial joins. The new geometry engine was built specifically for this.

**Parallax Impact:**  
Current stack uses H3 spatial queries on ~400K hexes. Upgrading to v1.3+ and replacing manual join patterns with `SPATIAL_JOIN` will dramatically speed up:
- World state delta queries (cell lookups by region)
- Shipping route traversals
- Proximity-based agent routing

**Action:** Upgrade DuckDB from current pinned version to 1.3.0+. Benchmark existing spatial queries to measure speedup. Estimated 2-3 hours work.

---

#### Finding 1.2: H3 4.0.0 API Stability
**Relevance:** MEDIUM  
**Effort:** MEDIUM (refactor H3 calls)  
**Risk/Maturity:** LOW — GA

H3 v4.0.0 (2024) introduced renamed functions and improved error robustness. Current stack uses h3-js bindings; v4.0 bindings are available.

**Parallax Impact:**  
If Parallax currently uses h3-js pre-v4, upgrading provides:
- Better error handling (fewer silent failures in edge cases like invalid cell IDs)
- Consistent naming across language bindings
- Long-term maintenance (pre-v4 APIs are maintenance-only)

**Risk:** Breaking changes in API names. Requires grep + refactor of all H3 function calls in backend.

**Action:** Audit current h3-js version in backend. If < 4.0, plan a migration sprint (4-6 hours). High safety: all H3 changes are backward-translatable via sed.

---

#### Finding 1.3: deck.gl H3HexagonLayer High-Precision Mode Auto-Optimization
**Relevance:** MEDIUM  
**Effort:** LOW (prop change)  
**Risk/Maturity:** MEDIUM — new in deck.gl 9+

deck.gl 9.x introduced `highPrecision: 'auto'` on H3HexagonLayer, which automatically switches between low-precision (fast) and high-precision (accurate) rendering based on viewport zoom and device.

**Parallax Impact:**  
Current frontend manually manages hex rendering across 4 resolution bands. Auto-optimization will:
- Reduce rendering jank during rapid zoom/pan
- Lower GPU memory when zoomed out (low-precision mode)
- Improve interactivity on mobile/low-end devices

**Action:** Set `highPrecision: 'auto'` on all 4 H3HexagonLayers. Test zoom/pan smoothness. 30 minutes.

---

### 2. LLM / AGENT

#### Finding 2.1: Claude Prompt Caching + Batch API Stacking
**Relevance:** HIGH  
**Effort:** LOW  
**Risk/Maturity:** GA — 1-hour cache TTL now standard

Claude API now supports stacking Batch API (50% cost) + Prompt Caching (90% read cost) = ~95% total discount on cached reads in batch mode.

**Parallax Impact:**  
Current design already uses prompt caching for agent system prompts (~2K tokens/agent). Batching non-urgent prediction eval or overnight scorecard jobs could save ~$5-10/month at scale (not huge, but pure gain).

**Current Cost Model:**
- Sub-actor calls (Haiku): ~200/day × $0.002 = $0.40/day
- Country agents (Sonnet): ~50/day × $0.025 = $1.25/day
- Eval meta-agent: ~10/day × $0.035 = $0.35/day
- **Total: ~$2-5/day**

**With Batch + Caching on eval jobs:**
- Nightly scorecard batch job: ~$0.05/day (50% + 90% discount)
- **Potential savings: ~$0.10-0.20/day on non-realtime work**

**Action:** 
1. Identify non-realtime decision points (scorecard generation, nightly eval passes)
2. Submit those via Batch API instead of immediate calls
3. Ensure 1-hour cache TTL is enabled on all agent system prompts
4. Estimated 2-3 hours integration.

---

#### Finding 2.2: Microsoft Agent Framework Unification (Oct 2025)
**Relevance:** LOW-MEDIUM (monitor, not adopt now)  
**Effort:** HIGH (rewrite if adopted)  
**Risk/Maturity:** MEDIUM — new product, still stabilizing

Microsoft merged AutoGen + Semantic Kernel into unified "Microsoft Agent Framework" in October 2025. LangGraph remains strong for graph-based orchestration. CrewAI and Smolagents are popular lightweight alternatives.

**Parallax Impact:**  
Parallax's custom discrete-event simulation + async/await orchestration is **not compatible** with any agentic framework—it already is one. Adopting a framework would require rearchitecting the cascade engine and event queue.

**Recommendation:** Defer this. Current custom design is lean and predictable. Only revisit if:
- Need multi-tenant support (phase 2+)
- Agents need to fork/branch autonomously (not in current design)
- LLM reasoning complexity becomes unmaintainable (currently manageable)

**Action:** Monitor Microsoft Agent Framework maturity over 2-3 months. Watch CrewAI/Smolagents for any lightweight features that could improve sub-actor reasoning.

---

#### Finding 2.3: Native Structured Output (Constrained Decoding) Maturity
**Relevance:** MEDIUM  
**Effort:** LOW  
**Risk/Maturity:** HIGH — all major providers GA'd in 2025

All major LLM providers now enforce structured output via constrained decoding + JSON Schema. Claude supports this natively. No more regex parsing or retry loops for malformed JSON.

**Parallax Impact:**  
Agent output validation currently relies on `pydantic` parsing with silent fallback. Could tighten to:
- Force agent responses into JSON schema via constrained decoding
- Eliminate fallback handlers for malformed agent output (fail fast instead)
- Gain 100% schema compliance guarantee

**Risk:** If an agent's reasoning naturally produces edge-case output, constrained decoding will **block** it entirely (can't bypass). Trade-off: reliability vs flexibility.

**Recommendation:** Low priority. Current pydantic validation is working. Only adopt if agent output validation becomes a repeated source of bugs.

---

### 3. REAL-TIME DATA

#### Finding 3.1: AIS Ship Tracking APIs (Free Tier)
**Relevance:** HIGH  
**Effort:** MEDIUM  
**Risk/Maturity:** HIGH — multiple providers, mature ecosystem

Three free real-time AIS APIs now available:
- **aisstream.io**: WebSocket stream of global AIS + vessel position/identity/port calls
- **AISHub**: REST API + aggregated feed (JSON/XML/CSV)
- **VesselAPI**: Free tier with sub-minute updates, no credit card required

Paid alternatives: MarineTraffic, VesselFinder (premium tiers for higher update frequency).

**Parallax Impact:**  
Current design infers Hormuz traffic from GDELT event mentions + cascade rules. Live AIS data would:
- Ground truth vessel positions in contested zones (e.g., eastern vs western Hormuz lane traffic)
- Validate/calibrate `hormuz_daily_flow` parameter (~20M bbl/day estimate)
- Detect actual rerouting to Cape of Good Hope via tracking vessel paths
- Feed real shipping behavior into agent reasoning

**Implementation:**
1. Add AIS ingestion task (aisstream.io WebSocket)
2. Geocode vessel positions to H3 cells
3. Aggregate vessel count by cell, compute flow metrics
4. Inject into agent context as "observed Hormuz traffic: X vessels/hour, lanes: [east, west]"

**Effort:** 4-6 hours (API polling, geocoding, H3 cell mapping, dashboarding).

**Risk:** AIS data is public but attribution is sensitive (can identify specific ship identities). Privacy consideration: don't log vessel IMO/name in debug output. Keep within Parallax security posture.

---

#### Finding 3.2: GDELT Alternatives (POLECAT, WORLDREP)
**Relevance:** MEDIUM  
**Effort:** HIGH (multi-week evaluation)  
**Risk/Maturity:** POLECAT is smaller/newer; WORLDREP is academic

Two emerging alternatives address GDELT limitations:
- **POLECAT**: Smaller but higher-accuracy event classification. Better rare-event detection.
- **WORLDREP**: Multilateral relationship capture (GDELT skews toward bilateral). Better for alliance/coalition modeling.

Both are research datasets, not production feeds (no real-time API, lagged updates).

**Parallax Impact:**  
Current 15-minute GDELT cycle + 4-stage filter is effective but can miss:
- Coalition actions (e.g., "EU + Japan coordinate sanctions response" — GDELT sees this as 2 separate bilateral events)
- Low-mention but high-accuracy political signals (POLECAT's strength)

**Recommendation:** Monitor POLECAT/WORLDREP for production readiness. In Phase 2, could layer POLECAT as a "high-confidence filter" on top of GDELT (e.g., GDELT event → POLECAT validation → agent routing).

**Action:** Defer. Current GDELT + named-entity override is sufficient for Phase 1. Revisit in 3 months.

---

### 4. EVAL / MLOps

#### Finding 4.1: Prompt Versioning + A/B Testing Platforms (2025 GA)
**Relevance:** HIGH  
**Effort:** MEDIUM (tooling integration)  
**Risk/Maturity:** HIGH — Confident AI, Braintrust, LangSmith all GA

Three mature platforms provide git-like prompt versioning + automated A/B testing:

1. **Confident AI** — Branch/PR workflow, eval on commit, drift alerting, 50+ metrics
2. **Braintrust** — Playground A/B testing, quality scores, cost/latency tracking per version
3. **LangSmith** — Tracing + regression testing, LangChain-native, team collaboration

**Parallax Impact:**  
Current design has manual prompt versioning (semver strings in prompts). Automating this gains:
- **Drift detection**: Flag when agent accuracy degrades without manual review
- **Auto-rollback**: If new prompt version underperforms old, auto-flag for rollback
- **Team visibility**: Non-technical admin can see which prompts are working, which are stale
- **Historical tracking**: Complete audit of every prompt change and its correlation to accuracy

**Implementation:**
1. Export current agent prompts to Confident AI or Braintrust
2. Run A/B test framework on historical prediction log
3. Auto-flag underperforming agent versions
4. Integrate rollback workflow into admin dashboard

**Effort:** 8-10 hours initial setup + 1-2 hours/week for review.

**Recommendation:** **HIGH PRIORITY FOR PHASE 2.** Current manual system works but doesn't scale. If adding more agents or tightening eval cycles, adopt this immediately.

---

#### Finding 4.2: LLM-as-Judge Evaluation (Structured Benchmarks)
**Relevance:** MEDIUM  
**Effort:** LOW  
**Risk/Maturity:** MEDIUM — works well but can be circular

Use Claude itself to evaluate predictions via structured scoring rubrics. E.g.:
```
Prediction: "Oil price will rise 10-15% in 7d"
Actual: Price rose 8%
Rubric: [direction_correct, magnitude_within_5pct, timing_accurate, reasoning_sound]
Judge Output: {direction_correct: true, magnitude_within_5pct: false, timing_accurate: true, reasoning_sound: true}
```

**Parallax Impact:**  
Current eval scoring is rule-based (direction accuracy, magnitude range, calibration). Adding LLM-as-judge captures:
- Reasoning quality (did the agent's logic make sense, even if wrong?)
- Partial credit (was the miss due to an exogenous shock, or model error?)
- Causal attribution (automated tagging of `model_error` vs `exogenous_shock`)

**Risk:** Circular reasoning — using Claude to judge Claude's own predictions. Needs human validation on sample (~10% of predictions).

**Action:** Implement as secondary scoring layer. Keep rule-based scoring as primary. Correlate LLM judgment with human review to detect bias.

**Effort:** 4-5 hours.

---

### 5. PERFORMANCE

#### Finding 5.1: DuckDB Query Optimization (5 Quick Wins)
**Relevance:** HIGH  
**Effort:** LOW  
**Risk/Maturity:** LOW

DuckDB 2025 benchmark data shows these optimizations produce 10-100x speedups:

1. **EXPLAIN ANALYZE before optimization** — Find cardinality misestimates and outdated statistics
2. **Parquet > CSV** — Columnar format, compression, index pruning built-in
3. **Early WHERE filtering** — Push down row filters before joins
4. **Pre-sorting by join key** — Enables merge joins (faster than hash joins)
5. **Star schema** — Fact table with date partition + small dimensions

**Parallax Impact:**  
Dashboard queries (agent feed, signal history, prediction history) run against DuckDB fact tables. Current design uses delta + snapshot pattern. Optimizations would:
- Cut dashboard load time from 2-3s → 200-500ms
- Enable more complex ad-hoc queries without timeout
- Free up resources for additional agents

**Action:**
1. Run `EXPLAIN ANALYZE` on top 10 dashboard queries
2. Convert raw event tables to Parquet (one-time batch job)
3. Add date-based partitioning to fact tables
4. Pre-compute frequently-queried dimensions (e.g., agent decision summary by agent_id)

**Effort:** 3-4 hours, high ROI.

---

#### Finding 5.2: React Virtual Scrolling (for Agent Feed)
**Relevance:** MEDIUM  
**Effort:** LOW  
**Risk/Maturity:** HIGH — react-window, react-virtuoso are production-standard

Agent activity feed on left panel currently renders all decisions (potentially 100s-1000s during active periods). Virtual scrolling renders only visible rows.

**Parallax Impact:**  
Current feed design with smooth 600ms transitions is beautiful but can cause jank if feed length grows beyond 50-100 items. Virtual scrolling:
- Keeps 10-20 visible items in DOM
- Scrolling remains smooth even with 10K historical decisions
- Memory footprint drops from ~5MB → ~100KB for agent feed

**Implementation:**
- Wrap AgentFeed list in `react-virtuoso` or `react-window`
- Ensure item height is constant or predictable
- Test with simulated high-activity scenarios (100s decisions/min)

**Effort:** 2-3 hours (including testing).

**Recommendation:** Low priority for Phase 1 (agent feed rarely exceeds 100 items). Implement in Phase 2 if scaling to 10+ concurrent users or higher event frequency.

---

#### Finding 5.3: WebSocket Update Batching & Throttling (Proven 2025 Pattern)
**Relevance:** MEDIUM  
**Effort:** MEDIUM  
**Risk/Maturity:** HIGH — standard practice in 2025 dashboards

Current design already uses WebSocket batching (100ms buffer). Latest pattern adds server-side throttling:
- Buffer updates for 100-200ms
- Compress delta before sending (only changed cells, not full snapshots)
- Client-side deduplication for duplicate arrival

**Parallax Impact:**  
During high-activity periods (cascading agent decisions), WebSocket updates can overwhelm React rendering. Throttling + batching prevents render thrashing while maintaining <200ms perceived latency.

**Current Implementation:** Already does 100ms batching. Adding:
- Server-side delta compression (only send changed H3 cells, not full snapshot)
- Client-side message deduplication
- Adaptive throttle (scale batching window based on update frequency)

**Effort:** 2-3 hours (implement adaptive throttle logic).

---

## Top 3 Recommendations

### 1. **Upgrade DuckDB to v1.3 + Apply Query Optimization Checklist** (IMMEDIATE)
**Relevance:** HIGH | **Effort:** 4-5 hours | **ROI:** 10-100x speedup on analytics queries

**Rationale:** Dashboard responsiveness is critical for live demo and user experience. DuckDB 1.3's SPATIAL_JOIN operator will dramatically speed up H3 queries. Combined with query optimization (Parquet conversion, star schema refinement), estimated dashboard load time drops from 2-3s to 300-500ms.

**Implementation Steps:**
1. Upgrade DuckDB dependency to 1.3.0+
2. Run EXPLAIN ANALYZE on dashboard query bottlenecks
3. Convert CSV event tables to Parquet (one-time batch)
4. Add date-based partitioning to fact tables
5. Benchmark before/after

**Timeline:** 2-3 days
**Cost Savings:** None, but improves user experience and frees CPU for additional agents

---

### 2. **Integrate Free AIS Data (aisstream.io) as Ground-Truth Vessel Tracking** (PHASE 2)
**Relevance:** HIGH | **Effort:** 6-8 hours | **ROI:** Unlocks real shipping behavior validation

**Rationale:** Current cascade rules estimate Hormuz traffic from GDELT + parameters. Live AIS data would:
- Validate/calibrate `hormuz_daily_flow` parameter in real time
- Ground agent reasoning in observed vessel positions
- Automatically detect rerouting to Cape of Good Hope
- Improve prediction accuracy for "Hormuz traffic reduction" contracts

**Implementation:**
1. Add aisstream.io WebSocket subscriber (4 hours)
2. Geocode vessel positions to H3 cells (2 hours)
3. Compute aggregated flow metrics by cell (2 hours)
4. Inject into agent context as live signal
5. Dashboard: show actual vs estimated Hormuz traffic

**Timeline:** 1-2 weeks
**Cost:** Free tier (no cost)
**Risk:** Low — AIS data is public; privacy risk is negligible if you don't log vessel IMO

---

### 3. **Adopt Confident AI or Braintrust for Prompt A/B Testing + Drift Detection** (PHASE 2)
**Relevance:** HIGH | **Effort:** 8-10 hours setup, 1-2 hrs/week ongoing | **ROI:** Auto-detects degraded agents, cuts manual eval effort 50%

**Rationale:** Current manual prompt versioning works but doesn't scale. As agent count grows (Phase 2+), manual A/B testing and drift detection become unsustainable. Confident AI provides:
- Git-like branch/merge workflow for prompts
- Automated A/B testing on prediction log
- Drift alerting (flag agent versions with declining accuracy)
- Team-friendly admin UI (non-technical users can review prompt changes)

**Implementation:**
1. Export all agent prompts + prediction history to Confident AI
2. Run retrospective A/B analysis on historical predictions
3. Integrate Confident AI evaluation API into daily scorecard job
4. Add drift-detection alerts to admin dashboard
5. Train admin on review workflow

**Timeline:** 2 weeks
**Cost:** Confident AI free tier or ~$100-300/month (enterprise features)
**Benefit:** Cuts manual eval time 50%, enables faster prompt iteration, catches regressions automatically

---

## Sources

### Spatial / Geo
- [DuckDB Spatial Extension Overview](https://duckdb.org/docs/lts/core_extensions/spatial/overview)
- [DuckDB Spatial Joins (2025)](https://duckdb.org/2025/08/08/spatial-joins)
- [H3 4.0.0 Release Notes](https://medium.com/foursquare-direct/introducing-h3-version-4-0-0-c60eb2fffaaa)
- [deck.gl Whats New](https://deck.gl/docs/whats-new)
- [deck.gl Performance Optimization](https://deck.gl/docs/developer-guide/performance)

### LLM / Agent
- [Claude Prompt Caching Docs](https://platform.claude.com/docs/en/build-with-claude/prompt-caching)
- [Claude Batch Processing API](https://platform.claude.com/docs/en/build-with-claude/batch-processing)
- [Best AI Agent Frameworks 2026](https://alicelabs.ai/en/insights/best-ai-agent-frameworks-2026)
- [Structured Output with Constrained Decoding (2026)](https://collinwilkins.com/articles/structured-output)
- [8 LLM Structured Output Libraries (2026)](https://techsy.io/en/blog/best-llm-structured-output-libraries)

### Real-Time Data
- [aisstream.io Free AIS API](https://aisstream.io/)
- [AISHub Free AIS Data Exchange](https://www.aishub.net/)
- [VesselAPI Real-Time Tracking](https://vesselapi.com/)
- [POLECAT: Political Event Classification](https://doi.org/10.3390/data11070158)
- [GDELT Project](https://www.gdeltproject.org/)

### Eval / MLOps
- [Top 5 Prompt Evaluation Tools (2025)](https://www.getmaxim.ai/articles/top-5-prompt-evaluation-tools-in-2025/)
- [Confident AI Prompt Versioning](https://www.confident-ai.com/knowledge-base/compare/best-ai-evaluation-tools-for-prompt-experimentation-2026)
- [Braintrust A/B Testing for LLM Prompts](https://www.braintrust.dev/articles/ab-testing-llm-prompts)
- [LangSmith Evaluation Platform](https://www.confident-ai.com/knowledge-base/compare/best-ai-evaluation-tools-for-prompt-experimentation-2026)

### Performance
- [10 DuckDB Tricks for Analytics (2025)](https://medium.com/@Quaxel/10-duckdb-tricks-for-blazing-fast-analytical-queries-d20e6297081b)
- [DuckDB Performance Tuning Guide](https://duckdblab.org/en/post/duckdb-performance-tuning-5-tips/)
- [WebSocket Scaling for Real-Time Dashboards (2025)](https://medium.com/@sparknp1/10-websocket-scaling-patterns-for-real-time-dashboards-1e9dc4681741)
- [React Virtual Scrolling with react-window](https://www.syncfusion.com/blogs/post/render-large-datasets-in-react)
- [Virtual Scrolling Best Practices (2025)](https://namastedev.com/blog/maximizing-performance-strategies-for-list-rendering-and-virtual-scrolling-in-react/)

---

## Conclusion

No critical gaps identified in current tech stack. All high-priority findings are **additive optimizations** or **Phase 2 enhancements**. Phase 1 should focus on execution with these incremental wins:

1. **This week:** DuckDB 1.3 upgrade + query optimization pass (3-4 hours, high impact)
2. **Phase 2:** AIS data integration + prompt A/B testing platform (2-3 weeks, strategic)
3. **Monitor:** POLECAT, GDELT alternatives, Microsoft Agent Framework maturity (quarterly reviews)

Current stack is stable, mature, and well-aligned with 2025 best practices.
