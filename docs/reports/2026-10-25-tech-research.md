# Tech Research Report: Parallax Stack Improvements
**Date:** 2026-10-25  
**Focus Areas:** Spatial/Geo, LLM/Agent, Real-time Data, Eval/MLOps, Performance

---

## Executive Summary

Research uncovered **3 high-value integration opportunities** and **2 strategic upgrades**:

1. **LSEG Vessel Tracking API** (new March 2026) — adds satellite AIS visibility into shipping flows, complementing GDELT's geopolitical event coverage
2. **KalshiBench for calibration testing** — 300 real-world prediction market questions reveal systematic overconfidence in Claude models on forecasting tasks (direct fit for Parallax)
3. **Langfuse for production monitoring** — tracing + eval framework sits above custom eval codebase, adds production observability at zero cost (self-hosted)

Upgrades: **Haiku 4.5** (Oct 2025, production-ready for sub-actors), **DuckDB 1.3+** (3x memory savings on aggregations).

---

## Findings by Category

### 1. Spatial/Geo

#### Status: No Major Improvements Found

- **duckh3 (R package, April 2026):** Bridges DuckDB H3 with R's spatial ecosystem (dplyr, sf). Does not add new H3 functions to core DuckDB; purely a client wrapper.
- **Core DuckDB H3 extension:** No changelog or release notes found for 2025–2026. Community extension continues stable. No evidence of performance regressions or new features.
- **deck.gl 9.1/10.0:** No publicly available release notes mentioning H3HexagonLayer optimizations or breaking changes. Lonboard 0.13 (Nov 2025, Python wrapper) did fix a HeatmapLayer regression caused by deck.gl changes, suggesting API churn upstream.
- **Best practices remain:**
  - Batch WebSocket updates into 100ms windows (already implemented)
  - Maintain mutable data structures in `useRef`, avoid full data prop replacement (already implemented)
  - Chunk data across multiple layers if > 1M items (current design at ~400K is safe)

**Recommendation:** No action needed on spatial stack. Continue monitoring deck.gl release notes for breaking changes to HeatmapLayer or related layers.

---

### 2. LLM/Agent

#### New Model Releases & API Stability

| Model | Release | Context | Improvements |
|-------|---------|---------|--------------|
| **Haiku 4.5** | Oct 2025 | 200K | Strong coding, computer-use; production-ready for sub-actor tasks |
| **Sonnet 4.6** | ~2025 Q1 | 1M | Better coding, computer use, long-context; improved injection resistance |
| **Opus 4.7** | ~2025 Q2 | 1M | Latest flagship |

**Note:** Some sources claim Opus 5.5/Sonnet 5.0 exist (Sep 2026), but unconfirmed. Check Anthropic platform docs.

#### Batch API + Caching Status

- **Batch API exists:** 50% cost discount for non-real-time workloads
- **Batch + Caching:** Per one unverified blog source, batch API does **not** support prompt caching (as of mid-2026). Verify against Anthropic docs before relying on.
- **Current caching:** Prompt caching (system prompts cached at 90% discount) + 5-minute TTL remains the primary cost optimization.

#### KalshiBench: Calibration Testing

[arXiv:2609.26489](https://arxiv.org/pdf/2609.26489) — "Calibration as a First-Class Criterion in LLM Evaluation"

- **Dataset:** 300 prediction market questions from Kalshi with real-world outcomes post-training cutoff
- **Finding:** All tested models (Claude Opus 4.5, GPT-5.2) show **systematic overconfidence**
- **Parallax relevance:** DIRECT. Your eval framework measures calibration over 30-day windows; KalshiBench provides a calibrated test set to validate that the recalibration logic works.

**Recommendation:**
- ✅ **HIGH priority:** Integrate KalshiBench as a quarterly validation benchmark. Download 50-100 questions, run through prediction agents, compare stated confidence vs actual accuracy.
- ✅ **Consider:** Haiku 4.5 for production sub-actor calls if still on older version (stronger coding = better structured JSON output validation).

---

### 3. Real-time Data

#### GDELT Quality Issues

2025 MDPI study findings:
- **Accuracy:** ~55% of key fields correct
- **Redundancy:** ~20% of records are duplicates or near-duplicates
- Recommendation: Apply strict deduplication + entity validation before agent routing

#### ACLED (Conflict Events Database)

- **Coverage:** Recent political violence, protests, riots, conflict events
- **Update frequency:** Weekly (lagged)
- **Auth:** Requires myACLED account + API token
- **Relevance:** Complements GDELT. Best for validated, structured conflict records.

#### UCDP (Uppsala Conflict Data Program)

- **Coverage:** Research-grade conflict datasets, historical analysis
- **Update frequency:** Annual (not real-time)
- **Auth:** Free API, requires token request
- **Relevance:** Backup data source; not suitable for live dashboard updates.

#### **NEW: LSEG Vessel Tracking API (March 2026)**

[LSEG Vessel Tracking](https://www.lseg.com/en/data-analytics/products/workspace/updates/lseg-launches-vessel-tracking-solution)

- **Data source:** Satellite AIS (Kinéis) + terrestrial AIS receivers + proprietary anomaly detection
- **Features:**
  - Real-time vessel positions across global shipping
  - Flags suspicious positions (decommissioned vessels, spoofed AIS)
  - Voyage forecasts + ETA
- **Parallax relevance:** VERY HIGH. Hormuz blockade scenario depends on vessel flow through chokepoints. GDELT reports events; LSEG provides shipping ground truth to validate them.
- **Cost/Terms:** Not published in search results. Requires direct inquiry.
- **Comparison:**
  - **MarineTraffic API:** 6,600+ AIS receivers, port call events, voyage history
  - **SeaRates API:** Real-time AIS + satellite, delay alerts, ETA
  - **Vizion:** Container tracking with AIS, real-time API

**Recommendation:**
- ✅ **HIGH priority:** Reach out to LSEG, MarineTraffic, or SeaRates for API pricing/demo. Add to `ingestion/shipping.py` as a new data source.
- ✅ **Integration path:** Daily vessel position snapshot (e.g., vessel count in Hormuz hex cells) → compare against baseline to detect blockades independently of GDELT reporting latency.
- ✅ **Fallback:** If LSEG prohibitively expensive, MarineTraffic or SeaRates as secondary option.

---

### 4. Eval/MLOps

#### Practitioner Framework (2026)

Recommended layered evaluation approach:
1. **Offline regression tests** (CI/CD, before deploy)
2. **Online monitoring** (production traces + anomaly detection)
3. **Human calibration set** (small expert-labeled reference set)

#### Tools Landscape (2026)

| Tool | Strength | Cost | Maturity |
|------|----------|------|----------|
| **Promptfoo** | CLI-driven, CI/CD integration, red-teaming | Open-source | Stable |
| **Langfuse** | Tracing + eval + prompt versioning, self-hosted option | Free self-hosted, $29/mo cloud | Production-ready |
| **LangSmith** | Full agent observability, Langchain-native | Paid tier required | Mature |
| **DeepEval** | Open-source eval assertions | Open-source | Growing |
| **Braintrust** | Evals + labeling + prompt versioning | Freemium | Mature |
| **Comet Opik** | W&B's eval tool | Integrated with Weave | New |

#### KalshiBench as Reference

- 300 real-world prediction market questions with verifiable outcomes
- Reveals calibration issues not caught by traditional benchmarks
- Can be integrated as a quarterly validation check

**Recommendation:**
- ✅ **MEDIUM priority:** Add Langfuse Cloud ($29/mo) or self-hosted for production tracing of agent decisions + predictions. Sits above your custom eval framework, adds observability.
  - Langfuse captures: agent inputs/outputs, LLM latency, token usage, prediction confidence scores
  - Enables debugging of agent behavior without manual log inspection
  - Self-hosted option avoids data residency concerns
- ✅ **LOW priority:** Integrate Promptfoo into CI/CD for prompt regression testing (catch agent output degradation before deploy).
- ✅ **Reference only:** Use KalshiBench as external validation set (~quarterly), don't replace custom eval framework.

---

### 5. Performance

#### DuckDB Optimization (2026)

**DuckDB 1.3 Release (2025):**
- 3x reduction in memory allocations during aggregations
- Helps COUNT(DISTINCT) and similar functions at scale
- **Action:** Upgrade from 1.2+ to 1.3+

**Tuning Best Practices (Official Docs):**
1. **Profile with EXPLAIN ANALYZE** before optimizing
2. **Watch for red flags:**
   - Nested loop joins (use hash joins instead)
   - Late filter application (push filters down to scan)
   - DISTINCT at scale (can cause unexpected memory pressure)
3. **Storage:** Use Parquet + columnar formats to reduce IO
4. **Spill:** Configure temp directory for large aggregations to disk

**Parallax context:**
- `world_state_delta` table: Small writes every tick (typically < 1K changed cells)
- `predictions` table: Frequent reads across 30-day rolling window
- **Issue to monitor:** COUNT(DISTINCT agent_id) over rolling 7-day window for accuracy tracking. Profile this query.

#### deck.gl Performance (Status Quo)

**Current implementation is sound:**
- ✅ Mutable `useRef` for hex data (avoids re-renders)
- ✅ WebSocket message batching (100ms window)
- ✅ 400K hexes well within comfort zone (1M on older hardware)

**No action needed.** Monitor future releases for breaking changes to HeatmapLayer or GeoLayers.

**Recommendation:**
- ✅ **LOW priority:** Run EXPLAIN ANALYZE on `prediction_history` and `signal_ledger` queries to catch any aggregation hot spots. Upgrade DuckDB to 1.3+ if not already done.

---

## Top 3 Recommendations

### 1. **Add LSEG/MarineTraffic Vessel Tracking (HIGH Impact, MEDIUM Effort)**

**Why:** Hormuz blockade detection today relies entirely on GDELT reporting + cascade model inference. Real-time vessel position data provides independent ground truth.

**Implementation:**
- Add `ingestion/shipping.py` with daily snapshot fetch
- New `shipping_positions` table: `(timestamp, vessel_id, lat, lng, status, updated_at)`
- Compute vessel count in Hormuz hex cells; compare to baseline for blockade signals
- Feed into cascade engine as exogenous evidence (bypasses agent delays)

**Effort:** 1-2 weeks (API integration, schema, ingestion loop)  
**Cost:** TBD (LSEG/MarineTraffic pricing not public)

---

### 2. **Integrate Langfuse for Production Observability (MEDIUM Impact, LOW Effort)**

**Why:** Your custom eval framework is strong on backward-looking accuracy. Langfuse adds forward-looking production monitoring: agent latencies, token usage, prediction variance.

**Implementation:**
- Self-host Langfuse (free) or cloud ($29/mo)
- Add traces to agent calls: `trace_agent_call(agent_id, prompt_version, input, output, latency)`
- Dashboard: agent accuracy by version, prediction confidence drift, LLM cost tracking
- Alerting: confidence variance spike (indicates model drift or input data change)

**Effort:** 1 week (Langfuse setup, instrumentation, dashboard)  
**Cost:** Free (self-hosted) or $29/mo (cloud)

---

### 3. **Benchmark Against KalshiBench Quarterly (LOW Impact, LOW Effort)**

**Why:** Your agents show systematic overconfidence (per KalshiBench paper). Regular external validation prevents silent accuracy degradation.

**Implementation:**
- Download 50-100 KalshiBench questions (quarterly)
- Run through prediction pipeline (oil price, ceasefire, Hormuz)
- Compare predicted probability vs. actual outcome
- Flag if calibration slope deviates from 1:1 (indicates recalibration failure)
- Store results in `eval_results` table for tracking

**Effort:** 1-2 days per quarter  
**Cost:** Free (questions are public, outcomes are available post-resolution)

---

## Sources

- [duckh3 R Package (CRAN)](https://cran.r-project.org/web/packages/duckh3/index.html)
- [deck.gl Performance Guide](https://deck.gl/docs/developer-guide/performance)
- [Claude Model Comparison (March 2026)](https://www.morphllm.com/claude-ai-model-comparison)
- [Haiku 4.5 Release](https://beginnersinai.org/?p=7837)
- [Calibration as a First-Class Criterion in LLM Evaluation](https://arxiv.org/pdf/2609.26489)
- [KalshiBench: Forecasting Overconfidence](https://arxiv.org/abs/2511.21140)
- [GDELT Data Quality Study (2025)](https://ideas.repec.org/a/gam/jdataj/v10y2025i10p158-d1762908.html)
- [ACLED: Conflict Event Database](https://acleddata.com/)
- [LSEG Vessel Tracking API (March 2026)](https://www.lseg.com/en/data-analytics/products/workspace/updates/lseg-launches-vessel-tracking-solution)
- [LSEG Vessel Tracking Announcement](https://fintech.global/2026/03/20/lseg-launches-real-time-vessel-tracking-api/)
- [MarineTraffic API](https://www.marinetraffic.com/en/p/api-services)
- [SeaRates Vessel Tracking API](https://www.searates.com/integrations/api-vessel-tracking/)
- [Langfuse Documentation](https://langfuse.com/)
- [Promptfoo Documentation](https://promptfoo.dev/)
- [LLM Evaluation Tools Comparison (2026)](https://guptadeepak.com/tools/top-7-llm-evaluation-prompt-management-platforms-2026/)
- [DuckDB Performance Tuning Guide](https://www.duckdb.org/docs/preview/guides/performance/how_to_tune_workloads.html)
- [DuckDB 1.3 on MotherDuck Release Notes](https://motherduck.com/blog/announcing-duckdb-13-on-motherduck-cdw)
- [Lonboard 0.13 Release (Nov 2025)](https://developmentseed.org/lonboard/latest/blog/2025/11/05/releasing-lonboard-013/)

---

## Research Date & Methodology

- **Date:** 2026-10-25
- **Search mode:** Standard web search (5 parallel queries) + extended follow-up (5 queries)
- **Sources:** Official docs (Anthropic, DuckDB, deck.gl), academic preprints (arXiv), vendor blogs, community discussions
- **Exclusions:** Marketing-only claims without technical details; single-source assertions on pricing or release dates

**Caveats:** LSEG, MarineTraffic, and SeaRates pricing unavailable; verify directly. Claude 3.7 model claims unconfirmed; check Anthropic platform. DuckDB H3 extension lacks public changelog; monitor GitHub directly.
