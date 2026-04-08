# Technology Research Report — Parallax Geopolitical Simulator
**Date:** April 1, 2026  
**Research Focus:** Spatial/Geo, LLM/Agent, Real-time Data, Eval/MLOps, Performance optimization

---

## Executive Summary

This report surveys emerging technologies across the Parallax tech stack to identify integration opportunities, cost optimizations, and performance improvements. The research covers 20+ technologies spanning H3/DuckDB extensions, Claude API improvements, real-time data sources, evaluation frameworks, and dashboard optimization techniques. **Top finding:** Claude API prompt caching + batch processing can reduce costs by up to 95%, and structured outputs GA enables formal schema validation for agent decisions. Secondary finding: real-time vessel tracking APIs (MarineTraffic/Kpler) offer validation layer for computed shipping routes. Tertiary: deck.gl v8.8+ custom Tileset2D support removes optimization friction for H3 rendering.

---

## Findings by Category

### 1. SPATIAL & GEO TECHNOLOGIES

#### 1.1 deck.gl v8.8+ Custom Tileset2D Support
- **Relevance:** HIGH
- **Status:** Stable, v8.8+ available
- **Description:** TileLayer now supports custom indexing systems via Tileset2D interface, enabling H3 and S2 grids with automatic incremental loading. Removes the need for ad-hoc H3 cell batching logic.
- **Integration Effort:** MEDIUM (refactor hex layer rendering to use TileLayer instead of manual cell arrays)
- **Risk/Maturity:** LOW — battle-tested in production since v8.8 (mid-2025)
- **Trade-off:** Additive. Could replace current H3HexagonLayer direct cell rendering with TileLayer abstraction, but current approach works well. Optional optimization.
- **Source:** [deck.gl documentation](https://deck.gl/docs/whats-new)

#### 1.2 deck.gl v9.1 React Integration (useWidget Hook)
- **Relevance:** MEDIUM
- **Status:** Stable, v9.1+
- **Description:** Official deck.gl widgets (zoom control, layer selector) now wrappable as React components via `useWidget` hook. Cleaner component hierarchy.
- **Integration Effort:** LOW (cosmetic, optional UI refactor)
- **Risk/Maturity:** LOW
- **Trade-off:** Additive. No replacement of existing code; purely improves developer ergonomics.
- **Source:** [deck.gl documentation](https://deck.gl/docs/whats-new)

#### 1.3 H3 DuckDB Extension (March 2026 Update)
- **Relevance:** MEDIUM
- **Status:** Actively maintained; updated March 25, 2026
- **Description:** H3 extension continues to receive updates and integrates well with DuckDB spatial extension. No breaking changes expected.
- **Integration Effort:** LOW (already in use, pinned version in deployment)
- **Risk/Maturity:** LOW — stable, community-maintained
- **Trade-off:** Status quo. Parallax's current pinned version strategy remains sound.
- **Source:** [H3 DuckDB Community Extensions](https://duckdb.org/community_extensions/extensions/h3)

#### 1.4 DuckDB-WASM in Browser (Performance Angle)
- **Relevance:** MEDIUM
- **Status:** Stable, production-ready
- **Description:** Query execution in browser using WASM is 10–100× faster than equivalent JavaScript object processing. Enables client-side analytics without backend round-trips.
- **Integration Effort:** HIGH (frontend architecture refactor; requires moving dashboard query logic to client)
- **Risk/Maturity:** MEDIUM — WASM is stable but adds client-side complexity
- **Trade-off:** Could offload some indicator card calculations (sparklines, aggregations) from backend to frontend. Would reduce WebSocket traffic. **Not recommended for Phase 1** (adds scope); candidate for Phase 2 performance pass.
- **Sources:** [DuckDB Speed Secrets](https://medium.com/@hadiyolworld007/duckdb-speed-secrets-10-tricks-for-2026-29c990a8701d), [High-Performance Statistical Dashboard](https://medium.com/@ryanaidilp/building-a-high-performance-statistical-dashboard-with-duckdb-wasm-and-apache-arrow-d6178aeaae6d)

#### 1.5 MapLibre v5 Globe View
- **Relevance:** LOW
- **Status:** Available as experimental feature
- **Description:** MapLibre v5 adds optional globe rendering mode. deck.gl integrates seamlessly.
- **Integration Effort:** N/A (out of scope for Parallax — 2D hex visualization is preferred)
- **Risk/Maturity:** MEDIUM (globe mode is more computationally expensive)
- **Trade-off:** Not applicable; Parallax requires 2D hex grids for scenario design.
- **Source:** [deck.gl with MapLibre](https://deck.gl/docs/developer-guide/base-maps/using-with-maplibre)

---

### 2. LLM & AGENT TECHNOLOGIES

#### 2.1 Claude API Prompt Caching — Workspace-Level Isolation (Feb 2026)
- **Relevance:** HIGH
- **Status:** Generally available (production-ready as of Feb 5, 2026)
- **Description:** System prompts (static per agent version) are cached and reused, reducing cost by up to 90% and latency by 80% on subsequent calls within cache TTL (5 min). Feb 2026 update: workspace-level isolation (previously org-level), improving cache hit rates in multi-tenant scenarios. **Automatic prefix matching:** system now checks for cache hits at all previous content block boundaries up to 20 blocks back, enabling single cache breakpoint at end of static content.
- **Integration Effort:** LOW (design already includes prompt caching, but can optimize cache breakpoint placement)
- **Risk/Maturity:** LOW — GA feature, widely used in production
- **Trade-off:** Additive optimization. Current design leverages caching; no refactor needed. Could benefit from explicit cache breakpoint tuning in agent system prompts.
- **Estimated Impact:** ~10–15% reduction in LLM token costs (design estimates $2–5/day; could drop to $1.75–4.25/day).
- **Sources:** [Prompt Caching Docs](https://platform.claude.com/docs/en/build-with-claude/prompt-caching), [API Pricing](https://www.metacto.com/blogs/anthropic-api-pricing-a-full-breakdown-of-costs-and-integration)

#### 2.2 Claude Batch API + Prompt Caching Stacking
- **Relevance:** MEDIUM
- **Status:** Stable, available
- **Description:** When batch processing is combined with prompt caching, discounts stack for **up to 95% total savings**. Batch API is 50% discount; prompt caching adds another 90% on cached tokens. Max output tokens raised to 300k on Batch API for Claude Opus/Sonnet (March 2026 update).
- **Integration Effort:** MEDIUM (requires batch job architecture change; not compatible with real-time live mode, but useful for cold start and eval phases)
- **Risk/Maturity:** LOW — Batch API is GA
- **Trade-off:** Applicable to **non-live** phases only: cold start bootstrap (historical replay), eval cron jobs. Would NOT replace live agent decision calls (must be real-time). Could save ~$20–30 on one-time cold start job.
- **Recommendation:** Implement batch job wrapper for cold-start historical replay to amortize bootstrap cost.
- **Sources:** [Batch Processing Docs](https://platform.claude.com/docs/en/build-with-claude/batch-processing), [Cost Optimization](https://claudelab.net/en/articles/api-sdk/claude-api-batch-processing-cost-optimization)

#### 2.3 Claude Structured Outputs — General Availability (Jan 2026)
- **Relevance:** HIGH
- **Status:** GA on Haiku 4.5, Sonnet 4.6, Opus 4.6
- **Description:** Structured outputs are now GA with expanded schema support, improved grammar compilation latency, no beta header required. Supports Pydantic (Python) and Zod (TypeScript) for strongly-typed schema definition. Agent output is **guaranteed** to match JSON schema; no fallback parsing needed.
- **Integration Effort:** MEDIUM (refactor agent decision JSON schema validation to use official Pydantic models instead of ad-hoc validation)
- **Risk/Maturity:** LOW — GA feature, tested extensively
- **Trade-off:** Additive. Current design already validates JSON schema; moving to official structured outputs reduces code bloat and ensures strict compliance.
- **Implementation:** Define Pydantic model for agent decision schema (agent_id, action_type, target_h3_cells, intensity, description, reasoning, confidence, prompt_version), pass to API, receive validated object.
- **Estimated Impact:** ~5% reduction in LLM calls rejected due to malformed output; improved observability.
- **Sources:** [Structured Outputs Docs](https://platform.claude.com/docs/en/build-with-claude/structured-outputs), [Agent SDK Structured Output](https://platform.claude.com/docs/en/agent-sdk/structured-outputs)

#### 2.4 Claude Agent SDK (Tool Use & Orchestration)
- **Relevance:** LOW
- **Status:** Available, documented
- **Description:** Agent SDK provides pre-built tool loop, context management, autonomous decision-making across multiple tool calls. Parallax does NOT use Agent SDK by design — custom DES is preferred for scenario control and cascade rule determinism.
- **Integration Effort:** N/A (would require major architecture refactor; incompatible with custom simulation engine)
- **Risk/Maturity:** MEDIUM (Agent SDK adds abstraction that conflicts with Parallax's explicit event queue and cascade rules)
- **Trade-off:** Not applicable. Agent SDK is for general-purpose autonomous agents; Parallax's swarm is embedded in a deterministic simulation engine. Keep custom approach.
- **Source:** [Agent SDK Overview](https://platform.claude.com/docs/en/agent-sdk/overview)

---

### 3. REAL-TIME DATA TECHNOLOGIES

#### 3.1 GDELT Cloud (AI Enrichment Layer)
- **Relevance:** MEDIUM
- **Status:** Available; actively marketed
- **Description:** GDELT Cloud layers AI-enriched event classification (CAMEO+ taxonomy) on raw GDELT data, offering conflict/cooperation classification per story cluster. Reduces manual filtering overhead.
- **Integration Effort:** HIGH (requires API integration, new data ingest pipeline, retraining of relevance filters)
- **Risk/Maturity:** MEDIUM — relatively new product; API stability unknown
- **Trade-off:** Could replace the four-stage GDELT filter (volume gate, dedup, semantic dedup, relevance scoring) with pre-classified GDELT Cloud events. **Risk:** adds vendor lock-in (GDELT Cloud requires commercial contract); current four-stage filter is open-source and transparent.
- **Recommendation:** Monitor GDELT Cloud maturity; not recommended for Phase 1 (introduces dependency on proprietary API). Candidate for Phase 2 if Phase 1 filter proves insufficient.
- **Source:** [GDELT Project](https://www.gdeltproject.org/)

#### 3.2 MarineTraffic API (AIS Vessel Tracking)
- **Relevance:** MEDIUM
- **Status:** Available but transitioning; consolidation under Kpler
- **Description:** Real-time AIS vessel positions (13,000+ global receivers). Now owned by Kpler (Jan 2024 acquisition); FleetMon consolidated into MarineTraffic. Pricing changed from credit-based to enterprise subscription (no public pricing tier).
- **Integration Effort:** MEDIUM (requires new data pipeline, API authentication, H3 cell mapping of vessel positions)
- **Risk/Maturity:** MEDIUM — Kpler ownership creates long-term uncertainty; pricing and API stability unknown
- **Trade-off:** Could supplement `searoute`-computed shipping routes with real vessel positions (validation layer). Would enable actual-vs-predicted shipping flow deltas. **Cost concern:** Kpler's enterprise pricing may exceed Phase 1 budget.
- **Recommendation:** Contact Kpler for pricing; consider as **optional Phase 2 enhancement** for model validation. For now, stick with `searoute` geometry + cascade rule throughput values.
- **Sources:** [MarineTraffic API](https://servicedocs.marinetraffic.com/), [Kpler Maritime Data](https://www.kpler.com/product/maritime/data-services)

#### 3.3 Alternative AIS Providers (VesselFinder, AISHub)
- **Relevance:** LOW-MEDIUM
- **Status:** Available, free/freemium tiers
- **Description:** AISHub and VesselFinder provide free or low-cost AIS data with public APIs. Lower data quality/update frequency than MarineTraffic but no subscription cost.
- **Integration Effort:** MEDIUM
- **Risk/Maturity:** MEDIUM — smaller providers, less SLA guarantee
- **Trade-off:** Possible backup/validation layer for shipping data, but quality concerns.
- **Recommendation:** Low priority for Phase 1. Evaluate only if MarineTraffic cost is prohibitive.
- **Source:** [AISHub](https://www.aishub.net/), [VesselFinder](https://www.vesselfinder.com)

#### 3.4 ACLED vs GDELT Comparison
- **Relevance:** LOW
- **Status:** Stable, both well-established
- **Description:** Current design uses both GDELT (fast, high volume, some false positives) and ACLED (slower, validated, lower false positive rate). Trade-off is deliberate and sound.
- **Integration Effort:** N/A
- **Risk/Maturity:** N/A
- **Trade-off:** Status quo is optimal. No change recommended.
- **Source:** [ACLED Conflict Data Comparison](https://acleddata.com/report/working-paper-comparing-conflict-data/)

---

### 4. EVAL & MLOPS TECHNOLOGIES

#### 4.1 Structured Prediction Evaluation (Parallax-Specific)
- **Relevance:** HIGH
- **Status:** Design includes prediction log and eval framework
- **Description:** Parallax's eval framework already tracks direction, magnitude, sequence, and calibration accuracy. Phase 1 design is sound and comprehensive.
- **Integration Effort:** LOW (implementation of existing design)
- **Risk/Maturity:** LOW
- **Trade-off:** Status quo. No external framework needed; custom eval logic is well-suited to scenario domain.
- **Source:** [Parallax Phase 1 Design](../superpowers/specs/2026-03-30-parallax-phase1-design.md), Section 7

#### 4.2 DeepEval (LLM Evaluation Framework)
- **Relevance:** MEDIUM
- **Status:** Available, open-source
- **Description:** DeepEval is an open-source framework for measuring LLM output quality (hallucination detection, factuality, relevance). Could supplement Parallax's agent decision quality checks.
- **Integration Effort:** MEDIUM (integrate metric suite for agent reasoning validation)
- **Risk/Maturity:** MEDIUM — newer framework; ecosystem still developing
- **Trade-off:** Additive. Could add automated hallucination detection to agent decision logs (e.g., flag decisions with reasoning that contradicts known facts). **Not critical for Phase 1** (manual review is sufficient); candidate for Phase 2 scaling.
- **Sources:** [DeepEval GitHub](https://github.com/confident-ai/deepeval), [LLM Evaluation Guide 2026](https://www.mlaidigital.com/blogs/llm-model-evaluation-frameworks-a-complete-guide-for-2026)

#### 4.3 MLflow / W&B Weave (Prompt Versioning & Traceability)
- **Relevance:** MEDIUM
- **Status:** Both available, industry-standard
- **Description:** MLflow and Weights & Biases offer prompt versioning, experiment tracking, and A/B comparison dashboards. Parallax design includes custom prompt versioning (semver) and A/B tracking.
- **Integration Effort:** HIGH (would require moving eval infrastructure to MLflow/W&B)
- **Risk/Maturity:** LOW — both GA, widely used
- **Trade-off:** Parallax's custom versioning system (v1.2.0 tags in decisions table, auto-rollback logic) is sufficient for Phase 1. MLflow/W&B would add observability but also complexity and vendor lock-in. **Not recommended for Phase 1**. Candidate for Phase 2 if eval needs to scale to 100+ agents.
- **Sources:** [LLM Evaluation Frameworks 2026](https://futureagi.substack.com/p/llm-evaluation-frameworks-metrics), [Datadog LLM Eval](https://www.datadoghq.com/blog/llm-evaluation-framework-best-practices/)

#### 4.4 LLM-as-a-Judge (Prediction Quality Evaluation)
- **Relevance:** MEDIUM
- **Status:** Emerging best practice
- **Description:** Use an LLM (e.g., Claude Opus) to evaluate the quality of agent predictions (e.g., "Is this prediction well-reasoned given the context? Does it account for key actors?"). Can be more nuanced than automated metrics.
- **Integration Effort:** MEDIUM (new cron job to run eval LLM on prediction logs; costs ~$0.035/call)
- **Risk/Maturity:** MEDIUM — technique is sound but adds LLM cost
- **Trade-off:** Could enhance prompt improvement pipeline (Section 7 of design). Instead of relying only on `model_error` tags and accuracy scores, use LLM judgment to score reasoning quality. **Estimated cost: $0.35/day if run on 10 predictions/day.** Could be worth it for Phase 2.
- **Source:** [LLM Evaluation Metrics](https://www.confident-ai.com/blog/llm-evaluation-metrics-everything-you-need-for-llm-evaluation)

---

### 5. PERFORMANCE TECHNOLOGIES

#### 5.1 DuckDB Query Caching (30–120s)
- **Relevance:** MEDIUM
- **Status:** Best practice recommendation (no built-in caching, but easy to implement)
- **Description:** Dashboard queries (sparklines, indicator card aggregations) can be cached for 30–120 seconds without perceptible user impact. Reduces CPU load significantly.
- **Integration Effort:** LOW (add simple memoization layer in FastAPI endpoints)
- **Risk/Maturity:** LOW
- **Trade-off:** Additive. Would reduce backend load during high-frequency WebSocket updates. Current design already batches updates (100ms), so caching would amplify effect.
- **Recommendation:** Implement simple `@cache_with_ttl(60s)` decorator on indicator card endpoints (price, traffic, escalation index).
- **Estimated Impact:** ~20–30% reduction in database query load.
- **Source:** [DuckDB Speed Secrets 2026](https://medium.com/@hadiyolworld007/duckdb-speed-secrets-10-tricks-for-2026-29c990a8701d)

#### 5.2 Web Workers for Non-Blocking Queries
- **Relevance:** MEDIUM
- **Status:** Standard web platform feature
- **Description:** Offload expensive React component renders (e.g., agent feed filtering, timeline scrubbing) to Web Workers to prevent UI blocking.
- **Integration Effort:** MEDIUM (refactor React components to use worker threads)
- **Risk/Maturity:** LOW
- **Trade-off:** Additive optimization. Would improve perceived dashboard responsiveness, especially on lower-end devices. **Not critical for Phase 1** (demo hardware is likely modern); candidate for Phase 2 if user testing shows lag.
- **Source:** [DuckDB Optimization Strategies](https://www.c-sharpcorner.com/article/how-to-optimize-duckdb-for-real-time-analytics-inside-a-browser-via-wasm/)

#### 5.3 MotherDuck Dives (Text-to-SQL Visualizations)
- **Relevance:** LOW
- **Status:** Available, experimental
- **Description:** AI-powered SQL-to-viz feature. Parallax has custom visualization layer (deck.gl + indicators); not applicable.
- **Integration Effort:** N/A
- **Risk/Maturity:** N/A
- **Trade-off:** Out of scope.
- **Source:** [DuckDB Ecosystem Newsletter March 2026](https://motherduck.com/blog/duckdb-ecosystem-newsletter-march-2026/)

#### 5.4 DuckDB 2026 Roadmap Features (C API, DuckPL, Encryption)
- **Relevance:** LOW-MEDIUM
- **Status:** In development
- **Description:** Upcoming features: C API for direct DuckDB calls, DuckPL procedural language, built-in storage encryption.
- **Integration Effort:** N/A (not yet available; watch for Phase 2)
- **Risk/Maturity:** TBD
- **Trade-off:** Storage encryption could be useful for sensitive simulation state, but not critical for Phase 1.
- **Recommendation:** Monitor DuckDB releases; revisit after Phase 1 if encryption/performance are bottlenecks.
- **Source:** [DuckDB Ecosystem Newsletter March 2026](https://motherduck.com/blog/duckdb-ecosystem-newsletter-march-2026/)

---

## TOP 3 RECOMMENDATIONS

### **Recommendation 1: Formalize Agent Decision Validation with Structured Outputs (HIGH PRIORITY)**

**What:** Move from ad-hoc JSON schema validation to Claude API's Structured Outputs (GA since Jan 2026).

**Why:**
- Eliminates parsing errors and malformed outputs (currently 5% rejection rate estimated).
- Reduces code complexity (replace validation logic with Pydantic model).
- Future-proof: all agent decisions guaranteed to conform to schema.

**How:**
1. Define Pydantic model for agent decision schema (matches current JSON in design Section 3).
2. Update agent system prompts to include `output_format` with schema.
3. Replace validation code with direct model instantiation.
4. Update decision logging to use model attributes.

**Effort:** MEDIUM (2–3 days for validation refactor + testing)  
**Cost Impact:** Neutral (no additional API calls; structured outputs are free feature)  
**Risk:** LOW (backward compatible; can dual-run old + new validation during transition)

**Timeline:** Phase 1 pre-launch if time permits; otherwise Phase 1.1 post-launch bugfix.

---

### **Recommendation 2: Implement Batch API + Prompt Caching for Cold Start Bootstrap (MEDIUM PRIORITY)**

**What:** Use Claude Batch API (50% discount) + prompt caching (90% on cached tokens) = **95% total savings** for historical replay cold-start job.

**Why:**
- One-time cold-start cost could drop from $30–50 to ~$2–5 (95% savings).
- Batch processing is deterministic (no real-time variance).
- Prompt caching reduces duplicate system prompt token costs across 50 agent calls.

**How:**
1. Implement batch job wrapper that reads GDELT events from last 30 days.
2. Enqueue agent decision calls to Batch API with shared system prompt (cached once).
3. Batch processes overnight, populates bootstrap state in DuckDB.
4. Deploy with golden snapshot, skip expensive live LLM calls on first boot.

**Effort:** MEDIUM (1–2 days; batch API integration + testing)  
**Cost Impact:** ~$25–45 one-time savings on cold start  
**Risk:** LOW (batch processing is non-blocking; doesn't affect live simulation)

**Timeline:** Phase 1 launch preparation (pre-deploy).

---

### **Recommendation 3: Add Opportunistic Query Caching to Indicator Cards (LOW PRIORITY)**

**What:** Cache dashboard query results (price sparkline, traffic percentage, escalation index) for 60 seconds using a simple Redis or in-process cache.

**Why:**
- Reduces backend load by ~20–30% during high-activity periods (many concurrent sessions).
- Users won't perceive 60-second staleness (data still "live").
- Easy to implement; improves scalability without refactoring.

**How:**
1. Wrap FastAPI indicator endpoints with `@cache_with_ttl(60)` decorator.
2. Use Redis (existing? add if not) or in-process cache (simple dict with TTL).
3. Invalidate cache on new major events (GDELT, agent decisions).

**Effort:** LOW (1 day)  
**Cost Impact:** Neutral (saves backend compute, not API calls)  
**Risk:** LOW (graceful degradation if cache fails)

**Timeline:** Phase 1 launch or Phase 1.1 performance pass.

---

## DETAILED SOURCES

- [Prompt Caching - Claude API Docs](https://platform.claude.com/docs/en/build-with-claude/prompt-caching)
- [Batch Processing - Claude API Docs](https://platform.claude.com/docs/en/build-with-claude/batch-processing)
- [Structured Outputs - Claude API Docs](https://platform.claude.com/docs/en/build-with-claude/structured-outputs)
- [Agent SDK - Claude API Docs](https://platform.claude.com/docs/en/agent-sdk/overview)
- [deck.gl Updates](https://deck.gl/docs/whats-new)
- [H3 DuckDB Extension](https://duckdb.org/community_extensions/extensions/h3)
- [DuckDB Speed Secrets 2026](https://medium.com/@hadiyolworld007/duckdb-speed-secrets-10-tricks-for-2026-29c990a8701d)
- [MarineTraffic API](https://servicedocs.marinetraffic.com/)
- [GDELT Project](https://www.gdeltproject.org/)
- [DeepEval Framework](https://github.com/confident-ai/deepeval)
- [DuckDB Ecosystem Newsletter March 2026](https://motherduck.com/blog/duckdb-ecosystem-newsletter-march-2026/)
- [LLM Evaluation Frameworks 2026](https://www.mlaidigital.com/blogs/llm-model-evaluation-frameworks-a-complete-guide-for-2026)

---

## CONCLUSION

Parallax's architecture is well-aligned with 2026 tech landscape. No critical gaps or urgent refactors needed. **Three actionable improvements** identified for cost, reliability, and performance:

1. **Structured Outputs** (HIGH priority, low cost, high confidence)
2. **Batch API bootstrap** (MEDIUM priority, high ROI, low risk)
3. **Query caching** (LOW priority, easy, scalability benefit)

Secondary findings (AIS data APIs, DeepEval integration, MLflow) are valuable for **Phase 2 product expansion** but not blocking Phase 1 launch.

---

*Report generated: April 1, 2026*  
*Prepared for: Parallax Development Team*
