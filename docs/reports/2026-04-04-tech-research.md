# Tech Research Report: 2026-04-04
## Parallax Geopolitical Simulator — Daily Scout Findings

**Focus Areas Searched:**
- Spatial/Geo visualization and data handling
- LLM/Agent frameworks and Claude API features
- Real-time data sources and geopolitical event feeds
- Evaluation frameworks and MLOps tooling
- Performance optimization for real-time React dashboards

---

## Key Findings by Category

### 1. SPATIAL/GEO

#### 1.1 DuckDB Spatial Extension: POINT_2D/LINESTRING_2D Optimization
**Status:** Experimental feature in current DuckDB  
**Relevance:** MEDIUM  
**Integration Effort:** Low (test with existing queries)  
**Risk:** Low — non-breaking experimental types  
**Type:** Additive optimization

DuckDB's spatial extension now includes explicit geometry types (`POINT_2D`, `LINESTRING_2D`, `POLYGON_2D`, `BOX_2D`) that allow optimization of geospatial algorithms when operating on these types vs. the generic `GEOMETRY` type. Currently only a few spatial functions have been explicitly specialized, but this is expanding.

**For Parallax:** Could accelerate H3 spatial index operations and route-to-cell conversions if these types are leveraged. Test cost is minimal.

**Sources:**
- [DuckDB Spatial Extension – DuckDB](https://duckdb.org/docs/current/core_extensions/spatial/overview)
- [Geospatial DuckDB - Tech Blog](https://tech.marksblogg.com/duckdb-geospatial-gis.html)

---

#### 1.2 deck.gl H3HexagonLayer: highPrecision Auto-Switching Mode
**Status:** Available in current deck.gl versions  
**Relevance:** MEDIUM  
**Integration Effort:** Very Low (one parameter change)  
**Risk:** Low — backward compatible  
**Type:** Performance enhancement to current stack

Recent optimization allows manual control and automatic switching between high-precision and high-performance rendering modes. Setting `highPrecision: false` forces low-precision instanced drawing for massive hex datasets. Mode 'auto' intelligently switches based on data characteristics.

**For Parallax:** Design already targets ~400K hexes (within comfort zone). This auto-switching could provide headroom for future resolution increases or real-time updates. Test with resolution 4 data to measure frame rate gains.

**Sources:**
- [H3HexagonLayer | deck.gl](https://deck.gl/docs/api-reference/geo-layers/h3-hexagon-layer)
- [Performance Optimization | deck.gl](https://deck.gl/docs/developer-guide/performance)

---

#### 1.3 CARTO Vector Tiles from Cloud Warehouses
**Status:** Production service in 2026  
**Relevance:** MEDIUM  
**Integration Effort:** High (infrastructure shift, tile serving)  
**Risk:** Medium — adds dependency on CARTO, licensing  
**Type:** Alternative complement to static Overture/Searoute pipeline

CARTO now streams vector tiles directly from cloud warehouses (Postgres, Snowflake, BigQuery) without pre-baking static tilesets. Could replace quarterly Overture Maps refreshes with live vector tiles.

**For Parallax:** Phase 1 uses static quarterly Overture data. This is a Phase 2 consideration for truly live map features. Not urgent for MVP.

**Sources:**
- [Large Scale Geospatial Visualization with Deck.gl, Mapbox-gl and Vue.js - DEV Community](https://dev.to/localeai/large-scale-geospatial-visualization-with-deck-gl-mapbox-gl-and-vue-js-54im)

---

### 2. LLM/AGENT

#### 2.1 Claude API Batch Processing + Prompt Caching Combo
**Status:** GA feature as of 2026  
**Relevance:** HIGH  
**Integration Effort:** Medium (refactor eval pipeline)  
**Risk:** Low — fully documented, well-supported  
**Type:** Cost reduction (80-95% potential savings on eval calls)

Batch Processing API provides 50% discount on token costs. Combined with Prompt Caching (10% of cached tokens), savings stack to achieve 95% cost reduction. Cache hit rates typically 30-98% depending on traffic patterns.

**Design Impact:** Agent system prompts (historical baseline) are the largest input component per the spec (~2-3K tokens). These are static per version and repeated across calls. With caching, repeated calls within 5-min window cost only 10% for the cached portion.

**For Parallax:**
- **Current est. cost:** $2-5/day under normal conditions
- **With batch+cache combo:** Potential $0.20-0.50/day for eval pipeline
- Batch API suits the daily eval cron job (identified predictions can be batched overnight)
- Live agent calls remain real-time but still benefit from prompt caching

**Recommendation:** Implement for eval pipeline immediately (Phase 1). Live agent calls can batch during low-activity periods.

**Sources:**
- [Batch processing - Claude API Docs](https://platform.claude.com/docs/en/build-with-claude/batch-processing)
- [Prompt caching - Claude API Docs](https://platform.claude.com/docs/en/build-with-claude/prompt-caching)
- [Claude API Batch Processing — Cut Costs by 50% | Claude Lab](https://claudelab.net/en/articles/api-sdk/claude-api-batch-processing-cost-optimization)

---

#### 2.2 Claude Structured Outputs (JSON Mode) — GA
**Status:** GA on Claude Sonnet 4.5, Opus 4.6, Haiku 4.5 as of 2026  
**Relevance:** MEDIUM  
**Integration Effort:** Low (schema definition + output_config change)  
**Risk:** Very Low — eliminates parse errors  
**Type:** Replaces current JSON validation logic

Structured outputs guarantee Claude responses match a defined JSON schema without manual validation or error handling. Moved from output_format to output_config.format in recent API changes.

**For Parallax:** Agent output schema is already defined (agent_id, tick, action_type, target_h3_cells, etc.). Structured outputs eliminate the need for custom JSON validation and malformed output rejection logic currently in spec (Section 13, agent output validation).

**Recommendation:** Adopt for all agent calls. Reduces code complexity and runtime parsing failures.

**Sources:**
- [Structured outputs - Claude API Docs](https://platform.claude.com/docs/en/build-with-claude/structured-outputs)
- [Build Claude 4.5 JSON Mode: Reliable Structured Output 2026 | Markaicode](https://markaicode.com/claude-45-json-mode-structured-output/)

---

#### 2.3 Claude Vision for Multimodal Analysis
**Status:** Available on all current Claude models (2026)  
**Relevance:** LOW for Phase 1 (HIGH for Phase 2)  
**Integration Effort:** Medium (image source pipeline)  
**Risk:** Low — vision is mature feature  
**Type:** Additive capability

All Claude models now support image input (PNG, JPG, GIF, WebP). Vision reasoning is perception-oriented (Claude reads axis labels, interprets relationships, explains context).

**For Parallax:** Could augment geopolitical analysis with:
- Satellite imagery analysis (port activity, fleet movements)
- News photo context (protest crowds, military deployments)
- Chart/infographic interpretation (price trends, trade flows)

**Not urgent for Phase 1** (text-only GDELT sufficient for MVP). Phase 2 opportunity when commercial satellite AIS/imagery feeds are added.

**Sources:**
- [Vision - Claude API Docs](https://platform.claude.com/docs/en/build-with-claude/vision)
- [Claude Vision for Document Analysis - A Developer's Guide](https://getstream.io/blog/anthropic-claude-visual-reasoning/)

---

#### 2.4 Agent Orchestration Frameworks (LangGraph, CrewAI, AutoGen, Microsoft Agent Framework)
**Status:** All active 2026 ecosystem  
**Relevance:** LOW for Phase 1  
**Integration Effort:** High (refactor custom DES)  
**Risk:** Medium (new dependencies, lock-in)  
**Type:** Alternative to current custom asyncio DES

Multiple frameworks available: LangGraph (fastest execution), CrewAI (role-playing agents), AutoGen (conversational multi-agent), Microsoft Agent Framework (enterprise graph-based).

**For Parallax:** Design explicitly states "No LangGraph" for Phase 1 — custom DES with asyncio+heapq provides tighter control over simulation ticks and cascade propagation. Swapping mid-Phase-1 would destabilize eval baseline.

**Reserve for Phase 2** if agent reasoning needs to become more complex (multi-step reasoning, tool use chains). Current sub-actor→country hierarchy works with direct LLM calls.

**Sources:**
- [LLM Orchestration in 2026: Top 22 frameworks and gateways](https://aimultiple.com/llm-orchestration)
- [Top 11 AI Agent Frameworks (2026): Expert-Tested & Reviewed | Lindy](https://www.lindy.ai/blog/best-ai-agent-frameworks)

---

### 3. REAL-TIME DATA

#### 3.1 aisstream.io — Free Global AIS WebSocket Feed
**Status:** Active, production-grade 2026  
**Relevance:** MEDIUM  
**Integration Effort:** Low (WebSocket subscription, NMEA parsing)  
**Risk:** Low — simple API, free tier available  
**Type:** Additive real-time data source

Free WebSocket API streaming global Automatic Identification System (AIS) data. Provides vessel positions, identities, port calls. OpenAPI 3.0 definitions available.

**For Parallax:** Complements existing GDELT event feed with **live vessel tracking**. Could feed shipping lane occupancy data directly into H3 cells, giving real-time anchor for "Hormuz traffic" right-panel indicator.

**Data Quality:** AIS data is broadcast by ships themselves (regulatory requirement for large vessels). Coverage is global but gaps exist in certain regions. Not a complete picture but highly actionable.

**Phase 1 vs 2:** Phase 1 uses EIA/GDELT as ground truth for eval. Could add AIS as supplementary feed in Phase 2 for richer maritime detail without compromising eval baselines.

**Sources:**
- [aisstream.io](https://aisstream.io/)
- [GitHub - aisstream/aisstream · GitHub](https://github.com/aisstream/aisstream)

---

#### 3.2 OpenAIS + AISHub — Open Source Vessel Tracking
**Status:** Active 2026  
**Relevance:** MEDIUM  
**Integration Effort:** Low to Medium (data aggregation)  
**Risk:** Low  
**Type:** Additive open-source alternatives to commercial APIs

Two open-source projects aggregating AIS:
- **OpenAIS:** Tools for deriving meaningful insight from raw vessel tracking data
- **AISHub:** Free AIS data sharing service, API in JSON/XML/CSV

**For Parallax:** Redundancy + cost control. If aisstream.io fails, fallback options exist. AISHub free tier removes subscription dependency.

**Sources:**
- [OpenAIS](https://open-ais.org/)
- [Free AIS vessel tracking | AIS data exchange | JSON/XML ship positions](https://www.aishub.net/)

---

#### 3.3 World Monitor — Open-Source Intelligence Dashboard
**Status:** Active 2026  
**Relevance:** MEDIUM (reference implementation)  
**Integration Effort:** N/A (reference, not integration)  
**Risk:** Low  
**Type:** Complementary reference, not a replacement

World Monitor aggregates military tracking, conflict monitoring, infrastructure mapping, news correlation, AI analysis. Uses both ACLED and GDELT sources. Open-source, browser-based.

**For Parallax:** Good reference for **dashboard layout and data aggregation patterns**. Shows how to combine GDELT + ACLED + geospatial visualization. Reinforces choice to use both GDELT (real-time) and ACLED (validated, lagged).

**Sources:**
- [World Monitor: A Free, Open-Source Global Intelligence Dashboard with 25 Data Layers and AI-Powered Threat Classification](https://darkwebinformer.com/world-monitor-a-free-open-source-global-intelligence-dashboard-with-25-data-layers-and-ai-powered-threat-classification/)

---

### 4. EVAL/MLOPS

#### 4.1 Promptfoo — Open-Source Prompt Testing & A/B Framework
**Status:** Actively maintained, used by OpenAI and Anthropic  
**Relevance:** HIGH  
**Integration Effort:** Medium (integrate into eval pipeline)  
**Risk:** Low — well-tested, open-source  
**Type:** Additive — complements custom eval framework

Declarative YAML-based prompt testing with built-in A/B comparison, version tracking, and traceability. Emphasizes "link evaluation score back to exact prompt/model/dataset version."

**For Parallax:** Aligns perfectly with existing **Prompt Versioning** design (Section 7). Promptfoo could automate:
- A/B comparison when new prompt versions deployed
- Multi-model testing (Haiku vs Sonnet trade-offs)
- Regression detection (flag when new version underperforms old)
- Dashboard for viewing accuracy by prompt version

**Integration Path:**
1. Export daily eval results (per-agent accuracy, confidence calibration)
2. Feed into Promptfoo eval suite
3. Flag versions for rollback if 7-day window drops below threshold (already designed)
4. Integrate results back into admin dashboard

**Phase 1 MVP:** Custom eval cron (as spec'd) is sufficient. Phase 1.5: Add Promptfoo for operator ergonomics and version tracking visualization.

**Sources:**
- [GitHub - promptfoo/promptfoo: Test your prompts, agents, and RAGs](https://github.com/promptfoo/promptfoo)
- [LLM Testing Tools and Frameworks in 2026: The Engineering Guide](https://contextqa.com/blog/llm-testing-tools-frameworks-2026/)

---

#### 4.2 DeepEval — LLM Evaluation Metrics Framework
**Status:** Actively maintained, open-source  
**Relevance:** MEDIUM  
**Integration Effort:** Low (Python library, pytest-like)  
**Risk:** Low  
**Type:** Additive metrics library

Framework specialized for unit testing LLM apps. Implements metrics: G-Eval, task completion, answer relevancy, hallucination detection, factual consistency, etc. Uses LLM-as-judge + NLP models.

**For Parallax:** Could supplement existing eval scoring (direction, magnitude, sequence, calibration). Particularly useful for detecting **hallucination** (agent invents false facts about actors/events) and **factual consistency** (internal contradictions in agent memory).

**Phase 1:** Not essential (custom metrics cover direction/magnitude/calibration). Phase 1.5: Add hallucination detection to flag when agents make up "decisions" not grounded in GDELT events.

**Sources:**
- [GitHub - confident-ai/deepeval: The LLM Evaluation Framework · GitHub](https://github.com/confident-ai/deepeval)
- [LLM Evaluation Metrics: The Ultimate LLM Evaluation Guide - Confident AI](https://www.confident-ai.com/blog/llm-evaluation-metrics-everything-you-need-for-llm-evaluation)

---

#### 4.3 Caldara-Iacoviello Geopolitical Risk (GPR) Index
**Status:** Academic open-source, data available 2026  
**Relevance:** MEDIUM  
**Integration Effort:** Low (HTTP API to fetch daily index)  
**Risk:** Very Low — 100+ years of academic development  
**Type:** Additive baseline/context data

Newspaper-based index of geopolitical tensions since 1900. Constructed from 10-newspaper tally (Benchmark, starts 1985) and 3-newspaper historical version (starts 1900). Country-specific indices also available.

**For Parallax:** Could serve as **baseline forecast** against which agent swarm predictions are compared. If GPR index is flat, "no escalation" is a strong naive baseline. If GPR index spikes, agents should match or beat that signal.

**Phase 1:** Not essential (spec uses "no change" and "market consensus" as baselines). Phase 2: Add GPR as third baseline — tests whether agent swarm adds value vs. established risk indices.

**Sources:**
- [Geopolitical Risk (GPR) Index](https://www.matteoiacoviello.com/gpr.htm)
- [Country-Specific Geopolitical Risk Index](https://www.matteoiacoviello.com/gpr_country.htm)
- [Geopolitical Risk Index](https://www.policyuncertainty.com/gpr.html)

---

### 5. PERFORMANCE

#### 5.1 React WebSocket Batching for High-Frequency Updates
**Status:** Best practice documented 2026  
**Relevance:** HIGH (already identified in spec)  
**Integration Effort:** Very Low (already designed in!)  
**Risk:** None — spec explicitly covers this (Section 5)  
**Type:** Implementation detail confirmation

Current design already accounts for this: "buffer incoming updates for 100ms, then flush as a single mutation to the ref." Search confirms this is standard pattern for 2026 real-time dashboards.

**Validation:** Design approach is sound. Recommend confirming:
- Batch interval (100ms) provides good UX responsiveness + reduces renders
- Batch size cap prevents memory bloat during high-activity periods
- Mutable `useRef` pattern decouples React renders from WebSocket updates

**Sources:**
- [Optimizing Real-Time Performance: WebSockets and React.js Integration Part II | Medium](https://medium.com/@SanchezAllanManuel/optimizing-real-time-performance-websockets-and-react-js-integration-part-ii-4a3ada319630)
- [How to Use WebSockets in React for Real-Time Applications](https://oneuptime.com/blog/post/2026-01-15-websockets-react-real-time-applications/view)

---

#### 5.2 Web Workers for Expensive Calculations
**Status:** Standard browser capability  
**Relevance:** LOW (not needed for Phase 1)  
**Integration Effort:** Medium  
**Risk:** Low  
**Type:** Optional performance optimization

Offload expensive calculations (GDELT filtering, semantic dedup, relevance scoring) to background threads.

**For Parallax:** GDELT filtering currently runs on backend (Python + DuckDB). No need to move to frontend Web Workers. If frontend needs to do heavy chart computation or hex sampling, Web Workers available as optimization.

**Not urgent for MVP.**

**Sources:**
- [Real-Time Data Visualization in React using WebSockets and Charts | Syncfusion Blogs](https://www.syncfusion.com/blogs/post/view-real-time-data-using-websocket)

---

## TOP 3 RECOMMENDATIONS

### 1. **Implement Claude Batch + Prompt Caching for Eval Pipeline** (HIGH impact, LOW risk)
- **Why:** Eval cron already identified as perfect use case for batching (daily predictions to resolve overnight). Potential 80-95% cost reduction on eval calls.
- **Effort:** Medium (refactor eval code to batch + add cache_control headers)
- **Phase 1 Timeline:** Add in final week of Phase 1 before live deployment. Reduces ongoing cost from $2-5/day to potentially $0.20-0.50/day.
- **Reference:** [Batch processing - Claude API Docs](https://platform.claude.com/docs/en/build-with-claude/batch-processing), [Prompt caching - Claude API Docs](https://platform.claude.com/docs/en/build-with-claude/prompt-caching)

### 2. **Adopt Claude Structured Outputs (JSON Mode)** (MEDIUM impact, VERY LOW risk)
- **Why:** Eliminates custom JSON validation logic + parsing failures. Spec already requires schema validation (Section 13); structured outputs make it native.
- **Effort:** Very Low (update API calls with output schema definition)
- **Phase 1 Timeline:** Can be done any time; recommend before first live agents fire for clean error handling.
- **Reference:** [Structured outputs - Claude API Docs](https://platform.claude.com/docs/en/build-with-claude/structured-outputs)

### 3. **Add aisstream.io AIS Feed as Supplementary Data Source** (MEDIUM impact, LOW risk)
- **Why:** Real-time vessel tracking complements GDELT events. "Hormuz traffic" right-panel indicator (spec Section 5) gains live ground truth anchor. Free tier available.
- **Effort:** Low (WebSocket subscription, NMEA message parsing, insert into `curated_events`)
- **Phase 1 Timeline:** Phase 1.5 or 2 — not on critical path for MVP. Doesn't break eval baselines if added as supplementary (not replacement) data source.
- **Reference:** [aisstream.io](https://aisstream.io/)

---

## ALTERNATIVES & LOWER-PRIORITY FINDINGS

- **DuckDB POINT_2D/LINESTRING_2D:** Worth testing if hex-to-cell spatial queries show latency. Currently spec'd approach is sound; optimization is optional.
- **deck.gl H3HexagonLayer highPrecision mode:** Good for future scaling beyond 400K hexes; test after Phase 1 baseline established.
- **Promptfoo:** Excellent for Phase 1.5 operator dashboard (visualization of prompt versions + accuracy trends). Not essential for MVP.
- **DeepEval:** Useful for Phase 1.5 hallucination detection. Current eval framework covers core metrics.
- **Claude Vision:** Phase 2 enhancement when satellite imagery feeds added.
- **Web Workers:** Unnecessary for Phase 1; backend already handles heavy lifting.

---

## SUMMARY

**Significant 2026 Opportunities:**
1. **Claude API cost reduction** (batch + caching) is immediate, high-impact
2. **Structured outputs** eliminate parsing fragility
3. **Real-time AIS data** enriches maritime scenario accuracy

**No Breaking Changes Required:** Current stack (DuckDB, deck.gl, FastAPI, sentence-transformers, Claude API) remains solid. Improvements are additive or optimize existing components.

**Phase 1 MVP Status:** On track. No critical tech gaps identified. Recommend implementing recommendations #1-2 before live deployment.

---

## Sources

- [DuckDB Spatial Extension – DuckDB](https://duckdb.org/docs/current/core_extensions/spatial/overview)
- [H3HexagonLayer | deck.gl](https://deck.gl/docs/api-reference/geo-layers/h3-hexagon-layer)
- [Batch processing - Claude API Docs](https://platform.claude.com/docs/en/build-with-claude/batch-processing)
- [Prompt caching - Claude API Docs](https://platform.claude.com/docs/en/build-with-claude/prompt-caching)
- [Structured outputs - Claude API Docs](https://platform.claude.com/docs/en/build-with-claude/structured-outputs)
- [Vision - Claude API Docs](https://platform.claude.com/docs/en/build-with-claude/vision)
- [aisstream.io](https://aisstream.io/)
- [GitHub - promptfoo/promptfoo](https://github.com/promptfoo/promptfoo)
- [GitHub - confident-ai/deepeval](https://github.com/confident-ai/deepeval)
- [Geopolitical Risk (GPR) Index](https://www.matteoiacoviello.com/gpr.htm)
