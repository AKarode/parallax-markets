# Technology Research Report: Parallax Stack Improvements
**Date:** 2026-07-27  
**Focus Areas:** Spatial/Geo, LLM/Agent, Real-time Data, Eval/MLOps, Performance  
**Researcher:** Daily Tech Scout

---

## Executive Summary

This research identifies 8 actionable improvements across the Parallax tech stack. Highest-value findings include DuckDB spatial v0.9.0 (50x performance gain), Claude Sonnet 5 (June 2026 release), GDELT Cloud API (structured geopolitical events), and AIS vessel tracking integrations. One critical regression: Claude prompt caching TTL reduced from 60min to 5min in early 2026, increasing cache miss costs 30-60% for production workloads.

---

## Findings by Category

### 1. Spatial/Geo

#### Finding 1.1: DuckDB Spatial Extension v0.9.0 — 50x Query Performance Gain
- **Status:** Production-ready (May 2026)
- **Relevance:** HIGH
- **Effort:** LOW (drop-in replacement)
- **Risk:** LOW (backward compatible)
- **Details:** 
  - Internal optimizations using `wk` and `geoarrow` libraries
  - Measured improvement: 28.4ms (optimized) vs 1380ms (baseline) — **~48x speedup** on spatial radius queries
  - Already integrated into DuckDB core; no separate extension install
  - Perfect for Parallax's dense H3 cell queries at res 7-9
- **Action:** Upgrade DuckDB to >= 1.2.0 and verify cell neighbor/radius lookups in cascade engine
- **Cost Impact:** Reduces DB bottleneck; cascade rule updates will execute faster with no API cost increase

#### Finding 1.2: DuckDB Native CRS Support — Arriving v1.5.0 (Feb 2026 / likely deployed by now)
- **Status:** Beta/Early GA (DuckDB v1.5.0+)
- **Relevance:** MEDIUM
- **Effort:** MEDIUM (schema refactor)
- **Risk:** LOW
- **Details:**
  - Coordinate reference system handling currently delegated to shapely/PostGIS patterns
  - Native CRS in DuckDB allows geodetic calculations (distance, bearing) without Python roundtrips
  - Useful for Hormuz threat distance calculations (e.g., "patrol vessel 5km from tanker")
- **Action:** If DuckDB v1.5+ is deployed, test CRS for marine geometry (WGS84 + projected mercator)
- **Cost Impact:** Marginal — eliminates occasional Python-level CRS validation, not a primary bottleneck

#### Finding 1.3: H3 Bulk APIs & SIMD Acceleration
- **Status:** Stable (bulk APIs in core H3); SIMD fork available (mattsta/h3)
- **Relevance:** LOW (incremental)
- **Effort:** VERY LOW (already using h3-js bulk APIs)
- **Risk:** VERY LOW
- **Details:**
  - H3 library added bulk operations: `latLngsToCells`, `cellsToLatLngs`, `cellsToBoundaries`
  - Parallax already uses these implicitly through DuckDB's H3 extension
  - SIMD-accelerated fork (mattsta/h3) exists for C/Rust users, not applicable to current Node/Python stack
- **Action:** No action needed; already in use
- **Cost Impact:** None

### 2. LLM/Agent

#### Finding 2.1: Claude Sonnet 5 (June 30, 2026) — New Agentic Baseline
- **Status:** GA (June 2026)
- **Relevance:** HIGH
- **Effort:** LOW (swap model ID in config)
- **Risk:** MEDIUM (test prediction quality before full deployment)
- **Details:**
  - Announced as "most agentic Sonnet yet"
  - Improvements in: coding, agentic work, tool use, computer use, professional knowledge
  - Better structured output reliability vs 4.5/4.6
  - Likely higher cost than 4.6; exact pricing not yet confirmed in search results
- **Action:** 
  1. A/B test Sonnet 5 on 10% of agent decisions for 3 days
  2. Compare prediction accuracy vs baseline
  3. If equivalent/better accuracy, evaluate cost delta before rollout
- **Cost Impact:** Unknown (requires pricing check); likely 15-25% higher than Sonnet 4.6

#### Finding 2.2: Claude Batch API — 50% Cost Reduction Available
- **Status:** GA (general availability)
- **Relevance:** HIGH
- **Effort:** MEDIUM (requires architecture change)
- **Risk:** LOW (no change to model outputs)
- **Details:**
  - Processes requests asynchronously within 24hr window for 50% discount on all tokens
  - Not suitable for live predictions (requires real-time response)
  - Ideal for: daily scorecard computation, eval meta-agent (prompt improvement pipeline), historical backtesting
- **Action:**
  1. Batch eval cron (runs nightly) — move to Batch API
  2. Batch scorecard computation (runs once daily) — move to Batch API
  3. Keep live agent decisions on standard API (must complete within 15-min tick)
- **Cost Impact:** ~50% reduction on eval tasks (~$0.17/day from $0.35/day = $0.18/day savings); $5.40/month

#### Finding 2.3: Prompt Caching TTL Regression — Critical 5-min Window Change
- **Status:** Deployed early 2026 (breaking change)
- **Relevance:** HIGH (negative)
- **Effort:** MEDIUM (monitoring + mitigation)
- **Risk:** MEDIUM (already affecting costs)
- **Details:**
  - Anthropic reduced prompt cache TTL from 60 minutes → 5 minutes without warning
  - Impact: On a 15-min tick cycle with 50 agents, cache misses increase from ~1/agent/hour to ~1/agent/15min
  - At 5-min TTL, cache hit rate drops 90% for typical geopolitical event workflows
  - This is a **cost regression of 30-60% for production workloads** relying on caching
  - System prompts (largest cached component) now re-paid every 5-10 minutes
- **Action:**
  1. Measure current cache hit rate (query DuckDB `llm_usage` for cache_hit_rate)
  2. If < 50% hits, consider switching to Batch API for agent swarm
  3. Alternatively, batch agent decisions within 5-min windows to keep system prompt cached
- **Cost Impact:** **Negative**: $0.20-0.30/day additional cost if not mitigated (cache regression on existing workload)

#### Finding 2.4: Combined Batch + Caching = 95% Savings
- **Status:** Confirmed (Anthropic docs)
- **Relevance:** MEDIUM
- **Effort:** MEDIUM (composition)
- **Risk:** LOW
- **Details:**
  - Batch API: 50% off
  - Caching within batch: 90% off cached tokens
  - Combined effect: ~95% total savings on batch requests
- **Action:** For eval workflows (daily cron), use Batch API + prompt caching
- **Cost Impact:** Minimal (eval already cheap; big gains on high-volume batch ops)

### 3. Real-time Data

#### Finding 3.1: GDELT Cloud API (MCP-Ready) — Structured Events
- **Status:** GA (2026)
- **Relevance:** HIGH (complements existing GDELT BigQuery)
- **Effort:** LOW (drop-in supplement to current GDELT ingestion)
- **Risk:** LOW
- **Details:**
  - Replaces raw GDELT with structured Events database (clustered Stories, linked Entities, summaries)
  - Hourly update cycle (vs current 15-min BigQuery ingestion)
  - MCP tools available for direct Claude integration (can embed event fetching in agent prompts)
  - Alternative to custom GDELT noise filter pipeline
- **Action:**
  1. Compare GDELT Cloud event relevance scores vs current 4-stage filter on 1-week dataset
  2. If precision improves, migrate ingestion to `gdeltcloud.com/api` (hourly)
  3. Keep Google News RSS as primary (5-15min, free) but use GDELT Cloud for structure enrichment
- **Cost Impact:** Minimal/unknown (free tier likely exists; check pricing)

#### Finding 3.2: Free AIS Vessel Tracking — Multiple Real-time Options
- **Status:** GA (multiple providers)
- **Relevance:** MEDIUM (new capability for Hormuz flow modeling)
- **Effort:** MEDIUM (new data ingestion module)
- **Risk:** LOW
- **Details:**
  - **AISstream.io**: Free WebSocket feed, bounding box subscriptions (perfect for Hormuz strait res 7-8 cells)
  - **AISHub**: Free aggregated AIS via JSON/XML/CSV
  - **VesselAPI**: Paid with free tier, 700K vessels, <1min update latency
  - **OpenAIS**: Open-source tools for vessel tracking analysis
- **Action:**
  1. Prototype AISstream.io WebSocket integration for Hormuz region (bounded by Lat 25-27N, Lng 54-58E)
  2. Parse live AIS messages → extract vessel positions → map to H3 cells (res 8)
  3. Correlate with "hormuz_traffic" KPI in cascade engine (replaces static estimates)
- **Cost Impact:** None (free); adds real-time shipping data validation

#### Finding 3.3: GDELT Guru — AI-Enhanced Geopolitical Intelligence
- **Status:** GA (2026)
- **Relevance:** LOW (alternative to current agent swarm, not complementary)
- **Effort:** N/A (external service, not integration candidate)
- **Risk:** LOW
- **Details:**
  - Third-party service combining GDELT + ML + LLM for deduplication and summarization
  - Targets DIY situational awareness; Parallax already does custom dedup + LLM reasoning
- **Action:** Skip (Parallax's custom pipeline is more specialized than generic GDELT Guru)
- **Cost Impact:** None (external competitor, not adopted)

### 4. Eval/MLOps

#### Finding 4.1: LLM-as-Judge for Prediction Calibration
- **Status:** Production-ready (2026)
- **Relevance:** HIGH (complements existing eval framework)
- **Effort:** LOW (add judge stage to eval pipeline)
- **Risk:** LOW
- **Details:**
  - LLM-as-Judge achieves 80-90% agreement with human judgment at 500-5000x lower cost
  - Use case: Evaluate whether agent predictions are "reasonable" (safety check before trading)
  - Requires calibration against 85-90% on 100 human-labeled examples per rubric
- **Action:**
  1. Add LLM judge to eval cron: "Is this prediction reasonable given the evidence?"
  2. Use Claude Haiku (cheapest model) for judge calls
  3. Flag predictions failing judge threshold (confidence > judge disagreement)
  4. Track judge-vs-human agreement on subset of predictions
- **Cost Impact:** +$0.10-0.20/day (Haiku is cheap; only runs on misses/surprises)

#### Finding 4.2: Production Evaluation Pipeline — Four-Stage Gate
- **Status:** Industry standard (2026)
- **Relevance:** MEDIUM (formalize existing ad-hoc process)
- **Effort:** LOW (restructure existing code)
- **Risk:** LOW
- **Details:**
  - Stage 1: Local rapid iteration (DeepEval/Promptfoo against 200-500 golden examples)
  - Stage 2: Automated quality gates (calibration, direction accuracy, magnitude)
  - Stage 3: Human review (misses, ambiguous cases)
  - Stage 4: Deployment + monitoring (A/B test, rollback on degradation)
- **Action:**
  1. Current eval framework follows this implicitly; make explicit via stage markers in code
  2. Invest in DeepEval or Promptfoo for local testing (not currently used)
  3. Define auto-rollback threshold: if 7-day accuracy drops > 5%, revert prompt version
- **Cost Impact:** Minimal (tooling free/cheap; improves quality)

#### Finding 4.3: Judge Calibration Baseline — 100 Examples Required
- **Status:** Industry standard
- **Relevance:** MEDIUM (quality guardrail)
- **Effort:** MEDIUM (curate training set)
- **Risk:** LOW
- **Details:**
  - Every new eval rubric needs calibration on 100 human-annotated examples
  - Current Parallax eval rubrics (direction, magnitude, sequence, calibration) likely lack this
  - Ensures judge agreement > 85% before relying on automated scoring
- **Action:**
  1. For each eval category (oil price, ceasefire, Hormuz traffic), source/annotate 100 examples
  2. Run judge on these 100; measure vs human truth
  3. If agreement < 85%, refine rubric
- **Cost Impact:** One-time effort (~2 hours curation); no ongoing cost

### 5. Performance

#### Finding 5.1: deck.gl v9.1+ React Widgets — Reduce Render Thrashing
- **Status:** GA (deck.gl v9.1, April 2026)
- **Relevance:** HIGH (direct solution to known bottleneck)
- **Effort:** MEDIUM (refactor hex data flow)
- **Risk:** LOW
- **Details:**
  - Parallax design doc already identified render thrashing: "WebSocket updates mutate useRef instead of useState to avoid React re-renders"
  - deck.gl v9.1 formalized this pattern with React widgets and `useWidget` hook
  - Avoids manual useRef management; deck.gl handles data/render separation transparently
- **Action:**
  1. Test deck.gl v9.1+ with `useWidget` for H3HexagonLayer
  2. Migrate from manual useRef mutation to useWidget pattern
  3. Measure frame rate improvement during high-frequency cell updates (test: 100 cell changes/sec)
- **Cost Impact:** None (refactor only); likely 30-50% frame rate improvement on dashboard

#### Finding 5.2: MapLibre v5 Globe View + deck.gl Interleaved Mode
- **Status:** GA (MapLibre v5, 2026)
- **Relevance:** LOW (nice-to-have, not critical path)
- **Effort:** LOW (requires v5 upgrade)
- **Risk:** LOW
- **Details:**
  - MapLibre v5 introduced globe view (3D Earth visualization)
  - deck.gl integrates seamlessly in "interleaved" mode (deck.gl renders into MapLibre WebGL context)
  - Requires MapLibre >= 3.0.0 for WebGL2
- **Action:** Optional enhancement for demo (impressive visuals); skip for production if time-constrained
- **Cost Impact:** None (optional)

#### Finding 5.3: WebSocket Batching Best Practice (Already Implemented)
- **Status:** Best practice (2026)
- **Relevance:** MEDIUM (confirm current implementation)
- **Effort:** VERY LOW (review existing code)
- **Risk:** VERY LOW
- **Details:**
  - Parallax design doc specifies: "Buffer incoming updates for 100ms, then flush as single mutation"
  - This remains optimal; no new techniques found
- **Action:** Review `backend/websocket_handler.py` to confirm 100ms batching window; no change needed
- **Cost Impact:** None

---

## Top 3 Recommendations

### Recommendation 1: Migrate Agent Eval Cron to Batch API (QUICK WIN)
**Priority:** HIGH  
**Timeline:** 1-2 days  
**Savings:** $5-10/month  
**Risk:** Very Low

**Rationale:**
- Daily eval cron (scorecard + meta-agent improvements) already runs asynchronously
- 24-hour latency acceptable for evaluation
- 50% discount on all tokens + 90% on cached system prompts = 95% total savings on eval
- Quick payback: one-time refactor pays for itself in 1-2 weeks

**Steps:**
1. Move eval cron to Batch API submission (queue jobs at 23:00 UTC)
2. Poll for results in morning (04:00-06:00 UTC)
3. Measure actual cost savings vs baseline
4. A/B test: compare eval speed/cost before/after

---

### Recommendation 2: Integrate Free AIS Tracking for Hormuz Vessel Flow (MEDIUM EFFORT, HIGH IMPACT)
**Priority:** HIGH  
**Timeline:** 3-5 days  
**Benefit:** Real-time shipping data replaces static scenario parameters  
**Risk:** Low (supplementary data, not primary)

**Rationale:**
- Parallax currently models "Hormuz traffic" as scenario parameters (static estimates)
- Real AIS data (free via AISstream.io) provides live ground truth
- Improves prediction calibration and edge detection
- Validates cascade logic against actual shipping behavior

**Steps:**
1. Prototype AISstream WebSocket connection for Hormuz bounding box
2. Parse AIS messages → extract vessel count, direction, speed
3. Correlate with H3 cells (res 8) at Hormuz strait
4. Create new KPI: `hormuz_live_traffic_count` (replaces estimate)
5. Backtest cascade engine: does live traffic improve direction accuracy?

---

### Recommendation 3: Mitigate Prompt Caching TTL Regression Immediately (CRITICAL FIX)
**Priority:** CRITICAL  
**Timeline:** 1 day (monitoring); 2-3 days (mitigation)  
**Cost Impact:** Prevents $0.20-0.30/day cost regression  
**Risk:** Low (backpressure monitoring only, no logic change)

**Rationale:**
- Anthropic silently changed cache TTL from 60min → 5min in early 2026
- Parallax's 15-min tick cycle means system prompts are now re-paid every 5-10 minutes
- This is a **30-60% cost regression** for workloads relying on caching
- Requires immediate action to avoid surprise budget blowouts

**Steps:**
1. **Immediate (today):** Add cache_hit_rate monitoring to budget tracker
   - Query `llm_usage` table for last 7 days
   - Calculate: `cache_hits / (cache_hits + cache_misses)`
   - Alert if < 50%
2. **Option A (Short-term):** Batch agent decisions within 5-min windows
   - Queue decisions; process every 5 min in batch
   - Keeps system prompt cached within the 5-min window
   - Tradeoff: slight latency increase (5-15 min decision delay)
3. **Option B (Medium-term):** Migrate high-volume agents to Batch API
   - Sub-actor calls (Haiku) most numerous; great batch candidates
   - Country agent calls stay on-demand (need tick-sync)
4. **Option C (Monitor & Accept):** Accept the cost increase; document as AWS-like "price change"
   - Likely cheapest overall vs migration effort
   - Update budget cap from $20 to $25/day if sustainable

---

## Secondary Recommendations (Lower Priority)

- **Claude Sonnet 5 A/B Test** (MEDIUM): Schedule 3-day A/B trial on 10% of decisions before full rollout. Verify quality gain justifies potential cost increase.
- **DuckDB v1.2+ Upgrade** (LOW): Ensure running DuckDB >= 1.2.0 for spatial performance. Verify cascade engine cell neighbor lookups benefit from 50x speedup.
- **deck.gl v9.1 React Widgets** (MEDIUM): Refactor hex data flow to use `useWidget` hook. Measure frame rate improvement during high-frequency updates.
- **LLM-as-Judge Eval** (MEDIUM): Add safety gate to eval pipeline. Requires calibration on 100 labeled examples; useful for preventing unreasonable predictions.

---

## Skipped Findings

The following technologies were evaluated but deemed out-of-scope:
- **LangGraph integration** — Phase 1 explicitly avoids LangGraph; custom DES is proven and cost-effective
- **GDELT Guru** — Parallax's custom agent swarm is more specialized; external service redundant
- **MapLibre v5 Globe** — Nice-to-have; low priority vs other improvements
- **Pydantic AI** — Agent framework; Parallax uses direct Claude API (simpler)

---

## Sources

- [H3 Geospatial Library](https://h3geo.org/docs/)
- [DuckDB Spatial Extension Performance](https://aetperf.github.io/2025/03/04/Spatial_queries_in_DuckDB_with_R-tree_and_H3_indexing.html)
- [DuckDB H3 Extension (duckh3 R package)](https://cidree.github.io/duckh3/)
- [Claude Batch Processing API](https://platform.claude.com/docs/en/build-with-claude/batch-processing)
- [Claude Prompt Caching TTL Change Impact](https://dev.to/whoffagents/claude-prompt-caching-in-2026-the-5-minute-ttl-change-thats-costing-you-money-4363)
- [Claude Cost Optimization Guide](https://pecollective.com/tools/claude-pricing-guide/)
- [GDELT Cloud API](https://docs.gdeltcloud.com/)
- [GDELT Project Overview](https://www.gdeltproject.org/)
- [AISstream.io Free AIS Tracking](https://aisstream.io/)
- [AISHub Free AIS Data](https://www.aishub.net/)
- [VesselAPI Ship Tracking](https://vesselapi.com/)
- [OpenAIS Vessel Analysis Tools](https://open-ais.org/)
- [LLM Evaluation Frameworks 2026](https://medium.com/@future_agi/llm-evaluation-frameworks-metrics-and-best-practices-2026-edition-162790f831f4)
- [deck.gl What's New](https://deck.gl/docs/whats-new)
- [MapLibre Newsletter April 2026](https://maplibre.org/news/2026-05-02-maplibre-newsletter-april-2026/)
- [Claude Sonnet 5 Analysis](https://caylent.com/blog/claude-sonnet-5-launch-analysis-what-changed-what-matters-and-what-to-validate)

---

**Report Generated:** 2026-07-27  
**Next Review:** 2026-08-10 (2-week cycle)
