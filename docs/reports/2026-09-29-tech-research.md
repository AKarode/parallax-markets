# Tech Research Report — 2026-09-29

**Focus areas:** Spatial/Geo, LLM/Agent, Real-time Data, Eval/MLOps, Performance

**Current date:** 2026-09-29  
**Parallax Phase:** Phase 1 (Iran/Hormuz scenario, live dashboard, continuous eval)

---

## Executive Summary

Parallax's tech stack is solid for Phase 1. No critical gaps or disruptive alternatives found. Key opportunities for Phase 2:

1. **Claude Batch API** + Prompt Caching can reduce LLM costs by 50-80% when combined — immediate win for high-volume agent evaluation or nightly eval runs.
2. **Helicone** or **LangSmith** would accelerate prompt versioning and A/B testing workflows currently manual in the eval framework.
3. **WorldMonitor** or **UCDP** APIs could supplement GDELT with structured geopolitical conflict data, reducing dedup burden.
4. **DuckDB-WASM + Web Workers** pattern can improve frontend dashboard responsiveness, but not critical for current H3 hex budget.

**No changes recommended for Phase 1.** All findings are additive; current stack is unblocked.

---

## 1. Spatial/Geo Technologies

### H3 and deck.gl — Status Quo Optimal

**Findings:**
- H3 remains the industry standard for hexagonal geospatial indexing. No competing hex grid library has gained adoption comparable to H3.
- deck.gl's `H3HexagonLayer` and `H3ClusterLayer` are actively maintained; latest updates (2024-2025) focus on performance and GPU memory efficiency.
- kepler.gl (built on deck.gl + H3) is the reference implementation for large-scale hex visualization.
- Overture Maps (used for static base layer) is mature and stable.

**Relevance:** HIGH (confirming current choice)  
**Effort to adopt alternatives:** N/A — H3 is the clear winner  
**Risk:** LOW — H3 ecosystem is stable, no deprecation signals

**Assessment:** Parallax's spatial tech stack (H3 community extension in DuckDB + deck.gl H3 layers) is optimal. No upgrade or alternative needed. The ~400K hex budget is well within deck.gl's 500K comfort zone.

### New H3 Extensions

**Findings:**
- ClickHouse added native H3 support via `clickhouse-h3` library for spatial aggregations — **not relevant** to Parallax since Parallax uses DuckDB, not ClickHouse.
- HexWeather (2024) uses H3 for weather grid aggregation — a use case pattern, not a new library.
- No new H3 bindings or language wrappers appeared in 2024-2025 beyond existing ones (Python, JavaScript, Rust).

**Relevance:** LOW  
**Effort:** N/A — purely informational  
**Risk:** N/A

**Recommendation:** Monitor H3 release notes for performance improvements, but no action needed.

---

## 2. LLM/Agent Technologies

### Claude Batch API + Prompt Caching — High-Impact Opportunity for Phase 2

**Findings:**

[Batch Processing](https://platform.claude.com/docs/en/build-with-claude/batch-processing):
- Claude Batch API provides 50% discount on input and output tokens.
- Accepts up to 10,000 requests per batch.
- Asynchronous processing — results delivered later (typically within minutes to hours, not real-time).
- **Ideal for:** nightly eval runs, historical reprocessing, batch prediction generation.

[Prompt Caching](https://platform.claude.com/docs/en/about-claude/pricing):
- System prompt + historical baseline cached for 5 minutes (Sonnet), 1 hour (Haiku).
- Cache read tokens cost 10% of input tokens; writes cost 125% (net savings on repeated calls).
- Real-world cache hit rates: 30-98% depending on traffic patterns.

**Combined Benefit:**
- Batch API (50%) + Prompt Caching (90% savings on cached portion) = **50-80% total cost reduction** when both are stacked.
- Parallax currently uses prompt caching implicitly (system prompts are stable per agent version). Batch API is not yet integrated.

**Current Parallax Usage:**
- Sub-actor calls (Haiku): ~200/day × $0.002 = $0.40/day
- Country agent calls (Sonnet): ~50/day × $0.025 = $1.25/day
- Eval meta-agent: ~10/day × $0.035 = $0.35/day
- **Current estimated: $2-5/day under normal conditions.**

**With Batch API:**
- Projected: $1-2.5/day under normal conditions (50% reduction).
- Eval runs could drop from ~$0.35/day to ~$0.08/day.

**Relevance:** HIGH (cost optimization + scalability)  
**Effort to integrate:**
- Batch API: ~2-3 days (refactor daily eval cron to submit batch, poll for results, no real-time impact).
- Prompt Caching: Already in use; no changes needed.
**Risk:** LOW — Batch API is well-documented; only trade-off is latency (not real-time).

**Recommendation:**
- **Phase 2 priority:** Integrate Batch API for nightly eval runs (checkpoint predictions, score, backfill metrics). Keeps real-time live predictions on synchronous calls.
- Verify cache TTL behavior in production before full rollout.

### Agent Orchestration Frameworks

**Findings:**
- LangGraph remains the dominant multi-agent orchestration framework (LLMs use it, it's well-documented).
- Phase 1 design explicitly chose custom DES (asyncio + heapq) over LangGraph to avoid boilerplate and maintain fine-grained control over event timing.
- No new frameworks have emerged that challenge LangGraph's position or offer compelling Phase 1 advantages.
- **Parallax's custom DES is actually simpler than LangGraph for this use case** — agents are stateless event handlers, not multi-turn reasoning chains.

**Relevance:** MEDIUM (informational; design decision already made)  
**Effort:** N/A  
**Risk:** N/A

**Recommendation:** Stick with custom DES. LangGraph would be overkill for Phase 1 and would increase latency (not needed for discrete event simulation).

### Structured Output Improvements

**Findings:**
- Claude API now supports JSON mode and schema enforcement natively (no external libraries).
- Pydantic v2 integration improves type validation on both input and output.
- Agent output schemas in Parallax (e.g., `PredictionOutput`, `AgentDecision`) are already well-defined.

**Relevance:** LOW (already in use)  
**Effort:** N/A — no changes needed  
**Risk:** N/A

**Recommendation:** No action needed. Agent output validation is already robust.

---

## 3. Real-Time Data Sources

### GDELT Alternatives and Supplements

**Findings:**

[GDELT Strengths & Limitations](https://www.worldmonitor.app/blog/posts/free-geopolitical-data-apis-2026/):
- GDELT: 15-minute cadence, 100+ languages, established infrastructure.
- Limitations: Duplicate reports, uneven media coverage bias, automated coding errors.

**Alternative Sources:**

| Source | Type | Frequency | Relevance to Parallax |
|--------|------|-----------|----------------------|
| [ACLED](https://acleddata.com/) | Conflict events (curated) | Weekly (validated/lagged) | Already integrated; good supplement to GDELT |
| [UCDP (Uppsala)](https://www.andybeger.com/data/ucdp/) | Conflict data + API | Weekly | HIGH — structured, peer-reviewed, free API with token auth |
| [WorldMonitor](https://www.worldmonitor.app/) | Unified dashboard (multiple sources) | Integrated | MEDIUM — good for signal cross-validation; read-only |
| [IMF PortWatch](https://www.worldmonitor.app/blog/posts/free-geopolitical-data-apis-2026/) | Vessel transit history | Daily | HIGH — **missing from current stack**, crucial for Hormuz shipping tracking |
| [SEA.AI](https://en.wikipedia.org/wiki/SEA.AI) | AIS vessel tracking | Real-time | HIGH — fine-grained shipping corridor pressure signal |

**Relevance:** HIGH (shipping tracking especially critical for Hormuz scenario)  
**Effort to integrate:**
- UCDP API: 2-3 days (add new ingestion module in `parallax.ingestion.*`).
- IMF PortWatch or SEA.AI: 1-2 days each (requires API key, data schema mapping).
- WorldMonitor: Read-only cross-validation (3-5 days for integration if needed).
**Risk:** MEDIUM
- New APIs may have rate limits or cost (SEA.AI is commercial).
- Data schema differences from GDELT; dedup logic must adapt.

**Recommendation:**
- **Phase 2 priority:** Add UCDP and IMF PortWatch APIs as supplements to GDELT.
  - UCDP: Provides structured conflict event ground truth for eval scoring.
  - IMF PortWatch: Daily vessel-transit data directly measures Hormuz blockade effectiveness.
- Defer commercial AIS (SEA.AI) until Phase 2 revenue/budget allows.

### Geopolitical Event Consolidation

**Findings:**
- No single "geopolitical event API" exists. Current approach (GDELT + ACLED) covers news + conflict events.
- Emerging platforms (e.g., WorldMonitor) bundle multiple sources but are read-only dashboards, not APIs.
- Best practice: multi-source ingestion with local dedup (which Parallax already does via semantic embedding dedup).

**Relevance:** MEDIUM  
**Effort:** Already implemented via four-stage GDELT filter.  
**Risk:** LOW

**Recommendation:** Current multi-source approach is sound. No changes needed for Phase 1.

---

## 4. Eval/MLOps Frameworks

### Prompt Versioning and A/B Testing

**Findings:**

[Top Platforms (2024-2025)](https://www.helicone.ai/blog/prompt-evaluation-frameworks):

| Tool | Strength | Relevance to Parallax |
|------|----------|----------------------|
| [Helicone](https://www.helicone.ai/) | Open-source; prompt versioning, experimentation, eval dashboards | **HIGH** — directly addresses current manual eval workflow |
| [LangSmith](https://smith.langchain.com/) | Tracing, dataset-driven testing, regression testing | **HIGH** — structured A/B testing across prompt versions |
| [Braintrust](https://www.braintrust.dev/) | A/B testing, evaluation, prompt management | MEDIUM — competitive but less mature than LangSmith |
| [PromptLayer](https://promptlayer.com/) | Prompt management, backtesting, model comparison | MEDIUM — overlaps with Helicone |

**Current Parallax Implementation:**
- Manual prompt versioning (semver in `agent_prompts` table).
- Daily cron identifies declining agents, flags for admin review.
- No built-in A/B testing framework — comparisons are manual.
- Eval results live in `eval_results` table; no external dashboard.

**What Parallax is Missing:**
- Automated A/B test harness (run two prompt versions in parallel, measure statistical significance).
- Visualization of prompt version performance over time.
- Integration with LLM observability (cost, latency, success rate per version).

**Relevance:** HIGH (critical for Phase 1 eval, essential for Phase 2 scaling)  
**Effort to integrate:**
- Helicone: 2-3 days (API client integration, wrap Claude calls).
- LangSmith: 3-4 days (instrumentation + dataset setup).
- Custom lightweight A/B harness: 1-2 days (use existing eval infrastructure, add statistical test).
**Risk:** MEDIUM
- Helicone and LangSmith add external dependencies and require API keys.
- Custom harness keeps data in-house but requires more maintenance.

**Recommendation:**
- **Phase 1 immediate:** Build lightweight in-house A/B test harness (1-2 days).
  - Modify daily eval cron to run flagged agents with both old and new prompt versions in parallel.
  - Add t-test or chi-squared test to measure significance (statsmodels library).
  - Store results in `eval_results` table with `variant` column.
  - Admin dashboard gets a "A/B Results" tab.
- **Phase 2:** Integrate Helicone or LangSmith for richer observability and automated dashboards.

### LLM Evaluation Metrics

**Findings:**
- Standard metrics (direction accuracy, magnitude accuracy, calibration) are well-established.
- Parallax already implements these (see Phase 1 design, Section 7).
- No new evaluation frameworks have materially changed the methodology since 2023.

**Relevance:** LOW (already mature in Parallax)  
**Effort:** N/A  
**Risk:** N/A

**Recommendation:** No changes needed.

---

## 5. Performance — React + WebSocket + DuckDB

### React Rendering Optimization for Real-Time Updates

**Findings:**

[High-Frequency Update Patterns (2025)](https://www.wildnetedge.com/blogs/building-real-time-dashboards-with-react-and-websockets):
- **Problem:** High-frequency WebSocket updates (100s/sec) to React state cause render thrashing, freezing deck.gl canvas.
- **Solution (already implemented in Parallax spec):** Decouple React UI state from deck.gl data:
  - H3 hex data lives in `useRef` (mutable, not triggering re-renders).
  - WebSocket updates mutate the ref directly.
  - deck.gl pulls from the mutable ref on its own render cycle.
  - UI-level changes (agent feed, indicators) trigger React re-renders only when needed.
  - **Batch updates:** Buffer incoming WebSocket messages for ~100ms, flush as single mutation.

**Parallax Status:**
- Design spec (Section 5) already describes this pattern: "H3 hex data lives in a **mutable `useRef`**, not `useState`. WebSocket `cell_update` messages mutate the ref directly."
- Implementation is pending (frontend is not yet live), but the architecture is sound.

**Relevance:** MEDIUM (critical for Phase 1 frontend launch)  
**Effort:** Frontend dev implementation (~3-5 days for React components).  
**Risk:** LOW — pattern is well-established and proven.

**Recommendation:**
- **Phase 1 frontend:** Implement `useRef` + batching pattern as designed.
- No need for DuckDB-WASM in browser for Phase 1 (backend computes queries, frontend renders).
- Monitor dashboard responsiveness in staging before go-live.

### DuckDB-WASM for Client-Side Analytics

**Findings:**
- DuckDB-WASM allows embedding SQL engine in browser, enabling client-side aggregations without backend round-trips.
- Pattern: Use Web Workers to isolate DuckDB query engine from React main thread.
- Achieves 60 FPS with millions of rows via this architecture.
- **Best for:** Small-to-medium datasets (browser memory limits). Large exports to CSV, filtering dashboards.

**Parallax Applicability:**
- Not needed for Phase 1 (backend is lightweight, dashboard is primarily visualization).
- Could be useful in Phase 2 if offline replay mode needs client-side replay (currently runs server-side).

**Relevance:** LOW (not critical for Phase 1)  
**Effort:** 3-5 days if needed.  
**Risk:** MEDIUM (adds complexity; only worthwhile if clear use case).

**Recommendation:**
- Defer to Phase 2.
- If dashboard gets slow before Phase 2, profile first (likely culprit is WebSocket batching, not query speed).

### DuckDB Performance Tuning

**Findings:**
- Single-writer pattern (asyncio.Queue) already implemented in Parallax design.
- No major performance changes in DuckDB 1.2+ (current spec pins version); stable for Phase 1 scale (~100M rows/month).
- Delta + snapshot strategy (Section 8 of design spec) prevents state table bloat.
- No new indexing tricks needed; DuckDB auto-tunes for most workloads.

**Relevance:** LOW (design already sound)  
**Effort:** N/A  
**Risk:** N/A

**Recommendation:** No tuning needed pre-launch. Monitor query performance in staging; if dashboard is slow, add `CREATE INDEX` on frequently filtered columns (e.g., `tick`, `cell_id`).

---

## Top 3 Recommendations (Prioritized)

### 1. **Integrate Claude Batch API for Eval Runs** (Phase 2 — HIGH impact, LOW effort)

**Rationale:**
- Current eval cost: ~$0.35/day (meta-agent calls).
- With Batch API: ~$0.08/day (77% reduction).
- Eval cycle is already asynchronous (daily cron); Batch API's latency is acceptable.
- Enables scaling to more agents or more frequent eval checkpoints without cost penalty.

**Action:**
- Refactor `parallax.scoring.scorecard` to submit daily predictions as batch job.
- Poll batch results in morning; backfill `eval_results` table.
- Estimate savings: ~$10/month → $2.50/month during Phase 1 continuous eval window (April-May).

**Timeline:** 2-3 days; Phase 2 after go-live.

---

### 2. **Add UCDP + IMF PortWatch APIs as Data Supplements** (Phase 2 — HIGH impact, MEDIUM effort)

**Rationale:**
- GDELT coverage is good but noisy; UCDP provides peer-reviewed conflict data.
- IMF PortWatch gives daily vessel-transit counts for Hormuz — **direct measurement of blockade effectiveness**.
- Improves eval ground truth (prevents false positives on "was a blockade effective?").
- Reduces cascade engine tuning effort (empirical shipping data vs. parameters).

**Action:**
- Add `parallax.ingestion.ucdp` module (structured conflict event API).
- Add `parallax.ingestion.portwatch` module (daily vessel counts per corridor).
- Integrate into `curated_events` pipeline (similar to GDELT + ACLED).
- Backfill historical data (if available) to validate predictions against reality.

**Timeline:** 3-5 days; Phase 2 implementation.

---

### 3. **Build Lightweight In-House A/B Test Harness for Prompt Versions** (Phase 1 or early Phase 2 — MEDIUM impact, LOW effort)

**Rationale:**
- Current workflow: Admin manually compares prompt version accuracy.
- Lightweight harness (1-2 days) enables:
  - Run old + new prompt versions in parallel for flagged agents.
  - Compute statistical significance (t-test).
  - Display results in admin dashboard.
  - Auto-recommend rollback if new version underperforms.
- Faster iteration on prompt improvements → better calibration.

**Action:**
- Modify daily eval cron to accept `--ab-test` flag.
- For agents with declining accuracy, spawn both current and candidate prompts in parallel (single event batch).
- Store results with `prompt_version_A`, `prompt_version_B`, `winner`, `p_value` in `eval_results`.
- Add admin dashboard panel: "A/B Test Results" with statistical summary.

**Timeline:** 1-2 days; can ship in Phase 1 if time permits, or early Phase 2.

---

## Findings Summary Table

| Category | Finding | Relevance | Effort | Risk | Status |
|----------|---------|-----------|--------|------|--------|
| Spatial/Geo | H3 + deck.gl are optimal; no alternatives needed | HIGH | — | LOW | ✅ No action |
| Spatial/Geo | HexWeather, new H3 extensions are informational | LOW | — | N/A | ℹ️ Monitor only |
| LLM/Agent | Batch API + Prompt Caching = 50-80% cost reduction | HIGH | 2-3d | LOW | ⭐ Phase 2 priority |
| LLM/Agent | LangGraph not needed; custom DES is better for Phase 1 | MEDIUM | — | N/A | ✅ No action |
| Real-time Data | UCDP + IMF PortWatch are high-value supplements | HIGH | 3-5d | MEDIUM | ⭐ Phase 2 priority |
| Real-time Data | WorldMonitor useful for signal cross-validation | MEDIUM | 3-5d | MEDIUM | 🔄 Consider Phase 2 |
| Real-time Data | SEA.AI (commercial AIS) deferred until revenue | HIGH | 1-2d | MEDIUM | 🔄 Phase 3+ |
| Eval/MLOps | Helicone/LangSmith for rich dashboards | HIGH | 3-4d | MEDIUM | 🔄 Phase 2 integration |
| Eval/MLOps | Lightweight A/B test harness (in-house) | MEDIUM | 1-2d | LOW | ⭐ Phase 1/2 quick win |
| Performance | React `useRef` + batching pattern (already designed) | MEDIUM | 3-5d | LOW | ✅ Implement per spec |
| Performance | DuckDB-WASM for client-side analytics | LOW | 3-5d | MEDIUM | 🔄 Phase 2+ if needed |
| Performance | DuckDB tuning (design already sound) | LOW | — | N/A | ✅ No pre-launch action |

---

## Conclusion

Parallax's tech stack is well-chosen and unblocked for Phase 1. No critical gaps or disruptive alternatives found.

**For Phase 1 (launch):**
- Proceed as designed.
- Implement React `useRef` + batching per spec.
- No external tool additions needed.

**For Phase 2 (scale + improve):**
- Integrate Batch API (cost savings, scalability).
- Add UCDP + IMF PortWatch (better eval ground truth).
- Build lightweight A/B test harness (faster prompt iteration).
- Evaluate Helicone/LangSmith (rich observability).

---

## Sources

1. [H3 Geospatial Indexing System](https://h3geo.org/docs/) — H3 official docs
2. [deck.gl — What's New](https://deck.gl/docs/whats-new) — Latest updates
3. [Claude API Batch Processing](https://platform.claude.com/docs/en/build-with-claude/batch-processing) — Official docs
4. [Claude API Prompt Caching](https://platform.claude.com/docs/en/about-claude/pricing) — Pricing and caching
5. [Claude Cost Optimization: Batching + Caching](https://dev.to/whoffagents/claude-api-cost-optimization-caching-batching-and-60-token-reduction-in-production-3n49) — DEV Community
6. [GDELT Project — Alternatives and Comparisons](https://www.worldmonitor.app/blog/posts/free-geopolitical-data-apis-2026/) — World Monitor 2026 guide
7. [Building a Geopolitical Signal Desk with AIS](https://dev.to/wudwerd/building-a-geopolitical-signal-desk-ais-corridor-pressure-multi-source-price-cross-validation-3eap) — DEV Community (AIS best practices)
8. [Top Prompt Evaluation Frameworks in 2025](https://www.helicone.ai/blog/prompt-evaluation-frameworks) — Helicone blog
9. [A/B Testing for LLM Prompts](https://www.braintrust.dev/articles/ab-testing-llm-prompts) — Braintrust guide
10. [Building Real-Time Dashboards with React + WebSockets](https://www.wildnetedge.com/blogs/building-real-time-dashboards-with-react-and-websockets) — WildNet Edge
11. [React + DuckDB-WASM at 60 FPS](https://medium.com/@hadiyolworld007/react-duckdb-wasm-at-60-fps-a00cafad3271) — Medium article
12. [DuckDB for Real-Time Dashboards](https://dev.to/aelmufti/duckdb-for-real-time-dashboards-lessons-from-world-data-visualizer-57ij) — DEV Community (World Data Visualizer lessons)

---

**Report generated:** 2026-09-29  
**Next review:** 2026-10-27 (monthly cadence)
