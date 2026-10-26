# Technology Research Report — 2026-10-26

**Focus areas:** Spatial/Geo, LLM/Agent APIs, Real-time Data Ingestion, Eval/MLOps, Performance Optimization

---

## Summary

Research identified **2 HIGH-value integration opportunities** and **3 actionable recommendations** for Phase 1 and Phase 2:

1. **Real-time Vessel Tracking APIs** (VesselFinder, Kpler, Datalastic) — adds satellite + terrestrial AIS visibility into Hormuz shipping flows, directly complementing GDELT geopolitical events
2. **Claude Batch API + Prompt Caching stack** — 50-95% cost savings on eval pipeline (daily scorecard, A/B testing); stackable discounts confirmed in official docs
3. **DeepEval + Calibration Metrics** — open-source framework with 50+ evaluation metrics; directintegration with existing eval pipeline

Current stack remains stable. No breaking changes found in DuckDB spatial, deck.gl, or Claude API. React/WebSocket performance patterns already align with 2026 best practices.

---

## Findings by Category

### 1. Spatial/Geospatial

#### 1.1 DuckDB Spatial Extension — Stable, No Major 2026 Updates
**Discovery:** DuckDB 1.5.6 (Sept 2026) includes bugfixes and Windows performance gains but no improvements to H3 or spatial extension.

**Assessment:**
- **Relevance:** LOW — current implementation is stable
- **Effort:** N/A
- **Risk:** N/A
- **Recommendation:** No action needed. Continue monitoring DuckDB release notes quarterly for breaking changes or new spatial functions.

**Sources:**
- [Announcing DuckDB 1.5.6](https://duckdb.org/2026/09/28/announcing-duckdb-156)
- [Awesome DuckDB Spatial](https://github.com/alperdincer/Awesome-DuckDB-Spatial)

---

#### 1.2 deck.gl H3HexagonLayer Performance — v9.4 Improvements Mentioned
**Discovery:** deck.gl v9.4 (Sept 2026) lists H3HexagonLayer performance improvements in release notes, but detailed changelog is jumbled in search results.

**Assessment:**
- **Relevance:** LOW-MEDIUM — only if current performance is a bottleneck
- **Effort:** LOW — upgrade deck.gl to 9.4+
- **Risk:** LOW — patch release in mature library
- **Recommendation:** Current design with 400K hexes is well within performance limits. Upgrade to v9.4 when updating other dependencies. Check v9.4 CHANGELOG for specific H3 changes before production upgrade.

**Sources:**
- [deck.gl What's New](https://deck.gl/docs/whats-new)
- [deck.gl Performance Guide](https://deck.gl/docs/developer-guide/performance)

---

### 2. LLM / Agent APIs

#### 2.1 Claude Batch API + Prompt Caching Stack — HIGH RELEVANCE ⭐
**Discovery:** Official Anthropic docs confirm prompt caching works with Batch API. Combined discounts stack for 50-95% savings on offline workflows.

**Current Parallax state:** Spec mandates prompt caching for system prompts (already implemented). Batch API not yet used for eval pipeline.

**Assessment:**
- **Relevance:** HIGH — directly applicable to daily scorecard and eval cron
- **Effort:** LOW — refactor `cli/brief.py --scorecard` to batch eval calls
- **Risk:** LOW — Batch API is GA, officially documented
- **Recommendation:**
  - Use Batch API for all eval/recalibration calls (meta-agent prompt suggestions, accuracy audits, A/B rollout comparisons)
  - Keep live agent swarm on standard API (must remain synchronous for event-driven reactions)
  - Batch requests need identical `cache_control` blocks to maximize cache hits
  - Verify current prompt cache TTL on Anthropic docs (one source claims it changed from 60 min to 5 min in early 2026, but official docs may differ)
  - **Estimated savings:** $30-50/month on Phase 1 eval budget; scales with eval frequency

**Sources:**
- [Claude Batch Processing Docs](https://platform.claude.com/docs/en/build-with-claude/batch-processing)
- [Claude Prompt Caching Docs](https://platform.claude.com/docs/en/build-with-claude/prompt-caching)
- [Anthropic API Pricing 2026](https://www.finout.io/blog/anthropic-api-pricing)

---

#### 2.2 New Claude Models — Monitoring Only
**Discovery:** Some sources mention Fable 5.1, Opus 5.5, Sonnet 5.0 (Sept 2026), but these model names are NOT confirmed in official Anthropic docs.

**Assessment:**
- **Relevance:** LOW — current Haiku/Sonnet/Opus models are appropriate
- **Effort:** N/A
- **Risk:** N/A (claim unverified)
- **Recommendation:** Monitor Anthropic releases. Verify model availability in platform docs before planning any migration.

**Sources:**
- [Anthropic API Pricing in 2026: Complete Guide](https://www.finout.io/blog/anthropic-api-pricing) — *Note: model names in this vendor guide may not match official Anthropic releases*

---

### 3. Real-Time Data Ingestion

#### 3.1 Real-Time Vessel Tracking APIs — HIGH RELEVANCE ⭐
**Discovery:** Multiple commercial providers offer real-time AIS (Automatic Identification System) tracking with varying coverage and latency:

**Providers:**
- **VesselFinder**: Real-time positions, voyage forecasts, ETA. Also sells raw NMEA streaming for lower latency.
- **Kpler**: ~5-second average latency, 10+ years historical AIS, satellite + terrestrial coverage. Enterprise-grade.
- **Datalastic**: Live ETA/destination + historical AIS. Reported at €99/month for full API.
- **Data Docked**: 830,000+ vessels globally, credit-based pricing, satellite + terrestrial.
- **Free alternatives**: AISstream.io (WebSocket feed), AISHub — verify current terms before relying on.

**Current Parallax state:** Uses GDELT events (text-based). No vessel position data.

**Assessment:**
- **Relevance:** HIGH — directly models shipping flow in Hormuz corridor. Complements GDELT geopolitical signals.
- **Effort:** MEDIUM — new ingestion pipeline required
- **Risk:** MEDIUM — vendor dependency, pricing verification needed
- **Recommendation:**
  - **Phase 1.5 (next 2 weeks):** Pilot VesselFinder or AISstream.io (free) on Hormuz corridor. Compare vessel positions against H3 cells with high threat_level from cascade engine. Measure:
    - Correlation between AIS vessel count drop and Hormuz flow disruption predictions
    - Latency (real-time AIS vs. next GDELT cycle)
    - Coverage gaps (terrestrial AIS only covers ~10-50km from coast)
  - **Phase 2:** If pilot shows strong correlation, integrate commercial provider (likely Kpler for lowest latency). Estimate $100-300/month for regional coverage.

**Sources:**
- [VesselFinder API Docs](https://api.vesselfinder.com/docs/)
- [Kpler Maritime Product](https://www.kpler.com/product/maritime/kplerais)
- [Datalastic Vessel Tracking](https://datalastic.com/)
- [Data Docked Maritime API](https://datadocked.com/)
- [50 Best Ship Tracking APIs 2026 — Strait of Hormuz](https://hormuzmonitor.com/50-best-ship-tracking-apis-2026/)

---

#### 3.2 GDELT Alternatives — MEDIUM RELEVANCE
**Discovery:** Newer event dataset WORLDREP (2024) shows higher accuracy than GDELT in expert-annotation tests (77.4% vs. 30.6%), but maturity and public API availability unclear.

**Other sources:** ACLED (conflict events, requires auth), UCDP (research-grade, annual updates, not real-time), World Monitor (vendor dashboard + API, paid Pro tier).

**Assessment:**
- **Relevance:** MEDIUM — WORLDREP shows promise for validation, others are slower/harder to integrate than GDELT
- **Effort:** MEDIUM-HIGH — GDELT is entrenched; switching would require revalidating all event filtering
- **Risk:** MEDIUM-HIGH — WORLDREP API availability unclear, other sources are lagged or commercial
- **Recommendation:** Monitor WORLDREP for public API release. Defer switching until Phase 2 eval shows GDELT blindspots. Continue GDELT as primary with semantic dedup already in place.

**Sources:**
- [Forecasting Future International Events: WORLDREP Dataset (arXiv 2411.14042)](https://arxiv.org/html/2411.14042v1)
- [Free Geopolitical Data APIs 2026](https://www.worldmonitor.app/blog/posts/free-geopolitical-data-apis-2026/)
- [Media in the Geopolitical Crossfire (AIB World)](https://insights.aib.world/article/66442-media-in-the-geopolitical-crossfire-identification-and-novel-data-sources-for-ib-research)

---

#### 3.3 Oil Price Data APIs — MEDIUM RELEVANCE
**Discovery:** EIA and FRED remain the authoritative free sources. Commercial alternatives (OilPriceAPI, Trading Economics) offer real-time/streaming but require paid subscriptions ($100-200+/month).

**Assessment:**
- **Relevance:** MEDIUM — current EIA/FRED sources are sufficient for Phase 1
- **Effort:** LOW — FRED API already in use
- **Risk:** LOW
- **Recommendation:** Stick with EIA/FRED for Phase 1. If Phase 2 requires futures forward curve (term structure), evaluate OilPriceAPI (free tier: 200 req/mo) or Refinitiv. EIA Short-Term Energy Outlook (STEO) is the most authoritative free forecast.

**Sources:**
- [EIA Petroleum Data](https://www.eia.gov/petroleum/data.php)
- [Best Financial Data APIs for Commodity Trading 2026](https://docs.oilpriceapi.com/blog/financial-data-api)
- [Alternatives to EIA Open Data (2026)](https://www.findmymoat.com/alternatives/eia-open-data)

---

### 4. Evaluation / MLOps

#### 4.1 Open-Source LLM Evaluation Frameworks — MEDIUM RELEVANCE
**Discovery:** DeepEval (pytest-style, 50+ metrics for agents/RAG) is the most practical open-source option. Galileo AI and SuperAnnotate offer commercial judge calibration and disagreement analysis.

**Assessment:**
- **Relevance:** MEDIUM — Parallax has custom eval. DeepEval could replace/augment it.
- **Effort:** MEDIUM — integration requires mapping Parallax prediction schema to DeepEval metrics
- **Risk:** LOW — DeepEval is stable, open-source
- **Recommendation:**
  - Evaluate DeepEval's metrics against existing Parallax eval codebase (`scoring/calibration.py`, `scoring/report_card.py`)
  - If DeepEval covers accuracy, calibration, sequence metrics with minimal code, consider adopting for Phase 2 standardization
  - DeepEval's pytest integration could replace custom test runners in Phase 1 eval cron
  - **Not urgent for Phase 1**, but flag for Phase 2 if eval complexity grows

**Sources:**
- [Top 5 Agent Evaluation Tools in 2026 (MLflow)](https://mlflow.org/top-5-agent-evaluation-frameworks/)
- [Best LLM Evaluation Frameworks in 2026 (FutureAGI)](https://futureagi.com/blog/llm-evaluation-frameworks-metrics-best-practices/)
- [8 Best Human-in-the-Loop LLM Evaluation Platforms 2026 (Braintrust)](https://www.braintrust.dev/articles/best-human-in-the-loop-llm-evaluation-platforms-2026)

---

#### 4.2 Confidence Calibration Metrics — LOW-MEDIUM RELEVANCE
**Discovery:** Previous reports identified calibration as a first-class metric (Oct 24-25 research). 2026 web search found no new papers, but confirmed tools exist: HELM benchmark includes calibration as a metric.

**Assessment:**
- **Relevance:** LOW-MEDIUM — already flagged in recent reports
- **Effort:** LOW — metrics-only, ~50 lines of Python
- **Risk:** LOW
- **Recommendation:** Implement Expected Calibration Error (ECE) in Phase 1 Week 2 (if not already done). Add per-agent calibration tracking to daily scorecard. Flag agents where confidence diverges > 15% from actual hit rate.

**Sources:**
- [HELM: A Holistic Evaluation Methodology (Stanford)](https://crfm.stanford.edu/helm/) — includes calibration, robustness, fairness metrics

---

### 5. Performance / Frontend

#### 5.1 React Real-Time Dashboard Best Practices — Already Implemented
**Discovery:** 2026 web sources confirm that Parallax's current design aligns with best practices:
- **useRef for mutable data** (avoid state churn) ✓ Already implemented
- **WebSocket batching** (100-200ms windows) ✓ Already implemented
- **Centralized connection manager** ✓ Should verify
- **Memoization** for non-live components ✓ Standard practice
- **Virtualization** for large lists — not applicable (agent feed is small)

**Assessment:**
- **Relevance:** LOW — current design is ahead of most 2026 practices
- **Effort:** N/A
- **Risk:** N/A
- **Recommendation:** No changes needed. Document WebSocket best practices in codebase for Phase 2 onboarding.

**Sources:**
- [Building Real-Time Dashboards with WebSockets and React](https://www.wildnetedge.com/blogs/building-real-time-dashboards-with-react-and-websockets)
- [Real-Time Systems for Web Developers (FreeCodeCamp)](https://www.freecodecamp.org/news/real-time-systems-for-web-developers-from-theory-to-a-live-go-react-app/)
- [WebSockets in React: Hooks, Lifecycle, and Pitfalls](https://websocket.org/guides/frameworks/react/)

---

## Top 3 Recommendations (Prioritized)

### 🎯 #1: Integrate Batch API for Eval Pipeline (Phase 1, Week 3–4)
**Why:** 50-95% cost reduction on eval cron + A/B testing. Zero risk, low effort.

**Action:**
1. Refactor `cli/brief.py --scorecard` to use Batch API for meta-agent calls (prompt suggestions, recalibration checks)
2. Keep live agent swarm on standard API (must be synchronous)
3. Ensure `cache_control` blocks are identical across all batch requests
4. Verify prompt cache TTL on Anthropic docs (resolve 60-min vs. 5-min claim)
5. Measure: cost per daily eval run before/after

**Effort:** 3-4 hours  
**Cost savings:** $30-50/month (~$400/year) on Phase 1 eval budget  
**Expected impact:** Green light for 2x/day eval runs; higher confidence in signal decisions  
**Risk:** LOW — official API, documented, no state required

---

### 🎯 #2: Pilot Real-Time Vessel Tracking (Phase 1, Week 5–6)
**Why:** Direct model of Hormuz shipping flow; complements GDELT signal coverage.

**Action:**
1. Evaluate free AIS options (AISstream.io, AISHub) for Hormuz region (Res 7-8 cells)
2. Ingest real-time vessel positions into H3 grid every 5 min
3. Compare vessel count drop against cascade engine's predicted Hormuz flow disruption
4. Measure correlation, latency, coverage gaps
5. If correlation > 0.7 and coverage sufficient, flag for Phase 2 commercial provider integration

**Effort:** 4-6 hours (integration + measurement)  
**Cost:** $0 (free tier evaluation)  
**Expected impact:** Validate cascade model against real shipping behavior; improve confidence in Hormuz disruption predictions  
**Risk:** LOW — optional integration, non-blocking for live prediction pipeline

---

### 🎯 #3: Upgrade deck.gl to v9.4 (Phase 1, Week 4)
**Why:** H3HexagonLayer performance improvements mentioned in release notes; low risk patch upgrade.

**Action:**
1. Review deck.gl v9.4 CHANGELOG for H3HexagonLayer-specific changes
2. Bump `package.json` `deck.gl` to 9.4.0+
3. Test hex map rendering with full 400K hex dataset
4. Verify no breaking changes in `H3HexagonLayer` props (highPrecision, etc.)
5. Deploy to staging first

**Effort:** 2-3 hours  
**Cost:** $0  
**Expected impact:** Smoother real-time hex updates; lower WebSocket latency spikes  
**Risk:** LOW — patch release, current design well-architected for layer updates

---

## Deferred (Phase 2+)

- **WORLDREP event dataset** — wait for public API release and Phase 1 eval results
- **Commercial Vessel Tracking (Kpler/Datalastic)** — defer until pilot phase validates model impact
- **DeepEval integration** — adopt in Phase 2 for eval standardization if complexity grows
- **Alternative oil price APIs** — stick with EIA/FRED unless Phase 2 requires futures term structure

---

## Sources

### Spatial/Geo
- [Announcing DuckDB 1.5.6](https://duckdb.org/2026/09/28/announcing-duckdb-156)
- [Awesome DuckDB Spatial](https://github.com/alperdincer/Awesome-DuckDB-Spatial/blob/main/README.md)
- [deck.gl What's New](https://deck.gl/docs/whats-new)
- [deck.gl Performance Guide](https://deck.gl/docs/developer-guide/performance)

### LLM/Agent
- [Claude Batch Processing Docs](https://platform.claude.com/docs/en/build-with-claude/batch-processing)
- [Claude Prompt Caching Docs](https://platform.claude.com/docs/en/build-with-claude/prompt-caching)
- [Anthropic API Pricing in 2026: Complete Guide](https://www.finout.io/blog/anthropic-api-pricing)
- [Claude API Cost Optimization: Caching, Batching, and 60% Token Reduction (DEV Community)](https://dev.to/whoffagents/claude-api-cost-optimization-caching-batching-and-60-token-reduction-in-production-3n49)

### Real-Time Data
- [VesselFinder API Docs](https://api.vesselfinder.com/docs/)
- [Kpler Maritime Product](https://www.kpler.com/product/maritime/kplerais)
- [Datalastic Vessel Tracking](https://datalastic.com/)
- [Data Docked Maritime API](https://datadocked.com/)
- [50 Best Ship Tracking APIs 2026 — Strait of Hormuz](https://hormuzmonitor.com/50-best-ship-tracking-apis-2026/)
- [Forecasting Future International Events: WORLDREP Dataset (arXiv 2411.14042)](https://arxiv.org/html/2411.14042v1)
- [Free Geopolitical Data APIs 2026](https://www.worldmonitor.app/blog/posts/free-geopolitical-data-apis-2026/)
- [EIA Petroleum Data](https://www.eia.gov/petroleum/data.php)
- [Best Financial Data APIs for Commodity Trading 2026](https://docs.oilpriceapi.com/blog/financial-data-api)

### Eval/MLOps
- [Top 5 Agent Evaluation Tools in 2026 (MLflow)](https://mlflow.org/top-5-agent-evaluation-frameworks/)
- [Best LLM Evaluation Frameworks in 2026 (FutureAGI)](https://futureagi.com/blog/llm-evaluation-frameworks-metrics-best-practices/)
- [8 Best Human-in-the-Loop LLM Evaluation Platforms 2026 (Braintrust)](https://www.braintrust.dev/articles/best-human-in-the-loop-llm-evaluation-platforms-2026)
- [HELM: A Holistic Evaluation Methodology (Stanford)](https://crfm.stanford.edu/helm/)

### Performance
- [Building Real-Time Dashboards with WebSockets and React](https://www.wildnetedge.com/blogs/building-real-time-dashboards-with-react-and-websockets)
- [Real-Time Systems for Web Developers (FreeCodeCamp)](https://www.freecodecamp.org/news/real-time-systems-for-web-developers-from-theory-to-a-live-go-react-app/)
- [WebSockets in React: Hooks, Lifecycle, and Pitfalls](https://websocket.org/guides/frameworks/react/)

---

**Report generated:** 2026-10-26  
**Researched by:** Claude Haiku 4.5 (Parallax Tech Scout)
