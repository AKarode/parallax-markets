# Tech Research Report: 2026-10-22

**Scout focus:** Spatial/Geo, LLM/Agent, Real-time Data, Eval/MLOps, Performance

---

## Findings

### Spatial & Geospatial Visualization

#### H3 Library Update (4.5.0, July 2026)
- **Status:** Core C library (libh3) reached v4.5.0 on 2026-07-01. JavaScript bindings (h3-js) updated July 2026.
- **New feature:** `reverseDirectedEdge()` function added. Bug fix: oversized `gridDisk()` calls no longer corrupt subsequent calls.
- **Relevance:** MEDIUM. Current stack uses h3-js for H3 resolution banding; update is clean, no breaking changes detected.
- **Effort:** LOW. Bump h3-js dependency and test hex rendering. No code changes needed.
- **Risk:** LOW. Patch-level fix within minor version.
- **Note:** R wrapper (hexify) still bundles H3 v4.4.1, one version behind.

#### H3 Visualization Caveat: Non-Equal-Area Hexagons
- **Finding:** H3 cells vary in area by ~1.6× across the same resolution, depending on latitude. This breaks choropleths and density maps if using cell area as implicit weighting.
- **Relevance:** MEDIUM. Parallax uses hex coloring for threat level, flow, and influence visualization. Visual appearance is correct, but statistical summaries (e.g., "average threat per region") could bias toward pole-heavy regions.
- **Alternative:** ISEA grid is equal-area but less supported in visualization libraries. Correction: rescale heatmap values by hex area if summary statistics matter in dashboard.
- **Effort:** LOW (if needed). Add h3 area lookup and normalize color scales accordingly.
- **Risk:** LOW. Visual-only impact; doesn't affect simulation or decision logic.

#### DuckDB Spatial Extension Status (2026)
- **Activity:** Active development. duckspatial R package updated June 2026. Spatial extension bundles with DuckDB core as of v1.1.
- **GeoParquet support:** Native read/write as of v1.1. Critical: must load spatial extension explicitly (`LOAD spatial;`) or table won't get geometry column.
- **Hilbert curves:** Cloud Native Geo blog describes Hilbert-function workflow for GeoParquet to improve query locality. Not yet benchmarked in Parallax context.
- **Relevance:** MEDIUM. Parallax already uses spatial extension for H3 cell indexing. GeoParquet could speed data import/export pipelines.
- **Effort:** MEDIUM. Requires benchmarking Hilbert vs current H3 storage, schema migration.
- **Risk:** LOW-MEDIUM. Mature feature, but Hilbert optimization is still relatively new.
- **Recommendation:** Defer unless query latency on world_state becomes a bottleneck. Current delta/snapshot design already avoids full scans.

### LLM / Agent & Prompting

#### Claude API Prompt Caching & Batch Processing (2026)
- **Prompt caching:** Production-ready. Cache TTL: 5 minutes. Read cost: ~10% of base input tokens for Sonnet. Cache hits are not guaranteed (depends on exact match of system prompt + cache breakpoint).
- **Batch API:** Anthropic batch API available. Discount: 50%. Results within 24 hours. Works with caching (batched requests within 5-min window can reuse cache).
- **Relevance:** HIGH. Parallax already uses prompt caching for system prompts (historical baseline ~2-3K tokens per agent). Batch API could optimize eval cron jobs and historical replay.
- **Effort:** LOW-MEDIUM. Code already designed for async. Add batch submission wrapper for non-real-time prediction runs (e.g., portfolio simulator, daily eval cron).
- **Risk:** LOW. Fully documented, widely used.
- **Cost impact:** Batching eval cron (currently ~10 calls/day) at 50% discount = save ~$0.15/day. Marginal but moves toward hard $20/day budget headroom.
- **Recommendation:** **Implement for scorecard/eval cron in next phase.** Prediction swarm stays real-time (can't wait 24h for market signals). Portfolio simulator runs nightly—good batch candidate.

#### Structured Output Mode (Claimed, Unverified)
- **Claim:** One vendor blog reports Claude Opus supports JSON schema enforcement, but source is low-credibility.
- **Status:** Requires verification against Anthropic docs. As of Phase 1 spec, agents use free-form reasoning → JSON parsing + schema validation.
- **Relevance:** LOW for Phase 1 (current approach works). MEDIUM for Phase 2 (if reliability matters more than verbosity).
- **Effort:** LOW if available (just pass schema). HIGH if not (current parsing is solid).
- **Risk:** MEDIUM. Unverified claim. Don't assume availability.

#### LLM Calibration & Evaluation (ICML 2026)
- **Academic finding:** "How to Correctly Report LLM-as-a-Judge Evaluations" (ICML 2026, arxiv 2511.21140) proposes plug-in method to correct bias from imperfect judges. Builds confidence intervals accounting for test set + calibration set.
- **Relevance:** HIGH. Parallax eval framework currently scores predictions via manual tagging (model_error, exogenous_shock, ambiguous). LLM-as-judge could automate miss attribution.
- **Calibration target:** Cohen's kappa ≥ 0.6 vs human-labeled anchor set. Requires bias control for position, verbosity, self-preference.
- **Effort:** MEDIUM. Prototype: (1) label 50-100 historical misses manually, (2) test Sonnet as judge against labeled set, (3) measure kappa, (4) refine judge prompt.
- **Risk:** LOW. Peer-reviewed, but don't replace human review entirely—use as first-pass filter.
- **Recommendation:** **Pilot in Phase 2 eval framework overhaul.** Current manual tagging works for Phase 1 scale (10-20 misses/week). If agents scale past ~100, automation becomes necessary.

### Real-Time Data & Event Ingestion

#### GDELT Cloud (Hosted Layer, 2026)
- **What it is:** Structured event layer built on top of GDELT article stream. Includes ACLED-style conflict coding (protests, riots, armed conflict). Updates hourly.
- **Caveat:** Historical coverage is sparse before March 2026. Fresh data only.
- **Relevance:** MEDIUM. Parallax uses raw GDELT + ACLED separately. GDELT Cloud could consolidate.
- **Cost:** TBD (need to check pricing). Likely requires subscription.
- **Effort:** MEDIUM. Swap Google News RSS + GDELT BigQuery for GDELT Cloud API. Adjust ingestion cadence from 15-min to 1-hour.
- **Risk:** MEDIUM. New vendor-managed service. Pricing and uptime SLAs critical.
- **Recommendation:** Evaluate as backup if current GDELT ingestion becomes unreliable. Not urgent for Phase 1.

#### Open-Source Maritime AIS Data (AISdb)
- **Tool:** AISdb (Python platform for AIS collection, cleaning, spatio-temporal querying). Described in 2024 SoftwareX paper. Supports joining AIS with environmental datasets.
- **Limitation:** Visualization module marked as outdated. Real-time streaming availability depends on local feed setup.
- **Relevance:** MEDIUM. Parallax models Hormuz shipping flow as % reduction but uses static searoute geometry, not live AIS. Real AIS data would improve realism.
- **Effort:** MEDIUM-HIGH. (1) Set up AIS data feed (e.g., AISHub or local receiver), (2) ingest into AISdb, (3) query vessel positions, (4) map to H3 cells, (5) update flow state.
- **Risk:** MEDIUM. Requires reliable AIS feed (commercial services like MarineTraffic are proprietary; open feeds are spotty).
- **Recommendation:** **Phase 2 enhancement.** Pair with searoute as baseline, AIS as real-time refinement. For Phase 1, continue static flow assumption (adequate for cascade logic).

#### Geopolitical Event Data Stack (No Silver Bullet)
- **Finding:** No single geopolitical event API. Industry standard is to layer two sources:
  1. **Conflict events:** ACLED (validated, lagged 1-2 weeks) or UCDP (research-grade, monthly).
  2. **News volume/mentions:** GDELT (fast, noisy) or GDELT Cloud (cleaner, hourly, 2026+ data only).
- **Current Parallax:** Uses both. GDELT Cloud could replace raw GDELT but trades 15-min freshness for cleaner structure.
- **Relevance:** MEDIUM. Current stack is reasonable; no better alternatives found.
- **Recommendation:** Stay with current approach for Phase 1. Monitor GDELT Cloud pricing for Phase 2 simplification.

### Performance & Optimization

#### DuckDB vs PostgreSQL (OLAP Context)
- **Benchmark (2023, Swiss university thesis):** DuckDB ~30× faster than PostgreSQL on analytical aggregations. PostgreSQL wins on transactional writes by 50%.
- **2026 trend:** MotherDuck claims their Quack pushdown consistently beats PostgreSQL on analytical scans. Vendor claim; treat skeptically.
- **Geospatial-specific:** No 2026 benchmark found. OpenStreetMap comparison exists but results not publicly available.
- **Hybrid approach:** DuckDB Postgres extension allows direct querying of live Postgres, useful for heterogeneous stacks.
- **Relevance:** LOW-MEDIUM for Phase 1. DuckDB already chosen. Relevant if Phase 2 scales to multi-user writes (would require Postgres hybrid).
- **Recommendation:** Stick with DuckDB single-writer for Phase 1. Document migration path to Postgres if write concurrency becomes critical in Phase 2.

#### deck.gl High-Frequency Data Optimization
- **Key principle:** Minimize unnecessary layer updates. Each data prop change triggers GPU buffer rebuild, cost scales with item count.
- **Best practice:** Batch updates instead of reassigning full dataset per tick. Use `dataComparator` callback to control when layer refreshes.
- **Performance ceiling:** ~60 FPS up to 1M items on 2015 MacBook. Drops to 10-20 FPS near 10M items.
- **Relevance:** HIGH. Parallax pushes ~400K hexes + WebSocket updates every few seconds during live simulation.
- **Current design:** Uses `useRef` for mutable hex data, decouples React UI from deck.gl data arrays. Batches WebSocket updates for 100ms window. Matches best practices.
- **Effort:** LOW (already implemented). Monitor FPS with profiler during user tests.
- **Recommendation:** **No changes needed.** Current architecture is solid. If performance degrades, profile with Chrome DevTools GPU timeline and consider chunking hex layers further.

#### DuckDB Query Optimization for Spatial Deltas
- **Finding:** No specific 2026 tuning guide found. Official docs recommend EXPLAIN ANALYZE on your own workload.
- **Practical opportunity:** Current delta/snapshot design avoids full scans. Could optimize further with Hilbert curve indexing on cell_id for better cache locality.
- **Effort:** MEDIUM. Requires benchmarking and schema changes.
- **Recommendation:** **Defer unless query latency becomes visible bottleneck.** Phase 1 data volume (~400K hexes) is well within DuckDB's sweet spot.

---

## Top 3 Recommendations

### 1. **Implement Claude Batch API for Eval Cron (Q1 2027)**
- **Why:** Parallax's daily eval cron (10-20 LLM calls) can move to batch processing (50% discount, 24-hour results). Pushes $20/day budget further.
- **Effort:** 3-4 days. Refactor eval cron to submit batch, poll results next day.
- **Impact:** Saves ~$0.15/day on eval costs (~$55/year). More importantly, proves cost-control discipline for Phase 2 scaling.
- **Risk:** LOW. Non-critical path (eval doesn't block predictions).

### 2. **Pilot LLM-as-Judge for Miss Attribution (Phase 2)**
- **Why:** Manual tagging of prediction misses works at Phase 1 scale but doesn't scale to 100+ agents. Academic calibration method (ICML 2026) is credible and practical.
- **Effort:** 1 week. Prototype: label 50 historical misses, test Sonnet judge, measure Cohen's kappa.
- **Impact:** Automates tedious admin task, improves feedback loop into prompt refinement.
- **Risk:** MEDIUM. Requires validation that judge kappa ≥ 0.6 on Parallax data before deploying.

### 3. **Defer AIS Integration; Stay with Static Searoute (Phase 1)**
- **Why:** Live AIS improves realism but requires reliable data feed and significant integration. Phase 1 timeline is April 7-21 (2-week ceasefire window). Static flow assumptions are adequate for cascade validation.
- **Effort:** Would be MEDIUM-HIGH; deferring saves 2-3 weeks.
- **Impact:** Unblocks Phase 1 launch on schedule. AIS becomes Phase 2 enhancement once core signal (predictions vs market prices) is proven.
- **Risk:** LOW. Simulation logic is robust enough to work with either static or dynamic flow. Future migration is straightforward (same H3 cell update interface).

---

## Links & Sources

**Spatial/Geo:**
- [H3 JavaScript v4.5.0 Changelog](https://cdn.jsdelivr.net/npm/h3-js@4.5.0/CHANGELOG.md)
- [DuckDB Spatial Extension with GeoParquet](https://cloudnativegeo.org/blog/2025/01/using-duckdbs-hilbert-function-with-geoparquet/)
- [duckspatial R Package](https://cran.r-universe.dev/api/packages/duckspatial)
- [deck.gl Performance Guide](https://deck.gl/docs/developer-guide/performance)

**LLM/Agent:**
- [Claude API Cache Pricing 2026](https://sandlabs.com.au/blog/claude-api-pricing-cost-optimization)
- [How to Reduce AI API Costs 80%](https://devtk.ai/en/blog/how-to-reduce-ai-api-costs/)
- [ICML 2026: How to Correctly Report LLM-as-a-Judge Evaluations](https://proceedings.mlr.press/v306/lee26bl.html)
- [arXiv: LLM Judge Calibration (2511.21140v3)](https://arxiv.org/abs/2511.21140v3)

**Real-time Data:**
- [Free Geopolitical Data APIs 2026](https://www.worldmonitor.app/blog/posts/free-geopolitical-data-apis-2026/)
- [AISdb: Maritime AIS Data Platform (SoftwareX 2024)](https://doaj.org/article/820b0928226445669e02858706cd49df)
- [AISdb on PyPI](https://pypi.org/project/aisdb)
- [AISCOT Documentation](https://aiscot.readthedocs.io/)

**Performance:**
- [DuckDB vs PostgreSQL Comparison](https://motherduck.com/learn/duckdb-vs-postgres-embedded-analytics.md)
- [DuckDB Ecosystem Newsletter July 2026](https://motherduck.com/blog/duckdb-ecosystem-newsletter-july-2026/)
- [DuckDB vs Postgres: Key Differences](https://airbyte.com/data-engineering-resources/duckdb-vs-postgres)

---

## Summary

**No critical blockers found.** Current stack is well-positioned for Phase 1 launch.

- **Quick wins (Q4 2026):** H3 library update (verify no breaking changes), verify Claude Opus structured output claim.
- **Phase 2 enhancements:** Batch API for eval cron, LLM-as-judge for miss attribution, AIS data integration, GDELT Cloud migration.
- **Deferred:** Geospatial query optimization, multi-user Postgres migration. Revisit if scaling beyond 100 agents or 50+ concurrent sessions.

All sources checked 2026-10-22. Links marked as vendor blogs (MotherDuck, Airbyte, etc.) are opinion; academic papers (ICML, arXiv) are stronger sources.
