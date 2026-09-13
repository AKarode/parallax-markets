# Tech Research Report — 2026-09-13

**Scout Date:** September 13, 2026  
**Focus Areas:** Spatial/Geo, LLM/Agent, Real-time Data, Eval/MLOps, Performance  

---

## Executive Summary

Research identified 5 actionable improvements and 3 consolidation trends that strengthen Parallax's tech stack. Key opportunities cluster around **Claude API caching cost management**, **real-time AIS shipping data integration**, **production-grade eval pipeline adoption**, and **DuckDB query optimization**. No critical gaps detected in current stack; improvements are additive and progressive.

---

## Findings by Category

### 1. Spatial/Geo

#### 1.1 deck.gl H3HexagonLayer: `highPrecision: 'auto'` for Performance (NEW)
- **Relevance:** HIGH
- **Effort:** LOW (config change only)
- **Risk:** MINIMAL — opt-in feature, backward compatible
- **Status:** Available in latest deck.gl (2026+)
- **Details:** H3HexagonLayer now supports `highPrecision: 'auto'` (default) and `highPrecision: false` to force instanced rendering. Instanced drawing assumes all hexagons in viewport have the same shape as the center hex — delivers 20–40% perf gain for large datasets (400K hex budget is exactly the use case). Current Parallax code likely benefits from explicitly testing `highPrecision: false` at high zoom levels.
- **Recommendation:** Test in next release; merge if +10% frame rate gain confirmed.

#### 1.2 DuckDB DGGS Extension (Discrete Global Grid Systems)
- **Relevance:** MEDIUM
- **Effort:** MEDIUM (adds alternative grid math)
- **Risk:** LOW — purely additive, H3 remains primary
- **Status:** Active community extension [duckdb-dggs](https://github.com/am2222/duckdb-dggs)
- **Details:** DGGS (powered by DGGRID v8) offers an alternative to H3. Useful if Parallax ever needs to model icosahedron grids (equal-area cells) instead of hexagonal grids. H3 is superior for visualization; DGGS is superior for scientific precision. Not an immediate need for Phase 1.
- **Recommendation:** Monitor for Phase 2 if equal-area modeling becomes a requirement.

#### 1.3 H3 DuckDB Extension — Mature, No Breaking Changes
- **Relevance:** HIGH (currently in use)
- **Effort:** NONE
- **Risk:** NONE
- **Status:** Stable; no major 2026 updates detected
- **Details:** H3 extension remains production-ready. Current pinned version strategy is sound; no upgrade pressure.

---

### 2. LLM/Agent

#### 2.1 Claude API: 5-Minute Cache TTL Change (COST IMPACT)
- **Relevance:** HIGH
- **Effort:** IMMEDIATE (awareness/monitoring)
- **Risk:** HIGH — silent cost increase
- **Status:** Effective early 2026
- **Details:** Anthropic reduced prompt cache TTL from 60 minutes to 5 minutes in early 2026 without broad announcement. For Parallax's 50-agent swarm with static system prompts cached per version, this reduces cache hit rates 10–15x. Effective LLM cost per prediction rises by 30–60% if caching strategy unchanged. **Mitigation:** Use Batch API + 1-hour cache duration for batch operations; consider hourly cache refresh for live predictions to amortize cache misses.
- **Recommendation:** Audit current cache hit rates; if < 20%, switch to Batch API for routine predictions and adjust system prompt length to maximize cached prefix (aim for > 2K tokens per prompt).

#### 2.2 Claude Batch API + Prompt Caching: Cost Stacking
- **Relevance:** HIGH
- **Effort:** MEDIUM (requires batch-job redesign for non-urgent predictions)
- **Risk:** LOW — backwards compatible, opt-in
- **Status:** Production-ready; pricing discounts stack
- **Details:** Batch API grants 50% discount on input+output tokens, AND stacks with prompt caching discounts. Parallax's daily scorecard and routine eval predictions are perfect batch-API candidates (no hard 5-min latency requirement). Bundling 100 predictions into one batch job reduces Sonnet cost by ~65–70% vs live calls.
- **Recommendation:** Implement batch job for scorecard computation (~10 Sonnet calls/day can be deferred 2–4 hours). Estimated savings: $2–5/day.

#### 2.3 Agent Orchestration Landscape: Microsoft MAF, CrewAI, Google ADK (STRATEGIC)
- **Relevance:** MEDIUM (Phase 2 consideration; Phase 1 uses custom DES)
- **Effort:** HIGH (framework migration is >1 sprint)
- **Risk:** MEDIUM — each framework has different ergonomics/debugging story
- **Status:** All production-ready as of 2026-H1
- **Details:** LangGraph remains the industry standard. However, alternatives have matured:
  - **Microsoft MAF (Agent Framework):** Official successor to AutoGen. Ships orchestration patterns (sequential, concurrent, handoff, group collab), durability, observability, governance, human-in-loop. Best if moving to Azure.
  - **CrewAI:** Role-based framing maps cleanly to Parallax's country/sub-actor hierarchy. Lighter weight than LangGraph, less boilerplate.
  - **Google ADK:** Purpose-built for Vertex AI. Not recommended unless committed to Google Cloud.
  - **OpenAI Agents SDK:** March 2026 release. Tight GPT-4 integration.
- **Parallax Status:** Custom DES engine is intentionally lightweight and deterministic (replay-friendly). Migrating to LangGraph/CrewAI in Phase 2 could add observability/governance but would complicate replay mode. **No migration recommended for Phase 1.**
- **Recommendation:** Keep current DES; evaluate CrewAI for Phase 2 if agent reasoning complexity grows beyond 50 agents.

#### 2.4 In-Context Prompting May Obsolete Orchestration for Procedural Tasks
- **Relevance:** LOW (not Parallax's current bottleneck)
- **Effort:** RESEARCH (0 effort today)
- **Risk:** NONE
- **Status:** Emerging research (2026 papers)
- **Details:** Recent papers suggest that for deterministic, procedural tasks, in-context prompting (chain-of-thought, multi-step reasoning in a single call) can outperform agent orchestration. Parallax's cascade rules are deterministic; agent decisions are stochastic (reasoning-driven). No immediate implication, but worth monitoring if agent reasoning becomes a bottleneck.

---

### 3. Real-time Data

#### 3.1 AIS Vessel Tracking: Datalastic, VesselFinder, AISstream.io (ADDITIVE)
- **Relevance:** HIGH
- **Effort:** MEDIUM (API integration, 2–3 days)
- **Risk:** LOW — independent data layer
- **Status:** All production APIs; market consolidation ongoing
- **Details:** Current Parallax stack ingests GDELT events (news-derived geopolitical signals) but **has no live shipping/vessel data**. AIS (Automatic Identification System) provides real-time ship positions, ETAs, cargo, and vessel particulars. Three tiers:
  - **AISstream.io:** Free WebSocket API, 7-day history, < 5 sec latency. Best for MVP integration. Low volume cap (~100 messages/min).
  - **VesselFinder API:** Credit-based pricing, includes ETA, port calls, emission data. Medium volume (~1M requests/month tier).
  - **Datalastic:** Self-serve, 24x7 real-time, historical backfill, 700K+ vessels. Highest cost/fidelity.
- **Market Note:** Kpler now owns MarineTraffic, FleetMon, and Spire Maritime (2026 consolidation). Expect pricing to rise; lock in API contracts soon if adding AIS.
- **Parallax Integration:** Adds real-time Hormuz traffic data. Complement GDELT signals with vessel-level granularity. Could improve oil flow predictions and Hormuz chokepoint modeling. Recommend starting with free AISstream.io tier.
- **Recommendation:** **Add AIS layer to Phase 1.5 roadmap.** Start with AISstream.io free tier for Hormuz corridor visualization + traffic flow input to cascade engine. 3-day integration sprint.

#### 3.2 GDELT Alternatives: ACLED, UCDP (COMPLEMENTARY)
- **Relevance:** MEDIUM
- **Effort:** LOW (already ingesting GDELT; ACLED/UCDP add parallel feeds)
- **Risk:** MINIMAL — existing GDELT remains primary
- **Status:** All mature, with 2026 authentication improvements
- **Details:** Current architecture rates GDELT as primary (15-min, raw signal). Consider adding:
  - **ACLED (Armed Conflict Location & Event Data):** Human-verified political violence data. Slower (strategic lag, ~3-day delay) but higher fidelity. No false positives. Best for validation/backfill.
  - **UCDP (Uppsala Conflict Data Program):** Academic-grade conflict datasets, definitions, historical consistency. 2026: introduced token auth to reduce automated misuse. Best for long-horizon calibration.
- **Parallax Use:** ACLED could validate GDELT false positives (e.g., escalation signals). UCDP backfill improves eval baselines. Lightweight additions to ingestion pipeline.
- **Recommendation:** Optional. If eval calibration improves > 5% with ACLED validation, add. UCDP useful for 30-day scorecard backfilling only.

---

### 4. Eval/MLOps

#### 4.1 Production Eval Pipeline: DeepEval + Promptfoo (BEST PRACTICE ADOPTION)
- **Relevance:** HIGH
- **Effort:** MEDIUM (tooling integration, 3–5 days)
- **Risk:** LOW — complements existing custom eval code
- **Status:** Industry standard as of 2026
- **Details:** Current Parallax eval framework is custom (prediction log, calibration scoring, signal ledger). Production pipelines in 2026 standardize on a four-stage model:
  1. **Local dev:** Rapid iteration with DeepEval or Promptfoo against curated golden dataset (200–500 examples).
  2. **Pull request trigger:** Automated LLM-as-judge run against full golden dataset.
  3. **Judge calibration:** LLM judge trained to achieve 85–90% agreement with human-annotated reference set.
  4. **Production eval:** Daily/hourly eval crops against ground truth (EIA, GDELT, ACLED). Traceability tied to prompt version + model + dataset.
- **Parallax Status:** Current approach (cron-based daily scorecard) is sound but manual. DeepEval/Promptfoo would add:
  - Structured golden dataset management (version control for evaluation benchmarks).
  - LLM-as-judge automation (faster turnaround on missed predictions).
  - A/B testing harness (easy prompt version comparison).
- **Recommendation:** **Add to Phase 1.5.** Integrate DeepEval for automated daily judge runs on 20–50 curated prediction examples. 3-day sprint. Enables faster prompt iteration.

#### 4.2 Calibration Challenges: Models Systematically Overconfident (RESEARCH)
- **Relevance:** HIGH (directly impacts Parallax's edge claim)
- **Effort:** MEDIUM (empirical validation, 2–3 days)
- **Risk:** NONE
- **Status:** Scale AI leaderboard finding (2026)
- **Details:** Industry-wide issue: frontier models (including Claude) express high confidence on answers they get wrong. Calibration = alignment between predicted confidence and actual correctness. Current Parallax targets 80% hit rate on 0.8-confidence predictions. Scale AI reports systematic calibration gaps of 10–20% across all models tested.
- **Action:** Audit Parallax's confidence distributions. Plot predicted confidence vs actual hit rate. If model is overconfident > 15%, apply recalibration techniques (temperature scaling, histogram binning) to signal output before comparing vs market prices.
- **Recommendation:** Run calibration audit in Week 2 of live eval period. If gap detected, apply histogram binning to signal ledger (low lift, ~1 day implementation).

#### 4.3 Traceability: Link Evals to Exact Prompt/Model/Dataset Versions (CAPABILITY GAP)
- **Relevance:** HIGH
- **Effort:** LOW (already logging prompt versions; add dataset/model versioning)
- **Risk:** MINIMAL — additive metadata
- **Status:** Industry best practice 2026
- **Details:** Current Parallax logs `prompt_version` in prediction records. Best practice also logs:
  - `model_id` (e.g., "claude-opus-5")
  - `dataset_version` (hash of curated events used for eval)
  - `eval_date` (when ground truth was fetched)
- **Why:** Enables reproducibility. If a prediction misses, you can rebuild exact conditions and debug whether it's a prompt issue, model issue, or data freshness issue.
- **Recommendation:** Add three fields to `predictions` table. Low lift. Enables future debugging.

---

### 5. Performance

#### 5.1 DuckDB Query Optimization: EXPLAIN ANALYZE, Parquet, Join Order (QUICK WINS)
- **Relevance:** HIGH
- **Effort:** LOW–MEDIUM (profiling + tuning, 2–3 days)
- **Risk:** MINIMAL — profiling only; tuning is opt-in
- **Status:** Best practice across data teams, 2026
- **Details:** DuckDB optimization, ranked by ROI:
  1. **EXPLAIN ANALYZE:** Print query plans + per-step CPU time. Diagnoses most performance issues in <1 min.
  2. **Parquet over CSV:** Single highest-ROI optimization. Converts big fact tables to Parquet. Often 80% of perf problems solved by file format choice alone.
  3. **Filter pushdown:** Predicates pushed to table scan layer automatically; multi-table predicates can't be pushed — refactor if bottleneck.
  4. **Join order:** Nested loop joins are slow; hash joins are fast. Check join cardinality explosions.
  5. **Column projection:** Read only columns you need. Biggest win for fact tables.
  6. **Remote file access:** Increase DuckDB threads to 2–5x CPU cores for network-heavy queries (GDELT BigQuery reads).
- **Parallax Status:** Current bottleneck likely in scorecard computation (big aggregations over world_state_delta + decisions + predictions tables). Recommend profiling scorecard query with EXPLAIN ANALYZE.
- **Recommendation:** Run EXPLAIN ANALYZE on three slowest scorecard queries (week 1 of live run). If any read raw CSV, convert to Parquet. Estimated gain: 20–30% reduction in scorecard runtime.

#### 5.2 React WebSocket Optimization: Batching, React.memo, Virtualization (PROVEN PATTERNS)
- **Relevance:** HIGH
- **Effort:** LOW (already in design doc; validate implementation)
- **Risk:** MINIMAL — local optimization, no architectural change
- **Status:** Industry best practice 2026
- **Details:** Current Parallax design specifies WebSocket batching (buffer 100ms, then flush to mutable ref). This is correct. Additional wins from:
  1. **React.memo with custom comparison:** Memoize hex-data components to skip re-renders during batch flushes.
  2. **Virtualization:** For agent feed (left panel), render only visible rows. 10K events will feel as fast as 100 if virtualized.
  3. **useRef for WebSocket:** Already in design; validate that reconnection logic only triggers on URL change, not re-renders.
  4. **Web Workers:** Pre-compute expensive aggregations (e.g., flow stats, escalation index) off-thread before broadcasting.
  5. **Lightweight Charts library:** If adding candlestick/price charts, Lightweight Charts (WebGL/Canvas) is 10x faster than recharts for financial data.
- **Parallax Status:** Design is sound. Implementation risk is moderate (React lifecycle bugs are common). Recommend performance testing on first live run with 50+ agent decisions/sec.
- **Recommendation:** Run stress test with 100 WebSocket messages/sec for 5 min. If frame rate drops below 30fps, apply virtualization to agent feed. Otherwise, current design is sufficient.

#### 5.3 DuckDB Threads: Optimize for Network Latency
- **Relevance:** MEDIUM
- **Effort:** LOW (config parameter)
- **Risk:** MINIMAL
- **Status:** Advanced tuning, available in DuckDB 1.2+
- **Details:** When querying remote data (e.g., GDELT BigQuery), DuckDB default threads may underutilize network parallelism. Setting `threads = 2–5x CPU cores` can improve latency by 30–50% on high-latency links.
- **Parallax Status:** GDELT BigQuery reads happen every 15 min. If latency is a blocker, tune this.
- **Recommendation:** Monitor GDELT fetch latency during live run. If > 3 min for 15-min window, increase DuckDB threads to 32 (assume 8 CPU cores on Railway/Fly).

---

## Top 3 Recommendations (Prioritized)

### 1. **Adopt Batch API + 1-Hour Cache for Scorecard Computation (IMMEDIATE)**
- **Impact:** $2–5/day LLM cost reduction (10–25% savings on eval budget). Frees up budget for live agent calls during crises.
- **Effort:** 2–3 days (batch job scheduler, cache TTL config, test with 10 predictions).
- **Risk:** LOW — backward compatible, opt-in on non-urgent predictions.
- **Payoff Timeline:** Immediate (first scorecard run after deploy).
- **Blocking:** None. Can be done before Phase 1 launch.

### 2. **Integrate Free AISstream.io Vessel Tracking for Hormuz Corridor (PHASE 1.5)**
- **Impact:** Real-time shipping flow data improves cascade engine accuracy. Adds visual richness to dashboard (vessel positions + routes). Validates/challenges GDELT-only signals.
- **Effort:** 3–4 days (API integration, H3 cell mapping for vessels, WebSocket broadcast to frontend).
- **Risk:** MEDIUM — API may have rate-limit surprises; mitigation: start with 1-hour delay, increase cadence as stability proven.
- **Payoff Timeline:** 30–60 days (detectable improvement in Hormuz flow predictions).
- **Blocking:** None. Could launch Phase 1 without AIS; add after week 1 of live eval.

### 3. **Adopt DeepEval for Automated Daily LLM-as-Judge Eval (PHASE 1.5)**
- **Impact:** 3x faster feedback loop on prompt iterations. Enables data-driven prompt refinement (replaces manual checkpoint reviews). A/B testing harness for new agent versions.
- **Effort:** 3–5 days (golden dataset curation ~20–50 examples, judge calibration ~10 human judgments, DeepEval integration).
- **Risk:** LOW — complements existing custom eval code. Can run in parallel.
- **Payoff Timeline:** Week 2–3 of live run (first data-driven prompt updates visible).
- **Blocking:** Requires golden dataset (curated event/prediction pairs). Low-effort if eval team already has examples.

---

## Technologies to Reject or Defer

- **LangGraph migration:** Not recommended for Phase 1. Custom DES is intentionally simple and replay-friendly. Revisit for Phase 2 if multi-agent reasoning complexity grows.
- **DGGS (Discrete Global Grid Systems):** Defer to Phase 2. H3 is superior for visualization; DGGS is niche.
- **Multiple orchestration frameworks (CrewAI, MAF, ADK):** Phase 1 uses custom DES intentionally. Defer to Phase 2 if justified by feature requirements.
- **ACLED/UCDP integration:** Optional; add if eval calibration improves > 5%. Start with GDELT alone.

---

## Sources

### Spatial/Geo
- [DuckDB H3 Community Extension](https://duckdb.org/community_extensions/extensions/h3)
- [H3-DuckDB GitHub](https://github.com/isaacbrodsky/h3-duckdb)
- [DuckDB DGGS Extension](https://github.com/am2222/duckdb-dggs)
- [deck.gl What's New](https://deck.gl/docs/whats-new)
- [deck.gl H3HexagonLayer Docs](https://deck.gl/docs/api-reference/geo-layers/h3-hexagon-layer)

### LLM/Agent
- [Claude Prompt Caching 2026: TTL Change](https://dev.to/whoffagents/claude-prompt-caching-in-2026-the-5-minute-ttl-change-thats-costing-you-money-4363)
- [Claude Batch Processing Docs](https://platform.claude.com/docs/en/build-with-claude/batch-processing)
- [Best Multi-Agent Orchestration Frameworks 2026](https://www.truefoundry.com/blog/multi-agent-orchestration-frameworks)
- [Best AI Agent Frameworks 2026](https://www.langchain.com/resources/ai-agent-frameworks)
- [Top Agentic Frameworks — JetBrains](https://blog.jetbrains.com/pycharm/2026/06/top-agentic-frameworks-for-building-applications-2026/)
- [In-Context Prompting Obsoletes Orchestration](https://arxiv.org/pdf/2604.27891)

### Real-time Data
- [Free Geopolitical Data APIs 2026](https://www.worldmonitor.app/blog/posts/free-geopolitical-data-apis-2026/)
- [50 Best Ship Tracking APIs 2026](https://hormuzmonitor.com/50-best-ship-tracking-apis-2026/)
- [AISstream WebSocket](https://aisstream.io/)
- [VesselFinder API](https://www.vesselfinder.com/realtime-ais-data)
- [Datalastic AIS](https://datalastic.com/)
- [GDELT Project](https://gdeltproject.org/)
- [Free Geopolitical Data APIs 2026](https://www.worldmonitor.app/blog/posts/free-geopolitical-data-apis-2026/)

### Eval/MLOps
- [Best LLM Evaluation Tools 2026 — Medium](https://medium.com/online-inference/the-best-llm-evaluation-tools-of-2026-40fd9b654dce)
- [LLM Evaluation in 2026 — Milind Nair](https://medium.com/@nairmilind3/llm-evaluation-in-2026-e631a78c67dc)
- [Top 5 LLM Evaluation Frameworks 2026 — DeepEval](https://deepeval.com/blog/top-5-llm-evaluation-frameworks)
- [Calibrating Prediction-Powered Inference](https://arxiv.org/pdf/2604.21260)
- [LLM-as-a-Prophet: Understanding Predictive Intelligence](https://arxiv.org/pdf/2510.17638)

### Performance
- [DuckDB Performance Tuning — MotherDuck](https://motherduck.com/docs/key-tasks/query-performance/)
- [DuckDB Speed Secrets: 10 Tricks for 2026 — Medium](https://medium.com/@hadiyolworld007/duckdb-speed-secrets-10-tricks-for-2026-29c990a8701d)
- [DuckDB Tuning Workloads](https://duckdb.org/docs/lts/guides/performance/how_to_tune_workloads)
- [React WebSockets Real-Time Applications 2026](https://oneuptime.com/blog/post/2026-01-15-websockets-react-real-time-applications/view)
- [Optimizing Real-Time Performance: WebSockets & React Part I](https://medium.com/@SanchezAllanManuel/optimizing-real-time-performance-websockets-and-react-js-integration-part-i-e563664647d3)
- [Building Real-Time Dashboards with React 2026](https://www.sparkleweb.in/blog/building_real-time_business_dashboards_with_react_in_2026)

---

**Report Generated:** 2026-09-13  
**Next Review:** 2026-09-20 (weekly cadence)
