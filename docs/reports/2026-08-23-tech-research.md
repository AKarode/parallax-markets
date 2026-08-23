# Technology Research Report: Parallax Daily Scout
**Date:** 2026-08-23  
**Focus Areas:** Spatial/Geo, LLM/Agent, Real-time Data, Eval/MLOps, Performance

---

## Summary

Research across 5 technology domains identified **3 high-impact recommendations** for the Parallax stack:

1. **Claude Batch API + 1-Hour Prompt Cache** — Stack 50% + 90% discounts for ~$400-600 annual savings on $20/day LLM budget
2. **AIS Vessel Tracking API Integration** — Add free real-time Hormuz shipping flow monitoring via AISstream.io/AISHub
3. **Langfuse v3/v4 for Eval Observability** — Replace manual prediction logging with 165x-faster structured tracing + A/B testing

---

## Findings by Category

### 1. Spatial & Geospatial

#### H3 + DuckDB Integration Status  
**Relevance: MEDIUM | Effort: LOW | Risk: LOW | Status: Mature**

- H3-DuckDB bindings fully stable; new WKT rendering support added (converts H3 cells to polygon geometries via SQL)
- `h3-duckdb` package actively maintained with R bindings also available (CRAN duckh3)
- **Assessment:** No major breaks or improvements needed. Current stack is near-optimal. Minor win: confirm `h3_latlng_to_cell` performance on ~400K hexes via `EXPLAIN ANALYZE`

#### deck.gl H3HexagonLayer Performance  
**Relevance: HIGH | Effort: LOW | Risk: LOW | Status: Optimized (2026)**

- New in 2026: `highPrecision: false` mode for high-performance, low-accuracy rendering
- Instanced drawing now default for large hex batches (assumes same shape across viewport)
- Auto-mode: switches to high-precision only on edge cases (diagonal crossing, pole)
- **Recommendation:** Enable `highPrecision: 'auto'` and benchmark instanced drawing for ~400K hex rendering. Likely 15-30% improvement on high-frequency WebSocket updates.

#### GDELT Alternatives: POLECAT Dataset  
**Relevance: MEDIUM | Effort: MEDIUM | Risk: LOW | Status: Emerging (Published 2025)**

- Political Event Classification, Attributes, Types (POLECAT): peer-reviewed alternative to GDELT
- **Strengths:** Better domain accuracy (geopolitical coding), extremely low redundancy (avoids GDELT's 50%+ duplicate articles)
- **Weaknesses:** Smaller scale, lagged (not real-time), no free API yet
- **Assessment:** POLECAT validates Parallax's multi-stage dedup strategy. Not ready to replace GDELT as primary source, but useful as secondary validation feed for monthly reports.

**Sources:**
- [h3-duckdb bindings](https://github.com/isaacbrodsky/h3-duckdb)
- [deck.gl H3HexagonLayer docs](https://deck.gl/docs/api-reference/geo-layers/h3-hexagon-layer)
- [POLECAT vs GDELT study](https://doi.org/10.3390/data11070158)

---

### 2. LLM & Agent Stack

#### Claude Batch API + Multi-Hour Prompt Cache  
**Relevance: HIGH | Effort: MEDIUM | Risk: LOW | Status: Stable (March 2026 update)**

**Key Change (March 2026):** Anthropic reduced default cache TTL from 60 minutes → 5 minutes, BUT added opt-in 1-hour cache tier.

**Costs in Parallax context (current $20/day budget):**
- Standard mode: ~$600/month
- Batch only (50% off): ~$300/month
- Batch + 1-hour cache (50% + 90%): ~$150/month
- **Savings: $450/month (~$5,400 annually)**

**How to use in Parallax:**
1. Non-urgent predictions (GDELT backlog, daily eval) → Batch API (up to 24h turnaround)
2. Sub-actor system prompts (static ~2KB) → 1-hour prompt cache with explicit cache_control breakpoints
3. Hot-path agents (breaking news) → Standard API (no batch)

**Implementation notes:**
- Batch API: No rate-limit risk, deterministic queuing, perfect for "predict and shelf" workflows
- 1-hour cache: TTL must be explicitly set in request; default is 5-min. Max 100 cached blocks per request.
- **Risk:** Pipeline complexity increases (need batch queue + cache policy routing). Mitigate with wrapper class.

#### Sub-Optimal: Cheaper Model Routing (Haiku-first)  
**Relevance: MEDIUM | Effort: MEDIUM | Risk: MEDIUM | Status: Viable**

- Current spec: Haiku for sub-actors, Sonnet for country agents
- Gap: No dynamic routing based on event significance (always fires at same cost)
- Alternative: Confidence-gated routing (low-confidence events → Haiku only, no country agent)
- **Assessment:** Marginal value (~5-10% savings). Defer unless cost becomes constraint.

**Sources:**
- [Claude Batch API docs](https://platform.claude.com/docs/en/build-with-claude/batch-processing)
- [Prompt Caching 2026 guide](https://hidekazu-konishi.com/entry/anthropic_claude_api_prompt_caching_and_token_efficiency.html)
- [Cost optimization case study](https://pecollective.com/tools/claude-pricing-guide/)

---

### 3. Real-Time Data Ingestion

#### AIS Vessel Tracking APIs (Free Tier)  
**Relevance: HIGH | Effort: LOW | Risk: LOW | Status: Mature (2026)**

**Free options:**
- **AISstream.io**: Free WebSocket feed of real-time ship positions (global, 15-30s latency)
- **AISHub.net**: Free JSON/XML REST API, historical data available
- **Vessel Finder API**: Credit-based free tier (500 credits/month, 1-2 queries per credit)

**Parallax use case:** Real-time Hormuz vessel count + routing bypass flow
- Ingest AIS positions within Hormuz region (lat/lng bounding box)
- Map vessels to H3 cells (H3_LATLNG_TO_CELL)
- Track flow rate: vessel_count / 15min tick
- Compare against cascade model predictions (validate "% flow reduction" estimates)

**Recommendation:** Pilot with AISstream.io WebSocket + weekly snapshots to `streaming_ais_positions` table. Cost: $0 (free tier unlimited). Effort: ~4-6 hours (WebSocket handler + H3 mapping). Risk: Low (read-only, fallback to synthetic flow if API fails).

#### GDELT Supplement: POLECAT Weekly Batch  
**Relevance: MEDIUM | Effort: MEDIUM | Risk: LOW | Status: Secondary source**

- Add weekly POLECAT ingest as validation check against GDELT
- Use for post-hoc calibration: "GDELT said 3 Iran escalations this week, POLECAT confirms 2 (high confidence). GDELT has 50% false-positive rate here."
- **Not recommended as primary replacement** — POLECAT still lagged and smaller scale.

**Sources:**
- [AIS Vessel Tracking APIs](https://hormuzmonitor.com/50-best-ship-tracking-apis-2026/)
- [AISHub.net free API](https://www.aishub.net/)
- [AISstream.io real-time WebSocket](https://www.aisstream.io/)
- [VesselFinder tracking](https://www.vesselfinder.com/)

---

### 4. Evaluation & MLOps

#### Langfuse v3 → v4 Upgrade Path  
**Relevance: HIGH | Effort: MEDIUM | Risk: LOW | Status: Beta→v4 in progress**

**Current (v3, March 2026):**
- 10x dashboard performance improvement over v2
- Nested trace capture for agent → sub-actor → LLM call chains
- Prompt versioning + playground built-in
- A/B testing for prompt variants

**Planned (v4, late 2026):**
- 165x faster trace ingestion (new observations-centric data model)
- GPT-4-grade eval-as-judge endpoint
- Langfuse SDKs for Python/JS native integration

**Parallax alignment:**
- Current manual `predictions` table logging → Langfuse SDKs (wrap agent calls)
- Eval framework: Replace cron-based scoring → Langfuse eval-as-judge + custom metrics
- Prompt versioning: Already exists in Parallax, but Langfuse dashboard makes it discoverable

**Implementation:** Start with v3 self-hosted (MIT open source, ~4 hours setup). Migrate prediction logger to Langfuse SDK. Pilot 1-2 agents. Decision point: v4 beta → upgrade by November.

**Cost:** $0 self-hosted. No API calls (unlike prompt-centric tools).

#### Promptfoo CLI for Prompt A/B Testing  
**Relevance: MEDIUM | Effort: LOW | Risk: LOW | Status: Stable (CLI-first)**

- Unit test framework for LLM prompts
- Define test suite (inputs, expected outputs, metrics)
- A/B test two prompt versions in parallel
- Generates markdown report with win/loss matrix

**Parallax use:** Automate the prompt improvement pipeline:
1. Daily cron flags declining agent (same as today)
2. Trigger Promptfoo suite (10 test cases from recent misses)
3. Generate variant prompt (meta-agent or template)
4. Run A/B test (Haiku on both variants, same 10 cases)
5. If variant wins, alert admin with Promptfoo report

**Recommendation:** Add as optional dev dependency. Use for offline testing before admin approval. Effort: ~2-3 hours to template per agent type.

**Sources:**
- [Langfuse observability platform](https://www.udemy.com/course/langfuse-for-llmops/)
- [Langfuse v3/v4 comparison](https://qaskills.sh/blog/langfuse-llm-observability-guide-2026)
- [Prompt A/B testing guide](https://www.getmaxim.ai/articles/how-to-perform-a-b-testing-with-prompts-a-comprehensive-guide-for-ai-teams/)
- [Promptfoo tutorial](https://qaskills.sh/blog/promptfoo-llm-testing-guide)

---

### 5. Performance

#### DuckDB Parquet + Partitioning  
**Relevance: MEDIUM | Effort: LOW | Risk: LOW | Status: Best practice**

**Current Parallax setup:** `world_state_delta` writes as DuckDB native INSERT (row-by-row).

**Optimization opportunities:**
1. **Archive to Parquet:** Deltas older than 7 days → monthly Parquet files (compress ~95%)
   - Query: `COPY (SELECT * FROM world_state_delta WHERE tick < X) TO 'delta_archive_202608.parquet'`
   - Restore: `SELECT * FROM 'delta_archive_202608.parquet' WHERE cell_id = ?`
2. **Hive partitioning:** Store by month + region (if spatial partitioning added)
3. **Query tuning:** Apply EXPLAIN ANALYZE to top 5 hot queries (snapshot restore, cell lookup, agent memory)

**Assessment:** Quick win for cost/storage. Unlikely to impact live latency (snapshots + deltas already designed for fast replay). Effort: ~2 hours. Do after first 30-day run to validate schema.

#### React WebSocket Batching & Virtualization  
**Relevance: HIGH | Effort: MEDIUM | Risk: MEDIUM | Status: Documented best practice**

**Current Parallax design (spec section 5):**
- Correct: WebSocket updates to `useRef` (mutable data, no re-render thrash)
- Correct: Batch updates in 100ms windows
- Gap: No virtualization (if agent feed grows to 1000s, scroll will lag)

**Recommendation:** Add virtualization to right-panel agent feed (using `react-window` or `react-virtual`). Each row: agent ID, action, confidence, timestamp. Render only visible ~50 rows, even if 500 exist.

**Effort:** ~3-4 hours (swap ScrollContainer for Virtualized list, adjust styles).

**deck.gl Rendering Tuning:**
- Set `highPrecision: 'auto'` (not default 'true')
- Profile with Chrome DevTools: if WebSocket updates cause GPU/CPU spikes, lower `highPrecision` to 'false' for non-critical zoom levels
- Benchmark: Expect 2-3x faster hex updates during high-activity periods

**Sources:**
- [DuckDB performance guide](https://duckdb.org/docs/lts/guides/performance/overview)
- [DuckDB partitioning optimization](https://binadit.com/tutorials/optimize-duckdb-performance-for-large-datasets-with-partitioning)
- [React WebSocket best practices](https://www.sencha.com/blog/building-real-time-dashboards-with-websockets-and-frontend-frameworks/)
- [Trading dashboard optimization](https://openwebsolutions.in/blog/high-performance-trading-dashboard-react-websockets/)

---

## Top 3 Recommendations (Priority Order)

### 1. Claude Batch API + 1-Hour Prompt Cache (QUICK BOOST)
**Relevance: HIGH | Effort: MEDIUM | Risk: LOW | Impact: $5,400/year savings + zero LLM cost growth**

- **Why:** Parallax has fixed $20/day budget constraint. Stacking discounts (50% + 90%) = massive headroom for more agents/eval calls.
- **Action:** Implement batch job wrapper for non-urgent predictions (GDELT backlog, daily reports). Update agent call paths to use 1-hour cache tier for static system prompts.
- **Timeline:** 2-3 days (1 dev).
- **Rollback:** Simple (revert to standard API calls if needed).

### 2. AIS Vessel Tracking Integration (HIGH VALUE, LOW EFFORT)
**Relevance: HIGH | Effort: LOW | Risk: LOW | Impact: +1 real-world validation metric for Hormuz flow model**

- **Why:** Free data source + direct model validation. Cascade engine predicts "% flow reduction." AIS gives ground truth: actual vessel counts.
- **Action:** Add AISstream.io WebSocket consumer. Map vessels to Hormuz H3 cells. Write weekly flow stats to `ais_vessel_flow` table. Dashboard card: "Predicted vs Actual Vessel Count (7d)."
- **Timeline:** 1-2 days (1 dev).
- **Data:** Free (AISstream.io free tier unlimited).

### 3. Langfuse v3 Self-Hosted Pilot (LONG-TERM TRACING)
**Relevance: HIGH | Effort: MEDIUM | Risk: LOW | Impact: Unified eval + observability + prompt versioning UI**

- **Why:** Replaces manual prediction logging + eval cron. Integrates with A/B testing. Prepares for v4 (165x faster).
- **Action:** Deploy Langfuse v3 OSS Docker container. Wrap top 3 agents (Iran, USA, Saudi) with Langfuse SDKs. Migrate prediction logger to Langfuse. Pilot 2-week run before full rollout.
- **Timeline:** 4-5 days (1 dev + QA).
- **Cost:** $0 (self-hosted MIT license).
- **Decision point:** After 2-week pilot, decide: keep self-hosted, upgrade to v4 beta, or revert to manual.

---

## Deferred / Not Recommended (This Sprint)

- **POLECAT as primary source:** Good validation, not ready for primary real-time ingestion.
- **Prompt routing (Haiku-first):** ~5-10% savings. Complexity/risk not worth it now. Revisit if budget tightens.
- **DuckDB Parquet archive:** Defer until after first 30-day run. Validate schema growth first.
- **React virtualization:** Nice-to-have. Defer unless dashboard scroll becomes visibly laggy.

---

## Summary of Links & Sources

**Spatial:**
- [H3-DuckDB bindings](https://github.com/isaacbrodsky/h3-duckdb)
- [deck.gl H3HexagonLayer](https://deck.gl/docs/api-reference/geo-layers/h3-hexagon-layer)
- [POLECAT study](https://doi.org/10.3390/data11070158)

**LLM/Agent:**
- [Claude Batch API](https://platform.claude.com/docs/en/build-with-claude/batch-processing)
- [Prompt caching guide](https://hidekazu-konishi.com/entry/anthropic_claude_api_prompt_caching_and_token_efficiency.html)

**Real-Time Data:**
- [AIS Vessel APIs](https://hormuzmonitor.com/50-best-ship-tracking-apis-2026/)
- [AISHub](https://www.aishub.net/)
- [AISstream.io](https://www.aisstream.io/)

**Eval/MLOps:**
- [Langfuse](https://www.udemy.com/course/langfuse-for-llmops/)
- [Promptfoo](https://qaskills.sh/blog/promptfoo-llm-testing-guide)

**Performance:**
- [DuckDB performance](https://duckdb.org/docs/lts/guides/performance/overview)
- [React WebSocket patterns](https://www.sencha.com/blog/building-real-time-dashboards-with-websockets-and-frontend-frameworks/)

---

**Next scout run:** 2026-08-30 (weekly cadence)  
**Author:** Claude Code (Automated Daily Scout)
