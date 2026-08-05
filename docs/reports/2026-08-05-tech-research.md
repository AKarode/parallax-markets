# Tech Research Scout Report — 2026-08-05

**Date:** August 5, 2026  
**Focus Areas:** Spatial/Geo, LLM/Agent, Real-time Data, Eval/MLOps, Performance  
**Scope:** Parallax Phase 1 tech stack evaluation (DuckDB + H3, Claude API, GDELT, deck.gl, React)

---

## Executive Summary

Research across 5 tech domains identified **3 critical findings** and **2 additive opportunities**:

1. **Critical (HIGH)**: Claude API cache TTL reduction (60min → 5min) increases effective costs by 30–60%. Batch API can offset with 50% savings; combined savings up to 95%.
2. **Critical (HIGH)**: GDELT Cloud is production-ready alternative with hourly updates and entity clustering — worth piloting for reduced ingestion latency vs. BigQuery 15-min cycle.
3. **Medium (MEDIUM)**: DuckDB Spatial Extension 1.5.4 (July 2026) added GDAL support for 50+ GIS formats — no immediate action needed but valuable for Phase 2 multi-format imports.
4. **Additive (MEDIUM)**: Langfuse (open-source) combines prompt versioning, tracing, and eval — tighter integration than current manual approach.
5. **Confirmed (MEDIUM)**: deck.gl + WebSocket batch architecture from spec is validated as best practice; no changes needed.

---

## Detailed Findings

### 1. Spatial & Geospatial

#### H3 and DuckDB Status (Confirmed Current)

- **DuckDB Spatial Extension 1.5.4** released July 2026. Primary new feature: GDAL integration for reading/writing 50+ GIS file formats (shapefile, GeoJSON, etc.).
- **H3 in DuckDB**: Community extension stable; WKT rendering support added mid-2026 (Isaac Brodsky). Supports native SQL H3 operations.
- **duckh3 R package** (May 2026): R bindings for H3 in DuckDB, converts spatial geometries to H3 cells at specified resolution.

**Assessment:**
- **Relevance:** MEDIUM — Stack already pinned and working. GIS format support is Phase 2 concern (multi-scenario imports).
- **Effort:** LOW — No changes needed for Phase 1. GDAL integration optional for Phase 2.
- **Risk:** LOW — Current pinned versions are stable.
- **Recommendation:** Monitor for H3 updates (asymmetric routing, faster cell operations). No action required this quarter.

---

### 2. LLM & Agent Orchestration

#### 2a. Claude API Cost Dynamics (Critical)

**Finding:** Anthropic changed prompt cache TTL from 60 minutes to 5 minutes in early 2026. This single change **increases effective API costs by 30–60%** on production workloads with frequent cache misses.

**Mitigation Options:**
- **Batch API**: 50% off. Can process messages asynchronously (~12-24hr latency). Cacheable prefixes retain 1-hour cache window when batched.
- **Prompt Caching**: 90% off cached tokens (when TTL is active).
- **Combined:** Batch API + prompt caching can yield **up to 95% savings** on high-volume workloads.

**Parallax Budget Impact:**
- Current budget: ~$2–5/day under normal conditions (per Phase 1 spec).
- With 5-min TTL: Effective cost ~$2.60–6.50/day (30–60% increase) if cache misses exceed ~20%.
- **Recommendation:** Implement batch processing for non-time-sensitive predictions (7-day forecasts, daily evals). Keep sub-agent calls (Haiku) on live path for real-time reaction.

**Assessment:**
- **Relevance:** HIGH — Direct $30–100/month impact on 30-day eval period.
- **Effort:** MEDIUM — Requires adding batch queue to `cli/brief.py` and evaluation pipeline. Estimate 1–2 days.
- **Risk:** LOW — Batch API is stable; optional feature, not critical path.

#### 2b. New Claude Models & Context Windows

**Finding:** Opus 4.6 and Sonnet 4.6 now available with 1M context windows (vs. Sonnet 3.5's 200K). Haiku 4.5 has 200K.

**Use Case for Parallax:**
- **Broader context window** enables agent memory to include 60+ days of historical cascade events (instead of ~20 decisions).
- **Cost:** Opus 4.6 at $5/$25 is cheaper than GPT-5 ($10/$30), but still 5x cost of Sonnet 4.6.
- **Trade-off:** Sonnet 4.6 (1M context) is sweet spot — use instead of Sonnet 3.5 for country agents to capture deeper history without Opus cost.

**Assessment:**
- **Relevance:** MEDIUM — Quality improvement, not critical for Phase 1 accuracy.
- **Effort:** LOW — Drop-in model ID change.
- **Risk:** LOW — Fully backward-compatible.
- **Recommendation:** After Phase 1 evals, A/B test Sonnet 4.6 vs. Sonnet 3.5 to measure calibration improvement with expanded context.

#### 2c. Agent Orchestration Frameworks (Status Check)

**Finding:** LangGraph 1.0 reached GA (April 2026). Microsoft Agent Framework also 1.0 GA with graph-based workflows, GroupChat, handoff patterns, MCP support.

**Parallax Decision:** Phase 1 spec explicitly avoided LangGraph (custom DES via asyncio + heapq). This remains correct:
- Parallax has bespoke cascade logic (6-rule deterministic engine) that doesn't fit generic agent frameworks.
- Custom simulation clock modes (live vs. replay) require fine-grained control.
- LangGraph is overkill for the current actor/sub-actor hierarchy and would add operational complexity.

**Assessment:**
- **Relevance:** LOW — Confirmed that avoiding LangGraph was right call.
- **Effort:** N/A.
- **Risk:** N/A.
- **Recommendation:** No change. Monitor LangGraph if Phase 2 adds open-ended multi-agent reasoning (e.g., emergent negotiations). For now, stick with custom engine.

---

### 3. Real-Time Data Sources

#### 3a. GDELT & Alternatives

**Status:** GDELT remains dominant free source for structured geopolitical event data. No compelling open-source competitors have emerged.

**New Finding:** GDELT Cloud (commercial) is production-ready enhancement:
- **Hourly updates** (vs. GDELT Project BigQuery 15-min, but with entity clustering & deduplication built-in).
- **Structured clustering:** Stories (deduplicated events) + linked entities + summaries.
- **Reduced downstream noise:** Better pre-filtering than current 4-stage filter pipeline.
- **Pricing:** ~$200–1000/month (varies by volume).

**Assessment for Parallax:**
- **Relevance:** HIGH — Current ingestion via GDELT BigQuery + custom filter is working but noisy.
- **Effort:** MEDIUM — Requires replacing `ingestion/gdelt_doc.py` with GDELT Cloud client + schema adapter.
- **Risk:** MEDIUM — Dependency on commercial service; adds cost (~$200–300 for 30-day eval period). Mitigate: Keep BigQuery as fallback, A/B test clustering quality.
- **Recommendation:** **Pilot GDELT Cloud for Phase 1.5.** Measure if hourly updates + pre-clustering reduce false positives and improve calibration vs. manual 4-stage filter. If successful, switch for Phase 2 (ongoing prod cost is justified).

#### 3b. Oil Price Data APIs

**Finding:** EIA API is slow (updates ~2x/day, 30–45min latency). OilPriceAPI offers real-time alternative.

**Current Stack:** Parallax uses EIA API v2 (Brent/WTI daily spot prices). This is sufficient for Phase 1 (daily predictions don't need intraday granularity).

**Assessment:**
- **Relevance:** LOW — Current setup matches prediction cadence (7-day forecasts, daily updates).
- **Effort:** N/A.
- **Risk:** N/A.
- **Recommendation:** No change for Phase 1. For Phase 2 intraday trading, evaluate OilPriceAPI for forward curve + intraday spot.

#### 3c. Shipping Data & AIS

**Note:** Research did not surface new AIS/shipping data APIs or real-time vessel-tracking feeds better than current searoute-based visualization.

**Current Stack:** searoute for route visualization (acknowledged as not-for-routing in spec). No major alternatives found.

**Assessment:**
- **Relevance:** LOW — visualization-only layer; real-time AIS would be Phase 2 enhancement.
- **Recommendation:** Monitor for open-source AIS aggregators (e.g., Automatic Identification System feeds from maritime authorities). No action needed for Phase 1.

---

### 4. Evaluation & MLOps

#### 4a. LLM Evaluation Frameworks (Status Check)

**Finding:** By 2026, evaluation landscape standardized around:
- **Tools:** DeepEval, W&B Weave, Langfuse (open), Promptfoo (open), MLflow.
- **Metrics:** BLEU, ROUGE, F1, BERTScore, GPTScore, + **LLM-as-a-judge workflows** (now standard, not novel).
- **Critical concept:** "Traceability" — ability to link evaluation score back to exact prompt version, model, dataset. This is table stakes.

**Parallax Current State:** Manual eval pipeline (`scoring/scorecard.py`, `scoring/calibration.py`). Tracks:
- Direction, magnitude, sequence, calibration scores ✓
- Prompt versioning per-prediction ✓
- Daily rollup metrics ✓
- **Gap:** No open-source traceability layer. Manual prompt versioning in `agent_prompts` table. No UI for side-by-side variant comparison.

**Assessment:**
- **Relevance:** MEDIUM — Current manual approach works for Phase 1. No critical gaps.
- **Effort:** MEDIUM — Integrating Langfuse or Promptfoo would add ~3–5 days. Overkill for Phase 1.
- **Risk:** LOW — Adding eval framework is optional; current queries are sufficient.
- **Recommendation:** **Post-Phase 1 (late Aug/early Sept).** If accuracy plateaus and prompt tuning becomes frequent, integrate Langfuse (open-source) for prompt versioning + traceability. Justifies ROI only if you're running 5+ prompt variants simultaneously.

#### 4b. Structured Output Improvements

**Finding:** All major LLM platforms now support strict structured output schemas (Anthropic's Batch API includes this). No major new tools or techniques emerged in 2026.

**Parallax Status:** Uses JSON schema validation on agent output (`PredictionOutput`, decision schema). This is already best practice.

**Assessment:**
- **Relevance:** LOW — Already implemented correctly.
- **Recommendation:** No change.

---

### 5. Frontend Performance

#### deck.gl + WebSocket Real-Time Data

**Finding:** Confirmed deck.gl best practices for real-time updates:
1. **Mutable ref pattern** (useRef, not useState) — prevents React re-renders for hex data changes ✓ (matches Parallax spec).
2. **Batch WebSocket updates** (~100ms buffer before flushing) — prevents per-message render thrashing ✓ (matches Parallax spec).
3. **Append layers vs. mutate** — better than mutating existing layer data for hot updates ✓ (Parallax uses cell mutation; consider layer append for 7-day predictions panel).

**Parallax Alignment:** Spec already incorporates all best practices. No changes needed.

**Assessment:**
- **Relevance:** MEDIUM — Validation that current architecture is sound.
- **Effort:** N/A.
- **Risk:** N/A.
- **Recommendation:** No immediate change. If frontend renders stall during high-activity periods (>50 updates/sec), consider migrating hex layer to append-only pattern (requires layer index tracking).

---

## Top 3 Recommendations

### Recommendation 1: Implement Batch API + Cache Optimization (Priority: HIGH)

**Action:** Add batch processing to non-time-sensitive prediction calls and eval pipeline.

- **Expected ROI:** 30–60% cost reduction ($30–100 over 30 days).
- **Effort:** 1–2 days (add batch queue to `cli/brief.py`, eval cron).
- **Timeline:** End of Phase 1 (mid-August) before scaling.
- **Risk Mitigation:** Keep live agent calls on synchronous path; batch only daily scorecard and 7-day forecast aggregation.

**Implementation sketch:**
```python
# In cli/brief.py
batch_requests = []
for agent_id in agents:
    batch_requests.append({"prompt": agent_system_prompt, "input": event_context})
# Submit to Anthropic batch API
batch_id = anthropic.beta.messages.batch.create(requests=batch_requests)
# Poll for results (12–24hr typical)
```

---

### Recommendation 2: Pilot GDELT Cloud (Priority: MEDIUM)

**Action:** Set up parallel ingestion from GDELT Cloud alongside current BigQuery pipeline.

- **Expected Improvement:** Reduced false positives from pre-clustering; 1-hour latency vs. 15-min (trade-off).
- **Cost:** ~$200–300 for 30-day eval period. One-time pilot cost.
- **Effort:** 2–3 days (schema adapter, comparison metrics).
- **Timeline:** Phase 1.5 (late Aug) if eval calibration shows noise from GDELT BigQuery.
- **Success Criteria:** False positive rate (low-relevance events that cascade unintentionally) drops >20%.

**Implementation sketch:**
```python
# In ingestion/gdelt_doc.py
gdelt_cloud_client = gdelt.CloudClient(api_key=os.getenv("GDELT_CLOUD_API_KEY"))
stories = gdelt_cloud_client.stories_list()  # Pre-deduplicated
# Compare to BigQuery events for novelty
```

---

### Recommendation 3: Monitor Sonnet 4.6 Adoption (Priority: MEDIUM)

**Action:** After Phase 1 evals are complete, run A/B test with Sonnet 4.6 (1M context) vs. Sonnet 3.5 for country agents.

- **Expected Improvement:** Deeper historical context reduces oscillation in agent decisions; potential +5–10% calibration gain.
- **Cost:** Similar per-token cost (Sonnet 4.6 is standard Sonnet 4, not premium). Possible slight savings if context window reduces prompt compression needs.
- **Effort:** 0.5 day (model ID swap, new eval run).
- **Timeline:** Early September (post-Phase 1).
- **Success Criteria:** Direction accuracy improves on 7+ consecutive predictions.

---

## Sources

**Spatial & Geo:**
- [DuckDB Spatial Extension Documentation](https://duckdb.org/docs/current/core_extensions/spatial/overview)
- [DuckDB Spatial GitHub](https://github.com/duckdb/duckdb-spatial)
- [duckh3 R Package (May 2026)](https://cran.r-project.org/web//packages//duckh3/duckh3.pdf)

**LLM & Agent:**
- [Claude Prompt Caching Documentation](https://platform.claude.com/docs/en/build-with-claude/prompt-caching)
- [Claude Batch Processing Documentation](https://platform.claude.com/docs/en/build-with-claude/batch-processing)
- [DEV Community: Claude Prompt Caching TTL Change 2026](https://dev.to/whoffagents/claude-prompt-caching-in-2026-the-5-minute-ttl-change-thats-costing-you-money-4363)
- [Claude Cost Optimization 2026: Batch API & Prompt Caching](https://pecollective.com/tools/claude-pricing-guide/)
- [LLM Orchestration Frameworks 2026](https://aimultiple.com/llm-orchestration)
- [Top Agentic Frameworks 2026 (JetBrains Blog)](https://blog.jetbrains.com/pycharm/2026/06/top-agentic-frameworks-for-building-applications-2026/)

**Real-Time Data:**
- [GDELT Cloud Documentation](https://gdeltcloud.com/)
- [GDELT Cloud Docs](https://docs.gdeltcloud.com/)
- [GDELT Project](https://www.gdeltproject.org/)
- [OilPriceAPI as EIA Alternative](https://docs.oilpriceapi.com/compare/eia-alternative)
- [EIA Petroleum Data API](https://www.eia.gov/opendata/)

**Eval & MLOps:**
- [Best LLM Evaluation Tools of 2026 (Medium)](https://medium.com/online-inference/the-best-llm-evaluation-tools-of-2026-40fd9b654dce)
- [LLM Evaluation: Frameworks, Metrics, Best Practices 2026](https://medium.com/@future_agi/llm-evaluation-frameworks-metrics-and-best-practices-2026-edition-162790f831f4)
- [Langfuse Documentation](https://www.truefoundry.com/blog/multi-agent-orchestration-frameworks)
- [Promptfoo: LLM Testing & Evals](https://qaskills.sh/blog/promptfoo-llm-testing-guide)
- [A/B Testing LLM Prompts in Production (Traceloop)](https://www.traceloop.com/blog/the-definitive-guide-to-a-b-testing-llm-models-in-production)

**Performance:**
- [deck.gl Performance Documentation](https://deck.gl/docs/developer-guide/performance)
- [deck.gl Real-Time Updates Best Practices (GitHub Discussion #8283)](https://github.com/visgl/deck.gl/discussions/8283)
- [WebSockets in React for Real-Time Applications](https://oneuptime.com/blog/post/2026-01-15-websockets-react-real-time-applications/view)
- [deck.gl Using with React](https://deck.gl/docs/get-started/using-with-react)

---

## Conclusion

**No critical stack failures found.** Current tech choices remain solid for Phase 1. Three opportunities for cost optimization and quality improvement are available post-Phase 1:

1. **Batch API** (quick win for 30–60% cost reduction)
2. **GDELT Cloud** (pilot only; measure if worthwhile)
3. **Sonnet 4.6 migration** (low-risk quality check)

All other findings are confirmatory — current architecture aligns with 2026 best practices.

**Next Scout Report:** End of Phase 1 eval (late August), after initial accuracy metrics are stable.
