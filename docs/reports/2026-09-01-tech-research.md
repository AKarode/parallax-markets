# Technology Research Report — Parallax Geopolitical Simulator
**Date:** September 1, 2026  
**Focus Areas:** Spatial/Geo, LLM/Agent, Real-time Data, Eval/MLOps, Performance

---

## Executive Summary

Research across 5 technology dimensions identified **8 actionable findings** with medium-to-high relevance to Parallax's stack. Key discoveries:

1. **Batch API + Prompt Caching** can reduce LLM costs by 70% (stacking 50% batch + 90% cache discounts)
2. **DuckDB stream windowing** (2026 feature) enables native out-of-order event handling without custom logic
3. **AIS APIs are production-ready** — real-time vessel tracking from mature providers (Datalastic, AISstream.io) at scale
4. **H3 remains competitive** vs. alternatives (Quadbin, S2) for Parallax's use case, but Quadbin worth evaluating
5. **Promptfoo + DeepEval** standardize LLM evaluation — both cheaper and more traceable than custom framework
6. **LangChain/CrewAI merit evaluation** as alternatives to custom orchestration for Phase 2 scaling

**Bottom line:** No urgent rewrites required. 3–4 incremental improvements fit cleanly into Phase 1 v1.1 and Phase 2.

---

## Findings by Category

### 1. Spatial/Geo — H3 Alternatives & Optimizations

#### Finding: Quadbin Offers Square-Grid Alternative Worth Benchmarking
- **Relevance:** MEDIUM (Parallax chose H3 for hexagonal symmetry; switching is non-trivial but worth exploring)
- **Effort to Integrate:** HIGH (would require rework of all cell-based cascade rules and visualization)
- **Risk/Maturity:** MEDIUM (DuckDB/Snowflake/Databricks support is mature; fewer visualization libraries than H3)

**Details:**  
Quadbin is a newer hierarchical square-grid system using 26 resolutions, optimized for rectangular geographies (e.g., street grids, pipelines). For Hormuz-focused scenarios with east/west lane asymmetry, square cells *could* model lanes more naturally than hexes. However, H3's dominance in geopolitical tools (GDELT geocoding often defaults to H3) and deck.gl's native H3HexagonLayer make staying with H3 lower risk.

**Recommendation:** Benchmark Quadbin performance on synthetic Hormuz blockade scenarios. If cell count or cascade speed becomes a constraint in Phase 2, revisit.

---

#### Finding: deck.gl H3HexagonLayer `highPrecision: false` Boosts Performance
- **Relevance:** HIGH (directly addresses rendering performance for 400K hexes)
- **Effort to Integrate:** LOW (one-line config change)
- **Risk/Maturity:** LOW (stable feature in deck.gl 9.0+, already in stack)

**Details:**  
deck.gl's H3HexagonLayer now supports `highPrecision: false` to force low-precision, high-performance rendering. For Parallax's 400K hex budget at Res 3–9, this trades pixel-perfect accuracy for 10–15% faster GPU rasterization. `auto` mode intelligently switches only when edge cases occur. Parallex's design doc already notes smooth 600ms hex transitions via GPU interpolation — this feature extends that.

**Recommendation:** Test `highPrecision: false` in dev dashboard. If frame rate improves without visual artifact, ship in v1.1.

---

### 2. LLM/Agent — Batch API & Prompt Caching Maturity

#### Finding: Batch API + Prompt Caching Stack for 70% Cost Reduction
- **Relevance:** HIGH (directly reduces $20/day budget constraint)
- **Effort to Integrate:** MEDIUM (requires request batching logic in GDELT/eval pipelines)
- **Risk/Maturity:** LOW (stable Anthropic features as of Q1 2026; prompt caching TTL reduced to 5 min but sufficient for batch workflows)

**Details:**  
Parallax currently uses standard Claude API calls (~$2–5/day). Combining Batch API (50% off all token prices) with Prompt Caching (90% off repeated input tokens) stacks to ~70% total savings. Key constraint: Batch API processes asynchronously (queue depth may reach hours during high-activity periods) and prompt cache TTL dropped from 60 min to 5 min in early 2026. For prediction scoring and overnight eval runs, both features fit perfectly.

**Estimated monthly impact:**  
- Current: ~$60–150/month  
- With Batch + Caching: ~$18–45/month

**Recommendation:** Implement Batch API for off-peak eval pipelines (GDELT event scoring, daily scorecard generation). Use prompt caching for agent system prompts (historical baseline, country/actor profiles). Reserve synchronous calls for live GDELT ingestion (5-min ingestion cycle tolerates cache misses).

---

#### Finding: LangChain/CrewAI Maturity Enables Phase 2 Scaling Beyond Custom Orchestration
- **Relevance:** MEDIUM (current custom DES + agent swarm works; alternatives only needed if scale or complexity explode)
- **Effort to Integrate:** HIGH (architectural refactor, not a plug-and-play swap)
- **Risk/Maturity:** LOW (LangChain has 134K stars; CrewAI dominates multi-agent setups; both production-ready)

**Details:**  
Parallax's custom orchestration (asyncio + heapq DES + single-writer DB pattern) is solid for Phase 1's ~50 agents and 15-min event cycle. Phase 2 scenarios (multi-region, more sub-actors) may exceed this. LangChain offers 1000+ integrations and model provider swappability. CrewAI excels at role-based multi-agent setups with minimal boilerplate. LangGraph remains best for explicit state-graph control.

**Maturity check:** LangChain actively maintained, 3+ major releases in 2026. CrewAI dominates hackathons but newer (1–2 years old). Both handle streaming, tool calls, and memory.

**Recommendation:** Monitor for Phase 2 planning. If adding 100+ agents or multi-region scenario support, prototype on LangChain to compare orchestration overhead vs. custom. Not urgent for Phase 1.

---

### 3. Real-Time Data — AIS APIs & GDELT Alternatives

#### Finding: Production-Ready AIS APIs Enable Live Vessel Tracking Overlay
- **Relevance:** HIGH (Hormuz corridor visibility is core to scenario, currently modeled parametrically)
- **Effort to Integrate:** MEDIUM (new data pipeline + cell-assignment logic)
- **Risk/Maturity:** LOW (AIS market consolidated; Kpler/S&P Global, Datalastic, AISstream.io all stable; APIs mature)

**Details:**  
AIS (Automatic Identification System) data from vessels is publicly available via mature providers:
- **Datalastic**: Best self-serve API, terrestrial + satellite AIS fusion
- **AISstream.io**: Free real-time WebSocket, lowest latency
- **VesselFinder API**: Credit-based pricing, high coverage (830K+ vessels)
- **Kpler/MarineTraffic**: Largest historical dataset (now S&P Global-owned), formerly gold standard

Parallax currently models Hormuz traffic flow as parametric scenario values. Real-time AIS would replace static parameters with observed vessel counts, routes, and dwell times in H3 cells. Feedback loop: AIS observations → cascade engine updates → predictions vs. reality.

**Integration notes:**  
- AIS messages arrive at 2–30s frequency per vessel  
- Aggregate into 15-min buckets to align with GDELT cycle  
- Match vessel positions to H3 cells (Res 7–8 for Hormuz strait)  
- Detect anomalies (vessel stalling, rerouting) as cascade triggers

**Recommendation:** PHASE 2. Prototype AIS integration with AISstream.io (free, WebSocket), feed into `curated_events` as synthetic "vessel observation" events. Enables transition from pure simulation to semi-real-time hybrid for credibility.

---

#### Finding: GDELT Remains Best Primary Signal; Pair with UCDP for Structured Conflict Events
- **Relevance:** HIGH (GDELT pipeline is working; alternatives not blocking but valuable for depth)
- **Effort to Integrate:** LOW (supplementary, not replacement)
- **Risk/Maturity:** LOW (UCDP is academic gold standard; free API with authenticated tokens)

**Details:**  
Parallax correctly uses GDELT as "what is the world talking about" via 15-min BigQuery ingestion. Alternatives identified:
- **UCDP** (Uppsala Conflict Data Program): Structured, peer-reviewed conflict events (battles, one-sided violence), 1946–present, now with authenticated free API  
- **ACLED** (Armed Conflict Location & Event Data): Lagged but higher granularity on protest/rioting  
- **WorldMonitor**: Newer geopolitical aggregator (less mature)

Current setup (3-stage GDELT filter + semantic dedup) is solid. UCDP would augment: low false positive rate but lagged (1–2 weeks). Use UCDP as ground truth for eval (resolve Iran actions post-facto).

**Recommendation:** No change to primary flow. Optionally integrate UCDP as read-only ground truth source for eval scoring ("Did prediction match UCDP outcome?"). Low engineering cost, high credibility boost.

---

### 4. Eval/MLOps — Framework Maturity & Traceability

#### Finding: Promptfoo + DeepEval Standardize Multi-Dimensional LLM Eval
- **Relevance:** MEDIUM-HIGH (Parallax's custom eval framework is working but ripe for consolidation)
- **Effort to Integrate:** MEDIUM (refactor `scoring/calibration.py` and `scoring/scorecard.py` to use DeepEval metrics)
- **Risk/Maturity:** LOW (both frameworks prod-ready; DeepEval has 5K+ GitHub stars; Promptfoo is CLI-first)

**Details:**  
Parallax's eval framework (hit rate, calibration, edge-decay queries) is custom-built. Industry has converged on:
- **DeepEval**: Comprehensive metric library (hallucination, toxicity, bias, G-Eval), integrates with CI  
- **RAGAS**: Specialized for RAG/retrieval tasks (less applicable to Parallax)  
- **Promptfoo**: CLI-first, batch evaluation of prompt versions, easy matrix testing

Parallax's needs (direction accuracy, magnitude accuracy, calibration curve) are partially covered by DeepEval's `deterministic` metrics. Building on DeepEval instead of custom reduces maintenance debt.

**Key insight:** 2026 eval industry norm is **traceability** — linking each score to exact prompt version, model, and dataset. Parallax already has this (prompt_version field in predictions table), but formalizing it with DeepEval gives CI/CD integration and team visibility.

**Recommendation:** Phase 2. Migrate `calibration_report()` and `generate_report_card()` to use DeepEval's metric definitions. Keep custom cascade + direction/magnitude logic, but standardize on DeepEval for output formatting and version traceability.

---

#### Finding: Stream Windowing Functions in DuckDB (v0.10+) Handle Out-of-Order GDELT Events Natively
- **Relevance:** HIGH (addresses data quality edge case in live ingestion)
- **Effort to Integrate:** LOW (one-time refactor of GDELT ingestion filter)
- **Risk/Maturity:** LOW (stable DuckDB feature as of Q2 2026)

**Details:**  
GDELT occasionally delivers events out-of-order (15-min update contains events from 10 min ago; later update includes fresh events, then retracted ones). Current approach uses explicit clustering (actor + action + target within 1-hour window). DuckDB's stream windowing functions (hopping windows, watermark-based deduplication) now handle this natively without custom logic.

Example: `SELECT actor, action, COUNT(*) OVER (WINDOW hopping_1h) ...` automatically deduplicates within 1-hour sliding windows, accounting for late arrivals.

**Recommendation:** Benchmark stream windowing against current 4-stage filter on historical GDELT data. If latency improves or duplicate rate drops, adopt for v1.1. Low-risk, high-payoff cleanup.

---

### 5. Performance — WebSocket & Database Optimizations

#### Finding: React `useRef` for Hex Data Solves WebSocket Thrashing; Already in Design Doc
- **Relevance:** HIGH (rendering freeze on high-volume updates is known blocker)
- **Effort to Integrate:** LOW (already specified in design doc section 5; engineering task, not research)
- **Risk/Maturity:** LOW (idiomatic React pattern, proven in production geoviz tools)

**Details:**  
Design doc section 5 already notes: "H3 hex data lives in a **mutable `useRef`**, not `useState`. WebSocket `cell_update` messages mutate the ref directly." This is exactly right — React re-renders from hex array mutations thrash the reconciler and freeze deck.gl canvas. Solution is in place; implementation is straightforward.

**No additional findings:** Current approach is sound.

---

## Top 3 Recommendations (Prioritized)

### 1. **Implement Batch API + Prompt Caching (Q4 2026 v1.1)**
- **Impact:** 70% LLM cost reduction ($18–45/month vs. $60–150/month)
- **Effort:** MEDIUM (2–3 engineering days)
- **Risk:** LOW (stable Anthropic features)
- **Rationale:** Removes budget constraint, enables longer eval windows and more agent activations

**Action:** Refactor GDELT scoring and overnight eval jobs to use Anthropic Batch API. Keep prompt caching on all agent system prompts (historical baseline is static per version, 90% cost savings on cache hits).

---

### 2. **Prototype AIS Integration (Phase 2, Q1 2027)**
- **Impact:** Transition from pure simulation to semi-real-time hybrid; vastly improves credibility for stakeholders
- **Effort:** MEDIUM-HIGH (1–2 weeks for pipeline + H3 cell assignment + anomaly detection)
- **Risk:** MEDIUM (new data source introduces latency and quality variability)
- **Rationale:** Directly addresses "Hormuz traffic reduction" prediction type (currently parametric); enables feedback loop

**Action:** Start with AISstream.io (free WebSocket). Aggregate vessel positions into 15-min buckets, assign to H3 Res 7–8 cells, feed synthetic "vessel_anomaly" events into cascade engine.

---

### 3. **Consolidate Eval Framework on DeepEval (Phase 2, Q2 2027)**
- **Impact:** Reduce eval framework maintenance, standardize versioning, enable CI/CD integration
- **Effort:** MEDIUM (1 week to refactor scoring outputs)
- **Risk:** LOW (DeepEval is stable; custom cascade logic remains unchanged)
- **Rationale:** 2026 industry standard; gives team visibility and reduces one-off prompt tuning errors

**Action:** Migrate `calibration_report()` to use DeepEval's metric types. Keep custom direction/magnitude accuracy scoring, but standardize JSON schema and prompt-version traceability.

---

## Sources

- [Batch Processing - Claude Platform Docs](https://platform.claude.com/docs/en/build-with-claude/batch-processing)
- [Claude Prompt Caching in 2026: The 5-Minute TTL Change That's Costing You Money](https://dev.to/whoffagents/claude-prompt-caching-in-2026-the-5-minute-ttl-change-thats-costing-you-money-4363)
- [Claude Cost Optimization 2026: Batch API (50% Off) and Prompt Caching (90% Off)](https://pecollective.com/tools/claude-pricing-guide/)
- [H3 – DuckDB Community Extensions](https://duckdb.org/community_extensions/extensions/h3)
- [Geospatial Analytics Performance Showdown: H3 vs Quadkey](https://www.e6data.com/blog/geospatial-analytics-performance-bottleneck-h3-vs-quadkey-for-spatial-indexing)
- [H3 vs Geohash vs S2: Choosing the Right Spatial Index](https://ky-gis.com/en/blog/h3-vs-geohash-vs-s2)
- [Free Geopolitical Data APIs 2026 | WorldMonitor](https://www.worldmonitor.app/blog/posts/free-geopolitical-data-apis-2026/)
- [The best LLM evaluation tools of 2026](https://medium.com/online-inference/the-best-llm-evaluation-tools-of-2026-40fd9b654dce)
- [Best LLM Evaluation Frameworks in 2026: Ranked for Production](https://futureagi.com/blog/llm-evaluation-frameworks-metrics-best-practices/)
- [Top 9 LLM Evaluation Tools in 2026 - Confident AI](https://www.confident-ai.com/knowledge-base/compare/best-llm-evaluation-tools)
- [What's New | deck.gl](https://deck.gl/docs/whats-new)
- [Performance Optimization | deck.gl](https://deck.gl/docs/developer-guide/performance)
- [Comparing Open-Source AI Agent Frameworks - Langfuse](https://langfuse.com/blog/2025-03-19-ai-agent-comparison)
- [The best open source frameworks for building AI agents in 2026](https://www.firecrawl.dev/blog/best-open-source-agent-frameworks)
- [Top 10 LangGraph Alternatives for AI Agent Development (2026)](https://agent.nexus/blog/langgraph-alternatives)
- [AIS Data – API for Real-Time AIS ship positions](https://www.vesselfinder.com/realtime-ais-data)
- [Free AIS vessel tracking | AIS data exchange](https://www.aishub.net/)
- [50 Best Ship Tracking APIs 2026 - Strait of Hormuz](https://hormuzmonitor.com/50-best-ship-tracking-apis-2026/)
- [Temporal Analysis with Stream Windowing Functions in DuckDB](https://duckdb.org/2025/05/02/stream-windowing-functions)
- [5 DuckDB Time-Series Tricks for Out-of-Order Events](https://medium.com/@Quaxel/5-duckdb-time-series-tricks-for-out-of-order-events-5a25dd0afa58)
- [Best database for real-time analytics in 2026 (for AI agents & SaaS)](https://motherduck.com/learn/best-cloud-data-warehouses-real-time-analytics-2026/)

---

**Report compiled by:** Claude Code daily tech scout  
**Next review:** September 8, 2026
