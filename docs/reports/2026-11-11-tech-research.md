# Tech Research Scout Report — 2026-11-11

**Focus areas:** Spatial/Geo indexing, LLM/Agent orchestration, Real-time data sources, Eval frameworks, Frontend performance

---

## Findings

### Spatial/Geo

#### H3 Community Fork with SIMD Optimization — **MEDIUM relevance**
- **Status:** A community fork (mattsta/h3) claims to be the primary maintained version since April 26, 2026
- **Upside:** Reported 2.1x speedups on microbenchmarks (e.g., cellToBoundary: 0.50µs → 0.23µs on Apple Silicon)
- **Risk:** Community fork, not official Uber release. Benchmarks are self-reported and unverified.
- **Effort to integrate:** LOW (drop-in replacement for h3-py if perf gains hold in production)
- **Caveat:** No independent verification. Core Uber H3 still at v4.4.1.

#### H3 v4 API Breaking Changes — **MEDIUM relevance**
- **Status:** h3-py v4 renamed most functions (geo_to_h3 → latlng_to_cell, etc.)
- **Impact:** Current Parallax code using v3 API will fail with AttributeError
- **Risk:** Known migration pain point, but straightforward
- **Effort:** MEDIUM (review and update all H3 call sites)
- **Recommendation:** If upgrading H3, schedule a dedicated pass to update all call sites

#### DuckDB Spatial/H3 Integration — **LOW relevance for Phase 1**
- **Status:** H3 support is mature (extension + community R package duckh3 released April 2026)
- **Upside:** Enables SQL queries directly on H3 cells; March 2025 benchmarks showed 28.4ms on H3-indexed queries vs 1380ms without index
- **Caveat:** Parallax already uses H3 community extension. No new performance breakthroughs announced in 2026.
- **Effort:** LOW (already using h3-duckdb)
- **Decision:** Continue current approach. No compelling reason to refactor.

---

### LLM / Agent Orchestration

#### Claude API Structured Outputs + Batch Processing — **HIGH relevance**
- **Status:** Anthropic's documented features now support structured output via `output_config.format` with 50% batch discount
- **Upside:** 
  - Enables guaranteed JSON schema compliance without post-processing
  - Batch API for non-time-sensitive predictions (e.g., daily briefing) costs 50% less
  - Compiled grammar cache (24hr TTL) further reduces token overhead
- **Risk:** Changing `output_config` invalidates prompt cache. Requires careful versioning.
- **Effort:** MEDIUM (refactor agent response parsing to use Anthropic's schema validation)
- **Timeline:** Structured outputs already in platform docs; batch API mature
- **Recommendation:** LOW priority for Phase 1 (current inference costs ~$2-5/day). Consider for Phase 2 if scaling beyond 50 agents.

#### Prompt Caching TTL Uncertainty — **MEDIUM relevance / CAUTION**
- **Issue:** Conflicting reports about cache TTL: official docs say 1-hour for batch, but one DEV post claims default dropped to 5 minutes in early 2026
- **Impact:** If true, cached savings drop from 90% to minimal for short-lived runs
- **Action:** Verify current TTL against official Anthropic pricing docs before relying on caching ROI
- **Effort:** LOW (one API call to confirm)

#### Multi-Agent Orchestration Landscape Consolidation — **HIGH relevance for Phase 2**
- **Status:** Frameworks maturing in 2026:
  - **LangGraph:** Graph-based workflows (nodes=agents, edges=transitions). Default pick for branching/retries.
  - **Microsoft Agent Framework:** GA'd April 2026, consolidates AutoGen + Semantic Kernel. Supports sequential, concurrent, handoff, group chat patterns.
  - **CrewAI:** Role-based agent crews with hierarchical processes.
- **Caveat:** Current Parallax uses custom DES + asyncio (deliberate choice per design doc). Moving to LangGraph would add complexity for unclear benefit.
- **Effort:** HIGH (architectural rewrite)
- **Risk:** Frameworks add overhead (graph traversal, state management). Custom approach optimized for Iran/Hormuz scenario constraints.
- **Recommendation:** Continue custom DES for Phase 1. Revisit for Phase 2 **only** if multi-scenario or complex agent coordination is required. Monitor LangGraph maturity.

---

### Real-Time Data Sources

#### World Monitor — Aggregated Geopolitical Intelligence Platform — **MEDIUM relevance**
- **Status:** Free dashboard + API offering conflict events, ship tracking, satellites, subsea cables, markets, cyber
- **Upside:** Single API reduces ingestion complexity vs piecing together GDELT + AIS + satellite data separately
- **Data freshness:** Not specified in available docs; claims near-real-time but not quantified
- **Risk:** Proprietary aggregator; depends on underlying data sources (likely GDELT + others)
- **Effort:** LOW (swap out multiple data ingestion modules for World Monitor API)
- **Cost:** Free tier available; premium unknown
- **Recommendation:** Evaluate for Phase 2. Phase 1 GDELT + EIA sufficient; adding third-party dependency requires trust assessment.

#### Real-Time AIS / Vessel Tracking APIs — **HIGH relevance**
- **Status:** Multiple commercial providers with different data sources and pricing:
  - **ShipFinder:** Terrestrial + satellite + BeiDou AIS, push channels (no polling)
  - **VesselFinder:** Real-time positions, voyage data, subscription-based
  - **Data Docked:** Flat-rate model, ~830k vessels, free tier available
  - **Datalastic:** Combines terrestrial + satellite, no dashboard
- **Upside:** Real-time Hormuz traffic visibility (currently Parallax uses flow % from cascade rules, not real vessel positions)
- **Risk:** Introduces paid dependency; pricing & coverage vary; API reliability untested in production
- **Effort:** MEDIUM (new ingestion module + WebSocket integration for live pushes)
- **Cost estimate:** ~$10-100/month depending on provider and update frequency
- **Data quality:** Coastal coverage strong; open ocean gaps possible (satellite AIS is sparse)
- **Recommendation:** HIGH priority for Phase 2 validation. Real vessel data would ground Hormuz traffic model. Proof-of-concept: integrate ShipFinder for 2-week trial, compare predicted vs observed traffic patterns against Kalshi market behavior.

#### GDELT Alternatives Assessment — **LOW relevance**
- **Status:** GDELT remains the most accessible free source for geopolitical events
- **Alternatives evaluated:**
  - **ACLED:** Coded conflict events, ~weekly refresh (too lagged for live)
  - **UCDP:** Monthly releases (not real-time)
  - **Global Event Tracker:** Still depends on GDELT + curated RSS (not independent)
  - **PizzINT:** GDELT-derived, adds bilateral threat signals (proprietary)
- **Caveat:** No free alternative offers better real-time coverage than GDELT's 15-minute cycle
- **Recommendation:** Continue GDELT as primary. World Monitor or proprietary feeds as Phase 2 supplements, not replacements.

---

### Evaluation & MLOps

#### Promptfoo (MIT, CLI-based A/B Testing) — **MEDIUM relevance for Phase 2**
- **Status:** CLI/YAML-based prompt testing framework; being acquired by OpenAI in 2026 (roadmap to integrate into Frontier)
- **Upside:** 
  - Unit-test-like workflow for prompts
  - Easy comparison of prompt versions
  - Compatible with current eval pipeline (can wrap existing scoring logic)
- **Risk:** Acquisition uncertainty; OpenAI integration timeline unknown
- **Effort:** LOW-MEDIUM (wrapper around existing `scoring/prediction_log.py`)
- **Recommendation:** Monitor OpenAI integration timeline. If Promptfoo becomes OpenAI-only, evaluate DeepEval as alternative. Current manual versioning sufficient for Phase 1.

#### LLM Evaluation Methodology Maturity — **HIGH relevance**
- **Key insights for Parallax:**
  - **Sample size:** LLM outputs vary ~15% at temperature=0. Standard stat tests underpower for this variability.
  - **Matched-pair evaluation:** Pair identical inputs across prompt versions. Cancels per-example difficulty noise.
  - **A/B test design:** Change one layer at a time (prompt, model, hyperparams, system config, UX).
  - **Baseline:** Run offline evals before routing live traffic. Version each prompt with its eval scores.
- **Current Parallax approach:** Daily cron + manual checkpoint + per-version tracking ✓ (already aligned with best practice)
- **Gap:** No matched-pair statistical test (rolling win-rate sufficient for Phase 1)
- **Recommendation:** Implement matched-pair bootstrap CI in `/scoring/calibration.py` for Phase 2. Current 7-day rolling window adequate for detecting agent degradation.

#### Prompt Versioning at Scale — **MEDIUM relevance**
- **Status:** Best practice is semver + eval scores logged per version
- **Parallax status:** Already implements `prompt_version` in predictions and agent_prompts table ✓
- **Gap:** No automated rollback if new version underperforms. Currently manual.
- **Effort:** LOW (add decision rule: if 7-day accuracy < baseline - 3%, alert admin)
- **Recommendation:** Add metric to eval cron: "if accuracy dropped > 3% over 7 days, send alert with rollback one-liner". No auto-rollback yet (requires human sign-off).

---

### Frontend / Performance

#### deck.gl v9.4 (Released Sept 2026) — **LOW-MEDIUM relevance**
- **Changes:** Picking performance optimization
- **Upside:** Hex map click responsiveness improvement (medium-impact for Phase 1)
- **Effort:** LOW (upgrade dependency, no code changes)
- **Risk:** Low (v9.4 is stable)
- **Caveat:** No performance numbers published. Original design doc already optimizes rendering (mutable useRef, 100ms batching).
- **Recommendation:** Non-urgent. Upgrade if clicking responsiveness becomes a demo issue.

#### Data Format > Layer Choice for Geospatial Perf — **MEDIUM relevance**
- **Key finding:** Binary buffers + tiling matter far more than layer implementation
- **Current Parallax:** Hex cells stored as JSON in DuckDB, serialized to frontend
- **Opportunity:** Export H3 cell positions as typed arrays (Float32Array) directly, eliminating per-feature JS iteration
- **Effort:** MEDIUM (new data export path in `/dashboard/data.py`)
- **Gain:** Likely 2-3x faster hex rendering for 400K hex map
- **Recommendation:** Defer to Phase 2 unless rendering performance becomes bottleneck in demos.

#### WebGPU Backend Claims (Unverified) — **LOW relevance / HIGH uncertainty**
- **Claim:** deck.gl WebGPU backend 2-3x faster than WebGL
- **Status:** Cannot verify against official sources. One academic comparison favors deck.gl+MapLibre for point clouds.
- **Risk:** Ecosystem immaturity; WebGPU still stabilizing
- **Recommendation:** Wait for WebGPU standardization (likely 2027-2028). WebGL path sufficient.

---

## Top 3 Recommendations

### 1. **Integrate Real-Time AIS / Vessel Tracking (Phase 2, HIGH impact)**
- **What:** Plug in ShipFinder or Data Docked AIS API for live Hormuz traffic
- **Why:** Ground truth for Hormuz traffic model validation. Enables A/B test: agent predictions vs real-world vessel positions vs Kalshi market behavior
- **Effort:** 1-2 weeks (new ingestion module, cascade rule calibration)
- **Cost:** ~$30-50/month + API key setup
- **Win:** Converts cascade simulation to semi-empirical model; dramatically improves credibility for market pricing comparison

### 2. **Upgrade H3 to SIMD-Optimized Fork + API v4 (Phase 1, if needed)**
- **What:** Evaluate mattsta/h3 fork (with perf benchmarks in your stack), and migrate to h3-py v4 API
- **Why:** Potential 2x speedup for H3 operations (map rendering, cell queries). Aligns with current best practice.
- **Effort:** 1-2 days (fork evaluation + API migration)
- **Risk:** Fork maturity unproven; own load testing required
- **Win:** Faster hex map interactivity, lower WebSocket latency
- **Gate:** Only if map responsiveness is a demo issue today. Otherwise, defer.

### 3. **Implement Automated Prompt Rollback Alert (Phase 2, MEDIUM impact)**
- **What:** Add decision rule to daily eval cron: if 7-day accuracy drops >3% from baseline, send admin alert with recommended rollback
- **Why:** Prevents cascade of poor predictions from a bad prompt version. Minimal effort, high safety.
- **Effort:** 4 hours (logic in `/scoring/calibration.py`)
- **Cost:** None
- **Win:** Catches agent degradation before it compounds; enables faster iteration on prompts

---

## Sources

### Spatial/Geo
- [mattsta/h3 GitHub](https://github.com/mattsta/h3)
- [duckh3 R Package Documentation](https://cran.rstudio.com/web/packages/duckh3/duckh3.pdf)
- [H3 in DuckDB: Spatial Indexing Guide](https://aetperf.github.io/2025/03/04/Spatial_queries_in_DuckDB_with_R-tree_and_H3_indexing.html)

### LLM/Agent
- [Claude API Structured Outputs](https://platform.claude.com/docs/en/build-with-claude/structured-outputs)
- [Claude API Batch Processing](https://platform.claude.com/docs/en/build-with-claude/batch-processing)
- [Claude Prompt Caching — TTL / Pricing](https://platform.claude.com/docs/en/about-claude/pricing)
- [Multi-Agent Orchestration Frameworks 2026](https://www.truefoundry.com/blog/multi-agent-orchestration-frameworks)
- [Microsoft Agent Framework GA April 2026](https://www.langchain.com/resources/ai-agent-frameworks)
- [LangGraph Documentation](https://docs.langchain.com/langgraph)

### Real-Time Data
- [World Monitor — Geopolitical Intelligence Dashboard](https://www.worldmonitor.app/)
- [ShipFinder AIS API](https://open.shipfinder.com/)
- [VesselFinder API Documentation](https://api.vesselfinder.com/docs/)
- [Data Docked — Maritime Data API](https://datadocked.com/vessel-location-api)
- [GDELT Project](https://gdeltproject.org/)
- [ACLED — Armed Conflict Location & Event Data](https://acleddata.com/)

### Eval/MLOps
- [Promptfoo — LLM Prompt Testing](https://www.promptfoo.dev/)
- [DeepEval — LLM Evaluation Framework](https://www.confident-ai.com/docs/introduction)
- [A/B Testing LLM Prompts: Statistical Best Practices](https://futureagi.com/blog/ab-testing-llm-prompts-best-practices-2026/)
- [LLM Evaluation Frameworks Comparison 2026](https://deepeval.com/blog/top-5-llm-evaluation-frameworks)

### Frontend/Performance
- [deck.gl Release Notes / What's New](https://deck.gl/docs/whats-new)
- [deck.gl v9.4 Picking Performance Tracker](https://github.com/visgl/deck.gl/issues/10270)
- [Geospatial Stack 2026 Deep Dive](https://ttlab.hopto.org/blog/culture/2026-05-16-geospatial-stack-2026-postgis-maplibre-mapbox-deckgl-kepler-protomaps-overture-maps-h3-s2-deep-dive)

---

## Assessment Summary

| Finding | Relevance | Effort | Risk | Recommendation |
|---------|-----------|--------|------|-----------------|
| AIS/vessel tracking API | HIGH | MEDIUM | LOW | Phase 2 proof-of-concept |
| Claude structured outputs + batching | HIGH | MEDIUM | MEDIUM | Phase 2 cost optimization |
| H3 SIMD fork + v4 API | MEDIUM | MEDIUM | MEDIUM | If demo perf issue arises |
| Multi-agent orchestration frameworks | HIGH | HIGH | MEDIUM | Monitor; Phase 2+ only |
| Automated prompt rollback alert | MEDIUM | LOW | LOW | Phase 2 quick win |
| deck.gl v9.4 upgrade | LOW | LOW | LOW | Non-urgent; defer unless needed |
| World Monitor aggregator | MEDIUM | LOW | LOW | Phase 2 evaluation |

---

**Next actions:**
1. Schedule 1hr proof-of-concept: compare ShipFinder real vessels vs Parallax predicted Hormuz traffic
2. Verify current Claude API cache TTL vs official docs
3. Monitor OpenAI + Promptfoo integration timeline
4. If H3 map interaction feels slow in live demo, benchmark mattsta/h3 fork

---

*Report generated 2026-11-11 by daily tech scout*
