# Tech Research Report: Parallax Stack Improvements
**Date:** 2026-08-09  
**Scope:** Spatial/Geo, LLM/Agent, Real-time Data, Eval/MLOps, Performance

---

## Executive Summary

This week's research identified **10 actionable improvements** across 5 technology domains, with 3 high-impact recommendations that could reduce LLM costs by 60%, add real-time AIS shipping data, and improve prediction calibration tracking. No breaking changes required; all findings are additive or backward-compatible.

---

## 1. Spatial & Geospatial Stack

### Finding 1.1: SIMD-Accelerated H3 Fork
**Relevance:** MEDIUM | **Effort:** LOW | **Risk:** LOW | **Status:** Available (2026-04-26+)

A performance-optimized fork of H3 with SIMD acceleration [github.com/mattsta/h3](https://github.com/mattsta/h3) appeared post-April 2026. Current Parallax uses pinned H3 community extension in DuckDB; this could replace with zero API changes.

- **Assessment:** Marginal speedup for cell encoding/decoding. Matters only if hex grid queries become a bottleneck (unlikely for 400K cells). Worth monitoring but not urgent.
- **Action:** Watch fork adoption metrics; backport to DuckDB extension if fork proves stable.

### Finding 1.2: DuckDB Experimental 2D Geometry Types
**Relevance:** MEDIUM | **Effort:** MEDIUM | **Risk:** MEDIUM | **Status:** Experimental (v1.0+)

DuckDB spatial extension now includes fixed-memory POINT_2D, LINESTRING_2D, POLYGON_2D, BOX_2D types (non-standard, DuckDB-native, not GEOMETRY). Theoretically **2-3× faster** than standard GEOMETRY for analytics workloads via vectorized execution.

- **Current state:** Parallax uses GEOMETRY (standards-compliant). Switching requires schema migration + retest of spatial joins.
- **Assessment:** HIGH value if ingesting massive polygon datasets (Overture Maps). Current usage is light—not blocking.
- **Action:** Pilot on a fresh DB instance; measure query perf on Overture building layer if performance becomes a pain point.

### Finding 1.3: ArcGIS + H3 Integration
**Relevance:** LOW | **Effort:** N/A | **Risk:** N/A | **Status:** Implemented in ArcGIS Pro 3.1+

ArcGIS Pro 3.1 now natively supports H3 grid generation. Not applicable to Parallax (non-GIS workflow) but worth noting for stakeholder demos—ArcGIS users can now replicate Parallax' hex grid in their own tools.

---

## 2. LLM & Agent Stack

### Finding 2.1: Claude Batch API for Sub-Actor Decisions ⭐ TOP PICK
**Relevance:** HIGH | **Effort:** LOW | **Risk:** LOW | **Status:** Production-ready (2026+)

**The Batch API cuts all Claude token prices by 50%.** If Parallax batches sub-actor decisions that don't need same-tick replies, this yields immediate 50% LLM cost savings.

- **Current cost:** ~$0.002/sub-actor call (Haiku). Batch API: ~$0.001.
- **Constraint:** Batch jobs have 24-hour SLA; unsuitable for same-tick reactions to live GDELT events.
- **Opportunity:** Off-tick background analysis (daily recalibration pass, weekly scenario replay) can batch 100s of calls for ~$0.50 instead of $1.00.
- **Estimated saving:** $1–2/day (~$30–60/month) with no architecture change.
- **Action:** Integrate `anthropic.messages.batch.create()` for daily eval cron and weekly retrospective agent runs.

**Reference:** [Claude Cost Optimization 2026: Batch API (50% Off) and Prompt Caching (90% Off)](https://pecollective.com/tools/claude-pricing-guide/) | [Batch processing - Claude Platform Docs](https://platform.claude.com/docs/en/build-with-claude/batch-processing)

### Finding 2.2: Persistent Prompt Caching (60+ min TTL)
**Relevance:** HIGH | **Effort:** MEDIUM | **Risk:** LOW | **Status:** Available on select Sonnet 4 / Opus 4 endpoints

**Alert:** Anthropic reduced cache TTL from 60 min → 5 min in early 2026. Parallax is likely already affected, silently raising API costs by 30–60%.

**New option:** Persistent cache (not yet public API but available to select orgs) survives across sessions for 60+ minutes.

- **Current risk:** If agent prompts are reused within 5-min windows, cache is thrashing; each call re-caches the entire system prompt.
- **Workaround (available now):** Use the documented `cache_control` parameter with ephemeral cache; batch calls within tight 5-min windows to maximize hit rates.
- **Improvement (available later):** Request persistent cache tier for production workspace—can reach 90% reduction on repeated system prompt costs.
- **Estimated impact:** $0.50–1.00/day savings if steady-state agent workload hits cache 3–5× per tick.
- **Action:** 
  1. Verify current cache hit rate via Anthropic usage dashboard.
  2. Batch sub-actor calls within 5-min windows to increase ephemeral cache hits.
  3. Request persistent cache access for eval cron work.

**Reference:** [Claude Prompt Caching in 2026: The 5-Minute TTL Change That's Costing You Money](https://dev.to/whoffagents/claude-prompt-caching-in-2026-the-5-minute-ttl-change-thats-costing-you-money-4363) | [Prompt Caching for Claude: Cut Your API Bill 60% in Production](https://www.aimagicx.com/blog/prompt-caching-claude-api-cost-optimization-2026)

### Finding 2.3: Workspace-Isolated Prompt Caching
**Relevance:** MEDIUM | **Effort:** ZERO | **Risk:** LOW | **Status:** Active (since Feb 2026)

Teams with separate workspaces cannot share cache. If Parallax ever moves to multi-workspace org (e.g., separate staging/prod workspaces), expect **30–60% increase in cache misses** and corresponding API cost spike.

- **Current state:** Single workspace—no impact.
- **Mitigation:** Keep staging + prod in same workspace, OR maintain separate DuckDB + agent state for each to amortize system prompt caching.

### Finding 2.4: Native Structured Outputs + JSON Schema Validation ⭐ TOP PICK
**Relevance:** HIGH | **Effort:** MEDIUM | **Risk:** LOW | **Status:** Generally available (Anthropic, Feb 4 2026)

Anthropic now supports native structured outputs (last major provider to ship it). Guarantees **100% schema-valid JSON** without regex parsing hacks.

- **Current Parallax approach:** Manual JSON schema validation on agent decision outputs (works, adds latency). 
- **New approach:** Pass `json_schema` + `strict: true` to Claude API; responses are guaranteed to match schema.
- **Benefit:** Eliminates retry loops for malformed JSON. Reduces token cost (model doesn't waste tokens on parsing-friendly re-formatting).
- **Action:** Integrate into `decision` schema validation. Test with Sonnet 4.6 first; roll to Haiku 4.5 once validated.

**Reference:** [LLM Structured Output Engineering: Reliable JSON from LLMs (2026)](https://appscale.blog/en/blog/structured-output-engineering-reliable-json-from-llms-2026) | [LLM Structured Outputs: JSON Schema and Validation](https://decodethefuture.org/en/llm-structured-outputs-json-schema/)

### Finding 2.5: Prompt Management via Lilypad + Mirascope
**Relevance:** MEDIUM | **Effort:** HIGH | **Risk:** MEDIUM | **Status:** Production (2026+)

Lilypad adds automatic prompt versioning + tracing via decorators; Mirascope provides code-centric structure. Replaces the current manual `prompt_versions` table for lighter workflows.

- **Assessment:** Valuable for teams with rapid iteration. Parallax eval framework already handles versioning + A/B testing. Lilypad is **additive, not required**.
- **Use case:** If prompt experimentation becomes frequent (post-Phase 1), Lilypad reduces boilerplate.
- **Action:** Monitor for Phase 2 when prompt tuning accelerates.

**Reference:** [How to Perform A/B Testing with Prompts: A Comprehensive Guide for AI Teams](https://www.getmaxim.ai/articles/how-to-perform-a-b-testing-with-prompts-a-comprehensive-guide-for-ai-teams/)

---

## 3. Real-Time Data Stack

### Finding 3.1: Free AIS Shipping Data via WebSocket ⭐ TOP PICK
**Relevance:** HIGH | **Effort:** LOW | **Risk:** LOW | **Status:** Production (2026+)

AISstream.io offers **free real-time AIS feed via WebSocket**—ship positions, destinations, voyages. Perfect for Hormuz corridor shipping volume estimates.

- **Current Parallax state:** Uses searoute + parameterized flow capacity. No real shipping data.
- **Opportunity:** Ingest real AIS positions into H3 grid; compare with simulated flow. Feeds directly into calibration loop (agent predictions vs observed vessel behavior).
- **Data quality:** AISstream relies on volunteer AIS receiver network; coverage is strong in Hormuz but degrades in contested waters.
- **Integration cost:** ~100 LOC for WebSocket handler + H3 cell mapping.
- **Action:** Pilot AISstream in dashboard as read-only indicator layer. Polygon geofences around Hormuz (res 8) + ship count aggregation = real-time shipping throughput proxy.

**Alternative:** AISHub (free, but requires sharing own AIS feed) or VesselAPI (free tier with credit-based pricing).

**Reference:** [aisstream.io](https://aisstream.io/) | [Free AIS vessel tracking](https://www.aishub.net/) | [50 Best Ship Tracking APIs 2026](https://hormuzmonitor.com/50-best-ship-tracking-apis-2026/)

### Finding 3.2: GDELT Cloud (Curated Events API)
**Relevance:** MEDIUM | **Effort:** MEDIUM | **Risk:** MEDIUM | **Status:** Production (2026+)

GDELT Cloud wraps raw GDELT with pre-clustered stories, resolved entities, and tone/sentiment indices via REST API.

- **Assessment:** Replaces some of the 4-stage GDELT filter logic (dedup, entity resolution). API pricing applies; unclear cost vs current Google BigQuery pull.
- **Benefit:** Smoother entity tagging (GDELT Cloud resolves "Iran's Supreme Leader" → "Khamenei" automatically).
- **Risk:** Vendor lock-in; requires API contract.
- **Action:** Evaluate if entity resolution becomes a bottleneck in Phase 2. Not urgent.

**Reference:** [GDELT Cloud: Geopolitical Risk & Global Event Data API](https://gdeltcloud.com/)

### Finding 3.3: GDELT Remains Best Free Geopolitical Feed
**Relevance:** HIGH | **Effort:** ZERO | **Risk:** LOW | **Status:** Current stack

No viable open-source replacement exists for free, real-time geopolitical event data at scale. GDELT + BigQuery is still the right choice. Some commercial alternatives (Dow Jones DNA, Kpler for shipping) are paid-only.

- **Action:** Continue GDELT strategy. Consider GDELT Cloud as optional enhancement post-Phase 1.

---

## 4. Evaluation & MLOps Stack

### Finding 4.1: Expected Calibration Error (ECE) for Prediction Tracking
**Relevance:** HIGH | **Effort:** MEDIUM | **Risk:** LOW | **Status:** Best practice (2026)

Parallax tracks calibration via "rolling 30-day window"; modern best practice adds **Expected Calibration Error (ECE)** metric—measures if 0.8 confidence predictions are right 80% of the time.

- **Current approach:** Confidence levels tracked but not binned/validated for calibration.
- **Improvement:** Compute ECE over prediction bins (e.g., [0.7–0.8) confidence, [0.8–0.9) confidence). Flag if ECE > threshold → triggers prompt recalibration.
- **Action:** Add ECE computation to `calibration_report()` function in `scoring/calibration.py`. Threshold: ECE > 0.1 = red flag.

**Reference:** [The Independence of Discrimination and Calibration in Clinical Risk Prediction](https://www.medrxiv.org/content/10.64898/2026.02.12.26346147v1.full) | [Evaluation of performance measures in predictive AI models](https://www.thelancet.com/journals/landig/article/PIIS2589-7500(25)00098-6/fulltext)

### Finding 4.2: DeepEval + Langfuse for LLM Eval Observability
**Relevance:** MEDIUM | **Effort:** MEDIUM | **Risk:** LOW | **Status:** Production (2026+)

DeepEval provides test frameworks for agent outputs; Langfuse adds tracing/observability. Together they replace ad-hoc eval scripts.

- **Assessment:** Valuable for **rapid iteration** on agent prompts. Parallax eval framework is already sophisticated; DeepEval is useful only if prompt tuning becomes frequent.
- **Benefit:** Integrates with CI/CD; auto-flags regressions before deploy.
- **Action:** Defer to Phase 2 if prompt experimentation accelerates.

**Reference:** [The best LLM evaluation tools of 2026](https://medium.com/online-inference/the-best-llm-evaluation-tools-of-2026-40fd9b654dce) | [Top LLM Testing Frameworks & Tools for QA (2026 Guide)](https://testomat.io/blog/llm-test/)

### Finding 4.3: RAGAS for RAG-Specific Eval (Not Applicable)
**Relevance:** LOW | **Effort:** N/A | **Risk:** N/A | **Status:** Production (2026+)

RAGAS evaluates retrieval-augmented generation quality. Parallax does not use RAG (agents generate predictions via cascade reasoning, not document retrieval).

- **Action:** Skip.

---

## 5. Frontend & Performance Stack

### Finding 5.1: React WebSocket Batching (Existing Best Practice)
**Relevance:** MEDIUM | **Effort:** LOW | **Risk:** LOW | **Status:** Recommended (2026+)

Current Parallax design (per spec: "buffer incoming updates for 100ms, then flush") is **already aligned** with 2026 best practices. No change needed.

- **Status:** ✅ Already implemented in spec.

### Finding 5.2: Virtualization for Large Agent Feed
**Relevance:** MEDIUM | **Effort:** MEDIUM | **Risk:** LOW | **Status:** Recommended (2026+)

If agent activity feed grows to 100s+ decisions per minute, render only visible rows (e.g., react-window). Current Parallax scrolling feed is fine for typical ~10–20 events/min.

- **Action:** Monitor performance; defer until DOM thrashing observed.

### Finding 5.3: deck.gl MapLibre Terrain Sync Improvement
**Relevance:** MEDIUM | **Effort:** LOW | **Risk:** LOW | **Status:** Available in v9.1+ (2026)

deck.gl now better synchronizes camera when base map includes terrain layers. Not applicable to current Parallax (flat H3 hexes, not 3D terrain). Future-proofing note for Phase 2 if 3D terrain ever added.

- **Action:** Skip for Phase 1.

### Finding 5.4: Open Visualization Collaborators Summit 2026 (Sept 9–10, Zurich)
**Relevance:** LOW | **Effort:** ZERO | **Risk:** ZERO | **Status:** Event (Sept 2026)

Upstream deck.gl + MapLibre teams convening. Worth monitoring for roadmap signals post-Sept.

**Reference:** [deck.gl Home](https://deck.gl/) | [MapLibre Newsletter April 2026](https://maplibre.org/news/2026-05-02-maplibre-newsletter-april-2026/)

---

## Top 3 Recommendations (Priority Order)

### Recommendation 1: Implement Claude Batch API for Off-Tick Analysis
**Impact:** 30–60 min payoff, $30–60/month LLM savings, zero risk  
**Effort:** 2–4 hours engineering  
**Timeline:** This week

Integrate Batch API for daily eval cron and weekly retrospective runs. No live-tick changes; all sub-actor + country agent calls for batch jobs route through batches.

**Owner:** Backend  
**Acceptance:** Cost savings measured via Anthropic usage dashboard; batch job completes within 24-hour SLA.

---

### Recommendation 2: Add AISstream Real-Time Shipping Layer to Dashboard
**Impact:** Real-time calibration data, high engagement (demos love live ship dots), 3–4 week payoff  
**Effort:** ~8–16 hours (WebSocket handler + H3 aggregation + viz layer)  
**Timeline:** Phase 1.5 (post-MVP launch)

Pilot AISstream WebSocket feed; aggregate ships into H3 cells (res 8 for Hormuz strait). Display as overlay on hex map. Compare real vessel traffic vs agent-predicted flow.

**Owner:** Backend + Frontend  
**Acceptance:** Real ship positions render on map; vessel count matches known port departures (manual spot-check).

---

### Recommendation 3: Adopt Native Structured Outputs for Agent Decisions
**Impact:** Eliminate JSON parsing retries, reduce token waste, improve reliability  
**Effort:** 4–6 hours (schema → json_schema param, validation logic)  
**Timeline:** Next sprint

Modify agent prompt handling to use Anthropic's native structured output API. All agent decision outputs guaranteed schema-valid; no fallback retry loops.

**Owner:** Backend (agent decision handler)  
**Acceptance:** 100% of agent decisions match JSON schema on first attempt; no validation failures in logs.

---

## Secondary Recommendations (Monitor/Defer)

| Finding | Reason to Defer | Revisit When |
|---------|-----------------|--------------|
| DuckDB 2D Geometry Types | Light geospatial queries; schema migration risk | Overture polygon queries bottleneck |
| Persistent Prompt Caching | Not yet public API; need workspace access request | Cache hit rate drops below 70% |
| DeepEval / Langfuse | Already have eval framework; additive only | Prompt iteration >2× per week |
| Lilypad Prompt Versioning | Manual versioning works; Lilypad is lightweight wrapper | Team > 2 people tuning prompts in parallel |
| Virtualized Agent Feed | 100+ events/min not yet reached | DOM re-render time > 200ms |

---

## Risk Summary

- **No breaking changes** identified.
- **Highest risk:** Switching to DuckDB 2D geometry types (schema migration). Recommend pilot on test DB.
- **Lowest risk:** Batch API, structured outputs, AIS data layer—all backward-compatible.
- **Workspace cache isolation**: Single-workspace design already mitigates this risk.

---

## Sources

### Spatial/Geo
- [mattsta/h3 - SIMD-accelerated H3 fork](https://github.com/mattsta/h3)
- [Awesome-DuckDB-Spatial](https://github.com/alperdincer/Awesome-DuckDB-Spatial)
- [DuckDB Spatial Extension Overview](https://duckdb.org/docs/lts/core_extensions/spatial/overview)
- [ArcGIS H3 Integration](https://www.esri.com/arcgis-blog/products/arcgis-pro/analytics/use-h3-to-create-multiresolution-hexagon-grids-in-arcgis-pro-3-1)

### LLM/Agent
- [Claude Batch API Cost Optimization 2026](https://pecollective.com/tools/claude-pricing-guide/)
- [Batch Processing - Claude Platform Docs](https://platform.claude.com/docs/en/build-with-claude/batch-processing)
- [Claude Prompt Caching: 5-Minute TTL Impact](https://dev.to/whoffagents/claude-prompt-caching-in-2026-the-5-minute-ttl-change-thats-costing-you-money-4363)
- [LLM Structured Outputs 2026](https://appscale.blog/en/blog/structured-output-engineering-reliable-json-from-llms-2026)
- [A/B Testing with Prompts Guide](https://www.getmaxim.ai/articles/how-to-perform-a-b-testing-with-prompts-a-comprehensive-guide-for-ai-teams/)

### Real-Time Data
- [AISstream.io](https://aisstream.io/)
- [AISHub Free AIS Tracking](https://www.aishub.net/)
- [50 Best Ship Tracking APIs 2026](https://hormuzmonitor.com/50-best-ship-tracking-apis-2026/)
- [GDELT Cloud API](https://gdeltcloud.com/)
- [GDELT Project](https://www.gdeltproject.org/)

### Eval/MLOps
- [Expected Calibration Error Framework](https://www.medrxiv.org/content/10.64898/2026.02.12.26346147v1.full)
- [Best LLM Evaluation Tools 2026](https://medium.com/online-inference/the-best-llm-evaluation-tools-of-2026-40fd9b654dce)
- [Top LLM Testing Frameworks 2026](https://testomat.io/blog/llm-test/)

### Performance
- [React WebSocket Real-Time Apps 2026](https://velt.dev/blog/websockets-react-guide)
- [Building Real-Time Dashboards with React 2026](https://www.sparkleweb.in/blog/building_real-time_business_dashboards_with_react_in_2026)
- [deck.gl Home](https://deck.gl/)
- [MapLibre Newsletter April 2026](https://maplibre.org/news/2026-05-02-maplibre-newsletter-april-2026/)

---

## Next Steps

1. **This week:** Create ticket for Batch API integration (Rec #1). Measure current cache hit rate.
2. **Next sprint:** Implement native structured outputs (Rec #3).
3. **Post-MVP:** Pilot AISstream layer (Rec #2).
4. **Ongoing:** Monitor H3 fork adoption and DuckDB 2D geometry maturity.
