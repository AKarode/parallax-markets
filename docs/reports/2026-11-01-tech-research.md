# Technology Research Report — Nov 1, 2026
## Parallax Geopolitical Simulator Stack Review

**Scope:** Searched for improvements across Spatial/Geo, LLM/Agent, Real-time Data, Eval/MLOps, and Performance categories.

---

## 1. Spatial & Geospatial Visualization

### Finding: R `duckh3` Package & Spatial Ecosystem Maturity

**What:** CRAN released `duckh3` v0.1.0 (April 2026) and `duckspatial` v1.2.1 (July 2026) as R bindings for DuckDB's H3 and spatial extensions. DuckDB's H3 extension is now a stable community extension with tens of thousands of weekly downloads.

**Relevance to Parallax:** **MEDIUM**
- **Pro:** Validates that the H3 + DuckDB stack is actively maintained and matured. Community support is growing.
- **Con:** The R packages don't directly help Python. DuckDB's Python interface already supports H3; no Python-side gains from the R ecosystem.

**Effort:** Low (informational; no code change needed)
**Risk/Maturity:** Low — DuckDB spatial is stable; ecosystem growth is positive signal.
**Type:** Additive (validation of current stack choice)

**Recommendation:** Continue with current DuckDB H3 setup. Monitor for Python-specific performance improvements in future DuckDB releases.

---

### Finding: deck.gl H3HexagonLayer Performance Tuning

**What:** deck.gl's H3HexagonLayer has high-precision rendering modes (`highPrecision: 'auto' | true | false`) and a high-performance path via the `_dataDiff` prop that skips attribute recomputation when data changes only partially. Picking (interactivity) adds overhead; disabling it is a performance lever if not needed.

**Relevance to Parallax:** **HIGH**
- **Pro:** Directly addresses the dashboard's render bottleneck. Current design already accounts for this (mutable refs + batching), but the `_dataDiff` prop could reduce GPU upload frequency further.
- **Con:** Requires testing to validate latency gains; picking interactions are useful for the dashboard.

**Effort:** Medium (1-2 hours to profile and benchmark with current data flow)
**Risk/Maturity:** Low — deck.gl is stable; the `_dataDiff` prop is documented.
**Type:** Optimization (replaces/enhances current batching strategy)

**Recommendation:** Add `_dataDiff` profiling to next performance sprint. Profile high-precision vs auto modes with live ~400K hex load to measure frame rate impact. Keep picking enabled; the interactivity value outweighs the cost at current scales.

---

## 2. LLM / Agent Reasoning & Structured Output

### Finding: Claude API Structured Outputs (GA Jan 2026) + Batch Caching Stacking

**What:** 
- Structured outputs (JSON mode) went GA on Jan 29, 2026 for Haiku/Sonnet/Opus 4.5+.
- Parameter moved from `output_format` to `output_config.format` on Feb 7, 2026 (old param still works during transition).
- Message Batches API now supports prompt caching, and caching TTLs can be configured to 1 hour for batch work (vs 5 min for live calls).
- **Extended batch output beta** (output-300k-2026-03-24 header) raises max_tokens to 300K for certain models.

**Relevance to Parallax:** **HIGH**
- **Pro:** Agents currently output structured JSON via prompting; structured outputs provide validation-at-source. Batch API + caching can reduce sub-actor call costs by 50% + an additional 90% on cached tokens — massive leverage for the $20/day budget.
- **Con:** Batch API introduces latency (intended for non-real-time work). Current live agents need synchronous responses; batch is only viable for offline eval/cold-start work.

**Effort:** Medium
- Structured outputs: Low (swap to `output_config` parameter, add schema validation).
- Batch API: High (separate async pipeline for eval cron and bootstrap; live agents stay on sync endpoint).

**Risk/Maturity:** Low — All GA features. Transition period for parameter names suggests good backward compatibility.
**Type:** Optimization (reduces LLM spend + improves output reliability)

**Recommendation:** 
1. **Immediate:** Adopt structured outputs for live agents (Haiku sub-actors, Sonnet country agents). Use `output_config.format` with agent response schema. Adds reliability at minimal cost.
2. **Next phase:** Implement Message Batches for daily scorecard cron and prompt improvement meta-agent. Estimated cost reduction: ~40% on eval work.

---

### Finding: Prompt Versioning & A/B Testing Tools Convergence

**What:** 2026 tools now tightly couple prompt versioning with A/B testing and evaluation traceability:
- **Langfuse** (open-source): Full lineage tracking (prompt version → model → dataset) linked to eval scores.
- **Promptfoo** (CLI-based): YAML prompts + tests, pull request-native workflow.
- **Agenta** (commercial): Prompt versioning + LLM-as-judge + A/B deployment testing.
- Key theme: **Context versioning matters** — experiments must version context bundle alongside prompt, or you're comparing two contexts instead of two prompts.

**Relevance to Parallax:** **HIGH**
- **Pro:** Current design has `prompt_version` tagging in predictions and an admin dashboard for manual prompt editing. Integrating a tool like Langfuse would automate lineage, add statistical significance testing, and enable rapid iteration on underperforming agents.
- **Con:** Requires new dependencies and a UI layer. Parallax already does prompt versioning manually; the marginal value is automation + stats.

**Effort:** Medium
- Integration: 3-5 days (ingest Langfuse SDK, tag LLM calls with version/dataset/context hashes, push eval scores back).
- Breakeven: Requires at least 2-3 prompt iterations to justify setup cost.

**Risk/Maturity:** Low — Langfuse is open-source with production users. Promptfoo is mature. Both are actively developed.
**Type:** Additive (enhances existing prompt versioning with automation)

**Recommendation:** 
- **If prompt iteration becomes frequent:** Adopt Langfuse for automated experiment tracking and statistical significance testing. This fits Parallax's daily eval cycle.
- **If iteration is infrequent:** Keep current manual system; cost/benefit doesn't justify integration yet.
- **Near-term:** Document current prompt versioning discipline (system prompts in `agent_prompts` table, eval feedback loop). This foundation makes future tool adoption cheaper.

---

## 3. Real-Time Data Sources

### Finding: GDELT Remains Default; ACLED is Better for Verification

**What:** 
- **GDELT:** Still the standard for high-volume, near-real-time event data (15-min feed latency via BigQuery). No verified substitute for news-derived signals.
- **ACLED:** Curated conflict events (researchers review sources and code events). More accurate but weekly-only batches, so lagged.
- **Commercial alternatives:** Dataminr, Samdesk, Factal, Crisis24 offer true real-time alerts but at enterprise cost and undisclosed latency.
- **Data quality caveat:** News coverage ≠ verified incident count. Always cross-check event times against other sources.

**Relevance to Parallax:** **MEDIUM**
- **Pro:** Current design already uses GDELT for speed and ACLED for validation (weekly). Recommendation is to keep this mix.
- **Con:** No free, high-speed alternative to GDELT that's better. ACLED's weekly lag makes it unsuitable for real-time prediction.

**Effort:** None (current setup is optimal for cost/speed/verification trade-off)
**Risk/Maturity:** Low — GDELT and ACLED are both stable, well-documented data sources.
**Type:** Validation (confirms current strategy is sound)

**Recommendation:** Maintain current GDELT + ACLED mix. If enterprise real-time is required in Phase 2, evaluate Dataminr or Crisis24, but expect 10x+ cost increase.

---

### Finding: AIS (Automatic Identification System) Shipping Data Is Now Accessible

**What:**
- **AISdb** (Python, open-source, 2024 SoftwareX): Database and analysis toolkit for AIS vessel positions. Clean, query-able, integrates with environmental datasets.
- **AISStream:** Real-time AIS feed (WebSocket + REST). Requires API key. Covers ship properties, voyage data, binary messages.
- **AISHub:** Cooperative data-sharing network. Free access by contributing your own AIS feed; no pay tier clearly documented.
- **ShipFinder:** Commercial API. GPS positions + properties. "Global coverage" doesn't guarantee uninterrupted feeds; check timestamps.

**Relevance to Parallax:** **MEDIUM-HIGH**
- **Pro:** AIS provides ground-truth vessel position data for Hormuz corridor. Could validate model predictions (e.g., "model predicts 40% traffic reduction; AIS shows 38% actual reduction").
- **Con:** AIS position data is relatively low-value without context (who owns ship, cargo type, destination). Requires supplemental data (shipping registries, cargo APIs) to ground predictions.
- **Latency:** AIS positions update every ~10 seconds for active vessels but are aggregated by the time they reach free APIs (typically 1-5 min lag).

**Effort:** Medium
- Integration: 2-3 days (AISdb setup, position tracking in H3, comparison pipeline).
- Requires: Choosing between AISStream (real-time, requires key) and AISHub (free, requires feed contribution).

**Risk/Maturity:** Medium
- AISdb is research code, not production-hardened.
- AISStream and AISHub terms of service may change; verify current access model before committing.

**Type:** Additive (enhances model validation with real-world vessel data)

**Recommendation:** 
- **Phase 1.5 (if time permits):** Integrate AISdb for vessel count + flow estimation through Hormuz. Validate model predictions daily. Build a simple query: `SELECT COUNT(*) FROM ais_positions WHERE timestamp > now - 1h AND location IN hormuz_corridor_h3_cells`.
- **Do not rely on AIS for real-time control decisions** (e.g., paper trades). Latency and gaps make it unsuitable for that. Use it for post-hoc validation only.

---

## 4. Evaluation & MLOps

### Finding: LLM Eval Frameworks Emphasize Statistical Rigor (New in 2026)

**What:** 
- **Statistical significance testing:** Atlan's 2026 guide emphasizes rigorous significance testing for LLM A/B tests (controlling for multiple comparisons, sample size, variance).
- **Tools:** DeepEval, RAGAS, Promptfoo, Phoenix, TruLens all provide eval scoring. Langfuse/PromptLayer/Agenta add versioning and deployment workflows.
- **Key limitation:** Most open-source tools focus on information retrieval (RAGAS) or general correctness (DeepEval). Few are tuned for prediction accuracy evaluation (the kind Parallax needs).
- **Note:** PostHog's LLM experimentation was in beta as of July 2026; likely GA now.

**Relevance to Parallax:** **MEDIUM**
- **Pro:** Parallax already has a custom eval framework (direction, magnitude, calibration scoring). LLM eval frameworks could accelerate scoring logic and add statistical rigor.
- **Con:** Prediction accuracy evaluation (calibration curves, resolution bands) is domain-specific. Off-the-shelf tools are not tailored to this use case.

**Effort:** Medium
- Integration: 2-3 days to add Langfuse instrumentation to prediction pipeline. Calibration scoring stays custom.

**Risk/Maturity:** Medium
- Langfuse is production-ready; Promptfoo and Phoenix are solid.
- Statistical testing libraries (scipy.stats, pingouin) are standard and mature.

**Type:** Additive (instrumentation + historical comparison tools)

**Recommendation:** 
- **Next eval iteration:** Add Langfuse SDK to the prediction pipeline. Tag each prediction with prompt_version, dataset_date, and context_hash. This provides free historical comparison and enables statistical significance testing without major refactoring.
- **Do not rely on generic LLM eval frameworks for calibration scoring.** Keep custom logic for direction/magnitude/calibration — they're domain-specific to prediction markets.

---

## 5. Performance & Frontend

### Finding: React Real-Time Dashboard Rendering Strategy (2026 Best Practice)

**What:**
- **Bottleneck is rendering, not WebSockets.** High-frequency updates cause React reconciliation thrash if each update triggers a re-render.
- **Solutions:** 
  1. Decouple data (mutable refs) from UI state (React state). Data updates mutate refs; only UI state changes trigger re-renders.
  2. Batch updates (100ms windows).
  3. Virtualize large lists (for agent feed).
  4. Use libraries like `react-use-websocket` for connection lifecycle management.
- **Parallax is already doing this.** Current design uses mutable refs + batching (100ms) per the design doc.

**Relevance to Parallax:** **MEDIUM** (already implemented; this is validation)
- **Pro:** Confirms current architecture is aligned with 2026 best practices.
- **Con:** No immediate gains; would require profiling to identify further optimizations.

**Effort:** Low (monitoring/profiling only)
**Risk/Maturity:** Low — Current pattern is well-established.
**Type:** Validation (confirms current design is sound)

**Recommendation:** 
- **Next performance sprint:** Profile React render time (use React DevTools Profiler) and WebSocket message rates during high-activity scenarios. Confirm that mutable ref + batching keeps frame rate > 30 fps.
- **If render time exceeds 16ms/frame:** Consider Virtualization for the agent feed (currently scrolling, will bloat if events accumulate).

---

## Top 3 Recommendations (Ranked by Impact + Effort)

### 1. Adopt Claude Structured Outputs + Plan Batch API Integration

**Impact:** HIGH — Structured outputs improve agent output reliability; Batch API reduces eval costs by 40-50%.
**Effort:** Medium (structured outputs: 2-3 hours; Batch integration: 2-3 days for eval pipeline).
**Timeline:** Immediate (structured outputs), next sprint (Batch).

**Action:** 
- Migrate agent responses to `output_config.format` with JSON schema.
- Prototype Message Batches for daily scorecard cron and prompt improvement meta-agent.

---

### 2. Integrate AIS Data for Prediction Validation

**Impact:** MEDIUM-HIGH — Ground-truth vessel data validates model predictions (key to earning edge).
**Effort:** Medium (2-3 days for AISdb + query pipeline).
**Timeline:** Phase 1.5 (if time permits before eval deadline April 21).

**Action:**
- Set up AISdb + query vessel counts in Hormuz corridor.
- Add daily comparison: model flow reduction vs actual AIS count change.
- Publish comparison metrics to dashboard.

---

### 3. Instrument Eval Pipeline with Langfuse (If Prompt Iteration Becomes Frequent)

**Impact:** MEDIUM — Automates prompt versioning, enables statistical significance testing.
**Effort:** Medium (3-5 days for SDK integration + dashboard setup).
**Timeline:** After eval deadline if iteration velocity is high (> 2 prompt changes/week).

**Action:**
- Evaluate current prompt change frequency.
- If > 2 changes/week, integrate Langfuse for experiment tracking.
- If ≤ 2 changes/week, keep manual system; ROI is low.

---

## Low-Priority Findings (No Immediate Action)

- **Prompt evaluation tools (Promptfoo, etc.):** Current manual system works; adopt only if prompt iteration velocity increases.
- **Commercial real-time alerting (Dataminr, Crisis24):** Out of budget for Phase 1; revisit for Phase 2 if live trading is proven.
- **H3HexagonLayer micro-optimizations (highPrecision tuning):** Profile first before investing; current batching strategy likely sufficient.

---

## Sources

### Spatial/Geo
- [Awesome DuckDB Spatial](https://github.com/alperdincer/Awesome-DuckDB-Spatial/)
- [duckh3 CRAN Package](https://cran.r-project.org/web/packages/duckh3/index.html)
- [H3 DuckDB Community Extension](https://duckdb.org/community_extensions/extensions/h3)
- [deck.gl H3HexagonLayer Docs](https://deck.gl/docs/api-reference/geo-layers/h3-hexagon-layer)
- [Lonboard H3 Layer Docs](https://developmentseed.org/lonboard/latest/api/layers/h3-hexagon-layer/)

### LLM/Agent
- [Claude API Release Notes](https://platform.claude.com/docs/en/release-notes/api)
- [Structured Outputs Docs](https://platform.claude.com/docs/en/build-with-claude/structured-outputs)
- [Batch Processing Docs](https://platform.claude.com/docs/en/build-with-claude/batch-processing)
- [LLM A/B Testing Framework](https://atlan.com/know/ab-testing-llm-applications/)
- [Best Prompt Evaluation Tools 2026](https://www.braintrust.dev/articles/best-prompt-evaluation-tools-2025)
- [LLM Evaluation Frameworks](https://medium.com/@future_agi/llm-evaluation-frameworks-metrics-and-best-practices-2026-edition-162790f831f4)
- [DeepEval Eval Frameworks](https://deepeval.com/blog/top-5-llm-evaluation-frameworks)
- [Promptfoo LLM Testing](https://qaskills.sh/blog/promptfoo-llm-testing-guide)

### Real-Time Data
- [GDELT Project](https://en.wikipedia.org/wiki/GDELT_Project)
- [ACLED](https://en.wikipedia.org/wiki/Conflict_and_Mediation_Event_Observations)
- [Geopolitical Risk Monitor Guide](https://halleytech.substack.com/p/building-a-geopolitical-risk-monitor-data-indicators-signals)
- [Dataminr Alternatives](https://offnadir-delta.com/blog/dataminr-alternatives-event-intelligence)
- [Best Geopolitical Risk Dashboards](https://www.worldmonitor.app/compare/best-geopolitical-risk-dashboards/)
- [Best Global Conflict Trackers 2026](https://www.worldmonitor.app/blog/posts/best-global-conflict-trackers-2026/)
- [AISdb Python Package](https://pypi.org/project/aisdb/)
- [AIS-ws-feedhandler](https://github.com/lcsrodriguez/AIS-ws-feedhandler)
- [SoftwareX: AISdb Paper (2024)](https://doaj.org/article/820b0928226445669e02858706cd49df)
- [AIS Data Tracking Tutorial](https://dev.to/shipfinder/how-to-use-an-ais-data-api-for-vessel-tracking-mi3)

### Performance
- [WebSockets in React 2026](https://oneuptime.com/blog/post/2026-01-15-websockets-react-real-time-applications/markdown)
- [Real-time Dashboard with React & WebSockets](https://dev.to/viitorcloud/build-real-time-dashboards-with-react-and-websockets-for-businesses-1169)
- [React Performance: Real-time Scale Strategies](https://stevekinney.com/courses/react-performance/real-time-scale-strategies)

---

**Report generated:** November 1, 2026
**Search scope:** Extended research on 5 tech categories
**Status:** No major stack changes recommended. Pursue structured outputs + Batch API for cost efficiency, AIS integration for validation, and Langfuse if prompt iteration accelerates.
