# Tech Research Scout — 2026-10-08

**Research Scope:** Spatial/Geo, LLM/Agent, Real-time Data, Eval/MLOps, Performance

**Current Stack:** DuckDB + H3, deck.gl, MapLibre GL, FastAPI, Claude API, React + Vite, sentence-transformers, searoute, GDELT BigQuery, EIA APIs

---

## Findings

### 1. Spatial & Geospatial

#### H3 4.5.0 Release (May 2026)
- **What:** H3 indexing library updated to 4.5.0 with multipolygon backend refactor.
- **Relevance:** MEDIUM — Parallax uses H3 4.x via the DuckDB community extension. The multipolygon refactor may improve polygon-to-cell-set conversions (e.g., when converting blockade zones to H3 cells for display), but it's a backend detail unlikely to change the API surface.
- **Effort:** LOW — Just bump version in Dockerfile; no code changes needed.
- **Risk:** MEDIUM — Untested on Parallax's ~400K hex budget. Run load test before deploying.
- **Action:** Monitor upstream H3 release notes. Update to 4.5.0 in next infra refresh cycle and validate deck.gl rendering at scale.

#### deck.gl / MapLibre GL Ecosystem (Still Current)
- **What:** deck.gl remains the GPU-powered layer framework for large datasets. MapLibre GL JS is the open-source standard (MapBox v3 adopted proprietary license in 2023).
- **Relevance:** HIGH — Parallax is already on this stack.
- **Assessment:** No compelling reason to change. The ecosystem is stable and battle-tested for real-time dashboards.

#### DuckDB Spatial Extension & H3 Integration
- **What:** R package `duckh3` (v0.1.0, published April 2026) wraps DuckDB's spatial + H3 extensions. No published benchmarks for H3 or spatial performance in 2026.
- **Relevance:** LOW — Parallax already uses the extensions directly. The R package adds no value to a Python/FastAPI backend.
- **Assessment:** No new insights on performance. Parallax should continue relying on DuckDB docs and internal benchmarks.

#### Amazon Redshift H3 Functions (January 2025)
- **What:** AWS added H3_Center and H3_Boundary functions to Redshift.
- **Relevance:** LOW — Parallax uses DuckDB (embedded), not Redshift. Cloud adoption is out of Phase 1 scope.

**Spatial/Geo Summary:**
- ✅ Current stack (H3 4.x, deck.gl, MapLibre GL) is stable and current.
- ✅ No strategic replacements recommended.
- 🔄 H3 4.5.0 is available; update in next cycle and test at scale.
- 📋 DuckDB spatial extension lacks published benchmarks; use internal profiling.

---

### 2. LLM & Agent

#### Claude API: Prompt Caching & Batch API (Current)
- **What:** Anthropic offers prompt caching (90% discount on cached input tokens after initial 25% write cost) and Batch API (50% cost reduction for non-real-time work). Conflict in sources: some claim caching + batch work together; others say batch doesn't support caching (as of mid-2026).
- **Relevance:** HIGH — Parallax has $20/day LLM budget; both features directly reduce costs.
- **Effort:** MEDIUM — Caching requires cache_control header on system prompts (already static per agent version). Batch API requires async job submission + polling. Both integrate with existing Anthropic SDK.
- **Risk:** LOW — Caching is backward compatible. Batch API is separate endpoint; easy to toggle.
- **Assessment:** **Strongly recommended.** Parallax's agent system has mostly static system prompts (historical baselines) that are reused across calls. Caching could reduce $2-5/day estimated cost by ~20-30% on frequent sub-actor calls.
- **Action:** 
  - Verify current docs at platform.claude.com for caching + batch compatibility.
  - Implement prompt caching on all agent system prompts (Haiku/Sonnet) with 5-min TTL.
  - Pilot batch API for eval meta-agent calls (non-real-time, can wait 24h for results).
- **Timeline:** 1-2 sprints. High ROI on budget.

#### New Claude Models (Unconfirmed for 2026)
- **What:** Search results mention "Claude 4 Opus," "Claude 3.5 Opus," "Claude 3.5 Haiku" from unreliable sources that contradict each other.
- **Relevance:** UNKNOWN — Cannot confirm model availability.
- **Action:** Check platform.claude.com model list directly. Do NOT rely on third-party sources.

#### Agent Frameworks: LangGraph vs CrewAI vs Microsoft Agent Framework
- **What:** 
  - **LangGraph:** Graph-based workflows with fine-grained control, state persistence, and failure recovery. 24K–32K GitHub stars. Best for reliability/observability.
  - **CrewAI:** Role-based agents, faster to prototype, less control over branching. Good for demos.
  - **Microsoft Agent Framework:** Positioning as successor to AutoGen (which entered maintenance mode in early 2026). New first-party alternative from OpenAI Agents SDK and Microsoft Agent Framework.
  - **Pydantic AI:** Typed-output layer, not a full orchestrator.
- **Relevance:** MEDIUM — Parallax's simulation engine is a **custom DES** (asyncio + heapq), not LangGraph. LangGraph + CrewAI are for agentic orchestration (routing, tool use, state), which Parallax handles differently.
- **Assessment:** 
  - Parallax does NOT need LangGraph/CrewAI because agents are not orchestrating themselves; they are invoked by the simulation engine and cascade logic.
  - If Phase 2 adds cross-agent negotiation or tool-use workflows, revisit LangGraph. For now, the custom engine is simpler and more aligned with the domain.
- **Action:** No change for Phase 1. Document this design choice. If Phase 2 adds multi-agent reasoning over tools, evaluate LangGraph's state persistence and branching for reliability.

**LLM/Agent Summary:**
- 🎯 **Priority:** Implement prompt caching on all agent system prompts (20-30% cost savings).
- 🎯 **Priority:** Pilot batch API for eval meta-agent (non-real-time evals).
- ✅ Current custom DES is better than LangGraph for Phase 1's cascade model.
- 📋 Verify Claude model availability; do not trust third-party sources.

---

### 3. Real-Time Data & Event Ingestion

#### GDELT Cloud (2026, Launched)
- **What:** Hosted layer on GDELT article stream. Turns raw articles into structured Events. Updates hourly. Best coverage from March 2026 onward; spotty before.
- **Relevance:** MEDIUM — Parallax already uses GDELT BigQuery. GDELT Cloud is a higher-level abstraction.
- **Effort:** LOW — Would replace GDELT BigQuery queries; same data source.
- **Risk:** MEDIUM — Historical data (before March 2026) is incomplete. Not suitable for long-term backfill.
- **Assessment:** GDELT Cloud could reduce pipeline complexity (no manual event extraction), but Parallax's four-stage filter (volume gate, dedup, semantic dedup, relevance scoring) still apply downstream. Test on pilot events.
- **Action:** Evaluate GDELT Cloud for live ingestion; keep BigQuery as fallback for historical/backfill. Run cost comparison (hourly updates vs daily BigQuery batches).

#### LSEG Vessel Tracking API (March 2026, Enterprise)
- **What:** Real-time AIS data from 25 Kinéis nanosatellites + 3,400+ terrestrial receiver stations. Validates signal anomalies. Aimed at enterprise/commodities.
- **Relevance:** HIGH — Parallax needs ship-traffic signals for Hormuz flow modeling.
- **Effort:** MEDIUM — Requires commercial contract and API integration.
- **Risk:** MEDIUM — Expensive (G2 review: "Accurate AIS Data, But Expensive"). LSEG is enterprise-focused, not startup-friendly.
- **Assessment:** If Parallax grows to trading/commercial use, LSEG is the gold standard. For Phase 1 research, AIS Hub or MarineTraffic is cheaper.
- **Action:** 
  - Phase 1: Use lower-cost AIS provider (AIS Hub or MarineTraffic API).
  - Phase 2: Evaluate LSEG for enterprise positioning/premium accuracy.

#### MarineTraffic / AIS Hub (Lower Cost)
- **What:** 
  - **MarineTraffic (Kpler):** 350K+ vessels, enterprise API, accurate, expensive.
  - **AIS Hub:** Open API for real-time AIS, lower cost, needs documentation review.
- **Relevance:** MEDIUM — Could supplement or replace searoute visualization with live vessel positions.
- **Effort:** LOW — Simple REST API integration.
- **Risk:** LOW — No critical path dependency; additive to current pipeline.
- **Assessment:** AIS data is valuable for showing real-time Hormuz traffic on the dashboard. GDELT events + actual vessel positions = stronger signal than rules-based flow estimates.
- **Action:** 
  - Research AIS Hub API docs and pricing.
  - Implement optional AIS data layer in dashboard (toggle live vessel positions).
  - Use for signal validation: compare predicted flow disruption vs observed AIS gaps.

#### ACLED (Authenticated Real-Time Conflict Events)
- **What:** Political violence, protests, riots; weekly ingestion; authenticated API access.
- **Relevance:** MEDIUM — Complements GDELT for conflict escalation signals.
- **Assessment:** Already in the design (Phase 1 spec mentions weekly ACLED batch). No new development needed.

#### Oil Price APIs (FRED / EIA / OilPriceAPI)
- **What:** 
  - **FRED / EIA:** Free, official, historical; weekly or daily updates.
  - **OilPriceAPI:** Intraday updates, commercial, claimed 99.9% SLA.
- **Relevance:** MEDIUM — Parallax uses EIA daily. Intraday prices could improve price-shock detection.
- **Effort:** MEDIUM — Integration is simple, but OilPriceAPI is a commercial dependency.
- **Risk:** MEDIUM — Commercial licensing; cost escalation risk.
- **Assessment:** FRED/EIA daily updates are sufficient for Phase 1 (15-min ticks, but oil price moves on 4h+ timescales). Intraday pricing adds little value.
- **Action:** Stick with EIA/FRED. If Phase 2 adds HFT-style trading, reconsider intraday APIs.

**Real-Time Data Summary:**
- 🎯 **Priority:** Integrate AIS Hub or MarineTraffic for live vessel positions (medium effort, high signal value).
- 🎯 **Priority:** Evaluate GDELT Cloud for hourly updates vs current daily BigQuery (cost/latency tradeoff).
- ✅ FRED/EIA daily oil prices sufficient for Phase 1.
- 📋 ACLED already in design; no change.
- 📋 LSEG Vessel Tracking is enterprise-grade; defer to Phase 2.

---

### 4. Evaluation & MLOps

#### Prompt Versioning + A/B Testing + Evaluation Platforms (2026 Landscape)
- **What:** Market consolidating around unified platforms that combine version control, A/B testing, and evaluation:
  - **Maxim AI:** Comprehensive (prompt versioning + experiment + eval + prod observability). 2026 top choice in one listicle.
  - **Braintrust:** Evaluation-first; strong for LLM eval workflows.
  - **LangSmith:** LangChain integration; not relevant to Parallax (custom DES).
  - **Agenta:** Open-source, self-hostable.
  - **Langfuse:** Open-source self-hosted with prompt-version labeling SDK.
  - **DeepEval:** Unit-testing framework (14+ metrics, pytest integration, custom metrics).
  - **PromptLayer:** Request logging, template tracking, A/B testing dashboard.
- **Relevance:** HIGH — Parallax's eval framework is custom-built (DuckDB tables for predictions, decisions, eval_results). A unified platform could reduce code.
- **Effort:** MEDIUM-HIGH — Switching from custom tables to a platform requires schema mapping, API integration, and retooling the daily eval cron.
- **Risk:** MEDIUM — Platform vendor lock-in. Lagfuse / Agenta / DeepEval are open-source; Maxim/Braintrust/LangSmith are commercial.
- **Assessment:** 
  - Parallax's current approach (prediction_id + prompt_version + manual eval table) is solid for Phase 1. 
  - For Phase 2, if the eval pipeline becomes a bottleneck, adopt **Langfuse** (open-source, self-hosted, prompt-version labeling) or **DeepEval** (lightweight, pytest-native, any provider).
  - **Do not adopt Maxim/Braintrust/LangSmith** — they are LangChain/LangGraph ecosystem tools, not suited to custom DES.
- **Action:** 
  - Phase 1: Keep custom eval. Document the schema (prediction_id, prompt_version, ground_truth, score, created_at).
  - Phase 2: Evaluate Langfuse for self-hosted observability + prompt versioning. Add pytest-style eval metrics via DeepEval.

#### A/B Testing Best Practices (From 2026 Guides)
- **Key insights:**
  - Change one layer at a time (prompt, model, hyperparameters, config, UX).
  - Run offline eval gate, then canary, then CI/CD gate. Online monitoring follows.
  - Minimum ~200 conversions (predictions) per variant to establish significance.
  - Run-to-run noise: 15% accuracy variation possible even at temperature 0. This is NOT a tool issue; it's fundamental to stochastic sampling.
- **Relevance:** HIGH — Parallax's eval framework needs this rigor.
- **Assessment:** Parallax's current approach (7-day rolling calibration window, per-version tracking) aligns with these practices. The 15% variance finding is important: if a 7-day variant count is <200 predictions, the result may be noise.
- **Action:** 
  - Ensure each agent prompt version accumulates at least 200 predictions before declaring a winner.
  - Log run-to-run variance in eval cron (temperature 0 variance as a sanity check).
  - Update prompt improvement pipeline to require 200+ prediction sample before approval.

**Eval/MLOps Summary:**
- ✅ Parallax's custom eval table design is sound for Phase 1.
- ✅ Current A/B practices (7-day window, per-version tracking) align with industry best practices.
- 📊 Log run-to-run variance (temperature 0) to understand measurement noise.
- 🎯 **Priority (Phase 2):** Adopt Langfuse (open-source) for observability + prompt-version tagging, or DeepEval for pytest-style metrics.
- 📋 Ignore commercial platforms (Maxim, Braintrust, LangSmith) — not designed for custom DES.

---

### 5. Performance

#### DuckDB Columnar Storage & Spatial Query Performance
- **What:** DuckDB uses columnar storage, vectorized operations, and zone maps for analytical queries. Single-machine scale works well; multi-core scaling shows weakness in benchmarks (performance drops off with larger datasets on many-core systems).
- **Relevance:** MEDIUM — Parallax stores ~400K hex cell snapshots + deltas. Queries are mostly recent-state lookups and aggregates, not huge scans.
- **Effort:** LOW — DuckDB tuning is configuration (no code changes).
- **Risk:** LOW — Safe tuning, easy to revert.
- **Assessment:** 
  - Parallax is within DuckDB's comfort zone (embedded, <50GB per Rill's guideline, single writer via asyncio.Queue).
  - No published H3 performance benchmarks in 2026. Use internal profiling.
  - Key settings: `memory_limit`, `threads`, `temp_directory`, `SELECT` only needed columns, Parquet format for large exports.
- **Action:** 
  - Profile current query latencies (WebSocket update cycles).
  - If WebSocket updates exceed 100ms latency, run `EXPLAIN ANALYZE` on hot queries.
  - Use `memory_limit = 16GB` (or half available RAM) to prevent thrashing.
  - Store snapshots as Parquet, not CSV.

#### React WebSocket & Real-Time Rendering (Critical Bottleneck)
- **What:** WebSocket can handle 1000s messages/sec. The bottleneck is React's reconciliation process. Solutions:
  - Decouple mutable data (useRef hex array) from React state.
  - Batch WebSocket updates (buffer 100ms, flush once).
  - Throttle updates to deck.gl (GPU rendering rate, ~60Hz).
  - Use delta updates (transmit only changes, not full state).
  - Streams + ReadableStream for backpressure control.
  - Libraries: react-use-websocket, stomp.js.
- **Relevance:** HIGH — Parallax dashboard pushes high-frequency hex updates via WebSocket.
- **Effort:** MEDIUM — Already implemented correctly in current design (useRef hex data, batching, delta updates per Section 5 of spec).
- **Risk:** LOW — Current design avoids the common React/WebSocket pitfall.
- **Assessment:** Parallax's architecture (Section 5, Frontend) already decouples React state from hex data and batches updates. This is the right approach. No changes needed unless WebSocket latency becomes visible.
- **Action:** 
  - Monitor WebSocket message latency in prod (via DevTools or metrics).
  - If updates lag (>100ms), profile the deck.gl render cycle (likely GPU bottleneck, not React).
  - Current batching (100ms window) is good for ~60Hz rendering; tune if needed.

#### General Performance Patterns
- **Parquet > CSV:** Use Parquet for snapshots and exports (better compression, faster reads).
- **Column selection:** SELECT only needed columns; DuckDB's zone maps skip row groups when columns are pruned.
- **Backpressure:** If DB write queue grows, it signals overload. Monitor queue depth.
- **EXPLAIN ANALYZE:** Profile before tuning; don't guess.

**Performance Summary:**
- ✅ DuckDB columnar + zone maps are suitable for Parallax's query profile.
- ✅ React WebSocket architecture is correct (useRef + batching).
- 📊 Monitor WebSocket latency in prod; profile hot queries if needed.
- 🎯 **Action:** Tune `memory_limit` and `threads` per available resources; use Parquet for snapshots.

---

## Top 3 Recommendations

### 1. **Implement Prompt Caching on All Agent System Prompts (HIGH ROI, 1-2 weeks)**
- **Why:** Parallax has static historical baselines per agent version, reused across 50+ agent calls/day. Prompt caching (90% discount on cached tokens after initial write cost) could reduce $2-5/day budget by 20-30%.
- **Impact:** Direct budget savings, no changes to agent output or eval.
- **Effort:** Low — add `cache_control` header to system prompt in agent invocation.
- **Risk:** None — caching is backward compatible; can toggle on/off.
- **Do this first:** Highest ROI on effort.

### 2. **Integrate AIS Vessel Tracking Data (MEDIUM ROI, 3-4 weeks)**
- **Why:** Parallax's Hormuz flow predictions are currently rule-based (cascade engine). Real-time vessel positions (AIS) provide ground-truth signals for validation and could improve prediction accuracy.
- **Impact:** Better signal validation; stronger historical eval on Hormuz traffic; potential for improved cascade calibration.
- **Effort:** Medium — API integration, dashboard layer, signal validation logic.
- **Risk:** Low — additive, non-critical path; can toggle on/off.
- **Provider:** Start with AIS Hub (cheaper) or MarineTraffic (more accurate); LSEG for Phase 2.

### 3. **Consolidate Eval Framework Into Langfuse for Phase 2 (MEDIUM ROI, 6-8 weeks)**
- **Why:** Parallax's custom eval table design is solid, but a unified observability platform (Langfuse = open-source, self-hosted) would reduce code and centralize prompt versioning, A/B testing, and eval metrics.
- **Impact:** Cleaner eval pipeline; easier prompt A/B testing; better audit trail.
- **Effort:** Medium — data migration, schema mapping, API integration.
- **Risk:** Vendor dependency (mitigated by open-source choice); requires Parallax to host Langfuse.
- **Timeline:** Phase 2 (after Phase 1 eval validation is complete).
- **Alternative:** Stay custom through Phase 1, adopt Langfuse in Phase 2 only if eval becomes a bottleneck.

---

## Sources

- [H3 GitHub Updates](https://upd.dev/uber/h3)
- [H3 Release (Ubuntu Packages)](https://ubuntuupdates.org/package/postgresql/jammy-pgdg/main/base/libh3-1)
- [deck.gl Official Site](https://deck.gl/)
- [CARTO: Making deck.gl AI-Ready](https://carto.com/blog/making-deckgl-ai-ready/)
- [2026 Geospatial Tools Deep Dive](https://www.youngju.dev/transcribe/culture/2026-05-16-map-geospatial-tools-2026-mapbox-maplibre-deck-gl-leaflet-protomaps-felt-deep-dive)
- [Amazon Redshift H3 Functions (2025)](https://aws.amazon.com/about-aws/whats-new/2025/01/amazon-redshift-new-geospatial-h3-indexing-functions/)
- [DuckDB H3 R Package (duckh3)](https://cran.r-project.org/web/packages/duckh3/index.html)
- [DuckDB Spatial Extension Talk](https://www.utwente.nl/evenementen/2024/5/1474788/talk-high-performance-spatial-data-management-and-analysis-with-duckdb)
- [LSEG Vessel Tracking API Launch (March 2026)](https://fintech.global/2026/03/20/lseg-launches-real-time-vessel-tracking-api/)
- [MarineTraffic G2 Reviews](https://www.g2.com/products/marinetraffic-marinetraffic/reviews)
- [AIS Hub API](https://public-api.org/api/1260/ais-hub)
- [World Monitor: Free Geopolitical Data APIs (2026)](https://www.worldmonitor.app/blog/posts/free-geopolitical-data-apis-2026/)
- [OilPriceAPI Documentation](https://docs.oilpriceapi.com/compare/eia-alternative)
- [FRED WTI Crude Oil Prices](https://fred.stlouisfed.org/graph?g=83wb)
- [EIA 2026 Oil Price Outlook](https://pboilandgasmagazine.com/eia-oil-price-to-average-58-per-barrel-in-2026-53-b-in-2027-after-69-b-in-2025/)
- [Prompt Management: Versioning, A/B Testing, Deployment](https://www.gmicloud.ai/en/blog/prompt-management-infrastructure-versioning-ab-testing-and-deployment-for-production-llm-apps)
- [Maxim AI: Top Prompt Versioning (2026)](https://www.getmaxim.ai/articles/top-5-prompt-versioning-platforms-in-2026/)
- [DeepEval vs PromptLayer (March 2026)](https://www.respan.ai/market-map/compare/deepeval-vs-promptlayer)
- [Braintrust, LangSmith, Agenta Comparison (Parse.gl)](https://www.parse.gl/prompts/p/i-want-to-ab-test-different-prompts-in-production-what-feature-flagging-platform-is-best-with-support-for-llm-evaluation--b862dc3c-e1ed-4564-a799-9628bbf2911b)
- [A/B Testing LLM Applications (Atlan, July 2026)](https://atlan.com/know/ab-testing-llm-applications.md)
- [LangGraph Alternatives (2026)](https://futureagi.com/blog/best-langgraph-alternatives-2026/)
- [CrewAI vs LangGraph vs AutoGen (2026)](https://futureagi.com/blog/crewai-vs-langgraph-vs-autogen-2026)
- [Microsoft Agent Framework vs AutoGen](https://next-it.co.id/blog/ai-agent-framework-comparison-2026-langchain-vs-crewai-vs-autogen-vs-pydanticai)
- [How Fast is DuckDB Really? (Fivetran)](https://www.fivetran.com/blog/how-fast-is-duckdb-really)
- [DuckDB Book Summary: Chapter 10](https://motherduck.com/duckdb-book-summary-chapter10/)
- [DuckDB in Depth: How It Works, What Makes It Fast](https://endjin.com/blog/duckdb-in-depth-how-it-works-what-makes-it-fast)
- [Rill Data: DuckDB OLAP Setup and Best Practices](https://docs.rilldata.com/reference/olap-engines/duckdb)
- [React + WebSocket Real-Time Applications (OneUptime, Jan 2026)](https://oneuptime.com/blog/post/2026-01-15-websockets-react-real-time-applications/)
- [React WebSocket: Real-time Connection (MaybeWorks)](https://maybe.works/blogs/react-websocket)
- [Robust React Native WebSocket Implementation (InstalGit)](https://instagit.com/facebook/react/react-native-websocket-robust-efficient-realtime-complex.md)
- [Langfuse: Open-Source LLM Observability](https://langfuse.com/)
- [DeepEval: LLM Evaluation Framework](https://github.com/confident-ai/deepeval)

---

## Notes

- No significant findings on H3 or deck.gl that would warrant changes to current stack; both are stable and current.
- Prompt caching is the highest-ROI near-term improvement (3-4 hours implementation, 20-30% budget savings).
- AIS vessel tracking could strengthen signal validation; worth piloting in Phase 1 if time permits.
- Eval platform consolidation deferred to Phase 2; current custom approach is sound.
- DuckDB performance is solid for Parallax's use case; no tuning needed until profiling shows bottlenecks.
