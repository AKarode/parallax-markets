# Tech Research Report: 2026-07-18
## Focus Areas: Spatial/Geo, LLM/Agent, Real-time Data, Eval/MLOps, Performance

---

## Executive Summary

This daily research scan identified **3 high-priority improvements** and several medium-priority opportunities for the Parallax stack. The most impactful finding is the potential to **cut LLM inference costs by 70-80% via Batch API + Prompt Caching stacking**. Additionally, emerging alternatives to GDELT (GDELT Cloud, POLECAT) and new AIS shipping data APIs could strengthen real-time event ingestion. MapLibre's new MLT tile format and DuckDB's time-series optimization patterns offer incremental performance wins.

---

## Findings by Category

### 1. **Spatial/Geo**

#### Finding 1.1: H3 SIMD Acceleration & Bulk APIs (HIGH Relevance)
- **What**: H3 fork released post-2026-04-26 adds SIMD-accelerated bulk coordinate conversion APIs: `latLngsToCells()`, `cellsToLatLngs()`, `cellsToBoundaries()`
- **Impact**: Parallax converts thousands of route points to H3 cells per ingestion cycle. SIMD bulk APIs could cut conversion latency by 2-3x
- **Effort**: LOW — update h3-js binding to v4.5+; may require custom bindings for new bulk APIs if not yet exposed
- **Risk**: LOW — additive optimization, no breaking changes
- **Status**: Additive — current h3-js works fine; this is pure performance gain
- **Sources**: [H3 GitHub](https://github.com/mattsta/h3), [CRAN duckh3 2026](https://cran.rstudio.com/web/packages/duckh3/duckh3.pdf)

#### Finding 1.2: MapLibre Tile (MLT) Format — 6x Compression (MEDIUM Relevance)
- **What**: MapLibre released MLT format (successor to MVT) with 6x improved compression via column-oriented layout and SIMD-friendly encoding
- **Impact**: Parallax loads 4 resolution bands of H3 hexagon tiles. 6x compression reduces tile payload, latency, and storage cost
- **Effort**: MEDIUM — requires tile serving pipeline changes. MapLibre GL JS clients accept MLT natively from v13+
- **Risk**: MEDIUM — adds tooling complexity; current MVP could stick with MVT. Consider for Phase 2 scaling
- **Status**: Additive — improves performance at scale, not critical for current phase
- **Sources**: [MapLibre MLT Release 2026-01-23](https://maplibre.org/news/2026-01-23-mlt-release/), [MapLibre Newsletter May 2026](https://maplibre.org/news/2026-06-03-maplibre-newsletter-may-2026/)

#### Finding 1.3: DuckDB H3 Extension Maturity (MEDIUM Relevance)
- **What**: DuckDB H3 extension (v4.5+) now supports R-tree spatial indexing alongside H3 coarse filtering for efficient spatial queries
- **Impact**: Parallax already uses DuckDB + H3. Combined R-tree + H3 indexing could speed `world_state_delta` queries that filter cells by zone
- **Effort**: LOW — enable extension, add index on cell_id
- **Risk**: LOW — schema-only change
- **Status**: Additive — current design works; this is optimization for future scale
- **Sources**: [Awesome DuckDB Spatial](https://github.com/alperdincer/Awesome-DuckDB-Spatial), [DuckDB Spatial Extension](https://duckdb.org/docs/lts/core_extensions/spatial/overview)

---

### 2. **LLM/Agent**

#### Finding 2.1: Batch API + Prompt Caching Stacking — 70-80% Cost Reduction (HIGH Relevance) ⭐
- **What**: Anthropic's Batch API (50% discount) and Prompt Caching (90% discount on cached tokens) can be combined. For requests > 5 min, cache TTL extends to 1 hour in batch mode
- **Impact**: Parallax's design already uses prompt caching for agent system prompts. Adding Batch API for non-urgent eval/telemetry calls could reduce LLM costs from ~$2-5/day to ~$0.50-1.50/day
- **Effort**: MEDIUM — refactor non-critical agent calls (eval meta-agent, daily scorecard generation) to use batch instead of immediate API calls
- **Risk**: LOW — only non-real-time decision paths use batch; live agent decisions remain synchronous
- **Concrete Example**: Daily eval scorecard generation can queue predictions for batch processing (4-24 hour latency acceptable) instead of calling Claude immediately
- **Status**: HIGH PRIORITY — estimated $50-100/month savings. Spec already targets $60-150 for 30-day run; this cuts it in half
- **Sources**: [Batch Processing Docs](https://platform.claude.com/docs/en/build-with-claude/batch-processing), [Prompt Caching Docs](https://platform.claude.com/docs/en/build-with-claude/prompt-caching), [2026 Cache TTL Analysis](https://dev.to/whoffagents/claude-prompt-caching-in-2026-the-5-minute-ttl-change-thats-costing-you-money-4363), [Batch + Caching Stacking](https://dev.to/whoffagents/claude-api-cost-optimization-caching-batching-and-60-token-reduction-in-production-3n49)

#### Finding 2.2: Prompt Versioning & A/B Testing Tools (MEDIUM Relevance)
- **What**: Platforms like Agenta (open-source), Langfuse, and Braintrust now offer structured prompt versioning with built-in A/B testing and performance tracking
- **Impact**: Parallax currently has manual semver versioning (v1.2.0) in `agent_prompts` table. Structured tools could automate A/B testing workflow (currently manual eval framework)
- **Effort**: HIGH — integrating third-party tool requires architectural changes or would need to build internal version
- **Risk**: MEDIUM — adds external dependency; could delay Phase 1 MVP
- **Status**: DEFER TO PHASE 2 — current manual eval framework works; structured tools are nice-to-have optimization
- **Sources**: [Agenta](https://www.getmaxim.ai/articles/how-to-perform-a-b-testing-with-prompts-a-comprehensive-guide-for-ai-teams/), [Langfuse A/B Testing](https://langfuse.com/docs/prompt-management/features/a-b-testing), [Braintrust A/B Testing 2026](https://www.braintrust.dev/articles/best-prompt-management-tools-2026/)

#### Finding 2.3: Claude Cache TTL Reduction Impact (MEDIUM Relevance)
- **What**: Anthropic reduced prompt cache TTL from 60 min to 5 min in early 2026. For agents that fire within short windows, cache may expire between calls
- **Impact**: Parallax's design assumes ~5-min cache TTL already (mentioned in spec). No action needed; confirm implementation respects TTL boundaries
- **Effort**: LOW — design review only
- **Risk**: NONE — already accounted for in design
- **Status**: VALIDATED — no changes needed
- **Sources**: [2026 Cache TTL Analysis](https://dev.to/whoffagents/claude-prompt-caching-in-2026-the-5-minute-ttl-change-thats-costing-you-money-4363)

---

### 3. **Real-time Data**

#### Finding 3.1: AIS Real-Time Shipping Data APIs (HIGH Relevance)
- **What**: AISstream.io (free WebSocket tier), MarineTraffic, VesselFinder, and others provide real-time Automatic Identification System data for vessel positions/movements
- **Impact**: Parallax uses GDELT events to infer Hormuz shipping flows. Direct AIS data could provide ground truth for vessel tracking during blockade scenarios. Complements GDELT with actual ship movement data
- **Effort**: LOW — add new ingestion module; connect WebSocket feed, parse NMEA/JSON, ingest to `raw_ais` table
- **Risk**: LOW — additive data source; no breaking changes
- **Status**: ADDITIVE — would improve scenario realism and eval grounding
- **Recommendation**: Integrate AISstream free tier for Hormuz/Persian Gulf coverage. Track vessel density as proxy for flow disruption
- **Sources**: [AISstream.io](https://aisstream.io/), [50 Best Ship Tracking APIs 2026](https://hormuzmonitor.com/50-best-ship-tracking-apis-2026/), [VesselFinder AIS API](https://www.vesselfinder.com/realtime-ais-data)

#### Finding 3.2: GDELT Cloud (Commercial Alternative) (MEDIUM Relevance)
- **What**: GDELT Cloud is a newer commercial offering that pre-clusters GDELT article streams into structured Events via MCP tools, with hourly updates
- **Impact**: Current Parallax design ingests raw GDELT from BigQuery and applies custom noise filtering (4-stage pipeline). GDELT Cloud pre-filters, which could reduce frontend compute
- **Effort**: MEDIUM — would require auth + pricing model validation; may duplicate existing 4-stage filter logic already implemented
- **Risk**: MEDIUM — adds cost (GDELT Project is free); may lock into commercial offering
- **Status**: WATCH FOR PHASE 2 — useful if BigQuery access becomes expensive or data volume exceeds current rates. Keep free GDELT pipeline as baseline
- **Sources**: [GDELT Cloud Docs](https://docs.gdeltcloud.com/), [GDELT Cloud Platform](https://gdeltcloud.com/)

#### Finding 3.3: POLECAT Dataset (Alternative to GDELT) (MEDIUM Relevance)
- **What**: POLECAT (Political Event Classification, Attributes, and Types) is an emerging alternative to GDELT. Smaller scale, but much lower redundancy and higher domain accuracy for geopolitical events
- **Impact**: Parallax's 4-stage GDELT filter combats redundancy (structural dedup + semantic dedup). POLECAT's smaller, higher-quality dataset could reduce noise filtering overhead
- **Effort**: HIGH — would require reworking entire ingestion pipeline, entity matching, and eval baselines
- **Risk**: HIGH — smaller dataset may miss breaking news; would need parallel ingestion with GDELT as fallback
- **Status**: RESEARCH ONLY FOR NOW — insufficient maturity for Phase 1. Monitor and evaluate after primary GDELT pipeline proves stable
- **Sources**: [POLECAT vs GDELT Comparison](https://doi.org/10.3390/data11070158)

---

### 4. **Eval/MLOps**

#### Finding 4.1: LLM Calibration Evaluation Standards (MEDIUM Relevance)
- **What**: Research in 2026 shows LLM confidence (probability estimates) are often poorly calibrated. Calibration evaluation frameworks now include multi-answer regimes, with scalar confidence being insufficient
- **Impact**: Parallax's eval framework scores calibration as "confidence level meaningful over 30-day rolling window." Recent research suggests need for richer calibration metrics (confidence intervals, uncertainty quantiles)
- **Effort**: MEDIUM — add calibration evaluation layer that bins predictions by reported confidence and measures actual accuracy per bin
- **Risk**: LOW — additive eval metric, no changes to agent prompts
- **Status**: NICE-TO-HAVE FOR PHASE 2 — current binary direction + magnitude accuracy sufficient for MVP. Add after first 30-day run
- **Sources**: [Calibration in LLMs 2026](https://arxiv.org/pdf/2605.11954), [LLM Evaluation Frameworks 2026](https://www.mlaidigital.com/blogs/llm-evaluation-frameworks-2026), [Best LLM Evaluation Tools 2026](https://medium.com/online-inference/the-best-llm-evaluation-tools-of-2026-40fd9b654dce)

#### Finding 4.2: Geopolitical Event Forecasting Benchmarks (MEDIUM Relevance)
- **What**: New benchmarks like MIRAI, ForecastBench, and ThinkTank-ME evaluate LLM agents on structured event forecasting and compare vs. human expert forecasters
- **Impact**: These benchmarks could serve as external eval baselines for Parallax. ForecastBench notes that LLMs still substantially underperform expert humans on unresolved questions
- **Effort**: LOW — implement as optional comparison metric (download ForecastBench dataset, backtest predictions against it)
- **Risk**: NONE — optional eval only
- **Status**: RESEARCH FOR PHASE 2 — would provide external validation that predictions are meaningful vs. naive baseline
- **Sources**: [MIRAI Framework](https://arxiv.org/pdf/2603.16642), [ForecastBench](https://arxiv.org/pdf/2411.14042)

---

### 5. **Performance**

#### Finding 5.1: React WebSocket Batching + Debouncing (MEDIUM Relevance)
- **What**: Latest best practices for React dashboards handling high-frequency updates: batch WebSocket messages (buffer 100ms), use useRef for mutable data (not useState), employ Web Workers for heavy computation
- **Impact**: Parallax frontend already implements batching and useRef for hex data (spec Section 5, render performance). This is **already in design**; validates architectural choice
- **Effort**: NONE — design already correct
- **Risk**: NONE
- **Status**: VALIDATED — current architecture is sound. Consider Web Workers for future client-side anomaly detection
- **Sources**: [React WebSocket Optimization 2026](https://medium.com/@SanchezAllanManuel/optimizing-real-time-performance-websockets-and-react-js-integration-part-i-e563664647d3), [Trading Dashboard React 2026](https://openwebsolutions.in/blog/high-performance-trading-dashboard-react-websockets/)

#### Finding 5.2: DuckDB Time-Series Optimization Patterns (MEDIUM Relevance)
- **What**: Modern DuckDB time-series practices use watermark-based late event handling and bucket-based incremental aggregation instead of full periodic snapshots
- **Impact**: Parallax currently uses delta table + periodic snapshots every 100 ticks. Watermark approach could reduce storage overhead for high-tick-rate runs while still handling out-of-order events
- **Effort**: MEDIUM — refactor `world_state_delta` ingestion logic to track watermark boundaries instead of hard snapshot intervals
- **Risk**: LOW — would improve scalability without breaking current replay logic
- **Status**: DEFER TO PHASE 2 — current design works well for 15-min tick rate; watermark optimization matters more at 1-sec ticks
- **Sources**: [DuckDB Time-Series Tricks](https://medium.com/@Quaxel/5-duckdb-time-series-tricks-for-out-of-order-events-5a25dd0afa58), [Time-Series with DuckDB](https://www.dench.com/blog/duckdb-time-series)

#### Finding 5.3: Lightweight Charting Libraries (LOW Relevance)
- **What**: LightweightCharts library (WebGL/Canvas-based) is optimized for high-frequency financial data rendering with candlestick support
- **Impact**: Parallax uses Recharts for sparklines in indicators. LightweightCharts could improve performance if indicator update frequency increases
- **Effort**: HIGH — would require replacing Recharts components
- **Risk**: MEDIUM — style/customization might differ
- **Status**: DEFER — Recharts adequate for current design
- **Sources**: [React Performance Dashboard 2026](https://www.sparkleweb.in/blog/building_real-time_business_dashboards_with_react_in_2026)

---

## Top 3 Recommendations

### 🔴 **#1: Implement Batch API for Non-Urgent Eval Calls (HIGH Impact, Medium Effort)**

**Why**: Cut LLM costs by 50-70% with minimal engineering. Parallax spec already budgets $60-150 for 30-day run; batching could cut to $30-50.

**What**: Refactor daily scorecard generation and eval meta-agent calls to use Batch API instead of immediate calls. Keep live agent decisions synchronous.

**How**:
1. Identify non-blocking LLM calls: eval scoring, daily report generation, prompt suggestion
2. Queue these to `eval_queue` table instead of calling Claude immediately
3. Spawn background job that batches queued requests into single Batch API call daily
4. Poll Batch API for results (24-48 hour SLA acceptable)
5. Update eval dashboard to show when results finalized

**Timeline**: 1-2 days implementation. High ROI.

---

### 🟡 **#2: Add AIS Real-Time Shipping Data Feed (Medium Impact, Low Effort)**

**Why**: Direct vessel tracking ground-truth for Hormuz flow scenarios. GDELT inference is useful but AIS provides actual ship positions.

**What**: Integrate AISstream.io free WebSocket tier to track vessel density/routes in Hormuz corridor. Store to `raw_ais` table.

**How**:
1. Implement AIS WebSocket ingestion module (parallel to GDELT)
2. Parse NMEA/JSON position reports
3. Convert vessel lat/lng to H3 cells
4. Aggregate vessel count per cell per 15-min tick
5. Use as eval ground truth: "did model predict vessel flow reduction correctly?"

**Timeline**: 2-3 days. Improves eval grounding significantly.

**Cost**: Free tier sufficient; no production API expense.

---

### 🟡 **#3: Evaluate GDELT Cloud for Phase 2 Scaling (Medium Impact, Research)**

**Why**: If BigQuery GDELT ingestion becomes expensive or noisy filtering becomes bottleneck, GDELT Cloud's pre-structured events reduce frontend compute.

**What**: Parallel research track (not Phase 1): Compare raw GDELT (free) vs. GDELT Cloud (commercial) on cost, latency, and signal quality.

**How**:
1. Contact GDELT Cloud for demo/pricing
2. Run 7-day parallel ingestion: raw GDELT + GDELT Cloud
3. Compare: cost/event, noise ratio, latency to agent router
4. Decide if commercial option justified at scale

**Timeline**: Decision after Phase 1 stabilizes (~week 2-3). No Phase 1 blocker.

---

## Links to Sources

### Spatial/Geo
- [H3 GitHub Fork (SIMD)](https://github.com/mattsta/h3)
- [MapLibre MLT Release](https://maplibre.org/news/2026-01-23-mlt-release/)
- [DuckDB Spatial Extension](https://duckdb.org/docs/lts/core_extensions/spatial/overview)

### LLM/Agent
- [Claude Batch Processing](https://platform.claude.com/docs/en/build-with-claude/batch-processing)
- [Claude Prompt Caching](https://platform.claude.com/docs/en/build-with-claude/prompt-caching)
- [Cache TTL 2026 Analysis](https://dev.to/whoffagents/claude-prompt-caching-in-2026-the-5-minute-ttl-change-thats-costing-you-money-4363)
- [Langfuse A/B Testing](https://langfuse.com/docs/prompt-management/features/a-b-testing)

### Real-time Data
- [AISstream.io](https://aisstream.io/)
- [50 Best Ship Tracking APIs 2026](https://hormuzmonitor.com/50-best-ship-tracking-apis-2026/)
- [GDELT Cloud](https://gdeltcloud.com/)
- [POLECAT vs GDELT](https://doi.org/10.3390/data11070158)

### Eval/MLOps
- [LLM Calibration Research](https://arxiv.org/pdf/2605.11954)
- [LLM Evaluation Frameworks 2026](https://www.mlaidigital.com/blogs/llm-evaluation-frameworks-2026)
- [MIRAI Forecasting Framework](https://arxiv.org/pdf/2603.16642)

### Performance
- [React WebSocket Optimization](https://medium.com/@SanchezAllanManuel/optimizing-real-time-performance-websockets-and-react-js-integration-part-i-e563664647d3)
- [DuckDB Time-Series Optimization](https://medium.com/@Quaxel/5-duckdb-time-series-tricks-for-out-of-order-events-5a25dd0afa58)

---

## Conclusion

Current Parallax tech stack is well-chosen and aligned with 2026 best practices. Three immediate opportunities exist:

1. **Cost optimization** (Batch API) — High impact, low risk
2. **Data enrichment** (AIS) — Moderate impact, low risk
3. **Commercial alternative evaluation** (GDELT Cloud) — Phase 2 research track

No critical gaps found. Design decisions (WebSocket batching, useRef for hex data, prompt caching) are validated against latest industry patterns.

---

**Report generated**: 2026-07-18  
**Next review**: 2026-07-25
