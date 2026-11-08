# Parallax Tech Research Report — 2026-11-08

**Scope:** Weekly scan for improvements, alternatives, and integrations across spatial/geo, LLM/agent, real-time data, eval/MLOps, and performance categories.

**Search date:** November 8, 2026
**Baseline:** Phase 1 design spec (2026-03-30)

---

## Research Areas Covered

1. **Spatial/Geo**: H3 tooling, DuckDB extensions, deck.gl updates, geospatial visualization
2. **LLM/Agent**: Claude API features, batch processing, structured output improvements
3. **Real-time Data**: GDELT alternatives, event databases, shipping/AIS data sources
4. **Eval/MLOps**: Prediction evaluation frameworks, calibration metrics, prompt versioning tools
5. **Performance**: DuckDB optimization, WebSocket patterns, real-time dashboard architecture

---

## Findings by Category

### 1. Spatial/Geo

#### duckh3 R Package (April 2026)
- **What**: R wrapper for DuckDB H3 operations (cell parents, children, centers)
- **Relevance**: **LOW** — R-only; Parallax backend is Python
- **Effort**: N/A
- **Risk/Maturity**: Stable (CRAN 0.1.0)
- **Status**: Additive research; does not apply to current stack

#### DuckDB H3 Community Extension
- **Status**: Confirmed available and stable; already in use in Parallax
- **Finding**: No breaking changes reported in 2026; community extension remains recommended path
- **Effort**: None (already deployed)
- **Relevance**: **HIGH** — foundational to current architecture
- **Recommendation**: Continue using; pin version in Docker as currently done

#### deck.gl v9.3 (April 2026)
- **What**: Tile3DLayer performance improvements, CSS calc() layout expressions, heatmap fixes
- **H3 status**: No H3-specific improvements in 2026 release notes
- **Relevance**: **MEDIUM** — general deck.gl maintenance but no direct H3 gains
- **Effort**: Low (update via npm)
- **Risk/Maturity**: Stable release
- **Recommendation**: Update deck.gl to v9.3 for tile rendering improvements, though H3HexagonLayer performance is unchanged

---

### 2. LLM/Agent

#### Claude API Prompt Caching
- **Status**: Already in use (spec section 8 mentions it)
- **2026 Update**: Pricing changed Sept 1, 2026
  - **Sonnet 5**: $0.30/MTok cache-read (was $0.20 through Aug 31)
  - **Sonnet 4.6**: $0.30/MTok (unchanged)
  - **Haiku 4.5**: Verify current rates on official pricing page
- **Finding**: Cache-read discount is 90% of standard (e.g., $3/MTok standard → $0.30 cached). System prompts are static per agent version, so caching is ideal here.
- **Relevance**: **HIGH** — already deployed; verify pricing impact
- **Effort**: Zero (already implemented)
- **Recommendation**: Audit current spend to confirm prompt caching is enabled on all agent calls; system prompts should be in first cache block

#### Claude API Batch API (50% Discount)
- **What**: Async batch submission with 24-hour turnaround, 50% discount on input+output tokens
- **Status**: Production (not beta)
- **Use case**: Off-peak eval runs, historical backtesting, non-critical agent decisions
- **Finding**: Batch API discounts stack with prompt caching (both apply). Useful for phase 1's scorecard computation.
- **Relevance**: **MEDIUM** — cost optimization for eval, not core live predictions
- **Effort**: Moderate (refactor scorecard pipeline to use batch API)
- **Risk/Maturity**: Production-ready; official docs available
- **Recommendation**: Adopt for daily scorecard computation (non-time-sensitive). Keep live agent calls on standard API to avoid latency.
- **Est. savings**: Scorecard runs cost ~$0.35/day; batch reduces to ~$0.18/day (47% savings)

#### Structured Output (JSON Schema)
- **Status**: Already available on Claude API (all current models support it)
- **Current use**: Parallax agent output schema is validated via pydantic after generation; structured outputs can make validation native
- **2026 update**: `output_config.format` parameter replaces older `output_format` (beta header no longer required)
- **Relevance**: **LOW-MEDIUM** — not blocking; current schema validation works
- **Effort**: Low if switching (Pydantic models → JSON schema via SDK helpers)
- **Risk/Maturity**: Stable, production-ready
- **Recommendation**: Defer to phase 2; current validation pattern is sufficient and explicit

---

### 3. Real-time Data

#### GDELT Cloud (Commercial)
- **What**: Event-coded version of GDELT public stream under CAMEO+ taxonomy
- **Latency**: Hourly ingest (~15 min typical)
- **History**: Limited; backfilling from March 2026 onwards
- **Relevance**: **MEDIUM** — real-time geopolitical events are core to Parallax
- **Effort**: Integration medium (new API client, handle different event schema than public GDELT)
- **Risk/Maturity**: Early (limited history before March 2026; vendor claims need verification)
- **Cost**: Pricing not disclosed in search; contact vendor
- **Recommendation**: Pilot GDELT Cloud for live period (April 7-21 ceasefire window) as backup to existing Google News RSS + public GDELT. Does not replace; adds higher-confidence event coding if available.

#### MyShipTracking / ShipFinder / Kpler AIS APIs
- **What**: Real-time vessel position, speed, course, ETA via terrestrial AIS
- **MyShipTracking**: Bulk vessel lookups by MMSI/IMO, historical tracks
- **ShipFinder**: Polygon-based fleet monitoring, push channels
- **Kpler**: Added `lastUpdatedAt` filter (early 2026) for incremental updates; historical API and real-time endpoints
- **LSEG Vessel Tracking API** (March 2026 launch): Combines terrestrial + satellite + roaming AIS; unified real-time picture
- **Relevance**: **MEDIUM-HIGH** — Hormuz strait traffic is a key indicator; live vessel tracking can improve flow predictions
- **Effort**: Moderate (new data source integration, H3 grid mapping of vessel positions)
- **Risk/Maturity**: LSEG and Kpler are established; pricing/rate limits need verification
- **Cost**: Pricing varies; MyShipTracking and ShipFinder are commercial; LSEG targets enterprise
- **Recommendation**: Evaluate **LSEG Vessel Tracking API** as premium option (satellite + terrestrial AIS fusion); integrate into `real-time_vessel_positions` table in DuckDB, feed into Hormuz flow predictor. Lower priority than GDELT improvements but high value if affordable.

---

### 4. Eval/MLOps

#### Promptfoo (OpenAI Acquisition, March 2026)
- **What**: Declarative YAML-driven prompt regression testing + red-teaming
- **License**: MIT (remains open-source post-acquisition)
- **Features**: CI/CD gates, first-class red-team support, regression suites
- **Relevance**: **HIGH** — Parallax needs prompt versioning and eval automation (spec section 7)
- **Effort**: Moderate (learn YAML config, integrate into eval cron)
- **Risk/Maturity**: Stable; open-source; MIT license; tested at scale
- **Recommendation**: **Adopt Promptfoo** to replace manual eval pipeline. Use for A/B testing prompt versions and detecting accuracy degradation. Example workflow:
  ```yaml
  prompts:
    - file: backend/src/parallax/agents/iran/irgc_navy_v1.2.0.txt
    - file: backend/src/parallax/agents/iran/irgc_navy_v1.3.0.txt
  tests:
    - vars:
        event: "Iranian vessel seizure near Hormuz"
      assert:
        - type: regex
          value: "military_deployment"
        - type: similarity
          value: "previous_decision_v1_2_0"
  ```

#### Calibration Metrics (Expected Calibration Error, Brier Score)
- **Status**: Documented in academic literature; not yet implemented in Parallax
- **Relevance**: **HIGH** — spec section 7 calls for calibration scoring; currently only direction/magnitude/sequence/confidence are scored
- **Tools**: DeepEval, Ragas, Braintrust, and LLMs can compute these natively
- **Effort**: Low-moderate (add ECE and Brier score computation to `calibration_report()` in `scoring/calibration.py`)
- **Risk/Maturity**: Metrics are well-defined; low implementation risk
- **Recommendation**: Add ECE and Brier score to daily scorecard (section 7). Example:
  - **ECE**: Bin confidence scores (e.g., 0-0.2, 0.2-0.4, …), compare avg confidence to actual accuracy per bin
  - **Brier score**: Mean squared error between predicted probabilities and binary outcomes

#### TruthTensor (arXiv 2601.13545)
- **What**: Evaluation framework that tests LLM predictions against live prediction markets (accuracy, calibration, narrative stability, cost)
- **Relevance**: **MEDIUM** — Parallax already uses Kalshi/Polymarket for ground truth; TruthTensor's methodology is aligned but not a new tool
- **Effort**: N/A (framework, not a library)
- **Risk/Maturity**: Research paper (published early 2026)
- **Recommendation**: Review paper for calibration and probabilistic scoring patterns; incorporate market-based ground truth (already planned in scorecard)

#### Langfuse / Braintrust (Observability)
- **Status**: Mentioned as options for CI/CD gates and human calibration
- **Relevance**: **LOW-MEDIUM** — nice-to-have for production observability; not blocking for phase 1
- **Effort**: Moderate
- **Risk/Maturity**: Both are production-ready
- **Recommendation**: Defer to phase 2 if live production monitoring becomes critical

---

### 5. Performance

#### DuckDB 1.5.2 (April 2026)
- **What**: 10% general performance boost, production-ready lakehouse features
- **Relevance**: **MEDIUM** — already using DuckDB; update is a general win
- **Effort**: Low (update via pip)
- **Risk/Maturity**: Stable release; pinned versions in production
- **Recommendation**: Update backend `requirements.txt` to `duckdb>=1.5.2` if not already done

#### Recompute-on-Write + WebSocket Fan-Out Pattern
- **Pattern**: When new data lands, recompute affected aggregates once and push results to all clients over WebSocket (no per-client recomputation)
- **Finding**: Reported 10x load reduction in production dashboard
- **Relevance**: **HIGH** — Parallax already uses WebSocket (spec section 5) but architecture not fully optimized
- **Current state**: Spec section 5 mentions WebSocket updates and mutable useRef pattern; implementation detail unknown
- **Effort**: Audit backend `main.py` WebSocket handlers; confirm aggregates are computed once per tick, not per client
- **Risk/Maturity**: Pattern is proven; low risk
- **Recommendation**: Code audit task — verify that cell update broadcasts are aggregated at backend before fan-out. If not, refactor to reduce DB query count during high-frequency updates.

#### Duckling SDK (5-15ms WebSocket Latency Claims)
- **What**: DuckDB-backed dashboard SDK claiming 5-15ms query latency and 10,000+ queries/sec
- **Relevance**: **LOW** — reference implementation for comparison; Parallax builds custom stack
- **Caveat**: Vendor-reported figures; unverified
- **Finding**: Benchmark useful for latency target; Parallax can aim for similar order of magnitude

#### Web Worker Pattern for Browser DuckDB (WASM)
- **Status**: Technique, not a tool
- **Relevance**: **LOW** — Parallax frontend uses deck.gl + React, not WASM DuckDB
- **Finding**: Relevant if phase 2 adds client-side querying

---

## Top 3 Recommendations (Priority Order)

### 1. **Adopt Promptfoo for Prompt Evaluation (HIGH)**
**Why:** Parallax already has prompt versioning and eval pipelines (spec section 7). Promptfoo automates A/B testing and red-teaming, reducing manual work.

**Action:**
- Install: `npm install -D promptfoo` (or global)
- Create `backend/eval/promptfoo.yml` with prompt pairs and test cases
- Integrate into daily eval cron to flag accuracy regressions
- Replaces manual prompt comparison in current eval pipeline

**Effort:** 2-3 days
**Cost savings:** ~3 hours/week of manual eval work
**Risk:** Low; MIT-licensed; proven tool
**Timeline:** Integrate by end of Nov 2026

---

### 2. **Add ECE & Brier Score to Daily Scorecard (HIGH)**
**Why:** Spec section 7 calls for calibration scoring; currently missing. These metrics are critical for evaluating whether agent confidence reflects true accuracy.

**Action:**
- Add functions to `scoring/calibration.py`:
  - `expected_calibration_error(predictions, outcomes)`
  - `brier_score(predictions, outcomes)`
- Include in daily scorecard computation
- Dashboard: display calibration score alongside hit rate

**Effort:** 1-2 days
**Cost:** ~$0.01/day (minimal compute)
**Risk:** Low; metrics are well-defined
**Timeline:** Integrate by mid-Nov 2026

---

### 3. **Pilot LSEG Vessel Tracking API for Hormuz Flow (MEDIUM)**
**Why:** Vessel positions are a direct proxy for Hormuz throughput; LSEG's satellite+terrestrial fusion is more reliable than terrain-limited AIS alone.

**Action:**
- Contact LSEG for pilot access (March 2026 launch suggests availability)
- Build `ingestion/lseg_vessel_positions.py` to fetch and grid-index vessel positions
- Add `real_time_vessel_positions` table to DuckDB schema
- Feed into `prediction/hormuz.py` flow calculation as alternative to manual scenario parameters
- A/B test: compare LSEG-informed flow predictions vs current rule-based estimates

**Effort:** 3-4 days (API integration, H3 mapping, eval)
**Cost:** TBD by LSEG (negotiate pilot rate)
**Risk:** Medium; enterprise API (may require contract); coverage for Persian Gulf not guaranteed (verify)
**Timeline:** Evaluate by Dec 1, 2026; decide on inclusion

---

## Secondary Findings (Lower Priority)

- **Claude Batch API**: Useful for off-peak scorecard runs; 47% cost savings on ~$0.35/day eval cost. Defer to Dec.
- **deck.gl v9.3**: Minor update; no urgent need but recommend within Q4 2026.
- **Prompt Caching**: Verify still enabled after Sept 1 pricing change; audit spend impact.
- **DuckDB 1.5.2**: Update `requirements.txt` to latest when convenient.

---

## Links & Sources

**Spatial/Geo:**
- [deck.gl What's New](https://deck.gl/docs/whats-new)
- [deck.gl Performance Guide](https://deck.gl/docs/developer-guide/performance)
- [duckh3 R Package (CRAN)](https://cran.r-project.org/web/packages/duckh3/refman/duckh3.html)

**LLM/Agent:**
- [Claude Prompt Caching Docs](https://platform.claude.com/docs/build-with-claude/prompt-caching)
- [Claude Structured Outputs Docs](https://platform.claude.com/docs/build-with-claude/structured-outputs)
- [Claude Batch API 50% Discount Guide (DEV Community)](https://dev.to/claudeguide/claude-batch-api-50-discount-for-async-workloads-2026-guide-2j6)

**Real-time Data:**
- [World Monitor — Free Geopolitical Data APIs 2026](https://www.worldmonitor.app/blog/posts/free-geopolitical-data-apis-2026/)
- [GDELT Cloud](https://gdeltcloud.com)
- [LSEG Vessel Tracking API Launch (March 2026)](https://www.pulse.bot/transportation/news/lseg-launches-real-time-vessel-tracking-api)
- [Kpler Maritime API Updates](https://www.kpler.com/blog/maritime-product-updates-smarter-risk-signals-stronger-apis-faster-mobile-experience)
- [ShipFinder AIS API](https://open.shipfinder.com/)
- [MyShipTracking v2 API](https://github.com/api-evangelist/myshiptracking)

**Eval/MLOps:**
- [Promptfoo (MIT Licensed)](https://promptfoo.dev)
- [Calibration as First-Class Criterion (OpenTrain)](https://www.opentrain.ai/papers/calibration-as-a-first-class-criterion-in-llm-evaluation--arxiv-2609.26489/)
- [TruthTensor — Evaluating LLMs via Prediction Markets (arXiv 2601.13545)](https://fugumt.com/fugumt/paper_check/2601.13545v3_enmode)
- [LLM Evaluation Frameworks 2026 Guide](https://www.mercor.com/resources/apex/llm-evaluation-frameworks/)

**Performance:**
- [DuckDB for Real-Time Dashboards (DEV Community)](https://dev.to/aelmufti/duckdb-for-real-time-dashboards-lessons-from-world-data-visualizer-57ij)
- [DuckDB 1.5.2 Release (April 2026)](https://www.pulse.bot/big-data/news/duckdb-152-boosts-performance-10-and-adds-productionready-lakehouse-features-855103f1-00bb-455d-8d20-b055481f6ea5/)
- [Duckling SDK Documentation](https://www.mintlify.com/chittihq/duckling/sdk/overview)

---

## Summary

No critical blockers found. **Three actionable improvements** identified for implementation by Dec 2026:
1. Promptfoo for prompt eval automation (HIGH priority)
2. Calibration metrics (ECE, Brier) in scorecard (HIGH priority)
3. LSEG Vessel Tracking API pilot (MEDIUM priority, pending vendor contact)

All three align with phase 1 goals and have moderate effort. No breaking changes to existing stack; all improvements are additive or low-risk upgrades.
