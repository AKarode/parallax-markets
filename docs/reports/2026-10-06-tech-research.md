# Daily Tech Research Report — 2026-10-06

**Parallax Geopolitical Simulator — Technology Stack Improvements**

---

## Research Focus Areas

1. **Spatial/Geo Technologies** — H3 updates, DuckDB spatial extensions, visualization alternatives
2. **LLM/Agent Frameworks** — Claude API improvements, prompt caching, agent orchestration
3. **Real-time Data Sources** — GDELT alternatives, AIS tracking, commodity price feeds
4. **Eval/MLOps** — Calibration frameworks, prompt evaluation, A/B testing for LLM
5. **Performance** — DuckDB optimization, WebSocket libraries, React rendering for real-time dashboards

---

## Findings by Category

### 1. SPATIAL/GEO TECHNOLOGIES

#### H3 Library Updates (4.5.0, May 2026)
- **Relevance:** MEDIUM | **Integration:** Easy | **Risk:** Low
- Latest upstream H3.js 4.5.0 and duckh3 R package (v0.1.0) provide stable H3 operations.
- Current stack (h3-js 4.1+) is sufficient; no value in upgrading to 4.5.0 for frontend hex visualization.
- **Verdict:** No action required. Current stack stable.

#### DuckDB Spatial H3 Extension
- **Relevance:** HIGH | **Integration:** Medium | **Risk:** Low
- DuckDB 1.3.0+ now provides native H3 functions via duckh3 extension (cell_to_latlng, latlng_to_cell, parent/child operations).
- Enables direct H3 spatial joins in SQL queries, eliminating Python H3 wrapping for cascade engine operations.
- Enables faster chokepoint zone aggregation and spatial cell-based queries.
- **Action:** Test `DuckDB H3::cell_to_latlng()`, `DuckDB H3::latlng_to_cell()` in cascade engine to reduce Python compute.

#### deck.gl Alternatives
- **Relevance:** LOW | **Integration:** Hard | **Risk:** Medium
- No compelling alternatives emerged (2026 landscape). Mapbox GL and MapLibre GL remain paired with deck.gl.
- **Verdict:** deck.gl + MapLibre GL stack is optimal for 400K+ hex grid visualization. No switch warranted.

---

### 2. LLM/AGENT TECHNOLOGIES

#### Claude API Prompt Caching & Batch Processing (2026)
- **Relevance:** HIGH | **Integration:** Easy | **Risk:** Low
- Prompt caching: 10x cheaper cached tokens vs. fresh, 5-minute TTL per conversation.
- Batch API improvements enable asynchronous request grouping.
- **For Parallax:** CRITICAL UPGRADE. Current 3 Sonnet calls per run (~$0.02) can halve cost via caching:
  - Cache system prompt + market data context between runs
  - Cache news article summaries if articles reused
  - Achieves: sub-$0.01 per run, 60-80% latency reduction on familiar scenarios
  - Budget impact: Could unlock real intraday runs instead of daily-only (currently $20/day cap).
- **Implementation:** Use `cache_control={"type": "ephemeral"}` in system prompt headers, cluster requests within 5-min windows.
- **Timeline:** 2 hours to implement, deploy in Week 1.

#### Claude 4 Opus Structured Output
- **Relevance:** MEDIUM | **Integration:** Easy | **Risk:** Low
- Claude 4 Opus now guarantees JSON schema compliance via structured output mode.
- Current `PredictionOutput` dataclass parsing is solid; structured output is incremental improvement.
- **Verdict:** Minor upgrade unless parsing edge cases encountered. Defer unless pattern failures arise.

#### Agent Orchestration Alternatives (2026 Landscape)
- **Relevance:** MEDIUM | **Integration:** Medium | **Risk:** Medium
- **Trend:** LangGraph (static graphs) declining; CrewAI (roles/tasks), Pydantic AI (type-safe), Mastra (TypeScript-first) rising.
- **For Parallax:** Not currently using an agent framework (direct API calls). Evaluation:
  - **CrewAI:** Only if multi-agent role reasoning desired. Overkill for 3 focused models.
  - **Pydantic AI:** Good fit if migrating to async Pydantic validation throughout. Cleaner than current manual approach.
  - **Recommendation:** Stick with direct Claude calls + manual cascade logic. Agent frameworks add latency + complexity not justified for current use case.
- **Verdict:** No migration recommended for Phase 1. Revisit in Phase 2 if multi-model reasoning complexity increases.

---

### 3. REAL-TIME DATA SOURCES

#### GDELT Alternatives & Supplements (2026)
- **Relevance:** MEDIUM | **Integration:** Easy | **Risk:** Low
- **New players:** EventRegistry (academic-grade, multi-lingual), ACLED (conflict-specific), WorldMonitor (AI-powered aggregation).
- **GDELT status:** Still dominant but GDELT Cloud (hourly clustered stories + entities) preferable to current free DOC API (rate-limited, frequent 429 errors).
- **For Parallax:**
  - **Immediate upgrade:** Migrate from GDELT DOC API to GDELT Cloud (hourly updates). More reliable, structured entities, fewer rate-limit failures.
  - **Supplement:** EventRegistry for non-English crisis coverage (Arabic news on Iran). Better precision for secondary sources. Caveat: ~24h lag, suitable for calibration not live trading.
  - **Timeline:** 1 hour to migrate to GDELT Cloud.

#### LSEG Vessel Tracking API (Launched March 2026)
- **Relevance:** MEDIUM | **Integration:** Hard | **Risk:** Medium
- Real-time AIS from 3,400+ receiver stations + 25 satellite constellation. Validates anomalous signals (spoofed/ghost vessels).
- **For Parallax:** Excellent proxy for Hormuz reopening prediction. But:
  - Expensive enterprise API (~$5K+/month estimated).
  - Requires custom integration.
  - Data already implicit in oil price swings + insurance market signals.
- **Verdict:** DEFER. Use market proxies (insurance quotes, tanker spot rates) instead. Revisit if edge-finding requires direct Strait vessel monitoring.

#### Oil Price Data Beyond EIA (2026)
- **Relevance:** MEDIUM | **Integration:** Easy | **Risk:** Low
- **OilPriceAPI:** REST + WebSocket, 15+ grades (Brent, WTI, Dubai, OPEC), updates every 5 minutes. $29/month entry tier, free trial available.
- **Refinitiv Eikon:** Enterprise commodity feed, $12-22K/year + API premium. Overkill for current phase.
- **For Parallax:**
  - EIA remains free, reliable, sufficient for daily predictions.
  - OilPriceAPI worth evaluation for **intraday runs** (5-min updates vs. daily EIA). ~$350/year is negligible vs. $20/day budget.
  - **Action:** Add OilPriceAPI WebSocket fallback for intraday edge detection during Hormuz crisis window (April 7-21 2026).
  - **Timeline:** 2 hours to implement.

---

### 4. EVAL/MLOPS TECHNOLOGIES

#### LLM Calibration Frameworks (2026 Research Boom)
- **Relevance:** HIGH | **Integration:** Medium | **Risk:** Low
- **"Metacognitive Probe"** (May 2026): 5-dimensional calibration diagnostics. Standard metrics: Expected Calibration Error (ECE) + Brier Score. Production targets: Cohen's kappa >0.6 vs. human labels, >0.8 strong.
- **For Parallax:** CRITICAL for edge-finding. Current prediction models lack calibration audit:
  - Current state: No calibration tracking. Probabilities are point estimates.
  - **Action:** Implement ECE tracking in `scoring/calibration.py`. Bucket predictions (0-10%, 10-20%, etc.), compute actual hit rate per bucket, flag over/under-confidence.
  - **Impact:** Reveals if model is overconfident (e.g., 80% predictions only correct 60% of time). Direct feedback loop for prompt tuning.
  - **Timeline:** 4 hours to implement and integrate.

#### Prompt Evaluation Frameworks (2026 Maturity)
- **Relevance:** HIGH | **Integration:** Easy | **Risk:** Low
- **Promptfoo** (open-source, free): Local eval, CI/CD native, red-teaming. No cloud dependency.
- **Parea AI** ($150/month): Cloud observability, human review workflows, production monitoring.
- **LangSmith/Langfuse:** Tightly integrated with LangGraph (less relevant for Parallax).
- **For Parallax:**
  - **Immediate:** Add Promptfoo to CI pipeline. Create eval set of recent news + ground-truth market outcomes. Run before each model update.
  - **Example eval:** "Suleimani assassination → oil +5% → ceasefire prob. 15%" — test both old and new prompts.
  - **Cost:** $0 (open-source). **Effort:** 2-3 hours setup.
  - **Mid-term:** Parea AI if paper trading edge widens (production observability of signal quality vs. market prices).
  - **Timeline:** 3 hours to set up baseline eval suite.

#### A/B Testing for LLM Prompts (2026 Playbook)
- **Relevance:** HIGH | **Integration:** Medium | **Risk:** Low
- **2026 standard:** MDE (minimum detectable effect), sample sizing, bootstrap CIs, matched pairs, bandit algorithms.
- **For Parallax:**
  - Current state: No A/B testing. Prompt iteration is manual.
  - **Action:** Use Promptfoo to establish baseline performance. Then:
    1. Keep a control prompt (current best).
    2. Test 2-3 variants on same eval set (recent news + ground-truth resolutions).
    3. Measure: hit rate, calibration, divergence magnitude.
    4. Only deploy variant if improvement is real (bootstrap CI excludes zero).
  - **Timeline:** Feasible before April 7 ceasefire window (implementation + 2 weeks baseline).

---

### 5. PERFORMANCE TECHNOLOGIES

#### DuckDB Optimization for 400K+ Rows (2026)
- **Relevance:** MEDIUM | **Integration:** Easy | **Risk:** Low
- **Key optimization:** Row group size. DuckDB 1.3.0+ ships 2x faster Top-N for LIMIT queries (up to 250K rows). Parallelism starts at 122K row threshold per thread.
- **For Parallax:** signal_ledger + prediction_log will hit 400K rows by mid-May (daily runs + paper trades).
  - Current config: Acceptable but can improve.
  - **Actions:**
    - Ensure row groups >100K (default in DuckDB, check config).
    - Use LIMIT aggressively in dashboard queries (pagination on frontend).
    - Out-of-core processing works but slower—keep in-memory if possible (400K rows ≈ 40-50MB, negligible memory).
  - **Timeline:** 1 hour audit of current schema + queries.

#### WebSocket Libraries (2026 Ecosystem)
- **Relevance:** LOW | **Integration:** Varies | **Risk:** Low
- **ws** (~80M/week npm downloads): Minimal, fast. Default for Node.js. Best-in-class.
- **Socket.IO** (~10M/week): High-level with fallback + rooms. Good for teams.
- **uWebSockets.js**: 5-10x throughput, C++ bindings, complex. Overkill for typical workloads.
- **For Parallax:** Currently using `ws`. This is the right choice.
  - uWebSockets.js unnecessary (won't have 10K concurrent connections).
  - **Verdict:** Keep current stack. No migration needed.

#### React Real-time Dashboard Optimization (2026)
- **Relevance:** MEDIUM | **Integration:** Medium | **Risk:** Low
- **Key techniques:** Pagination + infinite scroll, React virtualization (windowing), useMemo/useCallback memoization, Canvas rendering (Chart.js) for 1M+ points.
- **Libraries:** ECharts for 100K+ points; Recharts for smaller datasets.
- **For Parallax:**
  - Current dashboard (React + Vite + MapLibre + deck.gl) is solid.
  - If signal_ledger grows to 100K+ trades:
    - Add virtualization to trade table (react-window).
    - Consider ECharts for P&L chart if edge widens (many trades → large dataset).
    - Debounce/throttle WebSocket updates (50ms batching).
  - **Timeline:** 3-4 hours to implement virtualization + memoization if needed.

#### Server-Sent Events vs. WebSockets (2026 Analysis)
- **Relevance:** MEDIUM | **Integration:** Easy | **Risk:** Low
- **2026 consensus:** SSE covers 80% of "real-time" use cases. Simpler than WebSockets for server→client unidirectional updates.
- **For Parallax:**
  - Current: WebSocket for live dashboard updates (trades, market prices). Good choice for bidirectional.
  - **Alternative:** SSE for notifications (new signal, large divergence detected). Lower overhead, easier ops.
  - **Action:** Keep WebSocket for streaming market data/chart updates. Add SSE endpoint for alert notifications if needed (trivial addition).
  - **Timeline:** 2 hours if implemented.

---

## Top 3 Recommendations (Highest ROI Before April 2026)

| Priority | Action | Effort | Payoff | Timeline |
|----------|--------|--------|--------|----------|
| 🔴 **HIGH** | Implement Claude prompt caching (system prompt + context) | 2 hours | 50% cost cut, 60% latency reduction | Week 1 |
| 🔴 **HIGH** | Add ECE calibration tracking to scoring module | 4 hours | Validate edge quality, debug model bias | Week 2 |
| 🟠 **MEDIUM** | Set up Promptfoo eval pipeline + baseline | 3 hours | Prompt iteration via data, not intuition | Week 2 |

### Recommendation #1: Claude Prompt Caching
**Why:** 50% cost reduction on LLM calls unlocks intraday runs instead of daily-only. System prompt (3K tokens) is static and high-frequency; perfect caching candidate.
**How:** Add `cache_control={"type": "ephemeral"}` to system prompt headers in `prediction/oil_price.py`, `prediction/ceasefire.py`, `prediction/hormuz.py`. Cluster requests within 5-min windows.
**Impact:** $20/day budget → $10/day, enabling real-time edge detection during crisis events.

### Recommendation #2: ECE Calibration Tracking
**Why:** Edge-finding depends on trustworthy confidence scores. Current model has no calibration audit—may be overconfident (claiming 0.8 when actual is 0.6).
**How:** Implement Expected Calibration Error (ECE) in `scoring/calibration.py`. Bucket predictions by confidence level, compute actual hit rate per bucket, flag divergences.
**Impact:** Direct feedback loop: "Your 0.8 predictions are only 60% correct → revise prompt to be more conservative."

### Recommendation #3: Promptfoo Evaluation Pipeline
**Why:** Prompt iteration is currently manual and intuitive. Data-driven A/B testing with Promptfoo (free, open-source) closes the loop.
**How:** Create eval set of 20-30 recent news events + ground-truth market outcomes. Integrate into CI pipeline. Before deploying any prompt version, run both old and new against eval set.
**Impact:** Confidence that prompt changes improve performance (not luck). Enables rapid iteration during April ceasefire window.

---

## Bonus: Candidate Quick Wins

| Action | Effort | Payoff | Timeline |
|--------|--------|--------|----------|
| Migrate GDELT DOC API → GDELT Cloud (hourly) | 1 hour | Fewer 429 errors, structured entities | Week 1 |
| Add OilPriceAPI WebSocket fallback (intraday) | 2 hours | Intraday edge detection (5-min updates) | Week 3 |

---

## Sources

- [H3 Library Updates 2026](https://ubuntuupdates.org/package/postgresql/jammy-pgdg/main/base/libh3-1)
- [DuckDB H3 Extension](https://cidree.r-universe.dev/duckh3/doc/manual.html)
- [DuckDB Performance Optimization](https://duckdb.org/docs/current/guides/performance/how_to_tune_workloads.html)
- [Claude API 2026 Cache Pricing](https://www.tkmxai.it.com/claude-api-cache-pricing-in-2026-7)
- [Best LangGraph Alternatives 2026](https://futureagi.com/blog/best-langgraph-alternatives-2026/)
- [Agent Orchestration Frameworks CTO Guide](https://articles.firstaimovers.com/articles/langgraph-vs-langchain-crewai-autogen-2026/)
- [Free Geopolitical Data APIs 2026](https://www.worldmonitor.app/blog/posts/free-geopolitical-data-apis-2026/)
- [GDELT vs EventRegistry Comparison](https://ojs.aaai.org/index.php/ICWSM/article/view/14763)
- [LSEG Launches Real-time Vessel Tracking API](https://fintech.global/2026/03/20/lseg-launches-real-time-vessel-tracking-api/)
- [Oil Price API Documentation](https://docs.oilpriceapi.com/blog/financial-data-api)
- [Metacognitive Probe: LLM Calibration Diagnostics](https://arxiv.org/pdf/2605.09844)
- [Prompt Evaluation Frameworks Parea vs Promptfoo](https://www.respan.ai/market-map/compare/parea-ai-vs-promptfoo)
- [A/B Testing LLM Prompts Best Practices 2026](https://futureagi.com/blogs/ab-testing-llm-prompts-best-practices-2026)
- [WebSocket Libraries Best Practices 2026](https://pkgpulse.com/guides/socketio-vs-ws-vs-uwebsockets-websocket-servers-nodejs-2026)
- [How to Render Large Datasets in React](https://www.syncfusion.com/blogs/post/render-large-datasets-in-react)
- [Server-Sent Events vs WebSockets 2026](https://www.alexcloudstar.com/blog/server-sent-events-vs-websockets-2026/)

---

**Report Compiled:** 2026-10-06  
**Next Review:** 2026-10-13
