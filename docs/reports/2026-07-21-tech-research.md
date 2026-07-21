# Tech Research Report: 2026-07-21

**Focus areas:** Spatial indexing & visualization, Claude API advances, GDELT alternatives & real-time data, LLM evaluation frameworks, React/WebSocket performance optimization

---

## Executive Summary

This week's research identified several high-impact opportunities to reduce costs, improve responsiveness, and strengthen the evaluation framework. The standout finding is Claude API batch processing + prompt caching stacking to achieve ~10x cost reduction for non-urgent inference (evaluation, offline reasoning). Separately, DuckDB spatial queries can be significantly accelerated via R-tree indexing + spatial prefiltering, and GDELT Cloud offers a middle-ground API layer that may reduce BigQuery costs while maintaining structured event data.

**Top priorities for Phase 2:**
1. **Cost optimization:** Batch API (50% off) + prompt caching (90% off) on evaluation pipeline
2. **Spatial query acceleration:** R-tree indexes on H3 cell queries
3. **Event data diversification:** GDELT Cloud as BigQuery cost-reduction option

---

## Findings by Category

### 1. Spatial/Geo

#### Finding 1.1: DuckDB Spatial Extension with R-Tree Indexing
**Status:** Stable and production-ready (v1.5.2+, April 2026)

**What's new:**
- R-tree spatial indexes significantly accelerate queries by pruning bounding-box candidates before running expensive spatial predicates
- Native 2D geometry types (`POINT_2D`, `LINESTRING_2D`, `POLYGON_2D`, `BOX_2D`) with fixed internal layouts run geospatial algorithms ~2-3x faster than generic `GEOMETRY` type
- Hilbert function with GeoParquet improves locality and spatial sorting before storage

**Relevance to Parallax:** **HIGH**
- Current design already uses DuckDB spatial extension; R-tree indexes on H3 cell lookups would accelerate the hot path (filtering cells by bounding box during cascade updates)
- Native 2D types could speed up cascade rule evaluation loop if migrated from generic GEOMETRY

**Effort to integrate:** **MEDIUM**
- Requires profiling current spatial queries to identify hot paths
- Rewrite identified queries to use R-tree hints or native 2D types
- ~2-3 days work

**Risk/Maturity:** **LOW**
- DuckDB spatial is stable; R-tree indexing is standard GIS practice
- No breaking changes to schema

**Sources:**
- [DuckDB Spatial Extension](https://duckdb.org/docs/lts/core_extensions/spatial/overview)
- [DuckDB Spatial Performance Guide](https://github.com/alperdincer/Awesome-DuckDB-Spatial)
- [Medium: DuckDB Geospatial Fast Insights](https://medium.com/@Modexa/duckdb-geospatial-fast-insights-without-heavy-gis-ade24d833201)

---

#### Finding 1.2: deck.gl 9.1+ New Visualization Layers
**Status:** Stable (QuadkeyLayer and MaskExtension released 2025-2026)

**What's new:**
- `QuadkeyLayer`: Fills/strokes polygons for alternative hexagonal grids (e.g., QuadBin) with automatic geometry calculation
- `MaskExtension`: Filters layers by geofence (e.g., show/hide objects by country or user-drawn boundaries)
- TileLayer custom indexing support: Allows applications to supply custom Tileset2D implementations (can use H3 or other systems)

**Relevance to Parallax:** **MEDIUM**
- Current design uses H3HexagonLayer exclusively; MaskExtension could enable faster filtering of live hex updates by region
- Additive, not a replacement; may reduce frontend render cost during high-activity periods

**Effort to integrate:** **LOW-MEDIUM**
- MaskExtension: ~1 day to wire geofence boundaries to mask updates
- QuadkeyLayer: Not immediately useful unless considering alternative grids (out of scope for Phase 1)

**Risk/Maturity:** **LOW**
- Widely deployed; no known regressions

**Sources:**
- [deck.gl What's New](https://deck.gl/docs/whats-new)
- [Scaling Geospatial Analytics: H3 Indexing](https://community.databricks.com/t5/technical-blog/customer-blog-scaling-geospatial-analytics-efficient/ba-p/131234)

---

#### Finding 1.3: H3 v4 Released
**Status:** Current (2026)

**What's new:**
- Clearer APIs and multi-polygon support (H3 previously only supported individual polygons)
- Faster cell validation and neighbor operations

**Relevance to Parallax:** **LOW**
- Current design pins to specific H3 version for determinism
- Multi-polygon support not needed for Iran/Hormuz scenario (single zone per cell)

**Effort to integrate:** **LOW**
- Upgrade during Phase 2 maintenance window; backward compatible for single-polygon use cases

**Risk/Maturity:** **LOW**

**Sources:**
- [H3 Project](https://h3geo.org/)
- [Felt Blog: H3 Explained](https://felt.com/blog/h3-spatial-index-hexagons)

---

### 2. LLM / Agent

#### Finding 2.1: Claude API Batch Processing + Prompt Caching Stack
**Status:** Stable (Batch API; prompt caching updated Feb 2026)

**What's new:**
- **Batch API:** 50% discount on all tokens; processes asynchronously within 24 hours
- **Prompt caching:** Up to 90% savings on cached input tokens; cache hits range from 30-98% depending on traffic
- **Stacking:** Batch API (50% off) + prompt caching (90% off) = ~10x cost reduction for non-urgent workloads
- **Cache isolation:** Workspace-level (Feb 2026) instead of org-level
- **Cache TTL:** Default 5 minutes (reduced from 60 min in early 2026); 1-hour TTL available at higher cost
- **Batch compatibility:** Cache works with batch requests on best-effort basis

**Relevance to Parallax:** **VERY HIGH**
- Evaluation pipeline (end-of-day scorecard, prompt improvement recommendations) is non-urgent; batch API ideal
- Agent system prompts (historical baseline) are static per version; prime candidates for prompt caching
- Estimated savings: Daily prediction calls ($2-5) → could drop 50% with batch, another 90% off with caching on second+ call per version
- 30-day run cost could shrink from $60-150 to $6-15 if evaluation fully batched

**Effort to integrate:** **MEDIUM**
- Current design already uses prompt caching; need to:
  1. Separate urgent inference (real-time agent decisions) from non-urgent (evaluation, offline reasoning)
  2. Move evaluation pipeline to batch API (queue prediction evals, run daily via cron)
  3. Tune cache TTL based on traffic patterns (5 min vs 1 hour trade-off)
- ~3-4 days work

**Risk/Maturity:** **LOW**
- Both features stable and widely deployed
- Batch API has 24-hour SLA; acceptable for eval cron
- Cache misses are graceful (falls back to full token pricing)

**Notes:**
- Watch for cache invalidation on prompt changes; auto-refresh cache post-deploy
- Monitor cache hit rates in early 2026 deployments to optimize TTL choice

**Sources:**
- [Claude API Batch Processing](https://platform.claude.com/docs/en/build-with-claude/batch-processing)
- [Prompt Caching Guide](https://platform.claude.com/docs/en/build-with-claude/prompt-caching)
- [Claude Cost Optimization 2026](https://pecollective.com/tools/claude-pricing-guide/)
- [DEV: Claude Batch API in Practice](https://dev.to/whoffagents/claude-api-cost-optimization-caching-batching-and-60-token-reduction-in-production-3n49)

---

#### Finding 2.2: LLMOps / MLOps Convergence & Traceability Frameworks
**Status:** Maturing (2026 emphasis on traceability)

**What's new:**
- Platforms like DeepEval, W&B Weave, MLflow, Langfuse, RAGAS now treat datasets, prompts, and policies as versioned assets
- Automatic prompt versioning without manual intervention (e.g., Lilypad)
- Emphasis on "traceability" — linking evaluation scores to exact prompt version + model + dataset
- Continuous evaluation drives automatic prompt updates

**Relevance to Parallax:** **HIGH**
- Current design already has prompt versioning (semver) and per-version accuracy tracking
- Next step: Fully automated traceability from prediction → ground truth → eval score → prompt version → suggested improvements
- Could formalize the `model_error` → prompt-improvement pipeline

**Effort to integrate:** **MEDIUM-HIGH**
- Evaluate which platform (if any) integrates with Parallax stack:
  - MLflow: Python-friendly, works with DuckDB via plugin
  - W&B Weave: Cloud-based, cost per run
  - Langfuse: Open-source alternative, self-hosted option
- Current system is DIY; adopting a platform would centralize eval tracking
- ~1-2 weeks to evaluate and pilot

**Risk/Maturity:** **MEDIUM**
- MLOps platforms are mature; LLMOps-specific tooling still evolving
- Tight coupling to a platform increases vendor risk; consider open-source (Langfuse, MLflow) for Phase 1

**Sources:**
- [Best LLM Evaluation Tools 2026](https://medium.com/online-inference/the-best-llm-evaluation-tools-of-2026-40fd9b654dce)
- [LLMOps Architecture 2026](https://calmops.com/architecture/llmops-architecture-managing-llm-production-2026/)
- [Best LLMOps Platforms Compared](https://www.braintrust.dev/articles/best-llmops-platforms-2025)

---

### 3. Real-Time Data

#### Finding 3.1: GDELT Cloud vs. Raw GDELT + BigQuery
**Status:** Production (GDELT Cloud launched 2024, stable in 2026)

**What's new:**
- GDELT Cloud wraps raw GDELT Project article stream into structured Events database
- Clustered Stories, linked Entities, summaries, REST API
- Updates hourly (vs. 15-min for raw BigQuery)
- Eliminates need for BigQuery ingestion and parsing

**Relevance to Parallax:** **HIGH**
- Current design uses GDELT BigQuery with 4-stage noise filter (volume gate, dedup, semantic dedup, relevance scoring)
- GDELT Cloud pre-structures data, reducing client-side parsing burden
- BigQuery storage/query costs (~$0.01 per 1GB scan) vs. GDELT Cloud API costs (typically $50-500/month depending on tier)
- Trade-off: Lose raw event access (can't do custom semantic dedup) but gain cleaner, faster ingestion

**Effort to integrate:** **MEDIUM**
- Requires rewriting GDELT ingestion pipeline to consume GDELT Cloud API instead of BigQuery
- Keep semantic dedup as optional downstream filter if needed
- ~2-3 days

**Risk/Maturity:** **LOW**
- GDELT Cloud is stable; API is well-documented
- Switching back to BigQuery is possible if API proves inadequate

**Recommendation:** Pilot GDELT Cloud for Phase 2 eval; estimate cost savings before full cutover

**Sources:**
- [GDELT Cloud Docs](https://docs.gdeltcloud.com/)
- [GDELT Alternatives Comparison](https://dataresearchtools.com/best-news-apis-comparison/)
- [Currents API: GDELT Alternative](https://currentsapi.services/en/alternative/gdelt)

---

#### Finding 3.2: Real-Time AIS Shipping Data: Consolidation & New Free Options
**Status:** Rapidly consolidating (2026)

**What's new:**
- Market consolidation: Kpler now owns MarineTraffic, FleetMon, Spire Maritime; S&P Global acquired ORBCOMM's AIS
- Free alternatives: AISstream.io (WebSocket), AISHub, VesselAPI (free tier with sub-minute updates)
- Paid: Datalastic (€99+/month), VesselFinder (credit-based), SeaVantage (container logistics)
- Coverage split: Terrestrial AIS (coastal, <50nm) vs. satellite AIS (transoceanic); prices differ 10x

**Relevance to Parallax:** **MEDIUM**
- Current design includes shipping flow as a cascade indicator but doesn't ingest live AIS
- If Phase 2 adds real-time vessel tracking for Hormuz traffic:
  - For coastal zones, AISstream.io (free, WebSocket) or Datalastic are suitable
  - For open ocean, need satellite (Kpler/ORBCOMM) at higher cost
- Terrestrial AIS for Hormuz/Persian Gulf is ~$0/month (free tier) to €99/month

**Effort to integrate:** **MEDIUM**
- WebSocket ingestion similar to current GDELT pipeline
- Schema: vessel_id, position (lat/lng), speed, heading, destination
- Integrate into cascade engine as live traffic input

**Risk/Maturity:** **LOW**
- AIS APIs are widely deployed; WebSocket integrations standard
- Beware of satellite data licensing restrictions in some regions

**Note:** VesselFinder and AISstream.io offer free tiers; start there before paying

**Sources:**
- [50 Best Ship Tracking APIs 2026](https://hormuzmonitor.com/50-best-ship-tracking-apis-2026/)
- [AIS API Comparison 2025](https://datadocked.com/ais-api-providers)
- [Best AIS Apps 2026](https://primonautic.com/blog/best-ais-apps-for-ship-tracking-in-2026)
- [VesselFinder API Docs](https://www.vesselfinder.com/realtime-ais-data)

---

#### Finding 3.3: Oil Futures Forward Curve Access
**Status:** Fragmented; CME is authoritative but restricted access

**What's new:**
- CME Group offers WTI/Brent forward curves via direct API, cloud, DataMine (historical), or licensed distributors
- CME Volatility Index (CVOL) — 30-day implied volatility on WTI options — available for forward-looking analysis
- TradingView offers visualization layer for CME futures

**Relevance to Parallax:** **MEDIUM**
- Current design uses daily EIA spot prices only; forward curve (term structure) needed for proper oil price predictions in Phase 2
- Design spec notes: "Paid provider (CME Group, Nasdaq Data Link) required in Phase 2 if forward term structure is needed"
- CME API access is restricted (not simple REST); typically requires account and licensing

**Effort to integrate:** **MEDIUM-HIGH**
- CME direct API requires legal agreement and potential data licensing fees
- Alternative: Use third-party distributor (Bloomberg Terminal, Refinitiv, etc.) — likely cost-prohibitive for v1
- Simpler interim: Scrape forward curve visualization from public sources or use FRED/Yahoo Finance spot prices as proxy

**Risk/Maturity:** **MEDIUM**
- CME access is operational but gated; high barrier to entry
- Cost unknown without contacting CME directly

**Recommendation:** Defer to Phase 2; note in planning. For Phase 1, continue with EIA spot prices.

**Sources:**
- [CME Crude Oil Futures](https://www.cmegroup.com/markets/energy/crude-oil.html)
- [TradingView CME Futures Forward Curve](https://www.tradingview.com/symbols/NYMEX-CL1!/forward-curve/)

---

### 4. Evaluation / MLOps

#### Finding 4.1: LLM Evaluation Metrics & Frameworks (2026)
**Status:** Maturing; consolidating around common metrics

**What's new:**
- Standard benchmarks (MMLU, GLUE) + specialized metrics (RAGAS for RAG, hallucination detection, calibration)
- Tools: DeepEval, W&B Weave, MLflow, Humanloop, Arize AI, Langfuse, RAGAS
- Emphasis on "traceability" — linking scores to exact prompt version/model/dataset
- Automatic prompt versioning (Lilypad) without manual intervention

**Relevance to Parallax:** **HIGH**
- Current design has direction/magnitude/sequence/calibration scoring; already structured for evaluation
- Next: Formalize pipeline to store scores + link to prompt version, enable A/B comparisons
- Could adopt lightweight tool (Langfuse, MLflow) for centralized eval tracking

**Effort to integrate:** **MEDIUM**
- Current eval cron is DIY; adopting a platform would centralize tracking but add dependency
- Alternative: Enhance current DIY system with better versioning and dashboard (no new dependencies)
- Recommendation: DIY for Phase 1; evaluate platforms in Phase 2

**Risk/Maturity:** **LOW**
- Eval metrics are standard ML practice; no risk in current DIY approach
- Adopting a platform in Phase 2 is safe once Phase 1 patterns are clear

**Sources:**
- [Best LLM Evaluation Tools 2026](https://medium.com/online-inference/the-best-llm-evaluation-tools-of-2026-40fd9b654dce)
- [LLM Evaluation: Frameworks and Metrics 2026](https://futureagi.substack.com/p/llm-evaluation-frameworks-metrics)

---

### 5. Performance / Frontend

#### Finding 5.1: React 18 Concurrent Mode + useRef for Real-Time Dashboards
**Status:** Stable; best practice for high-frequency updates (matches Parallax design)

**What's new:**
- React 18 concurrent mode prevents render blocking; safe for WebSocket-driven dashboards
- useRef for mutable data (hex arrays) decouples React re-renders from WebSocket updates (Parallax already does this)
- Batching updates (100ms buffer) + react-use-websocket library reduce per-message re-renders
- Memoization with custom comparison (React.memo) fine-tunes which components re-render

**Relevance to Parallax:** **HIGH (Already Implemented)**
- Design spec Section 5 (Frontend) explicitly describes this pattern: "H3 hex data lives in a mutable useRef, not useState"
- Current implementation is correct; no changes needed

**Effort to integrate:** **NONE**
- Already implemented in current design

**Risk/Maturity:** **LOW**
- Widely deployed; React 18 is stable
- Batching (100ms) is already tuned in spec

**Recommendation:** Validate on high-activity days (crisis events, 20+ events/minute) that 100ms batching window is sufficient

**Sources:**
- [How to Use WebSockets in React 2026](https://oneuptime.com/blog/post/2026-01-15-websockets-react-real-time-applications/view)
- [Building Real-Time Business Dashboards with React 2026](https://www.sparkleweb.in/blog/building_real-time_business_dashboards_with_react_in_2026)
- [Medium: Optimizing Real-Time Performance with WebSockets and React](https://medium.com/@SanchezAllanManuel/optimizing-real-time-performance-websockets-and-react-js-integration-part-ii-4a3ada319630)

---

#### Finding 5.2: Lightweight Charting Libraries (WebGL/Canvas)
**Status:** Mature; Lightweight Charts widely adopted for financial data

**What's new:**
- Lightweight Charts library: Purpose-built for financial data, renders via WebGL/Canvas (not SVG)
- Supports candlestick, baseline, area charts; optimized for high-frequency ticking
- Significantly faster than D3/Recharts for time-series with 1000+ points

**Relevance to Parallax:** **MEDIUM**
- Right panel includes Brent price sparkline; currently likely SVG-based (slow on high-frequency updates)
- Switching to Lightweight Charts could improve responsiveness

**Effort to integrate:** **LOW-MEDIUM**
- Drop-in replacement for sparkline component
- WebSocket price updates feed directly into chart
- ~1-2 days

**Risk/Maturity:** **LOW**
- Lightweight Charts is stable and widely used in trading platforms

**Recommendation:** Pilot in Phase 2 if price updates feel laggy during live testing

**Sources:**
- [Building Real-Time Business Dashboards with React 2026](https://www.sparkleweb.in/blog/building_real-time_business_dashboards_with_react_in_2026)

---

## Top 3 Recommendations

### 1. **Claude API Batch Processing + Prompt Caching (Cost Reduction)**
**Priority: VERY HIGH | Timeline: Phase 2, ~3-4 days | Estimated ROI: 5-10x cost reduction on eval pipeline**

Separate urgent inference (real-time agent decisions) from non-urgent (evaluation, offline reasoning). Move evaluation to batch API, stack prompt caching. Predicted impact: 30-day run cost $60-150 → $6-15 with full batching/caching. Low risk; immediate cost savings.

**Action:** Profile current API spend, identify eval bottlenecks, implement batch queue for daily scorecard + prompt improvement cron.

---

### 2. **DuckDB Spatial Query Acceleration via R-Tree Indexing (Performance)**
**Priority: HIGH | Timeline: Phase 2, ~2-3 days | Estimated ROI: 2-3x faster cascade rule evaluation**

Profile cascade hot path (cell lookups during blockade → flow → price propagation). Add R-tree indexes to H3 cell queries; consider migrating generic GEOMETRY to native 2D types. Low risk; measurable latency improvement.

**Action:** Benchmark current cascade loop, profile `world_state_delta` queries, add R-tree hints and test speedup.

---

### 3. **Evaluate GDELT Cloud as BigQuery Alternative (Cost + Ops)**
**Priority: MEDIUM | Timeline: Phase 2 pilot, ~2-3 days | Estimated ROI: Potential 50-80% reduction in BigQuery costs + simpler ingestion**

Pilot GDELT Cloud API (hourly, pre-structured events) vs. raw BigQuery (15-min, custom parsing). Keep semantic dedup optional. Estimated BigQuery savings: $0.10-0.50/day → $0 if moved entirely to GDELT Cloud.

**Action:** Set up GDELT Cloud trial, rewrite GDELT ingestion pipeline to consume API, benchmark latency and cost. Decide on full cutover post-Phase 1.

---

## Dismissed / Low-Priority Findings

- **H3 v4 upgrade:** Backward compatible; defer to Phase 2 maintenance window. Multi-polygon support not needed for Phase 1.
- **Oil futures forward curve (CME API):** Gated, cost unknown, deferred to Phase 2. Continue with EIA spot prices.
- **LLMOps platform adoption (Phase 1):** DIY eval system is sufficient; evaluate platforms in Phase 2 once patterns clear. Avoid vendor lock-in early.
- **deck.gl MaskExtension:** Additive feature; low priority unless frontend render performance becomes bottleneck.

---

## Notes

- Watch Claude API cache TTL trade-off (5 min default vs. 1-hour at higher cost); validate hit rates in production
- AIS integration contingent on Phase 2 scope; free tiers (AISstream.io, VesselAPI) available if needed
- All findings align with existing Parallax architecture; no major rewrites required
- Recommendations stack well: batch API + caching + spatial indexing + GDELT Cloud together reduce ops complexity and costs significantly

---

**Report generated:** 2026-07-21 (automated daily scout)
**Next review:** 2026-07-28
