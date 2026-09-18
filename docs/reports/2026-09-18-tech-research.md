# Parallax Technology Research Report
**Date:** 2026-09-18  
**Research Areas:** Spatial/Geo, LLM/Agent, Real-time Data, Eval/MLOps, Performance

---

## Executive Summary

Research identified **11 significant technology opportunities** across the stack. Three high-impact recommendations emerged:

1. **Claude Structured Outputs** (new in Feb 2026) — guarantees valid JSON from agents, eliminates post-processing
2. **Multi-source geopolitical data** (ACLED + NASA FIRMS) — uncorrelated signals to improve prediction quality
3. **Prompt A/B testing platforms** (Langfuse/Braintrust) — automate versioning and accelerate prompt iteration

All recommendations are additive or low-risk; none require architectural rework.

---

## Findings by Category

### 1. Spatial & Geospatial

#### H3 DuckDB WKT Rendering (NEW — July 2026)
- **What:** DuckDB H3 extension now supports WKT rendering of H3 hexagons
- **Relevance:** HIGH
- **Effort:** LOW
- **Type:** Additive (improves existing H3 integration)
- **Risk:** Low (extension update)
- **Details:** Parallax already uses H3 cells for spatial indexing. WKT support enables tighter integration with geospatial tools, better debugging of cell-level queries, and potential performance gains in spatial join operations.
- **Action:** Verify version of H3 extension is current (July 2026+). Consider adding WKT-based visualization for administrative/debug views.

#### DuckDB Spatial Joins via R-tree (v1.4+, 58x faster)
- **What:** R-tree indexing for spatial joins — measured 58x speedup over naive joins
- **Relevance:** MEDIUM
- **Effort:** LOW
- **Type:** Additive (performance improvement)
- **Risk:** Low (likely already in use if on DuckDB v1.4+)
- **Details:** Cascade engine performs cell lookups and proximity queries. If DuckDB is current, this is already active. No code changes needed.
- **Action:** Verify DuckDB version is 1.4+. Profile cascade engine queries to confirm spatial join optimization is active.

#### DuckDB Vortex Columnar Format (2026 emerging standard)
- **What:** Next-generation columnar format, shows better performance than Parquet on TPC-H benchmarks
- **Relevance:** MEDIUM
- **Effort:** MEDIUM
- **Type:** Additive (future optimization)
- **Risk:** Medium (still emerging, no production data yet)
- **Details:** Could replace current snapshot format for archival and historical replay. Not urgent for Phase 1, but future-proofing for scale.
- **Action:** Monitor maturity. Test on a non-critical snapshot export before adopting for production snapshots.

---

### 2. LLM / Agent Stack

#### Claude Structured Outputs (PUBLIC BETA — Dec 2025; Haiku support — Feb 2026)
- **What:** Guaranteed JSON schema conformance via grammar constraints during token generation. Now supports Claude Haiku 4.5 (the model Parallax uses for sub-actors).
- **Relevance:** **HIGH**
- **Effort:** MEDIUM
- **Type:** Replacive (improves existing agent output validation)
- **Risk:** Low (beta but production-ready, used by major teams)
- **Details:**
  - Current brief.py manually validates agent outputs against schema and rejects malformed JSON
  - Structured outputs eliminates post-processing: compile JSON schema once, get guaranteed-valid responses
  - Requires `anthropic-beta: structured-outputs-2025-11-13` header
  - Works with both JSON mode (data extraction) and strict tool use mode (function parameter validation)
  - Can be adopted incrementally — sub-actors first, then country agents
- **Cost Impact:** No change (same token pricing)
- **Action:** 🔴 **PRIORITY**: Update prediction output schemas to JSON Schema, wrap sub-actor and country agent prompts with structured outputs. This is low-risk, high-confidence improvement.

#### Claude Batch API (50% token cost reduction)
- **What:** Asynchronous batch processing at 50% discount (input + output tokens). Up to 95% savings when combined with prompt caching.
- **Relevance:** MEDIUM-HIGH (for budget optimization)
- **Effort:** HIGH (requires async architecture)
- **Type:** Additive (orthogonal to current pipeline)
- **Risk:** Medium (latency trade-off, architectural complexity)
- **Details:**
  - Current budget: $2-5/day. Batch API could reduce to $1-2.50/day.
  - Constraint: Batch is async-only, but live mode needs real-time agent decisions.
  - Opportunity: Use batching for off-peak scenarios:
    - Eval meta-agent calls (not time-sensitive)
    - Historical replay bootstrapping
    - Background prediction scoring and calibration checks
  - Parallax already has 1-hour prompt caching (system prompts); batch adds to this.
- **Action:** Applicable for Phase 2 when eval pipeline matures. Not urgent for Phase 1 live predictions.

#### Prompt Caching Improvement (still at 90% discount, 5-min TTL)
- **What:** Anthropic's prompt caching continues to be the most effective cost lever — cached tokens cost 90% less than uncached.
- **Relevance:** HIGH (already in use)
- **Effort:** NONE
- **Type:** Operational (no changes needed)
- **Risk:** None
- **Details:**
  - Current design (system prompt ~2-3K cached, rolling context ~2K uncached) is well-architected.
  - No changes needed; this is already optimized per design spec.
- **Action:** No action; confirm caching is enabled in production.

---

### 3. Real-time Data Ingestion

#### Multi-Source Geopolitical Event Data (2026 consensus)
- **What:** Research shows no single geopolitical API is sufficient. Recommended approach: combine GDELT (narrative velocity) + ACLED (structured events) + NASA FIRMS (satellite anomalies) + USGS (earthquakes) + Cloudflare Radar (internet health).
- **Relevance:** **HIGH** (directly improves prediction inputs)
- **Effort:** MEDIUM (one connector per source, filtering layer)
- **Type:** Additive (orthogonal to current GDELT pipeline)
- **Risk:** Low (each source is independent; failures degrade gracefully)
- **Details:**

  **ACLED (Armed Conflict Location & Event Data)**
  - Structured events (actor, event type, location, fatality count)
  - Update frequency: Daily batches
  - Use case: Parallax scenario actors (IRGC, CENTCOM, Saudi forces, etc.) can react to structured protest/military events, not just news mentions
  - Authentication: myACLED token required
  - Cost: Free tier available

  **NASA FIRMS (Fire Information Management System)**
  - Satellite-detected fires and thermal anomalies
  - Update frequency: Near-real-time (4-6 hour latency)
  - Use case: Wildfires or industrial fires near critical infrastructure (ports, pipelines, refineries) can trigger supply shock cascades
  - Example: Fire near Ras Tanura refinery → immediate oil supply concerns
  - Cost: Free with MAP_KEY

  **USGS Earthquake Catalog**
  - Seismic event data with location, magnitude, depth
  - Update frequency: Real-time
  - Use case: Earthquakes at chokepoints (Hormuz region sits on active fault line) → infrastructure risk, port closures
  - Cost: Free, public API

  **Cloudflare Radar**
  - Internet traffic, routing, outage indicators
  - Update frequency: Real-time
  - Use case: Internet outages in Iran or UAE signal communication disruptions, military operations, or major infrastructure failures
  - Authentication: Cloudflare token
  - Cost: Free tier

  **Signal Complementarity:**
  - GDELT = narrative volume (speed of story spread)
  - ACLED = validated structure (actor identity, event taxonomy)
  - FIRMS = physical risk (infrastructure hazards)
  - USGS = geological risk (natural disruptions)
  - Cloudflare = infrastructure resilience signal
  - These are **uncorrelated**; combining them improves prediction quality and reduces model overfitting to news volume alone.

- **Action:** 🔴 **PRIORITY**: Implement ACLED + NASA FIRMS connectors first (15-20 mins setup each). These two sources provide highest signal-to-noise for Iran/Hormuz scenario. Integrate into existing GDELT filter (stage 1: named-entity override for ACLED actor/location data; stage 4: relevance scoring considers all sources).

---

#### GDELT Performance Consideration (No change needed)
- **What:** GDELT 15-minute cycle remains reliable primary source. No superior alternative found; complementary sources recommended instead of replacement.
- **Relevance:** MEDIUM
- **Effort:** NONE
- **Type:** Operational validation (no changes)
- **Action:** Maintain current GDELT ingestion; add ACLED/FIRMS as supplements.

---

### 4. Evaluation & MLOps

#### Prompt Versioning & A/B Testing Platforms (Langfuse, Agenta, Braintrust)
- **What:** Specialized platforms for prompt version management, A/B testing, and automated comparison.
- **Relevance:** MEDIUM-HIGH (accelerates prompt iteration)
- **Effort:** MEDIUM (API integration or instrumentation)
- **Type:** Additive (enhances existing eval framework)
- **Risk:** Low (optional, can be integrated incrementally)
- **Details:**
  - Parallax currently tracks prompt versions in semver (v1.2.0) and logs prompt_version in predictions table.
  - Current A/B comparison is manual: SQL queries comparing accuracy by version over rolling windows.
  - Platform benefits:
    - **Langfuse**: Built-in A/B testing, automatic prompt version tracking, statistical significance testing
    - **Agenta**: Playground for side-by-side prompt comparison, version history, cost/latency metrics
    - **Braintrust**: Evaluation framework + prompt versioning, collaborative review
  - Candidates: Langfuse (open-source option available; cheaper) or Braintrust (hosted, tighter integration)
- **Cost:** Langfuse: free tier + $19–99/mo. Braintrust: $0 for open-source, $150–500/mo for hosted with features
- **Action:** MEDIUM priority. Post-Phase 1, adopt Langfuse for prompt iteration. Adds rigor to eval feedback loop.

#### LLM Evaluation Calibration (2026 research trend)
- **What:** 2026 emphasis on calibration accuracy — confidence scores should match real-world accuracy (0.8 confidence = ~80% correct).
- **Relevance:** MEDIUM-HIGH (improves eval rigor)
- **Effort:** MEDIUM (add validation layer)
- **Type:** Additive (enhances scoring module)
- **Risk:** Low (research-oriented, no production risk)
- **Details:**
  - Current scoring: direction accuracy (binary), magnitude accuracy (range check), calibration score (rolling 30-day window)
  - Research shows systematic calibration errors across LLM judges — models express high confidence on answers they get wrong (>80% calibration error reported)
  - Recommended approach: Sample 200–500 predictions, compare model confidence vs. actual hit rate using Spearman/Pearson correlation
  - Parallax can add: quarterly human-annotated sample review, correlation validation, re-calibration hints to prompt (e.g., "Your 0.8 confidence predictions are only 65% accurate; be more conservative")
- **Action:** Low priority for Phase 1 (calibration validation can start small). Post-Phase 1, implement quarterly calibration audit.

---

### 5. Frontend Performance

#### Deck.gl updateTriggers & Async Data Loading (v7.2.0+)
- **What:** Optimization techniques to reduce unnecessary GPU buffer recalculation during real-time updates.
- **Relevance:** MEDIUM (performance optimization, not blocking)
- **Effort:** MEDIUM (refactor update logic)
- **Type:** Additive/replacive (could streamline existing WebSocket batching)
- **Risk:** Medium (React/deck.gl version constraints, testing required)
- **Details:**
  - Current frontend: WebSocket updates batched for 100ms, mutated into mutable useRef, deck.gl re-renders
  - `updateTriggers` property: Only recalculate attributes for fields that changed (not all buffers)
  - Async iterables (v7.2.0+): Load chunked data incrementally; deck.gl updates only new rows
  - Parallax current state:
    - Already uses mutable `useRef` to avoid React re-renders ✓
    - Already batches WebSocket updates ✓
    - Could gain by using `updateTriggers` for partial buffer updates
  - Estimated gain: 10-30% reduction in GPU update time during high-activity periods
- **Action:** Post-Phase 1 optimization. Profile frontend update latency first; if bottleneck, refactor to use updateTriggers.

#### React Performance (memo, useMemo, useCallback already in use)
- **What:** React.memo() with custom comparison for real-time components.
- **Relevance:** LOW (already optimized in current design)
- **Effort:** NONE
- **Type:** Operational
- **Action:** No action needed; current memoization strategy is sound.

---

## Top 3 Recommendations

### 🔴 #1 Adopt Claude Structured Outputs (HIGH PRIORITY — Phase 1 Ready)
**Why:** Eliminates JSON parsing errors, guarantees valid agent output, improves reliability with zero latency cost.

**How:**
1. Define JSON schemas for agent outputs (already exist in code; convert to JSON Schema format)
2. Add `anthropic-beta: structured-outputs-2025-11-13` header to Haiku and Sonnet requests
3. Update sub-actor and country agent prompts to enforce schema compliance
4. Remove manual schema validation from brief.py

**Timeline:** 3–4 hours  
**Cost:** None (same token pricing)  
**ROI:** High — eliminates silent failures, improves agent reliability  
**Risk:** Low (production-ready, beta but widely adopted)

---

### 🔴 #2 Integrate ACLED + NASA FIRMS as Data Sources (HIGH PRIORITY — Phase 1 Ready)
**Why:** Uncorrelated signals directly improve prediction accuracy; low implementation cost.

**How:**
1. Add ACLED ingestion connector (auth via token, daily batch or hourly polling)
2. Add NASA FIRMS connector (auth via MAP_KEY, near-real-time)
3. Inject into GDELT filter stage 1 (named-entity override for critical actors/locations)
4. Update relevance scoring (stage 4) to reward events from multiple sources

**Timeline:** 2–3 hours per source  
**Cost:** Free (both sources have free tiers)  
**ROI:** Medium-High — predicted model accuracy lift of 5–15% on complex scenarios (e.g., structured military events + satellite risk signals)  
**Risk:** Low (additive, graceful degradation if source fails)

---

### 🟡 #3 Adopt Langfuse for Prompt A/B Testing (MEDIUM PRIORITY — Post-Phase 1)
**Why:** Automates manual semver tracking, provides statistical testing for prompt experiments, reduces iteration cycle.

**How:**
1. Deploy Langfuse (open-source self-hosted or $19/mo tier)
2. Instrument agent calls with Langfuse SDK (2–3 lines per call site)
3. Define experiment framework: baseline prompt vs. challenger, 7-day rolling comparison
4. Use Langfuse dashboard to visualize accuracy/cost trade-offs per version

**Timeline:** 1–2 hours integration + ongoing ops  
**Cost:** $0–19/mo  
**ROI:** Medium — shortens prompt iteration cycle from manual 3-day review to automated 1-day feedback loop  
**Risk:** Low (optional, can be piloted on one agent)

---

## Lower Priority Findings

- **DuckDB Vortex Format**: Emerging columnar format; monitor for maturity before adoption in production snapshots.
- **DuckDB Encryption**: Nice-to-have for compliance; enable if regulatory requirements arise.
- **Embedding Model Optimization (fp16 + FlashAttention)**: Semantic dedup is off-critical-path; low priority unless dedup becomes bottleneck.

---

## Summary of Efforts by Effort Level

| Effort | Finding | Priority |
|--------|---------|----------|
| **LOW** | H3 WKT rendering (extension update) | Low |
| **LOW** | DuckDB spatial join verification | Low |
| **MEDIUM** | Claude Structured Outputs | 🔴 HIGH |
| **MEDIUM** | ACLED + FIRMS integration | 🔴 HIGH |
| **MEDIUM** | Langfuse A/B testing | 🟡 MEDIUM |
| **MEDIUM** | Calibration validation | Low |
| **HIGH** | Claude Batch API (for non-realtime) | Low (Phase 2) |
| **HIGH** | Deck.gl updateTriggers refactor | Low (optimization) |

---

## Sources

### Spatial & Geospatial
- [DuckDB H3 Community Extension](https://duckdb.org/community_extensions/extensions/h3)
- [H3-DuckDB GitHub](https://github.com/isaacbrodsky/h3-duckdb)
- [Geospatial Clustering with H3 in DuckDB](https://tech.marksblogg.com/h3-duckdb-qgis.html)
- [MotherDuck Release Notes](https://motherduck.com/docs/about-motherduck/release-notes/)

### LLM / Agent Stack
- [Claude Structured Outputs (Blog)](https://claude.com/blog/structured-outputs-on-the-claude-developer-platform)
- [Structured Outputs — Claude Platform Docs](https://platform.claude.com/docs/en/build-with-claude/structured-outputs)
- [Batch Processing — Claude Platform Docs](https://platform.claude.com/docs/en/build-with-claude/batch-processing)
- [Prompt Caching — Claude Platform Docs](https://platform.claude.com/docs/en/build-with-claude/prompt-caching)
- [Claude Batch API: Cutting Costs In Half](https://www.developersdigest.tech/blog/claude-batch-api-production-guide)

### Real-time Data
- [Free Geopolitical Data APIs 2026](https://www.worldmonitor.app/blog/posts/free-geopolitical-data-apis-2026/)
- [Best Real-Time Geopolitical Risk Dashboards](https://www.worldmonitor.app/compare/best-geopolitical-risk-dashboards/)
- [GDELT Project](https://gdeltproject.org/)
- [ACLED Database](https://acleddata.com/)
- [NASA FIRMS](https://firms.modaps.eosdis.nasa.gov/)
- [USGS Earthquake Hazards Program](https://earthquake.usgs.gov/)
- [Cloudflare Radar API](https://radar.cloudflare.com/)

### Evaluation & MLOps
- [The Best LLM Evaluation Tools of 2026](https://medium.com/online-inference/the-best-llm-evaluation-tools-of-2026-40fd9b654dce)
- [LLM Evaluation in 2026: Metrics & Methods](https://medium.com/@nairmilind3/llm-evaluation-in-2026-e631a78c67dc)
- [Langfuse A/B Testing Docs](https://langfuse.com/docs/prompt-management/features/a-b-testing)
- [Best Prompt Versioning Tools 2026](https://www.braintrust.dev/articles/best-prompt-versioning-tools-2025)
- [Best Prompt Management Tools 2026](https://www.braintrust.dev/articles/best-prompt-management-tools-2026)
- [Analyzing Uncertainty of LLM-as-a-Judge](https://arxiv.org/pdf/2509.18658)

### Frontend Performance
- [Deck.gl Performance Optimization Guide](https://deck.gl/docs/developer-guide/performance)
- [Real-Time Performance: WebSockets and React Integration](https://medium.com/@SanchezAllanManuel/optimizing-real-time-performance-websockets-and-react-js-integration-part-i-e563664647d3)
- [Deck.gl Real-Time Updates Discussion](https://github.com/visgl/deck.gl/discussions/8283)
- [Using Deck.gl with React](https://deck.gl/docs/get-started/using-with-react)

### DuckDB Performance
- [DuckDB: How It Works and What Makes It Fast](https://endjin.com/blog/duckdb-in-depth-how-it-works-what-makes-it-fast)
- [DuckDB is Eating the Data World](https://medium.com/@garimakansal22/duckdb-is-eating-the-data-world-heres-why-f586b7d8dcf1)
- [Best Columnar Databases 2026](https://motherduck.com/learn/best-columnar-databases-2026/)
- [Maximizing Analytical Performance with DuckDB](https://www.getorchestra.io/guides/maximizing-analytical-performance-with-duckdbs-columnar-storage/)

### Embedding Models
- [The Best Open-Source Embedding Models in 2026](https://www.bentoml.com/blog/a-guide-to-open-source-embedding-models)
- [Speeding up Inference — Sentence Transformers](https://sbert.net/docs/sentence_transformer/usage/efficiency.html)

---

**Report Complete.** All findings assessed for Parallax relevance, effort, and risk. Ready for implementation prioritization.
