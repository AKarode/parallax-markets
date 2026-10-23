# Technology Research Report — Parallax Stack Assessment
**Date:** October 21, 2026  
**Focus Areas:** Spatial/Geo, LLM/Agent, Real-time Data, Eval/MLOps, Performance

---

## Executive Summary

Searched for improvements and alternatives across the Parallax stack. Key findings:
- **Spatial/Geo:** H3 4.5.0 released May 2026 (contents unknown); deck.gl has auto-precision option; DuckDB H3 extension available but lacks published performance guidance.
- **LLM/Agent:** Model naming ambiguous across sources (conflicts between Sonnet 4.6 vs Sonnet 5, Opus 4.8 vs Opus 5). Batch API offers 50% discount but may not combine with prompt caching (sources disagree). Prompt caching TTL 5 min default.
- **Real-time Data:** GDELT Cloud (new structured events API, hourly updates, coverage from Mar 2026+) is a solid upgrade path. ACLED and UCDP are free alternatives. Commercial AIS via Kpler/MarineTraffic/LSEG adds shipping transparency but incurs cost.
- **Eval/MLOps:** Autorubric (rubric-based evaluation), LLM-as-judge calibration (Cohen's kappa > 0.6), Braintrust/LangSmith/Langfuse for prompt versioning. Gradual rollout (5%→25%→50%→100%) is standard practice.
- **Performance:** DuckDB out-of-core via `temp_directory`, thread scaling (2–5× cores for remote I/O), React batching for high-frequency updates, ECharts for 100K+ data points.

No critical gaps found. Stack is solid. Additive improvements available in eval tooling and real-time data sources.

---

## Detailed Findings

### 1. Spatial/Geo

#### H3 Library Updates
- **Status:** H3 4.5.0 released May 2026 (C library). R wrapper h3lib updated Mar 2026 (v0.1.4). JavaScript h3-js last updated Dec 2025.
- **Relevance:** LOW — Current pinned version works. New releases are incremental maintenance.
- **Effort:** LOW — Drop-in dependency update if changelog shows bug fixes relevant to Parallax.
- **Risk:** LOW — H3 is stable API.
- **Action:** Monitor releases, but no urgent upgrade needed.

#### Deck.gl H3HexagonLayer Precision
- **Status:** Layer includes `highPrecision` option with auto mode. Automatically adjusts precision based on zoom level.
- **Relevance:** MEDIUM — Dashboard already uses H3HexagonLayer; auto-precision may reduce jank on zoom.
- **Effort:** LOW — Verify option is enabled, test zoom interactions.
- **Risk:** LOW — Option is built-in, no external dependency.
- **Action:** Verify current usage. Enable if not already set.

#### DuckDB H3 Extension Performance
- **Status:** Community extension available, R wrapper `duckh3` published Apr 2026. No published tuning guidance.
- **Relevance:** MEDIUM — Currently in use for cell queries. Lack of tuning docs is a minor risk.
- **Effort:** MEDIUM — Requires custom benchmarking (DuckDB EXPLAIN ANALYZE on cell operations).
- **Risk:** LOW — Read-only operations; no correctness risk.
- **Action:** Baseline current query performance on `world_state_delta` and `world_state_snapshot` via EXPLAIN ANALYZE. If latency is acceptable, defer.

---

### 2. LLM/Agent

#### Model Lineup Ambiguity
- **Status:** Sources conflict on current models. Reported variants:
  - Haiku 4.5, Sonnet 4.6, Opus 4.8, Fable 5 (May 2026 sources)
  - Haiku 4.5, Sonnet 5, Opus 5, Fable 5, Mythos 5 (Aug 2026 sources)
- **Relevance:** HIGH — Direct impact on inference cost and quality.
- **Effort:** LOW — Check Anthropic's official API docs (anthropic.com).
- **Risk:** MEDIUM — Using outdated model names may silently fall back to older versions.
- **Action:** **DO THIS IMMEDIATELY:** Verify current model IDs against Anthropic docs and update `cli/brief.py` model references if needed. Log model version used in every prediction.

#### Batch API Discount + Caching Incompatibility
- **Status:** Sources claim Batch API gives 50% discount. Some claim Batch **does not** support prompt caching; others claim it does.
- **Relevance:** HIGH — Up to 95% savings if both combine; zero benefit if mutually exclusive.
- **Effort:** LOW — Single test call to Anthropic's API to verify.
- **Risk:** MEDIUM — Wrong assumption could lock in expensive inference.
- **Action:** **DO THIS IMMEDIATELY:** Test a batch request with a cached system prompt. If incompatible, document it. If compatible, switch to Batch API for daily scorecards (naturally async, 24-hour deadline tolerance).

#### Prompt Caching TTL
- **Status:** Default 5-minute TTL widely reported. Some sources cite enterprise tier with 24-hour TTL, but uncorroborated.
- **Relevance:** MEDIUM — Current design assumes caching within agent cooldown windows (30 min to 1 hr). 5-min TTL is tight but may work.
- **Effort:** LOW — Monitor cache hit logs. Add metrics on cache miss rate.
- **Risk:** LOW — Fallback is full price on cache miss, no correctness impact.
- **Action:** Add cache hit/miss instrumentation. If miss rate > 20%, investigate longer TTL tier with Anthropic support.

---

### 3. Real-time Data

#### GDELT Cloud (Structured Events)
- **Status:** New hosted service (Anthropic, Mar 2026+). Converts raw GDELT articles into structured Events, Stories, Entities. Hourly updates. REST API with hourly granularity.
- **Relevance:** HIGH — Current design uses raw GDELT with local noise filter. GDELT Cloud pre-filters and structures; could simplify pipeline.
- **Effort:** MEDIUM — New ingestion adapter required. Schema differs from current GDELT. Must map Event codes to Parallax action types.
- **Risk:** MEDIUM — Coverage is strong from Mar 2026 onward; historical depth (pre-Mar 2026) is limited. Bootstrap simulation may need current raw GDELT as fallback.
- **Action:** Request trial access. Design fallback to raw GDELT for pre-Mar 2026 bootstrap. Consider parallel ingestion during validation window (Oct–Nov 2026) to compare quality before cutover.

#### ACLED (Conflict Event API)
- **Status:** Free API with authentication (free account). Covers political violence, protests, riots, conflict events. Lagged (not real-time). Requires attribution per license.
- **Relevance:** MEDIUM — Complements GDELT for validated conflict signals. Useful for ground truth / eval comparison.
- **Effort:** LOW — Wrapper adapter, similar complexity to existing GDELT.
- **Risk:** LOW — Lagged data, so not for real-time decisions. Attribution requirement is contractual, not technical.
- **Action:** Integrate as secondary eval-only data source (post-event calibration). Document attribution in eval output.

#### UCDP (Uppsala Conflict Data Program)
- **Status:** Research-grade conflict dataset. Free API with token. Historical, validated. Not real-time.
- **Relevance:** LOW — Suitable for baseline calibration, not live monitoring.
- **Effort:** LOW — Lightweight integration for historical context.
- **Risk:** LOW — Pre-historical analysis only.
- **Action:** Use for initial agent historical baseline (Section 3: Agent Memory in design spec). Pre-load into `curated_events` for context-setting.

#### Maritime AIS (Kpler, MarineTraffic, LSEG)
- **Status:** Commercial real-time AIS data. Kpler/MarineTraffic claim 13,000+ coastal receivers + satellite constellation. LSEG's Vessel Tracking adds anomaly detection. Pricing not disclosed in search results.
- **Relevance:** MEDIUM — Direct observable for Hormuz traffic (key prediction metric). Current design relies on model estimates.
- **Effort:** MEDIUM — API integration + schema mapping. Requires account and API key.
- **Risk:** MEDIUM — Cost unknown. Subscription may be significant. No free tier found.
- **Action:** Request pricing from Kpler for trial. If <$200/month, pilot integration for Oct–Nov eval window. Otherwise defer to Phase 2 if Hormuz traffic accuracy is limiting.

---

### 4. Eval/MLOps

#### Autorubric Framework
- **Status:** Feb 2026 arXiv (2603.00077). Unified rubric-based LLM evaluation framework.
- **Relevance:** MEDIUM — Parallax's eval framework is manual (humans tag misses as `model_error` vs `exogenous_shock`). Autorubric could automate some of that.
- **Effort:** MEDIUM — Research paper; likely needs adaptation for prediction calibration (not general text eval).
- **Risk:** MEDIUM — Research-stage (arXiv). Implementation may be incomplete or require heavy customization.
- **Action:** Read paper. Assess feasibility for tagging decision chains (agent → prediction → outcome). If promising, spike a POC in Q1 2027.

#### LLM-as-Judge Calibration (Cohen's Kappa)
- **Status:** arXiv 2511.21140. Plug-in method to correct bias and compute confidence intervals. Targets Cohen's kappa > 0.6 against human labels (>0.8 considered strong).
- **Relevance:** MEDIUM — Parallax uses manual expert review for eval ground truth. LLM judge could accelerate closure on ambiguous misses (tagged `ambiguous`).
- **Effort:** MEDIUM — Requires human-labeled calibration set (~50–100 samples). Implements statistical correction.
- **Risk:** LOW — Method is research-validated. Implementation straightforward.
- **Action:** Collect 50 labeled eval samples (agent decision + outcome + human verdict). Build LLM judge with Sonnet. Measure kappa. If kappa > 0.6, use for ambiguous cases; otherwise escalate to human.

#### Prompt Versioning + A/B Testing Tools
- **Status:** Braintrust, LangSmith, Langfuse, PromptLayer, Vellum all offer versioning and A/B testing. Gradual rollout (5%→25%→50%→100%) with automatic rollback on quality drop is standard.
- **Relevance:** MEDIUM — Current design has manual prompt versioning in code (semver in agent_prompts table). External tool could streamline iteration.
- **Effort:** HIGH — Requires significant refactor to integrate external service. Current single-process architecture does not have external dependency injection.
- **Risk:** MEDIUM — Adds operational dependency. Trade-off: faster iteration vs. added complexity.
- **Action:** Current manual approach is acceptable for Phase 1. If prompt iteration becomes a bottleneck (>2 updates/day), evaluate Braintrust or LangSmith for Phase 2.

---

### 5. Performance

#### DuckDB Out-of-Core + Temp Directory
- **Status:** DuckDB supports data larger than RAM by spilling to disk. Configurable via `temp_directory`. Official tuning guide recommends profiling with EXPLAIN ANALYZE.
- **Relevance:** MEDIUM — Current design uses delta + snapshot to control growth (~38.4M rows/day without mitigation). Out-of-core is a safety valve if delta grows unexpectedly.
- **Effort:** LOW — Set `temp_directory` to a fast SSD (not mounted network volume). Benchmark EXPLAIN ANALYZE on largest query (likely `world_state_snapshot` reconstruction).
- **Risk:** LOW — Disk spill is slower than RAM, but correctness is guaranteed.
- **Action:** Set `temp_directory` to backend's ephemeral `/mnt/fast` or persistent `duckdb-data`. Monitor spill usage via DuckDB metrics. If spill > 10% of queries, optimize query or increase memory_limit.

#### Thread Scaling for Remote I/O
- **Status:** Official docs recommend threads = 2–5× CPU cores for workloads with many small network requests (e.g., remote Parquet reads). Default is core count.
- **Relevance:** MEDIUM — If Parallax scales to read from cloud Parquet (e.g., GDELT BigQuery exports), thread scaling helps.
- **Effort:** LOW — Config change in DuckDB connection setup.
- **Risk:** LOW — Excess threads slightly increase CPU overhead; beyond 5× cores, diminishing returns.
- **Action:** Current deployment reads local DuckDB file, so low priority. If Phase 2 reads remote data, bump threads to 3–4× cores and benchmark.

#### React Batching for High-Frequency Updates
- **Status:** Batch updates per animation frame (~60 Hz). React 18+ batches within event handlers. React 19 adds startTransition for background updates to avoid rendering jank.
- **Relevance:** HIGH — Current design mentions buffering WebSocket updates for 100ms before flushing to avoid render thrashing (Section 5: Render Performance). Batching aligns with this.
- **Effort:** LOW — Verify startTransition is used for cell data updates. Measure frame rate under high activity (>20 events/sec).
- **Risk:** LOW — React batching is built-in; no external dependency.
- **Action:** Verify current code uses startTransition for mutable ref updates in WebSocket handler. Benchmark frame rate at 100 events/sec. If jank occurs, reduce buffering window or switch to Canvas-based rendering (Phase 2).

#### Chart Library for High-Volume Data
- **Status:** Recharts suitable for <5K points (SVG-based). Apache ECharts for React recommended for 100K+ points (Canvas/WebGL). Live updates and 50+ chart types.
- **Relevance:** MEDIUM — Dashboard has time-series (Brent price sparkline, Hormuz traffic, escalation index). Current implementation unknown. If sparkline is SVG with unbounded growth, risk of jank.
- **Effort:** LOW-MEDIUM — If using Recharts, verify data window is capped (e.g., last 7 days). If ECharts needed, migration is straightforward.
- **Risk:** LOW — Preemptive optimization. Only required if benchmarks show jank.
- **Action:** Measure dashboard frame rate under live updates. If stable, no change. If jank occurs, cap Recharts dataset to rolling 7-day window or switch to ECharts.

---

## Top 3 Recommendations

### 1. **Verify Claude API Model Names & Test Batch Caching Compatibility** (HIGH URGENCY)
**Rationale:** Cost and quality depend on using the latest models. Batch API + caching ambiguity could represent 50–95% cost savings if compatible, or significant waste if incorrect. Test immediately.  
**Action Items:**
- Check Anthropic docs for current Haiku/Sonnet/Opus model IDs.
- Send a test batch request with a cached system prompt to verify compatibility.
- Update `cli/brief.py` and `prediction/*.py` to log model version on every inference.
- Document findings in code comments.
**Effort:** 2–4 hours  
**Impact:** Unblocks cost optimization and ensures correct model usage.

---

### 2. **Integrate GDELT Cloud as Primary Data Source (Validate in Oct–Nov)**
**Rationale:** GDELT Cloud pre-filters and structures events (reducing noise-filter complexity), updates hourly (faster than raw GDELT), and is newer infrastructure. Current raw GDELT pipeline is proven; GDELT Cloud is an upgrade but risks coverage gaps pre-Mar 2026.  
**Action Items:**
- Request trial access to GDELT Cloud API.
- Design parallel ingestion: consume both raw GDELT and GDELT Cloud during Oct–Nov eval window.
- Compare event quality, coverage, and ingestion latency side-by-side.
- Build schema adapter to map GDELT Cloud Events to Parallax action types.
- If quality is ≥ raw GDELT, cut over to GDELT Cloud for Phase 2.
**Effort:** 1–2 weeks (dev + validation)  
**Impact:** Simplified pipeline, lower noise, faster ingestion. Trade-off: historical bootstrap may need raw GDELT fallback.

---

### 3. **Build LLM-as-Judge Calibration for Ambiguous Eval Outcomes** (MEDIUM PRIORITY)
**Rationale:** Current eval framework manually resolves ambiguous misses (tagged `ambiguous`). LLM judge with kappa calibration could reduce manual review workload and accelerate feedback loop for prompt improvement.  
**Action Items:**
- Collect ~50 labeled samples: (agent decision, prediction, outcome, human verdict).
- Build LLM judge prompt using Sonnet. Test against calibration set.
- Measure Cohen's kappa against human labels (target > 0.6).
- If kappa > 0.6, use for auto-tagging ambiguous cases; otherwise escalate.
- Integrate into daily eval cron.
**Effort:** 1 week (dev + calibration)  
**Impact:** Faster eval loop, lower manual overhead. Enables iteration on prompt improvement.

---

## Sources

- [H3 Geospatial Library Updates](https://h3geo.org/docs/3.x/)
- [DuckDB H3 Extension](https://ftp.fau.de/cran/web/packages/duckh3/index.html)
- [deck.gl H3HexagonLayer API](https://deck.gl/docs/api-reference/geo-layers/h3-hexagon-layer)
- [DuckDB Ecosystem Newsletter May 2026](https://motherduck.com/blog/duckdb-ecosystem-newsletter-may-2026.md)
- [Claude Pricing in 2026](https://finout.io/blog/claude-pricing-in-2026-for-individuals-organizations-and-developers)
- [Claude Model Lineup 2026](https://www.secondtalent.com/resources/every-claude-ai-model-explained-compared/)
- [World Monitor - Geopolitical Data APIs 2026](https://www.worldmonitor.app/blog/posts/free-geopolitical-data-apis-2026/)
- [GDELT Project](https://en.wikipedia.org/wiki/GDELT_Project)
- [GDELT Cloud Documentation](https://docs.gdeltcloud.com/)
- [Kpler Maritime Data & APIs](https://www.kpler.com/solutions/fundamental-intelligence/maritime-data)
- [MarineTraffic AIS API Services](https://www.marinetraffic.com/en/ais-api-services)
- [LSEG Vessel Tracking Solution](https://www.lseg.com/en/data-analytics/products/workspace/updates/lseg-launches-vessel-tracking-solution)
- [LLM Evaluation Frameworks 2026](https://bigdataboutique.com/blog/llm-evaluation-frameworks-metrics-best-practices)
- [arXiv: Autorubric Framework (2603.00077)](https://arxiv.org/abs/2603.00077)
- [arXiv: Statistical Calibration of LLM Judges (2511.21140)](https://arxiv.org/abs/2511.21140)
- [FutureAGI: Prompt Versioning 2026](https://futureagi.com/blog/what-is-prompt-versioning-2026/)
- [FutureAGI: Best Prompt Experimentation Platforms 2026](https://futureagi.com/blog/best-prompt-experimentation-platforms-in-2026/)
- [DuckDB Performance Tuning Guide](https://duckdb.org/docs/guides/performance/how_to_tune_workloads)
- [freeCodeCamp: High-Frequency Real-Time Data in React](https://www.freecodecamp.org/news/high-frequency-real-time-data-in-react-from-ring-buffers-to-offscreencanvas/)
- [Querio: Top React Chart Libraries 2026](https://querio.ai/articles/best-react-chart-libraries-data-visualization)
- [Educative: Patterns for Real-Time Data](https://www.educative.io/courses/learn-react/np/patterns-for-real-time-data)

---

## Notes

- No critical gaps found in current stack. All recommendations are additive or exploratory.
- Model naming ambiguity and batch+caching incompatibility questions require immediate clarification with Anthropic.
- GDELT Cloud is the only data source finding with potential for streamlining the pipeline; recommend validation before cutover.
- LLM-as-judge and prompt versioning tools are improvements, not blockers. Current manual approach is acceptable for Phase 1.
- Performance findings are mostly confirming best practices already in design (React batching, delta+snapshot retention). No urgent optimization needed.
