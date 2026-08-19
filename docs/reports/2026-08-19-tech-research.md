# Tech Research Scout Report
**Date:** 2026-08-19  
**Focus Areas:** Spatial/Geo, LLM/Agent, Real-time Data, Eval/MLOps, Performance

---

## Executive Summary

Three high-impact improvements identified that directly strengthen Parallax's core stack. Structured outputs now available on Claude Sonnet/Opus (critical for agent output validation). DuckDB spatial joins achieved 58x performance boost in v1.3.0 (relevant for large-scale H3 cell operations). Claude batch API + prompt caching now mature and stackable for up to 70-80% cost reduction.

---

## Findings by Category

### 1. Spatial/Geo: DuckDB Spatial Joins – Major Performance Unlock

**Finding:** DuckDB v1.3.0 introduced a dedicated `SPATIAL_JOIN` operator that delivers 58x performance improvement for geospatial joins. Execution on 58M row datasets now faster than naive nested-loop join on 1M rows.

**Relevance:** **HIGH** — Parallax's H3 cell cascade rules require frequent spatial proximity queries across 400K hexes. This directly addresses the single biggest scaling risk in the simulation engine.

**Effort:** LOW — Single DuckDB version bump (1.2+ to 1.3+), no code changes. Automatic fallback to old path if v1.3 unavailable.

**Risk/Maturity:** LOW — Production-ready. Already integrated into DuckDB core (not an extension).

**Current Stack:** Uses DuckDB 1.2+ with H3 community extension. Likely running pre-1.3.0 version.

**Action:** Upgrade DuckDB dependency in `pyproject.toml` to `>=1.3.0`. Benchmark cascade rule performance (bloackade → flow reduction) before/after to quantify gains.

**Sources:** [DuckDB Spatial Joins announcement](https://duckdb.org/2025/08/08/spatial-joins) | [Architecture & Performance analysis](https://aetperf.github.io/2025/03/04/Spatial_queries_in_DuckDB_with_R-tree_and_H3_indexing.html)

---

### 2. LLM/Agent: Structured Outputs + Extended Prompt Caching – Agent Output Hardening + Cost Cut

**Finding #A:** Claude API now ships with **strict structured outputs** (JSON schema enforcement at token generation level). Works with Sonnet 4.5/Opus 4.1; Haiku 4.5 support coming soon. Ensures agent output always conforms to schema — no validation failures on malformed JSON.

**Relevance:** **HIGH** — Parallax's agent validation layer currently rejects malformed outputs and logs failures. Structured outputs eliminate this edge case entirely, making agent output parsing bulletproof.

**Effort:** MEDIUM — Requires `anthropic-beta: structured-outputs-2025-11-13` header and minor schema update. Pydantic models already define agent schemas; Claude SDK auto-converts to JSON schema.

**Risk/Maturity:** LOW — Beta feature but well-documented. No breaking changes expected.

**Finding #B:** Claude API prompt caching now supports **1-hour TTL** (alongside 5-min option). Write cost 2x base rate; read cost 0.1x base rate. Message Batches API supports prompt caching, providing **70-80% cost reduction** when both features stack.

**Relevance:** **HIGH** — Parallax's system prompts (historical baseline per agent) are static and large (~2-3K tokens). 1-hour caching + batch processing reduces cost from ~$2-5/day to ~$0.50-1.50/day.

**Effort:** MEDIUM — Requires refactoring agent call loop to use batch API (async queue → batch request builder). Cache TTL is automatic.

**Risk/Maturity:** PRODUCTION — Batch API fully mature (v1.1+). Cost impact is tangible only with high-volume calls (50+ agents daily).

**Action:** Prioritize structured outputs first (trivial ROI). Batch API refactor is lower priority for Phase 1 (current cost is acceptable), but essential for Phase 2 scaling.

**Sources:** [Claude API Batch Processing Docs](https://platform.claude.com/docs/en/build-with-claude/batch-processing) | [Structured Outputs Guide](https://platform.claude.com/docs/en/build-with-claude/structured-outputs) | [Cost optimization article](https://blog.imseankim.com/anthropic-claude-api-batch-processing-prompt-caching-cost-reduction-october-2025/)

---

### 3. Real-Time Data: Kpler (MarineTraffic) Consolidation + AIS Alternatives

**Finding:** MarineTraffic/FleetMon/Spire Maritime unified under **Kpler** (as of Sept 2025). Largest AIS network (13K+ receivers). Switched from credit-based to **enterprise subscription model only** — self-serve pricing no longer available.

**Relevance:** **MEDIUM** — Current stack doesn't use real-time AIS yet. Adding live vessel tracking (Hormuz strait) would improve cascade realism. However, Kpler's new subscription model may not fit Phase 1 budget.

**Effort:** MEDIUM — Requires API integration + WebSocket subscription handler.

**Risk/Maturity:** MEDIUM — Enterprise-only model raises cost/friction. Kpler's historical data and SLAs are strong, but entry cost is now undefined (requires sales contact).

**Alternative:** [Datalastic](https://datalastic.com/) offers self-serve AIS API alternative; [AISstream.io](https://aisstream.io/) offers free WebSocket; [VesselFinder API](https://www.vesselfinder.com/realtime-ais-data) offers credit-based pricing (pre-2025 model still available elsewhere).

**Action:** Skip for Phase 1 (GDELT event-based cascades sufficient). Evaluate Datalastic or AISstream for Phase 2 if budget allows. Get Kpler quote only if AIS becomes critical path.

**Sources:** [Kpler MarineTraffic Data Services](https://marinetraffic.com/en/ais-api-services/) | [AIS API comparison 2025](https://datadocked.com/ais-api-providers/) | [50 Best Ship Tracking APIs 2026](https://hormuzmonitor.com/50-best-ship-tracking-apis-2026/)

---

### 4. Eval/MLOps: Calibration Frameworks + A/B Testing Platforms

**Finding #A:** LLM evaluation frameworks now mature (HELM, OpenAI Evals, HELMeTRIC). Calibration metrics standard: ECE (Expected Calibration Error), ACE (Adaptive Calibration Error), Brier Score, NLL. Production monitoring combining offline benchmarks + human review + production telemetry.

**Relevance:** **HIGH** — Parallax's eval framework already tracks calibration (Section 7, design spec). Integrating a calibration library saves re-implementing metrics from scratch.

**Effort:** LOW — Can integrate `pycalibration` or similar. Existing scoring logic maps directly.

**Risk/Maturity:** LOW — Industry standard.

**Finding #B:** Prompt versioning + A/B testing platforms now mature. **Braintrust** (side-by-side comparison), **Langfuse** (prompt management + A/B), **Maxim** (prompt versioning + experiment tracking).

**Relevance:** **MEDIUM** — Parallax's prompt improvement pipeline (Section 7) currently manual. Adopting a framework adds scalability for Phase 2 when agent count grows.

**Effort:** MEDIUM — Langfuse integrates cleanly with async code (webhooks). Requires connecting decision logs to platform.

**Risk/Maturity:** PRODUCTION — All three platforms are production-grade. Langfuse offers self-hosted option.

**Action:** For Phase 1, keep manual prompt A/B (admin dashboard). For Phase 2, integrate Langfuse (self-hosted) or evaluate Braintrust if cost allows. Calibration metrics integrate into existing daily scorecard now (low-hanging fruit).

**Sources:** [Langfuse A/B Testing Docs](https://langfuse.com/docs/prompt-management/features/a-b-testing) | [Deepchecks LLM Evaluation Framework Guide](https://deepchecks.com/llm-evaluation/framework/) | [Braintrust A/B Testing](https://www.braintrust.dev/articles/ab-testing-llm-prompts)

---

### 5. Performance: deck.gl H3 Rendering + React Virtualization

**Finding #A:** deck.gl `H3HexagonLayer` now supports `highPrecision: false` flag for low-precision, high-performance rendering. Useful when edge-case sub-cell accuracy isn't needed (e.g., regional fleet positions don't require sub-100m precision).

**Relevance:** **MEDIUM** — Current design uses Res 3-9 H3 cells (400K total budget well under 500K deck.gl comfort zone). Precision optimization likely not critical path unless resolution scales up Phase 2.

**Effort:** LOW — Single property flag. Existing code already has 4-layer resolution strategy that implicitly trades precision for performance.

**Risk/Maturity:** LOW — Documented feature in stable deck.gl.

**Finding #B:** React dashboard rendering large datasets requires virtualization (windowing). `react-window` reduced table render time 1.2s → 200ms for 10K+ rows. WebSocket update batching (100-200ms windows) prevents render thrashing.

**Relevance:** **HIGH** — Parallax frontend already implements batching per design spec (Section 5, "Render Performance"). Batching to 100ms flush rate prevents per-message React re-renders.

**Effort:** LOW — Already implemented. Code uses `useRef` for H3 data + batched updates per spec.

**Risk/Maturity:** PROVEN — Parallax frontend design already incorporates this best practice.

**Action:** No changes needed for current implementation. If timeline scrub or agent feed scales beyond current 50 agents, consider `react-window` for virtualization (trivial addition).

**Sources:** [Syncfusion React Large Datasets Guide](https://www.syncfusion.com/blogs/post/render-large-datasets-in-react) | [deck.gl Performance Optimization](https://deck.gl/docs/developer-guide/performance)

---

### 6. Data: Oil Price APIs + Geopolitical Early Warning

**Finding #A:** EIA API remains best free option (daily WTI/Brent). For sub-minute futures or institutional data, **OilPriceAPI** offers comprehensive commodity coverage at fraction of Bloomberg cost. **FRED** (Federal Reserve) also offers historical oil price series.

**Relevance:** **LOW** — Current stack uses EIA API (v2). Sufficient for Phase 1 daily forecasting. FRED/OilPriceAPI unnecessary unless futures forward curve needed (Phase 2 refinement).

**Effort:** LOW — Drop-in API swap if needed.

**Risk/Maturity:** PRODUCTION — All APIs stable and well-documented.

**Finding #B:** Geopolitical early warning research shows emerging ML/NLP approaches: Composite Early Warning Index (CEWI) integrates macro-financial + political uncertainty; anomaly detection identifies pattern breaks in behavioral data. Research-stage but relevant for future agent prompt grounding.

**Relevance:** **LOW (Research)** — Parallax's cascade + agent reasoning is deterministic/heuristic-based. LLM agents don't currently use anomaly signals. Useful background for Phase 2 agent sophistication (e.g., "detect surge in overnight tanker insurance quotes as escalation signal").

**Effort:** MEDIUM+ (Research integration) — Would require new data pipelines (anomaly detection on event timeseries) + agent prompt updates.

**Risk/Maturity:** RESEARCH — Not production-ready, but academic precedent solid.

**Action:** Skip for Phase 1. Track for Phase 2 if agent prediction accuracy plateaus.

**Sources:** [BBVA Geopolitics Monitor](https://www.suerf.org/publications/suerf-policy-notes-and-briefs/the-bbva-research-geopolitics-monitor-tracking-geopolitical-sentiment-and-events-using-natural-language-techniques/) | [Crisis Observatory research](https://studies.aljazeera.net/en/analyses/toward-geopolitical-crisis-observatory-diagnosing-systemic-risk-news-flows-using-complex)

---

## Top 3 Recommendations

### 1. **Adopt Claude Structured Outputs (NOW)**
- **Why:** Agent output validation currently relies on post-hoc JSON parsing. Structured outputs eliminate malformed output edge cases at inference time.
- **Effort:** 1-2 hours to wire up. Pydantic schemas already exist.
- **Impact:** Improved robustness, cleaner error logs. Zero cost (free feature).
- **Timeline:** Add to next iteration cycle.

### 2. **Upgrade DuckDB to 1.3.0+ (NOW)**
- **Why:** 58x spatial join speedup directly benefits cascade engine (largest potential bottleneck). Single version bump, automatic benefits.
- **Effort:** 15 minutes (dependency update + test).
- **Impact:** Cascade throughput may improve 2-5x if currently hitting spatial join slowdowns. Measure empirically.
- **Timeline:** Immediate.

### 3. **Evaluate Langfuse for Phase 2 Prompt Management (PLAN)**
- **Why:** Manual prompt A/B testing works for Phase 1 (5-10 agents active). Phase 2 scales to 50+ agents and multi-scenario. Langfuse self-hosted option avoids vendor lock-in.
- **Effort:** 1-2 days integration + DevOps setup.
- **Impact:** Enables data-driven prompt versioning, automatic rollback on accuracy decline.
- **Timeline:** End of Phase 1, before Phase 2 scaling.

---

## Conclusion

**Current stack is well-positioned.** No critical gaps identified. Three targeted improvements offer clear ROI with low friction. DuckDB spatial upgrade is immediate win; Claude structured outputs add robustness; Langfuse planning ensures Phase 2 scales cleanly.

**No rip-and-replace risks:** React, deck.gl, FastAPI all current and well-maintained. GDELT remains reliable primary source despite alternatives. Agent cost control strategy already sound and will improve further with batch API adoption (Phase 2).

---

**Report compiled:** 2026-08-19 | **Next review:** 2026-09-16
