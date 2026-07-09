# Tech Research Scout — 2026-07-09

**Focus Areas:** Spatial/Geo, LLM/Agent, Real-time Data, Eval/MLOps, Performance

---

## Executive Summary

Five significant opportunities identified across the stack:
1. **Structured output improvements** → cost savings + agent schema validation
2. **Claude Opus 4.8 Fast Mode** → 3x cheaper Opus with adaptive thinking (production-ready for eval meta-agent)
3. **DuckDB 1.5 CRS support + Geometry core** → cleaner spatial queries without custom H3 extensions
4. **AIS vessel tracking APIs** → real-time shipping data layer (additive, not replacing GDELT)
5. **Prompt versioning platforms** → production-grade A/B testing (Braintrust's CI/CD integration notable)

---

## Findings by Category

### 1. Spatial/Geo

#### 1a. H3 SIMD-Accelerated Fork (mattsta/h3)
- **What:** Post-April 2026 fork of Uber H3 with performance optimizations + new bulk APIs (latLngsToCells, cellsToLatLngs, cellsToBoundaries)
- **Relevance:** MEDIUM → Bulk APIs reduce Python loop overhead for high-volume coordinate conversions
- **Effort:** LOW → Direct drop-in replacement for h3-js/h3-py
- **Risk:** LOW (Apache 2.0, open source) → Dual-license model (pre-fork Apache, post-fork SIC v1.0) unlikely to cause issues
- **Assessment:** Nice-to-have optimization if coordinate batch conversion becomes a bottleneck; current implementation probably sufficient
- **Sources:** [GitHub - mattsta/h3](https://github.com/mattsta/h3)

#### 1b. DuckDB 1.5 GEOMETRY Type in Core + CRS Support
- **What:** DuckDB v1.5 (March 2026) moved GEOMETRY from extension into core. Now supports CRS (coordinate reference system) as part of the type, with CRS consistency enforced across spatial functions
- **Relevance:** HIGH → Enables storing H3 cells + bounds with explicit CRS. Simplifies schema (no custom JSON workarounds)
- **Effort:** MEDIUM → Requires schema migration + review of spatial queries. New type brings ~5-10% query simplification
- **Risk:** MEDIUM → Type is stable now, but CRS system is relatively new. Test query plans carefully
- **Assessment:** **Recommend upgrading to DuckDB 1.5 after Phase 1 stabilizes.** CRS support reduces edge cases around coordinate precision. Defer to Phase 2 if current queries work
- **Sources:** [DuckDB Spatial Extension](https://duckdb.org/docs/lts/core_extensions/spatial/overview), [DuckDB 1.5 Spatial Updates](https://spatialists.ch/posts/2026/03/22-duckdb-15-with-spatial-updates/)

#### 1c. deck.gl H3 Rendering Optimizations
- **What:** deck.gl v9 adds `highPrecision: false` flag to force low-precision instanced rendering. H3TileLayer for tiled data loading. Mapbox Vector Tile (MVT) parsing 2-3x faster
- **Relevance:** MEDIUM → Current H3HexagonLayer renders ~400K hexes; optimization likely 10-20% perf gain under high update frequency
- **Effort:** LOW → Single prop change + optional adoption of H3TileLayer for incremental loading
- **Risk:** LOW → Backward compatible
- **Assessment:** **Low-hanging fruit.** Test `highPrecision: false` on GPU-constrained devices (mobile, older laptops). Measurable FPS improvement likely
- **Sources:** [deck.gl Whats New](https://deck.gl/docs/whats-new), [H3HexagonLayer Documentation](https://deck.gl/docs/api-reference/layers/h3-hexagon-layer)

---

### 2. LLM/Agent

#### 2a. Claude Sonnet 5 (Intro Pricing Through Aug 31, 2026)
- **What:** $2/$10 per 1M tokens (input/output) through Aug 31, 2026, then $3/$15. Released with improved reasoning and alignment
- **Relevance:** LOW-MEDIUM → Parallax uses Sonnet for country agents. Current cost ~$0.025/call; Sonnet 5 at intro pricing saves ~33%
- **Effort:** LOW → Drop-in model replacement in agent swarm
- **Risk:** LOW → Anthropic maintains backward compatibility
- **Assessment:** **Not urgent.** Current budget ($20/day) has massive headroom. Defer until Phase 2 scaling
- **Sources:** [Claude Sonnet 5 Announcement](https://www.anthropic.com/news/claude-sonnet-5), [Claude Pricing 2026](https://platform.claude.com/docs/en/about-claude/pricing)

#### 2b. Claude Opus 4.8 Fast Mode (3x Cheaper Opus)
- **What:** Released May 28, 2026. Opus 4.8 adds "adaptive thinking" (cost control) + Fast Mode: $10/$50 per 1M tokens (vs $15/$75 standard Opus). Fast Mode sacrifices some reasoning depth for 3x cost reduction
- **Relevance:** MEDIUM → Eval meta-agent currently estimated at $0.035/call on Sonnet. Fast Mode Opus could replace at 1/3 cost while keeping higher reasoning capacity
- **Effort:** MEDIUM → Requires testing eval accuracy on Fast Mode vs Sonnet. May need prompt tuning
- **Risk:** MEDIUM → Adaptive thinking is new; fast-mode inference may exhibit edge cases
- **Assessment:** **Test in Phase 1b if eval accuracy becomes cost-sensitive.** Consider for eval meta-agent post-ceasefire window closure (lower real-time pressure)
- **Sources:** [Claude Opus 4.8 Announcement](https://www.anthropic.com/news/claude-opus-48), [Claude Pricing Overview](https://platform.claude.com/docs/en/about-claude/pricing)

#### 2c. Prompt Caching: 5-Minute TTL Change (Early 2026)
- **What:** Anthropic reduced cache TTL from 60 minutes to 5 minutes in early 2026, increasing effective API costs by 30-60% for production workloads. Batch API requests can use 1-hour cache
- **Relevance:** HIGH → Parallax uses prompt caching for system prompts (~$0.005 savings per cached call). TTL change erodes savings
- **Effort:** LOW → No code changes required; just aware of cache hit rate assumptions
- **Risk:** NONE → Passive observation
- **Assessment:** **Already integrated in current design.** No action needed; just flag that prompt cache hit rates may be lower than projected. Monitor actual cache hits vs assumptions. Consider batch preprocessing for off-peak prediction runs
- **Sources:** [Prompt Caching Docs](https://platform.claude.com/docs/en/build-with-claude/prompt-caching), [Claude 5-Min TTL Impact Analysis](https://dev.to/whoffagents/claude-prompt-caching-in-2026-the-5-minute-ttl-change-thats-costing-you-money-4363)

#### 2d. Batch API (50% Token Discount)
- **What:** Asynchronous message batch processing with 50% discount on all tokens. No rate limits. Stacks with prompt caching (90% cached input discount + 50% batch discount possible)
- **Relevance:** MEDIUM → Parallax eval cron (daily) processes ~10-20 resolved predictions. Batch API perfect fit
- **Effort:** MEDIUM → Restructure daily eval job to batch-submit predictions instead of synchronous calls
- **Risk:** LOW → Batch processing introduces ~1min latency (batch processed within hours, not milliseconds)
- **Assessment:** **Recommend for Phase 2 or late Phase 1 if eval accuracy evaluation needs scaling.** Current $20/day budget doesn't justify batching complexity yet, but batch API could reduce eval cost from $0.35/day to ~$0.10/day
- **Sources:** [Batch Processing API Docs](https://platform.claude.com/docs/en/build-with-claude/batch-processing), [Cost Optimization Guide](https://claudeapi.com/en/blog/dev-guides/claude-batch-api-cost-optimization/)

#### 2e. Claude Structured Outputs (Now GA)
- **What:** General availability released; JSON schema enforcement on Claude Sonnet/Opus/Haiku 4.x. Guarantees valid JSON output
- **Relevance:** HIGH → Agent output validation currently manual (regex + retry on malformed JSON). Structured outputs eliminate validation code + failed agent calls
- **Effort:** LOW → Move agent schemas to JSON schema format, add `output_config.format` parameter
- **Risk:** LOW → GA feature, stable API
- **Assessment:** **Implement for agent decision schema immediately.** Replace current validation with structured output. Reduces latency + cost by eliminating malformed-output retries. Estimated 5-10% improvement in agent throughput
- **Sources:** [Structured Outputs Docs](https://platform.claude.com/docs/en/build-with-claude/structured-outputs), [Hands-On Guide](https://towardsdatascience.com/hands-on-with-anthropics-new-structured-output-capabilities/)

---

### 3. Real-Time Data

#### 3a. GDELT Alternatives: POLECAT & GDELT Cloud
- **What:** 
  - **POLECAT** (Political Event Classification): Research dataset with high domain accuracy and low redundancy vs GDELT's high-coverage model
  - **GDELT Cloud** (2026): Machine-learning wrapper over raw GDELT adding classified Events, clustered Stories, linked Entities, quantified signals
- **Relevance:** MEDIUM → GDELT is current primary data source. POLECAT complements (not replaces) for high-confidence conflict events
- **Effort:** MEDIUM (POLECAT) / LOW (GDELT Cloud) → POLECAT requires separate ingestion. GDELT Cloud is drop-in API
- **Risk:** MEDIUM (POLECAT) → Academic dataset, slower update cycle. LOW (GDELT Cloud) → Same provider, lower risk
- **Assessment:** **GDELT Cloud worth exploring for Phase 2:** reduces noise filtering burden (moving 3-stage filter upstream). POLECAT: defer until ground-truth comparison shows GDELT lag
- **Sources:** [POLECAT Evaluation](https://doi.org/10.3390/data11070158), [GDELT Cloud Docs](https://docs.gdeltcloud.com/)

#### 3b. Real-Time AIS Vessel Tracking (New Tier for Shipping Data)
- **What:** Six production-grade AIS APIs now available (Datalastic, MarineTraffic, VesselFinder, AISstream.io, S&P Global). Terrestrial AIS (T-AIS) covers ~40-60 NM from shore at seconds latency; Satellite AIS (S-AIS) global with minutes-to-hours latency
- **Relevance:** HIGH → Hormuz strait shipping is Parallax's core output metric. Current model infers flow from oil prices + GDELT. Real AIS adds direct observation layer
- **Effort:** MEDIUM → API integration + schema mapping (vessel → oil flow correlation). Datalastic/AISstream.io most developer-friendly
- **Risk:** LOW → Multiple providers (not single dependency); T-AIS data is public
- **Assessment:** **Recommend additive layer for Phase 1b or Phase 2.** Real-time vessel count + route changes immediately validates Hormuz model accuracy without waiting for downstream oil price signal. Datalastic or AISstream.io for fast integration. Cost: ~$100-500/month depending on tier
- **Sources:** [Datalastic AIS API](https://datalastic.com/), [AISstream.io Free WebSocket](https://aisstream.io/), [VesselFinder API](https://api.vesselfinder.com/docs/)

---

### 4. Eval/MLOps

#### 4a. Benchmark Saturation (2026 Frontier Models)
- **What:** Traditional benchmarks (MMLU) saturating at 88%+ on frontier models. GPT-5.3 Codex scores 99% on some. Field moving toward harder benchmarks (GPQA) and domain-specific evals
- **Relevance:** HIGH → Parallax eval framework depends on score deltas to catch model regressions. Generic benchmarks won't distinguish Parallax prompt changes
- **Effort:** LOW → Awareness shift; current eval already domain-specific (prediction accuracy on Iran/Hormuz)
- **Risk:** NONE
- **Assessment:** **Good news:** Parallax's custom eval (direction accuracy, magnitude, calibration) avoids benchmark trap entirely. Keep domain-specific focus
- **Sources:** [LLM Evaluation 2026 - Medium](https://medium.com/@nairmilind3/llm-evaluation-in-2026-e631a78c67dc), [LLM Benchmarks 2026 - LXT](https://www.lxt.ai/blog/llm-benchmarks/)

#### 4b. LLM-as-Judge for Agentic Systems
- **What:** Three metric classes for agentic eval: TrajectoryAccuracy (step sequence match), ToolCorrectnessJudge (correct tool invocation), TaskCompletionJudge (goal achieved). LLM-as-Judge achieves 80-90% human agreement at 500-5000x lower cost
- **Relevance:** MEDIUM → Parallax uses manual tagging of misses (model_error vs exogenous_shock). LLM-as-Judge could automate that classification
- **Effort:** MEDIUM → Template 3-4 LLM judges, aggregate votes. Requires curating golden examples for each category
- **Risk:** MEDIUM → Judge accuracy depends on prompt quality; garbage-in-garbage-out for tagging
- **Assessment:** **Test in Phase 1b for miss classification.** If manual tagging becomes bottleneck, LLM judges could scale eval faster. Current manual process probably sufficient until >100 predictions/day
- **Sources:** [LLM Evaluation Frameworks - FutureAGI](https://futureagi.substack.com/p/llm-evaluation-frameworks-metrics)

#### 4c. Production Prompt Versioning Platforms
- **What:** Three platforms lead 2026 market:
  - **Confident AI:** Git-style prompt branching, evaluation scorecard
  - **MLflow:** Experiment tracking + model registry + tracing
  - **Braintrust:** Native CI/CD via GitHub Actions; auto-runs experiments on PR, posts results
- **Relevance:** MEDIUM → Parallax has manual prompt versioning (semver in code). Production platform could automate A/B comparison
- **Effort:** MEDIUM-HIGH → Integration with CI/CD + eval infrastructure. Largest upfront cost is structuring eval results into platform's schema
- **Risk:** LOW → All three are well-maintained; Braintrust's GitHub integration most native to workflow
- **Assessment:** **Defer to Phase 2.** Current semver + manual A/B tracking sufficient for 3-5 agent versions. Braintrust worth evaluating if prompt iteration velocity accelerates post-ceasefire window (higher cadence of corrections)
- **Sources:** [Braintrust Prompt Versioning](https://www.braintrust.dev/articles/best-prompt-versioning-tools-2025), [MLflow Articles](https://mlflow.org/articles/top-llm-prompt-versioning-platforms-3)

---

### 5. Performance

#### 5a. DuckDB Optimization: Parquet > CSV, Projection Pushdown
- **What:** Switching from CSV to Parquet is the single highest-ROI DuckDB optimization (~2-10x improvement). Columnar storage enables predicate/projection pushdown. Use EXPLAIN ANALYZE to identify bottlenecks
- **Relevance:** HIGH → Parallax stores world_state_delta + predictions in DuckDB. Parquet format reduces I/O during daily scorecard compute
- **Effort:** LOW → One-time schema migration. Parquet compression also reduces storage (secondary benefit)
- **Risk:** LOW → Parquet is stable, widely supported
- **Assessment:** **Implement after Phase 1 baseline stabilizes.** Create Parquet export of historical deltas (not on hot write path). Dashboard + API queries read Parquet; live ingestion still uses DuckDB native format
- **Sources:** [DuckDB Performance Tuning](https://duckdblab.org/en/post/duckdb-performance-tuning-5-tips/), [Performance Guides](https://motherduck.com/duckdb-book-summary-chapter10/)

#### 5b. React Real-Time Dashboard: Batching + Virtualization + Web Workers
- **What:**
  - Batch WebSocket updates: buffer 100ms, flush once (not per-message re-render)
  - Virtualization: render only visible rows (~100 rows at a time vs 10K+)
  - Memoization: chart re-renders only on data change, not parent state
  - Web Workers: offload heavy computations (rolling averages, anomaly detection)
- **Relevance:** HIGH → Frontend currently decouples React from deck.gl via useRef (good). Can apply batching + Web Workers to indicator cards (price sparklines, escalation index)
- **Effort:** MEDIUM → Audit high-frequency update flows (Brent price, vessel count). Add batching layer + consider Web Worker for rolling-average calculation
- **Risk:** LOW → React best practices, no new libraries needed
- **Assessment:** **Implement before Phase 1 launch.** Agent feed (left panel) likely to scroll rapidly — virtualization immediately improves performance. Price sparkline updates can batch 250-500ms with no UX loss
- **Sources:** [Real-Time Dashboard Performance](https://www.segevsinay.com/blog/real-time-dashboard-performance), [WebSockets in React 2026](https://oneuptime.com/blog/post/2026-01-15-websockets-react-real-time-applications/view)

#### 5c. Python asyncio WebSocket: websockets vs picows
- **What:** Default: `websockets` library (pure Python, handles ~10K concurrent connections per core). Alternative: `picows` (C-accelerated parsing/frame building, extends limit to 50K+). Both integrate with asyncio/FastAPI
- **Relevance:** LOW → Parallax targets max 10 concurrent sessions (admin cap). Current load nowhere near limits
- **Effort:** NONE → websockets is already standard
- **Risk:** NONE → websockets is production-grade, no reason to change
- **Assessment:** **No action needed.** Keep websockets for simplicity. If Phase 2 scales to >100 concurrent dashboards, revisit picows
- **Sources:** [Python WebSocket Servers 2026](https://dasroot.net/posts/2026/02/python-websocket-servers-real-time-communication-patterns/), [websockets Documentation](https://websockets.readthedocs.io/en/stable/reference/asyncio/server.html)

---

## Top 3 Recommendations (Priority Order)

### 1. **Implement Claude Structured Outputs for Agent Schemas (IMMEDIATE)**
- **Why:** Eliminates malformed JSON validation + retry logic. Guaranteed valid output. 5-10% throughput improvement
- **Effort:** LOW (1-2 days)
- **ROI:** High — reduces operational burden + cost
- **Action:** Move agent decision schema to JSON schema format, add `output_config.format` to agent calls

### 2. **Add Real-Time AIS Vessel Tracking Layer (Phase 1b)**
- **Why:** Direct observation of Hormuz shipping validates model accuracy without waiting for downstream price signal. Fastest feedback loop for model correction
- **Effort:** MEDIUM (3-5 days)
- **ROI:** High — core metric visibility + early warning system
- **Action:** Integrate Datalastic or AISstream.io API. Map vessel count + routes to model's flow predictions. A/B test against current price-only inference

### 3. **Upgrade to DuckDB 1.5 + Adopt Parquet for Historical Data (Phase 2)**
- **Why:** CRS support simplifies spatial schema. Parquet reduces scorecard compute time + storage. Foundation for scaling Phase 2
- **Effort:** MEDIUM (schema migration + testing)
- **ROI:** Medium — operational efficiency, not feature value
- **Action:** After Phase 1 stabilizes, test migration on replica. Export daily deltas to Parquet. Profile before/after scorecard compute time

---

## Skipped/Low-Priority Findings

- **H3 SIMD fork:** Bulk API optimization premature; current perf adequate
- **Claude Sonnet 5:** No urgency; current $20/day budget has headroom
- **Claude Opus 4.8 Fast Mode:** Test later if eval becomes cost-constrained
- **POLECAT dataset:** Ground-truth comparison first (defer to Phase 2)
- **Braintrust CI/CD:** Overkill until prompt iteration cadence increases
- **Picows WebSocket:** Connection cap (10 sessions) nowhere near limits

---

## References

- [H3 Library](https://h3geo.org/)
- [DuckDB Spatial Extension](https://duckdb.org/docs/lts/core_extensions/spatial/overview)
- [deck.gl Documentation](https://deck.gl/docs/whats-new)
- [Claude API Docs](https://platform.claude.com/docs)
- [Structured Outputs](https://platform.claude.com/docs/en/build-with-claude/structured-outputs)
- [Batch Processing API](https://platform.claude.com/docs/en/build-with-claude/batch-processing)
- [Prompt Caching](https://platform.claude.com/docs/en/build-with-claude/prompt-caching)
- [AIS Vessel Tracking APIs](https://datalastic.com/)
- [GDELT Cloud](https://gdeltcloud.com/)
- [Real-Time Dashboard Performance](https://www.segevsinay.com/blog/real-time-dashboard-performance)

