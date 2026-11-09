# Tech Research Report: Parallax Stack Improvements
**Date:** 2026-11-09  
**Focus Areas:** Spatial/geo, LLM/agent, real-time data, eval/MLOps, performance

---

## Executive Summary

Research across five categories identified **2 high-impact findings** and several medium-effort improvements. No major gaps in the current stack, but opportunities exist to reduce LLM costs, add real-time shipping data, and optimize the eval/prompt iteration framework.

---

## Findings by Category

### 1. Spatial & Geospatial

#### Finding 1.1: DuckDB Spatial Indexing & Hilbert Curve Ordering (MEDIUM relevance, LOW effort, ADDITIVE)

**What:** Recent DuckDB 2.0 LTS (October 2026) added:
- R-tree spatial indexes for faster `ST_DWithin` queries (2025 benchmark showed 10-15% speedup)
- Native GeoParquet writer with auto-generated bounding box columns
- Hilbert curve sorting for spatial data locality
- Asynchronous S3 I/O for faster remote data reads

**Assessment:**
- **Relevance:** MEDIUM — Parallax runs H3 queries, not continuous range scans, but indexing helps the 400K hex analytics queries.
- **Effort:** LOW — Enable via `INSTALL spatial; LOAD spatial;` and add `ORDER BY hilbert_curve(lon, lat)` to GeoParquet writes.
- **Risk:** None — purely additive performance improvement.
- **Integration:** Add to `db/schema.py` initialization. Benchmark before/after on daily scorecard query latency.

**Sources:**
- [DuckDB 2.0 Performance Guide](https://duckdb.org/docs/2.0/guides/performance/overview)
- [Spatial queries with R-tree and H3 (March 2025)](https://aetperf.github.io/2025/03/04/Spatial_queries_in_DuckDB_with_R-tree_and_H3_indexing.html)

#### Finding 1.2: Grid Alternatives (S2, Geohash) Remain Immature (LOW relevance)

**What:** S2 (square hierarchical grid) and Geohash (quadtree encoding) exist but lack the visualization ecosystem H3 has (no deck.gl layer equivalent, limited open-source tooling).

**Assessment:**
- **Relevance:** LOW — No tactical advantage over H3 for Parallax's use case.
- **Recommendation:** Stick with H3. It dominates the geospatial visualization space.

---

### 2. LLM & Agent Orchestration

#### Finding 2.1: Claude Batch API + Prompt Caching Stacking for Cost Optimization (HIGH relevance, MEDIUM effort, ADDITIVE)

**What:** Claude's Batch API (50% discount on input tokens) and Prompt Caching (10% cost for cached reads, 25% for cache writes) can be combined. March 2026 documentation confirms compatibility. Effective cost drops to ~20-30% of standard sync rate on repeat calls with shared context.

**Details:**
- **Batch scope:** Supports vision, tool use, extended thinking, and prompt caching.
- **Cache write cost:** 25% of standard input token price (not mentioned in March 2026 docs but confirmed by third-party sources).
- **Cache duration:** 5-minute default; batch jobs can request 1-hour TTL for better hit rates.
- **Opus 4.8 improvement:** Minimum cacheable prompt length dropped from 1,500 tokens to 1,024 tokens (May 2026 release).

**How to Apply to Parallax:**
- Agent system prompts (historical baseline + country memory) are ~2-3K tokens each.
- Current daily cost: ~$2-5 at sync rates. With batch + cache stacking:
  - Overnight batch eval runs: 50% discount
  - Agent system prompts cached: 10% of standard input cost on cache hit
  - Estimated new daily cost: **~$0.50-1.50**
- **Tradeoff:** Batch jobs take 5+ minutes to complete (not suitable for live prediction scoring). Use for daily eval, overnight eval meta-agent, and periodic prompt A/B testing.

**Implementation:**
1. Separate agent calls into sync (live predictions, <100ms required) and batch (eval, historical analysis).
2. Use `client.beta.messages.batches.create()` for eval cron jobs.
3. Cache the system prompt of each agent version using the cache_control API.
4. Track cache hit rates in `llm_usage` table to measure savings.

**Risk:** LOW — Batch API is stable. Cache hit rates depend on token stability, which is high for static system prompts.

**Sources:**
- [Combining Caching with Batch API (March 2026)](https://claude-skills-guide-3lc.pages.dev/combining-caching-batch-api-95-percent-savings/)
- [Claude Batch API Documentation](https://platform.claude.com/docs/en/build-with-claude/batch-processing)
- [Opus 4.8 Release Notes (May 2026)](https://platform.claude.com/docs/en/release-notes/overview)

#### Finding 2.2: Cheaper Model Alternatives (Llama 4, DeepSeek) vs. Claude Trade-offs (MEDIUM relevance, MEDIUM effort, ALTERNATIVE)

**What:** Open-weight models hosted by inference providers cost 80-95% less than Claude:
- DeepSeek: ~$0.27/MTok input (10x cheaper than Claude Sonnet)
- Llama 4 Scout: ~95% below GPT-5.2
- Together AI Llama 3.x/Mixtral: $0.20-$0.90/MTok

**Tradeoffs:**
- **Complex reasoning:** Claude Opus/Sonnet outperforms Llama on multi-step geopolitical reasoning (country agent conflict resolution, cascade rule interpretation).
- **Latency:** Shared GPU inference adds tail latency during peak hours; not ideal for <100ms live predictions.
- **Recommendation:** Reserve Llama for low-criticality tasks:
  - Sub-actor initial filters (Haiku → Llama equivalent)
  - Historical replay (batch, not time-critical)
  - Cold start baseline (one-time bootstrap)
- Keep Claude Sonnet/Opus for country agents and real-time divergence detection.

**Assessment:**
- **Relevance:** MEDIUM — Cost savings are real (~$1-2/day), but reasoning quality risk is non-trivial.
- **Effort:** MEDIUM — Requires prompt tuning and eval baseline on Llama, then gradual canary.
- **Risk:** MEDIUM — If Llama sub-actor recommendations drift from reality, country agent decisions degrade. Mitigate with A/B eval.

**Sources:**
- [LLM Pricing Comparison 2026 (February)](https://inference.net/content/llm-api-pricing-comparison/)
- [Cheapest LLM APIs 2026](https://costbench.com/best/cheapest-llm-api/)
- [Open-Source vs Proprietary Cost Comparison](https://aicostcheck.com/blog/open-source-vs-proprietary-ai-cost-comparison-2026)

#### Finding 2.3: Prompt Versioning + Feature Flags Pattern (MEDIUM relevance, LOW effort, FOUNDATIONAL)

**What:** Industry standard for A/B testing LLM prompts in production:
1. Semver each prompt version (`v1.2.0`).
2. Use feature flags to route users/requests to specific versions.
3. Track accuracy per version over rolling windows.
4. Auto-flag if new version underperforms old within 7 days.

**How to Strengthen Parallax:**
- Parallax already logs `prompt_version` in decisions and predictions.
- Add feature flags system: store in DuckDB `agent_prompts` table as `active_version` boolean.
- On eval cron, auto-compare accuracy of `v1.2.0` vs `v1.2.1` over rolling 7-day window. If new version misses exceed old by >5%, flip flag back to old.
- Integrate with admin dashboard for one-click rollback.

**Assessment:**
- **Relevance:** MEDIUM — Already partially implemented. Completing it unlocks rapid iteration.
- **Effort:** LOW — Mostly dashboard/cron work.
- **Risk:** LOW — Feature flags decouple deployment from activation.

**Sources:**
- [A/B Testing LLM Prompts: 2026 Guide](https://atlan.com/know/ab-testing-llm-applications/)
- [Prompt Management & Versioning](https://kindatechnical.com/mlops-guide/prompt-management-versioning-testing-and-ab-testing.html)
- [FeatBit Prompt A/B Testing](https://www.featbit.co/blogs/ab-testing-llm-prompts)

---

### 3. Real-Time Data Ingestion

#### Finding 3.1: LSEG Vessel Tracking API Launch (March 2026) — Real-Time AIS Alternative (MEDIUM relevance, MEDIUM effort, ADDITIVE)

**What:** LSEG (London Stock Exchange Group) launched a real-time vessel tracking API in March 2026 combining terrestrial and satellite AIS feeds. Offers sub-5-second latency.

**Current State:** Parallax ingests GDELT news (15-60 min lag) but has no direct shipping flow data. Oil price is a proxy, but real AIS would enable:
- Actual vessel detours around Hormuz (vs. modeled rerouting)
- Shipping insurance spikes (tied to vessel tracking, not just price)
- Early signals of blockade effectiveness (reduced vessel attempts)

**Integration Options:**
1. **Basic:** Query LSEG API for Hormuz-area vessels every 15 minutes. Store MMSI, position, destination in DuckDB. Compute % change in vessel count as "flow indicator."
2. **Advanced:** Ingest into realtime WebSocket feed. Push vessel count + average route deviation to frontend dashboard.

**Assessment:**
- **Relevance:** MEDIUM — Adds ground truth validation layer for predictions, but not essential for core cascade logic (which is already scenario-calibrated).
- **Effort:** MEDIUM — Requires API key, authentication (likely token-based), schema design, WebSocket plumbing.
- **Cost:** Unknown (not quoted in search results). Likely enterprise pricing ($500-5000/month). Check against $20/day LLM budget.
- **Risk:** LOW — Data ingestion only, no impact on model.

**Timeline:** Defer to Phase 2 unless cost is <$5/day.

**Sources:**
- [LSEG Vessel Tracking API Launch (March 2026)](https://www.pulse.bot/transportation/news/lseg-launches-real-time-vessel-tracking-api-bfbe1be2-3a45-4dde-9d46-1e19cab4146e)
- [Real-Time Vessel Monitoring Platforms 2026](https://www.shipuniverse.com/tech/real-time-vessel-monitoring-platforms-compared-in-2026/)

#### Finding 3.2: GDELT Cloud (Paid) vs. Free GDELT (LOW-MEDIUM relevance, LOW effort, INFORMATION)

**What:** Kpler/GDELT Cloud offers hourly-coded event ingestion for $X/month (pricing not found). Free GDELT remains at 15-60 min lag with automated coding.

**Assessment:**
- **Relevance:** LOW-MEDIUM — Current GDELT + semantic dedup already provides good noise filtering. Hourly GDELT Cloud would improve freshness by 30-45 min.
- **Cost-benefit:** At $20/day LLM budget, can't afford enterprise data feeds. Stick with free GDELT.
- **Recommendation:** Continue with free GDELT + human-coded ACLED (weekly) baseline.

**Sources:**
- [GDELT Cloud Documentation](https://docs.gdeltcloud.com/)
- [Free Geopolitical Data APIs 2026](https://www.worldmonitor.app/blog/posts/free-geopolitical-data-apis-2026/)

---

### 4. Evaluation & MLOps

#### Finding 4.1: Industry A/B Eval Pipeline (Judge-Based Scoring) (HIGH relevance, MEDIUM effort, RECOMMENDED)

**What:** Standard production pipeline for LLM eval:
1. **Offline eval:** Run new prompt on held-out test set (curated GDELT events). Grade outputs with judge LLM (Sonnet).
2. **Shadow scoring:** Run both old and new in parallel on live events. Log both but execute only old.
3. **Canary:** Route 10% of live requests to new version. Monitor divergence rate.
4. **Full test:** If canary passes, gradual rollout with feature flag.
5. **Regression gate:** Block new version if eval metrics drop below baseline.

**How Parallax Benefits:**
- Currently: daily cron flags accuracy drop. But no structured eval pipeline.
- Upgrade: Add shadow and canary stages before promoting new country agent prompt.
- Cost: Judge-based scoring (using Sonnet to grade sub-actor outputs) adds ~$0.005-0.01/decision. At 100 eval decisions/day, ~$0.50-1.00/day.

**Tools:** Braintrust, Langfuse, Promptfoo, RAGAS all support this pattern.

**Assessment:**
- **Relevance:** HIGH — Parallax's eval loop is the competitive edge. Stronger eval = faster iteration = more accurate predictions by deadline.
- **Effort:** MEDIUM — Integrate judge LLM into eval cron, implement shadow table, add feature flag logic.
- **Risk:** LOW — Eval is offline; no impact on live predictions.

**Sources:**
- [A/B Testing LLM Applications: 2026 Guide](https://atlan.com/know/ab-testing-llm-applications/)
- [LLM Eval Frameworks](https://www.promptlayer.com/blog/llm-eval-framework/)
- [Braintrust A/B Testing](https://braintrust.dev/articles/ab-testing-llm-prompts)

#### Finding 4.2: Calibration Tracking (Confidence → Accuracy Alignment) (MEDIUM relevance, LOW effort, QUICK WIN)

**What:** Parallax already logs confidence scores on predictions. Current scoring measures direction/magnitude accuracy but not calibration (are 0.8 predictions actually right 80% of the time?).

**Quick Implementation:**
1. Group predictions by confidence bucket (0.5-0.6, 0.6-0.7, 0.7-0.8, 0.8-0.9, 0.9+).
2. For each bucket, compute hit rate over rolling 7-day window.
3. If 0.8 bucket's actual hit rate is 0.6, flag miscalibration.
4. Use recalibration function (existing in `scoring/recalibration.py`) to adjust future predictions.

**Assessment:**
- **Relevance:** MEDIUM — Calibration is harder to game than pure accuracy. Better metric.
- **Effort:** LOW — Query already exists. Add dashboard visualization + recalibration trigger.
- **Timeline:** 1-2 day task. Do during current eval loop.

---

### 5. Performance & Frontend

#### Finding 5.1: React Batching & Render Decoupling (LOW-MEDIUM relevance, LOW effort, BEST PRACTICE)

**What:** Current frontend risk: high-frequency WebSocket updates (hex changes, agent decisions) can trigger React re-renders that freeze deck.gl canvas.

**Mitigation (Already Documented in Design Spec):**
- H3 hex data lives in `useRef`, not `useState`.
- WebSocket `cell_update` messages batch into ref for 100ms, then flush.
- React re-renders only for UI changes (agent feed, indicators), not hex data.

**Status:** Design spec already specifies this correctly. Implementation should follow it.

**Assessment:**
- **Relevance:** LOW-MEDIUM — Already addressed in architecture. Risk: implementation drift.
- **Effort:** LOW — Enforce via code review when frontend is built.

**Sources:**
- [Real-Time Performance: WebSockets & React](https://medium.com/@SanchezAllanManuel/optimizing-real-time-performance-websockets-and-react-js-integration-part-i-e563664647d3)
- [React Batching & Backpressure](https://stevekinney.com/courses/react-performance/real-time-scale-strategies)

#### Finding 5.2: WebSocket Backpressure & Batching (LOW relevance, LOW effort, DEFENSIVE)

**What:** If backend pushes updates faster than frontend can render, buffer should not grow unbounded. Implement backpressure:
- Frontend sends ACK per batch.
- Backend holds updates in queue until ACK received.
- If queue grows, backend degrades gracefully (skip non-critical updates, e.g., hex opacity tweaks).

**Assessment:**
- **Relevance:** LOW — Not critical for Phase 1's modest update rates (<<1000/sec).
- **Effort:** LOW — Add a simple AsyncQueue + ACK pattern in FastAPI.
- **Defer:** Phase 2 scaling.

---

## Top 3 Recommendations

### 1. **Implement Batch API + Prompt Caching for Eval (HIGH impact, $1-2/day savings, 2-3 day effort)**

Deploy Claude Batch API for overnight eval runs and daily scoring. Cache agent system prompts. This compounds over 30 days ($30-60 savings on the Phase 1 eval run), reducing total project cost from ~$150 to ~$90-120. Operationally, it also speeds up eval cron (parallel batch processing vs. sequential sync calls).

**Owner:** Backend  
**Dependencies:** None  
**Timeline:** Week of Nov 16  

---

### 2. **Add Judge-Based Eval & Auto-Recalibration (HIGH impact, faster iteration, 3-4 day effort)**

Upgrade `scoring/calibration.py` to use a judge LLM (Sonnet, cached system prompt) to score agent outputs on a 1-5 scale. Add calibration bucket tracking to dashboard. This enables automated prompt refinement: if country agent accuracy drops, system automatically adjusts `agent_prompts` with recalibration flag and creates new version `v1.2.1` for canary testing. Multiplies iteration speed by ~3x.

**Owner:** Scoring team + Admin dashboard  
**Dependencies:** Batch API work (for cost alignment)  
**Timeline:** Week of Nov 23  

---

### 3. **Defer LSEG Vessel Tracking API to Phase 2 (Lower priority)**

Real-time AIS is valuable for ground-truth validation, but costs unknown. In Phase 1, simulate vessel tracking using GDELT vessel mentions + cascade flow model. If Phase 1 ends with strong eval results, budget a week in Phase 2 to integrate LSEG API.

**Owner:** Data team (deferred)  
**Timeline:** Post-April 2026  

---

## Implementation Checklist

- [ ] Contact Anthropic support to confirm batch + cache pricing stacking (verify with real test bill)
- [ ] Benchmark DuckDB R-tree indexing on daily scorecard queries
- [ ] Prototype batch API eval runner; measure latency and cost vs. current
- [ ] Implement judge LLM scoring in eval cron
- [ ] Add calibration bucket tracking to dashboard
- [ ] Implement feature flag system for prompt versions
- [ ] Code review on React render patterns (ensure useRef + batching implemented)
- [ ] Monitor Phase 1 eval window for Llama alternative experiments (low priority, defer)

---

## Sources

### Spatial & Geospatial
- [DuckDB 2.0 Performance Guide](https://duckdb.org/docs/2.0/guides/performance/overview)
- [Spatial queries with R-tree and H3 indexing (March 2025)](https://aetperf.github.io/2025/03/04/Spatial_queries_in_DuckDB_with_R-tree_and_H3_indexing.html)
- [15x Faster Geospatial Pipelines: DuckDB vs Pandas](https://chinmaydeval.netlify.app/blog/15x-faster-geospatial-pipelines-why-i-swapped-pandas-for-duckdb/)
- [Using DuckDB's Hilbert Curve with GeoParquet](https://cloudnativegeo.org/blog/2025/01/using-duckdbs-hilbert-function-with-geoparquet/)

### LLM & Agent Orchestration
- [Combining Caching with Batch API (March 2026)](https://claude-skills-guide-3lc.pages.dev/combining-caching-batch-api-95-percent-savings/)
- [Claude Batch API Documentation](https://platform.claude.com/docs/en/build-with-claude/batch-processing)
- [Opus 4.8 Release Notes (May 2026)](https://platform.claude.com/docs/en/release-notes/overview)
- [LLM API Pricing Comparison 2026](https://inference.net/content/llm-api-pricing-comparison/)
- [Cheapest LLM APIs 2026](https://costbench.com/best/cheapest-llm-api/)
- [A/B Testing LLM Prompts: 2026 Guide](https://atlan.com/know/ab-testing-llm-applications/)
- [Prompt Management & Versioning](https://kindatechnical.com/mlops-guide/prompt-management-versioning-testing-and-ab-testing.html)

### Real-Time Data
- [LSEG Vessel Tracking API Launch (March 2026)](https://www.pulse.bot/transportation/news/lseg-launches-real-time-vessel-tracking-api-bfbe1be2-3a45-4dde-9d46-1e19cab4146e)
- [Real-Time Vessel Monitoring Platforms 2026](https://www.shipuniverse.com/tech/real-time-vessel-monitoring-platforms-compared-in-2026/)
- [GDELT Cloud Documentation](https://docs.gdeltcloud.com/)
- [Free Geopolitical Data APIs 2026](https://www.worldmonitor.app/blog/posts/free-geopolitical-data-apis-2026/)

### Evaluation & MLOps
- [A/B Testing LLM Applications: 2026 Guide](https://atlan.com/know/ab-testing-llm-applications/)
- [LLM Evaluation Frameworks](https://www.promptlayer.com/blog/llm-eval-framework/)
- [Braintrust A/B Testing](https://braintrust.dev/articles/ab-testing-llm-prompts)
- [FeatBit Prompt A/B Testing](https://www.featbit.co/blogs/ab-testing-llm-prompts)

### Performance & Frontend
- [Real-Time Performance: WebSockets & React](https://medium.com/@SanchezAllanManuel/optimizing-real-time-performance-websockets-and-react-js-integration-part-i-e563664647d3)
- [React Real-Time Scale Strategies](https://stevekinney.com/courses/react-performance/real-time-scale-strategies)

---

**Report Generated:** 2026-11-09  
**Next Research Window:** 2026-11-23 (post-recommendation implementation review)
