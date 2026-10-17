# Parallax Technology Research Report
**Date:** 2026-10-17  
**Focus Areas:** Spatial/Geo, LLM/Agent, Real-time Data, Eval/MLOps, Performance

---

## Executive Summary

Research across five technology categories yields **two high-priority findings** and several additive improvements. The current tech stack (DuckDB + H3, deck.gl, Claude API with prompt caching, GDELT) remains solid for Phase 1. No critical gaps or replacement tech identified. Key opportunities:

1. **World Monitor** — open-source geopolitical event dashboard with API/MCP, worth evaluating as GDELT supplement
2. **Calibration in LLM forecasting** — a 2026 research area directly applicable to Parallax's eval framework
3. **Beta-Bernoulli calibration** — new technique for aligning LLM confidence with ground truth accuracy

---

## 1. Spatial/Geo Findings

### H3 Extension Status
- **Relevance:** MEDIUM (foundational, but stable)
- **Effort:** LOW (no action needed)
- **Risk/Maturity:** STABLE — H3 community extension has been in place for 2+ years, widely tested
- **Findings:**
  - DuckDB H3 extension remains stable; no 2026 version bumps or breaking changes found
  - CRAN package `duckh3` (April 2026) provides R bindings but doesn't signal new backend features
  - Current pinned version strategy is appropriate

### deck.gl v9.4 & v10 Roadmap
- **Relevance:** MEDIUM (rendering optimization)
- **Effort:** LOW (library upgrade, v9.4 is backward compatible)
- **Risk/Maturity:** STABLE for v9.4, EARLY for v10 features
- **Findings:**
  - **v9.4 (Sept 2026):** Final v9 release focuses on instanced picking (GPU optimization). Removes redundant picking colors, moves to row-index-based picking. Improves large-scale layer performance.
  - **v10 (roadmap):** WebGPU, Arrow integration, GPU compute, draw culling. Most work is still in planning.
  - **H3HexagonLayer optimization:** `highPrecision: false` forces instanced rendering mode (faster but lower precision). Current default is 'auto'. Explicit setting can trade precision for speed when rendering 400K+ hexes.
  - **Recommendation:** Test v9.4 upgrade path in next dev cycle to capture instanced picking gains. V10 is premature.

---

## 2. LLM/Agent Findings

### Claude API: Batch + Caching Still Dominant
- **Relevance:** HIGH (cost control is critical)
- **Effort:** LOW (already in design, incremental optimization)
- **Risk/Maturity:** STABLE — features are production-grade
- **Findings:**
  - **No new 2026 features announced.** Batch API and prompt caching remain the primary cost levers.
  - **TTL dispute:** Some sources claim Anthropic lowered default cache TTL from 60min to 5min in early 2026. **Verify against official Anthropic docs** — this is unconfirmed.
  - **Practical stack for Parallax:**
    - Use **1-hour cache TTL** for batch jobs (system prompt can be 1-3K tokens and is reused across agents)
    - Prime the cache with one full request before sending the batch (ensures cache is warm)
    - Combine with Message Batches API (50% cost reduction on top of caching)
    - Estimated result: 60% off full price for agent swarm calls with static system prompts
  - **Current budget ($2-5/day) remains achievable.** No cost optimization breakthrough needed for Phase 1.

### Prompt Caching Mechanics
- **Minimum cacheable prefix:** ~1,024 tokens (unconfirmed, check docs)
- **Cache cost model:** Write at ~1.25x normal input, reads at 0.1x (5-min cache). 1-hour cache write ~2x but reads still 0.1x.
- **Parallax application:** Agent system prompts (historical baseline + country doctrine) are 2-3K tokens and are static per prompt version. These are ideal for caching.

---

## 3. Real-Time Data Findings

### GDELT Alternatives & Supplements

#### World Monitor (Open Source + API)
- **Relevance:** HIGH (direct GDELT supplement)
- **Effort:** MEDIUM (new ingestion pipeline)
- **Risk/Maturity:** ALPHA — maintained but small community
- **What it is:**
  - Free, open-source (AGPL-3.0) dashboard aggregating 460+ news and OSINT feeds
  - Live map with 762 attributed providers
  - Provides API and MCP server for programmatic access
  - Streams raw news articles, NOT structured CAMEO event codes
- **Comparison to GDELT:**
  - Advantage: Free, live, open-source, MCP support (integrates directly into Parallax)
  - Disadvantage: Not event-coded (no CAMEO equivalents), less historical depth
- **Recommendation:** Trial as a **supplemental feed** alongside GDELT to catch real-time signals GDELT misses. Use for anomaly detection / early warning. Would require adapter to convert news articles → structured events via LLM (adds cost but could improve signal quality).

#### Alternative Datasets
- **UCDP** (Uppsala Conflict Data Program): Free API with request token. Research-grade conflict records, better validated than GDELT on armed conflict. Lagged (not real-time).
- **ACLED** (Armed Conflict Location & Event Data): Already in Phase 1 spec. Weekly batch, good for validation layer.
- **WORLDREP** (2024 academic dataset): Shows better alignment with expert labels on cooperation/conflict than GDELT, but not a live feed. Useful for historical baseline calibration.
- **None of these replace GDELT's real-time, free, volume.** Best approach: keep GDELT as primary, add ACLED for validation, trial World Monitor for early signals.

### AIS Vessel Tracking
- **Relevance:** MEDIUM-LOW (optional for shipping route detail)
- **Effort:** MEDIUM (new data source + map layer)
- **Risk/Maturity:** Depends on source
- **Findings:**
  - **Open source:** ais-vessel-tracker (GitHub) — free implementation using aisstream.io as feed source. Provides 90-day history, anomaly flags, sanctions screening. Maintenance status unclear; treat as MVP.
  - **Free proprietary:** VesselFinder (free tier), MyShipTracking. Cover coastal AIS; open ocean gaps without satellite tier.
  - **Coverage gap:** All free tools suffer from terrestrial-AIS-only coverage (no ships beyond coastal reception). Meaningful for Hormuz corridor detail, limited for open ocean rerouting.
- **Recommendation:** Out of scope for Phase 1. If Phase 2 adds real-time shipping lane modeling, revisit VesselFinder API or self-host ais-vessel-tracker.

---

## 4. Eval/MLOps Findings

### Calibration as a First-Class Metric
- **Relevance:** HIGH (core to prediction eval)
- **Effort:** MEDIUM (new scoring function, validation harness)
- **Risk/Maturity:** RESEARCH-GRADE (2026 papers emerging)
- **Findings:**
  - **Research gap:** Calibration is widely recognized as critical for trustworthy LLM evaluation, but rarely checked in practice. Parallax's eval framework already tracks calibration (design spec, § 7), but this research confirms it's the right priority.
  - **New techniques (2026):**
    - **Beta-Bernoulli calibrator** (arXiv:2605.27668): Maps LLM output probabilities to human uncertainty. Applicable to binary prediction tasks (e.g., "yes blockade" vs "no blockade").
    - **WorldReasoner** (arXiv:2606.11816): Evaluates whether agent reasoning chains are logically sound, not just prediction accuracy. Useful for identifying reasoning errors vs. data-driven misses.
  - **Practical implementation:** Check LLM predictions against 100-200 human-labeled ground truth examples. Compute Cohen's kappa (strong) or Krippendorff's alpha. Iterate rubric until kappa > 0.6.
  - **Parallax application:** Agent confidence scores (0.0-1.0) should be recalibrated against actual hit rates. Introduce a **recalibration layer** post-prediction that maps agent confidence → ground truth frequency using Beta-Bernoulli fitting.

### Calibration Drift Detection
- **Relevance:** HIGH (Phase 1 eval pipeline)
- **Effort:** LOW (add to daily cron)
- **Findings:**
  - Models evaluated under accuracy-only rubrics tend to overconfident guessing. Closed-form evaluations with no abstention option amplify this.
  - **Defense:** Periodically sample 50 recent predictions, compute calibration score (e.g., Brier score, calibration curve slope), flag if drift > threshold. This becomes part of the daily eval cron.

---

## 5. Performance Findings

### React Dashboard: High-Frequency Data
- **Relevance:** HIGH (critical for frontend stability)
- **Effort:** LOW-MEDIUM (refactoring patterns, no new libs)
- **Risk/Maturity:** STABLE (proven patterns from 2025+)
- **Findings:**
  - **The problem:** WebSocket updates at 5-10 Hz (high activity periods) can thrash React state, freezing the deck.gl canvas.
  - **The solution (already in spec):** Decouple React state from deck.gl data arrays. Use `useRef` for hex data, mutate it directly on WebSocket updates, let deck.gl pull data on its own render cycle. Batch updates in 100ms windows. This is already in the design (§ 5, "Render Performance").
  - **Practical confirmation:** Trading dashboard guide (2026) recommends throttling non-critical updates to 250-500ms. Memoize row components in virtualized lists. Use Canvas over SVG for dense data.
  - **Recommendation:** Current design is sound. Implement as specified, then profile with React DevTools Profiler if lag appears. No new tech needed.

### Large Dataset Rendering: Canvas vs SVG
- **Relevance:** MEDIUM (optimization opportunity)
- **Effort:** LOW (library configuration)
- **Risk/Maturity:** STABLE
- **Findings:**
  - Canvas rendering handles frequent updates and dense data better than SVG (DOM node overhead).
  - deck.gl uses GPU-accelerated WebGL (better than both for massive datasets).
  - For agent activity feed and prediction cards, SVG is fine (< 100 items). For hex map (400K cells), GPU acceleration (deck.gl) is required.
  - **Parallax:** Already uses deck.gl for hex layers. SVG only for timeline and small charts. No change needed.

### Embedding Model Performance
- **Relevance:** LOW (GDELT filtering only)
- **Effort:** LOW (model swap)
- **Risk/Maturity:** STABLE
- **Findings:**
  - **Current choice:** all-MiniLM-L6-v2 (sentence-transformers). Fast, low latency, good for semantic dedup.
  - **Alternatives:**
    - **All-mpnet-base-v2:** Better semantic quality, 2-3x slower. Overkill for GDELT event dedup (cosine sim > 0.85).
    - **EmbeddingGemma-300M:** Multilingual, runs on-device, rivals larger models on MTEB. Good if non-English news matters.
    - **Snowflake arctic-embed-l-v2.0, BGE-small:** Compact, high quality. Worth benchmarking if inference latency becomes a bottleneck.
  - **Current choice is solid.** all-MiniLM is the right speed/quality tradeoff for real-time GDELT dedup. No change recommended for Phase 1.

---

## Recommendations (Priority Order)

### 1. Integrate World Monitor as Supplemental Feed (HIGH)
- **Why:** Early signal detection on geopolitical events; open-source, API/MCP available
- **Effort:** 1-2 sprints (new ingestion module, event adapter, optional LLM event coding)
- **Expected value:** Catch real-time news 5-15 min before GDELT; reduce false negatives in scenario-critical entities
- **Risk:** GDELT integration already stable; World Monitor is experimental. Trial first with manual alert review.

### 2. Add Calibration Drift Checks to Daily Eval Cron (MEDIUM)
- **Why:** Prevents overconfident agent forecasts; 2026 research validates this as critical missing metric
- **Effort:** 1 sprint (add Beta-Bernoulli recalibration + drift detection to scoring module)
- **Expected value:** Flag prompt degradation earlier; improve forecast reliability over rolling 30-day window
- **Risk:** Requires ground truth data; if eval data is sparse, stat significance is weak. Implement with confidence intervals.

### 3. Test deck.gl v9.4 Upgrade Path (LOW-MEDIUM)
- **Why:** Instanced picking optimization should improve hex layer responsiveness at full resolution
- **Effort:** 1-2 days (test upgraded package in dev environment, profile)
- **Expected value:** Smoother interaction performance; may enable higher resolution detail layers without slowdown
- **Risk:** v9.4 is stable; backward compatible. Low risk upgrade.

---

## Minor Findings (Consider for Phase 2)

- **AIS vessel tracking:** Defer to Phase 2 if shipping route detail becomes a priority. Use VesselFinder API or self-host ais-vessel-tracker.
- **UCDP / ACLED for validation:** Integrate as confidence boosters for agent decision scoring, not real-time primary feed.
- **Embedding model refresh:** Benchmarking EmbeddingGemma-300M worth doing if GDELT filtering becomes a bottleneck (unlikely given current event volume).

---

## Notes & Caveats

- Most "2026 findings" are from vendor guides, blogs, and unverified sources. Treat as starting points, not authoritative.
- Claude API caching TTL dispute needs verification against official Anthropic pricing page.
- Embedding model benchmarks lack reliable head-to-head comparisons; MTEB provides a starting filter but always benchmark on your own data.
- AIS and World Monitor data quality vary by region; trial with manual spot checks before production automation.

---

## Sources

### Spatial/Geo
- [deck.gl What's New](https://deck.gl/docs/whats-new)
- [deck.gl v9.4 Release Tracker](https://github.com/visgl/deck.gl/issues/10270)
- [deck.gl v10 Roadmap](https://github.com/visgl/deck.gl/issues/10712)
- [DuckDB H3 Community Extension](https://duckdb.org/community_extensions/extensions/h3)
- [H3 DuckDB Bindings GitHub](https://github.com/isaacbrodsky/h3-duckdb)

### LLM/Agent
- [Claude API Batch Processing Docs](https://platform.claude.com/docs/en/build-with-claude/batch-processing)
- [Claude Prompt Caching in 2026: TTL Changes](https://dev.to/whoffagents/claude-prompt-caching-in-2026-the-5-minute-ttl-change-thats-costing-you-money-4363)
- [Claude API Cost Optimization Guide](https://dev.to/whoffagents/claude-api-cost-optimization-caching-batching-and-60-token-reduction-in-production-3n49)
- [Anthropic Claude Certified Developer: Batch & Caching](https://www.certsafari.com/anthropic/claude-developer-foundations/learn/claude-api-cost-and-scale-prompt-caching-batch-processing-and-cloud-platforms)

### Real-time Data
- [Free Geopolitical Data APIs 2026](https://www.worldmonitor.app/blog/posts/free-geopolitical-data-apis-2026/)
- [World Monitor Dashboard](https://www.worldmonitor.app/)
- [GDELT Alternatives Comparison](https://www.worldmonitor.app/compare/best-geopolitical-risk-dashboards/)
- [GDELT Alternative - Currents API](https://currentsapi.services/en/alternative/gdelt)
- [AIS Vessel Tracker GitHub](https://github.com/Snaporaz6/ais-vessel-tracker)
- [Free AIS Tracking Alternatives](https://www.marineradar.com/hub/which-is-the-free-alternative-to-marinetraffic)
- [MarineTraffic Alternatives 2026](https://primonautic.com/blog/marinetraffic-alternatives-top-ship-tracking-apps)

### Eval/MLOps
- [Calibration as a First-Class Criterion in LLM Evaluation](https://arxiv.org/pdf/2609.26489)
- [LLM-based Agents for Forecasting and Prediction](https://arxiv.org/pdf/2608.23058)
- [Build LLM Evaluation Framework 2026](https://futureagi.com/blog/build-llm-evaluation-framework-2025/)
- [Best Human-in-Loop LLM Evaluation Platforms 2026](https://www.braintrust.dev/articles/best-human-in-the-loop-llm-evaluation-platforms-2026/)
- [MLFlow: LLM Evaluation Frameworks](https://mlflow.org/articles/llm-evaluation-frameworks-explained-for-ai-practitioners/)

### Performance
- [React Performance Optimization: Large Datasets](https://blog.logrocket.com/best-react-chart-libraries-2026/)
- [Handling Large Datasets in React](https://medium.com/@david.pradeep/handling-large-datasets-in-react-lessons-from-a-production-failure-ee5f49b11aa3)
- [React Data Grid for Large Datasets](https://www.infragistics.com/blogs/best-react-data-grid-for-large-datasets-performance-guide/)
- [Trading Dashboard with Real-Time Charting 2026](https://openwebsolutions.in/blog/high-performance-trading-dashboard-react-websockets/)
- [Best Open-Source Embedding Models 2026](https://www.bentoml.com/blog/a-guide-to-open-source-embedding-models)
- [Best Embedding Models 2026 Comparison](https://futureagi.com/blog/best-embedding-models-2025/)
- [Sentence-Transformers Alternatives](https://markaicode.com/alternatives/sentence-transformers-alternatives/)

---

**Report Generated:** 2026-10-17  
**Next Review:** 2026-10-24
