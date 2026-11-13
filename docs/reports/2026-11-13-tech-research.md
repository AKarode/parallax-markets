# Tech Research Report: Parallax Tech Stack Improvements
**Date:** November 13, 2026  
**Focus Areas:** Spatial/Geo, LLM/Agent, Real-time Data, Eval/MLOps, Performance

---

## Overview

This report identifies emerging technologies and improvements that could strengthen Parallax's existing stack (DuckDB + H3, deck.gl, FastAPI, Claude API, GDELT ingestion). Findings are sourced from 2026 releases, vendor announcements, and practitioner reports. Only genuinely useful findings are included.

---

## Findings by Category

### 1. Spatial & Geospatial Visualization

#### H3 Library Updates (v4.5.0, May 2026)
- **Relevance:** HIGH
- **Effort:** LOW (drop-in upgrade)
- **Risk:** LOW (minor version bump)
- **Details:** H3 v4.5.0 released May 2026 with new bulk APIs (`latLngsToCells` and others). Swift bindings updated to 0.6.0. JavaScript and Python bindings have not yet exposed these bulk operations, so DuckDB C-level calls are available but higher-level SDKs lag.
- **For Parallax:** A minor upgrade; most benefit is for future C library improvements. Check release notes for performance gains.

#### deck.gl v9.3 Release (April 2026) & H3 Integration
- **Relevance:** MEDIUM
- **Effort:** MEDIUM (integration testing, potential UI tweaks)
- **Risk:** LOW (tested in production)
- **Details:** deck.gl 9.3 (April 2026) improves H3HexagonLayer rendering. Earlier 9.2 preview added WebGPU support and new widgets. H3 support added to ClusterTileLayer in 9.2.
- **For Parallax:** Current stack uses deck.gl 9.1.0. Upgrade to 9.3 could improve hex rendering performance and unlock ClusterTileLayer for aggregated views. Test hex transition performance and memory footprint.

#### DuckDB H3 Extension Performance Gains
- **Relevance:** HIGH
- **Effort:** LOW (already integrated)
- **Risk:** LOW (extension well-maintained)
- **Details:** Recent benchmarks show 20x speedups for point-to-H3 aggregation vs pure Python. DuckDB SQL is faster than Python/JavaScript bindings for spatial operations. Extension available via community repository. No official 2026 benchmarks, but April 2025 work confirms performance edge on R-tree queries.
- **For Parallax:** Current design already uses the extension. Ensure it's pinned to latest stable version and profile `world_state_delta` joins with H3 cell filters to confirm speedups.

#### Spatial Index Caveats
- **Relevance:** MEDIUM (architectural note)
- **Effort:** NONE (awareness only)
- **Risk:** NONE
- **Details:** DuckDB spatial indexes do not optimize `ST_DWithin` queries. Spherical geometry (proper distance math) requires manual projection in DuckDB; PostGIS handles this natively. H3 hexagon distances are implicit in the grid hierarchy.
- **For Parallax:** No action required; design already uses H3 hierarchical structure. Distances between cells are computed from hierarchy, not spherical calculations.

---

### 2. LLM & Agent Frameworks

#### Claude API Prompt Caching & Batch API
- **Relevance:** HIGH (cost control critical to Phase 1 budget)
- **Effort:** MEDIUM (integration to agent calling pattern)
- **Risk:** LOW (well-documented, widely adopted)
- **Details:**
  - **Prompt caching:** Cached input tokens cost ~90% less than normal (secondary sources claim). 5-minute TTL per session. Cached prefix must be reused within TTL.
  - **Batch API:** Non-real-time requests discounted ~50%. Ideal for eval meta-agent calls and post-hoc analysis.
  - **Combined stacking:** Both discounts stack. Haiku cached input batch cost reported as $0.05 per 1M tokens (unverified; check official pricing).
  - **Current design already plans caching:** System prompts (historical baselines) are large and static — perfect for caching. Per-call savings estimated at 90% on cached system prompt.
- **For Parallax:** 
  - Verify caching TTL with production tests; if 5 minutes is stable, all sub-actor calls within a 5-minute window reuse the same cached system prompt.
  - Batch API: defer eval meta-agent calls to daily batch for 50% discount.
  - Estimated additional savings: $2–5/day depending on hit rate and call volume.

#### Claude Agent SDK Structured Output
- **Relevance:** MEDIUM
- **Effort:** MEDIUM (refactor agent output parsing)
- **Risk:** LOW
- **Details:** Claude SDK (Python/TypeScript) offers autonomous tool execution, structured outputs via Pydantic models, streaming, and cost tracking. Structured output applies to the final response; tools fire freely during the loop.
- **For Parallax:** Current design validates agent JSON output manually. Could migrate to `messages.parse()` with Pydantic model for `AgentDecision` to reduce parsing errors and enforce schema at API boundary.

#### Managed Agents (Claude)
- **Relevance:** LOW (out of scope for Phase 1)
- **Effort:** HIGH (architectural change)
- **Risk:** MEDIUM (new abstraction)
- **Details:** Claude Managed Agents layer adds native scheduling, evaluation checkpoints ("Outcomes"), and multi-agent orchestration. Still requires coordinator logic and error handling.
- **For Parallax:** Deferred to Phase 2. Current asyncio loop works; Managed Agents would be useful for cross-country agent dependencies in Phase 2 multi-scenario runs.

---

### 3. Real-Time Data Sources

#### AIS Vessel Tracking APIs (New 2026 Launches)
- **Relevance:** HIGH (direct supplement to GDELT for Hormuz shipping)
- **Effort:** MEDIUM (API integration, schema mapping)
- **Risk:** MEDIUM (vendor lock-in, pricing varies)
- **Details:**
  - **LSEG Vessel Tracking API (March 2026 launch):** Real-time AIS from satellite + terrestrial. Single endpoint for position, speed, course, destination, ETA, draught.
  - **Kpler AIS:** Single live positions endpoint. ~5-second data latency. Supports Kafka streaming and NMEA feeds.
  - **Lloyd's List Intelligence Vessel Movements API:** AIS positions + port calls + ETAs via AIS SeaOrbis.
  - **Terrestrial-only:** AIS Hub, MyShipTracking (cheaper, but coastal only).
  - **Coverage:** Satellite-backed options (LSEG, Kpler) offer global coverage; terrestrial (AIS Hub) covers shipping lanes near shore.
  - **Pricing:** All commercial; most use credit/plan metering. No pricing in search results; check vendors directly.
- **For Parallax:**
  - **Immediate value:** Hormuz shipping data is a key signal. AIS data would provide real-time vessel counts and route changes, complementing GDELT event narrative.
  - **Integration approach:** Fetch live AIS data for Hormuz region (add to ingestion pipeline). Map vessel positions to H3 cells at res 7-8 (Hormuz resolution). Feed into cascade engine as `flow` updates.
  - **Source reliability:** LSEG and Kpler are established, low-latency, GDPR/regulatory-friendly. Start with either; LSEG may be easiest for enterprise adoption later.
  - **Cost impact:** Likely $500–5K/month depending on plan. Evaluate against $20/day LLM budget.

#### GDELT Cloud (Commercial Layer)
- **Relevance:** MEDIUM (upgrade from public GDELT)
- **Effort:** LOW (if using existing GDELT ingestion)
- **Risk:** LOW
- **Details:** GDELT Cloud is a commercial REST API + MCP layer on top of public GDELT. Structured events, stories, entities. Free tier available. Hourly ingest latency (~15 min typical). History before March 2026 being backfilled.
- **For Parallax:** Current design uses BigQuery GDELT directly. GDELT Cloud may not provide latency improvement over BigQuery. Worth exploring if free tier has structured event quality gains.

#### World Monitor (Real-Time Dashboard)
- **Relevance:** LOW (business intelligence tool, not data source)
- **Effort:** NONE
- **Risk:** NONE
- **Details:** Real-time dashboard ingesting GDELT, with composite scoring. Offers API and MCP server. Useful as a reference dashboard for evaluation, not as a data source to replace GDELT.
- **For Parallax:** Not applicable; use as a comparison baseline during eval.

#### ACLED (Political Violence Data)
- **Relevance:** MEDIUM (already in design as weekly batch)
- **Effort:** NONE (already integrated)
- **Risk:** NONE
- **Details:** High-quality human-verified conflict data, but operates on a strategic delay (not real-time). Commercial use requires license.
- **For Parallax:** Design already includes ACLED. No upgrade needed.

---

### 4. Evaluation & MLOps

#### Prompt Versioning + A/B Testing Frameworks
- **Relevance:** HIGH (critical to eval loop already in design)
- **Effort:** MEDIUM (integrate tooling or build bespoke)
- **Risk:** LOW
- **Details:**
  - **Best practice:** Git-style prompt history + eval-gated promotion + production rollback.
  - **Evaluation approach:** Offline evals on historical data → shadow scoring on live events → canary roll-out → full A/B test → CI/CD regression gate.
  - **Statistics:** Non-deterministic LLM output requires bootstrap confidence intervals and paired evals; standard product A/B sample sizes underestimate what's needed.
  - **Tools:** LangSmith ($39+/seat/mo), Langfuse (open-source option with A/B support), Confident AI, Maxim AI, Arize Phoenix. Open-source DeepEval also available.
  - **Dataset versioning:** Content-hashed datasets prevent silent data drift during experiments.
- **For Parallax:**
  - Current design includes prompt versioning and eval framework. Ensure:
    - Each agent prompt tagged with semver.
    - Predictions logged with prompt version.
    - Eval scoring compares performance per-version over rolling windows.
    - Model error misses feed into prompt refinement pipeline.
  - **Optional upgrade:** Integrate LangSmith or build bespoke tooling for A/B gating. Design is already 80% there; tooling provides dashboards and automation.

#### LLM Evaluation Frameworks
- **Relevance:** MEDIUM (not critical for Phase 1, improves Phase 2)
- **Effort:** MEDIUM (add eval harness)
- **Risk:** LOW
- **Details:** Frameworks like DeepEval (open-source) and commercial tools support calibration, direction accuracy, sequence accuracy, and confidence scoring. Many support bootstrap CIs and paired comparisons.
- **For Parallax:** Current design includes custom scoring (direction, magnitude, calibration). Consider adopting DeepEval or similar as a library for standardized metrics if scale demands it.

---

### 5. Performance

#### DuckDB Performance Tuning
- **Relevance:** HIGH (critical for state growth management)
- **Effort:** LOW (profiling and parameter tuning)
- **Risk:** NONE
- **Details:**
  - **Profiling:** Use `EXPLAIN ANALYZE` to identify bottlenecks before tuning.
  - **Settings:** Explicitly set `memory_limit` and `threads` for large workloads.
  - **Queries:** Predicate pushdown reduces disk I/O. Parquet partitioning helps skip irrelevant files.
  - **Delta table strategy (Phase 1 design):** Append-only delta + periodic snapshots avoids the naive full-snapshot problem (38.4M rows/day would overflow). Current design is optimal.
  - **Indexing:** Hash joins efficient if join keys are well-chosen. No R-tree optimization for distance queries (not a bottleneck for H3 hierarchical distances).
  - **Out-of-memory warning:** Some aggregate functions (esp. complex states) cannot offload to disk; be careful with GROUP BY on large datasets.
- **For Parallax:**
  - Profile `world_state_delta` joins and `predictions` rollup queries periodically.
  - Monitor that delta table growth stays manageable (current design caps retention at 30 days).
  - Storage expectation: ~38.4M delta rows/day if all hexes change; realistically much less since most cells are static.

#### WebSocket Optimization for Real-Time Dashboards
- **Relevance:** HIGH (frontend performance critical)
- **Effort:** MEDIUM (refactoring React state management)
- **Risk:** LOW
- **Details:**
  - **Decouple render rate from data rate:** Buffer incoming WebSocket messages, flush every 100ms instead of per-message.
  - **Mutable useRef for hot data:** Hex data lives in a mutable `useRef`, not `useState`. WebSocket updates mutate directly; React re-renders only for UI-level changes (agent feed, indicators).
  - **Bypass React for hot data:** Live price ticker or real-time cell flow can write directly to DOM if reconciliation overhead is unacceptable.
  - **Virtualization:** Tables with 100+ rows must use virtualization (react-window, react-virtualized) to avoid rendering all rows.
  - **React Query:** Push WebSocket updates into cache with `setQueryData` for smart UI coordination.
- **For Parallax:**
  - Current design already planned this: "H3 hex data lives in a mutable useRef, not useState." Ensure implementation follows this pattern.
  - Test high-frequency WebSocket updates (100+ cell updates/sec) on the target hardware to confirm no render thrashing.
  - Batching 100ms is a safe default; monitor and tune to balance latency and smoothness.

#### React Rendering for Large Datasets
- **Relevance:** MEDIUM (affects dashboard responsiveness)
- **Effort:** LOW
- **Risk:** NONE
- **Details:** Agent activity feed, decision logs, and GDELT event lists can hit 100+ rows. Virtualization (lazy rendering visible rows) is standard.
- **For Parallax:** Left-panel agent activity feed uses virtualization if it supports scrolling large lists.

---

## Top 3 Recommendations

### 1. **Integrate Real-Time AIS Vessel Tracking (LSEG or Kpler)**
**Priority: HIGH**  
**Rationale:**
- Hormuz shipping data is one of three core prediction signals. GDELT narrative + AIS vessel positions give dual coverage of shipping disruption.
- LSEG (March 2026 launch) and Kpler (established, 5-sec latency) both offer reliable, low-latency global coverage.
- **Action:** Evaluate pricing and coverage with LSEG and Kpler directly. Start with a 2-week trial on Kpler to test integration. Map vessel positions to H3 res 7-8 cells (Hormuz detail). Ingest live vessel counts as `flow` signals into the cascade engine.
- **Cost:** Likely $500–5K/month; evaluate against $20/day LLM budget. May be justified if it improves prediction accuracy.

### 2. **Upgrade deck.gl to v9.3 and Profile H3 Rendering Performance**
**Priority: MEDIUM**  
**Rationale:**
- Current stack runs deck.gl 9.1.0. v9.3 (April 2026) improves H3HexagonLayer rendering and offers WebGPU preview for future scaling.
- Low effort, low risk. Hex rendering is a hot path for the live dashboard.
- **Action:** Upgrade to v9.3. Run performance tests on hex transition animations (cell color changes, zoom). Compare frame rates and memory footprint. If >5% improvement, commit; otherwise stay on 9.1.

### 3. **Ensure Prompt Caching is Active on Agent Calls**
**Priority: HIGH (cost control)**  
**Rationale:**
- Design already plans caching (~90% discount on cached system prompts). System prompts are 2–3K tokens (static per version) and are reused within a 5-minute window.
- **Verification:** Check API responses for `cache_creation_input_tokens` and `cache_read_input_tokens` fields. Confirm cache hits are happening.
- **Action:** Log cache hit/miss ratio daily. If hit rate < 70%, investigate TTL issues or batch structure. Target: 80%+ hit rate for sub-actor system prompts.
- **Expected savings:** $1–3/day if hit rate is good.

---

## Sources

- [H3 v4.5.0 Release (May 2026)](https://foursquare.com/resources/blog/developer/introducing-h3-version-4-0-0/)
- [deck.gl v9.3 Release & What's New](https://deck.gl/docs/whats-new)
- [DuckDB H3 Extension Performance & Community Repository](https://github.com/isaacbrodsky/h3-duckdb)
- [Spatial Queries in DuckDB with R-tree and H3 Indexing](https://aetperf.github.io/2025/03/04/Spatial_queries_in_DuckDB_with_R-tree_and_H3_indexing.html)
- [Blazing Fast Geospatial SQL in DuckDB](https://docs.fused.io/blog/blazing-fast-geospatial-sql-in-duckdb)
- [Claude API Cost Optimization Guide (April 2026)](https://pecollective-com.pages.dev/tools/claude-pricing-guide/)
- [LLM Prompt Caching in Production](https://dev.to/jangwook_kim_e31e7291ad98/llm-prompt-caching-in-production-cut-api-costs-78-with-claude-8dd)
- [A/B Testing for LLM Applications (2026 Guide)](https://atlan.com/know/ab-testing-llm-applications/)
- [Best Prompt Experimentation Platforms in 2026](https://futureagi.com/blog/best-prompt-experimentation-platforms-in-2026/)
- [LLM Prompt Versioning and Lifecycle Management](https://futureagi.com/blog/prompt-versioning-lifecycle-management-2026/)
- [Free Geopolitical Data APIs (2026)](https://www.worldmonitor.app/blog/posts/free-geopolitical-data-apis-2026/)
- [GDELT Cloud Documentation](https://docs.gdeltcloud.com/)
- [LSEG Launches Real-Time Vessel Tracking API (March 2026)](https://www.pulse.bot/transportation/news/lseg-launches-real-time-vessel-tracking-api-bfbe1be2-3a45-4dde-9d46-1e19cab4146e)
- [Kpler Maritime Data & APIs](https://www.kpler.com/solutions/fundamental-intelligence/maritime-data)
- [Lloyd's List Intelligence Vessel Movements API](https://lloydslistintelligence.com/solutions/api/vessel-movements)
- [Shipfinder Real-Time AIS Tracking](https://open.shipfinder.com/)
- [AIS Hub Real-Time Vessel Tracking](https://public-api.org/api/1260/ais-hub)
- [DuckDB Performance Tuning Guide](https://duckdb.org/docs/guides/performance/overview)
- [How to Tune DuckDB Workloads](https://duckdb.org/docs/2.0/guides/performance/how_to_tune_workloads)
- [Optimizing Real-Time Performance: WebSockets and React.js Integration](https://medium.com/@SanchezAllanManuel/optimizing-real-time-performance-websockets-and-react-js-integration-part-i-e563664647d3)
- [Build Real-Time Analytics Dashboard with WebSockets and React Query](https://js-elite-dev.pages.dev/js/build-real-time-analytics-dashboard-websockets-redis-streams--react-query-performance-guide-7393d39d/)
- [WebSockets in React: Hooks, Lifecycle, and Pitfalls](https://websocket.org/guides/frameworks/react/)
- [How to Fix WebSocket Performance Issues (Jan 2026)](https://oneuptime.com/blog/post/2026-01-24-websocket-performance/)
- [Claude Agent SDK Documentation](https://www.augmentcode.com/guides/claude-agent-sdk-agent-loops-tool-calls)
- [The Claude Code Agentic Loop: A Complete Practitioner's Guide](https://medium.com/@roanmonteiro/the-claude-code-agentic-loop-a-complete-practitioners-guide-0b338647a3aa)
- [Agentic Workflows with Claude: Architecture Patterns & Production Deployment](https://medium.com/@reliabledataengineering/agentic-workflows-with-claude-architecture-patterns-design-principles-production-patterns-72bbe4f7e85a)
- [DeepEval: Open-Source LLM Evaluation Framework](https://github.com/confident-ai/deepeval)

---

## Next Steps

1. **Immediate:** Verify prompt caching hit rate on current agent calls (check API logs).
2. **This week:** Request trials/pricing from LSEG and Kpler for AIS data.
3. **Next sprint:** Upgrade deck.gl to v9.3 and benchmark hex rendering.
4. **Phase 2 prep:** Evaluate LLM eval tooling (LangSmith, Langfuse, DeepEval) for scaled multi-scenario runs.
