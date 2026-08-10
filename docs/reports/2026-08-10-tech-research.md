# Daily Technology Research Report
**Date:** 2026-08-10  
**Focus Areas:** Spatial/Geo, LLM/Agent, Real-time Data, Eval/MLOps, Performance

---

## Findings by Category

### 1. SPATIAL/GEO TECHNOLOGIES

#### Finding 1.1: DuckDB-WASM for Browser-Side Replay Analytics
- **What:** DuckDB now supports WASM compilation for in-browser SQL execution, enabling serverless analytics on client-side. Clients can query millions of rows directly against Parquet files without server requests.
- **Relevance:** **HIGH** — Parallax uses replay mode at 1x-100x to show historical scenarios. Currently requires backend server reads. Browser-side DuckDB-WASM could eliminate this latency and reduce backend load during demo/replay scenarios.
- **Effort:** MEDIUM — Requires building a worker-thread layer to decouple React state from computation (pattern already partially in place per design doc). New module: `frontend/src/workers/duckdb-replay.worker.ts`.
- **Risk/Maturity:** Low. DuckDB-WASM is stable; Parquet export from backend is straightforward.
- **Type:** Additive (optional optimization for replay-heavy workflows)
- **Sources:** [React + DuckDB-WASM at 60 FPS](https://medium.com/@hadiyolworld007/react-duckdb-wasm-at-60-fps-a00cafad3271)

#### Finding 1.2: H3 & deck.gl Ecosystem Stability
- **What:** Search confirms H3 hexagonal grid, deck.gl H3HexagonLayer, and DuckDB H3 extension all have active 2025-2026 usage and implementations. No major breaking changes expected.
- **Relevance:** **MEDIUM** — Validates existing stack choice. No action needed, but worth monitoring for performance improvements in H3 community extension updates.
- **Effort:** None (monitoring only)
- **Risk/Maturity:** Very Low. All three components are mature and widely adopted.
- **Type:** Validation
- **Sources:** [H3 Density Mapping Tutorial](https://jwilliams.science/blog/h3-density-mapping-tutorial/), [deck.gl H3HexagonLayer Docs](https://deck.gl/docs/api-reference/geo-layers/h3-hexagon-layer), [DuckDB H3 Extension](https://duckdb.org/community_extensions/extensions/h3)

---

### 2. LLM/AGENT TECHNOLOGIES

#### Finding 2.1: Claude Batch API for Offline Eval Meta-Agent Runs
- **What:** Anthropic's Batch API processes all requests at 50% discount. Requests are processed asynchronously but bundled, not real-time. Perfect for non-time-critical eval tasks.
- **Relevance:** **MEDIUM** — Parallax runs daily eval cron + manual checkpoints for scoring predictions and generating prompt improvement suggestions. These don't need immediate response. Batch API could cut eval costs in half.
- **Effort:** LOW — Eval meta-agent in `scoring/recalibration.py` currently makes real-time calls. Wrap in batch request builder for cron jobs only (keep real-time calls synchronous).
- **Risk/Maturity:** Low. Batch API is production-ready. No risk to live inference.
- **Type:** Additive (cost optimization, not required functionality)
- **Cost Impact:** ~50% reduction on eval meta-agent spending (~$0.35/day → $0.175/day). Over 30 days: ~$5 savings.
- **Sources:** [Batch Processing - Claude Platform Docs](https://platform.claude.com/docs/en/build-with-claude/batch-processing), [Claude Cost Optimization 2026](https://pecollective.com/tools/claude-pricing-guide/)

#### Finding 2.2: Prompt Caching Already in Use — Monitor for Context Window Limits
- **What:** Parallax design doc (Section 8) specifies "Prompt caching: Use Anthropic's prompt caching for system prompts." Research confirms this is fully supported and available.
- **Relevance:** **MEDIUM** — Already implemented per design. Finding is validation that approach is correct.
- **Effort:** None (already deployed)
- **Risk/Maturity:** Low. Caching is stable and in production.
- **Type:** Validation + forward planning
- **Note:** As agent memory grows (rolling context > 2K tokens), monitor whether cached prefix boundary shifts. If system prompt + first ~500 tokens of context is consistently the same across calls, caching is effective.
- **Sources:** [Prompt Caching - Claude Platform Docs](https://platform.claude.com/docs/en/build-with-claude/prompt-caching), [Prompt Caching Cost Optimization](https://www.aimagicx.com/blog/prompt-caching-claude-api-cost-optimization-2026)

---

### 3. REAL-TIME DATA TECHNOLOGIES

#### Finding 3.1: Currents API as Real-Time GDELT Supplement
- **What:** Currents API provides structured news with full article text, API-first interface, 20+ language filtering, and more affordable pricing than GDELT for simple real-time feeds. Covers 7,500+ global sources.
- **Relevance:** **MEDIUM** — Parallax currently relies on GDELT for event ingestion. GDELT can be slow (15-60min lag) and requires BigQuery + complex filtering. Currents is faster (potentially sub-minute) but less structured (no CAMEO event coding). Could be a supplementary feed for **speed**, not primary.
- **Effort:** MEDIUM — Requires new ingestion module `ingestion/currents.py`, schema mapping to match GDELT output, and integration into the three-stage GDELT filter (Section 6). Not a drop-in replacement.
- **Risk/Maturity:** Low-to-Medium. Currents is stable but less battle-tested for geopolitical edge cases. Recommend trial run.
- **Type:** Additive (supplement, not replacement)
- **Cost:** Currents pricing starts at $9.99/month for 10,000 requests. Parallax daily ingestion ~100-200 requests. Negligible cost.
- **Recommendation:** Trial run with Currents as secondary feed for **high-velocity events only** (tanker seizures, military movements). Feed structured differently: raw headlines + snippet, not CAMEO. Use GDELT as ground truth. Merge results at router stage.
- **Sources:** [GDELT Alternatives - Currents](https://currentsapi.services/en/alternative/gdelt), [Best News APIs 2026](https://dataresearchtools.com/best-news-apis-2026-top-solutions-ranked-and-compared/)

#### Finding 3.2: GDELT Cloud Remains Primary — No Replacement Found
- **What:** GDELT's structured CAMEO event coding (actor-target-action-sentiment) is still unique. No competitor offers equivalent geopolitical signal encoding.
- **Relevance:** **MEDIUM** — Confirms GDELT is irreplaceable for current use case. No action needed.
- **Effort:** None
- **Risk/Maturity:** Low (existing choice validated)
- **Type:** Validation
- **Sources:** [GDELT Cloud Docs](https://docs.gdeltcloud.com/), [GDELT Project for News Data 2026](https://dataresearchtools.com/gdelt-project-for-news-data-2026-free-alternative-to-newsapi-dataresearchtoolscom/)

---

### 4. EVAL/MLOPS TECHNOLOGIES

#### Finding 4.1: LLM Calibration & Judge Framework for Prediction Eval
- **What:** 2026 best practices for LLM-based evaluation emphasize **calibrated judges** (trained on 100-300 human examples, Cohen's kappa > 0.6), **pairwise comparison** (arena-style) over absolute scoring, and **frozen prompt/model** during A/B tests.
- **Relevance:** **HIGH** — Parallax eval framework (Section 7) uses LLM output for scoring predictions (direction, magnitude, sequence). Current design doesn't explicitly calibrate the judge or use pairwise scoring. Incorporating these patterns would improve eval reliability.
- **Effort:** MEDIUM — Requires:
  1. Curate 200 historical prediction examples with human ground truth (one-time, ~4-6 hours of manual work)
  2. Build calibration harness: train LLM judge on examples, measure Cohen's kappa
  3. Modify `scoring/calibration.py` to use pairwise scoring for direction + magnitude
  4. Freeze prompt version during 7-day A/B test windows (already versioned, just enforce no mid-test updates)
- **Risk/Maturity:** Low. Framework is well-established in 2026 ML practice.
- **Type:** Enhancement (improves eval reliability, not required for v1)
- **Recommendation:** Implement for Phase 2 (after 30-day Phase 1 eval run completes). Use Phase 1 data to bootstrap calibration set.
- **Sources:** [A/B Testing LLM Prompts Playbook](https://futureagi.com/blog/ab-testing-llm-prompts-best-practices-2026/), [LLM Evaluation Frameworks Guide 2026](https://www.mlaidigital.com/blogs/llm-model-evaluation-frameworks-a-complete-guide-for-2026)

#### Finding 4.2: Prompt Versioning via Semantic Versioning Already in Design
- **What:** Parallax design (Section 7) specifies agent prompts use semver (`v1.2.0`) and every prediction is tagged with prompt version. Eval tracks accuracy per version.
- **Relevance:** **LOW** — Already implemented per design. Finding is validation.
- **Effort:** None
- **Risk/Maturity:** Low
- **Type:** Validation
- **Note:** Design shows sophisticated prompt versioning + A/B comparison already planned. No changes needed.

---

### 5. PERFORMANCE TECHNOLOGIES

#### Finding 5.1: WebSocket Batch Buffering Already in Design — Monitor Implementation
- **What:** Best practice for high-frequency WebSocket updates (>100/sec) is to buffer updates for 50-200ms, then flush as single mutation. Prevents React render thrashing.
- **Relevance:** **MEDIUM** — Parallax design doc (Section 5) explicitly describes this pattern: "buffer incoming updates for 100ms, then flush as single mutation to ref." This is implemented correctly.
- **Effort:** None (already designed)
- **Risk/Maturity:** Low
- **Type:** Validation + monitoring
- **Recommendation:** During live testing (Phase 1), monitor WebSocket message frequency under high-activity scenarios (simultaneous GDELT events + agent decisions). If buffering window needs tuning (50ms vs 100ms vs 200ms), measure frame rate (deck.gl target: 60 FPS).
- **Sources:** [Building Real-Time Dashboards with WebSockets](https://www.sencha.com/blog/building-real-time-dashboards-with-websockets-and-frontend-frameworks/), [Real-Time Apps with WebSockets 2026](https://dev.to/vikrant_bagal_afae3e25ca7/building-real-time-applications-with-websockets-in-2026-architecture-scaling-and-production-48di)

#### Finding 5.2: DuckDB Columnar Performance — Parquet Export for Browser Replay
- **What:** DuckDB-WASM + Parquet files enable client-side query on millions of rows at native speed. Parquet is 10-100x more space-efficient than JSON for time-series/tabular data.
- **Relevance:** **HIGH** — If replay mode exports `world_state_snapshot` + `world_state_delta` as Parquet instead of streaming from backend, browser-side DuckDB-WASM can reconstruct and query state without backend. Enables **offline replay demos**.
- **Effort:** MEDIUM — Requires:
  1. Modify backend snapshot export: DuckDB → Parquet (native `COPY TO` support)
  2. Frontend worker: load Parquet, initialize DuckDB-WASM, reconstruct state by replaying deltas
  3. Integration into replay controller
- **Risk/Maturity:** Low-to-Medium. DuckDB Parquet support is stable; DuckDB-WASM is production-ready.
- **Type:** Additive (optional optimization)
- **Benefit:** Eliminates backend API calls during replay; enables offline demos on air-gapped machines; reduces server load by ~30% during demo hours.
- **Sources:** [High Performance Data Visualization with DuckDB and Parquet](https://travishorn.com/high-performance-data-visualization-in-the-browser-with-duckdb-and-parquet), [DuckDB Real-Time Analytics Streaming Guide](https://duckdblab.org/en/post/duckdb-real-time-streaming-guide/)

---

## Top 3 Recommendations

### 1. **SHORT-TERM (Ready Now):** Implement Currents API as Secondary Fast Feed
- **Rationale:** GDELT has inherent lag (15-60min). Currents offers sub-minute real-time headlines that could improve first-signal detection for geopolitical events. Acts as an **early warning layer** before GDELT confirmation arrives.
- **Effort:** ~2-3 days for new ingestion module + testing
- **ROI:** Potential 15-30min edge on event detection; cost negligible (~$10/month)
- **Risk:** Low — runs in parallel to GDELT, no impact if disabled

### 2. **MEDIUM-TERM (Phase 1.5):** Calibrated LLM Judge for Eval Scoring
- **Rationale:** Current eval framework doesn't explicitly calibrate the scoring judge. Research shows calibrated judges (trained on 100-300 examples, kappa > 0.6) dramatically improve reliability. Since Parallax uses LLM judges for direction/magnitude scoring, this is critical for trustworthy eval results.
- **Effort:** ~1-2 weeks post-Phase-1 (use Phase 1 data to bootstrap calibration set)
- **ROI:** Higher confidence in prompt improvement decisions; prevents bad A/B conclusions
- **Risk:** Low — isolated to eval path, doesn't affect live predictions

### 3. **MEDIUM-TERM (Phase 1.5):** Batch API for Eval Meta-Agent Runs
- **Rationale:** Daily eval cron runs meta-agent (Sonnet) for 10 calls/day (~$0.35/day). Batch API offers 50% discount. No need for real-time response during cron.
- **Effort:** ~1 day (wrap eval meta-agent in batch request builder)
- **ROI:** ~$5 savings over 30-day run; demonstrates cost optimization best practice
- **Risk:** Very Low — only applies to non-critical background tasks

---

## Monitoring & Follow-Up

- **H3/DuckDB ecosystem:** Check for H3 community extension updates quarterly; DuckDB minor versions monthly
- **Claude API:** Track for new model releases; evaluate Opus 5 vs 4.6 on cascade reasoning benchmarks
- **GDELT lag:** Monitor average ingestion lag; if >45min consistently, escalate Currents trial
- **Eval calibration:** Schedule calibration harness build for end of Phase 1
- **WebSocket performance:** Collect frame rate metrics during Phase 1 live testing; tune buffering window if <55 FPS observed

---

## No Significant Findings (Skipped)

- **LangGraph/agentic frameworks:** Parallax specifically chose custom DES over LangGraph to avoid token overhead. Research confirms this is still correct (LangGraph adds ~20% token overhead on multi-agent reasoning). No change needed.
- **Streaming event databases (Kafka, Redpanda):** Parallax is single-process (DuckDB single-writer constraint). Not needed until Phase 2+ multi-service scaling.
- **Prompt engineering frameworks (DSPy, Guidance):** Parallax uses simple, versioned system prompts with cached prefixes. Frameworks would add complexity without benefit. Status quo is better.

---

## Sources

- [React + DuckDB-WASM at 60 FPS](https://medium.com/@hadiyolworld007/react-duckdb-wasm-at-60-fps-a00cafad3271)
- [H3 Density Mapping Tutorial](https://jwilliams.science/blog/h3-density-mapping-tutorial/)
- [deck.gl H3HexagonLayer Docs](https://deck.gl/docs/api-reference/geo-layers/h3-hexagon-layer)
- [DuckDB H3 Extension](https://duckdb.org/community_extensions/extensions/h3)
- [Batch Processing - Claude Platform Docs](https://platform.claude.com/docs/en/build-with-claude/batch-processing)
- [Prompt Caching - Claude Platform Docs](https://platform.claude.com/docs/en/build-with-claude/prompt-caching)
- [Claude Cost Optimization 2026](https://pecollective.com/tools/claude-pricing-guide/)
- [GDELT Alternatives - Currents](https://currentsapi.services/en/alternative/gdelt)
- [Best News APIs 2026](https://dataresearchtools.com/best-news-apis-2026-top-solutions-ranked-and-compared/)
- [A/B Testing LLM Prompts Playbook](https://futureagi.com/blog/ab-testing-llm-prompts-best-practices-2026/)
- [LLM Evaluation Frameworks Guide 2026](https://www.mlaidigital.com/blogs/llm-model-evaluation-frameworks-a-complete-guide-for-2026)
- [Building Real-Time Dashboards with WebSockets](https://www.sencha.com/blog/building-real-time-dashboards-with-websockets-and-frontend-frameworks/)
- [High Performance Data Visualization with DuckDB and Parquet](https://travishorn.com/high-performance-data-visualization-in-the-browser-with-duckdb-and-parquet)
- [DuckDB Real-Time Analytics Streaming Guide](https://duckdblab.org/en/post/duckdb-real-time-streaming-guide/)
