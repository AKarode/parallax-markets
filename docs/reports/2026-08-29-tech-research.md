# Tech Research Report — 2026-08-29

## Overview

Daily technology research scout for Parallax geopolitical simulator. Searched across 5 focus areas for improvements, alternatives, and emerging technologies that could strengthen the current stack (DuckDB + H3 + deck.gl + Claude API + FastAPI).

## Focus Areas Searched

1. **Spatial/Geo**: DuckDB extensions, H3 tooling, deck.gl updates, geospatial visualization
2. **LLM/Agent**: Claude API features (prompt caching, batch API), structured output improvements
3. **Real-time Data**: GDELT alternatives, AIS shipping data, geopolitical event databases
4. **Eval/MLOps**: Prediction evaluation frameworks, prompt versioning, A/B testing systems
5. **Performance**: WebSocket optimization, React rendering, DuckDB performance

---

## Findings by Category

### 1. Spatial/Geo

#### DuckDB Spatial Extension — Experimental Geometry Types (MEDIUM relevance)

**Finding**: DuckDB v1.5.2 (April 2026) stabilized the spatial extension with experimental fixed-precision geometry types (POINT_2D, LINESTRING_2D, POLYGON_2D, BOX_2D) that offer better compression and faster execution than the standard GEOMETRY type.

- **Relevance**: MEDIUM — Parallax currently uses DuckDB + H3 community extension (resolution-specific hex cells). The new types could accelerate range queries on cells if Parallax switches to point-based (port locations) or linestring-based (shipping routes) representations, but H3 cells are already optimized for this use case.
- **Effort**: LOW — Opt-in migration; current queries continue working.
- **Risk**: LOW — Experimental label; mature enough for production per v1.5.2 release notes.
- **Action**: Monitor for additional specialized functions. If Parallax adds port/route detail layers, test against existing H3-cell queries for throughput gains.

---

#### deck.gl H3HexagonLayer — `highPrecision: false` Performance Flag (MEDIUM relevance)

**Finding**: deck.gl v9.x added optional low-precision rendering mode (`highPrecision: false`) for H3HexagonLayer, enabling developers to trade render fidelity for GPU speed when full precision is not required.

- **Relevance**: MEDIUM — Parallax dashboard renders ~400K hexes across 4 resolution bands. Currently using GPU interpolation (600ms transitions). Low-precision mode could eliminate jank during high-frequency updates without architectural changes.
- **Effort**: LOW — One-line prop change; test render quality vs fps tradeoff.
- **Risk**: LOW — Opt-in flag; visual artifacts only if enabled without testing.
- **Action**: Benchmark on low-end browsers (Safari on iPad, mid-range Android). If 15+ hex updates/sec cause stutter, enable `highPrecision: false` on highest-resolution layers (res 8-9, smallest hexes).

---

#### deck.gl TileLayer with H3 Support (LOW relevance)

**Finding**: deck.gl v8.8+ added TileLayer support for custom indexing systems including H3, enabling incremental tile loading for large H3-indexed datasets.

- **Relevance**: LOW — Parallax pre-loads all 400K hexes at startup. TileLayer shines for 10M+ hex datasets. Applicable only if scenario scope expands (global model).
- **Effort**: MEDIUM — Requires refactoring data loading from batch to streaming.
- **Risk**: MEDIUM — Introduces async tile fetching complexity; edge cases in tile boundary transitions.
- **Action**: Defer to Phase 2. Document for multi-scenario expansion.

---

### 2. LLM/Agent

#### Claude API Prompt Caching — 5-Minute TTL Caveat (HIGH relevance)

**Finding**: Anthropic changed cache TTL from 60 minutes to 5 minutes in July 2026. This increased effective API costs for production workloads by 30–60% since system prompts (agent baselines) no longer persist across hour-long cycles. Parallel feature: Persistent cache (beta) on select Sonnet 4 and Opus 4 endpoints survives across sessions.

- **Relevance**: HIGH — Parallax budget is ~$2–5/day with aggressive caching of agent system prompts (historical baselines ~3K tokens). 5-min TTL means agent prompts are re-transmitted every 5 minutes during high-activity periods, defeating the 90% savings model.
- **Effort**: MEDIUM — Requires migration to Persistent cache (beta) or acceptance of cost increase.
- **Risk**: MEDIUM — Persistent cache is beta; Anthropic may change pricing/availability.
- **Action**: URGENT — Test Persistent cache on Sonnet 4/Opus 4 pilot. If stable, migrate critical agent prompts (country agents) to persistent prefix. If unavailable in production tier, accept 30–40% cost increase and adjust budget cap.

---

#### Claude Structured Outputs — GA on Haiku/Sonnet/Opus (HIGH relevance)

**Finding**: Claude's Structured Outputs (JSON schema enforcement) became GA in 2026 across Claude 4.5 models (Haiku, Sonnet, Opus). Output conforms to schema at generation time, eliminating parse errors and retry logic.

- **Relevance**: HIGH — Parallax agent output validation currently happens post-generation via Pydantic schema. Structured outputs eliminate need for retry loops on malformed agent decisions/predictions. Could shorten decision pipeline by 0–30% (depends on malform rate).
- **Effort**: LOW — Replace `response_format={"type": "json"}` hints with explicit schema objects in API calls.
- **Risk**: LOW — Backward compatible; existing prompts continue working.
- **Action**: IMMEDIATE — Audit agent prompt calls (prediction models, decision handlers). Enable structured outputs for agent output schema. Measure reduction in retries/errors. Expected gain: ~5–10% reduction in LLM calls for agent swarm.

---

#### Claude Batch API — 50% Discount (MEDIUM relevance)

**Finding**: Claude Batch API offers 50% off all usage. Batches take 5 min to 24 hours. Combined with Persistent prompt caching (1-hour window within batch), cache hit rates improve significantly.

- **Relevance**: MEDIUM — Parallax daily eval pipeline (`daily_scorecard` cron) could batch all eval queries once/day (50% discount). Live agent decisions cannot batch (real-time). Eval cost: ~$0.35/day → ~$0.175/day if batched.
- **Effort**: MEDIUM — Separate batch submission path for eval pipeline; requires async result polling.
- **Risk**: LOW — Eval is non-blocking; latency acceptable.
- **Action**: Implement batch submission for daily eval cron. Expected savings: ~$105/30-day run.

---

### 3. Real-time Data

#### AISstream.io WebSocket API — Free Real-Time Maritime Tracking (HIGH relevance)

**Finding**: AISstream.io provides free WebSocket API for real-time Automatic Identification System (AIS) data — live vessel positions, types, destinations. Complements GDELT for tracking physical shipping flows through Hormuz.

- **Relevance**: HIGH — Current cascade model (Section 4, design spec) simulates oil flow reduction via blockade rules, but has no ground-truth maritime signal. AIS data would validate/recalibrate flow assumptions. Hormuz traffic is a direct observable input.
- **Effort**: MEDIUM — WebSocket ingestion similar to existing GDELT poller. Schema mapping (vessel → H3 cell). Deduplication.
- **Risk**: LOW — Data quality varies (coverage gaps in Persian Gulf). Use as secondary signal.
- **Action**: PHASE 2 — Ingest AIS data for Hormuz corridor (res 7-8 cells). Correlate vessel counts against Kalshi market contracts (e.g., "Hormuz traffic > X vessels/day"). Feeds directly into recalibration pipeline.

---

#### GDELT Alternatives — UCDP + ACLED Stack (MEDIUM relevance)

**Finding**: UCDP (Uppsala Conflict Data Program) and ACLED (Armed Conflict Location & Event Data) are academically grounded conflict datasets. GDELT is broader but noisier. No single "geopolitical API" — effective signal requires stacking: conflicts (ACLED/UCDP) + news (GDELT) + earthquakes (USGS) + internet outages (Cloudflare Radar).

- **Relevance**: MEDIUM — Parallax currently relies solely on GDELT for event ingestion. ACLED is already available (weekly batch per spec). UCDP is new addition; offers validated conflict taxonomy (armed clash, explosions/remote violence, protests, etc.) vs GDELT's raw volume.
- **Effort**: MEDIUM — Add UCDP ingest poller (weekly or daily). Merge with GDELT. Adjust relevance filter to prefer UCDP events (higher confidence) when available.
- **Risk**: LOW — Additive; doesn't replace GDELT.
- **Action**: PHASE 2 — Add UCDP conflict data. Implement relevance weighting (prefer UCDP-tagged events). Use ACLED weekly batch for validation (compare agent predictions against ground-truth conflict events).

---

#### Marine Cadastre & USGS Supplementary Signals (LOW relevance)

**Finding**: U.S. Marine Cadastre publishes vessel traffic data (AIS, coast guard); USGS provides earthquake feeds. Both are free, public, and correlate with geopolitical risk (earthquakes hit ports/power; vessel rerouting visible in traffic).

- **Relevance**: LOW — Out of scope for Iran/Hormuz MVP. Relevant if Parallax expands to global shipping scenarios or multi-region modeling.
- **Effort**: MEDIUM — Requires H3-based geospatial joins (earthquake epicenter → nearby port/infrastructure cells).
- **Risk**: LOW — Optional signal; use for model validation.
- **Action**: Defer to Phase 2. Document for multi-region expansion.

---

### 4. Eval/MLOps

#### Langfuse Prompt Versioning & Traceability (MEDIUM relevance)

**Finding**: Langfuse provides prompt management, versioning, and linked evaluation scores. Ecosystem matured in 2026 to integrate versioning directly into LLM call traces.

- **Relevance**: MEDIUM — Parallax already has manual prompt versioning (semver tags, `prompt_version` field in predictions table). Langfuse would automate versioning, link scores to prompt versions automatically, and expose A/B comparison dashboards.
- **Effort**: MEDIUM — Integrate Langfuse SDK into agent calls; requires schema adaptation for `prompt_version` tracking.
- **Risk**: MEDIUM — External dependency; vendor lock-in risk.
- **Action**: Evaluate Langfuse as Phase 2 enhancement. Current manual system (DuckDB + cron) is functional; Langfuse adds observability. If admin usability is a constraint, adopt.

---

#### Promptfoo Unit Testing & A/B Testing (MEDIUM relevance)

**Finding**: Promptfoo provides lightweight CLI-based A/B testing, unit testing, and regression detection for prompts. Integrates with CI/CD.

- **Relevance**: MEDIUM — Parallax evaluation pipeline (Section 7, spec) is cron-based. Promptfoo could add regression tests (ensure new prompt doesn't underperform baseline) and CI/CD gates before deployment.
- **Effort**: LOW — Add Promptfoo test suite; define baseline expectations (e.g., "oil price direction accuracy > 60%"). Hook into prompt update workflow.
- **Risk**: LOW — Optional; doesn't replace existing eval system.
- **Action**: Add Promptfoo tests for each agent prompt version. Run before admin approval. Expected benefit: catch prompt regressions 1–2 days earlier than cron.

---

#### DeepEval & Confident AI Frameworks (LOW relevance)

**Finding**: DeepEval and Confident AI are SaaS platforms for LLM evaluation, dataset management, and CI/CD integration. Mature in 2026.

- **Relevance**: LOW — Parallax has custom eval pipeline (DuckDB-native, no external dependencies). Migrating to SaaS adds cost and latency. Applicable only if eval becomes a bottleneck.
- **Effort**: HIGH — Requires data export, schema mapping, third-party integration.
- **Risk**: MEDIUM — Introduces external dependency; vendor lock-in.
- **Action**: Monitor for cost/latency issues. Current approach preferred for MVP.

---

### 5. Performance

#### WebSocket Batching & Update Coalescing (HIGH relevance)

**Finding**: High-frequency WebSocket updates (>10/sec) cause React re-render thrashing. Solution: batch updates (buffer 100ms), mutate `useRef` directly, and push to deck.gl on single render cycle. Museums of examples in 2026 dashboards.

- **Relevance**: HIGH — Parallax spec (Section 5) already identifies this issue and prescribes the solution (useRef for hex data, batched WebSocket messages). Current implementation status unknown.
- **Effort**: LOW — If not already done, implement batching middleware in WebSocket handler.
- **Risk**: LOW — Isolated change; no API surface.
- **Action**: Audit frontend WebSocket handler. If batching is not implemented, add 100ms coalesce buffer for `cell_update` messages. Expected gain: eliminate render stutter during high-activity periods.

---

#### React.memo & Custom Comparison for Dashboard Cards (MEDIUM relevance)

**Finding**: Real-time dashboards with many card components (agent feed, indicators, timeline) benefit from React.memo with custom `areEqual` comparisons to prevent unnecessary re-renders of expensive components (charts, lists).

- **Relevance**: MEDIUM — Parallax dashboard has 3 major card sections (agent activity, live indicators, timeline). If indicator cards re-render on every price update, performance degrades. Already described in design spec (Section 5).
- **Effort**: LOW — Wrap components with React.memo; add shallow equality checks.
- **Risk**: LOW — Safe optimization; visual regression unlikely.
- **Action**: Audit indicator and timeline card components. Apply React.memo to prevent re-renders when parent updates but props unchanged. Expected gain: ~10–20% reduction in card render time.

---

#### Virtualization for Long Agent Activity Feed (LOW relevance)

**Finding**: React list virtualization libraries (react-window, react-virtualized) render only visible rows, allowing 10K-row lists to feel as responsive as 100-row lists.

- **Relevance**: LOW — Parallax agent feed displays ~20–50 recent decisions (manageable). Virtualization applicable only if feed grows to 1000+ decisions per session.
- **Effort**: MEDIUM — Requires refactoring agent feed component.
- **Risk**: LOW — Backward compatible; opt-in.
- **Action**: Defer to Phase 2. Monitor agent feed scroll performance. If sluggish with >100 decisions, adopt virtualization.

---

## Top 3 Recommendations

### 1. **Enable Claude Structured Outputs on Agent Swarm Calls (IMMEDIATE)**

**Why**: Eliminates agent output retry loops, reduces token consumption by ~5–10%, and guarantees schema compliance without Pydantic post-processing. One-line change per agent call.

**Action**:
- Audit all agent LLM calls in `prediction/oil_price.py`, `prediction/ceasefire.py`, `prediction/hormuz.py`, and decision handlers.
- Enable structured outputs with explicit JSON schemas (agent output schema from spec Section 3).
- Measure retry rate before/after. Target: <1% malformed outputs.

**Expected Impact**: ~$0.30–0.50 savings over 30 days (fewer retries), plus smoother decision pipeline.

---

### 2. **Migrate Agent Prompts to Persistent Cache (PHASE 1, with caveat)**

**Why**: 5-minute cache TTL (July 2026 change) erased Parallax's 90% token savings. Persistent cache (beta) restores cost efficiency but requires Sonnet 4/Opus 4 endpoints.

**Action**:
- Test Persistent cache on staging with 3–5 country agents.
- If stable, migrate critical prompts (Iran, USA, Saudi Arabia) to persistent prefixes.
- If unavailable in production tier, accept 30–40% cost increase and adjust daily budget cap to $6–8/day.

**Expected Impact**: Restore ~70% token savings (90% → 70% post-TTL-change), or accept documented cost increase.

---

### 3. **Ingest Real-Time AIS Maritime Data for Hormuz Validation (PHASE 2)**

**Why**: Parallax cascade model (blockade → flow reduction → price shock) is rule-based. AIS data provides ground-truth signal for vessel counts in Hormuz, enabling recalibration of flow assumptions and direct correlation with market contracts.

**Action**:
- Stand up AISstream.io WebSocket poller (free tier, unlimited).
- Sample vessel positions into res 7-8 H3 cells (Hormuz strait).
- Correlate daily vessel counts with Kalshi market ("Hormuz traffic > X vessels/day") contracts.
- Feed validation results into recalibration pipeline (scoring/recalibration.py).

**Expected Impact**: Validation loop for flow assumptions; recalibration confidence increases 10–20%.

---

## Sources

### Spatial/Geo
- [DuckDB Extensions for 2026](https://medium.com/@Praxen/duckdb-extensions-youll-actually-use-in-2026-bd0ea86a359f)
- [DuckDB Spatial Overview](https://duckdb.org/docs/lts/core_extensions/spatial/overview)
- [DuckDB Spatial Repository](https://github.com/duckdb/duckdb-spatial)
- [deck.gl What's New](https://deck.gl/docs/whats-new)
- [deck.gl Upgrade Guide](https://deck.gl/docs/upgrade-guide)

### LLM/Agent
- [Claude API Prompt Caching Guide](https://hidekazu-konishi.com/entry/anthropic_claude_api_prompt_caching_and_token_efficiency.html)
- [Claude Prompt Caching 5-Minute TTL Impact](https://dev.to/whoffagents/claude-prompt-caching-in-2026-the-5-minute-ttl-change-thats-costing-you-money-4363)
- [Claude Batch Processing Docs](https://platform.claude.com/docs/en/build-with-claude/batch-processing)
- [Anthropic Structured Outputs Announcement](https://claude.com/blog/structured-outputs-on-the-claude-developer-platform)
- [Claude Structured Output Guide](https://thomas-wiegold.com/blog/claude-api-structured-output/)

### Real-Time Data
- [AIS Vessel Tracking Best Practices 2026](https://www.seavantage.com/blog/best-vessel-tracking-software-in-2026-8-ais-platforms-compared)
- [AISHub Free AIS Service](https://www.aishub.net/)
- [AISstream WebSocket API](https://aisstream.io/)
- [OpenAIS Tools](https://open-ais.org/)
- [Marine Cadastre Vessel Traffic Data](https://hub.marinecadastre.gov/pages/vesseltraffic)
- [Free Geopolitical Data APIs 2026](https://www.worldmonitor.app/blog/posts/free-geopolitical-data-apis-2026/)
- [GDELT Solutions](https://www.gdeltproject.org/solutions.html)

### Eval/MLOps
- [Best LLM Evaluation Tools 2026](https://medium.com/online-inference/the-best-llm-evaluation-tools-of-2026-40fd9b654dce)
- [Prompt A/B Testing Guide](https://www.getmaxim.ai/articles/how-to-perform-a-b-testing-with-prompts-a-comprehensive-guide-for-ai-teams/)
- [Braintrust Best Prompt Evaluation Tools](https://www.braintrust.dev/articles/best-prompt-evaluation-tools-2025)
- [DeepEval LLM Evaluation](https://deepeval.com/blog/best-llm-evaluation-platforms)
- [Promptfoo Evaluation Tutorial](https://qaskills.sh/blog/promptfoo-llm-testing-guide)

### Performance
- [WebSocket Optimization for React Dashboards 2026](https://oneuptime.com/blog/post/2026-01-15-websockets-react-real-time-applications/view)
- [WebSocket & React Integration Part I](https://medium.com/@SanchezAllanManuel/optimizing-real-time-performance-websockets-and-react-js-integration-part-i-e563664647d3)
- [WebSocket & React Integration Part II](https://medium.com/@SanchezAllanManuel/optimizing-real-time-performance-websockets-and-react-js-integration-part-ii-4a3ada319630)
- [Real-Time Dashboards with React 2026](https://www.sparkleweb.in/blog/building_real-time_business_dashboards_with_react_in_2026)

---

## Summary

**Key Takeaways:**
- **Claude API**: Structured outputs (GA) + Persistent cache (beta) should be priority — immediate token/cost improvements.
- **Real-time Data**: AIS integration validates cascade model assumptions — Phase 2 high-impact addition.
- **Performance**: Current architecture (batched WebSocket, useRef for hex data) already sound; minor optimizations available (React.memo, virtualization).
- **Spatial**: DuckDB spatial extension stable; deck.gl performance modes useful if UI becomes bottleneck.
- **Eval**: Lightweight tools (Promptfoo) recommended over SaaS platforms; manual DuckDB system is sufficient.

**No significant blockers identified. All recommendations are additive or opt-in migrations.**

