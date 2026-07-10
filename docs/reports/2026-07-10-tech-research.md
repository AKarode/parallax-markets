# Tech Research Report: Parallax Stack Improvements (2026-07-10)

**Date:** July 10, 2026  
**Scope:** Spatial/Geo, LLM/Agent APIs, Real-time Data Sources, Eval/MLOps, Frontend Performance

---

## Executive Summary

Parallax's current tech stack remains solid, but three significant improvements have emerged this quarter:

1. **Claude Sonnet 5** (released June 30, 2026) offers superior agentic capabilities but introduces breaking API changes and tokenizer updates that increase token counts up to 35%.
2. **Prompt caching + Batch API stacking** can now deliver up to 90% + 50% cost savings, directly lowering Parallax's $20/day budget ceiling.
3. **AISstream.io** provides free, real-time WebSocket AIS data as a high-value supplement to existing shipping data sources.

---

## Findings by Category

### 1. LLM / Agent APIs — HIGH PRIORITY

#### Claude Sonnet 5 (Released June 30, 2026)

**Relevance:** HIGH — Potential to replace Sonnet 4.6 for country-agent decisions.  
**Effort:** MEDIUM — Breaking API changes require careful migration.  
**Risk:** MEDIUM — New tokenizer increases token counts up to 35%.

**What's new:**
- Superior instruction following, tool selection, and error correction for autonomous workflows.
- Computer use capabilities excel in browser-based tasks.
- SWE-bench Pro: 63.2% (vs Opus 4.8: 69.2%), edges past Opus on knowledge work.
- **Breaking changes**: New tokenizer (token counts up +35%), three hard-fail API changes for existing code.
- **Pricing** (introductory through Aug 31, 2026): $2/M input tokens, $10/M output tokens (then $3/$15).

**Assessment:**
Sonnet 5's agentic improvements (better tool selection, error recovery) map well to Parallax sub-actor decision-making and conflict resolution. However, the tokenizer update means existing cost estimates need recalibration. **Recommendation: Test migration in parallel track before full cutover.** Recalculate budget impact: if tokens increase 35%, sub-actor cost goes from ~$0.002 to ~$0.003/call, country agent from ~$0.025 to ~$0.034/call. New daily estimate: ~$3-7/day (still under $20 budget). The agentic improvements are worth the migration effort once tokenizer adjustment is factored in.

**Sources:**
- [Anthropic Claude Sonnet 5](https://www.anthropic.com/news/claude-sonnet-5)
- [Claude Sonnet 5 Developer Guide](https://www.developersdigest.tech/blog/claude-sonnet-5-developer-guide-2026)

---

#### Prompt Caching + Batch API Stacking

**Relevance:** HIGH — Direct cost reduction on daily LLM budget.  
**Effort:** LOW — Already implemented for system prompts; extend to batch workflows.  
**Risk:** LOW — Feature-complete and stable.

**What's new:**
- Prompt caching now uses workspace-level isolation (not organization-level).
- Batch API supports prompt caching; **the two discounts stack**: 90% off cached input tokens + 50% off all tokens via Batch API.
- Cache TTL: 5 minutes for real-time, 1 hour for batch processing.
- Typical cache hit rates: 30–98% depending on traffic pattern.

**Assessment:**
Parallax already uses prompt caching for agent system prompts (historical baseline). The new capability is to **stack Batch API savings on top**: run non-urgent prediction updates (eval meta-agent calls, prompt refinement suggestions) via Batch API with full prompt caching. **Recommendation: Implement batch runner for daily eval cron jobs (currently ~10 calls/day @ $0.035 each).** Batching these with caching could reduce $0.35/day eval cost to ~$0.07/day. Overall daily savings: ~$0.30/day → $9/month or $108/year.

**Sources:**
- [Batch Processing - Claude Platform Docs](https://platform.claude.com/docs/en/build-with-claude/batch-processing)
- [Prompt Caching - Claude Platform Docs](https://platform.claude.com/docs/en/build-with-claude/prompt-caching)
- [Claude Cost Optimization 2026](https://pecollective.com/tools/claude-pricing-guide/)

---

### 2. Real-time Data Sources — MEDIUM PRIORITY

#### AISstream.io: Free WebSocket AIS Data

**Relevance:** MEDIUM — Supplements current Hormuz vessel tracking. Valuable for demos without API cost.  
**Effort:** LOW — Drop-in WebSocket consumer in addition to existing ingestion.  
**Risk:** LOW — Free tier, no SLA. Use alongside paid provider (MarineTraffic/Kpler).

**What's new:**
- Free, real-time WebSocket API for AIS vessel positions.
- Subscribe to bounding boxes, receive live AIS messages as vessels broadcast them.
- No authentication required; best-effort coverage.

**Assessment:**
Parallax currently has no live vessel tracking in the data ingestion pipeline. AISstream.io provides a **zero-cost supplement** for dashboard visualization and scenario demos. Subscribe to Hormuz, Gulf of Oman, and Cape of Good Hope bounding boxes; merge with GDELT shipping incident reports for richer context. **Recommendation: Integrate as optional data source for visualization layer only.** Do not rely on it for critical trading signals (no SLA), but perfect for "show live traffic patterns" in demos and interviews.

**Sources:**
- [50 Best Ship Tracking APIs 2026 - Strait of Hormuz](https://hormuzmonitor.com/50-best-ship-tracking-apis-2026/)
- [MarineTraffic API Alternatives](https://datadocked.com/marinetraffic-api-alternative)

---

#### GDELT Cloud: ML-Enhanced Event Classification

**Relevance:** MEDIUM — Potential to improve event filtering accuracy over raw GDELT.  
**Effort:** MEDIUM — Would replace raw GDELT → curated_events pipeline.  
**Risk:** MEDIUM — Proprietary layer on top of GDELT; cost vs. benefit analysis needed.

**What's new:**
- Adds machine layer to raw GDELT: pre-classified events, clustered stories, linked entities, quantified signals.
- Replaces the semantic dedup + relevance scoring stage (currently done in-house with sentence-transformers).

**Assessment:**
GDELT Cloud's pre-classification could save ~50ms/event in local ML inference (all-MiniLM-L6-v2 embeddings). However, it's unclear whether pre-canned classifications are better than custom Parallax-trained scoring. **Recommendation: Defer to Phase 2.** In Phase 1, continue with local filtering (cost: ~$0 beyond data, vs. GDELT Cloud licensing unknown). Revisit if noise filtering becomes a bottleneck.

**Sources:**
- [GDELT Cloud](https://gdeltcloud.com/)
- [GDELT Project](https://www.gdeltproject.org/)

---

#### Oil Price APIs: WebSocket Streaming Alternative

**Relevance:** MEDIUM — EIA + FRED are already in stack; WebSocket alternatives offer real-time intra-day prices.  
**Effort:** LOW — Additional consumer alongside existing EIA batch ingestion.  
**Risk:** LOW — Use as reference only; do not depend for trading signals.

**What's new:**
- OilPriceAPI and Alpha Vantage now offer WebSocket streaming for Brent/WTI.
- Real-time ticks vs. EIA's daily snapshot.

**Assessment:**
Current pipeline ingests EIA daily prices only. **Recommendation: Add WebSocket consumer for real-time Brent/WTI for dashboard sparklines and intra-day monitoring**, but continue using EIA daily for prediction model inputs (consistency with eval historical data). This is a **visualization enhancement, not a modeling improvement**. Estimated cost: ~$0–5/month for dev tier.

**Sources:**
- [OilPriceAPI Alternatives](https://www.oilpriceapi.com/vs)
- [EIA Petroleum Data](https://www.eia.gov/petroleum/data.php)

---

### 3. Spatial / Geo Visualization — LOW-MEDIUM PRIORITY

#### deck.gl H3HexagonLayer: High-Performance Mode

**Relevance:** LOW-MEDIUM — Dashboard already renders smoothly; optimization opportunity if scaling to finer resolution.  
**Effort:** LOW — Single-line config change: `highPrecision: false`.  
**Risk:** LOW — Opt-in trade-off: faster rendering at cost of accuracy on pentagon cells near pole.

**What's new:**
- `highPrecision: false` forces lower-precision, high-performance rendering.
- Assumes all hexes in viewport have same shape as center hex (valid assumption for res 5–8 in Hormuz region).
- Automatic fallback to high-precision when needed (pentagons, edge cases).

**Assessment:**
Parallax dashboard renders ~400K hexes across 4 resolution bands with smooth 600ms GPU transitions. If future scenarios add finer resolution (res 9 for infrastructure detail), `highPrecision: false` is a low-risk optimization. **Recommendation: Document as Phase 2 scaling option.** Not urgent for current Hormuz scenario.

**Sources:**
- [H3HexagonLayer - deck.gl Docs](https://deck.gl/docs/api-reference/geo-layers/h3-hexagon-layer)
- [deck.gl What's New](https://deck.gl/docs/whats-new)

---

#### DuckDB Spatial Extension: Native 2D Geometry Types

**Relevance:** LOW — Currently using H3 cells + JSON attributes. Native geometry could improve performance in Phase 2.  
**Effort:** MEDIUM — Would require schema migration.  
**Risk:** MEDIUM — 2D types are marked experimental.

**What's new:**
- `POINT_2D`, `LINESTRING_2D`, `POLYGON_2D`, `BOX_2D` native types with fixed memory layout.
- Theoretically enable faster geospatial algorithms vs. nested struct representation.

**Assessment:**
Current Parallax design stores cell state as `(cell_id, JSON attributes)`. Migrating to `LINESTRING_2D` for shipping routes or `POLYGON_2D` for regional boundaries could improve query speed, but requires careful benchmarking. The 2D types are still experimental and may lack some spatial functions. **Recommendation: Defer to Phase 2 optimization pass.** Profile first to confirm bottleneck before investing migration effort.

**Sources:**
- [DuckDB Spatial Overview](https://duckdb.org/docs/lts/core_extensions/spatial/overview)
- [Awesome DuckDB Spatial](https://github.com/alperdincer/Awesome-DuckDB-Spatial)

---

### 4. Eval / MLOps — MEDIUM PRIORITY

#### Langfuse: Open-Source LLM Observability + Prompt Versioning

**Relevance:** MEDIUM — Aligns with Parallax eval framework design: per-version tracking, production traces, dataset regression testing.  
**Effort:** MEDIUM — Replaces custom `agent_prompts` + `eval_results` query layer with Langfuse SDK.  
**Risk:** LOW — Open-source; runs self-hosted or via Langfuse Cloud.

**What's new:**
- Every production trace links to exact prompt version, model config, and dataset.
- Prompt deployment tracking with version management.
- Dataset regression testing: run eval suite against old + new prompts automatically.
- LLM-as-judge scoring on production traces (built-in).

**Assessment:**
Parallax's eval design already includes prompt versioning (semver, per-prediction tags), but manually tracks via `agent_prompts` + `eval_results` tables. Langfuse would **automate the trace→version→score pipeline**, reducing engineering overhead for the prompt improvement cron. **Recommendation: Evaluate for Phase 2 if manual prompt ops becomes bottleneck.** For Phase 1, current approach is sufficient. If adopted, integrate Langfuse SDK into prediction logging (minimal changes to async/await flow).

**Sources:**
- [Langfuse LLM Observability](https://www.braintrust.dev/articles/best-prompt-versioning-tools-2025)
- [LLMOps Architecture 2026](https://calmops.com/architecture/llmops-architecture-managing-llm-production-2026/)

---

#### Calibration & Confidence Scoring: Scale AI's 2026 Finding

**Relevance:** HIGH — Directly impacts Parallax eval scoring accuracy.  
**Effort:** LOW — Awareness item; add calibration check to eval cron.  
**Risk:** LOW — Reference for improving eval methodology, not a new tool.

**What's new:**
- Scale AI leaderboard reports systematic high calibration errors across all 2026 models.
- ECE (Expected Calibration Error): models express high confidence on answers they get wrong.
- Implication: Parallax's confidence scores (0.0–1.0 per agent prediction) may not align with actual accuracy.

**Assessment:**
Parallax's eval framework tracks calibration over 30-day rolling windows (Section 7 of design spec). **Recommendation: Add explicit calibration plots to daily scorecard.** Compute ECE for each agent; flag if model's 0.8-confidence predictions are actually right only ~60% of the time. This feeds directly into prompt improvement pipeline: if an agent is overconfident, note it as a refinement signal. **Action: Add ECE calculation to `scoring/calibration.py`**.

**Sources:**
- [LLM Evaluation Metrics 2026](https://www.genaimlinstitute.com/blog/llm-evaluation-metrics)
- [LLM Evaluation Frameworks 2026](https://gogloby.com/insights/llm-evaluation/)

---

### 5. Frontend Performance — LOW PRIORITY

#### React 18 Concurrent Features + Batching Pattern

**Relevance:** LOW — Dashboard already uses `useRef` for mutable hex data (prevents thrash). Further optimizations are marginal.  
**Effort:** LOW — React 18 is current version; no migration needed.  
**Risk:** LOW — Marginal gains for current hex count.

**What's new:**
- React 18 concurrent features allow UI to stay responsive during high-frequency data bursts.
- Batching updates (current Parallax design: "buffer for 100ms, flush") is industry-standard.
- Virtualization + Web Workers for heavy calculations.

**Assessment:**
Parallax design **already implements the right pattern**: `useRef` for mutable hex data, batch updates at 100ms cadence. Further optimization (virtualization for agent feed, Web Workers for cell scoring) are not urgent unless dashboard exhibits lag with >50 concurrent users. **Recommendation: Profile first before optimizing.** Monitor WebSocket message throughput and React component render time; optimize if either becomes bottleneck.

**Sources:**
- [React WebSocket Real-time Dashboard Optimization 2026](https://openwebsolutions.in/blog/high-performance-trading-dashboard-react-websockets/)
- [Building Real-Time Dashboards with React 2026](https://www.sparkleweb.in/blog/building_real-time_business_dashboards_with_react_in_2026)

---

## Top 3 Recommendations (Prioritized by Impact × Feasibility)

### 1. **Migrate Claude API calls to Sonnet 5 with Batch API stacking** (Phase 1, Sprint 2)

**Why:** Combines two high-impact improvements:
- Sonnet 5's agentic capabilities improve agent reasoning.
- Batch API + caching stacking reduces daily cost by ~$0.30 (3–5% of budget).

**Effort:** 1–2 sprints (parallel testing track; gradual cutover).  
**Blocker:** Recalibrate tokenizer impact; validate decision quality on holdout eval set.

---

### 2. **Add AISstream.io WebSocket consumer for live vessel tracking visualization** (Phase 1, Sprint 3)

**Why:** Free, high-value data source for demos and dashboard realism.
- Subscribers to Hormuz + Gulf of Oman + Cape reroute cells.
- Merge with GDELT incident reports for richer context.
- Zero cost; opt-in for visualization only.

**Effort:** 2–3 days (new ingestion pipeline + WebSocket handler).  
**Blocker:** None (non-critical path).

---

### 3. **Add ECE (Expected Calibration Error) metric to daily scorecard** (Phase 1, ongoing)

**Why:** Identifies systematic overconfidence in agent predictions.
- Feeds directly into prompt improvement cron (Flag: "Agent X is overconfident").
- Aligns with 2026 industry finding about model calibration.

**Effort:** 1 day (add ECE calculation to `scoring/calibration.py`).  
**Blocker:** None.

---

## Technologies NOT Recommended (Phase 1)

| Technology | Reason |
|-----------|--------|
| GDELT Cloud | Proprietary layer on GDELT; unclear ROI. Revisit Phase 2 if noise filtering becomes bottleneck. |
| DuckDB Native 2D Geometry | Experimental; migration cost not justified unless spatial queries are performance bottleneck (unlikely). |
| Langfuse (full integration) | Adds operational complexity. Current `agent_prompts` + `eval_results` approach is sufficient. Consider Phase 2 if manual ops scale. |
| Paid AIS (Datalastic/MarineTraffic) | Free AISstream.io covers demo needs. Escalate to paid only if trading-signal quality requires enterprise SLA. |

---

## Links to Key Resources

**Claude API & Cost Optimization:**
- [Batch Processing Docs](https://platform.claude.com/docs/en/build-with-claude/batch-processing)
- [Prompt Caching Docs](https://platform.claude.com/docs/en/build-with-claude/prompt-caching)
- [Claude Sonnet 5 Announcement](https://www.anthropic.com/news/claude-sonnet-5)

**Real-time Data:**
- [AISstream.io](https://aismarine.org/) (via GitHub: AIS-tracks/aismarine)
- [OilPriceAPI WebSocket Docs](https://docs.oilpriceapi.com/)

**Spatial:**
- [deck.gl H3HexagonLayer Docs](https://deck.gl/docs/api-reference/geo-layers/h3-hexagon-layer)
- [DuckDB Spatial Docs](https://duckdb.org/docs/lts/core_extensions/spatial/overview)

**Eval/MLOps:**
- [Langfuse](https://www.braintrust.dev/articles/best-prompt-versioning-tools-2025)
- [Scale AI Calibration Report](https://www.genaimlinstitute.com/blog/llm-evaluation-metrics)

---

**Report generated:** July 10, 2026  
**Next review:** July 31, 2026 (post-Phase 1 launch)
