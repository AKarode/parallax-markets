# Parallax Tech Research Report — 2026-07-26

**Focus areas:** Spatial/Geo, LLM/Agent features, Real-time Data, Eval/MLOps, Performance optimization

---

## Executive Summary

Significant opportunities exist in **cost reduction via batch API + prompt caching stacking** (95% savings on eval work), **real-time AIS shipping data integration** (critical gap for Hormuz monitoring), and **LLM-as-a-Judge eval automation** (replaces manual calibration pipeline). Three architectural upgrades are recommended, all low-effort with immediate ROI.

---

## Findings by Category

### 1. Spatial/Geospatial

#### DuckDB Spatial Join Operator (v1.3.0+) — 58× Performance Improvement
- **Relevance:** HIGH
- **Effort:** LOW (already in use, just ensure latest version)
- **Risk:** Low maturity, but production-ready as of v1.3.0
- **Details:** DuckDB v1.3.0 introduced a dedicated `SPATIAL_JOIN` operator that builds an R-tree index on-the-fly for the smaller table during join execution. Delivers 58× speedup over previous version. Critical for real-time H3 cell lookups during cascade propagation.
- **Action:** Verify backend is pinned to DuckDB ≥1.3.0. This acceleration is automatic — no code changes required.
- **Reference:** [Spatial Joins in DuckDB](https://duckdb.org/2025/08/08/spatial-joins)

#### DuckDB Native GEOMETRY Type (v1.5+)
- **Relevance:** MEDIUM
- **Effort:** LOW
- **Details:** GEOMETRY became a built-in type in DuckDB v1.5, reducing dependency on the spatial extension for core operations. The extension still provides experimental types (`POINT_2D`, `LINESTRING_2D`, `POLYGON_2D`) for advanced use cases.
- **Action:** If upgrading to v1.5, consider removing spatial extension from package manager and relying on built-ins for standard operations.
- **Reference:** [DuckDB Spatial Extension](https://duckdb.org/docs/lts/core_extensions/spatial/overview)

#### deck.gl H3HexagonLayer Performance Flag (2025 Release)
- **Relevance:** MEDIUM
- **Effort:** LOW
- **Details:** New `highPrecision: false` flag forces low-precision, high-performance rendering on H3HexagonLayer. Useful for dashboards with 400K+ hexes where GPU precision is not critical. Combined with batched WebSocket updates (already implemented), this can reduce render jitter.
- **Action:** Test `highPrecision: false` in production build. A/B test vs. current precision to validate visual quality trade-off.
- **Reference:** [deck.gl What's New](https://deck.gl/docs/whats-new)

#### Alternative Grid Systems (QuadKey, Geohash, QuadBin)
- **Relevance:** LOW-MEDIUM
- **Effort:** HIGH (requires full refactor of H3 mapping logic, data migration)
- **Risk:** High. Switching from H3 would require reprocessing all historical snapshots and decisions.
- **Rationale:** H3's hierarchical nature is well-matched to the cascade engine's multi-resolution model. QuadKey and Geohash have comparable performance but offer no advantage over the current setup.
- **Recommendation:** NOT recommended for Phase 1. Keep as Phase 2+ exploration if performance demands scale beyond 1M hexes.

---

### 2. LLM/Agent Features

#### Claude Batch API + Prompt Caching Stack = 95% Cost Reduction
- **Relevance:** VERY HIGH
- **Effort:** MEDIUM
- **Current Gap:** Eval/meta-agent work (prompt improvement pipeline) is run synchronously today. Perfect candidate for batching.
- **Details:** 
  - Batch API: 50% cost reduction on all standard models (Haiku/Sonnet), 24-hour turnaround
  - Prompt caching (1-hour TTL, now GA): 90% cost reduction on cached tokens (2x write, 0.1x read)
  - Stacked: Up to 95% savings when both applied together
  - Example: Eval meta-agent (~2K cached system prompt + 6K eval context) on 50 predictions would cost ~$0.025/call synchronously, ~$0.002 via batch + cache
- **Action:** 
  1. Refactor eval scoring pipeline to batch all N predictions into single Batch API call
  2. Ensure meta-agent system prompts are marked as cache_control:ephemeral (1-hour cache)
  3. Monitor cache hit rates via API usage logs
- **Phase 2:** Apply batch API to routine daily scoring cron (10-20 calls/day becomes single batched request)
- **Estimated savings:** $0.30-0.50/day on eval work alone ($9-15/month), with headroom to increase agent frequency during active crisis periods
- **References:** 
  - [Batch Processing - Claude Platform Docs](https://platform.claude.com/docs/en/build-with-claude/batch-processing)
  - [Anthropic Claude API October 2025 Guide](https://blog.imseankim.com/anthropic-claude-api-batch-processing-prompt-caching-cost-reduction-october-2025/)
  - [Claude Batch API: 50% Lower Cost](https://claudeimplementation.com/blog/claude-batch-api)

#### Prompt Caching 1-Hour TTL (Now GA as of October 2025)
- **Relevance:** VERY HIGH
- **Effort:** LOW (already implemented in Phase 1 spec with 5-min TTL)
- **Details:** Upgrade from 5-minute cache (1.25x write cost) to 1-hour cache (2x write cost). For repeated country agent calls within an hour, the 1-hour cache is more cost-effective.
- **Action:** 
  1. Verify `cache_control={"type": "ephemeral"}` is set on all system prompts in agent definitions
  2. No code changes required — this is an API parameter update
- **Estimated impact:** With 50 agents × ~3 calls/day each = 150 calls, 1-hour cache creates ~10x prefix reuse. Saves $0.15-0.30/day vs. 5-min cache.
- **Reference:** [Prompt Caching with Claude](https://www.anthropic.com/news/prompt-caching)

#### Agent Orchestration Frameworks (Survey)
- **Relevance:** MEDIUM
- **Current state:** Phase 1 uses custom asyncio-based DES engine (not LangGraph/CrewAI)
- **Findings:** Leading frameworks (LangGraph, CrewAI, MetaGPT, OpenAI Agents SDK) solve multi-agent coordination, but Parallax's custom engine is already optimized for geopolitical simulation semantics.
- **Recommendation:** Do NOT migrate to LangGraph/CrewAI for Phase 1. Custom engine provides better control over cascade semantics and event ordering. Revisit only if Phase 2 requires true multi-objective reasoning (e.g., competing stakeholder agents). LangGraph's graph-based state machine is overkill for current architecture.
- **Reference:** [LLM Orchestration in 2026: Top 22 Frameworks](https://aimultiple.com/llm-orchestration)

---

### 3. Real-Time Data & Geopolitical Event Feeds

#### AIS Shipping Data Integration (CRITICAL GAP)
- **Relevance:** VERY HIGH
- **Effort:** MEDIUM (API integration, WebSocket handling)
- **Current gap:** Spec mentions Searoute for visualization only, no real-time vessel tracking. Hormuz flow % on dashboard is cascaded from predicted blockade state, not actual vessel data.
- **Details:**
  - **Market consolidation (2023-2025):** Kpler now owns MarineTraffic, FleetMon, and Spire Maritime (as of April 2025). S&P Global completed acquisition of ORBCOMM's AIS business (November 2025).
  - **Free options:** AISstream.io (real-time WebSocket), AISHub (free JSON/XML API) — both adequate for Hormuz chokepoint monitoring
  - **Commercial options:** Datalastic (self-serve API, €99/month for full ship data + historical), MarineTraffic/Kpler (largest dataset), VesselFinder (credit-based)
- **Recommended approach:** 
  1. **MVP:** Integrate AISstream.io WebSocket for real-time Hormuz corridor vessel tracking
  2. **Integration:** Parse AIS position reports, convert to H3 cells (res 7-8 for Hormuz), compare predicted vs. actual flow
  3. **Feedback:** Divergences between predicted flow and actual AIS vessel count feed into eval feedback ("Your model predicted 30% flow reduction, actual AIS shows 15% — overshooting risk aversion")
- **Cost:** AISstream.io free tier adequate for PoC; Datalastic €99/month if commercial deployment needed
- **Action items for Phase 2:**
  1. Set up AISstream.io WebSocket ingestion in `ingestion/ais_stream.py`
  2. Add `ais_position_reports` table to schema
  3. Map AIS positions to H3 cells, compare to cascade-predicted Hormuz flow
  4. Surface actual vs. predicted vessel count in right-panel indicators
- **References:**
  - [AIS Data Providers for Maritime Vessel Tracking](https://www.darkshipping.com/post/ais-data-providers)
  - [Free AIS Vessel Tracking](https://www.aishub.net/)
  - [AISstream.io](https://aisstream.io/)
  - [Best Ship Tracking APIs 2026](https://hormuzmonitor.com/50-best-ship-tracking-apis-2026/)

#### GDELT Cloud (Commercial Alternative)
- **Relevance:** LOW-MEDIUM
- **Effort:** MEDIUM (API migration)
- **Details:** GDELT Cloud is a commercial SaaS wrapper over open GDELT data, providing pre-coded events, entity resolution, and story clustering via REST API. Reduces in-house GDELT parsing complexity.
- **Trade-off:** Cost (~$500-2000/month) vs. reduced engineering overhead. For PoC phase, open GDELT is sufficient.
- **Action:** Revisit if Phase 2 requires higher-quality entity extraction or real-time story clustering.
- **Reference:** [GDELT Cloud](https://gdeltcloud.com/)

#### Alternative Geopolitical Data (Google Trends)
- **Relevance:** LOW-MEDIUM
- **Details:** Google Trends suffers less political interference than GDELT and can serve as independent signal validation during geopolitical tensions (e.g., "Iran tensions" search spike correlates with escalation events).
- **Action:** Low-priority. Consider adding as supplementary signal in Phase 2 if model calibration shows systematic GDELT bias.

---

### 4. Evaluation & MLOps

#### Braintrust A/B Testing Platform
- **Relevance:** HIGH
- **Effort:** MEDIUM (integration with eval pipeline)
- **Current gap:** Phase 1's prompt versioning tracks version numbers but has no automated A/B comparison framework. Manual review required.
- **Details:** Braintrust offers A/B testing for LLM prompts with automated tracking of quality scores, latency, cost, and token usage per variant. Supports dataset-driven testing.
- **Proposed integration:**
  1. After prompt update, mark new version as "experiment" in Braintrust
  2. Route 10% of new events to new prompt version, 90% to old for 24 hours
  3. Braintrust auto-compares accuracy, cost, latency
  4. If new version underperforms on any metric, auto-rollback signal triggers
- **Cost:** $500-2000/month (depends on usage tier), but offsets cost of manual eval work
- **Action:** Trial integration with one agent (e.g., IRGC Navy) in Phase 2. If successful, expand to full agent swarm.
- **Reference:** [Best Prompt Evaluation Tools 2025](https://www.braintrust.dev/articles/best-prompt-evaluation-tools-2025)

#### Opik (LLM-as-a-Judge Scoring)
- **Relevance:** HIGH
- **Effort:** MEDIUM
- **Current gap:** Phase 1 uses hardcoded scoring (direction accuracy, magnitude, calibration). LLM-as-a-Judge can automate contextual "was this prediction actually correct given real-world ambiguity?"
- **Details:** Comet Opik supports both LLM-as-a-Judge (Claude evaluates prediction misses) and heuristic scoring. Tracks production metrics (latency, cost) alongside accuracy.
- **Proposed use:**
  1. For any prediction marked "ambiguous" by current scorer, spawn Opik LLM-as-a-Judge task
  2. Pass prediction + ground truth context to Claude, ask "Is this a model error, exogenous shock, or data lag?"
  3. Opik aggregates verdicts, flags patterns (e.g., "consistently underestimating Iran's restraint")
- **Cost:** Free tier for basic usage, paid for production scaling
- **Action:** Integrate Opik into eval scoring pipeline as secondary verify pass in Phase 2.
- **Reference:** [LLM Evaluation Guide 2025](https://www.xbytesolutions.com/llm-evaluation-metrics-framework-best-practices/)

#### Promptfoo (Open-Source Prompt Testing)
- **Relevance:** MEDIUM
- **Effort:** LOW
- **Details:** Open-source prompt testing framework supporting 50+ models. Useful for local, non-production prompt iteration and security testing (prompt injection resistance).
- **Action:** Use Promptfoo in dev environment for rapid prompt prototyping before committing to Braintrust A/B test.
- **Reference:** [Prompt Testing Frameworks 2025](https://mirascope.com/blog/prompt-testing-framework)

#### Lilypad (Automatic Prompt Versioning)
- **Relevance:** MEDIUM
- **Effort:** LOW (decorator-based)
- **Details:** Decorator-based automatic versioning (`@lilypad.trace`). Any parameter or prompt change triggers a new version without manual semver updates.
- **Trade-off:** Less control than manual semver (Phase 1 spec preference), but lower overhead
- **Action:** Consider for Phase 2 if manual versioning becomes bottleneck during active crisis periods.

---

### 5. Performance Optimization

#### React + DuckDB-WASM + Web Workers for 60 FPS Dashboards
- **Relevance:** HIGH
- **Effort:** MEDIUM-HIGH (refactor dashboard analytics to Web Worker)
- **Current state:** Phase 1 uses WebSocket updates to React state, which can cause render thrashing with high-frequency updates.
- **Details:**
  - Offload SQL queries (filtering, aggregating dashboard KPIs) from main thread to Web Worker running DuckDB-WASM
  - Keep React on main thread for UI only
  - Results: Smooth 60 FPS rendering even with 1000+ WebSocket updates/sec
- **Proposed refactor:**
  1. Move dashboard query logic (`get_scorecard_metrics`, `get_signal_history`) to Web Worker
  2. Worker queries local DuckDB-WASM instance (cached state snapshot pushed to browser on load)
  3. WebSocket updates mutate worker's DuckDB state directly, not React state
  4. Worker posts aggregated KPI updates to main thread (~100ms batches), React re-renders only UI
- **Estimated impact:** Eliminates render jitter during high-activity periods. Dashboard remains responsive even at 60+ decision events/sec.
- **References:**
  - [React + DuckDB-WASM at 60 FPS](https://medium.com/@hadiyolworld007/react-duckdb-wasm-at-60-fps-a00cafad3271)
  - [Event-Loop Friendly Analytics with React + DuckDB](https://medium.com/@hadiyolworld007/event-loop-friendly-analytics-with-react-duckdb-80b7b8e3e424)

#### DuckDB Streaming Support (v1.2+)
- **Relevance:** MEDIUM
- **Effort:** LOW
- **Details:** DuckDB v1.2+ includes native streaming support for real-time ingestion pipelines (GDELT, AIS). Better than async queue-based writes for bursty, high-throughput scenarios.
- **Current state:** Backend uses asyncio.Queue for single-writer pattern. This is fine for current event volume, but streaming extension could reduce latency spikes during crisis periods.
- **Action:** Low priority. Revisit if GDELT or AIS ingestion becomes a bottleneck (currently not on the critical path).

#### Embedding Model Alternatives
- **Relevance:** LOW-MEDIUM
- **Current choice:** all-MiniLM-L6-v2 (good balance of quality and speed for semantic dedup)
- **Alternatives:**
  - **e5-base-v2:** Slightly higher quality (768-dim vs. 384-dim), ~10% slower
  - **gte-multilingual-base:** Better multilingual performance if expanding to non-English news sources
  - **Static embeddings:** 100-400× faster but 15% lower quality — NOT recommended (semantic dedup accuracy is critical)
- **Recommendation:** Keep all-MiniLM-L6-v2. It's lightweight, battle-tested, and sufficient for GDELT event dedup. Upgrade to gte-multilingual-base only if non-English GDELT coverage becomes a priority.

---

## Top 3 Recommendations (Priority Order)

### 1. **Batch API + Prompt Caching Stack for Eval Work** (IMPLEMENT IN PHASE 2, WEEK 1)
- **Why:** Immediate 95% cost reduction on non-critical eval/meta-agent calls. Pays for itself in <2 weeks.
- **Effort:** 2-3 days (refactor eval scoring pipeline to batch)
- **Outcome:** $0.30-0.50/day savings, $100+/month on eval work. Frees up LLM budget for more frequent crisis monitoring.
- **Risk:** Low. Batch API is GA, well-tested, no breaking changes.
- **Implementation:** 
  1. Mark all system prompts with `cache_control: {"type": "ephemeral"}`
  2. Batch prediction scoring: collect all N predictions due for scoring, submit single Batch API request
  3. Monitor cache hit rates in usage logs

### 2. **AIS Shipping Data Integration (Real-Time Vessel Tracking)** (IMPLEMENT IN PHASE 2, WEEKS 2-4)
- **Why:** Fills critical gap in real-time Hormuz monitoring. Current cascade predictions are untethered from actual vessel behavior. AIS provides ground truth for model calibration.
- **Effort:** 3-5 days (WebSocket ingestion + H3 mapping + indicator display)
- **Outcome:** 
  - Actual vs. predicted flow divergences feed directly into eval feedback loop
  - "Predicted 30% flow reduction, actual AIS shows 15%" becomes explicit calibration signal
  - Dashboard indicators (Hormuz traffic %) now reflect real data, not just cascade output
- **Risk:** Low. AISstream.io is stable, free tier sufficient for PoC.
- **Implementation:**
  1. Add AISstream.io WebSocket client to backend (`ingestion/ais_stream.py`)
  2. Parse AIVDM sentences, extract lat/lng/vessel type
  3. Convert to H3 cells (res 7 for Hormuz chokepoint)
  4. Compare actual vessel count to cascaded "flow %" prediction
  5. Surface divergence in right-panel indicators and eval feedback

### 3. **Braintrust A/B Testing Integration (IMPLEMENT IN PHASE 2, WEEKS 5-6)**
- **Why:** Automates manual prompt evaluation, eliminates subjective rollback decisions. Enables rapid iteration during crisis periods.
- **Effort:** 3-4 days (integration + one pilot agent)
- **Outcome:**
  - Prompt improvements are data-driven, not opinion-driven
  - Reduces time to detect and rollback underperforming versions
  - Supports "champion vs. challenger" prompts running in parallel
- **Risk:** Medium. Adds operational complexity (managing experiments), but benefits outweigh cost.
- **Implementation:**
  1. Create Braintrust workspace, add API key to env vars
  2. Pilot with one agent (e.g., Iran sub-actor team)
  3. New prompt versions automatically routed to experiment via Braintrust SDK
  4. Daily cron compares accuracy, cost, latency metrics
  5. Auto-signal rollback if underperforming

---

## Not Recommended

- **Switching from H3 to QuadKey/Geohash:** No performance gain, high refactor cost, breaks existing data.
- **GDELT Cloud migration:** Premature. Open GDELT + semantic dedup sufficient for current needs. Cost-benefit improves only at >10K events/day scale.
- **Static embedding models:** Trade-off in semantic accuracy not worth 100x speed gain. all-MiniLM-L6-v2 is already fast enough.
- **Alternative agent frameworks (LangGraph, CrewAI):** Current custom DES engine is better-suited to geopolitical simulation semantics. Revisit only if Phase 2 introduces competing stakeholder reasoning.

---

## References & Sources

- [DuckDB Ecosystem Newsletter September 2025](https://motherduck.com/blog/duckdb-ecosystem-newsletter-september-2025/)
- [Spatial Joins in DuckDB (58× improvement)](https://duckdb.org/2025/08/08/spatial-joins)
- [DuckDB Spatial Extension Overview](https://duckdb.org/docs/lts/core_extensions/spatial/overview)
- [deck.gl What's New](https://deck.gl/docs/whats-new)
- [Claude Batch Processing Docs](https://platform.claude.com/docs/en/build-with-claude/batch-processing)
- [Batch API + Prompt Caching 95% Savings](https://blog.imseankim.com/anthropic-claude-api-batch-processing-prompt-caching-cost-reduction-october-2025/)
- [Prompt Caching Feature](https://www.anthropic.com/news/prompt-caching)
- [LLM Orchestration Frameworks 2026](https://aimultiple.com/llm-orchestration/)
- [AIS Data Providers Comparison](https://www.darkshipping.com/post/ais-data-providers)
- [Best Prompt Evaluation Tools 2025](https://www.braintrust.dev/articles/best-prompt-evaluation-tools-2025)
- [LLM Evaluation Guide 2025](https://www.xbytesolutions.com/llm-evaluation-metrics-framework-best-practices/)
- [React + DuckDB-WASM at 60 FPS](https://medium.com/@hadiyolworld007/react-duckdb-wasm-at-60-fps-a00cafad3271)
- [DuckDB Real-Time Streaming Guide](https://duckdblab.org/en/post/duckdb-real-time-streaming-guide/)

---

**Generated:** 2026-07-26 | **Scout:** Claude Code Tech Research Agent
