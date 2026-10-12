# Parallax Daily Tech Research Report
**Date:** 2026-10-12  
**Focus Areas:** Spatial/Geo, LLM/Agent, Real-time Data, Eval/MLOps, Performance

---

## Executive Summary

This report surveys improvements in five technology areas supporting Parallax. Key findings include emerging real-time vessel tracking APIs, recent evaluation frameworks for prediction markets, DuckDB performance optimizations, and unverified Claude API cost-reduction features. Most findings are **additive** (complement existing stack) rather than requiring replacement.

---

## Findings by Category

### 1. SPATIAL/GEOSPATIAL

#### A. H3 Library Updates (v4.5.0, July 2026)
**Relevance:** MEDIUM | **Effort:** LOW | **Risk:** LOW | **Type:** Additive

- **JavaScript bindings:** h3-js reached v4.5.0 (2026-07-01) with new `reverseDirectedEdge` function and fix for oversized `gridDisk` calls corrupting subsequent calls.
- **Python bindings:** h3 package at v4.4.2, conda-forge at v4.4.1. Stable API across v3→v4 transition.
- **Assessment:** Grid system and cell identifiers remain unchanged across major versions, so no code migration risk. The `gridDisk` overflow fix may improve stability for edge cases in hex neighborhood queries. Current Parallax uses h3-js for frontend only; consider updating if using gridDisk for H3 cell enumerations.
- **Action:** Monitor release notes; upgrade at next frontend dependency refresh.

**Sources:**
- [H3 Changelog (h3-js 4.5.0)](https://cdn.jsdelivr.net/npm/h3-js@4.5.0/CHANGELOG.md)
- [H3 Documentation](https://access.crunchydata.com/documentation/h3/latest/)
- [H3 on Conda-Forge](https://anaconda.org/conda-forge/h3/)

---

#### B. DuckDB H3 Extension Performance (R package duckh3)
**Relevance:** LOW | **Effort:** MEDIUM | **Risk:** MEDIUM | **Type:** Additive

- **New R wrapper:** duckh3 (v0.1.0, published 2026-04-24) wraps DuckDB spatial + H3 extension for R users. Described as "fast & memory-efficient" but with unverified performance claims.
- **Test status:** CRAN checks show 1 ERROR, 12 OK on flavors. Error on r-devel-linux-x86_64-fedora-clang. Not production-ready across all environments.
- **Python availability:** No Python bindings found. DuckDB's H3 support exists as a community extension but lacks benchmarks.
- **Assessment:** Parallax is Python/FastAPI, not R, so duckh3 is not applicable. The underlying DuckDB H3 extension could be useful for spatial queries on ~400K hexes, but no performance data exists to justify migration from pure Python + h3-js. Run internal benchmarks before prioritizing.
- **Action:** Defer until DuckDB H3 extension gains production status and benchmarks. Monitor DuckDB community extensions page.

**Sources:**
- [duckh3 CRAN Package](https://cran.r-project.org/web/packages/duckh3/index.html)
- [DuckDB Spatial Talk (2024)](https://www.utwente.nl/nl/eemcs/agenda/2024/5/1474788/talk-high-performance-spatial-data-management-and-analysis-with-duckdb)

---

#### C. deck.gl H3HexagonLayer Performance Modes
**Relevance:** HIGH | **Effort:** LOW | **Risk:** LOW | **Type:** Additive

- **Instanced drawing:** The layer can draw large hex sets by assuming all viewport hexagons match the one at center. Error usually imperceptible for Res 6-9 but can accumulate at Res 3-4.
- **High-precision mode:** Automatically triggered for pentagons, coarse resolutions (Res 0-5), or mixed resolutions. Trades speed for accuracy. Can be explicitly controlled via `highPrecision: 'auto' | true | false`.
- **Metrics API:** deck.gl v9+ exposes `metrics` property on Deck instances (fps, CPU/GPU render time, memory) for real-time profiling.
- **Assessment:** Parallax uses 4 layers (Res 3-4, 5-6, 7-8, 9). Res 3-4 may trigger high-precision mode by default, impacting frame rate during high-activity periods. Parallax's current approach (separate layers per resolution band) already mitigates this. Instanced drawing is already active. The metrics API could improve dashboard responsiveness monitoring — currently not exposed.
- **Action:** Add metrics endpoint to FastAPI to expose deck.gl frame rate and render times. Consider explicit `highPrecision: false` for Res 3-4 layer if profiling shows CPU strain during crisis spikes.

**Sources:**
- [deck.gl H3HexagonLayer API Reference](https://deck.gl/docs/api-reference/geo-layers/h3-hexagon-layer)
- [deck.gl What's New](https://github.com/visgl/deck.gl/blob/b4f96929402e489ac283ab1abeb61355618f63dd/docs/whats-new.md)

---

### 2. LLM/AGENT

#### A. Claude API Batch Processing + Prompt Caching (Unverified Pricing)
**Relevance:** HIGH | **Effort:** MEDIUM | **Risk:** MEDIUM | **Type:** Additive

- **Batch API:** Claimed 50% discount on standard pricing; processes requests asynchronously within 24-hour window.
- **Prompt caching:** Claimed ~10% cost for cache reads, unclear write cost (reported as 1.25x or $0.01 per 1K tokens — conflicting sources). Cache TTL typically 5-10 minutes, but enterprise tier with 24-hour TTL reported but unconfirmed.
- **Combined savings:** Marketing claims up to 95% effective spend reduction on eligible workloads; unverified by independent benchmarks.
- **Constraints:** Max 4 cacheable content blocks per request (unconfirmed). Batch API not suitable for real-time agent decisions. Prompt caching best for stable system prompts (agent baselines are ~2-3K tokens — good candidate).
- **Parallax relevance:** Design doc specifies $20/day budget with prompt caching already planned (system prompt is the largest input component). Batch API could complement eval cron tasks (daily scorecard, prediction calibration) but not live agent calls.
- **Assessment:** Cost reduction is critical to Parallax but depends on *official* Anthropic pricing docs. The search results are third-party, unvetted sources. Do not commit to batch/caching strategy without verifying against https://api.anthropic.com/pricing.
- **Action:** **Required:** Verify prompt caching and batch API details on official Anthropic docs. Quantify savings on current token usage (est. 200 Haiku + 50 Sonnet calls/day). Consider batch API for daily eval scorecard. Confirm enterprise cache TTL before relying on 24-hour caching.

**Sources:**
- [Claude Pricing 2026 (Third-Party Estimate)](https://finout.io/blog/claude-pricing-in-2026-for-individuals-organizations-and-developers)
- [Claude API Cost Reduction Guide](https://cut-the-saas.com/the-cut/claude-api-pricing)

---

### 3. REAL-TIME DATA

#### A. GDELT Data Quality Concerns
**Relevance:** MEDIUM | **Effort:** LOW | **Risk:** LOW | **Type:** Additive

- **Accuracy:** 2025 study in *Data* (MDPI) found key field accuracy only ~55%, with 20% redundancy. Recommend deduplication and validation before use.
- **Parallax mitigation:** Already implements 4-stage filter: volume gate, structural dedup, semantic dedup (sentence-transformers), relevance scoring. Named-entity override allows high-value low-mention signals. Design is sound.
- **Assessment:** Parallax's noise-filtering strategy is well-suited to GDELT's limitations. No change needed, but awareness of ~55% accuracy should inform confidence scores on predictions driven by single-source GDELT events.
- **Action:** Document GDELT accuracy limits in eval notes. Consider GDELT Cloud as complement (see below).

**Sources:**
- [GDELT Project Documentation](https://docs.gdeltcloud.com/)
- [Foreign Policy Article on GDELT Syria Coverage](https://staging02.foreignpolicy.com/?p=19371)

---

#### B. GDELT Cloud Alternative (Hourly, Conflict-Focused)
**Relevance:** MEDIUM | **Effort:** MEDIUM | **Risk:** MEDIUM | **Type:** Additive

- **GDELT Cloud:** Newer GDELT-derived product; updates hourly (vs. GDELT's 15-min raw); conflict events follow ACLED methodology. Data sparse before March 2026 (not useful for historical validation).
- **Positioning:** GDELT Cloud is a filter and re-presentation of base GDELT, not an independent data source.
- **Assessment:** Could supplement GDELT for conflict-specific events; hourly cadence is less granular than Parallax's 15-min cycle. Limited historical depth hurts eval. ACLED (below) may be better fit for validated conflict.
- **Action:** Low priority. Revisit if GDELT Cloud adds historical backfill or real-time (< 1 hr) capability.

**Sources:**
- [GDELT Cloud Documentation](https://docs.gdeltcloud.com/)
- [WorldMonitor Geopolitical Data APIs 2026](https://www.worldmonitor.app/blog/posts/free-geopolitical-data-apis-2026/)

---

#### C. Real-Time Vessel Tracking: LSEG + Alternatives
**Relevance:** HIGH | **Effort:** MEDIUM | **Risk:** LOW | **Type:** Additive

- **LSEG Vessel Tracking API (Launched March 2026):** Real-time satellite + terrestrial AIS fusion. Validates positions against anomalies (interference, decommissioned vessels). Backed by Kinéis constellation (25 nanosatellites) + terrestrial networks. Targets enterprise commodities users.
- **MyShipTracking REST API:** Live terrestrial AIS. Returns positions, voyage data, zone queries, historical tracks, ETAs. Paid credit-metered API; limited free trial.
- **SeaRates Vessel Tracking:** IMO/MMSI/name search; includes predictive ETA. Logistics-focused.
- **AIS Hub:** Community-fed real-time AIS; minimal documentation; token-based auth.
- **Parallax relevance:** Live Hormuz traffic is a key indicator. Current design reluses on simulated flow + cascade rules, not real AIS. Adding real vessel tracking would dramatically improve Hormuz closure scenarios. Integrating live AIS could replace parametric "% blockade" model with ground-truth vessel counts.
- **Assessment:** LSEG is premium enterprise product; no pricing found. MyShipTracking and SeaRates are established; AIS Hub is community alternative. Effort: ~200 lines of code to ingest vessel positions, map to H3 zones, compute flow metrics. Risk: API dependency, latency SLAs not specified.
- **Action:** HIGH PRIORITY. Evaluate LSEG (contact sales) for enterprise access. As fallback, integrate MyShipTracking or SeaRates API to populate `vessel_positions` table. Pilot with free AIS Hub. This could be Phase 2 feature (live AIS overlay on dashboard, real-time flow metrics).

**Sources:**
- [LSEG Vessel Tracking API Launch (March 2026)](https://fintech.global/2026/03/20/lseg-launches-real-time-vessel-tracking-api/)
- [MyShipTracking GitHub](https://github.com/api-evangelist/myshiptracking)
- [SeaRates Vessel Tracking Blog](https://www.searates.com/blog/post/searates-vessel-tracking-how-to-track-a-ship-online-in-real-time)
- [AIS Hub Public API](https://public-api.org/api/1260/ais-hub)

---

### 4. EVALUATION & MLOps

#### A. Prediction Arena: Autonomous LLM Trading on Live Markets
**Relevance:** HIGH | **Effort:** HIGH | **Risk:** MEDIUM | **Type:** Additive

- **What it is:** Framework for benchmarking LLMs by autonomously trading on prediction markets (Polymarket, Kalshi). Models manage portfolios, time entries/exits, learn from live feedback. Avoids overfitting via prospective evaluation (no backtesting).
- **Key insight:** Testing against *live* market prices under real capital constraints reveals model weaknesses that benchmarks on static data miss.
- **Status:** arXiv paper (2604.07355); no release date or code availability mentioned.
- **Parallax relevance:** Parallax's eval framework (Section 7 of design) already compares predictions vs market prices and tracks calibration. Prediction Arena's autonomous trading loop is orthogonal — it's not about improving agent accuracy but about stress-testing via real capital allocation.
- **Assessment:** Conceptually relevant. Could inform Parallax's Phase 2 portfolio allocator (currently Quarter-Kelly, static sizing). Implementation effort high (portfolio rebalancing, slippage modeling, live order placement). Risk: live trading losses if models are untested.
- **Action:** Watch arXiv. If code is released, use Prediction Arena's framework for Phase 2 position-sizing validation (paper trading first). Not critical for Phase 1 (end of 2-week ceasefire window 2026-04-21 is imminent in historical context).

**Sources:**
- [Prediction Arena Paper](https://arxiv.org/pdf/2604.07355)

---

#### B. PolyBench: Evaluation on 38.6K Polymarket Binary Markets
**Relevance:** HIGH | **Effort:** LOW | **Risk:** LOW | **Type:** Additive

- **What it is:** Benchmark dataset of 38,666 Polymarket binary markets. Evaluates 7 LLMs on forecasting accuracy and trading. Timestamp-locked market snapshots (Feb 6-12, 2026). Public GitHub repo.
- **Coverage:** Broad real-world market set; not Iran-focused but geopolitical markets included.
- **Method:** Snapshot markets at fixed points in time, evaluate LLM predictions against actual outcomes post-resolution. Prospective (not backtested).
- **Parallax relevance:** Parallax predictions are on Iran-specific markets (Kalshi/Polymarket). PolyBench offers a large validation set to compare Parallax's Sonnet predictions against baselines. Could be used to benchmark Parallax's overall accuracy on a broader market set.
- **Assessment:** Low effort — download dataset, run Parallax's prediction models on PolyBench markets, compute hit rate. Useful for Phase 2 validation. arXiv paper + public data, no licensing barriers mentioned.
- **Action:** Download PolyBench after Phase 1 closes (post 2026-04-21). Use as holdout test set to validate Parallax's generalization beyond Iran scenario.

**Sources:**
- [PolyBench Paper](https://arxiv.org/abs/2604.14199)
- [PolyBench GitHub](https://github.com/PolyBench)

---

#### C. PredictionMarketBench: Event-Driven Replay Framework
**Relevance:** MEDIUM | **Effort:** MEDIUM | **Risk:** LOW | **Type:** Additive

- **What it is:** SWE-bench-style benchmark for algorithmic trading agents. Event-driven replay of Kalshi limit-order-book (LOB) and trade history. Deterministic, timestamped episodes.
- **Key insight:** Naive trading agents underperform due to transaction costs and settlement delays. Framework isolates trading logic from prediction logic.
- **Status:** arXiv 2602.00133 (submitted Jan 2026); no code/data availability mentioned.
- **Parallax relevance:** Parallax's PaperTradeTracker (scoring/tracker.py) simulates trades on Kalshi. PredictionMarketBench's LOB replay could improve simulator fidelity. Currently, Parallax uses simplified market depth; real LOB data would add realism.
- **Assessment:** Useful for Phase 2 (improving trade execution). Not urgent for Phase 1. Effort depends on whether Kalshi LOB data is obtainable. Kalshi API may not expose full LOB history; check API docs.
- **Action:** Defer to Phase 2. Contact Kalshi to inquire about historical LOB data export. If available, consider integrating PredictionMarketBench's event-driven replay as a trade simulator improvement.

**Sources:**
- [PredictionMarketBench Paper](https://arxiv.org/abs/2602.00133)

---

#### D. PolySwarm: 50-Agent Swarm on Polymarket (Real/Paper Trading)
**Relevance:** MEDIUM | **Effort:** MEDIUM | **Risk:** HIGH | **Type:** Parallel Implementation

- **What it is:** Trading system (not eval framework), 50 LLM personas with Quarter-Kelly sizing. Supports paper and live trading modes.
- **Assessment:** PolySwarm is a reference implementation of what Parallax is building (swarm + position sizing + trading). Risk: live trading losses; unclear if paper mode is isolated. Design doc already specifies Quarter-Kelly + paper mode. PolySwarm's architecture is likely similar.
- **Action:** Not recommended. Parallax is designing its own portfolio allocator; PolySwarm is a parallel implementation from competitors. Monitoring it for architectural ideas is fine (unit economics, Kelly framing), but integration is unlikely.

**Sources:**
- [PolySwarm Paper](https://arxiv.org/abs/2604.03888)

---

### 5. PERFORMANCE

#### A. DuckDB Optimization Techniques
**Relevance:** HIGH | **Effort:** LOW | **Risk:** LOW | **Type:** Additive

- **Columnar format:** Convert frequently queried CSVs to Parquet. Queries scan only needed columns. Significant speedup.
- **Tight WHERE clauses:** Use date ranges, value comparisons, not function wrapping. Enables index usage (sargable queries).
- **Late materialization (v1.3+, June 2025):** 3-10x faster reads on queries with LIMIT clauses (common for pagination, top-K).
- **Real-world result:** PostgreSQL → DuckDB in-process cache yielded 5-10x speedup on analytical queries.
- **Parallax relevance:** Design stores raw events in DuckDB; queries serve dashboards and APIs. Parallax tables: `curated_events` (rows: ~10K/week), `decisions` (rows: ~500/week), `predictions` (rows: ~1K/week), `world_state_delta` (~10M rows/month). Late materialization could improve pagination on large tables. Columnar storage (Parquet) not directly applicable since DuckDB is the source, not an import.
- **Assessment:** Easy wins. Apply sargable WHERE clauses in dashboard queries (timeframe filters, entity filters). Use LIMIT in prediction/decision feeds. Already low risk since these are query optimizations, not schema changes.
- **Action:** Audit dashboard queries (dashboard/data.py) for sargability. Add query metrics to track improvement. No changes needed to schema or ingestion.

**Sources:**
- [DuckDB Performance Guide](https://duckdb.org/docs/guides/performance/overview)
- [10 DuckDB Optimizations Every Data Engineer Should Know](https://medium.com/@ThinkingLoop/10-duckdb-optimizations-every-data-engineer-should-know-cb831c9956ef)
- [DEV Community: DuckDB Arrow Parquet Stack 2026](https://dev.to/dataformathub/duckdb-arrow-and-parquet-the-ultimate-analytical-stack-for-2026-2mbi)

---

#### B. WebSocket Streaming Architecture for Real-Time Dashboards
**Relevance:** HIGH | **Effort:** MEDIUM | **Risk:** MEDIUM | **Type:** Additive

- **Finding:** General consensus that DuckDB alone cannot handle distributed analytics with multi-user WebSocket fan-out. Requires server-side layer (caching, connection pooling).
- **Parallax architecture:** Already uses single-writer pattern + FastAPI WebSocket to fan out updates. Design is sound.
- **Assessment:** Parallax's approach (Section 9, state persistence) is correct. Single DuckDB process, WebSocket server fans out to many clients. No architecture change needed. Performance tuning (batch updates, 100ms flush) already specified.
- **Action:** Monitor websockets library for newer versions (currently 14.0+). Profile WebSocket message throughput during simulated crisis (100+ events/sec). If latency > 1 sec, consider message compression or binary protocol.

**Sources:**
- [Tinybird DuckDB Alternatives Analysis (May 2026)](https://www.tinybird.co/blog/md/duckdb-alternatives)

---

## Summary Table

| Finding | Category | Relevance | Effort | Risk | Recommendation |
|---------|----------|-----------|--------|------|-----------------|
| H3 v4.5.0 updates | Spatial | MEDIUM | LOW | LOW | Monitor; upgrade at next refresh |
| duckh3 R package | Spatial | LOW | MEDIUM | MEDIUM | Defer; not Python-applicable |
| deck.gl metrics API | Spatial | HIGH | LOW | LOW | Add to FastAPI; profile high-load scenarios |
| Claude API batch/caching | LLM | HIGH | MEDIUM | MEDIUM | **Required:** Verify official pricing; implement if savings > 20% |
| GDELT accuracy | Data | MEDIUM | LOW | LOW | Document limits; note in eval |
| GDELT Cloud | Data | MEDIUM | MEDIUM | MEDIUM | Low priority; revisit if adds history |
| LSEG Vessel Tracking API | Data | **HIGH** | MEDIUM | LOW | **TOP PRIORITY:** Evaluate for Phase 2; pilot with AIS Hub |
| Prediction Arena | Eval | HIGH | HIGH | MEDIUM | Watch for code release; Phase 2 portfolio validation |
| PolyBench | Eval | HIGH | LOW | LOW | Use as Phase 2 holdout test set |
| PredictionMarketBench | Eval | MEDIUM | MEDIUM | LOW | Phase 2; contact Kalshi for LOB data |
| PolySwarm | Eval | MEDIUM | MEDIUM | HIGH | Monitor; do not integrate (parallel impl) |
| DuckDB query optimization | Perf | HIGH | LOW | LOW | Audit dashboard queries; apply sargability |
| WebSocket streaming | Perf | HIGH | MEDIUM | MEDIUM | Profile; optimize if latency > 1sec |

---

## Top 3 Recommendations

### 1. **Verify Claude API Batch + Caching Economics [REQUIRED]**
   - **Why:** Parallax's $20/day LLM budget is tight. Batch API + prompt caching could reduce costs by 30-50%, adding runway to Phase 2.
   - **Action:**
     1. Check official Anthropic pricing page for batch API (50% discount?) and prompt caching (read cost, TTL).
     2. Quantify current usage: ~200 Haiku (sub-actors) + 50 Sonnet (country agents) + 10 eval calls/day.
     3. Estimate cost delta: If batch (daily scorecard) saves 30% and caching saves 20% on system prompts, potential savings: ~$3-5/day.
     4. Implement batch API for daily `--scorecard` cron if savings confirmed.
     5. Implement system prompt caching for all agent calls (system prompt is largest input token component).
   - **Effort:** 4 hours (API integration, cost simulation, testing).
   - **Risk:** Low; changes are in ingestion pipeline, not core engine.

### 2. **Integrate Real-Time Vessel Tracking for Hormuz Scenarios [Phase 2 Feature]**
   - **Why:** Hormuz blockade intensity is a core prediction target. Real vessel tracking (AIS) replaces parametric models with ground truth, dramatically improving scenario realism and predictive power.
   - **Action:**
     1. Evaluate LSEG Vessel Tracking API (contact sales for enterprise terms).
     2. Fallback: Pilot with free AIS Hub or paid MyShipTracking (free trial).
     3. Ingest live vessel positions into new `vessel_positions` table (lat/lng + timestamp).
     4. Map vessel positions to H3 cells via h3_lat_lng_to_cell.
     5. Compute real-time Hormuz flow metric: (vessel count in Hormuz cells) / (baseline count).
     6. Feed this into cascade engine as an exogenous signal (alternative to agent-initiated blockade).
     7. Add vessel heatmap layer to deck.gl dashboard.
   - **Effort:** 40 hours (API integration, H3 mapping, cascade rule modification, dashboard layer).
   - **Risk:** Medium; API reliability/latency TBD; adds external dependency.
   - **ROI:** High; real data beats simulation. Could unlock Parallax → hedge fund edge if vessel tracking is proprietary advantage.

### 3. **Optimize DuckDB Queries + Add deck.gl Metrics Monitoring [Phase 1 Polish]**
   - **Why:** Dashboard performance directly impacts user perception during live crises. Real-time metric exposure (fps, render time, memory) allows proactive tuning.
   - **Action:**
     1. Audit `dashboard/data.py` for non-sargable WHERE clauses. Add date/entity range filters.
     2. Profile `predictions` and `decisions` tables for LIMIT queries; ensure late materialization is active (DuckDB 1.3+).
     3. Add `/api/metrics` endpoint exposing deck.gl `Deck.metrics` (fps, CPU/GPU time, memory).
     4. Wire metrics into dashboard right panel (live performance card: "45 fps, 12ms render time").
     5. Set alert threshold: if fps < 30 during live event, degrade to lower-resolution H3 layer (Res 3 only) or pause WebSocket updates temporarily.
   - **Effort:** 8 hours (query audit, metrics endpoint, dashboard card, alert logic).
   - **Risk:** Low; query changes are backward-compatible; metrics are read-only.
   - **ROI:** Medium; improves reliability; helps diagnose performance issues during crises.

---

## Conclusion

Most findings are **additive enhancements** that complement Parallax's current stack. No fundamental replacements are needed. Highest-impact work is:
1. Verifying Claude API cost savings (potential 3-5x runway extension).
2. Evaluating real-time vessel tracking for Phase 2 (unlocks real-world edge over simulation-only competitors).
3. Query and performance polishing for Phase 1 demo reliability.

The team should prioritize items 1 (required for budget confidence) and 3 (Phase 1 ship quality), then target item 2 (Phase 2 differentiator).

---

**Report compiled by:** Daily Tech Scout  
**Next report:** 2026-10-13
