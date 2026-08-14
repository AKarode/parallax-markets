# Technology Research Report — August 14, 2026

**Focus areas:** Spatial/Geo, LLM/Agent, Real-time Data, Eval/MLOps, Performance

---

## Executive Summary

Research identified **5 HIGH-value findings** with actionable next steps, **3 medium-value** additive improvements, and **2 deprecated patterns** to monitor. No critical stack gaps found; Parallax is well-positioned with current technology choices. Key highlights:

1. **Prompt caching TTL reduced to 5min** — requires prompt lifecycle tuning for cost control
2. **DuckDB Quack protocol** shipping fall 2026 — eliminates single-writer bottleneck if Phase 2 scales horizontally
3. **AISstream.io free real-time AIS** — immediate upgrade to shipping lane detection with no cost
4. **Model2Vec distillation** — 500x faster semantic dedup with minimal integration effort
5. **Traceability frameworks (DeepEval/Lilypad)** — production-ready infrastructure for eval tracking

---

## Findings by Category

### 1. SPATIAL & GEOSPATIAL

#### A. DuckDB Experimental Geometry Types (POINT_2D, LINESTRING_2D, POLYGON_2D)
- **What:** Native DuckDB support for 2D geometries with fixed memory layout, better compression, faster execution
- **Relevance:** MEDIUM — Parallax currently relies on H3 cells and JSON payloads; these types could optimize storage/query on port/chokepoint geometries
- **Effort:** LOW — Drop-in replacement for current GeoJSON handling; test before migration
- **Risk:** MEDIUM — Experimental status; community support is strong but v1.0 stability timeline unclear
- **Action:** Monitor DuckDB 1.3+ releases; profile query performance on `infrastructure` cells (ports, terminals) before upgrade

#### B. deck.gl H3HexagonLayer `highPrecision: false` Option
- **What:** GPU-optimized low-precision rendering for large hex grids
- **Relevance:** MEDIUM — Parallax uses H3HexagonLayer extensively; applicable for 400K hex rendering
- **Effort:** TRIVIAL — Single property flag; test visual quality degradation
- **Risk:** LOW — Already stable in v9.1, proven in production
- **Action:** Test on dense regions (Hormuz res 7-8) to measure FPS gain vs visual quality loss; document threshold

#### C. TileLayer Custom Indexing (S2 / H3 Incremental Loading)
- **What:** deck.gl v8.8+ supports custom indexing systems for tile-based incremental loading
- **Relevance:** LOW — Parallax pre-loads all 400K cells; incremental loading saves memory but adds complexity
- **Effort:** MEDIUM — Requires tile-based architecture refactor
- **Risk:** MEDIUM — Adds latency for panned regions if not carefully optimized
- **Action:** Defer to Phase 2; only pursue if memory pressure in production

---

### 2. LLM & AGENT REASONING

#### A. Claude Prompt Cache TTL Reduced to 5 Minutes (Critical Update)
- **What:** Anthropic reduced ephemeral cache TTL from 60 minutes to 5 minutes in early 2026; persistent cache (Sonnet 4/Opus 4) survives across sessions
- **Relevance:** HIGH — Parallax pre-computes agent system prompts (~2K tokens cached); TTL affects cost modeling
- **Impact on Budget:** Calls within 5min hit 90% discount; calls outside window pay full price. With 50 agents and 15min event intervals, many calls **miss** the cache now.
- **Effort:** LOW — Requires prompt scheduling tuning (batch similar events within 5min windows)
- **Risk:** LOW — Transparent API change; no code changes needed, only operational tuning
- **Action:** (1) Switch to persistent cache on Sonnet 4/Opus 4 endpoints (if available). (2) Tune event router to batch similar agent activations within 5min windows. (3) Re-baseline daily LLM cost; expect 20-30% increase if caching was core to budget model.

#### B. Claude Batch API (50% Cost Reduction)
- **What:** Anthropic Batches API processes groups of requests at 50% of standard pricing; latency tolerance measured in hours
- **Relevance:** MEDIUM — Applicable to non-real-time phases (eval meta-agent, overnight prompt testing, historical replay)
- **Effort:** LOW — Batch API is a simple JSON envelope over standard requests; integrates cleanly with eval pipeline
- **Risk:** LOW — No change to model quality; only cost and latency tradeoff
- **Action:** Migrate eval meta-agent (`_run_scorecard()`) to Batch API; measure latency tolerance. Estimate savings: ~$0.35/day → ~$0.18/day on eval calls.

#### C. Persistent Cache (Sonnet 4 / Opus 4 Specific)
- **What:** Cache survives across sessions/days (unlike ephemeral 5min cache)
- **Relevance:** HIGH — Long-running agents benefit from multi-day cache consistency
- **Effort:** LOW — Same prompt caching API; only requires endpoint selection
- **Risk:** MEDIUM — Requires Sonnet 4/Opus 4 access (may not be available on all Anthropic tiers)
- **Action:** (1) Confirm persistent cache availability on account. (2) If available, migrate country agent system prompts to Sonnet 4/Opus 4 for persistent cache. (3) Benchmark cost impact.

#### D. Cheaper Inference Alternatives
- **What:** Competitors offer lower-cost budget models: Gemini 2.0 Flash ($0.075/$0.30), GPT-4o mini ($0.15/$0.60) vs Claude Haiku ($1/$5)
- **Relevance:** LOW — Parallax is sensitive to reasoning quality (cascade correctness, agent consistency); Haiku trade-off is acceptable for sub-actor calls
- **Effort:** HIGH — Requires prompt rewriting, agent behavior testing, eval regression suite
- **Risk:** HIGH — Different model behavior on geopolitical reasoning; may degrade prediction accuracy
- **Action:** Monitor as fallback if budget constraints tighten; defer to Phase 2 cost review

---

### 3. REAL-TIME DATA & EVENT INGESTION

#### A. AISstream.io (Free Real-Time AIS WebSocket)
- **What:** Free WebSocket feed of global AIS vessel positions, updated every 10-30 seconds; competitor to paid Spire/MarineTraffic
- **Relevance:** HIGH — Parallax models Hormuz shipping lane traffic; real-time AIS is a high-fidelity ground truth signal
- **Current Gap:** Parallax uses `hormuz_daily_flow` parameter (scenario config) without live vessel-level data; adding AIS enables accurate real-time flow tracking
- **Effort:** MEDIUM — (1) Add WebSocket ingestion for AIS stream. (2) Geospatial filter for Persian Gulf / Strait of Hormuz (lat/lng bounds → H3 cells). (3) Aggregate vessel count + gross tonnage by route. (4) Feed into cascade engine as exogenous signal.
- **Risk:** LOW — Additive signal (no refactoring of existing logic); can be toggled off if stream becomes unreliable
- **Cost:** $0 (free tier) vs $5K+/month for enterprise AIS
- **Action:** IMMEDIATE — Integrate AISstream.io as Phase 1 enhancement. (1) Add `ais_ingestion.py` module. (2) Filter by Hormuz geographic bounds. (3) Compare live vessel counts against `hormuz_daily_flow` baseline to detect anomalies. (4) Inject anomaly signals into cascade engine.

#### B. Datalastic Self-Serve AIS API
- **What:** Transparent per-query credit-based pricing for AIS data; less consolidated than Kpler/Spire
- **Relevance:** MEDIUM — Backup to AISstream.io if free stream becomes congested; supports historical query for backtesting
- **Effort:** LOW — REST API integration (simpler than WebSocket)
- **Risk:** LOW — Established provider; cost is transparent and low-volume friendly
- **Action:** Defer to Phase 2; list as fallback for high-volume scenarios

#### C. GDELT Cloud (Enhanced GDELT with Clustering & Entity Resolution)
- **What:** Commercial GDELT enhancement with pre-clustered stories and resolved entities
- **Relevance:** MEDIUM — Parallax manually clusters GDELT with semantic dedup; pre-clustering saves compute
- **Effort:** MEDIUM — Requires API swap from GDELT BigQuery to GDELT Cloud endpoints
- **Risk:** MEDIUM — Commercial pricing (unknown per-call cost); need to evaluate savings vs raw GDELT
- **Action:** Request API access and conduct cost-benefit analysis (GDELT BigQuery $0 vs GDELT Cloud per-query pricing)

#### D. POLECAT Dataset (Political Event Classification & Types)
- **What:** Emerging alternative to GDELT with lower redundancy but smaller scale
- **Relevance:** LOW — Parallax is optimized for GDELT's massive scale; POLECAT's smaller dataset may miss early weak signals
- **Effort:** HIGH — Requires rewriting ingestion pipeline, event deduplication logic, and agent router
- **Risk:** MEDIUM — Smaller dataset may reduce edge-finding capability
- **Action:** Monitor; consider as supplementary signal in Phase 2 if GDELT performance plateaus

---

### 4. EVALUATION & MLOPS

#### A. Traceability Frameworks (DeepEval, Lilypad, MLflow)
- **What:** Unified systems that link predictions ↔ prompt version ↔ model ↔ dataset ↔ eval score; automatic versioning decorators
- **Relevance:** HIGH — Parallax has basic prompt versioning; traceability framework would eliminate manual correlation work
- **Current Gap:** Parallax tracks `prompt_version` in `predictions` table but lacks unified platform for A/B comparison
- **Effort:** MEDIUM — (1) Integrate DeepEval or Lilypad into `scoring/calibration.py` and eval cron. (2) Decorate agent calls with @lilypad.trace (auto-captures prompt version, model, inputs). (3) Query lineage in eval dashboards.
- **Risk:** LOW — These are instrumentation libraries; no model changes needed
- **Recommendation:** Use **Lilypad** (simpler, fewer dependencies) for Phase 1 traceability; migrate to DeepEval later if eval complexity grows
- **Action:** Add Lilypad instrumentation to agent calls in `cli/brief.py` and `prediction/*.py`

#### B. Calibration Scoring (RAGAS Metrics, Hallucination Detection)
- **What:** Standardized metrics for evaluating LLM outputs: RAGAS (Retrieval-Augmented Generation Assessment), hallucination detection, semantic similarity
- **Relevance:** MEDIUM — Parallax computes `calibration_score` (binary direction accuracy); RAGAS would add depth
- **Effort:** MEDIUM — RAGAS is designed for RAG systems but applicable to agent reasoning evaluation
- **Risk:** LOW — Purely additive metrics; doesn't change core eval
- **Action:** Add RAGAS evaluation to `scoring/calibration.py`; use to detect agent hallucinations in decision reasoning

#### C. A/B Testing Framework (Confident AI, Braintrust)
- **What:** Platforms for running side-by-side prompt experiments with statistical significance testing
- **Relevance:** MEDIUM — Parallax prompt versioning is manual; A/B platform would automate testing
- **Effort:** MEDIUM — (1) Integrate A/B framework into eval pipeline. (2) For new prompt versions, automatically route subset of events to new version. (3) Compute statistical significance after N predictions.
- **Risk:** LOW — Additive to current pipeline
- **Action:** Defer to Phase 2 after Lilypad traceability is in place; stack Confident AI on top for automated A/B

---

### 5. PERFORMANCE

#### A. Model2Vec Distillation (500x Faster Semantic Embeddings)
- **What:** Distills sentence-transformer embeddings into static vectors; enables ~500x faster CPU inference for semantic dedup
- **Current Tech:** Parallax uses `sentence-transformers` (all-MiniLM-L6-v2) for GDELT semantic dedup in stage 4 (baseline: ~50ms per 1K events)
- **Relevance:** HIGH — Dedup runs every 15min; 500x speedup → 1ms per 1K events (negligible latency)
- **Effort:** LOW — Model2Vec is a drop-in replacement; same `cosine_similarity` interface, just faster
- **Risk:** LOW — Distillation is a standard technique; quality degradation is minimal for cosine similarity
- **Estimated Gain:** Dedup latency drops from ~50ms → 1ms per event batch; frees CPU cycles for other tasks
- **Action:** Test Model2Vec distillation on `all-MiniLM-L6-v2` model; measure quality (should match parent >0.95 correlation); switch if latency benefit is material

#### B. ONNX Runtime Optimization (3x CPU Speedup)
- **What:** ONNX Runtime accelerates embedding inference on CPU/GPU via operator fusion and memory optimization
- **Relevance:** MEDIUM — Orthogonal to Model2Vec; can be combined for even larger speedup
- **Effort:** LOW — ONNX-optimized all-MiniLM-L6-v2 available from HuggingFace (LightEmbed); drop-in replacement
- **Risk:** LOW — ONNX is mature; backend swap is transparent
- **Action:** Apply after Model2Vec; combine both for ~500x × 3x = 1500x theoretical speedup (practical gain ~100-200x due to other bottlenecks)

#### C. React Performance: Virtualization + React.memo
- **What:** React rendering optimization for high-frequency updates (>100Hz WebSocket messages)
- **Current Implementation:** Parallax uses `useRef` for hex data + batching (100ms buffer); matches best practices
- **Relevance:** LOW — Parallax design already decouples hex data (mutable ref) from React state; no bottleneck identified
- **Effort:** TRIVIAL — If regressions occur, apply React.memo on agent feed component
- **Risk:** NEGLIGIBLE
- **Action:** Document pattern in architecture guide; monitor for regressions

#### D. react-use-websocket Library (WebSocket Boilerplate Reduction)
- **What:** React hook for WebSocket lifecycle management; eliminates manual event listener setup
- **Relevance:** LOW — Parallax uses raw WebSocket; library is nice-to-have for maintainability
- **Effort:** LOW — Hook-based refactor of `/frontend/src/hooks/useWebSocket` (if not already using)
- **Risk:** LOW — Widely used library
- **Action:** Consider if WebSocket reconnection logic becomes complex; defer to Phase 2 refactor

#### E. DuckDB Quack Protocol (Multi-Writer Support, Fall 2026)
- **What:** DuckDB v2.0 shipping Quack remote protocol for client-server architecture; enables true multi-process writes
- **Relevance:** MEDIUM → HIGH (Phase 2 only) — Parallax single-writer constraint may become bottleneck if worker count scales
- **Current Limitation:** All simulation logic must run in one process to avoid `database is locked` errors
- **Phase 2 Impact:** If horizontal scaling is needed, Quack eliminates this constraint by turning DuckDB into a server
- **Timeline:** Fall 2026 (after current sprint)
- **Effort:** MEDIUM — Requires process refactor (GDELT ingestion, eval cron, cascade logic as separate services)
- **Risk:** MEDIUM — Quack is new; will need production validation before relying on it
- **Action:** Track DuckDB v2.0 release notes; design Phase 2 architecture with Quack as optional backend

#### F. DuckLake v1.0 Specification (Data Lakehouse Pattern)
- **What:** DuckDB-based lakehouse format published April 2026; enables multi-process writes + time-travel queries
- **Relevance:** MEDIUM (Phase 2) — Alternative to Quack if lakehouse pattern fits Parallax eval/replay use case
- **Effort:** HIGH — Requires schema redesign (delta tables vs snapshot pattern)
- **Risk:** MEDIUM — New specification; community adoption still ramping
- **Action:** Defer; evaluate after Quack matures in fall 2026

---

## Deprecated/Monitor Patterns

### A. Prompt Caching at 60min TTL
- **Status:** DEPRECATED — TTL reduced to 5min in 2026
- **Impact:** Cost assumptions from design doc (Section 8) need revision
- **Action:** Update cost tracking; re-baseline daily spend

### B. Sentence-Transformers for Real-Time Dedup
- **Status:** MONITOR — Model2Vec offers 500x speedup; plan migration
- **Timeline:** Implement in next sprint if CPU profiling shows dedup as bottleneck

---

## Top 3 Recommendations (Priority Order)

### 1. **Add Free Real-Time AIS Feed (AISstream.io)** — IMMEDIATE
- **Why:** Parallax currently simulates Hormuz traffic with static config parameters; real-time AIS adds ground-truth fidelity with zero cost
- **Effort:** Medium (1-2 days) — Clean separation (new `ais_ingestion.py` module)
- **Impact:** High — Enables accurate live vessel tracking, anomaly detection, paper trading validation
- **Success Metric:** Live vessel count in Hormuz matches broadcast news reports within 5-10 vessel accuracy
- **Timeline:** This sprint

### 2. **Migrate to Claude Persistent Cache + Batch API** — THIS SPRINT
- **Why:** Prompt caching TTL reduced to 5min; persistent cache + batch API recovers cost efficiency and simplifies operational tuning
- **Effort:** Low (1 day) — API-level change, no model changes
- **Impact:** Medium — Stabilizes daily LLM spend, reduces cache misses, enables cheaper eval pipeline
- **Success Metric:** Daily LLM cost returns to $2-5 range (from expected $3-8 with 5min TTL)
- **Timeline:** This sprint

### 3. **Implement Model2Vec + ONNX Distillation for Semantic Dedup** — NEXT SPRINT
- **Why:** 500x+ speedup on GDELT dedup (~50ms → 1ms per batch); minimal risk; unlocks CPU cycles
- **Effort:** Low (1 day) — Drop-in replacement for sentence-transformers
- **Impact:** Medium — Reduces ingestion latency, frees resources for other tasks
- **Success Metric:** Dedup latency <5ms for 1K events; quality (cosine sim correlation) >0.95 vs current model
- **Timeline:** Next sprint

---

## Sources & References

### Spatial/Geo
- [Awesome DuckDB Spatial](https://github.com/alperdincer/Awesome-DuckDB-Spatial)
- [Spatial Queries in DuckDB with R-tree and H3 Indexing](https://aetperf.github.io/2025/03/04/Spatial_queries_in_DuckDB_with_R-tree_and_H3_indexing.html)
- [DuckDB Spatial Extension](https://duckdb.org/docs/lts/core_extensions/spatial/overview)
- [deck.gl Performance Guide](https://deck.gl/docs/developer-guide/performance)
- [deck.gl What's New](https://deck.gl/docs/whats-new)

### LLM & Agent
- [Claude Prompt Caching 5-Minute TTL Change — Dev Community](https://dev.to/whoffagents/claude-prompt-caching-in-2026-the-5-minute-ttl-change-thats-costing-you-money-4363)
- [Claude Prompt Caching Guide](https://hidekazu-konishi.com/entry/anthropic_claude_api_prompt_caching_and_token_efficiency.html)
- [Claude Batch Processing Docs](https://platform.claude.com/docs/en/build-with-claude/batch-processing)
- [Claude Cost Optimization 2026](https://pecollective.com/tools/claude-pricing-guide/)

### Real-Time Data
- [Best Vessel Tracking Software in 2026](https://www.seavantage.com/blog/best-vessel-tracking-software-in-2026-8-ais-platforms-compared)
- [Datalastic Vessel Tracking API](https://datalastic.com/)
- [AIS Data Providers](https://www.darkshipping.com/post/ais-data-providers)
- [Data Docked AIS API](https://datadocked.com/ais-api-providers/)
- [GDELT Project](https://www.gdeltproject.org/)
- [GDELT Cloud](https://gdeltcloud.com/)
- [POLECAT Dataset Paper](https://doi.org/10.3390/data11070158)

### Eval & MLOps
- [Best LLM Evaluation Tools of 2026 — Medium](https://medium.com/online-inference/the-best-llm-evaluation-tools-of-2026-40fd9b654dce)
- [A/B Testing Prompts Guide](https://www.getmaxim.ai/articles/how-to-perform-a-b-testing-with-prompts-a-comprehensive-guide-for-ai-teams/)
- [LLM Testing Frameworks 2026](https://testomat.io/blog/llm-test/)
- [Braintrust Prompt Evaluation](https://www.braintrust.dev/articles/best-prompt-evaluation-tools-2025)
- [LLM Evaluation Frameworks 2026 — Medium](https://medium.com/@future_agi/llm-evaluation-frameworks-metrics-and-best-practices-2026-edition-162790f831f4)
- [Confident AI Evaluation Tools](https://www.confident-ai.com/knowledge-base/compare/best-ai-evaluation-tools-for-prompt-experimentation-2026)

### Performance
- [React WebSocket Real-Time Dashboards](https://www.innovationm.com/blog/react-websockets/)
- [Optimizing WebSockets + React Integration — Medium](https://medium.com/@SanchezAllanManuel/optimizing-real-time-performance-websockets-and-react-js-integration-part-ii-4a3ada319630)
- [Building Real-Time Dashboards with React 2026](https://www.sparkleweb.in/blog/building_real-time_business_dashboards_with_react_in_2026)
- [Model2Vec: 50× Smaller, 500× Faster Embeddings — Medium](https://medium.com/coding-nexus/make-sentence-transformers-50-smaller-and-500-faster-with-model2vec-ad2b1fb002aa)
- [Best Embedding Models 2026](https://www.bentoml.com/blog/a-guide-to-open-source-embedding-models)
- [Sentence Transformers Efficiency Guide](https://sbert.net/docs/sentence_transformer/usage/efficiency.html)
- [DuckDB Concurrency](https://duckdb.org/docs/current/connect/concurrency)
- [DuckDB Quack Protocol — Medium](https://siddique-ahmad.medium.com/duckdb-just-changed-the-game-meet-quack-the-protocol-that-unlocks-multiple-writers-d339e92f0bda)
- [DuckDB in Production](https://www.dench.com/blog/duckdb-in-production)

---

## Conclusion

Parallax stack is mature and well-aligned with 2026 technology landscape. **No critical gaps identified.** Key action items are:
1. **AISstream.io integration** — High-value, low-effort immediate win
2. **Prompt caching cost tuning** — Required to stabilize budget post-TTL change
3. **Model2Vec distillation** — Performance optimization for next sprint

Phase 2 should monitor **DuckDB Quack** (multi-writer support) and **traceability frameworks** (eval scaling). Otherwise, core stack (DuckDB, deck.gl, Claude API, FastAPI) remains best-in-class for this use case through 2026-2027.
