# Technology Research Report: 2026-08-12

**Focus Areas:** Spatial/Geo, LLM/Agent, Real-time Data, Eval/MLOps, Performance

---

## Executive Summary

Research identified 4 actionable findings that could materially improve Parallax's cost, reliability, and user experience. Most significant: prompt caching TTL degradation creates hidden cost spike, AIS data APIs offer Hormuz specificity unavailable in GDELT alone, and React virtualization is critical for agent feed performance. Structured outputs and DuckDB optimization are mature wins ready for integration.

---

## Findings by Category

### 1. Spatial/Geospatial

#### DuckDB Native Spatial Extension (Mature Alternative)
- **Relevance:** MEDIUM
- **Effort:** LOW
- **Risk:** LOW
- **Assessment:** DuckDB's core spatial extension (7K lines C++, built on GDAL/PROJ/GEOS) is production-ready and provides full-featured PostGIS-equivalent geometry operations. Currently Parallax pins an older H3 community extension; native spatial could reduce dependency fragility while enabling richer queries (polygon containment, distance calculations beyond H3 cell ops).
- **Integration:** Can coexist with current H3 layer. Parallel implementation for non-critical queries (port analysis, route geometry).
- **Risk factors:** Switching from H3 to pure spatial would break existing cell-based cascade logic—not recommended mid-project. But supplementing with spatial for geometry-heavy queries (port analysis, shipping lane clustering) is low-risk.

#### A5 DGGS as Alternative Hierarchical Indexing
- **Relevance:** LOW
- **Effort:** HIGH
- **Risk:** MEDIUM
- **Assessment:** A5 DGGS (Discrete Global Grid System) is hierarchical like H3, but with less tooling and lower adoption. Parallax's H3 choice is sound; switching would require rewriting cascade rules and visualization layers.
- **Recommendation:** Monitor but don't pursue; H3 ecosystem is strongest.

#### S2 Geometry for Spherical Calculations
- **Relevance:** LOW-MEDIUM
- **Effort:** LOW
- **Risk:** LOW
- **Assessment:** S2 provides true spherical geometry (vs planar H3). Useful if oil price shock calculation needs accuracy on Great Circle distances (Cape reroute penalty is currently ~11,600 NM estimate). Currently a parameterized scenario value; S2 would make it data-driven.
- **Integration:** Supplemental—compute cape reroute distance once via S2, cache as parameter.

---

### 2. LLM/Agent

#### ⚠️ Prompt Caching TTL Regression (Cost Risk)
- **Relevance:** HIGH
- **Effort:** MEDIUM
- **Risk:** HIGH (if ignored)
- **Assessment:** **Critical finding.** Anthropic silently changed prompt cache TTL from 60 min → 5 min in early 2026. This degrades cache hit rates for Parallax's agent swarm: system prompts (historical baseline, ~3K tokens each) are cached per agent version, but with 5-min TTL, multi-hour between major events means repeated cache misses and 10x input cost vs. 90% discount.
- **Current impact:** ~$2-5/day estimate in design doc assumes 5-min TTL already accounts for this, but worth verifying.
- **Mitigations:**
  1. Use **Persistent Cache** (available on Sonnet 4.6+/Opus 4.6+): survives session boundaries, viable for daily batch jobs.
  2. **Batch API** for non-real-time work (daily scorecard, prompt eval) gets 50% cost reduction automatically.
  3. Monitor actual cache hit rates via Anthropic usage logs; flag if degrading.

#### Batch API for Cost Reduction
- **Relevance:** HIGH
- **Effort:** LOW
- **Risk:** LOW
- **Assessment:** Parallax has non-real-time work (daily scorecard computation, batch eval on historical data) that could tolerate latency. Batch API gives flat 50% discount on input+output tokens—apply to `--scorecard` and `--eval` runs.
- **Integration:** FastAPI endpoint already handles scorecard; wrap eval calls in batch queue, execute once/day.
- **Estimated savings:** ~$1-2/day if scorecard + eval moved to batch.

#### Claude Structured Outputs (GA, Complex Schema Support)
- **Relevance:** HIGH
- **Effort:** LOW
- **Risk:** LOW
- **Assessment:** Anthropic just shipped native structured outputs support (GA) across Haiku/Sonnet/Opus with complex schema validation. Parallax already validates agent output JSON via Pydantic; structured outputs eliminate the need for custom validation and guarantee conformance.
- **Current state:** Agent decisions use JSON schema validation post-hoc. Structured outputs bake validation into the model itself—fewer retries, cleaner code.
- **Integration:** Drop-in via `response_format={"type": "json_schema", "json_schema": {...}}` on all agent calls.
- **Benefit:** Eliminates ~5-10% of agent calls that fail validation and retry.

#### Context Compaction (Beta)
- **Relevance:** MEDIUM
- **Effort:** LOW
- **Risk:** MEDIUM (beta feature)
- **Assessment:** New beta feature (header `compact-2026-01-12`) condenses earlier conversation history into summaries server-side, reducing context window pressure. Useful if agent memory tables grow large over 30+ days.
- **Recommendation:** Pilot on eval meta-agent first; low risk since it's non-critical.

---

### 3. Real-Time Data

#### GDELT Cloud Hourly Updates vs. BigQuery 15-min
- **Relevance:** MEDIUM
- **Effort:** MEDIUM
- **Risk:** LOW
- **Assessment:** Parallax currently uses GDELT BigQuery (15-min cycle). GDELT Cloud (2026) offers hourly updates with event clustering following ACLED methodology. Trade-off: hourly is slower but noisier; 15-min is better for real-time responsiveness but relies on BigQuery quota.
- **Use case:** Could supplement BigQuery ingestion for redundancy—if BQ quota exhausted, fall back to GDELT Cloud.
- **Integration:** Parallel ingestion pipeline, merge results.

#### AIS (Automatic Identification System) APIs for Real-Time Shipping
- **Relevance:** HIGH
- **Effort:** MEDIUM
- **Risk:** LOW
- **Assessment:** **Actionable finding.** Current stack has no real-time vessel tracking—cascade engine models Hormuz traffic as a parameter (20M bbl/day) updated daily via EIA. AIS APIs (MarineTraffic, Datalastic, AISstream) provide live vessel positions in Hormuz strait. This is a significant data gap for a system claiming to model real-time blockade impacts.
- **Market consolidation:** Kpler acquired MarineTraffic + FleetMon; MarineTraffic ended credit-based pricing, now enterprise-only. **Best alternatives:**
  1. **AISstream.io** - Free real-time WebSocket, good for proof-of-concept.
  2. **Datalastic** - Self-serve API, per-request pricing (~$0.01/vessel).
  3. **VesselAPI** - REST API, good for historical + real-time blend.
- **Parallax integration:** Count vessels in H3 cells (res 7-8, Hormuz corridor), feed as real-time input to cascade engine. Replace fixed parameter with dynamic data.
- **Cost:** AISstream free tier sufficient for demo; production would need paid tier (~$50-200/month for Hormuz region).
- **Value:** Differentiates from rule-based models; enables detection of actual vs. perceived blockades.

#### ACLED Weekly Validated Conflict Data
- **Relevance:** MEDIUM
- **Effort:** LOW
- **Risk:** LOW
- **Assessment:** Parallax already uses ACLED (lagged, weekly). ACLED is the gold standard for armed conflict validation. Leverage more deeply: pull not just events but also ACLED's monthly data quality reports (which flag event inflation in certain regions/sources). Use to auto-flag agents when their predictions diverge from ACLED ground truth.

---

### 4. Evaluation & MLOps

#### Braintrust (Code-Based Evaluation Platform)
- **Relevance:** MEDIUM
- **Effort:** MEDIUM
- **Risk:** LOW
- **Assessment:** Braintrust connects dataset management, scoring, production monitoring, and CI-based release gates in one system. Parallax already has eval framework (prediction log, scoring, prompt versioning), but it's hand-rolled. Braintrust could replace custom code for:
  1. Version comparison (auto A/B test new prompts).
  2. Production tracing (capture every agent call, evaluation result).
  3. Release gates (don't deploy prompt v1.3.0 if accuracy drops below baseline).
- **Integration:** Wrap agent calls with Braintrust SDK, define scorers (direction, magnitude, calibration) in their DSL.
- **Cost:** ~$500-2k/month depending on scale; Parallax's $2-5/day token spend is small enough to fit well.
- **Alternative:** Galileo AI (faster to start with prebuilt evaluators, but less flexible for custom eval logic).
- **Recommendation:** Pilot Braintrust for prompt versioning + A/B testing.

#### Galileo AI (Prebuilt Evaluators)
- **Relevance:** MEDIUM
- **Effort:** LOW
- **Risk:** LOW
- **Assessment:** 20+ built-in metrics (faithfulness, relevance, toxicity, etc.) + Luna-2 small evaluation models. Ships with LangGraph/CrewAI integration. Better fit if Parallax stays with agent framework only; worse if custom eval metrics needed.
- **Use case:** Quick start for general agent quality checks; supplement with custom scorers for domain-specific (direction, magnitude) metrics.
- **Recommendation:** Evaluate as alternative if Braintrust overhead feels heavy.

---

### 5. Performance

#### React Virtualization (Critical for Agent Feed)
- **Relevance:** HIGH
- **Effort:** MEDIUM
- **Risk:** LOW
- **Assessment:** **Critical finding.** Parallax's left panel (agent activity feed) scrolls decisions. With 50 agents, 10-20 events/day, and continuous live updates, rendering the full feed DOM causes janky scrolling + UI lag during high-activity periods. Design doc already notes this ("render thrashing if you push WebSocket updates into React state") but doesn't implement a fix.
- **Solution:** Use `react-window` or `react-virtuoso` to virtualize the agent feed list. Render only visible + buffer items (~50 visible on typical 1440px height, render 100 total).
- **Libraries:**
  - `react-window` - lightweight, battle-tested, mature.
  - `react-virtuoso` - higher-level, auto-handles dynamic heights, smaller bugs in corner cases.
- **Integration:** Wrap agent feed in `FixedSizeList` (if decisions all ~60px), or `Virtuoso` (for variable heights).
- **Estimated impact:** 60+ FPS maintained even during 100+ concurrent updates/sec (if they were to occur).
- **Effort:** ~1-2 days for integration + testing.

#### WebSocket Optimization (Batching, Payload Size)
- **Relevance:** MEDIUM
- **Effort:** LOW
- **Risk:** LOW
- **Assessment:** Design doc mentions batching updates (100ms buffer); this is correct. Specific optimizations:
  1. **Message compression:** gzip payloads if > 1KB (adds <5ms latency, saves 50-70% bandwidth).
  2. **Delta updates:** Only send changed fields, not full cell state (already in design).
  3. **Sticky sessions:** If scaling backend, load balancers must maintain WebSocket affinity.
  4. **Connection pooling:** Re-connect logic with exponential backoff (already common).
- **Implementation:** Low-hanging fruit in FastAPI WebSocket handler.

#### DuckDB Performance Optimization
- **Relevance:** MEDIUM
- **Effort:** LOW
- **Risk:** LOW
- **Assessment:** Parallax uses DuckDB for all mutable state (world_state_delta, decisions, predictions). Optimization checklist:
  1. **Column projection:** Only read columns needed (huge win for wide tables).
  2. **Parquet format:** Store cold data (historical snapshots, archived deltas) as Parquet, not in-DB. Predicate pushdown gives 10-100x speedup on scans.
  3. **ENUM types:** Convert string columns (agent_id, action_type) to ENUM, reduce storage + improve filtering.
  4. **EXPLAIN ANALYZE:** Profile slow queries (decisions over 30 days is a big table).
  5. **Pre-sorted keys:** If joining on agent_id repeatedly, pre-sort Parquet files by agent_id before loading.
- **Priority:** ENUM conversion is easiest win. Parquet archive for >7 days old data is medium-term optimization.
- **Estimated impact:** ~30-50% query speedup on prediction history + eval queries.

---

## Top 3 Recommendations

### 1. Integrate AIS Real-Time Vessel Tracking (HIGH impact, MEDIUM effort)
- **Why:** Replaces a static parameter (20M bbl/day) with ground truth. Enables detection of actual blockade efficacy vs. perceived threats. Differentiates Parallax from rule-based competitors.
- **Action:** Evaluate AISstream.io free tier (proof-of-concept). Implement vessel count aggregation into H3 cells (Hormuz res 7-8). Feed into cascade engine as dynamic flow parameter.
- **Timeline:** 2-3 weeks for integration + testing.
- **Cost:** Free tier for demo; ~$50-100/month production.

### 2. Migrate Agent Calls to Structured Outputs + Batch API (HIGH impact, LOW effort)
- **Why:** Structured outputs eliminate validation retry loops (~5-10% of calls). Batch API cuts costs 50% on non-real-time work (scorecard, eval).
- **Action:**
  1. Update all agent prompts to use Claude's native structured output format.
  2. Wrap `--scorecard` and `--eval` CLI commands in batch queue.
  3. Monitor actual cache hit rates and switch to persistent cache for long-lived agent versions.
- **Timeline:** 1 week for implementation + testing.
- **Savings:** ~$0.50-1.50/day + improved reliability.

### 3. Implement React Virtualization on Agent Feed (MEDIUM impact, MEDIUM effort)
- **Why:** Maintains 60+ FPS during high-volume agent activity. UX improvement for live demo.
- **Action:** Integrate `react-window` into left panel agent list. Test with synthetically generated 500+ decision events.
- **Timeline:** 3-5 days for integration + tuning.
- **Effort:** Moderate; requires understanding of deck.gl/WebSocket interaction.

---

## Secondary Recommendations (Monitor / Pilot)

- **Prompt Caching TTL Regression:** Verify actual cache hit rates; prioritize persistent cache if degradation observed.
- **Braintrust for Eval:** Pilot as alternative to hand-rolled prompt versioning system; defer decision after Parallax eval framework matures.
- **DuckDB ENUM Types:** Quick win for storage/query efficiency; apply to `agent_id`, `action_type`, `status` columns.
- **Context Compaction (beta):** Monitor Anthropic updates; safe to pilot on non-critical eval meta-agent.

---

## Sources

### Spatial/Geospatial
- [DuckDB Spatial Extensions Overview](https://duckdb.org/docs/lts/core_extensions/spatial/overview)
- [Awesome DuckDB Spatial - Curated List](https://github.com/alperdincer/Awesome-DuckDB-Spatial)
- [Spatial SQL Landscape 2026 - Matt Forrest](https://forrest.nyc/best-spatial-sql-tools/)

### LLM/Agent
- [Claude Prompt Caching Guide - Bartosz Cruz](https://bartoszcruz.com/blog/claude-api-prompt-caching-cut-costs-90-percent)
- [Claude Prompt Caching 5-min TTL Cost Impact - DEV Community](https://dev.to/whoffagents/claude-prompt-caching-in-2026-the-5-minute-ttl-change-thats-costing-you-money-4363)
- [Claude Cost Optimization 2026 - PECollective](https://pecollective.com/tools/claude-pricing-guide/)
- [Claude Structured Outputs - Platform Docs](https://platform.claude.com/docs/en/build-with-claude/structured-outputs)
- [Structured Outputs GA Announcement](https://claude.com/blog/structured-outputs-on-the-claude-developer-platform)

### Real-Time Data
- [GDELT Cloud API Documentation](https://docs.gdeltcloud.com/)
- [GDELT Cloud Geopolitical Risk & Event Data](https://gdeltcloud.com/)
- [50 Best Ship Tracking APIs 2026](https://hormuzmonitor.com/50-best-ship-tracking-apis-2026/)
- [MarineTraffic API Services](https://support.marinetraffic.com/en/articles/9552659-api-services)
- [AIS API Providers Comparison - Data Docked](https://datadocked.com/ais-api-providers)

### Evaluation & MLOps
- [Braintrust vs Galileo AI Comparison](https://www.braintrust.dev/articles/braintrust-vs-galileo-ai)
- [Best LLM Evaluation Tools 2026 - Braintrust](https://www.braintrust.dev/articles/best-llm-evaluation-tools-integrations-2025)
- [Galileo AI Agent Reliability Platform](https://www.braintrust.dev/articles/best-galileo-ai-alternatives-2026)

### Performance
- [DuckDB Speed Secrets 2026 - Nikulsinh Rajput](https://medium.com/@hadiyolworld007/duckdb-speed-secrets-10-tricks-for-2026-29c990a8701d)
- [DuckDB Performance Tuning Guide - DuckDB Lab](https://duckdblab.org/en/post/duckdb-performance-tuning-5-tips/)
- [DuckDB Performance Guide - Official Docs](https://duckdb.org/docs/lts/guides/performance/overview)
- [WebSocket Optimization for Real-Time Dashboards - ZeonEdge](https://zeonedge.com/blog/building-real-time-applications-websockets-2026-architecture-scaling)
- [React Rendering Optimization for Large Datasets - Medium](https://medium.com/@kc_clintone/how-virtualization-makes-react-apps-fast-without-rendering-everything-2f5275df94de)
- [React Virtualization with react-window - OneUptime](https://oneuptime.com/blog/post/2026-01-15-react-virtualization-large-lists-react-window/view)

---

**Report Generated:** 2026-08-12  
**Next Review:** 2026-08-19
