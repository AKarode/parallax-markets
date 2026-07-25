# Technology Research Scout Report
**Date:** 2026-07-25  
**Focus Areas:** Spatial/Geo, LLM/Agent, Real-time Data, Eval/MLOps, Performance

---

## Executive Summary

Parallax's tech stack is mature and well-positioned. Key research findings surface **three high-impact, medium-effort improvements**:

1. **Claude Batch API** (50% cost reduction) + prompt caching (90% off cached) — urgent for $20/day LLM budget
2. **Real AIS maritime tracking APIs** (Datalastic, AISstream.io) — unlocks live vessel positions for Hormuz visualization
3. **Prompt versioning platform** (Braintrust, Confident AI) — operationalizes the eval framework already built into the spec

No findings suggest stack replacements. Current choices (DuckDB, H3, deck.gl, FastAPI) remain best-in-class. Most improvements are additive optimizations.

---

## Findings by Category

### 1. Spatial & Geospatial

**Summary:** H3 remains dominant. Integration options are expanding in enterprise tools, but the open-source ecosystem is stable.

| Finding | Relevance | Effort | Risk | Notes |
|---------|-----------|--------|------|-------|
| **ArcGIS Pro 3.1 H3 support** | LOW | N/A | N/A | Enterprise-only. Not relevant unless adopting ArcGIS. |
| **Felt native H3 visualization** | MEDIUM | Low | Low | Browser-based alternative to deck.gl for demos. Add as optional secondary viewer for stakeholder demos. Not a replacement. |
| **DuckDB spatial + H3 ecosystem mature** | HIGH | Low | Low | `duckh3` R package published (May 2026); bindings stable. H3 community extension remains the right choice. |
| **deck.gl v9 streaming layers + async iterables** | HIGH | Medium | Low | Built-in support for incremental data updates without manual array merging. Enables efficient hex update batching. **Prioritize integration.** |
| **WebGPU support roadmap for deck.gl** | MEDIUM | High | Low | Future capability; not yet production. Revisit in 6 months. |

**Recommendation:** Upgrade to deck.gl's async iterable data sources and streaming layer support. This pairs with your planned batched WebSocket updates and reduces React re-render thrashing. ~2–3 hours integration work.

---

### 2. LLM / Agent Orchestration

**Summary:** Claude API cost optimizations are critical and immediately actionable. Agent orchestration frameworks are stable; LangGraph is production standard for deterministic control flows.

| Finding | Relevance | Effort | Risk | Notes |
|---------|-----------|--------|------|-------|
| **Claude Batch API (50% discount)** | **CRITICAL** | Medium | Low | Process daily brief, evals, and predictions in batches overnight. Cuts LLM spend by half. Applies to Sonnet/Opus calls. |
| **Prompt caching (90% off cached tokens)** | **CRITICAL** | Low | Low | **Warning:** TTL changed from 60min to 5min in early 2026 (breaks some cached workflows). Verify cache hit rates. Spec already includes this; verify implementation. |
| **Batch + Caching stack** | **CRITICAL** | Low | Low | Combine both: batch API jobs get prompt caching within the batch. Theoretical max: 95% cost reduction. Realistic: 60–75% with cache misses. |
| **LangGraph (vs custom DES)** | MEDIUM | High | Medium | Spec already chose custom DES over LangGraph for this exact reason: determinism + replay without LLM. **Stick with current choice.** LangGraph only if multi-scenario orchestration required in Phase 2. |
| **CrewAI (role-based agents)** | LOW | N/A | N/A | Spec uses country/sub-actor hierarchy already (similar abstraction). Not a replacement. |
| **Claude 5 family availability** | LOW | N/A | N/A | Spec pins Haiku/Sonnet for cost control. Opus 5 available but no budget headroom. Revisit if $20/day cap increases. |

**Top Recommendation:** Implement Batch API immediately. Wrap daily brief + eval cron in batch jobs. Estimated savings: **$8–12/day** (60% of current $20 budget). Target: 2–3 day implementation.

---

### 3. Real-Time Data Sources

**Summary:** GDELT remains the best free option. **Real AIS vessel tracking APIs are a genuine new edge** for Hormuz visualization that Parallax hasn't yet integrated.

| Finding | Relevance | Effort | Risk | Notes |
|---------|-----------|--------|------|-------|
| **GDELT Cloud (hourly vs 15-min)** | MEDIUM | Low | Low | Enhanced version with less latency-sensitive updates. Consider for non-crisis periods; stick with GDELT 2.0 for real-time. No cost difference. |
| **No viable GDELT replacement** | HIGH | N/A | N/A | Structured CAMEO event coding + tone scores remain unmatched. GDELT's combination of free + structured is irreplaceable. |
| **AIS vessel tracking APIs (Datalastic, VesselFinder, AISstream.io)** | **HIGH** | Medium | Medium | **Game-changer.** Real-time ship positions in Hormuz strait can feed directly into H3 cells and flow calculations. Currently missing. |
| **AIS data types: T-AIS (terrestrial) vs S-AIS (satellite)** | HIGH | N/A | N/A | T-AIS: near-real-time but coastal only (~40–60 NM). S-AIS: global but higher latency. Hormuz needs T-AIS (coastal chokepoint). |
| **Market consolidation risk** | MEDIUM | N/A | Medium | Kpler now owns MarineTraffic/Spire/FleetMon. Pricing may shift; diversify API providers. |

**Top Recommendation:** Evaluate AISstream.io (free WebSocket access to live AIS) as a Phase 1.5 feature. This transforms Hormuz traffic visualization from inferred (via cascade model) to observed (via real AIS). Effort: **3–5 days**. Adds realism to demo.

---

### 4. Evaluation & MLOps

**Summary:** Parallax's eval framework design is sound. Implementing a **prompt versioning platform** bridges the gap between the planned A/B testing logic and actual prompt management tooling.

| Finding | Relevance | Effort | Risk | Notes |
|---------|-----------|--------|------|-------|
| **Calibration crisis across all LLM models** | HIGH | Low | Low | Scale AI reports systematic high-confidence-on-wrong-answers. Implies even confident predictions need skeptical evaluation. Parallels Parallax's eval strategy (score calibration over 30-day window). **No action needed; spec already accounts for this.** |
| **LLM-as-Judge methods** | MEDIUM | Medium | Medium | 80–90% agreement with humans at 500–5000x lower cost. Could replace human eval bottleneck for ambiguous misses. Useful for Phase 1.5 scaling. |
| **Prompt versioning platforms (Braintrust, Confident AI, Latitude, PromptLayer)** | **HIGH** | High | Low | Spec assumes manual prompt versioning in DB + admin dashboard. **Adopting a platform cuts implementation time by 50%.** Enables A/B testing, git-style branches, PR workflows, auto-rollback on regression. |
| **A/B testing rigor (MDE, bootstrap CI, bandits)** | MEDIUM | High | Low | Spec's 7-day rolling accuracy window is good baseline. Moving to statistical rigor (confidence intervals, rollout strategies) is Phase 2 work. |
| **Eval frameworks (DeepEval, W&B Weave, MLflow)** | MEDIUM | Low | Low | General-purpose LLM eval. Parallax's domain-specific eval (hit rate, calibration, sequence accuracy) is custom. These tools are useful for monitoring but not essential. |

**Top Recommendation:** Pre-evaluate Braintrust or Confident AI for Phase 1.5 adoption. These platforms automate the prompt improvement pipeline (identify misses → suggest edits → review → deploy → monitor) described in the spec. ROI: saves 50+ hours of dashboard coding. **Decision point: 1 week exploration, $2-5K/month cost.**

---

### 5. Performance Optimization

**Summary:** Current architecture is sound. Three medium-effort wins unlock better real-time responsiveness.

| Finding | Relevance | Effort | Risk | Notes |
|---------|-----------|--------|------|-------|
| **DuckDB memory tuning (80% of available RAM)** | MEDIUM | Low | Low | Spec's single-writer queue design is correct. Add explicit PRAGMA memory_limit tuning to deployment. Prevents OOM on large snapshots. |
| **EXPLAIN ANALYZE as diagnostic tool** | MEDIUM | Low | Low | Use before/after optimization. Spec's world_state_delta + snapshot strategy already optimizes heavily. Marginal gains from query tuning. |
| **deck.gl v9 streaming + incremental updates** | HIGH | Medium | Low | **Paired with WebSocket batching** (spec already plans 100ms batching), this eliminates render thrashing. Upgrade priority. |
| **React Compiler (static-analysis optimization)** | MEDIUM | High | Low | Automatic memoization and unused render elimination. Requires React 19+. Current stack uses React 18.3.1. Upgrade decision for Phase 2. |
| **React 18 concurrent rendering** | HIGH | Medium | Low | Already in spec design (WebSocket handler updates mutable useRef, React re-renders only for UI changes). Ensure implementation follows this pattern strictly. |
| **WebTransport as future alternative to WebSocket** | LOW | High | Medium | Emerging protocol for lower latency. Not yet stable. Revisit 2027. |

**Top Recommendation:** Ensure WebSocket update batching (100ms window) is correctly implemented. Pair with deck.gl v9 streaming layers. This is a high-leverage, medium-effort combo that ensures dashboard remains responsive under high-frequency updates.

---

## Top 3 Recommendations

### 1. **Implement Claude Batch API + Prompt Caching Stack** (CRITICAL)
- **Why:** Cuts LLM spend by 60–75%, stretches $20/day budget to cover 2–3x current throughput
- **How:** Wrap daily brief + eval cron in batch jobs; verify prompt caching TTL settings
- **Effort:** 2–3 days
- **Timeline:** Implement before launch
- **Sources:** [Batch API docs](https://platform.claude.com/docs/en/build-with-claude/batch-processing), [Prompt Caching 2026 cost advisory](https://dev.to/whoffagents/claude-prompt-caching-in-2026-the-5-minute-ttl-change-thats-costing-you-money-4363)

### 2. **Integrate Real AIS Vessel Tracking (AISstream.io or Datalastic)** (HIGH IMPACT)
- **Why:** Transforms Hormuz traffic from inferred to observed; adds realism to demo; validates flow cascade model against ground truth
- **How:** Stream live vessel positions into H3 cells, feed into flow calculations, visualize on deck.gl
- **Effort:** 3–5 days
- **Timeline:** Phase 1.5 (post-launch, before 2-week eval window)
- **Sources:** [AIS API comparison](https://hormuzmonitor.com/50-best-ship-tracking-apis-2026/), [AISstream.io](https://aisstream.io/)

### 3. **Evaluate & Trial Prompt Versioning Platform (Braintrust or Confident AI)** (STRATEGIC)
- **Why:** Automates the A/B testing + prompt improvement pipeline; cuts implementation effort 50%; enables production-grade prompt management
- **How:** 1-week exploration trial; build a sample agent prompt experiment; measure time saved vs manual DB/dashboard approach
- **Effort:** 5–7 days exploration; $2–5K/month if adopted
- **Timeline:** Phase 1.5 decision (affects eval dashboard design)
- **Sources:** [A/B Testing guide for LLMs](https://futureagi.com/blog/ab-testing-llm-prompts-best-practices-2026/), [Braintrust](https://www.braintrust.dev/), [Confident AI](https://www.confident-ai.com/)

---

## Findings by Maturity & Stack Fit

| Category | Current | Finding | Action | Priority |
|----------|---------|---------|--------|----------|
| **LLM APIs** | Claude Sonnet + Haiku | Batch API + caching stack | Implement immediately | CRITICAL |
| **Spatial DB** | DuckDB + H3 community | Ecosystem mature; deck.gl v9 streaming | Upgrade deck.gl; verify H3 version | HIGH |
| **Geospatial viz** | deck.gl + MapLibre | Streaming layers + async iterables | Adopt v9 features for efficiency | HIGH |
| **Event data** | GDELT 2.0 (BigQuery) | No replacement; GDELT Cloud available | Stick with 2.0; optional upgrade to Cloud in Phase 2 | MEDIUM |
| **Shipping data** | Cascade model only (inferred) | Live AIS APIs (observed) | Trial AISstream.io | HIGH |
| **Eval framework** | Manual (spec design) | Prompt versioning platforms | Trial for 1 week | STRATEGIC |
| **Performance** | WebSocket + batching + mutable useRef | deck.gl streaming; React Compiler | Pair deck.gl v9 with batching; React 19 upgrade is Phase 2 | MEDIUM |

---

## Stack Health Assessment

✅ **Best-in-class choices (no changes needed):**
- DuckDB + H3 for spatial persistence
- deck.gl + MapLibre for visualization
- FastAPI + asyncio for backend
- Custom DES engine over LangGraph (correct for Phase 1 replay mode)

⚠️ **Optimizations (additive, no replacement):**
- Claude Batch API for cost control
- AIS APIs for ground-truth shipping data
- Prompt versioning platform for eval automation
- deck.gl v9 for render efficiency

❌ **No findings suggesting replacements** for core stack.

---

## Links & Sources

### Spatial/Geo
- [deck.gl Performance Guide](https://deck.gl/docs/developer-guide/performance)
- [deck.gl Real-time Updates Best Practices (GitHub Discussion)](https://github.com/visgl/deck.gl/discussions/8283)
- [DuckDB Spatial & H3 Ecosystem (Awesome DuckDB Spatial)](https://github.com/alperdincer/Awesome-DuckDB-Spatial)
- [duckh3 R Package](https://cran.r-project.org/web/packages/duckh3/index.html)

### LLM/Agent
- [Claude Batch API Docs](https://platform.claude.com/docs/en/build-with-claude/batch-processing)
- [Prompt Caching 2026 Cost Advisory (DEV Community)](https://dev.to/whoffagents/claude-prompt-caching-in-2026-the-5-minute-ttl-change-thats-costing-you-money-4363)
- [Claude Cost Optimization Stack](https://pecollective.com/tools/claude-pricing-guide/)
- [Best Multi-agent Frameworks 2026 (TrueFoundry)](https://www.truefoundry.com/blog/multi-agent-orchestration-frameworks)

### Real-time Data
- [AIS APIs Comparison (Strait of Hormuz Monitor)](https://hormuzmonitor.com/50-best-ship-tracking-apis-2026/)
- [AISstream.io](https://aisstream.io/)
- [Datalastic AIS API](https://datalastic.com/)
- [GDELT Project](https://www.gdeltproject.org/)
- [GDELT Cloud Docs](https://docs.gdeltcloud.com/)

### Eval/MLOps
- [LLM Evaluation Guide 2026 (Nextrendseo)](https://nextrendseo.wordpress.com/2026/06/30/llm-evaluation-guide/)
- [A/B Testing LLM Prompts Best Practices 2026 (Future AGI)](https://futureagi.com/blog/ab-testing-llm-prompts-best-practices-2026/)
- [Braintrust A/B Testing Guide](https://www.braintrust.dev/articles/ab-testing-llm-prompts)
- [Confident AI](https://www.confident-ai.com/)
- [PromptLayer](https://promptlayer.com/)
- [Latitude (Prompt Management)](https://latitude.sh/)

### Performance
- [DuckDB Performance Tuning Guide](https://duckdblab.org/en/post/duckdb-performance-tuning-5-tips/)
- [React Performance Optimization 2026 (Softaims)](https://softaims.com/blog/react-performance-optimization)
- [React Concurrent Rendering Guide (Relia Software)](https://reliasoftware.com/blog/concurrent-rendering-in-react)
- [Real-Time Dashboards with React 2026 (Sparkle Web)](https://www.sparkleweb.in/blog/building_real-time_business_dashboards_with_react_in_2026)

---

## Next Steps

1. **This week:** Spike Claude Batch API integration. Target: half-day PoC wrapping one prediction call in a batch job.
2. **Next week:** Trial AISstream.io. Stream 5 sample vessels into H3 cells; verify integration effort.
3. **Week 3:** Evaluation & decision: Adopt prompt versioning platform? (1-week trial to measure productivity gains.)

---

*Report generated by Claude Code technology scout — 2026-07-25*
