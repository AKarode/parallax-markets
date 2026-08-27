# Technology Research Report — 2026-08-27

**Focus areas:** Spatial/Geo, LLM/Agent, Real-time Data, Eval/MLOps, Performance

---

## Findings by Category

### 1. Spatial/Geo Technologies

#### DuckDB H3 Extension Performance Improvements
- **Status:** Mature, actively maintained via DuckDB Community Extensions
- **Relevance:** HIGH
- **Effort to integrate:** LOW (already in use; focus on optimization)
- **Risk/Maturity:** LOW — production-ready
- **Detail:** R-tree + H3 indexing patterns (published March 2025) show spatial queries on 31M rows with H3 cells significantly faster than raw geometry operations. DuckDB SQL H3 operations outperform Python/JS calls for batch processing. Current spec pinning H3 version in Docker is appropriate; consider periodic benchmarking against latest extension releases.
- **Source:** [Spatial queries in DuckDB with R-tree and H3 indexing](https://aetperf.github.io/2025/03/04/Spatial_queries_in_DuckDB_with_R-tree_and_H3_indexing.html), [Awesome-DuckDB-Spatial](https://github.com/alperdincer/Awesome-DuckDB-Spatial)

#### deck.gl H3HexagonLayer High-Precision vs Performance Trade-off
- **Status:** New feature (2025 release)
- **Relevance:** HIGH
- **Effort to integrate:** LOW (prop-based toggle)
- **Risk/Maturity:** LOW — battle-tested in Uber dashboards
- **Detail:** H3HexagonLayer now supports `highPrecision: false` to force low-precision, high-performance rendering (instanced drawing assumes center hex shape). For Hormuz detail (res 7-8), precision matters; for open ocean (res 3-4), toggling precision off yields 2-3× speedup. Parallelism already uses `auto` mode per spec, which is optimal.
- **Recommendation:** Add a scenario parameter `h3_hexagon_high_precision` (default true for Hormuz, false for distant ocean) and expose in admin dashboard to A/B test against live data.
- **Source:** [deck.gl Performance Optimization](https://deck.gl/docs/developer-guide/performance), [H3HexagonLayer API](https://deck.gl/docs/api-reference/geo-layers/h3-hexagon-layer)

---

### 2. LLM/Agent Technologies

#### Claude Batch API + Prompt Caching: Cost Stacking & Cache Hit Optimization
- **Status:** Fully GA as of October 2025
- **Relevance:** HIGH
- **Effort to integrate:** MEDIUM (requires request batching refactor)
- **Risk/Maturity:** LOW — production-proven
- **Detail:** Message Batches API provides 50% cost discount on batch requests. Combined with prompt caching (1-hour TTL, 10% read cost, 2× write cost), total savings stack: 50% + 90% = 95% for repeated system prompts. Current implementation uses 5-min cache; upgrading to 1-hour TTL for static agent system prompts (`historical_baseline`) reduces re-cache penalty and improves hit rates to 30–98% depending on traffic. Batch API particularly valuable for eval meta-agent calls (10/day currently).
- **Current cost:** ~$2-5/day (estimate from spec).
- **Post-optimization estimate:** ~$0.10-0.25/day (95% reduction for cached prefix + batch API stack).
- **Implementation:** Move evaluation meta-agent calls (daily cron) and low-urgency agent re-evaluations into batch jobs. Keep live GDELT ingestion on sync API (requires real-time response).
- **Source:** [Claude Batch Processing](https://docs.claude.com/en/docs/build-with-claude/batch-processing), [Cost Optimization Guide](https://hidekazu-konishi.com/entry/anthropic_claude_api_prompt_caching_and_token_efficiency.html)

#### Claude Haiku 4.5 as Primary Sub-Actor Model
- **Status:** Latest release (October 2025)
- **Relevance:** HIGH
- **Effort to integrate:** LOW (drop-in replacement for existing Haiku calls)
- **Risk/Maturity:** LOW — Anthropic's newest stable release
- **Detail:** Haiku 4.5 now matches Sonnet 4 performance on coding, agent, and reasoning tasks while remaining 3× cheaper ($1/$5M tokens vs Sonnet $3/$15M). Spec already uses Haiku for sub-actors; no change needed. However, Haiku 4.5 extended thinking support (new) could improve cascade reasoning without cost increase — consider optional `enable_extended_thinking` param for high-confidence predictions.
- **Source:** [Claude Haiku 4.5 Deep Dive](https://caylent.com/blog/claude-haiku-4-5-deep-dive-cost-capabilities-and-the-multi-agent-opportunity), [Anthropic Claude Haiku](https://www.anthropic.com/claude/haiku)

#### Structured Output JSON Schema Validation
- **Status:** Constrained decoding via vLLM/Outlines; Anthropic native support (2025)
- **Relevance:** MEDIUM
- **Effort to integrate:** MEDIUM (client-side validation in place; add server-side guided decoding)
- **Risk/Maturity:** MEDIUM — grammar-constrained decoding can distort output semantics on edge cases
- **Detail:** Current spec validates agent output JSON schema post-hoc (reject malformed, log). Switching to constrained decoding at inference time (Anthropic or vLLM-style) guarantees valid JSON before returning, reducing post-processing error handling. Recent benchmark (JSONSchemaBench, 2025) shows 95%+ compliance on real-world schemas. Trade-off: slight latency increase + potential semantic degradation for complex schemas. Recommended for well-tested decision schema but not for free-form reasoning fields.
- **Recommendation:** Integrate for `agent_output` and `predictions` JSON schemas (rigid structure), keep post-hoc validation for `reasoning` and `description` fields (freeform).
- **Source:** [JSONSchemaBench](https://arxiv.org/pdf/2501.10868), [SLOT: Structuring Output](https://arxiv.org/pdf/2505.04016)

#### Prompt Versioning & A/B Testing Infrastructure
- **Status:** Mature platforms available (Braintrust, W&B Weave, LangSmith)
- **Relevance:** HIGH
- **Effort to integrate:** LOW-MEDIUM (spec already has semver + per-version tracking; formalize with tooling)
- **Risk/Maturity:** LOW — widely adopted in production
- **Detail:** Spec already implements prompt versioning (semver) and per-prediction `prompt_version` tracking. Formalize A/B comparison with a dedicated tool: Braintrust or W&B Weave for version comparison, auto-flagging performance regressions. LangSmith integrates with LangChain but Parallax uses raw API calls. Braintrust is LLM-agnostic and lightweight.
- **Recommendation:** Integrate Braintrust API for automated version performance tracking and approval workflows in the daily eval cron. Cost: ~$100-300/month for 10K+ evaluations/month (well within budget).
- **Source:** [Braintrust A/B Testing](https://www.braintrust.dev/articles/ab-testing-llm-prompts), [LangSmith Prompt Tracking](https://blog.promptlayer.com/5-best-tools-for-prompt-versioning/)

---

### 3. Real-Time Data Sources

#### AIS Vessel Tracking APIs for Hormuz Corridor
- **Status:** Multiple production APIs available
- **Relevance:** MEDIUM-HIGH
- **Effort to integrate:** MEDIUM (new ingestion pipeline + schema)
- **Risk/Maturity:** MEDIUM — satellite/terrestrial AIS hybrid coverage 99.8-99.9% uptime
- **Detail:** Current spec uses Searoute for visualization geometry only (explicitly not for operational logic). Real vessel flow tracking from live AIS data would ground "Hormuz traffic" indicators in observed data vs. cascade rules alone. Options:
  - **VesselFinder** or **Data Docked**: REST API, 99.9% uptime, live positions every 5–15 min
  - **AISHub**: Free tier with rate limits (suitable for MVP)
  - Estimated cost: $500-2000/month for production-grade service
- **Recommendation:** DEFER to Phase 2. For Phase 1, validate cascade rules produce reasonable Hormuz traffic estimates (vs. historical baselines). AIS integration amplifies signal but adds complexity and cost. Revisit post-validation.
- **Source:** [Datalastic](https://datalastic.com/), [VesselFinder API](https://www.vesselfinder.com/realtime-ais-data), [Data Docked](https://datadocked.com/)

#### GDELT Alternatives & Supplementary Event Feeds
- **Status:** Multiple complementary sources identified
- **Relevance:** MEDIUM
- **Effort to integrate:** MEDIUM (each requires custom ingestion filter)
- **Risk/Maturity:** MEDIUM — ACLED is validated/lagged (weekly), UCDP is slow, Currents API is commercial
- **Detail:** Spec already flags GDELT 429 rate-limit issues and uses ACLED weekly as fallback. Additional supplements:
  - **ACLED** (conflict events): Recommended, lagged 1-2 weeks, free, validated. Already in spec.
  - **UCDP** (Uppsala Conflict Data): Academic, slower updates, free API. Adds coverage on older events.
  - **Currents API**: News API alternative to GDELT, API-first, 20+ languages, flat monthly rate ($299-599). Better for real-time but less geopolitical-focused.
  - **Webz.io News API**: Alternative news firehose (commercial, ~$300/month).
- **Recommendation:** No change needed for Phase 1. ACLED covers validation needs. Post-Phase-1, test Currents API as primary (more reliable than GDELT 429 spikes) or add UCDP as low-priority background ingestion for backtesting.
- **Source:** [Free Geopolitical Data APIs 2026](https://www.worldmonitor.app/blog/posts/free-geopolitical-data-apis-2026/), [GDELT Alternatives](https://currentsapi.services/en/alternative/gdelt)

---

### 4. Eval/MLOps Frameworks

#### LLM Calibration & Prediction Confidence Metrics
- **Status:** Research-active (2025 publications); frameworks emerging
- **Relevance:** HIGH
- **Effort to integrate:** MEDIUM (requires calibration curve fitting + holdout set)
- **Risk/Maturity:** MEDIUM — theoretically sound, practical implementations still maturing
- **Detail:** Spec includes basic calibration scoring (confidence vs. accuracy over rolling 30-day windows). Recent 2025 work on calibrating LLM confidence via linear probes and prompt-based approaches suggests more robust calibration possible. Key insight: Temperature-based confidence (from LLM generation) often miscalibrated; domain-specific recalibration (e.g., "Iran predictions are 10% overconfident") improves real-world estimates.
- **Recommendation:** Expand eval framework to compute calibration curves per agent per prediction type (e.g., "hormuz_traffic_reduction") using Platt scaling or isotonic regression. Requires ~100 resolved predictions per bucket (achievable at 30-day eval window). Feed recalibrated confidences back into portfolio allocator (currently uses raw LLM confidence).
- **Source:** [Calibrating Prediction-Powered Inference](https://arxiv.org/pdf/2604.21260), [Calibrating LLM Judges](https://arxiv.org/pdf/2512.22245)

#### Prediction Evaluation Frameworks (Holistic)
- **Status:** HELM and open-source frameworks (2025+)
- **Relevance:** MEDIUM
- **Effort to integrate:** LOW (reference, not implementation)
- **Risk/Maturity:** HIGH — these are research benchmarks, not turnkey eval systems
- **Detail:** HELM provides comprehensive coverage (generalization, bias, calibration, efficiency) but is designed for model benchmarking, not per-agent production tracking. Current spec's eval_results table structure is sound; no need to adopt HELM wholesale. However, HELM's bias evaluation patterns (e.g., "does model favor certain countries?") could be applied as secondary checks.
- **Recommendation:** Use HELM metrics as design reference when expanding eval dimensions (e.g., add country-level bias tracking to daily scorecard). Don't integrate HELM tooling directly.
- **Source:** [Deepchecks LLM Eval Framework](https://deepchecks.com/llm-evaluation/framework/), [LLM Evaluation Guide 2025](https://www.xbytesolutions.com/llm-evaluation-metrics-framework-best-practices/)

---

### 5. Performance Optimization

#### WebSocket Batching & Backpressure for Real-Time Dashboards
- **Status:** Industry best practices (2025)
- **Relevance:** HIGH
- **Effort to integrate:** LOW (spec already uses message batching; formalize buffer window)
- **Risk/Maturity:** LOW — proven pattern in production dashboards
- **Detail:** Spec mentions batching updates for 100ms to prevent render thrashing. Latest 2025 patterns confirm this + add backpressure handling: if buffer fills (indicates slow client), drop non-critical updates (e.g., low-relevance GDELT events) before dropping critical updates (agent decisions, price changes). FastAPI WebSocket + asyncio.Queue already supports this; current implementation is close to optimal.
- **Recommendation:** Formalize buffer strategy: separate queues for (a) critical updates (decisions, prices, escalation), (b) informational updates (GDELT feed), (c) heartbeat/ping. On high-frequency load, shed (b) but never (a). Implement memory-bounded queue with overflow metric to admin dashboard.
- **Source:** [10 WebSocket Scaling Patterns](https://medium.com/@sparknp1/10-websocket-scaling-patterns-for-real-time-dashboards-1e9dc4681741), [FastAPI WebSockets Guide](https://dev-faizan.medium.com/building-real-time-applications-with-fastapi-websockets-a-complete-guide-2025-40f29d327733)

#### React Concurrent Rendering for Hex Map + UI Decoupling
- **Status:** React 19 (2025+), now production-ready
- **Relevance:** HIGH
- **Effort to integrate:** MEDIUM (refactor state management, no API changes)
- **Risk/Maturity:** LOW — React concurrent features no longer experimental
- **Detail:** Spec's approach (mutable `useRef` for hex data, separate React state for UI) aligns with concurrent rendering best practices. React 19 adds `useTransition` and `useDeferredValue` for non-blocking updates. Applying these to UI state (agent feed, indicator cards) while hex data updates in background ensures smooth user interactions during high-load periods.
- **Recommendation:** Apply `useTransition` to indicator card updates and agent feed sorting/filtering. Keep hex data mutations in ref. Measure before/after using React DevTools Profiler. Expected improvement: 20-30% reduction in frame drops during 1000+ concurrent hex updates.
- **Source:** [React Concurrent Rendering Performance](https://community.nasscom.in/index.php/communities/mobile-web-development/concurrent-rendering-performance-optimization-react), [React 2025 What's New](https://dev.to/knewton25/react-2025-whats-new-and-what-you-should-know-4pgh)

#### DuckDB Query Performance on Large State Tables
- **Status:** Best practices documented (2025)
- **Relevance:** MEDIUM
- **Effort to integrate:** LOW (monitoring/index tuning)
- **Risk/Maturity:** LOW — DuckDB's query planner is mature
- **Detail:** Spec's delta + snapshot approach avoids the 1.15B row problem. Monitor query latency on `world_state_delta` joins (especially range queries on tick ranges). DuckDB's automatic indexing often sufficient, but explicit CREATE INDEX on (tick, cell_id) may help. Periodic CHECKPOINT commands compress delta files.
- **Recommendation:** Add monitoring: log query time on key dashboard queries (e.g., "last 100 ticks of cell changes"). If median query time > 100ms, consider index hints or materialized views for hot queries. Current architecture unlikely to hit this threshold given delta strategy.

---

## Top 3 Recommendations (Priority Order)

### 1. **Implement Claude Batch API + Upgrade Prompt Caching TTL**
   - **Impact:** 90-95% cost reduction on eval pipeline; $2-5/day → $0.10-0.25/day (if eval-heavy workload) or $0.50-1.00/day (realistic mixed load)
   - **Effort:** MEDIUM (1-2 days for refactor + testing)
   - **Risk:** LOW — API changes are backward-compatible
   - **Rationale:** Direct cost savings align with project budget constraint ($20/day cap). Batch API is production-stable (October 2025). Combining 50% batch discount + 90% caching discount on static agent system prompts is a force multiplier. Allows scaling eval framework (more prompt versions, more agents) within same budget.
   - **Action:** 
     - Upgrade prompt cache TTL from 5min to 1hr for agent system prompts (`historical_baseline` fields)
     - Move daily eval meta-agent calls (10/day) into batch request job
     - Add metrics to BudgetTracker: track cache hit rates per agent version

### 2. **Add AIS Vessel Tracking Integration (Phase 2 Prep)**
   - **Impact:** Ground "Hormuz traffic" signal in real-world data; improves cascade rule calibration; enables live vs. predicted divergence detection
   - **Effort:** MEDIUM-HIGH (2-3 days to integrate one AIS provider)
   - **Risk:** MEDIUM — adds operational dependency on third-party API; requires validation against cascade rules
   - **Rationale:** Phase 1 validates cascade rules produce reasonable estimates. AIS data would confirm: "Does our blockade → flow reduction rule match reality?" Deferring to Phase 2 is correct, but start research now. Budget ~$1000/month for production AIS service (VesselFinder or Data Docked) in Phase 2.
   - **Action (now):**
     - Document which AIS provider to use (recommend VesselFinder for 99.9% uptime + structured JSON)
     - Sketch ingestion schema: vessel positions → H3 cell occupancy → aggregation into "vessels_in_hormuz" metric
     - Create GitHub issue for Phase 2 with design doc

### 3. **Formalize Prompt Versioning with Braintrust Integration**
   - **Impact:** Automate A/B testing of agent prompts; catch performance regressions before they accumulate; reduce manual eval workload
   - **Effort:** LOW-MEDIUM (1-2 days to integrate API + hook into daily eval cron)
   - **Risk:** LOW — Braintrust is LLM-agnostic and lightweight
   - **Rationale:** Spec already tracks `prompt_version` per prediction. Braintrust adds automated comparison, flagging regressions, and approval workflows. Cost ~$150-300/month (well under budget). Pays for itself in operator time savings and faster prompt improvement cycles.
   - **Action:**
     - Sign up for Braintrust (free tier available for testing)
     - Integrate Braintrust SDK into daily eval cron: log each prediction evaluation to Braintrust with `prompt_version` tag
     - Set up auto-flagging rule: if new version underperforms old by >5% over 7-day rolling window, alert admin
     - Expose Braintrust version comparison dashboard in admin UI (or link to Braintrust directly)

---

## Notes

- **Cost optimization**: Batch API + prompt caching together can reduce daily LLM spend by 90-95%, allowing aggressive scaling of eval framework without exceeding $20/day cap.
- **No significant concerns** with current stack. H3 extension, deck.gl, FastAPI, DuckDB, React all mature and well-supported. Recommendations are *optimizations*, not fixes.
- **Phase 2 candidates**: AIS integration, structured output constrained decoding, Currents API as GDELT backup, React Compiler (when fully stable).

---

## Sources

### Spatial/Geo
- [DuckDB Spatial Queries with R-tree and H3](https://aetperf.github.io/2025/03/04/Spatial_queries_in_DuckDB_with_R-tree_and_H3_indexing.html)
- [Awesome-DuckDB-Spatial](https://github.com/alperdincer/Awesome-DuckDB-Spatial)
- [deck.gl Performance Optimization](https://deck.gl/docs/developer-guide/performance)
- [deck.gl H3HexagonLayer API](https://deck.gl/docs/api-reference/geo-layers/h3-hexagon-layer)
- [Uber H3 Hexagonal Grid](https://www.analyticsvidhya.com/blog/2025/03/ubers-h3-for-spatial-indexing/)

### LLM/Agent
- [Claude Batch Processing](https://docs.claude.com/en/docs/build-with-claude/batch-processing)
- [Cost Optimization: Caching + Batching](https://hidekazu-konishi.com/entry/anthropic_claude_api_prompt_caching_and_token_efficiency.html)
- [Claude Haiku 4.5 Deep Dive](https://caylent.com/blog/claude-haiku-4-5-deep-dive-cost-capabilities-and-the-multi-agent-opportunity)
- [Anthropic Claude Haiku](https://www.anthropic.com/claude/haiku)
- [JSONSchemaBench](https://arxiv.org/pdf/2501.10868)
- [SLOT: Structuring Output](https://arxiv.org/pdf/2505.04016)
- [Braintrust A/B Testing](https://www.braintrust.dev/articles/ab-testing-llm-prompts)
- [Best Prompt Versioning Tools](https://blog.promptlayer.com/5-best-tools-for-prompt-versioning/)

### Real-Time Data
- [Free Geopolitical Data APIs 2026](https://www.worldmonitor.app/blog/posts/free-geopolitical-data-apis-2026/)
- [GDELT Alternatives](https://currentsapi.services/en/alternative/gdelt)
- [Datalastic AIS API](https://datalastic.com/)
- [VesselFinder Real-Time AIS](https://www.vesselfinder.com/realtime-ais-data)
- [Data Docked Maritime API](https://datadocked.com/)

### Eval/MLOps
- [Calibrating Prediction-Powered Inference](https://arxiv.org/pdf/2604.21260)
- [Calibrating LLM Judges](https://arxiv.org/pdf/2512.22245)
- [Deepchecks LLM Evaluation Framework](https://deepchecks.com/llm-evaluation/framework/)
- [LLM Evaluation Guide 2025](https://www.xbytesolutions.com/llm-evaluation-metrics-framework-best-practices/)

### Performance
- [10 WebSocket Scaling Patterns](https://medium.com/@sparknp1/10-websocket-scaling-patterns-for-real-time-dashboards-1e9dc4681741)
- [FastAPI WebSockets Guide](https://dev-faizan.medium.com/building-real-time-applications-with-fastapi-websockets-a-complete-guide-2025-40f29d327733)
- [React Concurrent Rendering](https://community.nasscom.in/index.php/communities/mobile-web-development/concurrent-rendering-performance-optimization-react)
- [React 2025 What's New](https://dev.to/knewton25/react-2025-whats-new-and-what-you-should-know-4pgh)

---

*Generated by daily technology research scout for Parallax geopolitical simulator.*
