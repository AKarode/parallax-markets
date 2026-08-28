# Tech Research Report — 2026-08-28

**Focus Areas Researched:**
- Spatial/Geo: H3 updates, DuckDB extensions, visualization improvements
- LLM/Agent: Claude API enhancements, agent orchestration alternatives, structured output improvements
- Real-time Data: GDELT alternatives, shipping/AIS data sources, geopolitical event feeds
- Eval/MLOps: Prediction evaluation frameworks, prompt versioning, A/B testing
- Performance: DuckDB optimization, WebSocket tuning, React rendering for dashboards

---

## Key Findings

### Spatial & Geospatial

#### 1. H3-DuckDB Extension Maturity (HIGH relevance, LOW effort, MATURE)

**Finding:** Isaac Brodsky's H3-DuckDB extension is production-stable and actively maintained. New feature: WKT rendering of H3 hexagons directly in SQL enables fast polygon geometry conversion for visualization without runtime overhead.

**Status:** Already in Parallax stack (pinned). Extension is mature; no migration risk.

**Recommendation:** No action needed for Phase 1. For Phase 2, consider new WKT rendering for optimized hex-to-polygon conversion if visualization performance becomes bottleneck.

**Maturity:** Stable. Isaac Brodsky continues maintaining bindings across languages (Python, JavaScript, DuckDB).

---

#### 2. DuckDB Asynchronous I/O Coming in v2.0 (MEDIUM relevance, MEDIUM effort, BETA)

**Finding:** DuckDB v2.0 scheduled for fall 2026 adds async read support for Parquet and CSV, enabling non-blocking I/O when synchronous reads don't saturate available bandwidth. This improves throughput on cloud VMs with I/O variance.

**Applicability to Parallax:** Parallax uses Parquet for snapshots and live data replay. Async I/O could improve replay performance and reduce page load latency during dashboard initialization.

**Risk:** Beta feature; test thoroughly before deploying to production. DuckDB's DES engine is synchronous — async I/O won't help simulation ticks themselves, only pre-caching and background snapshot writes.

**Recommendation:** Monitor v2.0 release. Pilot async Parquet reads for dashboard queries (non-blocking data hydration). Consider for Phase 2 if dashboard load time is measured as a bottleneck.

---

#### 3. deck.gl H3HexagonLayer `highPrecision: 'auto'` (LOW relevance, LOW effort, STABLE)

**Finding:** `highPrecision: 'auto'` is now the default, automatically choosing between instanced rendering (fast, lower precision) and GPU-intensive high-precision based on viewport zoom and data size. Manual override via `highPrecision: false` forces low-precision for maximum performance.

**Status:** Parallax already uses deck.gl with H3HexagonLayer. This change is backward-compatible.

**Recommendation:** No action required. Current rendering already benefits from this optimization. If dashboard renders laggy during high-frequency updates, test `highPrecision: false` override on specific resolution bands.

---

### LLM & Agent Architecture

#### 4. Claude Prompt Caching in 2026 — TTL Change Impact (HIGH relevance, MEDIUM effort, IMPORTANT)

**Finding:** Anthropic quietly changed prompt cache TTL from 60 minutes to 5 minutes in early 2026. This directly impacts Parallax's cost model.

**Impact:** Agent system prompts (the expensive ~3K token baseline per country agent) were previously cached for 1 hour, reducing cost of sub-actor → country-agent cascade chains. With 5-minute TTL, cache hits become less likely in low-frequency scenarios.

**Parallax Mitigation:** Ensure all agent calls within a 5-minute window reuse the same system prompt version. Current architecture (GDELT 15-min cycle) means agent activations naturally cluster within cache windows.

**Recommended Action (PRIORITY):**
- Add cache hit tracking to budget_tracker.py. Log `cache_hit_rate` metric alongside LLM spend.
- Verify that daily cost stays within $20/day budget under real GDELT traffic patterns. If cache hit rate drops below 40%, consider:
  - Batching low-priority events to trigger agent decisions in clusters rather than scattered across 15-min windows.
  - Using prompt caching for the `curated_events` embedding model (all-MiniLM-L6-v2 context is static per scenario).

**Maturity:** Stable. This is Anthropic's current behavior.

---

#### 5. Batch API for Eval & Retrospective Analysis (MEDIUM relevance, LOW effort, STABLE)

**Finding:** Claude Batch API offers 50% cost discount and can process up to 10,000 requests/batch with 24-hour SLA. Ideal for non-realtime workloads.

**Parallax Use Case:** Daily eval cron job (compute hit rate, calibration curve, prompt improvement suggestions) is not time-critical. Moving to batch API cuts eval costs in half (~$0.10-0.20 per day instead of $0.35).

**Implementation:** Deferred from Phase 1. Eval pipeline currently uses Sonnet on-demand. For Phase 2, batch-process daily eval loop overnight.

**Risk:** Minimal. Eval job already runs post-hoc (after predictions resolve). 24-hour latency is acceptable.

---

#### 6. Structured Output Validation Improvements (HIGH relevance, MEDIUM effort, IMPORTANT)

**Finding:** As of August 2026, Claude's structured output (via tool-use wrapper) does NOT guarantee schema compliance. Anthropic's official docs state: "The strict parameter is currently ignored for tool definitions. Claude will make a best effort to provide valid arguments, but does not guarantee schema compliance."

**Parallax Status:** Parallax already validates agent outputs against JSON schema. Current approach:
- Malformed outputs are rejected and logged.
- Parser errors trigger a retry with simplified prompt.

**Risk/Opportunity:** Agent output validation is already defensive. No change needed for Phase 1. For Phase 2, consider adding output-validation layer (Pydantic AI or Instructor) if schema compliance becomes blocking.

**Recommendation:** Status quo is acceptable. Agent JSON schema in `decision` table is non-strict; cascade engine ignores malformed fields gracefully.

---

#### 7. Agent Orchestration Alternatives to LangGraph (MEDIUM relevance, HIGH effort, INFORMATIONAL)

**Finding:** LangGraph (graph-based), CrewAI (role-based swarm), and custom orchestration are the three primary patterns in 2026.

**Parallax Status:** Already uses custom Python asyncio orchestration with heapq DES. This is intentional and documented.

**Key Trade-off:**
- **LangGraph:** Handles complex multi-step workflows with state checkpoints. Overkill for Parallax's cascade rules and stateless agent decisions.
- **CrewAI:** Better for quick multi-agent setups with minimal code. Abstracts state management but less control over cascade logic.
- **Custom DES:** Parallax's choice. Full control, zero abstraction overhead, but requires careful testing.

**Recommendation:** No migration to LangGraph recommended for Phase 1. Custom DES is appropriate for Parallax's geopolitical cascade use case. Monitor CrewAI for Phase 2 if multi-agent complexity grows.

---

### Real-Time Data Sources

#### 8. Shipping/AIS Data APIs — Market Consolidation (HIGH relevance, HIGH effort, ACTIONABLE)

**Finding:** Kpler (formerly separate entities) now dominates maritime data:
- **Kpler AIS** (unified brand since Sept 2025): Acquired MarineTraffic, FleetMon, Spire Maritime. Provides real-time vessel tracking, predictive ETAs, terminal congestion signals.
- **Datalastic:** Most developer-friendly ship tracking API; tracks global tankers with laden/ballast detection.
- **SeaVantage:** Unified AIS endpoints for tankers, bulkers, containers, LNG with real-time and historical tracks.

**Parallax Opportunity:** Currently uses `searoute` for visualization geometry only (not for actual routing). Adding real-time AIS data enables:
1. **Actual vessel tracking:** Show live tanker positions in Hormuz corridor (Res 8 hexes).
2. **Rerouting signals:** Detect when tankers deviate to Cape of Good Hope route; feed as exogenous events to cascade engine.
3. **Supply shock validation:** Compare model-predicted flow reductions against observed vessel movements.

**Integration Effort:** MEDIUM-HIGH. Requires:
- New ingestion module: `ingestion/ais.py` (webhook or polling from Kpler/Datalastic).
- New table: `vessel_positions` (vessel_id, timestamp, h3_cell, lat_lng, laden_status).
- Dashboard layer: Overlay vessel markers on H3 map (separate deck.gl SymbolLayer).

**Cost:** Kpler/Datalastic charge ~$500-2000/month for production APIs. **Not in Phase 1 budget.** Deferred to Phase 2.

**Recommendation:** Spike integration with Datalastic or Kpler demo API. Verify that live vessel data produces measurable edge (e.g., predict flow _before_ official shipping reports). If validation shows value, fund Phase 2.

---

#### 9. GDELT Alternatives & Supplements (MEDIUM relevance, LOW effort, INFORMATIONAL)

**Finding:** No single replacement for GDELT. 2026 best practice: assemble multi-source stack.

| Source | Frequency | Coverage | Cost |
|--------|-----------|----------|------|
| GDELT (BigQuery) | 15 min | Global news events, high volume | Free ($0-5/month BigQuery) |
| ACLED | Weekly | Armed conflict, protests, validated | Free |
| UCDP | Quarterly | Conflict dyads, academic quality | Free (requires token auth) |
| USGS Earthquakes | Real-time | Seismic events (infrastructure risk) | Free |
| NASA FIRMS | 1-2 day | Fire detection via satellite | Free |

**Parallax Current Stack:** Google News RSS (free, 5-15 min) + GDELT BigQuery (15 min). Both reliable primary sources.

**Recommendation:** No change needed for Phase 1. GDELT + Google News RSS are sufficient. For Phase 2, consider adding ACLED as secondary source for validated conflict events (reduces noise filtering load).

---

### Eval & MLOps

#### 10. Prompt Versioning & A/B Testing Infrastructure (HIGH relevance, MEDIUM effort, IMPORTANT)

**Finding:** 2026 best practice for LLM production systems: prompt changes ship behind CI gate. Infrastructure must connect versioning → evaluation → staged deployment.

**Leading Platforms:**
- **Braintrust:** Environment-based deployment (dev/staging/prod). Prevents untested changes from production.
- **Langfuse:** Open-source LLM platform with deep observability + linear versioning (name + incrementing version).
- **PromptLayer:** Simplest versioning; automatic tracking of every LLM call.
- **Promptfoo:** Open-source CLI testing framework with YAML config for systematic prompt evaluation.

**Parallax Status:** Currently uses semver (`v1.2.0`) for agent prompts. Prediction log records prompt version. Daily cron identifies underperforming agents and flags manual prompt edits.

**Gap:** No automated staged deployment. Approved prompt edits immediately go live (no staging environment).

**Recommendation for Phase 2:**
1. Integrate Promptfoo for CI-gated prompt testing. YAML config defines baseline eval dataset + success criteria.
2. Add staging environment: deploy new prompts to subset of country agents (e.g., 20% of decisions). Monitor 7-day accuracy before full rollout.
3. Use Langfuse (open-source) for observability + prompt history. Tracks which prompt version generated each prediction.

**Effort:** MEDIUM. Requires:
- Pytest integration for Promptfoo (5-10 hours).
- Staging deployment logic in decision router (2-3 hours).
- Langfuse setup + SDK integration (4-5 hours).

**ROI:** Reduces risk of bad prompt deployments. Enables confident experimentation on eval improvements.

---

#### 11. LLM Evaluation Frameworks (HIGH relevance, MEDIUM effort, IMPORTANT)

**Finding:** 2026 evaluation landscape emphasizes **traceability**: link any score back to exact prompt version, model version, and test case.

**Key Tools:**
- **Braintrust:** Scalable evaluation, production feedback loop, traceability built-in.
- **MLflow:** Open-source ML lifecycle tool with LLM eval support. Heavier setup than Braintrust but integrates with Databricks.
- **DeepEval:** Lightweight eval framework with RAGAS metrics (retrieval, answer relevance, faithfulness).

**Parallax Current Approach:**
- Direction, magnitude, sequence accuracy scoring (custom Python functions).
- Calibration curve (rolling 30-day window).
- Causal tagging (model_error, exogenous_shock, data_lag, ambiguous).

**Gap:** No traceability system. Eval results stored in `eval_results` table but not linked back to exact prompt version, model version, or prediction dataset snapshot.

**Recommendation for Phase 2:**
1. Add `eval_dataset_id` and `eval_run_id` to scoring pipeline. Create snapshots of test data and prompt versions before evaluation.
2. Integrate Braintrust SDK (if budget allows) or implement lightweight custom traceability (recommended).
3. Dashboard query: "Show calibration curve for Iran/Khamenei v1.2.0 vs v1.2.1 over last 7 days."

**Effort:** LOW-MEDIUM. Traceability can be done with custom schema (3-4 hours) or Braintrust SDK (6-8 hours).

---

### Performance & WebSocket Optimization

#### 12. React 19 + TanStack Query for Real-Time Dashboards (HIGH relevance, LOW effort, READY-TO-USE)

**Finding:** TanStack Query (formerly React Query) delivers 3x faster sync than Redux by decoupling cache from UI re-renders. 2026 default dashboard stack: React 19 + Vite + shadcn/ui + TanStack Query.

**Parallax Current Stack:** React 18 + Vite + Vite + deck.gl. **No TanStack Query.**

**Current Issue:** Dashboard state management uses useState + WebSocket mutations directly into React state. High-frequency updates (cell_updates every tick) cause render thrashing on deck.gl canvas.

**Current Workaround:** Spec section 5 documents a solution—H3 hex data lives in useRef (mutable), not useState. Works but bypasses React's reconciliation; makes components harder to reason about.

**Benefit of TanStack Query:**
- Decouples server state (WebSocket data) from UI state (indicators, feed).
- Automatic background refetch, stale-while-revalidate, deduplication.
- WebSocket integration via `setQueryData` hook — clean separation.
- Built-in optimistic updates for user actions.

**Recommended Action (Phase 2):**
1. Upgrade React 18 → 19. Backwards compatible; no breaking changes.
2. Add TanStack Query for:
   - `useQuery('cellUpdates', fetchCellData)` → mutable server state for deck.gl.
   - `useQuery('indicators', fetchIndicators)` → reactive UI cards (price, flow, escalation).
   - `useQuery('agentDecisions', fetchAgentFeed)` → scrolling agent activity feed.
3. Remove manual useRef workaround. TanStack Query + Suspense handles high-frequency updates natively.

**Effort:** MEDIUM. Requires refactoring data-fetching layer (~10-15 hours). Low risk; TanStack Query is production-proven.

**Maturity:** Stable. TanStack Query v5 is widely used; React 19 just reached stable (August 2026).

---

#### 13. WebSocket Optimization for High-Frequency Updates (MEDIUM relevance, MEDIUM effort, IMPLEMENTABLE)

**Finding:** WebSocket performance under 10k+ events/second requires:
1. Efficient encoding (Protocol Buffers or MessagePack, not JSON).
2. Message batching (buffer 100ms, flush once) to reduce per-message overhead.
3. Ping/pong frames for dead connection detection.
4. Graceful reconnection with backoff.

**Parallax Current Status:**
- WebSocket sends updates as JSON strings.
- No explicit message batching or encoding optimization.
- Spec documents batching strategy (100ms buffer) but implementation unclear.

**Recommended Action (Phase 2):**
1. Benchmark current throughput under 100+ concurrent WebSocket clients (simulate dashboard load).
2. If bottleneck: switch to MessagePack encoding for WebSocket payloads (~40% smaller than JSON).
3. Verify batching in place: batch incoming updates for 100ms, flush as single mutation.
4. Add Prometheus metrics: `websocket_message_latency_ms`, `batched_updates_per_flush`, `connection_churn`.

**Effort:** MEDIUM. Encoding switch is straightforward (~3-4 hours). Metrics instrumentation (~2-3 hours).

**Risk:** Low. Changes are backward-compatible if wrapped in version-aware encoding negotiation.

---

#### 14. DuckDB Performance Tuning for Simulation Queries (MEDIUM relevance, MEDIUM effort, IMMEDIATE)

**Finding:** Key DuckDB optimization patterns for Phase 1 right now:
1. **Use EXPLAIN ANALYZE before/after query changes.** Cardinality estimation problems are common; ANALYZE updates statistics and often resolves them instantly.
2. **Parquet with column pruning and predicate pushdown:** 60x faster than CSV on filtered queries.
3. **Partition pruning:** Automatically skips partitions. Approximately 12x speedup.
4. **ENUM types for strings:** Reduces storage and improves filter performance.
5. **Temp directories for spilling:** Configure `temp_directory` for disk spillover if RAM is constrained.

**Parallax Application:**
- `world_state_delta` table: PARTITION BY date (daily). Queries for "current tick" or "last 24 hours" automatically prune.
- `decisions` and `predictions` tables: Convert `agent_id`, `action_type`, `prediction_type` to ENUM to reduce storage.
- Dashboard queries: Use SELECT with specific columns (not SELECT *). Parquet column pruning will skip unneeded data.

**Recommendation (Immediate for Phase 1):**
1. Add EXPLAIN ANALYZE output to CI pipeline. Run on key queries (e.g., "reconstruct world state from delta + snapshot").
2. Verify partition pruning on `world_state_delta` queries. Example:
   ```sql
   SELECT * FROM world_state_delta WHERE date >= CURRENT_DATE - 7;
   ```
   Should report "Partitions scanned: 7" not "Partitions scanned: all".
3. Convert agent_id, action_type to ENUM on table creation.

**Effort:** LOW. Mostly configuration + verification (~2-3 hours).

---

## Summary: Top 3 Recommendations

### 1. **Add Real-Time AIS Data Ingestion (Phase 2, HIGH value)**

**What:** Integrate Kpler or Datalastic vessel tracking API to ingest live tanker positions into H3 cells.

**Why:** Enables validation of model predictions against ground truth. If model predicts 30% flow reduction due to blockade, but AIS shows tankers still moving, catch the model error early.

**Effort:** MEDIUM-HIGH (40-60 hours for MVP). Cost: $500-2000/month API access.

**Risk:** API dependency; requires monitoring for service degradation.

**Payoff:** Unlocks continuous feedback loop for prompt improvement. Turns Parallax from "interesting sim" to "production edge-finder."

---

### 2. **Prompt Versioning + Staged Deployment Infrastructure (Phase 2, MEDIUM value)**

**What:** Integrate Promptfoo for CI-gated prompt testing + staging environment for A/B testing new prompts on 20% of decisions before full rollout.

**Why:** Reduces risk of bad prompt changes. Enables confident experimentation (e.g., "Try more aggressive Iran prompts"). Traceability is now industry standard.

**Effort:** MEDIUM (20-30 hours). Open-source tooling (Promptfoo + custom staging logic).

**Cost:** Zero additional (no external SaaS).

**Payoff:** Faster iteration on prompt improvement. Confidence in prod deployments.

---

### 3. **Upgrade to React 19 + TanStack Query (Phase 2, LOW complexity)**

**What:** Replace manual useRef workaround with TanStack Query for server state management. Upgrade React 18 → 19.

**Why:** Cleaner code. Better performance under high-frequency WebSocket updates. Production-standard pattern.

**Effort:** MEDIUM (15-20 hours). Low risk; backwards-compatible.

**Payoff:** Better developer experience, measurable performance gains (3x faster sync per TanStack docs).

---

## No-Action Items (Already Handled or Out of Scope)

- **H3-DuckDB Extension:** Already pinned and stable. No upgrade needed for Phase 1.
- **deck.gl H3HexagonLayer:** Auto-tuned via `highPrecision: 'auto'`. No action.
- **GDELT Alternatives:** Current stack (Google News RSS + GDELT) is solid. ACLED is a nice-to-have supplement in Phase 2.
- **Structured Output Validation:** Already defensive; JSON schema validation on agent outputs is working.
- **Agent Orchestration Frameworks:** Custom DES is appropriate. LangGraph/CrewAI are alternatives if needs change.

---

## Sources

### Spatial & Geospatial
- [H3-DuckDB Extension](https://github.com/isaacbrodsky/h3-duckdb)
- [Awesome DuckDB Spatial](https://github.com/alperdincer/Awesome-DuckDB-Spatial)
- [DuckDB is probably the most important geospatial software of the last decade](https://news.ycombinator.com/item?id=43881468)
- [deck.gl What's New](https://deck.gl/docs/whats-new)

### LLM & Agent
- [Claude Prompt Caching in 2026: The 5-Minute TTL Change](https://dev.to/whoffagents/claude-prompt-caching-in-2026-the-5-minute-ttl-change-thats-costing-you-money-4363)
- [Batch Processing - Claude Platform Docs](https://platform.claude.com/docs/en/build-with-claude/batch-processing)
- [Evaluating LLM Structured Output Modes (2026)](https://futureagi.com/blog/evaluating-llm-structured-output-modes-2026/)
- [The best AI agent frameworks in 2026](https://www.langchain.com/resources/ai-agent-frameworks)

### Real-Time Data
- [Oil Tanker Tracker API - Datalastic](https://datalastic.com/blog/oil-tanker-tracker-api/)
- [Real-Time Vessel Tracking & AIS Data | SeaVantage](https://www.seavantage.com/real-time-crude-oil-tanker-vessel-tracking-analytics)
- [Free Geopolitical Data APIs 2026 | WorldMonitor](https://www.worldmonitor.app/blog/posts/free-geopolitical-data-apis-2026/)
- [GDELT Project for News Data 2026](https://dataresearchtools.com/gdelt-project-for-news-data-2026-free-alternative-to-newsapi/)

### Eval & MLOps
- [Best LLM evaluation tools with SDK integrations (2026) - Braintrust](https://www.braintrust.dev/articles/best-llm-evaluation-tools-integrations-2025)
- [Top 5 Prompt Versioning Platforms in 2026](https://www.getmaxim.ai/articles/top-5-prompt-versioning-platforms-in-2026/)
- [Best Prompt Testing Frameworks in 2026: 7 Compared](https://futureagi.com/blog/best-prompt-testing-frameworks-2026/)
- [Top 7 Braintrust Alternatives and Competitors, Compared (2026)](https://www.confident-ai.com/knowledge-base/compare/top-braintrust-alternatives-and-competitors-compared)

### Performance & WebSocket
- [React Server Components + TanStack Query: The 2026 Data-Fetching Power Duo](https://dev.to/krish_kakadiya_5f0eaf6342/react-server-components-tanstack-query-the-2026-data-fetching-power-duo-you-cant-ignore-21fj)
- [WebSocket Streaming in 2025: Real-Time Data, Protocols, and Implementation](https://www.videosdk.live/developer-hub/websocket/websocket-streaming)
- [WebSockets vs Server-Sent Events vs gRPC Streaming in 2026](https://techai-explained.github.io/techai-explained/articles/websockets-vs-sse-vs-grpc/)
- [DuckDB Performance Tuning: 5 Tips from Slow Queries to Millisecond Response](https://duckdblab.org/en/post/duckdb-performance-tuning-5-tips/)
- [DuckDB Parquet Performance Guide](https://duckdblab.org/en/post/duckdb-parquet-performance-guide/)

---

**Report Date:** 2026-08-28  
**Next Review:** 2026-09-25 (monthly cadence)
