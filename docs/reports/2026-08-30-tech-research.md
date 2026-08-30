# Tech Research Scout Report — 2026-08-30

**Focus areas searched:** Spatial/Geo visualization, LLM/Agent APIs and eval frameworks, Real-time geopolitical data, Performance optimization (DuckDB, WebSockets)

---

## Key Findings by Category

### 1. LLM/Agent — Claude API Cost Optimization (HIGH relevance)

**Finding: Stable Sonnet 5 pricing locks in cost savings**

Claude Sonnet 5 pricing is now locked at **$2/$10 per million input/output tokens** (previously scheduled to increase to $3/$15 on Sept 1, 2026). This stabilization removes uncertainty from Parallax's $20/day budget model.

- **Relevance:** HIGH — Direct cost impact on prediction model runs  
- **Effort:** NONE — Already integrated; this is pure upside  
- **Risk/Maturity:** PRODUCTION — Official pricing commitment  
- **Type:** Cost reduction (additive)

---

### 2. LLM/Agent — Batch API + Prompt Caching Combo (HIGH relevance)

**Finding: Combined savings strategy for eval pipeline**

The **Message Batches API** (50% discount on tokens) and **prompt caching** (90% discount on cached prefix tokens) now stack:
- Cached system prompts pay only 10% of normal input cost on repeat calls (5-min TTL)
- Batch API adds another 50% discount on both input and output
- **Combined:** Eval runs with repeated system prompts could reduce token costs by up to 80% vs standard API calls

Parallax's eval pipeline—which re-evaluates predictions with the same agent prompts repeatedly—is an ideal use case.

- **Relevance:** HIGH — Directly applies to daily eval cron and model_error re-scoring  
- **Effort:** MEDIUM — Already using prompt caching; requires integrating batch API for eval scorecards  
- **Risk/Maturity:** PRODUCTION — Batch API is stable; prompt caching is mature  
- **Type:** Cost optimization + throughput (additive)

**Recommendation:** Integrate batch API for the daily `compute_daily_scorecard()` eval job (which processes ~15+ metrics across 5 categories). This could reduce eval token spend from ~$0.35/day to ~$0.08/day.

---

### 3. LLM/Agent — Langfuse for Prompt Versioning (HIGH relevance)

**Finding: Open-source prompt management with version control and deployment labels**

**Langfuse** provides the exact workflow Parallax's eval framework needs:
- **Version control:** Every prompt change is tracked with automatic version IDs, timestamps, and diffs
- **Labels for environments:** Tag prompts with `production`, `staging`, `experiment-v1`, etc.
- **Quick rollback:** Change a label to instantly rollback all predictions to a prior version
- **A/B testing:** Compare versions across multiple agents simultaneously
- **Change log:** Full audit trail of who changed what and when

Parallax's manual prompt versioning (semver strings, `prompt_version` field in predictions) can be replaced by Langfuse's built-in system, eliminating manual tracking and enabling safer A/B testing.

- **Relevance:** HIGH — Directly implements the "prompt improvement pipeline" from the design spec  
- **Effort:** MEDIUM — Requires integrating Langfuse SDK, refactoring prompt storage from `agent_prompts` table to Langfuse  
- **Risk/Maturity:** PRODUCTION — Langfuse is open-source, backed by Series A funding, widely adopted  
- **Type:** Replacement (replaces manual versioning; additive for eval tracking)

**Recommendation:** Integrate Langfuse for the prompt management system. It would replace the `agent_prompts` table and provide:
1. Automatic version tracking (no more manual semver)
2. Safe A/B testing via labels (production/staging)
3. Instant rollback without code changes
4. Team collaboration on prompt edits (useful when expanding beyond one developer)

---

### 4. LLM/Agent — Promptfoo for Prompt Testing (MEDIUM relevance)

**Finding: YAML-driven prompt and model comparison tool**

**Promptfoo** excels at side-by-side model and prompt comparisons using a declarative YAML configuration. This avoids boilerplate Python code and makes it easy for non-technical domain experts (geopolitical analysts) to propose and test prompt variants.

- **Relevance:** MEDIUM — Useful for the prompt improvement pipeline, but not as critical as Langfuse  
- **Effort:** MEDIUM — Requires setting up test datasets and YAML configs  
- **Risk/Maturity:** PRODUCTION — Actively maintained, widely used  
- **Type:** Additive (complements Langfuse for testing)

**Recommendation:** Consider as a secondary tool if the team expands and non-engineers need to propose prompt changes. For now, focus on Langfuse first.

---

### 5. Real-time Data — WorldMonitor for Data Integration (MEDIUM relevance)

**Finding: Multi-source geopolitical data aggregator**

**WorldMonitor** integrates multiple free and paid geopolitical data sources (ACLED, UCDP, Cloudflare Radar, USGS, NASA FIRMS) into a single API with normalized country-risk, route-risk, market, news, and agent workflows.

Current Parallax stack:
- GDELT (high-recall narrative data)
- ACLED (structured conflict events)
- EIA (energy prices)

WorldMonitor would add:
- Infrastructure signals (Cloudflare Radar for internet outages)
- Physical hazards (USGS earthquakes, NASA fires)
- Unified normalization across sources

- **Relevance:** MEDIUM — Complements GDELT but not a replacement; adds infrastructure/hazard signals  
- **Effort:** MEDIUM — Requires API integration and contract negotiation (freemium model)  
- **Risk/Maturity:** EMERGING — Smaller startup; free tier exists, but production reliability TBD  
- **Type:** Additive (complements GDELT and ACLED)

**Recommendation:** Evaluate WorldMonitor's free tier post-launch. The infrastructure signals (internet outages, seismic events) could improve prediction accuracy for supply-chain disruptions, but it's not critical for Phase 1. ACLED + GDELT is sufficient.

---

### 6. Performance — DuckDB Asynchronous I/O (MEDIUM relevance)

**Finding: DuckDB v2.0 async reads for Parquet/CSV (Fall 2026)**

DuckDB v2.0 (scheduled fall 2026) adds **asynchronous I/O** for Parquet and CSV file reads. This allows concurrent reads without blocking, which is crucial for:
- Scaling the `world_state_delta` delta-table approach to multi-terabyte archives
- Parallel event ingestion (GDELT, ACLED) without blocking the event queue
- Faster replay mode throughput at 100x speed

Current bottleneck: DuckDB reads Parquet files synchronously. With async I/O, multiple reads can overlap.

- **Relevance:** MEDIUM — Matters for scaling Phase 2+ (multi-scenario support, archive queries)  
- **Effort:** LOW — Passive upgrade; async I/O is opt-in, not mandatory  
- **Risk/Maturity:** BETA — Feature announced for v2.0; not yet released  
- **Type:** Performance enhancement (additive)

**Recommendation:** Plan to upgrade to DuckDB v2.0 post-launch. For Phase 1 (single scenario, 30-day window), current performance is fine. But for multi-scenario support or long-term archives, async I/O becomes critical.

---

### 7. Performance — WebSocket Batching Already in Design (LOW action)

**Finding: Parallax is already implementing best practices**

The design spec's Section 5 (Frontend) explicitly describes the optimal WebSocket pattern for high-frequency updates:
- Batch incoming WebSocket updates for 100ms before flushing to mutable `useRef` data
- Decouple React UI state from deck.gl data arrays to avoid render thrashing
- Use `DataFilterExtension` or manual `setProps` for GPU-side updates

This matches 2026 best practices from industry experts. No action needed.

- **Relevance:** LOW — Already implemented in design  
- **Effort:** NONE  
- **Risk/Maturity:** PRODUCTION — Aligned with industry practice  
- **Type:** Validation (confirms current approach is sound)

---

### 8. Spatial/Geo — deck.gl MaskExtension for Filtering (LOW relevance)

**Finding: New deck.gl extension for geofence-based filtering**

deck.gl's new `MaskExtension` allows showing/hiding hex layers by geofence (e.g., only display hexes within a country boundary, or hide cells by threat level). Useful for UI polish.

- **Relevance:** LOW — Nice-to-have for UI polish, not critical  
- **Effort:** LOW — Requires updating H3HexagonLayer configuration  
- **Risk/Maturity:** PRODUCTION — deck.gl v9.1+ stable  
- **Type:** UI enhancement (additive)

**Recommendation:** Defer to Phase 2 unless UX testing shows filtering by influence is a key user workflow.

---

## Top 3 Recommendations

### 1. **Integrate Langfuse for Prompt Versioning** (Priority: HIGH, Start: Week 2)

**Why:** Parallax's eval framework relies on semver strings and manual prompt tracking. Langfuse provides production-grade version control, deployment labels, and rollback—exactly what the "prompt improvement pipeline" needs. This removes manual bookkeeping and enables safe A/B testing.

**Effort:** 2–3 days  
**Impact:** Safer prompt updates, faster A/B testing, team-ready (no more manual semver)  
**Cost:** Free (open-source) or $99/mo for managed hosting (negligible vs $20/day LLM budget)

---

### 2. **Integrate Batch API for Daily Eval Scorecard** (Priority: HIGH, Start: Week 3)

**Why:** The daily `compute_daily_scorecard()` cron job recomputes 15+ metrics using the same agent prompts repeatedly. Batching + caching saves 80% of eval tokens while increasing throughput. This reduces daily LLM cost from ~$0.35 to ~$0.08.

**Effort:** 1–2 days  
**Impact:** 75% cost reduction for eval work; complies with $20/day budget even with high activity  
**Cost:** Zero (Anthropic API)

---

### 3. **Plan DuckDB v2.0 Upgrade for Multi-Scenario Support** (Priority: MEDIUM, Start: Post-launch)

**Why:** DuckDB v2.0's async I/O (fall 2026) enables efficient multi-scenario support and long-term archive queries. This is not critical for Phase 1, but should be on the roadmap.

**Effort:** Low (passive upgrade)  
**Impact:** 10–50x faster replay and archive queries when Phase 2 scales to multiple simultaneous scenarios  
**Cost:** Zero

---

## Summary

**Significant findings:** 3 (Langfuse, Batch API, DuckDB v2.0 roadmap)  
**Nice-to-haves:** 2 (WorldMonitor, deck.gl MaskExtension)  
**Validation-only:** 2 (WebSocket patterns, Sonnet pricing stability)

**Parallax's current stack is well-designed and aligned with 2026 best practices.** The main opportunities are:
1. **Langfuse** for safer prompt versioning (directly implements the eval pipeline)
2. **Batch API** for lower eval costs (pure cost reduction)
3. **DuckDB v2.0** for future scaling (low-priority now, important later)
