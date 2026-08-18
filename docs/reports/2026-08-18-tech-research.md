# Parallax Tech Research Report
**Date:** August 18, 2026  
**Scope:** Spatial/Geo, LLM/Agent, Real-time Data, Eval/MLOps, Performance  
**Focus:** Identifying improvements, alternatives, and integration opportunities for Phase 1 tech stack

---

## Executive Summary

Research identified 8 high-impact findings across 5 tech categories, with 3 strong recommendations for near-term integration. Most valuable: Claude API batch processing for 50% cost reduction on offline eval workloads, real-time AIS shipping data to supplement GDELT, and structured outputs to eliminate agent output parsing errors.

---

## Findings by Category

### 1. Spatial/Geo

#### 1.1 — DuckDB Asynchronous I/O (H3 Performance)
**Status:** Upcoming in DuckDB v2.0 (Fall 2026)  
**Finding:** DuckDB v2.0 ships asynchronous Parquet and CSV reads, enabling non-blocking I/O for EC2/S3 workflows. For Parallax's single-writer topology, async reads reduce blocking on the hot path when the cascade engine queries `world_state_delta` or `world_state_snapshot` tables.

**Relevance:** MEDIUM — Beneficial only if scaling Parallax to cloud infra with remote object storage.  
**Effort:** LOW — Drop-in improvement. Requires no code changes; enable at connection time.  
**Risk:** LOW — Still beta; wait for GA in fall 2026.  
**Type:** Additive. Improves read latency without replacing current architecture.

**Source:** [DuckDB Asynchronous I/O](https://duckdb.org/2026/07/31/asynchronous-io)

---

#### 1.2 — Quack: DuckDB Multi-Writer Protocol
**Status:** Beta (v1.5.2+), GA targeted Fall 2026 with v2.0  
**Finding:** DuckDB Quack protocol enables concurrent writes across multiple instances. Current Parallax architecture mandates single-process writer via asyncio.Queue. Quack allows separation of simulation, ingestion, and eval into independent services writing to shared DuckDB without lock contention.

**Relevance:** MEDIUM-HIGH — Unlocks Phase 2 scaling (separate worker services for ingestion, eval, cascade).  
**Effort:** MEDIUM — Requires architectural refactor to separate services. Single-process topology is currently a core constraint.  
**Risk:** MEDIUM — Quack is beta through 2026. Maturity unproven at scale. Recommend waiting until GA (Q4 2026).  
**Type:** Replacement. Removes single-writer constraint but requires restructuring.

**Source:** [DuckDB Quack Protocol](https://medium.com/medium/duckdb-just-changed-the-game-meet-quack-the-protocol-that-unlocks-multiple-writers-d339e92f0bda), [DuckDB Concurrency](https://duckdb.org/docs/current/connect/concurrency)

---

#### 1.3 — deck.gl H3 TileLayer (Resolution Pyramid)
**Status:** Stable since v8.8  
**Finding:** deck.gl TileLayer supports custom indexing systems including H3. Allows multi-resolution H3 pyramids (Res 3 → Res 9) with level-of-detail (LOD) loading at zoom. Parallax currently manually manages 4 H3HexagonLayers. TileLayer can unify these into one adaptive layer.

**Relevance:** MEDIUM — Improves frontend rendering simplicity and zoom-aware performance.  
**Effort:** MEDIUM-HIGH — Refactor frontend to use TileLayer + custom H3 index function. Existing 4-layer approach works well; ROI is marginal.  
**Risk:** LOW — TileLayer is stable. Low architectural risk.  
**Type:** Additive/Simplification. Consolidates 4 layers into 1, improving code maintainability.

**Source:** [deck.gl Performance Optimization](https://deck.gl/docs/developer-guide/performance), [deck.gl TileLayer](https://deck.gl/docs/api-reference/geo-layers/tile-layer)

---

### 2. LLM/Agent Features

#### 2.1 — Claude Batch Processing API (50% Cost Reduction)
**Status:** GA, production-ready  
**Finding:** Message Batches API processes bulk requests asynchronously, cutting costs by 50% and increasing throughput. Combine with prompt caching for ~90% total cost reduction. Parallax's daily eval cron (`_run_scorecard()`, prediction scoring, prompt improvement suggestions) is a perfect batch workload — eval runs offline, throughput-limited, not latency-sensitive.

**Use Case:** Batch 10–20 daily eval jobs + prediction scoring into one batch request. Process overnight. Cost: ~$0.50/day vs $1.00/day.  
**Relevance:** HIGH — Direct cost reduction on $2–5/day daily spend. Eval cron touches every scored prediction.  
**Effort:** LOW — Isolated to `cli/brief.py` scorecard logic. Wrapper around existing Sonnet calls.  
**Risk:** LOW — Fully GA and widely used in production.  
**Type:** Additive. Improves cost without changing API behavior.

**Source:** [Claude Batch Processing](https://platform.claude.com/docs/en/build-with-claude/batch-processing), [Batch API Cost Optimization](https://claudelab.net/en/articles/api-sdk/claude-api-batch-processing-cost-optimization)

---

#### 2.2 — Claude Structured Outputs (Eliminate Parsing Errors)
**Status:** GA for Opus 4.1, Sonnet 4.5, Haiku 4.5 (since Feb 4, 2026)  
**Finding:** Structured outputs enforce JSON schema constraints on Claude's response, guaranteeing valid agent output (e.g., `AgentDecision` schema) without retry loops or fallback logic. Eliminates current risk: malformed agent JSON → error log → lost decision tick.

**Current Parallax:** Agent output manually validated against `AgentDecision` schema; malformed outputs logged and skipped.  
**Improvement:** Pass `AgentDecision` JSON schema in API request. Claude **guarantees** schema-compliant output. No validation code needed.

**Relevance:** HIGH — Eliminates silent failures in agent swarm. Malformed decisions can break cascade logic.  
**Effort:** LOW — Add `json_schema` field to agent calls in `prediction/oil_price.py`, `prediction/ceasefire.py`, `prediction/hormuz.py`.  
**Risk:** LOW — Widely adopted in production. No quality loss.  
**Type:** Simplification. Replaces manual validation code with guaranteed output.

**Source:** [Claude Structured Outputs](https://platform.claude.com/docs/en/build-with-claude/structured-outputs), [Structured Output Guarantee](https://apito.ai/en/blog/dev-guides/claude-structured-outputs-json-schema-guide-2026/)

---

#### 2.3 — Claude Opus 5 vs Sonnet 5 (Cost-Efficiency Reassessment)
**Status:** GA, released July 2026  
**Finding:** Opus 5 is 50% cheaper than Opus 4.8, at "thoughtful proactive" intelligence. Sonnet 5 launched June 2026 at $2/$10 per million tokens (through Aug 31). For country-agent decision reasoning, Sonnet 5 may now replace Opus with better cost-quality tradeoff.

**Current Parallax:** Country agents use Sonnet 4.6 (~$0.025/call). Haiku 4.5 for sub-actors (~$0.002/call).  
**Potential:** Sonnet 5 at $2/1M input ~$0.002 input cost vs Sonnet 4.6 at $3/1M ~$0.003. Cheaper + higher capability.

**Relevance:** MEDIUM — Marginal cost improvement on already-cheap calls (~$2–5/day total).  
**Effort:** LOW — Swap model ID in prediction calls: `model="claude-sonnet-5"` instead of `claude-sonnet-4-6-20250514`.  
**Risk:** LOW — Both are GA. Sonnet 5 is widely used. One-line change; can A/B test.  
**Type:** Optimization. Better cost-quality tradeoff within same tier.

**Source:** [Claude Opus 5 Release](https://medium.com/ai-for-professionals/every-powerful-claude-model-explained-in-july-2026), [Claude Models Comparison 2026](https://tygartmedia.com/claude-models-comparison/)

---

#### 2.4 — Anthropic Prompt Caching (5-min TTL Gotcha)
**Status:** GA, production-ready — **BUT** 5-minute TTL (reduced from 60min in early 2026)  
**Finding:** Prompt caching reduces cached token cost to 10%. Parallax already uses caching for agent system prompts (historical baseline ~2–3K tokens). **Critical gotcha:** TTL dropped from 60min → 5min in early 2026. Repeated agent calls > 5min apart lose cache. For batch processing, use longer cache by configuring batch timeout.

**Current Parallax:** System prompts are cached. With 50 agents × 20 events/day, cache hit rate depends on reactivation frequency (30–60min cooldown). 5min TTL may cause eviction mid-batch.  
**Optimization:** For batch eval cron, explicitly request cache persistence using TTL hints or keep batch processing within 5min window.

**Relevance:** MEDIUM — Reduces input token costs by 60–90%. Already partially implemented.  
**Effort:** LOW — Monitor cache hit rates in logging. Tune batch window size to stay within 5min.  
**Risk:** LOW — Existing feature. Main risk is cache thrashing if not tuned.  
**Type:** Optimization. Improves existing feature efficacy.

**Source:** [Prompt Caching TTL 2026](https://dev.to/whoffagents/claude-prompt-caching-in-2026-the-5-minute-ttl-change-thats-costing-you-money-4363), [Anthropic Prompt Caching Guide](https://hidekazu-konishi.com/entry/anthropic_claude_api_prompt_caching_and_token_efficiency_guide_2026)

---

### 3. Real-Time Data & Signals

#### 3.1 — AIS (Automatic Identification System) Shipping Data
**Status:** Production APIs available from Kpler/MarineTraffic, VesselFinder, Datalastic (2026)  
**Finding:** Real-time AIS vessel tracking APIs provide live ship positions with 15–30min latency. Kpler (formerly MarineTraffic) owns the largest receiver network (13,000+ receivers globally). Parallax currently uses Searoute (static routes) + parameterized vessel flow estimates. **AIS data adds ground truth**: actual vessel counts and positions in Hormuz strait, bypasses (Suez, Cape of Good Hope), and insurance routes.

**Use Case:** Ingest AIS data → H3 cells → compare predicted "reduced Hormuz flow %" against observed AIS traffic. Closes ground-truth loop.  
**Integration:** Real-time WebSocket from Datalastic or Kpler AIS API. Subscribe to Hormuz bounding box. Emit to cascade engine.  
**Relevance:** HIGH — Validates core simulation assumption (Hormuz flow reduction). Enables live ground truth without manual monitoring.  
**Effort:** MEDIUM — 1–2 weeks to integrate AIS API, model vessel counts as H3 flows, add eval metric comparing predicted vs observed traffic.  
**Risk:** MEDIUM — AIS APIs are commercial (paid subscriptions). Datalastic/Kpler pricing not quoted; likely $200–500/month for realtime historical archive. Requires vendor eval.  
**Type:** Additive. New data source; orthogonal to existing GDELT ingestion.

**Source:** [MarineTraffic API](https://support.marinetraffic.com/en/articles/9552659-api-services), [Kpler Maritime Data](https://www.kpler.com/product/maritime/data-services), [Datalastic Ship Tracking API](https://datalastic.com/), [Ship Tracking APIs 2026](https://hormuzmonitor.com/50-best-ship-tracking-apis-2026/)

---

#### 3.2 — POLECAT (Emerging Political Event Database)
**Status:** Research stage; smaller than GDELT but maturing  
**Finding:** POLECAT (Political Event Classification, Attributes, Types) is an emerging alternative to GDELT 2.0. Research from 2026 shows POLECAT exhibits high domain identification accuracy and lower redundancy than GDELT. Complements GDELT (which has noise) but smaller scale.

**Relevance:** LOW-MEDIUM — Interesting for comparison, not replacement. Would require parallel ingestion pipeline.  
**Effort:** HIGH — Requires new ingestion module, entity matching, relevance scoring per POLECAT schema.  
**Risk:** MEDIUM — Still research-stage. No clear commercial availability or API.  
**Type:** Additive. Supplement, not replace, GDELT.

**Source:** [GDELT and POLECAT Comparison](https://doi.org/10.3390/data11070158), [POLECAT Research](https://www.mdpi.com/2306-5729/10/10/158)

---

### 4. Evaluation & MLOps

#### 4.1 — Braintrust LLM Evaluation Platform
**Status:** Series B (Feb 2026, $80M at $800M valuation)  
**Finding:** Braintrust is a production-grade LLM evaluation framework: define a dataset of test cases, task function (calls LLM), and scorers (grade outputs), then run experiments with A/B comparison, regression detection, and version tracking. Parallax currently uses manual eval cron with hardcoded scoring functions (`calibration_report()`, `generate_report_card()` in `scoring/`).

**Use Case:** Braintrust can replace Parallax's manual eval pipeline. Define agent prompts as tasks, predictions as test cases, scoring functions as Braintrust scorers. Get automated A/B comparison across prompt versions.  
**Relevance:** MEDIUM — Improves eval rigor but Parallax's current eval is minimal (directional accuracy, magnitude, calibration). Braintrust shines at large eval suites.  
**Effort:** MEDIUM-HIGH — Requires refactoring eval logic into Braintrust SDK. Benefit is cleaner versioning + automated regression detection.  
**Risk:** LOW — Braintrust is GA and widely adopted. Integration is via SDK.  
**Type:** Replacement. Replaces manual eval cron with SaaS platform.

**Source:** [Braintrust Eval Guide](https://www.braintrust.dev/articles/how-to-eval), [Braintrust LLM Evaluation](https://www.braintrust.dev/articles/llm-evaluation-metrics-guide), [AI Agent Evaluation 2026](https://www.morphllm.com/ai-agent-evaluation)

---

#### 4.2 — DeepEval G-Eval (Custom Scoring Functions)
**Status:** GA, production-ready  
**Finding:** DeepEval's G-Eval framework uses Claude as a judge to score complex, domain-specific metrics (e.g., "Does this agent's reasoning align with real-world geopolitical doctrine?"). Parallax's current metrics are quantitative (hit rate, calibration). G-Eval enables qualitative scoring.

**Use Case:** "Judge the quality of agent reasoning against known geopolitical patterns" → G-Eval with custom judge prompt.  
**Relevance:** LOW-MEDIUM — Augments existing eval, not required. Useful for prompt improvement feedback loop.  
**Effort:** LOW — Wrapper around Claude API. Can be integrated incrementally into eval cron.  
**Risk:** LOW — DeepEval is open-source and GA.  
**Type:** Additive. Enhances eval without replacing current metrics.

**Source:** [DeepEval G-Eval Framework](https://inference.net/content/llm-evaluation-tools-comparison/)

---

### 5. Performance

#### 5.1 — FastAPI WebSocket Optimization (SSE vs WS)
**Status:** Best practices solidified 2026  
**Finding:** For high-frequency dashboards, FastAPI WebSockets handle bi-directional messaging but struggle at 12K+ concurrent connections. Server-Sent Events (SSE) handle 100K without issues. Parallax uses WebSockets for agent decisions + hex updates. Dashboard is uni-directional (server → client); no user input that needs low-latency response.

**Recommendation:** Consider SSE for hex cell updates + cascades (simpler, scales better). Keep WebSocket for critical bidirectional (e.g., manual override, pause/resume).  
**Relevance:** MEDIUM — Improves scalability if Parallax grows to many viewers. Current load (10–50 sessions) is not bottlenecked.  
**Effort:** MEDIUM — Requires frontend/backend refactor. Current WebSocket implementation is proven.  
**Risk:** MEDIUM — Behavioral change. Requires frontend testing.  
**Type:** Optimization. Improves scalability at higher user counts.

**Source:** [FastAPI Real-Time API Guide 2026](https://medium.com/@rameshkannanyt0078/fastapi-real-time-api-websockets-vs-sse-vs-long-polling-2026-guide-ce1029e4432e), [FastAPI WebSocket Patterns](https://medium.com/@connect.hashblock/10-fastapi-websocket-patterns-for-live-dashboards-3e36f3080510)

---

#### 5.2 — React 19 Compiler (Automatic Memoization)
**Status:** Stable since Oct 2025  
**Finding:** React 19 ships React Compiler, which automatically memoizes components and hooks (no manual useMemo/useCallback). Meta reports 12% faster initial loads and 2.5x faster interactions. Parallax frontend uses React 18.3.1 (current project). Compiler is opt-in via build flag.

**Relevance:** MEDIUM — Performance win for hex map interactions and timeline scrubbing. React 18 → 19 upgrade is in scope.  
**Effort:** MEDIUM-HIGH — Upgrade React to 19 + enable compiler. Test hex map re-renders and WebSocket update handling.  
**Risk:** MEDIUM — React 19 is stable but less proven at scale than 18. May have edge cases with custom hooks.  
**Type:** Optimization. Replaces manual memoization with compiler.

**Source:** [React 19 Dashboard Guide 2026](https://www.usedatabrain.com/how-to/create-react-dashboard), [React Compiler Performance](https://medium.com/@SanchezAllanManuel/optimizing-real-time-performance-websockets-and-react-js-integration-part-ii-4a3ada319630)

---

#### 5.3 — Vite 8 with Rolldown (Faster Builds)
**Status:** GA (March 2026)  
**Finding:** Vite 8 replaces Rollup with Rolldown (Rust-based bundler). Parallax frontend uses Vite 6.0.0. Upgrade to Vite 8 → faster builds + smaller bundle. Build performance is not currently a bottleneck, but bundle size matters for cold load on dashboard.

**Relevance:** LOW-MEDIUM — Marginal improvement on already-fast Vite builds. DOM size (deck.gl hexes) is the hot path, not bundle size.  
**Effort:** LOW — Vite upgrades are usually backwards-compatible.  
**Risk:** LOW — Vite 8 is GA and widely used.  
**Type:** Optimization. Incremental improvement in build + load time.

**Source:** [React Dashboard 2026 Guide](https://www.usedatabrain.com/how-to/create-react-dashboard)

---

## Top 3 Recommendations

### Recommendation 1: Claude Batch Processing API (HIGH Impact, LOW Effort)
**What:** Integrate Claude Batch API into `cli/brief.py` scorecard logic.  
**Why:** Direct 50% cost reduction on daily eval workload (~$1/day → $0.50/day). Eval is offline-tolerant; batch is perfect fit.  
**How:** Wrap prediction scoring + prompt feedback in Message Batches API. Process overnight. Expected timeline: **1 week**.  
**Impact:** Recurring $15/month savings. Directly improves unit economics.

---

### Recommendation 2: Claude Structured Outputs (HIGH Impact, LOW Effort, Risk Reduction)
**What:** Pass `json_schema` field when calling agent LLMs (`prediction/oil_price.py`, etc.).  
**Why:** Eliminates silent failures from malformed agent JSON. Structured outputs guarantee schema compliance. Zero quality loss.  
**How:** Update agent Sonnet calls to include `AgentDecision` JSON schema. Remove manual validation code.  
**Timeline:** **3–5 days**. Low-risk.  
**Impact:** Improves reliability. Removes error-handling complexity.

---

### Recommendation 3: Real-Time AIS Shipping Data (HIGH Impact, MEDIUM Effort)
**What:** Ingest Kpler/MarineTraffic AIS data into cascade engine. Compare predicted Hormuz flow % against observed vessel counts.  
**Why:** Closes ground-truth gap. Validates core simulation assumption. High-value signal for eval.  
**How:** 
1. Evaluate vendor pricing (Kpler/Datalastic). 
2. Subscribe to Hormuz bounding box feed.
3. Convert AIS vessel positions → H3 cell counts.
4. Add eval metric: predicted flow % vs observed AIS traffic.
**Timeline:** **2–3 weeks**. Includes vendor evaluation.  
**Impact:** Enables real ground-truth eval. Differentiator for Parallax's prediction quality.

---

## Lower-Priority Findings

| Finding | Reason to Defer |
|---------|-----------------|
| DuckDB Quack (multi-writer) | Beta through 2026. Single-writer architecture works. Revisit Q1 2027. |
| Braintrust Platform | Current eval is minimal. Justify cost later when eval complexity grows. |
| Sonnet 5 Model Swap | Marginal cost savings (~$0.10/day). Low priority. Consider in next quarter. |
| React 19 Upgrade | Current React 18 is stable. Not a blocker. Batch with Phase 2 work. |
| Vite 8 Upgrade | Build perf is not bottleneck. Include in routine dependency updates. |

---

## Data Quality Notes

- **Sources:** Primarily 2026-published articles, vendor documentation, and academic papers.
- **Vendor Evaluation:** AIS pricing not quoted in public docs. Recommend RFP to Kpler/Datalastic for Parallax's throughput + retention needs.
- **Model Versions:** Claude, DuckDB, React versions current as of August 18, 2026.

---

## Next Steps

1. **Week of Aug 19:** Begin Batch API integration. Estimate: 1 week.
2. **Week of Aug 26:** Structured outputs rollout. Estimate: 5 days.
3. **Sept 2–16:** AIS vendor evaluation + PoC integration. Decision gate: vendor pricing + API reliability.
4. **Oct 2026:** Re-assess React 19 + Vite 8 for next full release cycle.

---

*Report generated by Parallax tech research scout.*
