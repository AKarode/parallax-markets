# 2026-09-17 Technology Research Report — Parallax Stack

**Focus Areas:** Spatial/Geo, LLM/Agent, Real-time Data, Eval/MLOps, Performance

---

## 1. SPATIAL/GEOSPATIAL

### ⭐ DuckDB Spatial Extension – Native GEOMETRY Type
- **What**: Built-in GEOMETRY type (DuckDB v1.5, March 2026). Over 100 ST_* functions (ST_Distance, ST_Intersection, ST_Contains) + R-tree indexing
- **Release**: v1.5 (March 2026)
- **Relevance**: HIGH — Core to world state and cascade engine spatial calculations
- **Integration Effort**: 2-3 days (refactor cell queries to use ST_* functions)
- **Maturity**: STABLE
- **Assessment**: Geometry compression 3-10x vs JSON. GDAL/GEOS bundled (no external deps). Faster spatial joins than Shapely for H3 polygon operations. Direct upgrade path from current approach.

### H3 SIMD-Accelerated Fork (mattsta/h3, April 2026)
- **What**: Community fork with SIMD-accelerated bulk APIs, ~2-3x faster on vectorized operations
- **Release**: April 2026 (active maintenance)
- **Relevance**: MEDIUM — Improves chokepoint zone queries and hexagon aggregation
- **Integration Effort**: 4-8 hours (swap h3 package, benchmark cell coverage)
- **Maturity**: PRODUCTION — Community adoption growing; maintainer active
- **Assessment**: Relevant if Hormuz zone coverage scales. Good fallback if mattsta fork maturity concerns arise; main h3-js v4.x is slower but official.

### deck.gl v9.4 + WebGPU Integration (September 2026)
- **What**: WebGPU support across all layers, new @deck.gl/maplibre module for MapLibre integration, MultiViewLayout for responsive dashboards
- **Release**: v9.4 (September 5, 2026)
- **Relevance**: MEDIUM — Frontend visualization performance, multi-layer overlays, responsive layout
- **Integration Effort**: 1 week (add @deck.gl/maplibre module, test WebGPU on tile layers)
- **Maturity**: STABLE
- **Assessment**: WebGPU enables faster shipping route animations and MapLibre basemap + deck.gl overlays seamlessly. MultiViewLayout helps responsive design for mobile future. Current design is single-view; marginal benefit today.

### MapLibre GL v6 (July 2026)
- **What**: Latest stable release; FFI engine improvements for iOS/Android; skip pre-release MLT tile format (no server support until 2027)
- **Release**: July 2026
- **Relevance**: MEDIUM — Dashboard rendering and map performance
- **Integration Effort**: 1-2 weeks (test v6 compatibility; skip MLT)
- **Maturity**: STABLE
- **Assessment**: Drop-in upgrade from v4/v5. Battle-tested. MLT format not worth integrating now; 2027+ when tile servers support it.

---

## 2. LLM & AGENT

### ⭐ Claude Prompt Caching (GA, 90% Cost Reduction)
- **What**: Cache writes cost 125% of base input tokens, cache reads cost 10%. System prompts + prediction templates are reused across runs
- **Release**: GA (December 2024)
- **Relevance**: HIGH — Directly addresses $20/day LLM budget constraint
- **Integration Effort**: 1-2 days (mark system prompts with `cache_control` parameter)
- **Maturity**: STABLE
- **Assessment**: ⭐ IMMEDIATE WIN. Parallax runs 3 prediction cycles/day with 50 agents. System prompt (news summary, entity list) + prediction template reused → 60-90% input cost reduction. Cache headers are transparent to logic. Free upgrade with latest Anthropic SDK.

### ⭐ Claude Structured Outputs (GA, All Models)
- **What**: Guaranteed JSON schema compliance at generation time (not parsing time). All Claude models: Haiku, Sonnet, Opus 4.5+
- **Release**: GA (December 2025)
- **Relevance**: HIGH — Replace cascade output parsing, guarantee valid prediction JSON
- **Integration Effort**: 2-3 days (Pydantic schema for PredictionOutput, refactor brief.py)
- **Maturity**: STABLE
- **Assessment**: Eliminates `json.loads()` errors in cascade reasoning. First-request grammar cache overhead ~100-300ms (cached 24h). Saves ~1-2% input tokens. Worth immediate integration.

### Claude Opus 5 (January 2025) — Enhanced Reasoning
- **What**: Improved extended reasoning for complex multi-step geopolitical analysis
- **Release**: January 2025
- **Relevance**: MEDIUM — Country agents currently use Sonnet; Opus could improve calibration
- **Integration Effort**: EASY — Drop-in model swap, monitor cost/latency
- **Maturity**: STABLE
- **Assessment**: Cost ~2x Sonnet. Use for country-agent level decisions only (high-impact predictions). A/B test: run 10 country agents on Opus vs Sonnet for 1 week, compare calibration scores. Only upgrade if accuracy improves >5%.

### First-Party Agent SDKs (Anthropic SDK v0.52+)
- **What**: Native tool loops, session state, structured outputs in one API
- **Release**: Stable (2025)
- **Relevance**: MEDIUM — Consider if cascade engine becomes multi-turn agentic
- **Integration Effort**: 2-3 weeks (migrate to Anthropic agents API)
- **Maturity**: STABLE
- **Assessment**: Only relevant if cascade reasoning becomes truly agentic (iterative refinement). Today's one-shot architecture doesn't need it. Phase 2 consideration.

---

## 3. REAL-TIME DATA

### ⭐ Claude Prompt Caching for Data Feeds (Reuse + Cost Savings)
- **What**: Cache market data, historical news summaries across prediction runs
- **Relevance**: HIGH — Amplifies caching benefit for data ingestion
- **Effort**: 1 day (mark data templates for caching)
- **Assessment**: If GDELT summaries or market snapshots are cached, every agent call hits 10% read cost instead of parsing new data.

### Kpler / MarineTraffic (AIS Shipping Data)
- **What**: 13K AIS receivers globally, 2-3min latency, covers Hormuz Strait. Kpler acquired MarineTraffic Dec 2023; integrated 2024-2025
- **Release**: Production
- **Relevance**: HIGH — Hormuz chokepoint shipping visibility as proxy for blockade threat
- **Integration Effort**: 1-2 weeks (API integration, cascade rule for shipping flow)
- **Maturity**: STABLE
- **Assessment**: Shipping delays/rerouting before news hits = edge signal. Expensive: >$5K/month for Hormuz zone. Check AISHub (free, 15-30min lag) or Datalastic (cheaper, documented) first. Real-time vessel counts beat agent predictions on this metric.

### Global Geopolitical Events Database (Tsinghua, 2024)
- **What**: Bilateral alignment scores for all 18,528 UN dyads, 1950-2024. Released 2025.
- **Release**: 2025
- **Relevance**: MEDIUM — Supplement GDELT with academic-grounded bilateral relationship risk
- **Integration Effort**: 3-5 days (ingest dataset, join with cascades on country pairs)
- **Maturity**: STABLE
- **Assessment**: Structural baseline complements event-centric GDELT. Useful for Iran-Saudi, Iran-US pair scoring. Stable historical context.

### ACLED + UCDP (Backup to GDELT)
- **What**: ACLED (armed conflict events, daily/real-time), UCDP (authenticated free API). Complement GDELT's rate-limiting and coverage gaps
- **Release**: Stable
- **Relevance**: MEDIUM — Reduce GDELT 429 rate-limit dependency
- **Integration Effort**: 1 week (add UCDP API poller + ACLED RSS, deduplicate with GDELT)
- **Maturity**: STABLE
- **Assessment**: Both slower than GDELT (daily/weekly vs real-time) but reliable. Useful for night-time coverage when Google News is stale and GDELT lags.

### EIA API Stability Check
- **What**: Validate EIA API endpoint stability, backfill 2024-2026 historical Brent/WTI
- **Release**: Stable (open data, government API)
- **Relevance**: HIGH — Core oil price prediction input, no deprecation risk
- **Integration Effort**: 1 day (confirm endpoints, validate against 2025 forecasts)
- **Maturity**: STABLE
- **Assessment**: EIA Aug 2025 forecast called for $50/bbl by end-2026 (vs $81 in 2024). Test if Parallax beats naive EIA forecasts. No change needed; validate existing implementation.

---

## 4. EVALUATION & MLOps

### ⭐ Langfuse (Traceability-First Prompt Versioning)
- **What**: Instrument Sonnet calls with trace linkage. Every prediction → trace → prompt version → evaluation score → scorecard metric. Open-source + paid tier.
- **Release**: Stable (v3.x mature)
- **Relevance**: MEDIUM — Tie predictions to prompt versions, track edge decay over time
- **Integration Effort**: 1 week (instrument Anthropic SDK calls, set up Langfuse dashboard)
- **Maturity**: STABLE
- **Assessment**: ⭐ HIGH PRIORITY for debugging. Replaces ad-hoc CSV ledger with queryable audit trail. Critical for "did prompt change cause edge decay?" diagnosis. Drop-in Anthropic SDK integration.

### Calibration: Truthful Calibration Error (ICML 2026)
- **What**: Research on avoiding ECE gamification; subsampled smooth calibration error + truthful measures catch overconfident predictions
- **Release**: Academic (2024-2026 research, ICML 2026 tutorial)
- **Relevance**: HIGH — Improve daily_scorecard calibration metrics, detect miscalibration early
- **Integration Effort**: 2-3 days (add truthful calibration error to scoring/calibration.py)
- **Maturity**: RESEARCH (pure math, no external deps)
- **Assessment**: Current calibration report uses naive binning. Parallax's 15-metric scorecard should flag when model is systematically overconfident. Direct math implementation; low risk.

### LLM-as-Judge for Cascade Reasoning Quality
- **What**: Evaluate cascade chain quality (reasoning addresses oil supply, geopolitical risk, insurance rates) without waiting for market resolution
- **Release**: Mainstream (2025-2026 production standard)
- **Relevance**: MEDIUM — Early feedback loop for cascade reasoning quality
- **Integration Effort**: 1 week (define rubric, run Claude Haiku for automated scoring)
- **Maturity**: STABLE
- **Assessment**: Market resolution lag is 15-60 days. LLM-as-judge rubric scores daily predictions immediately. Heuristic metric, complements market ground truth. Formalize current ad-hoc narration into scorecard.

---

## 5. PERFORMANCE

### ⭐ DuckDB v1.5 Query Optimization Best Practices
- **What**: Partition pruning, column selection, EXPLAIN ANALYZE profiling. Techniques produce 10-100x query speedup
- **Release**: Stable (March 2026)
- **Relevance**: HIGH — Daily scorecard queries must stay sub-second
- **Integration Effort**: 2-3 days (profile slow queries, apply optimizations, tune threads)
- **Maturity**: STABLE
- **Assessment**: Partition pruning on world_state_delta + column selection + EXPLAIN ANALYZE = fast scorecard. Increase DuckDB.threads to 2-5x CPU cores for Parquet scanning. Profile before optimizing; may not be critical path today, but scorecard must scale.

### React Compiler 1.0 (October 2025) + Server Components
- **What**: Auto-memoization, React Server Components + streaming give 70% TTFB reduction. Landed Oct 2025, now default in Create React App.
- **Release**: October 2025
- **Relevance**: MEDIUM — Dashboard initial load + interactive rendering
- **Integration Effort**: 1-2 weeks (upgrade React 18 → 19, enable compiler, test SSR)
- **Maturity**: STABLE
- **Assessment**: 12% faster initial load, 2.5x faster interactions. Server Components + streaming cut 3-way network round-trips. Dashboard polls /api/latest-signals every 30s; server-side filtering + progressive streaming could reduce latency.

### WebSockets Library (v16.0+, Pure Python Async)
- **What**: Python async WebSocket server, handles 10K concurrent connections per core
- **Release**: Stable (maintained, production-ready)
- **Relevance**: MEDIUM — Real-time brief updates to dashboard
- **Integration Effort**: 1-2 days (add /ws endpoint to main.py, connect React client)
- **Maturity**: STABLE
- **Assessment**: Parallax dashboard currently polls API every 30s. WebSocket broadcasts reduce latency to sub-100ms, cut server load. Simple asyncio native integration; no polling overhead.

### H3 Performance Tuning for Bulk Operations
- **What**: Batch cell lookups, use SIMD fork for vectorized operations
- **Release**: Stable (techniques documented)
- **Relevance**: MEDIUM — Cascade engine zone lookups (1000s of chokepoint cells/tick)
- **Integration Effort**: 1 day (batch cell lookups, profile current vs SIMD)
- **Maturity**: STABLE
- **Assessment**: If cascade zone coverage expands (e.g., Persian Gulf + Suez + Panama), bulk operations become bottleneck. Batch API + SIMD → 2-3x speedup. Profile before optimizing; may not be critical path today.

---

## Summary: Top 3 Recommendations

### 🏆 #1: Claude Prompt Caching (Immediate)
- **Why**: Direct cost reduction on LLM budget. System prompts and prediction templates reused across all 50 agents, 3 cycles/day → 60-90% input token savings
- **Impact**: IMMEDIATE — Cut LLM budget from $20/day target to ~$4-8/day
- **Effort**: 1-2 days (mark cache headers, validate cost tracking)
- **Cost**: Zero (free upgrade)
- **Next Step**: Enable cache_control on system prompts and prediction templates; monitor token usage for week 1

### 🏆 #2: Claude Structured Outputs + DuckDB GEOMETRY (Combined Robustness)
- **Why**: Structured Outputs eliminate prediction JSON parsing errors (eliminates ad-hoc validation). DuckDB GEOMETRY 3-10x compresses spatial state, enables faster ST_* queries
- **Impact**: MEDIUM-HIGH — Fewer cascade errors, faster spatial operations, cleaner code
- **Effort**: 2-3 days each (4-6 days total, can parallelize)
- **Cost**: Zero (free upgrades)
- **Next Step**: Refactor brief.py to use Structured Outputs schema; profile world_state_delta spatial queries before/after GEOMETRY migration

### 🏆 #3: Langfuse Tracing + DuckDB Query Optimization (Observability + Speed)
- **Why**: Langfuse creates audit trail for every prediction → prompt version → evaluation. DuckDB tuning keeps scorecard sub-second as state grows. Combined: diagnosis + scale
- **Impact**: MEDIUM — Better debugging, sustained performance under growth
- **Effort**: 1 week + 2-3 days = 1.5 weeks
- **Cost**: Langfuse free tier covers ~100K traces/month (plenty for Phase 1)
- **Next Step**: Instrument SDK calls with Langfuse; profile scorecard queries with EXPLAIN ANALYZE; add batch optimization for slow paths

---

## Findings by Component (Priority Matrix)

| Priority | Component | Finding | Relevance | Effort | Risk | Status |
|----------|-----------|---------|-----------|--------|------|--------|
| **IMMEDIATE** | Claude API | Prompt Caching | HIGH | 1-2d | LOW | Do now — $12/day savings |
| **HIGH** | Prediction | Structured Outputs | HIGH | 2-3d | LOW | Do now — eliminate parse errors |
| **HIGH** | Spatial DB | GEOMETRY Type | HIGH | 2-3d | LOW | Do now — compress state, speed queries |
| **HIGH** | Performance | DuckDB Query Opt | HIGH | 2-3d | LOW | Do before state bloat |
| **HIGH** | Eval | Truthful Calibration | HIGH | 2-3d | LOW | Do now — catch miscalibration |
| **HIGH** | Observability | Langfuse Tracing | MEDIUM | 1w | LOW | Do this week — debugging |
| **MEDIUM** | Data | AIS Vessel Tracking | HIGH | 1-2w | MEDIUM | Explore free tier first (AISHub) |
| **MEDIUM** | Frontend | React Compiler v1.0 | MEDIUM | 1-2w | LOW | Upgrade for TTFB improvement |
| **MEDIUM** | Visualization | deck.gl v9.4 | MEDIUM | 1w | LOW | Nice-to-have for responsive layout |
| **MEDIUM** | Data | ACLED + UCDP Backup | MEDIUM | 1w | LOW | Reduce GDELT rate-limit dependency |
| **LOW** | Data | Global Geopolitical DB | MEDIUM | 3-5d | LOW | Structural baseline (nice-to-have) |
| **SKIP** | Spatial | H3 SIMD fork | MEDIUM | 4-8h | MEDIUM | Skip unless profiling shows bottleneck |
| **SKIP** | Frontend | MapLibre MLT | LOW | 2w | MEDIUM | Wait for tile server support (2027+) |
| **SKIP** | Agent | Anthropic Agents API | MEDIUM | 2-3w | MEDIUM | Phase 2 — one-shot adequate today |

---

## Key Sources

- [DuckDB Spatial Documentation](https://duckdb.org/docs/lts/core_extensions/spatial/overview)
- [Claude Structured Outputs Docs](https://platform.claude.com/docs/en/build-with-claude/structured-outputs)
- [Prompt Caching API Guide](https://platform.claude.com/docs/en/build-with-claude/prompt-caching)
- [mattsta/h3 GitHub](https://github.com/mattsta/h3)
- [deck.gl v9.4 Release Notes](https://deck.gl/docs/whats-new)
- [MapLibre GL v6 Newsletter](https://maplibre.org/news/2026-08-02-maplibre-newsletter-jul-2026/)
- [Langfuse Docs](https://langfuse.com/docs)
- [ICML 2026 Calibration Tutorial](https://calibration-tutorial.github.io/)
- [DuckDB Speed Optimization Guide 2026](https://medium.com/@hadiyolworld007/duckdb-speed-secrets-10-tricks-for-2026-29c990a8701d)
- [React Server Components Streaming](https://www.sitepoint.com/react-server-components-streaming-performance-2026/)
- [Python WebSocket Patterns 2026](https://dasroot.net/posts/2026/02/python-websocket-servers-real-time-communication-patterns/)
- [Kpler AIS Data Integration](https://www.seavantage.com/blog/vessel-tracking-api-integration-guide)
- [Global Geopolitics Dataset](https://github.com/tianyufan-econ/global-geopolitics)

---

## Next Steps

1. **This week (Sept 17-19)**: Enable prompt caching on system prompts. Refactor prediction calls to use Structured Outputs. Validate cost impact.
2. **Next week (Sept 22-26)**: Migrate world_state_delta to DuckDB GEOMETRY. Profile scorecard queries, apply EXPLAIN ANALYZE optimizations.
3. **Week 3+ (Oct 1+)**: Integrate Langfuse tracing. Explore AISHub free tier for vessel tracking. Consider React 19 upgrade path.

---

**Report Date**: 2026-09-17  
**Stack Status**: Excellent optimization opportunity in LLM costs (prompt caching), robustness (structured outputs), and observability (Langfuse). Three immediate wins available; focus on cost reduction + spatial performance first.
