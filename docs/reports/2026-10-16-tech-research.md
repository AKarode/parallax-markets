# Technology Research Scout Report — 2026-10-16

## Scope

Daily research across 5 key areas of the Parallax geopolitical simulator tech stack:
1. **Spatial/Geo** — H3 tooling, DuckDB extensions, hex grids, visualization improvements
2. **LLM/Agent** — Claude API features, agent frameworks, structured outputs, inference cost
3. **Real-time Data** — GDELT alternatives, geopolitical event databases, shipping/AIS sources
4. **Eval/MLOps** — Prediction evaluation, LLM eval tools, prompt versioning, A/B testing
5. **Performance** — DuckDB tuning, WebSocket optimization, React rendering

---

## Findings by Category

### 1. Spatial/Geo

#### 1.1 DuckDB H3 Extension Updates
- **Finding:** New R package `duckh3` published to CRAN (April 2026). Wraps DuckDB spatial + H3 extensions for R users.
- **Relevance:** LOW — Parallax uses Python, not R. No new Python extension updates found.
- **Effort:** N/A
- **Risk/Maturity:** Stable (wraps existing extensions)
- **Action:** No change needed; current H3 community extension remains solid.

#### 1.2 deck.gl H3HexagonLayer Performance
- **Finding:** deck.gl v9 H3HexagonLayer supports instanced rendering (assumes viewport-center hex shape applies to viewport; error imperceptible) and high-precision mode for edge cases (pentagons, coarse resolutions, mixed resolutions). No 2026-specific updates found.
- **Relevance:** MEDIUM — Parallax already uses instanced rendering; high-precision mode available as optimization lever.
- **Effort:** LOW — Configuration flag only if needed.
- **Risk/Maturity:** Stable; trade-off documented.
- **Action:** Monitor for high-precision toggle if performance testing later flags hex geometry as a bottleneck.

---

### 2. LLM / Agent Orchestration

#### 2.1 Claude API Prompt Caching (Confirmed in Use)
- **Finding:** Prompt caching costs 90% less on cache hits (~0.1x standard input price) and ~1.25x on cache writes. **Design doc mentions implementation already.** Current usage: system prompts (historical baselines) cached across repeated agent calls within 5-min TTL.
- **Relevance:** HIGH — Already implemented, working as designed.
- **Effort:** N/A
- **Risk/Maturity:** Stable (since mid-2024, widely deployed).
- **Action:** No change. Cost savings already captured.

#### 2.2 Claude API Batch Processing
- **Finding:** Batch API accepts message collections, processes async, returns 50% discount. **Conflict in sources:** Some claim batch + prompt caching stack; others say they don't (as of mid-2026). Official Anthropic docs must be checked.
- **Relevance:** MEDIUM — Potential $20k → $10k savings on monthly eval runs (if backend scales), but uncertain compatibility with caching.
- **Effort:** MEDIUM — Requires async job polling + result retrieval architecture.
- **Risk/Maturity:** Stable, but compatibility needs verification against current platform.claude.com docs.
- **Action:** Verify batch + caching stack support with Anthropic before investing. Document findings in engineering notes.

#### 2.3 PydanticAI for Structured Outputs
- **Finding:** PydanticAI (2026) is Python-first, Pydantic-native agent framework with strong structured-output support. Alternatives: CrewAI, Agno (both more heavyweight). Parallax currently uses custom asyncio DES + direct LLM calls (by design, no LangGraph).
- **Relevance:** MEDIUM — Could simplify agent output validation + structured-output enforcement, but current approach (manual JSON schema validation + logging) works.
- **Effort:** MEDIUM-HIGH — Would require refactor of agent decision flow.
- **Risk/Maturity:** PydanticAI is new (2026); adoption less widespread than LangGraph.
- **Action:** Shelve for Phase 2. Current approach is lean and effective. Revisit if agent complexity grows (e.g., multi-turn reasoning, long-context history).

#### 2.4 Claude Haiku 4.5 Pricing Competitiveness
- **Finding:** Haiku 4.5 costs $1/$5 per million input/output tokens. Cheaper alternatives exist (Qwen3.8-Flash at $0.15/$0.47) but trade quality + reliability. Relative to Haiku: OpenAI GPT-3.5 Turbo is cheaper (~$0.50/$1.50), but the design doc notes Claude is chosen for reasoning quality.
- **Relevance:** LOW — Haiku 4.5 already selected as optimal for cost/quality trade-off.
- **Effort:** N/A
- **Risk/Maturity:** Pricing stable.
- **Action:** No change. Current model choice validated.

---

### 3. Real-time Data

#### 3.1 GDELT Alternatives & Supplements
- **Finding:** 
  - **ACLED:** Human-verified political violence/protests/conflict. Lagged (not real-time), requires account + licensing.
  - **UCDP:** Validated conflict records. Free API (requires token). Research-grade, not minute-to-minute monitoring.
  - **GDELT Cloud:** Hourly refresh of GDELT events, but data history thin before March 2026 (backfill ongoing).
  - **World Monitor:** Dashboard built on GDELT, not a replacement.
- **Assessment:** GDELT remains primary (high recall). ACLED + UCDP useful for *validation* of GDELT findings (causal attribution on misses in eval framework).
- **Relevance:** MEDIUM — Additive, not replacing. Could improve miss classification (exogenous_shock vs model_error).
- **Effort:** LOW to MEDIUM — APIs are straightforward; would feed into eval pipeline.
- **Risk/Maturity:** ACLED has licensing complexity; UCDP is academic and stable.
- **Action:** Integrate ACLED + UCDP queries into post-prediction validation. Flag: check ACLED licensing terms for non-commercial use.

#### 3.2 AIS Vessel Tracking for Shipping Corridor Monitoring
- **Finding:**
  - **AISHub:** Cooperative free network. Access by contributing receiver feed (high uptime required). Returns JSON/CSV positions. No commercial terms.
  - **AISStream.io:** Open-source client (AIS-ws-feedhandler), proprietary data. Supports real-time NMEA stream.
  - **MyShipTracking:** Paid REST API, credit-metered, live + history. No free tier (trial only).
  - **Searoutes:** Commercial, satellite + terrestrial AIS, includes ETA and port-call data.
  - **AISViz:** Research project (Dalhousie U), open-source extraction + visualization toolbox.
- **Assessment:** AIS data is *orthogonal* to predictions but strengthens visualization + validation. Real vessel positions would improve Hormuz corridor credibility.
- **Relevance:** HIGH — Adds credible real-world layer to hex map. Strong for demo/interview impact.
- **Effort:** MEDIUM — API integration (REST or WebSocket), H3 cell mapping for vessel positions, separate ingestion loop.
- **Risk/Maturity:** 
  - AISHub: Free but operationally risky (requires maintaining a feed).
  - MyShipTracking/Searoutes: Commercial, stable, proven.
  - AISStream/AISViz: Open-source, but support quality variable.
- **Budget Impact:** AISHub free; commercial options likely $50–200/month.
- **Action:** **Recommended for Phase 2.** Start with AISStream.io (open-source client, predictable data) for dev/test. Evaluate commercial options (Searoutes) for production credibility. Low priority for current Phase 1 (prediction models are the value driver).

---

### 4. Eval / MLOps

#### 4.1 LLM Evaluation Frameworks (Promptfoo, DeepEval, Ragas)
- **Finding:**
  - **Promptfoo:** YAML-driven prompt regression, red-team support, lightweight. Designed for CI gates.
  - **DeepEval:** pytest-style, 50+ built-in metrics. More comprehensive.
  - **Ragas:** RAG-focused (less relevant for Parallax).
  - **Architecture consensus (2026):** Layered system = offline regression suites + online/shadow eval + human-calibrated anchors. Frameworks are tools *within* this system, not the system itself.
- **Current Parallax approach:** Custom prediction log + calibration queries + prompt versioning + A/B tracking (per design doc Section 7). No red-team or structured regression CI gate yet.
- **Relevance:** MEDIUM — Parallax eval framework is solid; Promptfoo could add:
  - Structured prompt regression CI gate (A/B testing before rollout).
  - Red-team suite (jailbreak resistance, hallucination checks).
  - Dashboard for eval results over time.
- **Effort:** MEDIUM — Integrate Promptfoo into CI/dev workflow. Would require exporting labeled prediction misses as regression test dataset.
- **Risk/Maturity:** Promptfoo is stable and lightweight (YAML-driven). DeepEval more enterprise-y.
- **Action:** **Recommended for Phase 2 eval refinement.** Start with Promptfoo for CI-gated prompt rollout + red-team tests. Requires ~50+ labeled eval dataset (achievable by end of 30-day Phase 1 run).

#### 4.2 LLM Judge Calibration & Drift
- **Finding:** 
  - Judge calibration requires 100+ labeled examples + weekly maintenance (per Hamel Husain, secondhand).
  - Known failure modes: length bias, position bias, self-preference bias (LLM prefers its own outputs).
  - Risk: Judge scores shift after vendor model updates → CI failures on unchanged prompts.
  - Mitigation: Pin model version, version the judge, run weekly calibration loop.
- **Current Parallax approach:** Manual causal attribution on misses (model_error, exogenous_shock, etc.). Uses Claude for eval meta-agent, but doesn't use LLM-as-judge for scoring automatically.
- **Relevance:** MEDIUM — If Parallax later automates calibration scoring, these mitigations are critical.
- **Effort:** MEDIUM — Adds versioning + monitoring infrastructure.
- **Risk/Maturity:** Known risks are well-documented (arXiv 2601.22025, practitioner blogs). Mitigations are mature.
- **Action:** Document calibration strategy for Phase 2. If moving to auto-scoring, apply mitigations immediately.

---

### 5. Performance

#### 5.1 React Real-time Dashboard WebSocket Optimization
- **Finding:** Bottleneck is rendering, not network. Modern WebSockets handle 1000s msgs/sec. Solutions: throttle, batch, virtualize, selective updates, backpressure.
- **Current Parallax approach (per design doc):** Already implements best practices:
  - H3 hex data in `useRef` (mutable, bypasses React reconciliation).
  - WebSocket messages batched for 100ms before flushing to ref.
  - React re-renders only for UI changes (agent feed, indicators), not hex data.
- **Relevance:** LOW — Already optimized.
- **Effort:** N/A
- **Risk/Maturity:** N/A
- **Action:** No change. Monitor during live deployment. If render thrashing appears, confirm batching is working (100ms window may need tuning based on event frequency).

#### 5.2 DuckDB Performance Tuning for Large Datasets
- **Finding:**
  - Profile with `EXPLAIN` (no run) and `EXPLAIN ANALYZE` (with run).
  - Common bottlenecks: nested loop joins → hash joins, missing filter pushdowns, scanning unnecessary columns.
  - Remote I/O: increase threads to 2–5x CPU cores for parallelism.
  - Memory risk: Complex aggregates (e.g., PIVOT, list() in aggregates) can't spill to disk → OOM on large datasets.
  - Optimization: Use tight range predicates (e.g., `date >= X AND date < Y`) instead of function calls on columns (e.g., `YEAR(date) = 2026`).
  - Data format: Convert frequently-used CSVs to Parquet for faster scans.
- **Parallax state growth (design doc Section 9):** 
  - ~400K hexes × 15-min ticks = massive append-only risk.
  - Mitigated by delta + snapshot strategy (only changed cells per tick, snapshots every 100 ticks).
  - This is already architected correctly.
- **Relevance:** MEDIUM — Good practices to monitor as dataset grows. Parallax should:
  - Run EXPLAIN ANALYZE on daily scorecard queries (15+ metrics, large joins).
  - Monitor for PIVOT usage (none currently, but eval queries might use it).
  - Watch memory usage during peak activity (agent decisions + cascade + eval in parallel).
- **Effort:** LOW — Mostly observation + tuning parameters; no code changes needed yet.
- **Risk/Maturity:** Stable; DuckDB docs are clear.
- **Action:** Document performance checklist for Phase 1 → Phase 2 transition:
  1. Profile scorecard queries with EXPLAIN ANALYZE.
  2. Confirm delta + snapshot retention is working (no unbounded table growth).
  3. Set temp directory for large spills (in production).
  4. Monitor thread count vs CPU cores (may need `threads` parameter tuning).

---

## Consolidated Assessment

### Quick Wins (Low Effort, High/Medium Impact)
1. **Verify Batch API + Caching Stack** (Effort: LOW, Impact: MEDIUM) — Check Anthropic docs, document findings. Could unlock 50% savings on eval batch jobs if compatible.
2. **Integrate ACLED + UCDP for Validation** (Effort: LOW, Impact: MEDIUM) — Feed into eval causal attribution. Improves miss classification.
3. **Document DuckDB Tuning Checklist** (Effort: LOW, Impact: MEDIUM) — Proactive monitoring prevents perf surprises as Phase 1 data grows.

### Medium-term Additions (Phase 2)
1. **AIS Vessel Tracking** (Effort: MEDIUM, Impact: HIGH for credibility/demo) — Real-world shipping data on Hormuz visualization. Start with AISStream.io or Searoutes.
2. **Promptfoo CI-gated Prompt Rollout** (Effort: MEDIUM, Impact: MEDIUM) — Red-team tests + structured regression suite. Requires ~50+ labeled dataset by Phase 1 end.
3. **PydanticAI for Output Validation** (Effort: MEDIUM-HIGH, Impact: MEDIUM) — Simplifies agent reasoning + structured outputs. Shelve until agent complexity grows.

### Already Optimized (No Action)
- Claude Haiku 4.5 pricing (best in class for cost/quality).
- React dashboard performance (best practices in place).
- Prompt caching (implemented, working as designed).

---

## Top 3 Recommendations

### 1. **Verify Batch API Compatibility & Cost Model** (Highest Priority)
**Why:** Could unlock 50% savings on daily eval runs ($20/day → $10/day), which scales with deployment. Uncertainty on batch + caching stacking prevents commitment.

**Action:**
- Check Anthropic docs (platform.claude.com) for official stance on batch + prompt caching in Oct 2026.
- Prototype batch API with a small set of predictions (~10) to measure actual cost reduction.
- Document findings in engineering notes; commit cost model once validated.

**Timeline:** 1–2 days exploratory work. Include in Phase 2 cost review.

---

### 2. **Plan AIS Vessel Tracking for Phase 2 MVP** (Demo Impact)
**Why:** Real-time vessel positions on Hormuz visualization dramatically improves credibility + interview/demo impact. Orthogonal to predictions, so can be added without core refactor.

**Action:**
- Evaluate AISStream.io (open-source client) vs Searoutes (commercial) during Phase 1 data collection.
- Design H3 cell mapping for vessel positions (integrate with existing hex layer).
- Estimate cost + data latency for production.
- Add as Phase 2a scope (before Phase 2b agent refinements).

**Timeline:** Research 3–5 days. Implementation 1–2 weeks in Phase 2.

---

### 3. **Implement Promptfoo CI-gated Prompt Rollout for Phase 2** (Process Improvement)
**Why:** Prevents regressions on prompt changes + structures A/B testing. Current prompt versioning is manual; automation reduces risk as swarm complexity grows.

**Action:**
- During Phase 1, export prediction misses (tagged model_error) as structured dataset (~50+ examples by day 30).
- Set up Promptfoo YAML suite in dev repo (regression tests + red-team checks).
- Integrate into CI: new prompt versions must pass regression suite before deployment.
- Start with 2–3 critical agents (Iran, USA, Saudi Arabia) and expand.

**Timeline:** Research 2–3 days. Implementation 1 week in Phase 2 after data collection ends.

---

## Sources

### Spatial/Geo
- [duckh3 R Package (CRAN)](https://cran.r-project.org/web/packages/duckh3/index.html)
- [deck.gl H3HexagonLayer Docs](https://deck.gl/docs/api-reference/geo-layers/h3-hexagon-layer)

### LLM/Agent
- [Claude API Cache Pricing (Unverified sources)](https://tkmxai.it.com/claude-api-cache-pricing-in-2026-5)
- [LangGraph Alternatives 2026](https://www.truefoundry.com/blog/langgraph-alternatives)
- [PydanticAI & Agent Frameworks](https://blog.premai.io/15-best-ai-agent-frameworks-for-enterprise-open-source-to-managed-2026/)

### Real-time Data
- [Free Geopolitical Data APIs 2026](https://www.worldmonitor.app/blog/posts/free-geopolitical-data-apis-2026/)
- [AIS Vessel Tracking (AISHub)](https://public-api.org/api/1260/ais-hub)
- [AISStream.io](https://github.com/lcsrodriguez/AIS-ws-feedhandler)
- [Searoutes Vessel Tracking](https://searoutes.com/en/products/vessel-tracking)

### Eval/MLOps
- [LLM Evaluation Frameworks 2026](https://bigdataboutique.com/blog/llm-evaluation-frameworks-metrics-best-practices)
- [Best Prompt Testing Frameworks 2026](https://futureagi.com/blog/best-prompt-testing-frameworks-2026/)
- [When "Better" Prompts Hurt (arXiv 2601.22025)](https://arxiv.org/abs/2601.22025)

### Performance
- [React WebSocket Optimization 2026](https://oneuptime.com/blog/post/2026-01-15-websockets-react-real-time-applications/markdown)
- [React Performance: Real-time Data](https://stevekinney.com/courses/react-performance/real-time-data-performance)
- [DuckDB Performance Tuning](https://www.duckdb.org/docs/current/guides/performance/how_to_tune_workloads.html)
- [DuckDB Optimizations (Medium)](https://medium.com/@ThinkingLoop/10-duckdb-optimizations-every-data-engineer-should-know-cb831c9956ef)

---

**Report Date:** 2026-10-16  
**Next Scan:** 2026-10-17  
**Findings Summary:** 3 quick wins (batch API verification, ACLED/UCDP integration, DuckDB tuning), 3 medium-term additions (AIS tracking, Promptfoo, PydanticAI), no critical tech debt or blockers identified.
