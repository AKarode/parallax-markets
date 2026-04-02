# Parallax Tech Research Report — 2026-04-02

**Research Focus:** Spatial/Geo improvements, LLM/Agent orchestration, real-time data sources, evaluation frameworks, frontend performance optimization.

---

## Executive Summary

Parallax Phase 1 is well-positioned with a solid tech stack. Research across five focus areas reveals **3 high-impact opportunities**: (1) batch API + extended thinking for agent cost/quality optimization, (2) AIS real-time shipping integration for Hormuz corridor, (3) state management refactor (Zustand over Context) for 70% re-render reduction on the dashboard.

Most findings are **additive** rather than replacements. The current stack is mature and appropriate. No breaking changes recommended.

---

## Findings by Category

### 1. Spatial/Geo

#### Finding 1.1: DuckDB 2026 Extensions Ecosystem Stabilization
**Relevance:** MEDIUM | **Effort:** LOW | **Risk:** LOW | **Type:** Additive

DuckDB's spatial extensions remain the recommended path for Phase 1+. In 2026, the ecosystem has stabilized around H3 + spatial as core extensions. New experimental types (`POINT_2D`, `LINESTRING_2D`, `POLYGON_2D`, `BOX_2D`) offer theoretical performance gains for geospatial algorithms due to fixed memory layout, but are still experimental.

**Assessment:** Current pinned H3 extension is stable. Monitor experimental 2D types for Phase 2 if performance analysis shows geometry operations becoming a bottleneck. Currently, ~400K hexes across 4 resolution bands is comfortably handled.

**Source:** [DuckDB Spatial Extension](https://duckdb.org/docs/current/core_extensions/spatial/overview), [DuckDB Geospatial Tech Blog](https://tech.marksblogg.com/duckdb-geospatial-gis.html)

---

#### Finding 1.2: deck.gl H3 Performance Optimization — TileLayer + highPrecision
**Relevance:** MEDIUM | **Effort:** MEDIUM | **Risk:** LOW | **Type:** Additive

Starting from v8.8, deck.gl's TileLayer supports custom indexing systems (including H3) for incremental loading. H3HexagonLayer now supports `highPrecision: false` mode for fast, low-precision rendering. These are explicit optimizations for large H3 datasets.

**Assessment:** Current design uses 4 separate H3HexagonLayer instances (one per resolution band). TileLayer with custom H3 indexing could reduce memory footprint and improve pan/zoom responsiveness for very large datasets (>500K hexes). **Phase 1 doesn't require this yet**, but if Hormuz hex budget creeps beyond 400K in future scenarios, TileLayer should be evaluated. `highPrecision: false` is useful if rendering becomes jittery during high-frequency WebSocket updates.

**Source:** [deck.gl Performance Guide](https://deck.gl/docs/developer-guide/performance), [GitHub #6869](https://github.com/visgl/deck.gl/discussions/6869)

---

### 2. LLM/Agent Orchestration

#### Finding 2.1: Claude API Batch API + Prompt Caching Combo — 75-95% Cost Reduction Opportunity
**Relevance:** HIGH | **Effort:** HIGH | **Risk:** MEDIUM | **Type:** Replacive (Optimization)

**Batch API (50% discount):**
- Asynchronous processing of large volumes of requests
- 50% discount on both input and output tokens
- Trade-off: 24-hour processing window, not real-time

**Prompt Caching Workspace Isolation Update (Feb 5, 2026):**
- Cache hits now cost 10% of standard input price
- Workspace-level isolation (not org-level)
- Breaks even after 1 cache read (5-min TTL) for longer prompts, 2 reads for shorter ones
- **Combining both can save up to 95% on inference costs**

**Assessment:** Parallax already implements prompt caching for agent system prompts (2-3K tokens per agent). The Phase 1 design targets $2-5/day. If budget pressure emerges:
- **Near-term:** Batch non-urgent eval/meta-agent calls (10 calls/day). Estimated savings: ~$0.20/day on eval calls.
- **Medium-term:** Batch low-priority sub-actor calls (Haiku tier, high volume). Estimated savings: ~$0.15/day.
- **Cost:** Introduces 24-hour eval lag. For Phase 1's 30-day continuous run, acceptable if eval is run in two tiers (real-time critical, batch non-critical).

**Risk:** Adds operational complexity (batch queue management). Requires careful separation of real-time vs. batch agent calls. **Do not batch country-agent (Sonnet) calls in live mode — they drive forward simulation.**

**Source:** [Claude API Pricing](https://platform.claude.com/docs/en/about-claude/pricing), [Prompt Caching](https://platform.claude.com/docs/en/build-with-claude/prompt-caching), [Batch API Guide](https://claudelab.net/en/articles/api-sdk/claude-api-batch-processing-cost-optimization)

---

#### Finding 2.2: Extended Thinking (Opus/Sonnet 4.6) for Complex Agent Reasoning
**Relevance:** MEDIUM | **Effort:** MEDIUM | **Risk:** LOW | **Type:** Additive

Claude Opus/Sonnet 4.6 support adaptive extended thinking, where Claude dynamically decides how much to reason before responding. Useful for:
- Complex conflict resolution between sub-actor recommendations
- Multi-step reasoning on causal attribution in eval feedback
- Debugging why an agent's prediction diverged from reality

**Assessment:** Phase 1 sub-actors (Haiku) are lightweight; extended thinking overkill for them. **Consider for country-agent decision logic (Sonnet tier)** if conflict resolution between sub-actors becomes messy. Example: Iran's IRGC, Foreign Ministry, and Oil Ministry have conflicting recommendations — extended thinking could provide better reasoning on which to weight. Cost: ~+$0.01-0.02 per call. Benefit: higher reasoning quality.

**Not recommended for Phase 1 MVP** (adds latency + cost), but flag for Phase 2 if decision quality becomes limiting.

**Source:** [Building with Extended Thinking](https://platform.claude.com/docs/en/build-with-claude/extended-thinking), [Extended Thinking Tips](https://platform.claude.com/docs/en/build-with-claude/prompt-engineering/extended-thinking-tips)

---

#### Finding 2.3: LangGraph for Hierarchical Agent Orchestration (Comparison with Current Design)
**Relevance:** MEDIUM | **Effort:** HIGH | **Risk:** MEDIUM | **Type:** Optional Enhancement

LangGraph is a graph-based multi-agent orchestration framework with explicit support for hierarchical control flows. It finished 2.2x faster than CrewAI in comparable multi-agent tests. Hierarchical architecture (orchestrator → subordinate agents) is exactly what Parallax implements.

**Assessment:** Parallax already implements a **custom hierarchical agent design**: country agents (orchestrators) + sub-actors (subordinates) connected via a cascade engine. Switching to LangGraph would:
- **Pro:** Native persistence, graph visualization, state management for free.
- **Con:** Adds dependency; requires rewriting custom DES and cascade logic. Parallax's design is already optimized for this specific scenario (single writer, asyncio-based, deterministic replays).
- **Verdict:** Not a replacement for Phase 1. The custom design is simpler and more predictable for this use case. LangGraph is better for general-purpose multi-agent orchestration; Parallax's simulation engine + agent swarm is domain-specific and tighter.

**Phase 2 option:** If adding multi-scenario support, LangGraph could manage scenario orchestration.

**Source:** [LangGraph Documentation](https://www.langchain.com/langgraph), [Top Agentic Frameworks 2026](https://aimultiple.com/agentic-orchestration)

---

### 3. Real-Time Data Sources

#### Finding 3.1: AIS (Automatic Identification System) Shipping Data APIs for Hormuz Corridor
**Relevance:** HIGH | **Effort:** MEDIUM | **Risk:** LOW | **Type:** Additive

Multiple AIS providers offer real-time vessel tracking via JSON/XML APIs:

| Provider | Coverage | Pricing | Latency | Notes |
|----------|----------|---------|---------|-------|
| **aisstream.io** | Global terrestrial AIS | Free | 5-30s | Community-operated, basic data |
| **Datalastic** | Global terrestrial + satellite | Paid | 5-15s | Non-stop 24/7 coverage, Python-friendly |
| **VesselFinder** | Global terrestrial | Paid | Real-time | Live positions, port calls, ETA |
| **Portcast** | Global | Paid | Real-time | ETA/ETD predictions, risk data |
| **Kpler/MarineTraffic** | 13,000+ receivers worldwide | Paid | Real-time | Largest AIS network, enterprise-grade |

**Assessment:** Parallax already models shipping traffic in Hormuz via H3 flow attributes. Adding real AIS data would:
- **Pro:** Ground truth for validation. Model Hormuz traffic reduction realistically when blockade occurs. Detect actual rerouting to Cape of Good Hope.
- **Con:** Adds ingestion pipeline, parsing, and schema mapping. ~100-200 vessels transiting Hormuz daily → 1-2 new data streams.
- **Recommendation for Phase 1:** Use **aisstream.io (free, basic)** or negotiate trial access to **Portcast** (has ETA predictions, valuable for cascade logic). Implement as optional data source; simulator continues with parameterized flow defaults if AIS feed fails.
- **Integration effort:** Moderate (new BigQuery-like async ingestion + H3 cell mapping).

**Source:** [AIS Hub](https://www.aishub.net/), [aisstream.io](https://www.aisstream.io/), [Datalastic](https://datalastic.com/), [Portcast](https://www.portcast.io/ocean-vessel-tracking-api)

---

#### Finding 3.2: GDELT Alternatives & Supplements (Complementary, Not Replacement)
**Relevance:** MEDIUM | **Effort:** MEDIUM | **Risk:** LOW | **Type:** Additive

Research shows **GDELT has no perfect replacement**, but supplements exist:

- **ICEWS (Integrated Conflict Early Warning System):** Comparable scale to GDELT; U.S. DoD system; **not publicly available.**
- **Diffbot Knowledge Graph:** Web-sourced facts on billions of entities; narrow (no historical depth like GDELT's 1979 baseline; no non-web sources).
- **World Monitor:** Open-source dashboard aggregating GDELT + ACLED + military tracking. No new data source, just aggregation layer.
- **GDELT Cloud:** GDELT data with pre-built analysis skills for geopolitical/strategic risk.

**Assessment:** GDELT is the right choice for Phase 1. Its **four-stage noise filter** (volume gate + structural dedup + semantic dedup + relevance scoring) is already sophisticated. ACLED (weekly, conflict-validated) is already included as a supplement. **No replacement needed.**

**Possible addition:** Integrate **World Monitor** as a reference dashboard (not a data source) to cross-check Parallax's event deduplication logic.

**Source:** [GDELT Solutions](https://www.gdeltproject.org/solutions.html), [Diffbot Knowledge Graph](https://blog.diffbot.com/knowledge-graph-comparison-gdelt-vs-diffbot/), [World Monitor](https://darkwebinformer.com/world-monitor-a-free-open-source-global-intelligence-dashboard-with-25-data-layers-and-ai-powered-threat-classification/)

---

#### Finding 3.3: Oil & Energy Data APIs (Current Sufficiency)
**Relevance:** LOW | **Effort:** LOW | **Risk:** LOW | **Type:** Status Check

Current stack includes EIA API (daily prices), FRED API (benchmark series), Energy Institute Statistical Review. Design notes that proper futures forward curve requires paid providers (CME Group, Nasdaq Data Link).

**Assessment:** Current feed is sufficient for Phase 1 (cascade logic uses daily spot prices and policy-level parameters, not intraday futures). If Phase 2 requires modeling intraday price volatility or futures-driven speculation, evaluate CME or Nasdaq Data Link APIs. For now, skip.

---

### 4. Evaluation & MLOps

#### Finding 4.1: DeepEval Framework for LLM Agent Evaluation
**Relevance:** MEDIUM | **Effort:** MEDIUM | **Risk:** LOW | **Type:** Additive

DeepEval (Confident AI) is a developer-focused testing framework for LLM applications. Provides:
- Predefined metrics: accuracy, bias, hallucination detection
- CI/CD integration for automated testing
- Ranking/comparison of model versions

Parallax's eval framework already has:
- Prediction scoring (direction, magnitude, sequence, calibration)
- Causal attribution on misses (`model_error`, `exogenous_shock`, etc.)
- Prompt versioning with A/B tracking

**Assessment:** Parallax's **custom eval framework is more specialized** than DeepEval. DeepEval targets general LLM applications; Parallax needs domain-specific prediction scoring. However, **DeepEval could augment:**
- Automated hallucination detection on agent reasoning (flag if agent claims a false fact)
- Bias detection across country agents (flag if one agent systematically over-weighted in conflicts)

**Effort:** Medium (integrate DeepEval as optional side-channel metric). **Phase 1 skip; Phase 2 optional if bias becomes a concern.**

**Source:** [DeepEval GitHub](https://github.com/confident-ai/deepeval), [LLM Evaluation Frameworks 2026](https://www.mlaidigital.com/blogs/llm-model-evaluation-frameworks-a-complete-guide-for-2026)

---

#### Finding 4.2: Continuous Evaluation Pipelines & Human-in-the-Loop Feedback (2026 Trend)
**Relevance:** HIGH | **Effort:** MEDIUM | **Risk:** LOW | **Type:** Aligned

2026 industry trends emphasize:
- **Continuous evaluation** with real-time monitoring (not batch at day end)
- **Human-in-the-loop feedback** combining AI metrics with expert review

Parallax Phase 1 has:
- Daily cron eval (batch)
- Manual checkpoints (human)
- Admin dashboard for eval review & prompt editing

**Assessment:** Phase 1 already aligned with trend. The daily cron + manual checkpoint + admin dashboard design is sound. **Consider adding:**
- Real-time prediction monitoring dashboard (show active predictions, confidence, time-to-resolve)
- Expert review queue (flag high-confidence misses for human review immediately, not next day)

**Low-effort add:** WebSocket push of eval results to admin dashboard as they compute (not just cron batch).

---

### 5. Frontend Performance

#### Finding 5.1: React State Management — Zustand for High-Frequency Updates
**Relevance:** HIGH | **Effort:** HIGH | **Risk:** MEDIUM | **Type:** Replacive (Optional)

**Current design:** Uses React Context + mutable `useRef` for H3 hex data (already optimized to avoid re-renders per WebSocket update).

**2026 benchmark:** Switching from Context to Zustand reduced re-renders by 70% and improved interaction latency from 180ms to 45ms in a comparable real-time dashboard.

**Assessment:** Parallax's **current design is already optimized** (mutable ref + batched updates every 100ms). The 70% re-render reduction from Zustand is achieved when moving **away from Context**, not when already using refs. **Full refactor to Zustand is not necessary for Phase 1**, but could be a clean consolidation:
- **Pro:** Cleaner state separation (UI state in Zustand, H3 data in ref), better devtools.
- **Con:** Another dependency, refactoring effort is high (~2-3 days).
- **Recommendation:** Phase 1, measure current performance first. If WebSocket throttling is hitting limits (>200 updates/sec), evaluate Zustand. Otherwise, current design is fine.

**Source:** [React WebSocket Integration Part II](https://medium.com/@SanchezAllanManuel/optimizing-real-time-performance-websockets-and-react-js-integration-part-ii-4a3ada319630)

---

#### Finding 5.2: Update Batching, Throttling, and Virtualization (Best Practices Alignment)
**Relevance:** MEDIUM | **Effort:** LOW | **Risk:** LOW | **Type:** Aligned

Industry best practices for real-time dashboards (2026):
- Batch updates for 100-200ms before flushing
- Throttle high-frequency events (e.g., price ticks)
- Virtualize long lists (only render visible items)

Parallax Phase 1:
- Already batches WebSocket updates for 100ms ✓
- Agent activity feed (left panel) uses scrolling; no virtualization mentioned

**Assessment:** Aligned on batching. **Consider virtualization for agent activity feed:** if 50 agents each make 5 decisions/hour, that's 250 decisions/day = long list. Virtualization (e.g., `react-window`) would ensure smooth scrolling even at 2-3 decisions/sec during active crises.

**Low-effort add:** Implement `react-window` for agent feed if performance testing shows lag on large feeds. Phase 1 acceptable without it.

---

#### Finding 5.3: Web Workers for Heavy Calculations (Server-side Alternative)
**Relevance:** LOW | **Effort:** LOW | **Risk:** LOW | **Type:** Not Applicable

Best practice: Offload heavy calculations (e.g., rolling averages, anomaly detection) to Web Workers or server-side pre-computation.

**Assessment:** Parallax's frontend is mostly rendering (H3 hexes, sparklines, cards). Heavy calculations (cascade rules, price shocks, flow reduction) run server-side. **No Web Worker use case for Phase 1.**

---

## Embeddings Model Review

#### Finding: all-MiniLM-L6-v2 Still Optimal for Parallax Use Case
**Relevance:** LOW | **Effort:** LOW | **Risk:** LOW | **Type:** Status Check

Current design uses `all-MiniLM-L6-v2` (22M params, ~4-5x faster than all-mpnet-base-v2) for semantic deduplication of GDELT events.

2026 embedding landscape shows:
- all-mpnet-base-v2 still popular (768D, general-purpose)
- all-MiniLM-L6-v2 remains lightweight favorite
- Qwen3-Embedding-0.6B emerging for specialized tasks
- Geospatial-specific embeddings (PRESTO, ESD) for remote sensing timeseries

**Assessment:** all-MiniLM-L6-v2 is **still the right choice for Parallax**. It's fast (sub-100ms for 100 events), lightweight, and general-purpose. Geospatial embeddings (PRESTO, ESD) are for remote sensing imagery, not text events. **No change recommended.**

**Source:** [Best Open-Source Embeddings 2026](https://www.bentoml.com/blog/a-guide-to-open-source-embedding-models)

---

## Top 3 Recommendations (Prioritized)

### Recommendation 1: Integrate Real AIS Data for Hormuz Corridor (HIGH Impact, Immediate)
**Priority:** HIGH | **Effort:** 3-5 days | **Cost:** $0-500/month (depending on provider)

**Rationale:**
- Hormuz is the core scenario; real vessel data is crucial for validation
- aisstream.io (free) provides immediate proof-of-concept; Portcast (paid) adds ETA predictions for cascade logic
- Moderate implementation effort; high confidence in value add

**Implementation:**
1. Stand up async ingestion from aisstream.io (free tier)
2. Map vessel positions to H3 cells (res 6-7 in Persian Gulf)
3. Compute daily flow (vessels/day) per cell; compare against parameterized baseline
4. Flag divergences in eval results (actual flow < predicted → real blockade signal)
5. Optional: Negotiate Portcast trial for ETA predictions (improves rerouting logic)

**Phase 1 timeline:** Add in week 2-3 once core simulation is stable.

---

### Recommendation 2: Implement Batch API for Eval/Meta-Agent Calls (MEDIUM Impact, Cost Control)
**Priority:** MEDIUM | **Effort:** 2-3 days | **Cost Savings:** $0.30-0.50/day (~$9-15/month in 30-day run)

**Rationale:**
- Eval meta-agent calls (10/day) and low-priority sub-actor batches can be asynchronous
- Batch API provides 50% discount; combined with prompt caching, 75%+ savings
- Introduces 24-hour lag acceptable for non-critical evals

**Implementation:**
1. Separate real-time agent calls (country agents in live sim) from batch-able calls (eval scoring, prompt improvement suggestions)
2. Queue eval calls; batch submit 2x/day (morning, evening)
3. Retrieve results with batch status API; backfill eval_results table next morning
4. Dashboard shows "eval in progress" status for recent predictions

**Phase 1 timeline:** Phase 1b (week 3-4), after confirming daily LLM costs stabilize.

---

### Recommendation 3: React State Management + Zustand Refactor (MEDIUM Impact, Technical Debt)
**Priority:** MEDIUM-LOW | **Effort:** 2-3 days | **Payoff:** Cleaner code, potential 50-70% re-render reduction if validated

**Rationale:**
- Current mutable ref + batching is functional but unconventional
- Zustand provides cleaner state separation (UI state vs. data state) and better devtools integration
- 70% re-render reduction observed in comparable dashboards; worth benchmarking

**Implementation:**
1. Move UI-level state (agent feed, indicators, timeline position) to Zustand store
2. Keep H3 hex data in mutable ref (still the right choice for high-frequency updates)
3. Replace Context providers with Zustand hooks
4. Benchmark before/after: measure re-render count and interaction latency during high WebSocket load

**Phase 1 timeline:** Post-MVP (week 4-5), only if performance testing reveals bottlenecks. Otherwise, Phase 2.

---

## Not Recommended (Out of Scope)

- **LangGraph adoption:** Phase 1's custom DES + async architecture is tighter and more predictable
- **Extended thinking for sub-actors:** Cost/latency not justified for MVP; consider for Phase 2 if conflict resolution becomes limiting
- **GDELT replacement:** No viable alternative; current four-stage filter is sophisticated
- **Full Zustand migration before benchmarking:** Current design is already optimized; refactor only if validated as bottleneck
- **DeepEval integration:** Parallax's custom eval framework is more specialized; optional for Phase 2 bias detection

---

## Links & Sources

**Spatial/Geo:**
- [DuckDB Spatial Extension](https://duckdb.org/docs/current/core_extensions/spatial/overview)
- [DuckDB Geospatial GIS](https://tech.marksblogg.com/duckdb-geospatial-gis.html)
- [deck.gl Performance Guide](https://deck.gl/docs/developer-guide/performance)
- [deck.gl GitHub #6869](https://github.com/visgl/deck.gl/discussions/6869)

**LLM/Agent:**
- [Claude API Pricing](https://platform.claude.com/docs/en/about-claude/pricing)
- [Prompt Caching Docs](https://platform.claude.com/docs/en/build-with-claude/prompt-caching)
- [Batch API Cost Optimization](https://claudelab.net/en/articles/api-sdk/claude-api-batch-processing-cost-optimization)
- [Extended Thinking](https://platform.claude.com/docs/en/build-with-claude/extended-thinking)
- [Extended Thinking Tips](https://platform.claude.com/docs/en/build-with-claude/prompt-engineering/extended-thinking-tips)
- [LangGraph Overview](https://www.langchain.com/langgraph)
- [Agentic Orchestration Frameworks 2026](https://aimultiple.com/agentic-orchestration)

**Real-Time Data:**
- [aisstream.io](https://www.aisstream.io/)
- [AIS Hub](https://www.aishub.net/)
- [Datalastic AIS API](https://datalastic.com/)
- [VesselFinder AIS Data](https://www.vesselfinder.com/realtime-ais-data)
- [Portcast Vessel Tracking](https://www.portcast.io/ocean-vessel-tracking-api)
- [Kpler Maritime Data](https://www.kpler.com/product/maritime/data-services)
- [GDELT Solutions](https://www.gdeltproject.org/solutions.html)
- [World Monitor Intelligence Dashboard](https://darkwebinformer.com/world-monitor-a-free-open-source-global-intelligence-dashboard-with-25-data-layers-and-ai-powered-threat-classification/)

**Evaluation & MLOps:**
- [LLM Evaluation Frameworks 2026](https://www.mlaidigital.com/blogs/llm-model-evaluation-frameworks-a-complete-guide-for-2026)
- [Best LLM Evaluation Tools 2026](https://medium.com/online-inference/the-best-llm-evaluation-tools-of-2026-40fd9b654dce)
- [DeepEval Framework](https://github.com/confident-ai/deepeval)

**Frontend Performance:**
- [React WebSocket Optimization Part II](https://medium.com/@SanchezAllanManuel/optimizing-real-time-performance-websockets-and-react-js-integration-part-ii-4a3ada319630)
- [WebSockets in React 2026](https://oneuptime.com/blog/post/2026-01-15-websockets-react-real-time-applications/view)
- [React Performance Best Practices 2025](https://dev.to/alex_bobes/react-performance-optimization-15-best-practices-for-2025-17l9)

**Embeddings:**
- [Best Open-Source Embeddings 2026](https://www.bentoml.com/blog/a-guide-to-open-source-embedding-models)
- [Geospatial Embeddings](https://github.com/hfangcat/Awesome-Geospatial-Embeddings)

---

**Report Generated:** 2026-04-02  
**Scout:** Daily Tech Research (Claude Code)  
**Next Review:** 2026-04-03
