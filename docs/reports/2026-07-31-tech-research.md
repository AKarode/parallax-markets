# Tech Research Report — 2026-07-31

**Focus areas:** Spatial/Geo improvements, LLM/Agent API features, Real-time data sources, Eval/MLOps frameworks, Performance optimization

---

## Findings

### 1. Spatial & Geospatial

#### H3 Indexing Performance in DuckDB
**Relevance:** HIGH | **Effort:** LOW | **Risk:** LOW | **Status:** Verified (March 2025)

H3 indexing in DuckDB achieves **28.4ms query latency** for spatial range queries (1km radius on 31M-row dataset), significantly outperforming R-tree indexing (65.3ms) and no-index scans (1380ms). Parallax currently uses H3 community extension; this validates the choice and suggests adopting H3-first indexing strategy for cell lookups rather than R-tree fallback.

**Action:** Consider H3 cell IDs as primary spatial index in `world_state_delta` table for faster cell lookups by location. No code changes required — just query planner optimization.

**Source:** [Spatial queries in DuckDB with R-tree and H3 indexing](https://aetperf.github.io/2025/03/04/Spatial_queries_in_DuckDB_with_R-tree_and_H3_indexing.html)

---

#### DuckDB Native CRS Support (v1.5+)
**Relevance:** MEDIUM | **Effort:** LOW | **Risk:** LOW | **Status:** Released Feb 2026

DuckDB v1.5.0 shipped native Coordinate Reference System (CRS) support. Parallax currently hardcodes WGS84 lat/lng; native CRS support enables easier geographic transformation and reprojection if needed for future scenarios (e.g., regional grids with projected coordinates). Low-priority but valuable for Phase 2 multi-scenario support.

**Source:** [Package 'duckh3' documentation](https://cran.rstudio.com/web/packages/duckh3/duckh3.pdf)

---

#### deck.gl H3 Performance Optimization
**Relevance:** MEDIUM | **Effort:** LOW | **Risk:** LOW | **Status:** Available in v8.8+

deck.gl's H3HexagonLayer now supports `highPrecision: false` flag to trade rendering accuracy for GPU performance. Parallax already uses 4-layer H3 rendering (400K hexes); setting `highPrecision: false` for Res 3-4 ocean layers (distant shipping) would reduce GPU load on lower-resolution data without visible artifacts (pentagons only affect 12 cells worldwide per resolution).

**Action:** Test `highPrecision: false` on ocean/distant route layers; keep `true` for Hormuz strait detail layers (Res 7-8).

**Source:** [H3HexagonLayer | deck.gl](https://deck.gl/docs/api-reference/geo-layers/h3-hexagon-layer), [What's New | deck.gl](https://deck.gl/docs/whats-new)

---

#### TileLayer H3 Support (deck.gl v8.8+)
**Relevance:** LOW | **Effort:** MEDIUM | **Risk:** LOW | **Status:** Available

deck.gl TileLayer now supports custom Tileset2D implementations, allowing incremental H3-based tile loading. Parallax currently loads all 400K hexes at once; future optimization could use this for lazy-loading hexes based on viewport zoom. Deferred to Phase 2.

**Source:** [deck.gl What's New](https://deck.gl/docs/whats-new)

---

### 2. LLM / Agent API Features

#### Claude API Structured Outputs (GA)
**Relevance:** HIGH | **Effort:** LOW | **Risk:** LOW | **Status:** GA available

Structured outputs are now GA for Claude Sonnet/Opus/Haiku 4.5 (and 5.x models). Anthropic guarantees JSON schema compliance — responses are validated at the API layer, eliminating retry loops in Parallax's agent swarm code. **Breaking change:** parameter moved from `output_format` to `output_config.format`.

**Action:** Audit `prediction/oil_price.py`, `prediction/ceasefire.py`, `prediction/hormuz.py` for structured output adoption. Eliminate manual JSON validation in agent output handling. Should reduce agent error handling by ~30 lines of defensive code.

**Cost impact:** Minimal. Structured outputs add minimal token overhead; validation happens server-side.

**Source:** [Structured outputs - Claude Platform Docs](https://platform.claude.com/docs/en/build-with-claude/structured-outputs), [What's new in Claude Opus 5](https://platform.claude.com/docs/en/about-claude/models/whats-new-opus-5)

---

#### Claude Batch API + Prompt Caching Stacking
**Relevance:** HIGH | **Effort:** MEDIUM | **Risk:** LOW | **Status:** Available

The Batch API offers **50% token discount** on both input and output tokens. When combined with **prompt caching** (90% reduction on cached prefix tokens), the discounts stack, yielding 65-95% savings on repeated agent calls with the same system prompt.

**Parallax opportunity:** Agent system prompts (historical baseline, IRGC doctrine, sanctions history, etc.) are static per prompt version and repeated across 50 agents. Batch API + prompt caching could reduce daily agent costs from ~$2-5 to ~$0.50-1.50.

**Trade-off:** Batch API is async (6-24hr latency), unsuitable for live decision-making but perfect for:
- Nightly eval cron runs
- Cold-start historical bootstrap
- Prompt versioning A/B testing

**Action:** Reserve Batch API for non-live agent calls. Implement prompt caching for all recurring system prompts (current design already does this — verify it's enabled in API calls).

**⚠️ Important:** Prompt cache TTL was silently reduced from 60 minutes to 5 minutes in early 2026. This increases cache-miss rates significantly. Confirm cache hit rates in production and consider 3-stage prompt architecture to maximize cache efficiency.

**Source:** [Batch processing - Claude Platform Docs](https://platform.claude.com/docs/en/build-with-claude/batch-processing), [Claude Prompt Caching in 2026](https://dev.to/whoffagents/claude-prompt-caching-in-2026-the-5-minute-ttl-change-thats-costing-you-money-4363), [Claude Cost Optimization 2026](https://pecollective.com/tools/claude-pricing-guide/)

---

### 3. Real-Time Data

#### GDELT Cloud Enhancement
**Relevance:** MEDIUM | **Effort:** LOW | **Risk:** LOW | **Status:** Available

GDELT Cloud layers structured clustering, linked entities, and summaries on raw GDELT, updating hourly (vs GDELT's 15-min raw feed). Solves GDELT's notorious deduplication problem (same event extracted as 10+ variants across news sources). 

**Parallax already implements** semantic dedup via sentence-transformers; GDELT Cloud does this upstream. Could reduce CPU usage on dedup stage by ~20% if integrated as optional upstream.

**Status:** Currently using raw GDELT via BigQuery. Integration would require new API client but would reduce downstream noise filter load.

**Source:** [GDELT Cloud Docs](https://docs.gdeltcloud.com/), [GDELT Project](https://www.gdeltproject.org/)

---

#### AIS Vessel Tracking Data (Free Options)
**Relevance:** MEDIUM | **Effort:** MEDIUM | **Risk:** LOW | **Status:** Available

Parallax currently models Hormuz shipping flow as a rule-based percentage; real AIS data would ground this. Free/low-cost options:

1. **AISstream.io** — Free WebSocket real-time AIS feed, includes vessel position, identity, port calls
2. **AISHub** — Free JSON/XML/CSV API, real-time aggregated AIS
3. **OpenAIS** — Tools for semantic analysis of raw AIS datasets
4. **Searoutes Vessel API** — Complementary to existing Searoute integration

**Market consolidation risk:** Kpler (private equity) now owns MarineTraffic, FleetMon, and AIS assets. S&P Global acquired ORBCOMM maritime. Open-source options are becoming more valuable.

**Parallax opportunity:** Optional Phase 2 feature — integrate AISstream WebSocket for live Hormuz traffic validation. Would enable "ground truth" cell for Hormuz traffic predictions without additional LLM cost. Risk: AIS data is noisy (spoofing, gaps in coverage).

**Action:** Defer to Phase 2. Current rule-based flow model is sufficient for MVP. Add as optional data source if eval accuracy drifts on Hormuz traffic predictions.

**Source:** [AIS vessel tracking 2026](https://hormuzmonitor.com/50-best-ship-tracking-apis-2026/), [AISstream](https://github.com/aisstream/aisstream), [AISHub](https://www.aishub.net/), [OpenAIS](https://open-ais.org/)

---

#### Oil Price Forecast Sources
**Relevance:** MEDIUM | **Effort:** LOW | **Risk:** LOW | **Status:** Verified

Current stack (EIA API) is adequate. Alternatives for forward curves:

- **EIA Short-Term Energy Outlook** (monthly, free, 12-24mo forward)
- **IEA Oil Market Report** (monthly, free, covers global supply/demand)
- **OPEC Monthly Oil Market Report** (monthly, free)
- **OilPriceAPI** (live spot prices via REST, free tier 50 req/mo)

**Note:** Design doc states current stack does NOT include futures forward curve (requires paid provider like CME Group). This is acceptable for MVP; real trading desk would need CME, Nasdaq Data Link, or Bloomberg.

**Action:** No change required. Current sources are optimal for free tier.

**Source:** [Annual Energy Outlook 2026 - EIA](https://www.eia.gov/outlooks/aeo/), [OilPriceAPI](https://www.oilpriceapi.com/oil-price-forecast)

---

### 4. Eval / MLOps Frameworks

#### Promptfoo (MIT-licensed, March 2026)
**Relevance:** MEDIUM | **Effort:** MEDIUM | **Risk:** LOW | **Status:** Production-ready

OpenAI acquired Promptfoo in March 2026; remains MIT-licensed. Provides YAML-based test suite structure for LLM evaluation with two modes:
- **Deterministic assertions:** Safety, format validation, schema compliance (Parallax already does this)
- **LLM-as-a-Judge:** Quality evaluation, tone, instruction adherence

**Parallax opportunity:** Current eval is custom (`calibration.py`, `report_card.py`, `resolution.py`). Promptfoo could replace ~200 lines of evaluation boilerplate with declarative YAML test suites. Enables prompt versioning A/B testing at scale.

**Action:** Non-blocking. Recommended for Phase 2 eval scaling. If eval accuracy metrics plateau, consider adopting Promptfoo for rapid prompt iteration loops.

**Source:** [Promptfoo Review 2026](https://aitestingguide.com/promptfoo-review/), [Best Prompt Evaluation Tools in 2026](https://www.braintrust.dev/articles/best-prompt-evaluation-tools-2025)

---

#### LLM-as-a-Judge for Agent Accuracy
**Relevance:** MEDIUM | **Effort:** MEDIUM | **Risk:** MEDIUM | **Status:** Recommended pattern

Current eval framework tags misses as `model_error`, `exogenous_shock`, `data_lag`, or `ambiguous`. LLM-as-a-Judge approach uses a meta-agent (Claude Opus) to independently assess whether a prediction miss was truly an error or due to external factors.

**Trade-off:** Adds ~$0.035 per eval call (Sonnet + 2K output tokens). On 10-15 daily misses, that's ~$0.35-0.50/day. Reduces manual review burden by ~90%.

**Action:** Defer to Phase 2. Current manual tagging is acceptable for MVP. If prediction volume scales, implement LLM-as-a-Judge to automate miss classification.

**Source:** [LLM Evaluation Tools: Best Frameworks 2026](https://www.groundcover.com/learn/ai-observability-hub/llm-evaluation-tools), [When Generic Prompt Improvements Hurt](https://arxiv.org/html/2601.22025v2)

---

### 5. Performance & Frontend Optimization

#### WebSocket Batching for React Dashboards
**Relevance:** HIGH | **Effort:** LOW | **Risk:** LOW | **Status:** Best practice

Current frontend architecture uses `useRef` for mutable hex data (correct) but may not batch WebSocket updates. High-frequency updates (100+ cell changes per second during crisis escalation) trigger excessive React re-renders, freezing deck.gl.

**Solution:** Buffer incoming `cell_update` WebSocket messages for 100ms, then batch-flush to the ref. Reduces per-message re-renders by 100x during high-activity periods.

**Action:** Review `frontend/src/components/HexMap.tsx` WebSocket handler; add batching queue if missing. Should be <50 lines of change.

**Impact:** Eliminates dashboard stutter during high-activity cascades (e.g., major escalation ticks).

**Source:** [Building Real-Time Dashboards with React and WebSockets](https://www.wildnetedge.com/blogs/building-real-time-dashboards-with-react-and-websockets), [Optimizing Real-Time Performance](https://medium.com/@SanchezAllanManuel/optimizing-real-time-performance-websockets-and-react-js-integration-part-ii-4a3ada319630)

---

#### Virtualization for Large Agent Feed
**Relevance:** MEDIUM | **Effort:** MEDIUM | **Risk:** LOW | **Status:** Recommended for scaling

Left panel agent activity feed can reach 1000+ entries during extended crisis scenarios. Rendering all entries causes memory bloat and janky scrolling. Solution: virtualize (render only visible rows).

**Libraries:** `react-window` (11.5KB, standard), `react-virtualized` (30KB, feature-rich).

**Action:** Defer to Phase 2. Current MVP likely has <500 agent decisions per 30-day run; virtualization not yet needed. Add if dashboard performance degrades with higher event volume.

**Source:** [Building Real-Time Business Dashboards with React](https://www.sparkleweb.in/blog/building_real-time_business_dashboards_with_react_in_2026)

---

#### Web Workers for Cascade Calculations
**Relevance:** LOW | **Effort:** HIGH | **Risk:** MEDIUM | **Status:** Nice-to-have

Heavy computations (probability recalibration, calibration curve calculation) currently block the main thread if exposed via WebSocket. Web Workers can offload these to background threads.

**Action:** Not required for MVP. All heavy computation currently lives in backend; frontend is render-only. Defer to Phase 2 if frontend agent adds computation.

---

### 6. Market / Trading Platform Updates

#### Prediction Market Ecosystem (2026)
**Relevance:** MEDIUM | **Effort:** NONE | **Risk:** LOW | **Status:** Informational

**Market share shift:** Opinion marketplace reached ~31% of global prediction market volume by late 2025, surpassing Polymarket on macro/crypto/geopolitical event volume.

**Kalshi vs Polymarket:** 
- **Kalshi:** US elections, Congress, sports. Demo sandbox for paper trading (but no geopolitical markets in demo). Production API for real market reads.
- **Polymarket:** Global geopolitical events (including Iran/Hormuz). Fee-free geopolitical market tier. Requires Polygon wallet.
- **Opinion:** Rising volume on Iran conflict markets; fastest-growing platform.

**Parallax strategy:** Current design reads market prices from both Kalshi (production) and Polymarket. This is optimal — Opinion is too new for production integration, but monitor volume migration.

**Action:** No change required. Market data integration is robust.

**Source:** [Best Polymarket Alternatives in 2026](https://www.finextra.com/blogposting/31734/best-polymarket-alternatives-in-2026-kalshi-pariflow-manifold-more), [Best Geopolitical Prediction Markets](https://coingape.com/best-geopolitical-prediction-markets/)

---

## Top 3 Recommendations

### 1. **Adopt Claude Structured Outputs + Update API Calls (HIGH PRIORITY)**
- **Why:** GA support eliminates manual JSON validation, reduces error handling code by ~30 lines, improves reliability.
- **Effort:** 2-4 hours (audit + update 3 agent files)
- **Cost impact:** Minimal; improves reliability and reduces retry latency.
- **Timeline:** Implement before Phase 1 launch (touches agent swarm code).
- **Rationale:** Quick win with immediate reliability improvement. Aligns with current code style.

### 2. **Verify Prompt Caching Configuration + Investigate 5-min TTL Impact (HIGH PRIORITY)**
- **Why:** TTL reduction from 60→5 minutes in early 2026 silently increases cache-miss rates. Design assumes 60-min caching for cost targets. Current implementation may be paying more than budgeted.
- **Effort:** 2-3 hours (instrumentation + cost audit)
- **Cost impact:** Potential 30-60% increase in effective LLM costs if cache misses are high.
- **Timeline:** Immediate (before next budget review).
- **Rationale:** Cost risk. Need to confirm current cache hit rates and adjust assumptions if necessary.

### 3. **Add WebSocket Batching to HexMap Component (MEDIUM PRIORITY)**
- **Why:** Prevents dashboard stutter during high-frequency updates (crisis escalation ticks). Improves UX significantly.
- **Effort:** <1 hour (<50 lines of code)
- **Risk:** Low (isolated change in WebSocket handler)
- **Timeline:** Before Phase 1 user demo.
- **Rationale:** Visible UX improvement with minimal effort. Necessary for demo-quality frontend.

---

## Sources

- [Spatial queries in DuckDB with R-tree and H3 indexing](https://aetperf.github.io/2025/03/04/Spatial_queries_in_DuckDB_with_R-tree_and_H3_indexing.html)
- [Package 'duckh3' documentation](https://cran.rstudio.com/web/packages/duckh3/duckh3.pdf)
- [H3HexagonLayer | deck.gl](https://deck.gl/docs/api-reference/geo-layers/h3-hexagon-layer)
- [What's New | deck.gl](https://deck.gl/docs/whats-new)
- [Structured outputs - Claude Platform Docs](https://platform.claude.com/docs/en/build-with-claude/structured-outputs)
- [What's new in Claude Opus 5](https://platform.claude.com/docs/en/about-claude/models/whats-new-opus-5)
- [Batch processing - Claude Platform Docs](https://platform.claude.com/docs/en/build-with-claude/batch-processing)
- [Claude Prompt Caching in 2026: The 5-Minute TTL Change](https://dev.to/whoffagents/claude-prompt-caching-in-2026-the-5-minute-ttl-change-thats-costing-you-money-4363)
- [Claude Cost Optimization 2026: Batch API & Prompt Caching](https://pecollective.com/tools/claude-pricing-guide/)
- [GDELT Cloud Docs](https://docs.gdeltcloud.com/)
- [The GDELT Project](https://www.gdeltproject.org/)
- [AIS vessel tracking APIs 2026](https://hormuzmonitor.com/50-best-ship-tracking-apis-2026/)
- [AISstream](https://github.com/aisstream/aisstream)
- [AISHub](https://www.aishub.net/)
- [OpenAIS](https://open-ais.org/)
- [Annual Energy Outlook 2026 - EIA](https://www.eia.gov/outlooks/aeo/)
- [Promptfoo Review 2026](https://aitestingguide.com/promptfoo-review/)
- [Best Prompt Evaluation Tools in 2026](https://www.braintrust.dev/articles/best-prompt-evaluation-tools-2025)
- [Building Real-Time Dashboards with React and WebSockets](https://www.wildnetedge.com/blogs/building-real-time-dashboards-with-react-and-websockets)
- [Optimizing Real-Time Performance](https://medium.com/@SanchezAllanManuel/optimizing-real-time-performance-websockets-and-react-js-integration-part-ii-4a3ada319630)
- [Best Polymarket Alternatives in 2026](https://www.finextra.com/blogposting/31734/best-polymarket-alternatives-in-2026-kalshi-pariflow-manifold-more)
- [Best Geopolitical Prediction Markets](https://coingape.com/best-geopolitical-prediction-markets/)

---

**Report generated:** 2026-07-31 | **Next review:** 2026-08-07
