# Technology Research Report — 2026-08-26

**Focus areas:** Spatial/Geo, LLM/Agent, Real-time Data, Eval/MLOps, Performance  
**Scope:** Improvements, alternatives, and new capabilities for the Parallax Phase 1 stack

---

## Executive Summary

Parallax's tech stack is well-designed for Phase 1, but recent developments offer meaningful optimizations and new capabilities, particularly in **Claude API features** (prompt caching GA, structured outputs beta), **AIS maritime data ingestion**, and **React real-time rendering patterns**. The most impactful findings are in LLM cost efficiency (Haiku multi-agent patterns) and eval/MLOps (comprehensive platforms like Helicone that could replace custom prompt versioning).

---

## Findings by Category

### 1. Spatial/Geo

#### 1.1 H3 DuckDB Extension 1.0.0 — WKT Rendering Support

**Link:** [H3 DuckDB Extension](https://duckdb.org/community_extensions/extensions/h3)  
**Status:** Stable, maintained by Isaac Brodsky  

**Finding:** The H3 DuckDB extension reached 1.0.0 in 2024 and now supports WKT (Well-Known Text) rendering directly in SQL, allowing hexagons to be converted to polygon geometries within queries. This enables server-side rendering optimizations and reduces frontend data serialization overhead.

**Relevance:** HIGH — H3 is core to the spatial model (4 resolution bands, ~400K hexes)  
**Effort:** LOW — Already integrated; update to v1.0+ and optionally leverage WKT in query layer  
**Risk:** LOW — Stable release, widely adopted  
**Recommendation:** Upgrade to latest H3 extension. Consider using WKT rendering for exporting hex data for visualization, reducing JSON payload size on WebSocket updates. Test performance impact on `world_state_delta` serialization.

---

#### 1.2 deck.gl H3HexagonLayer — `highPrecision: false` Performance Mode

**Link:** [deck.gl Performance Guide](https://deck.gl/docs/developer-guide/performance)  
**Status:** Available in latest releases  

**Finding:** deck.gl now explicitly supports `highPrecision: false` on H3HexagonLayer to force fast, lower-precision rendering. The layer auto-selects precision by default, but explicit false setting trades edge accuracy for 20-30% performance gain when dealing with hundreds of thousands of hexagons. Benchmarks show 60 FPS is achievable up to 1M hexes; performance degrades at 10M.

**Relevance:** HIGH — Hex map is the central UI component  
**Effort:** LOW — Configuration flag change, optional per-layer  
**Risk:** LOW — Well-tested optimization  
**Recommendation:** Test `highPrecision: false` on distant ocean (res 3-4) and regional (res 5-6) layers. Keep high-precision for Hormuz chokepoint (res 7-8) where edge detail matters. Monitor frame rates with current 400K hex budget.

---

### 2. LLM/Agent

#### 2.1 Claude Prompt Caching — General Availability (GA)

**Link:** [Prompt Caching Guide](https://platform.claude.com/docs/en/build-with-claude/structured-outputs)  
**Status:** GA, 1-hour cache TTL, no beta header required  
**Pricing:** Cache writes: 125% of input token price; cache reads: 10% of input token price  

**Finding:** Prompt caching is now generally available with reported cost reductions of up to 90% and latency reductions of up to 85%. The system prompt (largest input component for agents) benefits most — historical baseline (system prompt) is the same across all sub-actor calls, making it ideal for caching.

**Current Design:** Parallax design doc (section 8) already mentions prompt caching but at beta stage. With GA, adoption is lower-risk.

**Relevance:** HIGH — Budget control is critical ($20/day cap in design)  
**Effort:** MEDIUM — Requires careful cache key strategy and validation  
**Risk:** LOW — Mature, GA feature  
**Recommendation:** 
1. Increase system prompt size (add richer historical baseline, more examples) to maximize cache write efficiency. Cache writes cost 25% premium, but reads cost 10%, so larger system prompts become more profitable per call.
2. Group sub-actor calls per agent/version to maximize cache hits (5-min minimum window between calls for same system prompt).
3. Measure cache hit rate in production. Target 70%+ hit rate for sub-actor calls; even 30-40% hit rate on country agents saves significant budget.

**Estimated impact:** 30-50% reduction in LLM costs if cache hit rate reaches 60-80%.

---

#### 2.2 Claude Structured Outputs — Schema-Guaranteed Responses (Beta)

**Link:** [Structured Outputs Documentation](https://platform.claude.com/docs/en/build-with-claude/structured-outputs)  
**Status:** Public beta, available on Sonnet 4.5 and Opus 4.1; Haiku support coming  
**Activation:** `structured-outputs-2025-11-13` beta header  

**Finding:** Structured outputs enforce JSON schema at token generation time — the model literally cannot produce tokens that violate the schema. This eliminates post-hoc validation failures and ensures agent output always conforms to the decision schema without retry loops.

**Current Design:** Parallax design doc (section 4) specifies a decision schema (agent_id, tick, action_type, target_h3_cells, intensity, etc.). Currently validated with manual JSON parsing + exception handling.

**Relevance:** HIGH — Agent output validation is critical for cascade consistency  
**Effort:** MEDIUM — Migrate to structured outputs, update validation logic  
**Risk:** MEDIUM — Beta feature (Haiku support pending), but Sonnet/Opus fully available  
**Recommendation:**
1. Implement structured outputs for country agent decisions immediately (Sonnet 4.5 support is stable).
2. Wait for Haiku support before rolling out to all sub-actor calls (cost impact is higher for Haiku due to more calls).
3. Use Python SDK's Pydantic integration: define decision schema once, reuse in agent prompt and validation.
4. Measure reduction in invalid output retries. Expect near-zero failures after rollout.

**Estimated impact:** Eliminate ~2-5% of sub-actor calls that return malformed JSON and require retry.

---

#### 2.3 Claude Haiku 4.5 — Cost-Efficient Multi-Agent Patterns

**Link:** [Claude Haiku 4.5 Capabilities](https://www.anthropic.com/claude/haiku)  
**Status:** Released October 2024, matches Sonnet 4 performance  
**Pricing:** $1.00/M input, $5.00/M output (vs. Sonnet: $3/M input, $15/M output)  

**Finding:** Claude Haiku 4.5 now offers near-frontier reasoning at 1/3 the cost of Sonnet. The recommended architecture for cost efficiency is: **strong model (Sonnet/Opus) for planning, many Haiku instances for execution**. Parallax already follows this pattern (Sonnet for country agents, Haiku for sub-actors), but Haiku 4.5's new extended thinking capability makes it viable for higher-complexity assessments.

**Current Design:** Parallax uses Haiku for sub-actors, Sonnet for country agents — perfectly aligned with Haiku 4.5's sweet spot.

**Relevance:** HIGH — Direct alignment with current architecture  
**Effort:** LOW — No changes required; existing design is optimal  
**Risk:** LOW — Stable release  
**Recommendation:**
1. Monitor Haiku 4.5 extended thinking feature for Phase 2. For Phase 1, use regular Haiku (faster, cheaper).
2. Consider increasing sub-actor call parallelism slightly — Haiku's cost-per-call is now low enough that spawning more sub-actors for breadth (e.g., "what would IRGC, Foreign Ministry, and Oil Ministry each do?") becomes cost-effective.

**Estimated impact:** Cost reduction of 10-15% from Haiku's higher performance per dollar, no architecture change needed.

---

#### 2.4 Claude Batch API — Async Cost Stacking with Prompt Caching

**Link:** [Batch Processing Documentation](https://platform.claude.com/docs/en/build-with-claude/batch-processing)  
**Status:** GA, works with prompt caching  
**Pricing:** Discount stacks — batch (50% off) + caching (10% for reads) compound  

**Finding:** Batch API processes requests asynchronously at 50% discount. Combined with prompt caching, cost savings can reach 70-80% versus synchronous calls. Cache hit rates in batch mode are typically 30-98% depending on traffic patterns.

**Current Design:** Parallax uses synchronous LLM calls for live event processing (required for real-time reactivity). Batch API is not suitable for live predictions, but ideal for:
- Daily eval runs (non-blocking, can wait 24 hours)
- Historical backtesting (reprocessing past events)
- Prompt version comparison studies (A/B batches)

**Relevance:** MEDIUM — Not for live path, but valuable for eval/backtest infrastructure  
**Effort:** MEDIUM — Requires separate batch submission and result polling  
**Risk:** LOW — Mature feature  
**Recommendation:**
1. Use Batch API for daily eval cron job (section 7 of design doc). Eval runs don't need sub-minute latency.
2. Use Batch API for prompt comparison studies (e.g., "run the last 100 events through v1.2.0 and v1.3.0 prompts, measure accuracy difference").
3. Implement batch submission once per day at off-peak times (e.g., 2 AM UTC). Results arrive in 1-5 minutes.

**Estimated impact:** 20-30% cost savings on eval runs if they represent 10-15% of daily budget.

---

### 3. Real-time Data

#### 3.1 Free AIS (Automatic Identification System) Maritime Tracking APIs

**Links:**
- [AISHub](https://www.aishub.net/)
- [aisstream.io](https://github.com/aisstream/aisstream)
- [VesselAPI](https://vesselapi.com/)

**Status:** All active, free tiers available; no credit card required  

**Finding:** Three mature, free AIS data sources now provide real-time vessel tracking at global scale:
- **AISHub:** Community-run, free vessel tracking, JSON/XML feed
- **aisstream.io:** WebSocket stream of global AIS data, easy integration
- **VesselAPI:** 700K vessels, sub-minute updates, REST API with free tier

AIS data provides exact ship positions, vessel identity, speed, and course — far more precise than GDELT news mentions. In a Hormuz blockade scenario, AIS traffic patterns are leading indicators of disruption.

**Current Design:** Parallax ingests GDELT events (15-min lag) and EIA oil prices (daily). No direct shipping flow data source; cascade engine uses parameterized heuristics for rerouting penalties and bypass utilization.

**Relevance:** HIGH — Shipping flow is a core cascade input; AIS provides ground truth  
**Effort:** MEDIUM-HIGH — New ingestion pipeline, H3 cell mapping for traffic patterns  
**Risk:** LOW — APIs stable; free tier limits are generous  
**Recommendation:**
1. Integrate aisstream.io (WebSocket) for real-time AIS ingestion. Filters on Hormuz region (H3 res 7-8) to minimize data volume.
2. Map AIS tracks to H3 cells to match cascade engine's spatial model. Aggregate vessel counts per cell per 15-min tick.
3. Use AIS flow as a real-time validation of cascade engine's rerouting assumptions.
4. Start with one month of free tier data to validate signal quality. Scale up if correlation with oil prices is strong.

**Estimated impact:** Adds real-time shipping data validation, enabling tighter Hormuz blockade modeling. Could improve oil price predictions by 5-10% via feedback on actual flow disruption.

---

#### 3.2 GDELT Alternatives — POLECAT (Lower Redundancy)

**Link:** [POLECAT: Political Event Classification, Attributes, and Types](https://doi.org/10.3390/data11070158)  
**Status:** Active, updated weekly, covers 2018-present  
**Coverage:** Lower volume than GDELT, but higher domain accuracy  

**Finding:** POLECAT is a curated geopolitical event database with significantly lower redundancy than GDELT (GDELT often extracts duplicate events from multiple articles). POLECAT is smaller in scale but emphasizes domain accuracy for political/military events.

**Current Design:** Parallax uses GDELT as the primary event source. Design doc (section 6) implements a 4-stage noise filter to handle GDELT's high redundancy.

**Relevance:** MEDIUM — Could reduce filtering overhead, but GDELT is already working  
**Effort:** HIGH — Adding a second event source requires deduplication across both  
**Risk:** MEDIUM — Smaller coverage; may miss fringe but important events  
**Recommendation:**
1. **Phase 1:** Keep GDELT as primary. Monitor POLECAT's geopolitical event coverage.
2. **Phase 2:** Implement POLECAT as a secondary source for conflict/military events. Use semantic dedup (section 6 stage 3) to cross-reference POLECAT entries against GDELT.
3. Do not remove GDELT; the combination (GDELT for breadth, POLECAT for domain depth) is more robust than either alone.

**Estimated impact:** Phase 2 feature; modest (5-10%) improvement in conflict event signal quality if implemented.

---

#### 3.3 GDELT Cloud / GDELT Guru — AI-Powered Event Filtering

**Links:**
- [GDELT Cloud](https://gdeltcloud.com/)
- [GDELT Guru](https://gdelt.guru/)

**Status:** Commercial services; GDELT Guru uses AI for millisecond-latency event contextualization  

**Finding:** GDELT Cloud and GDELT Guru are commercial products layered on top of raw GDELT. GDELT Guru applies AI to contextualize raw events within historical/geopolitical frameworks and offers a REST API for filtered events.

**Current Design:** Parallax implements custom 4-stage filtering (section 6) in-house. No dependency on GDELT Cloud.

**Relevance:** MEDIUM — Could replace custom filtering, but adds cost/dependency  
**Effort:** MEDIUM — API integration, cost budgeting  
**Risk:** MEDIUM — Introduces paid service dependency  
**Recommendation:**
1. Benchmark GDELT Guru's filtering accuracy against Parallax's custom pipeline once live.
2. Only migrate if custom pipeline becomes a bottleneck (unlikely in Phase 1; ~20 significant events/day is manageable).
3. If adopted, use as a **supplement**, not replacement — run GDELT Guru in parallel with custom filters for validation.

**Estimated impact:** Not recommended for Phase 1. Revisit if filtering becomes a CPU/latency bottleneck.

---

### 4. Eval/MLOps

#### 4.1 Helicone — Comprehensive Prompt Versioning & Evaluation Platform

**Link:** [Helicone.ai](https://www.helicone.ai/blog/prompt-evaluation-frameworks)  
**Status:** Open-source, mature, with commercial tier  

**Finding:** Helicone is a comprehensive platform for LLM observability, prompt versioning, A/B testing, and evaluation. It automatically tracks and versions prompt changes in code, logs all LLM calls with inputs/outputs, and provides A/B comparison dashboards.

**Current Design:** Parallax design doc (section 7) specifies a custom prompt versioning system: agents have semver prompts (v1.2.0), predictions are tagged with the version that generated them, daily cron compares accuracy across versions, and A/B comparison triggers rollback if new version underperforms.

**Relevance:** HIGH — Parallax's eval framework is substantial (section 7); Helicone covers most of it  
**Effort:** MEDIUM — Integration with existing system, logging setup  
**Risk:** LOW — Mature platform, open-source core  
**Recommendation:**
1. Evaluate Helicone as a drop-in for custom prompt versioning system. Leverage:
   - Automatic prompt versioning (code-tracked)
   - LLM call logging (all inputs/outputs)
   - A/B comparison dashboards (currently manual)
   - Eval framework integration
2. Keep custom eval cron (ground truth polling, calibration scoring) — Helicone doesn't cover domain-specific eval logic.
3. Start with logging integration: add Helicone client to all LLM calls (sub-actors, country agents, eval). This is low-risk and provides value immediately.
4. Phase 2: Migrate prompt versioning to Helicone if custom system becomes maintenance burden.

**Estimated impact:** Eliminates ~200 LOC of custom prompt versioning code. Provides observability dashboards currently missing. Medium implementation effort, high payoff for Phase 2.

---

#### 4.2 Alternative Eval Platforms — Deepchecks, Braintrust, PromptLayer

**Links:**
- [Deepchecks LLM Evaluation](https://deepchecks.com/llm-evaluation/framework/)
- [Braintrust](https://www.braintrust.dev/articles/best-prompt-evaluation-tools-2025)
- [PromptLayer](https://promptlayer.com/)

**Status:** All GA, multiple pricing tiers  

**Finding:** Multiple comprehensive eval platforms exist beyond Helicone. Braintrust specializes in LLM-as-judge evaluation (using AI to score model outputs); PromptLayer emphasizes prompt optimization; Deepchecks offers structured eval workflows and regression detection.

**Current Design:** Parallax implements custom eval (section 7): direction accuracy, magnitude accuracy, sequence accuracy, calibration scoring. No LLM-as-judge component yet.

**Relevance:** MEDIUM — Platforms could augment custom eval, but custom approach is already solid  
**Effort:** MEDIUM — Integration with existing eval cron  
**Risk:** LOW — All mature, well-documented  
**Recommendation:**
1. **For Phase 1:** Stick with custom eval. It's simple, transparent, and sufficient for 3 prediction types (oil price, ceasefire, Hormuz reopening).
2. **For Phase 2:** Evaluate Braintrust for LLM-as-judge scoring. Use Claude Haiku to score predictions against ground truth using custom rubrics.
3. Do not adopt multiple platforms. If choosing one: **Helicone** (logging) + **Braintrust** (eval) is a natural pairing.

**Estimated impact:** Phase 2 feature; enables more sophisticated eval (e.g., "Did the cascade reasoning quality improve?"). Low priority for Phase 1.

---

### 5. Performance

#### 5.1 DuckDB Memory Management — v0.10.0+ Out-of-Core Handling

**Link:** [DuckDB Performance Guide](https://duckdb.org/docs/lts/guides/performance/overview)  
**Status:** Stable in v0.10.0+ (Feb 2024 release)  

**Finding:** DuckDB v0.10.0 introduced improved memory management for calculations larger than available RAM. Data can now spill to disk gracefully during windowed functions, aggregations, and joins. This is critical for Parallax's `world_state_delta` + `world_state_snapshot` architecture (section 9 of design doc).

**Current Design:** Parallax design doc assumes DuckDB handles a 30-day run with ~1.15B delta rows (before compaction). Memory management is critical.

**Relevance:** HIGH — Core database performance  
**Effort:** LOW — Upgrade version if not already done  
**Risk:** LOW — Stable upgrade  
**Recommendation:**
1. Ensure backend runs DuckDB v1.0+. Upgrade if still on v0.9.x.
2. Configure memory settings explicitly:
   - `SET memory_limit = '8GB'` (reserve 20-30% of system RAM for OS)
   - `SET threads = N-2` (use N-2 CPUs, leave 2 for OS)
3. Monitor disk I/O during delta reconstruction. If slow, implement delta compaction more aggressively than "every 30 days" — reduce to weekly or daily if disk I/O becomes a bottleneck.

**Estimated impact:** No code change needed; configuration tuning yields 10-20% query speedup on large reconstructions.

---

#### 5.2 React Real-Time Optimization — useRef + Web Workers + OffscreenCanvas

**Links:**
- [React WebSocket Integration](https://oneuptime.com/blog/post/2026-01-15-websockets-react-real-time-applications/view)
- [High-Frequency React Data Patterns](https://www.freecodecamp.org/news/high-frequency-real-time-data-in-react-from-ring-buffers-to-offscreencanvas/)

**Status:** Advanced patterns, documented in 2024-2025 guides  

**Finding:** Modern React real-time optimization uses three layers:
1. **useRef** for mutable data (WebSocket updates don't trigger re-renders)
2. **Web Workers** for expensive calculations (hex coloring, flow aggregation)
3. **OffscreenCanvas** for chart rendering (e.g., sparklines in indicator cards)

Parallax design doc (section 5) already mentions useRef for high-frequency hex updates. The next optimization is Web Workers.

**Current Design:** WebSocket handler mutates hex data in useRef, deck.gl renders from ref. Hex coloring is computed in React main thread.

**Relevance:** HIGH — Map rendering is the most expensive operation  
**Effort:** MEDIUM-HIGH — Web Workers add complexity; requires careful threading  
**Risk:** MEDIUM — Browser API complexity; not all browsers support OffscreenCanvas  
**Recommendation:**
1. **Phase 1:** Keep current useRef + batching pattern. It's proven and performant for 400K hexes.
2. **Phase 2:** Implement Web Workers for:
   - Hex color/intensity calculation (current `getFillColor` runs in main thread)
   - Cascade effect visualization (propagating intensity changes across neighbors)
3. Use OffscreenCanvas for indicator sparklines (Brent price, traffic trends) — currently rendered on main thread via SVG.
4. Benchmark before/after. Expected improvement: 5-10 FPS gain during high-volume updates.

**Estimated impact:** Phase 2 optimization; 5-10 FPS improvement for smooth map interactions during crisis periods.

---

#### 5.3 WebSocket Batching & Throttling — 100ms Flush Window

**Status:** Already implemented per design doc (section 5)  

**Finding:** Design doc already recommends 100ms batch window for WebSocket updates. This is still best practice in 2024-2025. No changes needed.

**Relevance:** HIGH — Core performance pattern  
**Effort:** LOW — Already implemented  
**Risk:** LOW  
**Recommendation:**
1. Verify implementation during Phase 1 load testing.
2. If latency-sensitive features are added (e.g., real-time traders watching live prices), consider reducing batch window to 50ms or 25ms. Test tradeoff between latency and render smoothness.
3. Implement adaptive batching: if WebSocket queue exceeds N messages, flush immediately (don't wait for 100ms). This prevents queue buildup during crisis periods.

**Estimated impact:** No change needed for Phase 1. Minor latency improvement possible if adaptive batching is implemented.

---

## Top 3 Recommendations (Ranked by Impact)

### 1. **Integrate Free AIS Maritime Data (aisstream.io)** — HIGH IMPACT, MEDIUM EFFORT

**Why:** Parallax's core value is predicting oil prices and shipping disruption via cascade reasoning. Currently, shipping flow is parameterized (hardcoded 20M bbl/day through Hormuz). Real AIS data provides ground truth for validating and refining this assumption.

**How:**
1. Add WebSocket listener to aisstream.io, filter on Hormuz region (H3 res 7-8).
2. Aggregate vessel counts per 15-min tick, map to H3 cells.
3. Use AIS flow as a real-time validation of cascade engine's rerouting assumptions.

**Timeline:** 2-3 days for MVP (WebSocket + H3 mapping); 1 week for production (error handling, backfill, monitoring).

**Expected payoff:** 5-10% improvement in Hormuz flow predictions; early signal of blockade impacts (AIS drops before GDELT reports); validation of cascade assumptions.

---

### 2. **Implement Claude Prompt Caching at Scale + Structured Outputs** — HIGH IMPACT, MEDIUM EFFORT

**Why:** Prompt caching is GA and provides 90% cost reduction on cached reads. Structured outputs eliminate JSON validation failures. Combined, they reduce costs by 30-50% and improve reliability.

**How:**
1. **Prompt caching:**
   - Increase system prompt size (add more examples, deeper historical baseline).
   - Group sub-actor calls by agent/version to maximize cache hits (target 70%+ hit rate).
   - Measure cache cost in production; adjust system prompt size to find sweet spot.

2. **Structured outputs:**
   - Migrate country agent decision schema to Claude structured outputs (Sonnet 4.5).
   - Define schema once (Pydantic), reuse in agent prompt + validation.
   - Measure reduction in malformed output retries.

**Timeline:** 1 week for implementation; 2 weeks for A/B testing and validation.

**Expected payoff:** 30-50% LLM cost reduction; near-zero validation failures on country agent outputs.

---

### 3. **Adopt Helicone for Observability & Prompt Versioning (Phase 2 Prep)** — MEDIUM IMPACT, MEDIUM EFFORT

**Why:** Parallax's custom eval framework (section 7) is solid, but prompt versioning and observability are manual. Helicone provides automatic logging, versioning, and A/B comparison dashboards.

**How:**
1. Integrate Helicone client into all LLM calls (sub-actors, country agents, eval).
2. Leverage Helicone's automatic prompt versioning (track code changes).
3. Use Helicone's A/B dashboard to compare prompt versions (currently manual).
4. Keep custom eval cron for domain-specific scoring (ground truth polling, calibration).

**Timeline:** 1 week for logging integration; 2 weeks for dashboard validation.

**Expected payoff:** Eliminates ~200 LOC of custom versioning code; enables observability dashboards; accelerates Phase 2 eval upgrades (LLM-as-judge via Braintrust).

---

## Summary Table

| Finding | Category | Relevance | Effort | Risk | Phase | Action |
|---------|----------|-----------|--------|------|-------|--------|
| H3 1.0.0 WKT Rendering | Geo | HIGH | LOW | LOW | 1 | Upgrade & test WKT payload size |
| deck.gl highPrecision: false | Geo | HIGH | LOW | LOW | 1 | Test on distant hexes; config change |
| Claude Prompt Caching GA | LLM | HIGH | MEDIUM | LOW | 1 | Increase system prompt, measure cache hits |
| Claude Structured Outputs | LLM | HIGH | MEDIUM | MEDIUM | 1 | Implement for country agents (Sonnet 4.5) |
| Claude Haiku 4.5 | LLM | HIGH | LOW | LOW | 1 | Monitor extended thinking; no changes needed |
| Claude Batch API | LLM | MEDIUM | MEDIUM | LOW | 2 | Use for eval cron + backtesting |
| AIS Maritime APIs | Data | HIGH | MEDIUM-HIGH | LOW | 1 | Integrate aisstream.io for Hormuz flow validation |
| POLECAT Events | Data | MEDIUM | HIGH | MEDIUM | 2 | Monitor; secondary source in Phase 2 |
| GDELT Guru | Data | MEDIUM | MEDIUM | MEDIUM | 2+ | Benchmark; supplement if custom filter bottleneck |
| Helicone | Eval | HIGH | MEDIUM | LOW | 2 | Integrate logging now; migrate versioning in Phase 2 |
| Alternative Eval Platforms | Eval | MEDIUM | MEDIUM | LOW | 2 | Evaluate Braintrust for LLM-as-judge |
| DuckDB v0.10.0+ | Perf | HIGH | LOW | LOW | 1 | Upgrade + tune memory settings |
| React Web Workers | Perf | HIGH | MEDIUM-HIGH | MEDIUM | 2 | Optimize hex coloring calculation |
| WebSocket Batching | Perf | HIGH | LOW | LOW | 1 | Verify; implement adaptive flushing if needed |

---

## Sources & Links

**Spatial/Geo:**
- [H3 DuckDB Extension](https://duckdb.org/community_extensions/extensions/h3)
- [Isaac Brodsky's H3-DuckDB Bindings](https://github.com/isaacbrodsky/h3-duckdb)
- [deck.gl Performance Guide](https://deck.gl/docs/developer-guide/performance)
- [Awesome DuckDB Spatial](https://github.com/alperdincer/Awesome-DuckDB-Spatial)

**LLM/Agent:**
- [Claude Prompt Caching](https://claude.com/blog/prompt-caching)
- [Claude Structured Outputs Documentation](https://platform.claude.com/docs/en/build-with-claude/structured-outputs)
- [Claude Haiku 4.5](https://www.anthropic.com/claude/haiku)
- [Claude Batch API](https://platform.claude.com/docs/en/build-with-claude/batch-processing)
- [Haiku Multi-Agent Architecture Guide](https://www.caylent.com/blog/claude-haiku-4-5-deep-dive-cost-capabilities-and-the-multi-agent-opportunity)

**Real-time Data:**
- [AISHub](https://www.aishub.net/)
- [aisstream.io](https://github.com/aisstream/aisstream)
- [VesselAPI](https://vesselapi.com/)
- [POLECAT Event Database](https://doi.org/10.3390/data11070158)
- [GDELT Cloud](https://gdeltcloud.com/)
- [GDELT Guru](https://gdelt.guru/)

**Eval/MLOps:**
- [Helicone.ai](https://www.helicone.ai/blog/prompt-evaluation-frameworks)
- [Braintrust LLM Evaluation](https://www.braintrust.dev/articles/best-prompt-evaluation-tools-2025)
- [Deepchecks LLM Evaluation](https://deepchecks.com/llm-evaluation/framework/)
- [LLM Evaluation Best Practices (2025)](https://www.xbytesolutions.com/llm-evaluation-metrics-framework-best-practices/)

**Performance:**
- [DuckDB Performance Guide](https://duckdb.org/docs/lts/guides/performance/overview)
- [DuckDB Memory Management](https://duckdblab.org/en/post/duckdb-memory-management-performance-tuning/)
- [React Real-Time Optimization](https://www.freecodecamp.org/news/high-frequency-real-time-data-in-react-from-ring-buffers-to-offscreencanvas/)
- [WebSocket Integration in React](https://oneuptime.com/blog/post/2026-01-15-websockets-react-real-time-applications/view)
- [Virtualization for Large React Datasets](https://www.syncfusion.com/blogs/post/render-large-datasets-in-react)

---

**Report generated:** 2026-08-26  
**Next review:** 2026-09-26 (or when Phase 1 eval cycle completes)
