# Technology Research Report — 2026-09-02

## Executive Summary

Conducted targeted technology research across 5 critical areas: Spatial/Geo, LLM/Agent, Real-time Data, Eval/MLOps, and Performance. Identified 3 high-impact, low-friction improvements: GeoArrow spatial acceleration, real-time AIS vessel tracking, and automatic prompt versioning via Lilypad.

---

## Search Focus Areas

1. **Spatial/Geo**: H3 updates, DuckDB extensions, deck.gl performance, alternative hex grids
2. **LLM/Agent**: Claude API features, prompt caching, batch processing, structured output
3. **Real-time Data**: GDELT alternatives, AIS shipping data, oil price APIs
4. **Eval/MLOps**: Prediction frameworks, prompt versioning, A/B testing for prompts
5. **Performance**: DuckDB optimization, WebSocket React patterns, streaming architecture

---

## Findings by Category

### 1. Spatial/Geo

#### DuckDB GeoArrow + WebAssembly Integration (HIGH RELEVANCE)
- **Status**: Production-ready (GeoArrow spec, DuckDB-Wasm support launched 2026)
- **Impact**: 10x–50x performance boost for browser-based spatial analytics
- **Architecture**: Columnar GeoArrow format bypasses geometry parsing overhead; per-thread arena allocation eliminates heap contention
- **Relevance to Parallax**: DIRECT — addresses the dashboard's deck.gl render thrashing on high-frequency cell updates (currently mitigated with useRef, but GeoArrow would eliminate the problem root)
- **Effort**: MEDIUM-HIGH (refactor spatial queries to leverage POINT_2D/LINESTRING_2D/POLYGON_2D types)
- **Risk**: LOW (official DuckDB extension, proven in production use)
- **Notes**: Experimental geometry types (POINT_2D, LINESTRING_2D, POLYGON_2D) with fixed memory layout enable aggressive vectorization — 2x–50x speedup over generic GEOMETRY type

#### H3 SIMD Acceleration (mattsta fork)
- **Status**: Post-2026-04-26 fork with bulk APIs and SIMD optimizations
- **Impact**: 10–30% speedup on H3 cell-to-cell operations (neighbor lookups, ring generation)
- **Relevance**: MEDIUM (incremental, not transformative for current workload)
- **Effort**: LOW (drop-in replacement for upstream h3-py, if pinning is already managed)
- **Risk**: LOW-MEDIUM (community fork, but well-documented)

#### deck.gl H3HexagonLayer Performance Mode
- **Status**: v9+ supports `highPrecision: 'auto'` with flat shading for ColumnLayer
- **Impact**: Developers can now force low-precision (instanced) rendering for 2x–3x throughput on large datasets
- **Relevance**: MEDIUM (Parallax already uses highPrecision; auto mode is safer than forcing false)
- **Effort**: LOW (property toggle)
- **Risk**: NEGLIGIBLE

---

### 2. LLM/Agent

#### Claude API Prompt Caching — 5-Minute TTL Change (COST IMPACT)
- **Status**: Anthropic changed default cache TTL from 60 minutes → 5 minutes in early 2026
- **Impact**: Reduced cost per cache write (now cheaper to write frequently), but shorter window for reuse
- **Relevance**: HIGH (Parallax uses prompt caching for agent system prompts)
- **Consideration**: For agent cooldown windows (30 min for sub-actors, 1 hr for country agents), the 5-min TTL means **cache misses after cooldown restarts**. For low-activity periods (e.g., nights), the shorter TTL saves money. **Tradeoff**: Accept higher cache misses for lower write costs, OR use 1-hour TTL beta header (if available) for longer reuse window.
- **Effort**: NONE (automatic if using latest SDK)
- **Risk**: LOW (understand the cost/latency tradeoff)

#### Batch API with 50% Discount
- **Status**: Message Batches API supports prompt caching and deferred processing
- **Use case**: Historical replay, daily eval cron, bulk prediction generation
- **Relevance**: MEDIUM (reduces operational cost but adds latency — not suitable for live prediction paths)
- **Effort**: LOW (add batch submission for non-real-time workflows)
- **Risk**: NEGLIGIBLE (complementary to live pipeline)

#### Output Caching (2026 Feature)
- **Status**: NEW — cache output tokens in addition to input tokens
- **Impact**: Useful when agent responses are repetitive or when the same decision is inferred multiple times
- **Relevance**: LOW-MEDIUM (only if sub-actors or country agents generate identical outputs frequently — not typical)
- **Effort**: LOW (enable in request params)

---

### 3. Real-time Data Sources

#### AIS (Automatic Identification System) Vessel Tracking
- **Free Options**:
  - **AISHub**: Free, no auth, JSON/XML/CSV, ~500–1000 message/sec global
  - **VesselAPI Free Tier**: 700K+ vessels, sub-minute updates, no credit card
- **Paid Options**:
  - **Datalastic**: €99/month, developer-friendly, 14-day free trial, instant API key provisioning
  - **Data Docked**: Satellite + terrestrial hybrid AIS coverage
- **Relevance to Parallax**: HIGH (Hormuz traffic disruption is a core prediction target; AIS data validates Hormuz flow %)
- **Effort**: LOW (REST API, similar integration to EIA)
- **Risk**: LOW (free tiers available for MVP)
- **Notes**: Terrestrial AIS covers 40–60 NM from coast (covers Hormuz strait). Satellite AIS provides global coverage but higher latency. For Hormuz focused scenario, terrestrial is sufficient.

#### Oil Price APIs
- **Primary**: OilPriceAPI (free tier: 10K requests/month, paid: $19/month+)
  - REST endpoint, source-timestamped, SDKs for Python/Node
  - Collects from multiple independent sources; tracks spreads
  - Benchmarks: Brent, WTI, Dubai, Urals, OPEC Basket
- **Secondary**: Trading Economics (Bloomberg-grade data, paid)
- **Relevance**: MEDIUM (already in use via EIA API v2; OilPriceAPI provides redundancy and real-time sourcing)
- **Effort**: LOW (drop-in addition)
- **Risk**: LOW (API reliability proven)

#### GDELT Alternatives & Complements
- **ACLED** (Armed Conflict Location & Event Data): Structured, validated conflict events, lower recall than GDELT but higher precision. Recommended for pairing with GDELT.
- **UCDP** (Uppsala Conflict Data Program): Academically rigorous, free API with auth, best for historical conflict definitions. Lagged.
- **WORLDREP**: New dataset addressing GDELT limitations in multilateral relations and relationship labeling accuracy.
- **WorldMonitor**: Comprehensive geopolitical API mentioned as alternative (limited details in search results).
- **Relevance to Parallax**: MEDIUM (GDELT is still primary; ACLED + WORLDREP could augment for higher precision on escalation signals)
- **Effort**: LOW (add as secondary data source)
- **Risk**: LOW (validation framework already in place for new event sources)
- **Note**: Parallax's 3-stage GDELT filter (volume gate + named-entity override, structural dedup, semantic dedup) already mitigates GDELT noise; alternatives add precision but not strictly necessary for Phase 1.

---

### 4. Eval/MLOps

#### Lilypad (Automatic Prompt Versioning)
- **Status**: Production library, extends Mirascope
- **Features**: `@lilypad.trace` decorator for automatic version capture, execution tracing, prompt diffs
- **Relevance to Parallax**: HIGH (directly solves the challenge of linking predictions/eval scores back to the exact prompt version that produced them)
- **Current Workaround**: Parallax stores `prompt_version: "v1.2.0"` in every prediction record and maintains an `agent_prompts` table with full prompt text. Lilypad automates this.
- **Effort**: LOW (wrapper decorator, minimal refactoring)
- **Risk**: LOW (lightweight, non-invasive)
- **Integration Path**: Wrap `_run_cascade_for_agents()` or individual agent LLM calls with `@lilypad.trace` → automatic version tracking + tracing to Lilypad backend (self-hosted or managed) → simplifies eval pipeline

#### DeepEval with A/B Testing
- **Status**: Production framework (metrics, test authoring, CI/CD integration)
- **Features**: Direction/magnitude/calibration scoring, A/B testing for prompt variants, observability dashboards
- **Relevance to Parallax**: MEDIUM (complements existing `eval_results` table; DeepEval could automate metric computation)
- **Effort**: MEDIUM (integrate scoring functions into `compute_daily_scorecard()`)
- **Risk**: LOW (optional — can run in parallel with existing evaluation)

#### Traceability Trend
- **Observation**: By 2026, best practice is to annotate eval scores with exact prompt ID, model ID, and dataset version at ingestion time. This enables root-cause analysis ("why did v1.2.0 underperform?") without manual archaeology.
- **Relevance to Parallax**: HIGH (Parallax already does this via `prompt_version` in predictions; Lilypad + DeepEval would formalize and automate)
- **Effort**: LOW

---

### 5. Performance

#### React WebSocket Streaming Patterns (Critical for Dashboard)
- **Challenge**: WebSocket messages arriving at 50–100 ms intervals trigger React re-renders for each update, causing deck.gl canvas thrashing
- **Solutions**:
  1. **Update Batching**: Buffer WebSocket messages for 100–500 ms, then flush as single state mutation (Parallax already does this with useRef)
  2. **useSyncExternalStore** (React 18): Official primitive for subscribing to external data sources (e.g., WebSocket, Redux, event emitters) without triggering unnecessary re-renders
  3. **Virtualization**: Render only visible rows in agent feed (currently unbounded scroll)
  4. **Web Workers**: Offload expensive aggregations (rolling averages, anomaly detection) to background thread
- **Relevance to Parallax**: HIGH (Parallax already uses useRef batching; useSyncExternalStore could simplify further)
- **Effort**: LOW (adopt useSyncExternalStore for dashboard state subscriptions)
- **Risk**: LOW (official React API, mature)

#### DuckDB Spatial Performance Optimizations
- **Arena Allocation**: Per-thread arena backed by buffer manager eliminates heap contention, enables vectorized execution
- **Experimental Geometry Types**: POINT_2D, LINESTRING_2D, POLYGON_2D with fixed memory layout → 2x–50x speedup over generic GEOMETRY
- **Native CRS Support** (v1.5.0, Feb 2026): Improved spatial workflows for coordinate transformations
- **Relevance**: HIGH (H3 cells are POINT_2D under the hood; storing routes as LINESTRING_2D would accelerate flow calculations)
- **Effort**: MEDIUM-HIGH (refactor spatial schema)
- **Risk**: LOW (official, experimental-but-production-ready)

---

## Top 3 Recommendations

### 1. Adopt DuckDB GeoArrow + Experimental Geometry Types (HIGH PRIORITY)

**Why**: Parallax's bottleneck is real-time H3 cell state updates (world_state_delta) flowing to the dashboard. The current workaround (useRef batching) works but is fragile under high-frequency updates. GeoArrow eliminates the parsing overhead entirely, and experimental geometry types (POINT_2D for cells, LINESTRING_2D for routes) would accelerate cascade rule computations.

**Action**:
1. Refactor `world_state_delta` schema to use POINT_2D for cell centers and LINESTRING_2D for shipping routes
2. Update spatial queries in `cascade.py` to leverage fixed-layout geometry types
3. Enable GeoArrow output format for WebSocket cell_update messages (if deck.gl supports native GeoArrow input)
4. Benchmark: Expect 3x–10x throughput improvement for cell updates under load

**Effort**: MEDIUM-HIGH (2–3 weeks, requires schema migration and query refactoring)
**Risk**: LOW (DuckDB spatial extension is production-ready; experimental types are well-documented)
**Cost Impact**: Negligible
**Timeline**: Post-Phase 1 optimization

---

### 2. Integrate Real-time AIS Vessel Tracking (MEDIUM PRIORITY)

**Why**: Hormuz traffic disruption is the #1 prediction target. Current model relies on rule-based capacity estimates; actual vessel positions would validate predictions and ground truth. AISHub or VesselAPI free tier requires minimal engineering.

**Action**:
1. Add AISHub or VesselAPI as secondary data source (alongside GDELT/EIA)
2. Ingest vessel positions in Hormuz bounding box (26°N–27°N, 55°E–57°E) into `raw_ais` table
3. Compute Hormuz northbound/southbound vessel counts per 1-hour window
4. Inject as signal into agent context: "Vessel count in Hormuz: N, trend: up/down"
5. Use as ground truth for Hormuz_traffic_reduction predictions

**Effort**: LOW (API integration, ~100 LOC)
**Risk**: LOW (free tier available; fallback to rule-based if API unavailable)
**Cost**: Negligible (free tier) or ~€99/month for Datalastic if high-volume needed
**Timeline**: Phase 1 + 1 week

---

### 3. Implement Lilypad for Automatic Prompt Versioning & Tracing (LOW PRIORITY)

**Why**: Parallax's eval framework manually tracks prompt versions via `agent_prompts` table and predictions.prompt_version string. Lilypad automates this, reducing operational friction during prompt iteration cycles and enabling root-cause analysis. A/B testing becomes trivial.

**Action**:
1. Install Lilypad via pip
2. Wrap agent LLM calls (in `cascade.py`) with `@lilypad.trace` decorator
3. Configure Lilypad backend (self-hosted or managed; cheap/free for MVP)
4. Refactor `compute_daily_scorecard()` to pull trace metadata from Lilypad instead of reconstructing from DB tables
5. Enable Lilypad dashboard for prompt diff visualization during admin review of eval results

**Effort**: LOW (wrapper decoration, ~50 LOC)
**Risk**: LOW (non-invasive, complementary to existing eval)
**Cost Impact**: Negligible (self-hosted or free tier)
**Timeline**: Phase 1 + 2–3 days

---

## Secondary Opportunities (Low Priority, Future Consideration)

| Technology | Fit | Effort | Notes |
|-----------|-----|--------|-------|
| ACLED + WORLDREP as GDELT complement | MEDIUM | LOW | Higher precision on conflict escalation, but 3-stage filter already mitigates GDELT noise |
| Batch API for historical replay | MEDIUM | LOW | Reduces eval cost, but not urgent until Phase 2 scaling |
| Output caching (Claude API) | LOW | LOW | Only useful if agent responses repeat; rare in geopolitical reasoning |
| useSyncExternalStore for dashboard | MEDIUM | LOW | Simplifies state management, but useRef + batching already works well |

---

## Notes on Tradeoffs & Risks

### Claude API TTL Change (5-minute cache, down from 60 minutes)
Parallax benefits from longer cache windows because agent cooldowns are 30 min (sub-actors) and 1 hr (country agents). With 5-min TTL, cache misses more frequently during active periods. **Mitigation**: If available, use the 1-hour TTL beta header for this use case. Monitor Anthropic's documentation for updated guidance on long-running agent workflows.

### GDELT Alternatives
GDELT is irreplaceable for real-time signal volume, but ACLED and WORLDREP address precision. Consider adding as secondary stream only if eval metrics show systematic false positives on escalation predictions.

### AIS Data Quality
Terrestrial AIS covers Hormuz strait well (40–60 NM from coast). Satellite AIS provides global coverage but higher latency and cost. For Phase 1, terrestrial AIS (free tier) is sufficient.

---

## Sources

### Spatial/Geo
- [DuckDB Spatial Extension Overview](https://duckdb.org/docs/lts/core_extensions/spatial/overview)
- [GeoArrow & High-Performance Spatial Analytics (FOSS4G 2026)](https://talks.osgeo.org/foss4g-2026/talk/T7TNGZ/)
- [H3 SIMD Fork (mattsta)](https://github.com/mattsta/h3)
- [H3 Documentation](https://h3geo.org/docs/)
- [deck.gl H3HexagonLayer API](https://deck.gl/docs/api-reference/geo-layers/h3-hexagon-layer)
- [deck.gl What's New](https://deck.gl/docs/whats-new)

### LLM/Agent
- [Claude Platform: Batch Processing](https://platform.claude.com/docs/en/build-with-claude/batch-processing)
- [Claude API Prompt Caching Guide 2026](https://hidekazu-konishi.com/entry/anthropic_claude_api_prompt_caching_and_token_efficiency.html)
- [Prompt Caching TTL Changes 2026](https://dev.to/whoffagents/claude-prompt-caching-in-2026-the-5-minute-ttl-change-thats-costing-you-money-4363)

### Real-time Data
- [AISHub Free AIS API](https://www.aishub.net/)
- [VesselAPI Real-time AIS Data](https://vesselapi.com/ais-data-api)
- [OilPriceAPI Real-time Oil Prices](https://www.oilpriceapi.com/)
- [GDELT Alternatives Research](https://www.worldmonitor.app/blog/posts/free-geopolitical-data-apis-2026/)
- [GDELT Futures Dataset Paper](https://arxiv.org/html/2411.14042v1)

### Eval/MLOps
- [Best LLM Evaluation Tools 2026](https://medium.com/online-inference/the-best-llm-evaluation-tools-of-2026-40fd9b654dce)
- [DeepEval Framework](https://deepeval.com/blog/top-5-llm-evaluation-frameworks)
- [Braintrust Prompt Evaluation Tools 2026](https://www.braintrust.dev/articles/best-prompt-evaluation-tools-2025)

### Performance
- [Streaming Architecture 2026: Beyond WebSockets](https://jetbi.com/blog/streaming-architecture-2026-beyond-websockets)
- [React WebSocket Optimization Guide](https://www.sitepoint.com/streaming-backends-react-controlling-re-render-chaos/)
- [Real-time Dashboard Development 2026](https://www.sparkleweb.in/blog/building_real-time_business_dashboards_with_react_in_2026)

---

## Summary

**High-impact findings**:
1. DuckDB GeoArrow for 10x–50x spatial query acceleration (production-ready)
2. Real-time AIS vessel tracking validates Hormuz disruption predictions (free tier available)
3. Lilypad automates prompt versioning + tracing (low friction, high value for eval cycle)

**Cost implications**: None (all recommendations are additive or cost-neutral on the $20/day budget)

**Timeline**: Top 3 recommendations can be staged across Phase 1 and early Phase 2 without blocking current functionality.

---

*Report generated 2026-09-02*
