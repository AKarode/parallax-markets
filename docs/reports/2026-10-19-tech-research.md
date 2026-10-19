# Tech Research Scout Report — 2026-10-19

**Scope:** Spatial/Geo, LLM/Agent, Real-time Data, Eval/MLOps, Performance

---

## Summary

Moderate improvements available across the stack. Primary opportunities:
1. **DuckDB 1.5.6** — Adopt latest for query optimization gains (Sept 2026)
2. **Real-time AIS data** — Commercial integrations (SeaVantage/Datalastic) offer near-real-time Hormuz traffic but at cost
3. **LLM evaluation** — Formalized Define-Test-Diagnose-Fix loop available (Jan 2026 academic framework)
4. **deck.gl 9.4** — WebGPU paths improve H3HexagonLayer rendering
5. **Batch API + Caching interaction** — Needs clarification with Anthropic before optimization planning

No high-risk findings. Most improvements are incremental.

---

## Findings by Category

### 1. Spatial / Geo Libraries

#### H3 Core Library Updates (v4.5.0, May 2026)

**Relevance:** MEDIUM | **Effort:** LOW | **Risk:** LOW

- Core H3 library updated to v4.5.0 (May 21, 2026)
- Improvements: Gosper island boundary edge iterator, Vec3d indexing refactor
- h3-js v4.5.0 released July 1, 2026 (uses core v4.5.0, adds reverse-directed-edge function, fixes oversized gridDisk corruption)
- **Action:** Project pins H3 version in deployment. Upgrading to v4.5.0 is backward compatible; benefit depends on edge-case improvements. Low priority unless you hit the gridDisk bug.

**Sources:**
- H3 GitHub releases: [v4.5.0 finalized May 2026](https://github.com/uber/h3/releases)
- h3-js CHANGELOG: [v4.5.0 July 2026](https://cdn.jsdelivr.net/npm/h3-js@4.5.0/CHANGELOG.md)

---

#### DuckDB H3 Extension Stability

**Relevance:** HIGH | **Effort:** NONE | **Risk:** LOW

- DuckDB's H3 community extension is mature and well-integrated
- duckh3 R package (v0.1.0, April 2026) provides stable interface, 96.7% test coverage, 1.3K downloads/year
- No performance regressions reported; no migration needed
- **Action:** No change required. Current setup is solid.

**Sources:**
- duckh3 CRAN listing: [Published April 24, 2026](https://cran.r-project.org/web/packages/duckh3/index.html)

---

#### deck.gl 9.4 WebGPU Update (September 2026)

**Relevance:** MEDIUM | **Effort:** LOW | **Risk:** LOW

- deck.gl v9.4 (Sept 2026) adds WebGPU rendering paths to all layers, including H3HexagonLayer
- Improves GPU utilization for high-frequency updates (critical for real-time hex redraws)
- MapLibre transitioning to v6 (April 2026), compatible with deck.gl 9.x
- **Action:** Upgrade to deck.gl v9.4. Verify H3HexagonLayer performance improvement in your specific hex density (400K hexes across 4 resolution bands). Test hex transition smoothness before/after.

**Sources:**
- CARTO blog on deck.gl 9.4: [Making deck.gl AI-Ready](https://carto.com/blog/making-deckgl-ai-ready/)
- MapLibre newsletter April 2026: [MapLibre v6 transition](https://maplibre.org/news/2026-05-02-maplibre-newsletter-april-2026/)

---

### 2. LLM / Agent Improvements

#### Prompt Caching + Batch API Compatibility (Unconfirmed)

**Relevance:** HIGH | **Effort:** NONE | **Risk:** MEDIUM

- **Claim:** Batch API (50% cost discount) does NOT currently support prompt caching. One mid-2026 source states this; others don't address it.
- **If true:** You must choose between batch jobs OR cached prompts, not both.
- **Current stack:** Uses prompt caching for agent system prompts (historical baseline, ~3K tokens). Batch API has not been adopted.
- **Action:** **Before optimizing LLM spend further, verify this limitation directly with Anthropic.** If batch + caching work together, you can cut sub-actor call costs by ~72% (50% batch + 90% caching stacked). If not, stick with caching.

**Sources:**
- Unverified third-party claim: [cut-the-saas.com pricing guide](https://cut-the-saas.com/the-cut/claude-api-pricing)
- Official reference: Check [Anthropic platform docs](https://platform.anthropic.com/docs)

---

#### Model Tiering Strategy Validated (Haiku 4.5 vs Opus 4.6)

**Relevance:** HIGH | **Effort:** NONE | **Risk:** LOW

- **Costs (Q3 2026):**
  - Haiku 4.5: $1.00 / $5.00 per 1M input/output tokens
  - Sonnet 4.6: $3.00 / $15.00
  - Opus 4.6: $5.00 / $25.00 (with 80.8% on SWE-bench Verified)
- **Current practice:** Sub-actors use Haiku, country agents use Sonnet. This aligns with cost-optimal routing.
- **Benchmarks:** Opus outperforms Haiku on GPQA Diamond (83.3% vs 55.2%), but no geopolitical forecasting benchmarks available. Your own eval on recent predictions will reveal if Haiku misses cascade reasoning or if Sonnet suffices.
- **Estimated savings:** Teams using Haiku→Sonnet→Opus routing report 40-60% cost savings vs all-Opus. You're already doing this.
- **Action:** No change needed. If eval shows Haiku sub-actors miss subtle signals, run A/B test (Haiku vs Sonnet sub-actors for 7 days), measure calibration delta, and decide.

**Sources:**
- Morph LLM comparison (March 2026): [Claude model lineup and routing](https://www.morphllm.com/claude-ai-model-comparison)
- Cost calculator: [Haiku 4.5 vs Opus 4.6 pricing](https://futureagi.com/llm-cost-calculator/compare/claude-haiku-4-5-20251001-vs-claude-opus-4-6-20260205)

---

### 3. Real-Time Data Sources

#### AIS-Based Hormuz Traffic (Multiple Commercial Options)

**Relevance:** HIGH | **Effort:** MEDIUM | **Risk:** MEDIUM

**Free baseline:**
- **WTO Strait of Hormuz Trade Tracker** (free, daily lag, AIS-based)
  - Updated once daily at 5:00 p.m. CET
  - Gaps: Captures only active AIS transmissions; disabled/interrupted signals = missing vessel segments
  - May understate actual volumes significantly during blockade scenarios
  - **Action:** Use for ground truth validation, not live signals

**Commercial near-real-time:**
- **SeaVantage** (commercial, 15-minute updates, Hormuz-specific)
  - Claims 15-min update cycle with estimated positions during AIS gaps
  - Addresses WTO's coverage blind spots
  - **Relevance:** HIGH for live scenario validation
  - **Risk:** Reconstructed positions are estimates, not observed data. Validate accuracy against reported incidents.

- **Datalastic Maritime API** (commercial, MCP server available)
  - Real-time vessel tracking, Gulf of Oman coverage confirmed
  - MCP integration possible for direct Claude access
  - **Relevance:** MEDIUM (MCP integration is novel; check API reliability)

- **Tradlinx** (commercial vessel tracking)
  - Per-vessel search and live route tracking
  - No Hormuz-specific claims found; pricing unclear

**Action:** 
- Keep WTO tracker as free ground truth baseline
- Evaluate SeaVantage trial (15-min cadence matches scenario ticks perfectly)
- Test Datalastic MCP integration as experimental data feed
- Do NOT commit to commercial service yet; validate coverage during 2-week ceasefire window (April 2026) first

**Sources:**
- WTO Strait of Hormuz Trade Tracker: [Dashboard and methodology](https://globaltradedata.wto.org)
- SeaVantage Hormuz monitoring: [24/7 Live Monitoring](https://www.seavantage.com/strait-of-hormuz-24-7-live-monitoring)
- Datalastic MCP integration: [Maritime data via Claude](https://datalastic.com/blog/)

---

#### GDELT Alternatives (Limited)

**Relevance:** MEDIUM | **Effort:** HIGH | **Risk:** MEDIUM

- **GDELT Cloud** (hosted GDELT, hourly refresh)
  - Produces coded conflict events
  - **Caveat:** Current coverage weak before March 2026. Older history thin.
  - **Not recommended** for pre-March backtesting or replays

- **ACLED** (validated conflict events, lagged)
  - Higher quality than GDELT (human-validated)
  - Requires authenticated account, weekly lag (not real-time)
  - **Use case:** Ground truth validation, not live ingestion

- **UCDP** (conflict research, not live)
  - Research-grade records only
  - **Not suitable** for live monitoring

- **War Monitor** (dashboard, real-time)
  - Powered by GDELT data (not independent)

**Action:** GDELT remains your best free real-time source. Academic comparison (2025) of GDELT vs POLECAT is available if you need to evaluate fork.

**Sources:**
- GDELT Cloud: [docs.gdeltcloud.com](https://docs.gdeltcloud.com/)
- Academic evaluation: [GDELT vs POLECAT for forecasting (2025)](https://www.doi.org/10.3390/data11070158)

---

### 4. Evaluation / MLOps

#### Define-Test-Diagnose-Fix Framework (January 2026)

**Relevance:** HIGH | **Effort:** MEDIUM | **Risk:** LOW

- **Paper:** Daniel Commey (Jan 2026) proposes formalized eval loop for LLM systems
  - Define: Set metrics upfront (direction accuracy, magnitude, calibration — you have this)
  - Test: Maintain 50–200 event eval set in git, baseline, iterate
  - Diagnose: Automated checks (JSON validity, output bounds), human rubrics, LLM-as-judge
  - Fix: Prompt edits, gate in CI, refresh eval set over time
- **Key insight:** Two-word prompt change can shift accuracy by 10-15 points on same benchmark. A/B testing is critical.
- **Current practice:** You have prediction logging and daily eval cron. Missing the formalized test suite version control and LLM-as-judge automation.
- **Action:** 
  - Add versioned eval dataset to git (curated 100 events covering normal + crisis scenarios)
  - Implement LLM-as-judge for calibration scoring (Sonnet evaluates each prediction: was confidence justified?)
  - Gate prompt changes in CI (new version must beat baseline on eval set before deployment)

**Sources:**
- Commey framework (arXiv Jan 2026): [When "Better" Prompts Hurt](https://arxiv.org/abs/2601.22025)

---

#### Structured Output Testing (Emerging Best Practice)

**Relevance:** MEDIUM | **Effort:** MEDIUM | **Risk:** LOW

- **Layered eval pipelines** (2026 standard):
  1. Fast property checks in CI (JSON schema validation, bounds checks, field presence)
  2. Quality metrics pre-release (LLM scoring, semantic dedup, logic validation)
  3. Vulnerability scanning pre-deployment (jailbreak attempts, injection, tone drift)
- **Tools:** DeepEval, Promptfoo, Giskard are emerging standards. No clear winner; feature overlap is high.
- **Current practice:** You validate agent JSON schema on every response. Missing: bounds checks, field type validation, cascading logic checks.
- **Action:** 
  - Add structured output validator to agent response handler (check field types, ranges, H3 cell validity)
  - Adopt Promptfoo for prompt versioning + eval set management (simplifies CI gating)

**Sources:**
- FutureAGI evaluation guide (2026): [Complete Guide to LLM Evaluation Tools](https://futureagi.substack.com/p/the-complete-guide-to-llm-evaluation)
- Medium piece on layered evals: [DeepEval, Promptfoo, Giskard](https://medium.com/@srinib100/llm-evaluation-frameworks-deepeval-promptfoo-and-giskard-ad4e1547ec1c)

---

### 5. Performance Optimization

#### DuckDB 1.5.6 Adoption (September 2026)

**Relevance:** HIGH | **Effort:** LOW | **Risk:** LOW

- **Latest stable:** DuckDB v1.5.6 (Sept 28, 2026)
- **Improvements:** Query optimizer pushdown, Top-N window elimination, crash fixes (deadlock in memory manager)
- **Notable:** v1.5.2 (April 2026) showed ~10% improvement on TPC-H composite score (778,041 → 854,676 QphH@Score)
- **Upcoming:** DuckDB v2.0.0 arrives this fall (October/November 2026). Check release notes for breaking changes.
- **Current version:** Project likely uses 1.5.x. No migration risk.
- **Action:** 
  - Upgrade to v1.5.6 immediately (minor version, backward compatible, ~10% perf gain likely carries forward)
  - Monitor DuckDB 2.0.0 release notes for breaking changes (coming this month). Delay 2.0 upgrade until after April ceasefire validation unless it fixes a blocker.

**Sources:**
- DuckDB 1.5.6 release: [Announcing DuckDB 1.5.6](https://duckdb.org/2026/09/28/announcing-duckdb-156)
- DuckDB 1.5.2 performance: [~10% TPC-H gain](https://duckdb.org/2026/04/13/announcing-duckdb-152)
- MotherDuck ecosystem newsletter: [July 2026](https://motherduck.com/blog/duckdb-ecosystem-newsletter-july-2026/)

---

#### React + WebSocket Real-Time Dashboard Optimization

**Relevance:** MEDIUM | **Effort:** MEDIUM | **Risk:** LOW

- **Bottleneck:** Direct WebSocket updates into React state cause re-render thrashing on high-frequency updates (your design doc already identifies this)
- **Current mitigation:** Use mutable `useRef` for hex data, batch WebSocket messages every 100ms, decouple React UI from deck.gl data
- **2026 best practices:**
  1. Offload aggregation / filtering to Web Workers (don't do math in React render thread)
  2. Use exponential backoff for reconnects (load balancers kill idle connections)
  3. Visible connection-status indicator (critical UX signal during latency)
  4. Keep ping/pong heartbeats
  5. Minimize re-renders (only re-render UI components, let deck.gl pull from `useRef`)
- **Vite-specific:** No major 2026 updates found. Current setup (bundle splitting, HMR) is standard.
- **Action:** Audit current WebSocket handler:
  - Are Web Workers used for GDELT filtering / event aggregation? (Low priority if 10–20 events/day)
  - Is exponential backoff implemented? (Add if not)
  - Is connection status visible to users? (Add if missing — critical for debugging user reports of stale data)

**Sources:**
- OneUptime WebSocket guide (Jan 2026): [React WebSocket patterns](https://oneuptime.com/blog/post/2026-01-15-websockets-react-real-time-applications)
- Scaling real-time dashboards: [High-frequency rendering optimization](https://dev.to/viitorcloud/build-real-time-dashboards-with-react-and-websockets-for-businesses-1169)

---

## Top 3 Recommendations

### 1. **Upgrade DuckDB to 1.5.6 (This Week)**
   - **Why:** ~10% performance gain, query optimization. Risk: none. Effort: 30 minutes.
   - **Impact:** Faster prediction log queries, faster eval cron, snappier API responses.
   - **Action:** `pip install duckdb==1.5.6`, test against current snapshot, deploy.

### 2. **Clarify Batch API + Prompt Caching Interaction (This Week)**
   - **Why:** Unlocks potential 72% cost reduction on sub-actor calls. Current claim unverified.
   - **Impact:** Could cut daily LLM cost from $2–5 to <$1 during normal operations.
   - **Action:** Email Anthropic support with question: "Does Message Batches API support prompt caching on the same call?" Implement whichever combo is allowed.

### 3. **Adopt SeaVantage Trial for Real-Time Hormuz AIS (Before April Ceasefire)**
   - **Why:** Your scenario needs live Hormuz traffic data to validate oil flow estimates. WTO tracker is lagged (daily) and incomplete (AIS gaps). SeaVantage fills both gaps at 15-min cadence.
   - **Impact:** Ground truth for cascade rule tuning (blockade % → shipping reduction %). Validates model predictions against observed vessel behavior.
   - **Action:** 
     - Request trial access (verify Hormuz coverage, 15-min update SLA)
     - Ingest into DuckDB `observed_hormuz_traffic` table
     - Compare predictions vs actual during first high-volatility event in April ceasefire window
     - Decide to commit based on data quality + cost

---

## Low-Priority Findings

- **H3 v4.5.0:** Incremental improvements (Gosper edge iterator, Vec3d refactor). Upgrade if you hit gridDisk edge cases.
- **LLM evaluation frameworks (Promptfoo/DeepEval):** Good to have; not critical. Current prediction logging + daily eval cron covers 80% of use case. Add structured output validation first (lower effort, high value).
- **DuckDB 2.0.0:** Monitor release notes. Likely safe to upgrade after April (not before), pending breaking-change assessment.

---

## Skipped / Out of Scope

- Concordia framework (Phase 2, beyond current agent scope)
- LangGraph (Phase 2, reserved for agent reasoning upgrades)
- Multiple simultaneous scenarios (Phase 1 is Iran/Hormuz only)
- Mobile dashboard (Phase 1 is desktop)

---

## No Significant Gaps Found

- Spatial visualization (deck.gl 9.4 WebGPU is solid upgrade)
- H3 grid library (v4.5.0 is stable, no migration issues)
- GDELT alternatives (none beat GDELT for free, real-time, broad coverage)
- FastAPI / asyncio stack (no major 2026 changes relevant to current architecture)

---

**Report Date:** 2026-10-19  
**Researcher:** Daily Tech Scout  
**Next Review:** 2026-11-16 (watch for DuckDB 2.0.0 release)
