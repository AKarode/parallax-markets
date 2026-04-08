# Tech Research Report — 2026-04-03

## Scope

Daily technology research for Parallax geopolitical simulator Phase 1. Searched across five core improvement areas: spatial/geo, LLM/agent, real-time data, eval/MLOps, and performance optimization.

---

## Key Findings by Category

### 1. SPATIAL/GEO UPDATES

#### H3 Latest Release (January 2026)
- **Finding**: H3-py v4.4.2 released January 2026; H3 v4.1.3 integrated in Greenplum; Databricks Runtime 11.2 added 28 built-in H3 expressions for analytics
- **Relevance**: HIGH — Core to hex visualization pipeline
- **Effort**: LOW — No integration changes needed; community extension already pinned in Phase 1
- **Risk**: MATURE — H3 ecosystem stable and actively maintained
- **Assessment**: Parallax already uses pinned H3 version per design doc. New versions available for future upgrades; no immediate action required.

#### DuckDB Spatial Extension Optimization
- **Finding**: R-tree indexing benchmarks show significant execution time improvements; experimental non-standard 2D types (POINT_2D, LINESTRING_2D, POLYGON_2D) coming with potential for 2-3x faster geospatial algorithms
- **Relevance**: HIGH — Phase 1 stores 400K hexes; hot-path queries benefit most
- **Effort**: MEDIUM — Requires profile-based validation on Phase 1 workloads before migration
- **Risk**: MEDIUM — Experimental 2D types may stabilize; current spatial extension is stable
- **Assessment**: Current design uses DuckDB spatial + H3 extension; waiting on 2D type stabilization is prudent. EXPLAIN ANALYZE now recommended to identify query bottlenecks.

#### MapLibre GL Performance Gains
- **Finding**: Recent MapLibre updates improve GeoJSON rendering performance; WebGPU integration in roadmap (matches deck.gl's direction)
- **Relevance**: MEDIUM — Frontend map layer already solid with deck.gl + MapLibre GL
- **Effort**: LOW — Passive adoption via dependency updates
- **Risk**: LOW — MapLibre is stable alternative to Mapbox GL
- **Assessment**: Keep MapLibre updated; no urgent changes needed.

---

### 2. LLM/AGENT IMPROVEMENTS

#### Anthropic Prompt Caching Workspace-Level Isolation (Feb 5, 2026)
- **Finding**: Workspace-level cache instead of org-level; caches last cacheable block automatically; 90% cost reduction on cached tokens, 80% latency improvement
- **Relevance**: HIGH — Phase 1 uses static system prompts (historical baseline) for all agents; this is ideal for caching
- **Effort**: LOW — Requires API call modification to include cache control; design doc already mentions prompt caching (Section 8, estimated ~$2-5/day without caching optimizations)
- **Risk**: LOW — Feature is production-ready
- **Assessment**: **PRIORITY RECOMMENDATION** — Implement cache control on system prompts immediately. With ~50 agents and multiple tiers, could reduce LLM costs from $2-5/day to ~$0.20-0.50/day. ROI: single implementation session pays for itself in hours.

#### Anthropic Batch API Extended Output (Feb 2026)
- **Finding**: Batch API cost 50% below standard; max_tokens raised to 300k for Opus/Sonnet; optimized for prompt caching
- **Relevance**: MEDIUM — Phase 1 runs in live mode with 15-minute ingestion cycle; batch API best for async eval/replay scenarios
- **Effort**: MEDIUM — Replay mode could use batch API to process historical events asynchronously at lower cost
- **Risk**: LOW — Batch processing adds latency but eval cron and replay can tolerate it
- **Assessment**: Defer to Phase 2 for batch eval. Phase 1 live mode doesn't fit batch pattern; prompt caching is the immediate win.

#### Structured Output in Public Beta (2026)
- **Finding**: Guaranteed JSON schema conformance on Claude responses; eliminates need for response parsing/validation re-tries
- **Relevance**: HIGH — Phase 1 agent output schema (Section 3.2) relies on JSON validation; malformed responses logged and rejected
- **Effort**: LOW — Drop-in replacement for current JSON schema validation
- **Risk**: LOW — Public beta, Anthropic actively improving
- **Assessment**: Pilot structured outputs on sub-actor tier (Haiku, lowest cost). If robust, migrate country agents. Reduces validation overhead and malformed response handling.

#### Agent Orchestration Framework Landscape
- **Finding**: LangGraph (2.2x faster than CrewAI, 8-9x better token efficiency vs LangChain/AutoGen); Microsoft Agent Framework combines AutoGen + Semantic Kernel with graph workflows; crewAI for role-playing agents
- **Relevance**: LOW-MEDIUM — Phase 1 explicitly avoids LangGraph (design doc, Section 4: "Custom DES, no LangGraph")
- **Effort**: HIGH — Refactor entire simulation engine from asyncio+heapq to graph framework
- **Risk**: HIGH — Architectural rewrite; custom cascade rules may not map cleanly to framework abstractions
- **Assessment**: Reserved for Phase 2. Current custom DES is lean and fits the exact cascade logic. LangGraph is more valuable if agents need complex reasoning chains (Phase 2+ feature).

---

### 3. REAL-TIME DATA IMPROVEMENTS

#### Maritime AIS Vessel Tracking Integration (Additive)
- **Finding**: MarineTraffic (now Kpler-owned), Datalastic, VesselFinder, PortCast, Data Docked all offer real-time AIS APIs; 13k+ global AIS receivers; terrestrial updates every few seconds near shore
- **Relevance**: HIGH — Hormuz Strait shipping is critical to Phase 1 scenario; searoute provides visualization geometry only, not operational data
- **Effort**: MEDIUM — Requires API key, data ingestion pipeline, H3 cell mapping for vessel positions
- **Risk**: MEDIUM — Most are commercial APIs (costs vary); free options exist (aishub.net) but with lower update frequency
- **Assessment**: **SECONDARY RECOMMENDATION** — Add real-time AIS feed to `curated_events` pipeline. Shows actual vessel transits vs simulated rerouting. Improves ground truth collection for eval framework. Start with free aishub.net (5-10 min updates) or negotiate trial with MarineTraffic. Recommend post-Phase-1-launch (can be added without redesigning hot path).

#### GDELT Alternatives
- **Finding**: ICEWS (DoD, not public); ReliefWeb (UN humanitarian portal); Diffbot Knowledge Graph (broader entity coverage, different source patterns)
- **Relevance**: MEDIUM — GDELT is primary; alternatives are supplements or research alternatives
- **Effort**: HIGH — Requires new ingestion pipeline and three-stage filter retuning
- **Risk**: MEDIUM — GDELT has known limitations (event extraction errors, lag) but is mature and domain-proven
- **Assessment**: GDELT is solid for Phase 1. ReliefWeb could supplement for humanitarian/refugee dimensions if scenario expands; Diffbot too different (not event-focused). No immediate change needed.

#### Oil Price Forward Curves
- **Finding**: EIA forecasts available monthly; FRED (free) has WTI/Brent spot data through March 2026; CME Group has WTI futures; full forward curve requires paid provider (Nasdaq Data Link, CME)
- **Relevance**: MEDIUM — Phase 1 uses EIA API + FRED API for spot prices only (design doc notes paid provider needed for Phase 2)
- **Effort**: HIGH — Requires paid API subscription and integration
- **Risk**: MEDIUM — Cost escalation; data licensing
- **Assessment**: Stay with current spot price feeds for Phase 1. Phase 2 can integrate paid forward curve. For now, use CME futures as proxy for market expectations.

---

### 4. EVAL/MLOps IMPROVEMENTS

#### Promptfoo Open-Source Prompt Testing & A/B Testing
- **Finding**: YAML-based declarative config, CLI + CI/CD integration, LLM-as-a-judge evaluations, used by OpenAI/Anthropic
- **Relevance**: HIGH — Phase 1 has eval framework with prompt versioning (design doc, Section 7.4) but is home-grown
- **Effort**: LOW-MEDIUM — Integrate as complementary tool; can coexist with existing `predictions` table
- **Risk**: LOW — Open-source, mature, no vendor lock-in
- **Assessment**: **TERTIARY RECOMMENDATION** — Adopt Promptfoo for agent prompt versioning A/B tests. Current eval cron is daily; Promptfoo can run continuous A/B testing on new prompt versions before deployment. Replace manual admin dashboard review step with automated test gate. Quick win: 1-2 session integration.

#### LLM-as-a-Judge Evaluation (Opik, DeepEval, Langfuse)
- **Finding**: Opik (Comet-backed), DeepEval, Langfuse all support LLM-based evaluation with custom metrics and traceability
- **Relevance**: HIGH — Phase 1 eval scores are rule-based (direction, magnitude, sequence, calibration). LLM-as-judge could catch nuanced prediction misses
- **Effort**: MEDIUM — Integrate as secondary eval scorer; requires prompt engineering for judge criteria
- **Risk**: MEDIUM — LLM eval can be noisy; requires tuning
- **Assessment**: Defer to Phase 2 unless prediction miss patterns show systematic blind spots. Current rule-based eval is interpretable and sufficient for 30-day run.

---

### 5. PERFORMANCE OPTIMIZATION

#### DuckDB Query Tuning
- **Finding**: EXPLAIN ANALYZE is essential; filter pushdown is single biggest win; Parquet >> CSV; ENUM types reduce storage and improve query speed; allocate 80-90% RAM
- **Relevance**: HIGH — Phase 1 stores `world_state_delta` at high frequency; queries must be fast for replay and eval
- **Effort**: LOW — Profiling and query rewrites; no infrastructure change
- **Risk**: LOW — Safe, non-breaking optimization
- **Assessment**: Before Phase 1 launch, run EXPLAIN ANALYZE on all hot-path queries (world state reconstruction, prediction fetch, cascade evaluation). Convert any raw string columns to ENUM if repeated. Use Parquet format for snapshot exports.

#### React WebSocket Batching for Real-Time Dashboards
- **Finding**: Batching updates every 100-200ms reduces frontend CPU by up to 65%; best practices: useRef for high-frequency updates, requestAnimationFrame for paint sync, Web Workers for heavy compute
- **Relevance**: HIGH — Phase 1 frontend design doc (Section 5.2) notes WebSocket batching is already planned ("buffer incoming updates for 100ms, then flush as a single mutation to the ref")
- **Effort**: LOW — Already designed; implementation is during frontend dev
- **Risk**: LOW — Well-established pattern
- **Assessment**: Design doc already prescriptive here. Ensure implementation follows: useRef for hex data, 100ms buffer, DataFilterExtension for deck.gl updates. No remote changes needed.

---

## Top 3 Recommendations

### 1. Implement Anthropic Prompt Caching (IMMEDIATE)
**Rationale**: System prompts are static per agent version; workspace-level isolation now available. 90% token cost reduction on cached prefix. Phase 1 estimated $2-5/day LLM cost could drop to $0.20-0.50/day. Single API modification. Zero risk.

**Action**: Add `cache_control: { type: "ephemeral" }` to system prompt block in Claude API calls. Verify cache hit rates in first 48 hours. Target: Deploy before Phase 1 public launch.

**Effort**: 1-2 hours

---

### 2. Integrate Real-Time AIS Vessel Tracking (POST-LAUNCH)
**Rationale**: Searoute provides visualization only; real AIS data improves ground truth collection and demonstrates live integration. Hormuz shipping is core to scenario credibility. Low risk if decoupled from core cascade engine.

**Action**: Add AIS ingestion to `curated_events` pipeline (parallel track to GDELT). Map vessel positions to H3 cells at appropriate resolution. Include in replay data collection. Use free aishub.net API initially; negotiate MarineTraffic trial if budget allows.

**Effort**: 2-3 sessions

**Risk**: API availability; commercial terms

---

### 3. Adopt Promptfoo for Agent Prompt A/B Testing (PHASE 1.1)
**Rationale**: Current eval framework has manual prompt review step. Promptfoo automates A/B testing with YAML config, CI/CD integration, and LLM-as-judge scoring. Reduces admin burden; speeds prompt iteration.

**Action**: Configure Promptfoo with agent prompt versions and test dataset (curated events from first 7 days of Phase 1 run). Integrate as gate before new prompt deployment. Hook to admin dashboard.

**Effort**: 1-2 sessions

---

## Sources

- [H3 GitHub](https://github.com/uber/h3)
- [H3 Official Docs](https://h3geo.org/)
- [DuckDB Spatial Extension](https://duckdb.org/docs/current/core_extensions/spatial/overview)
- [H3-DuckDB Extension](https://github.com/isaacbrodsky/h3-duckdb)
- [DuckDB Community Extensions Directory](https://query.farm/duckdb_community_extensions_directory)
- [Claude API Prompt Caching](https://platform.claude.com/docs/en/build-with-claude/prompt-caching)
- [Claude API Batch Processing](https://platform.claude.com/docs/en/build-with-claude/batch-processing)
- [Claude API Release Notes](https://platform.claude.com/docs/en/release-notes/overview)
- [LLM Orchestration Frameworks 2026](https://aimultiple.com/llm-orchestration)
- [Agent Framework Overview (Microsoft)](https://learn.microsoft.com/en-us/agent-framework/overview/)
- [GDELT Project](https://www.gdeltproject.org/)
- [MarineTraffic / Kpler](https://www.kpler.com/product/maritime/data-services)
- [VesselFinder AIS API](https://www.vesselfinder.com/realtime-ais-data)
- [Data Docked - AIS API](https://datadocked.com/vessel-location-api)
- [EIA Short-Term Energy Outlook](https://www.eia.gov/outlooks/steo/)
- [FRED Oil Price Data](https://fred.stlouisfed.org/series/DCOILWTICO)
- [CME Crude Oil Futures](https://www.cmegroup.com/markets/energy/crude-oil/light-sweet-crude.html)
- [Promptfoo GitHub](https://github.com/promptfoo/promptfoo)
- [Langfuse A/B Testing](https://langfuse.com/docs/prompt-management/features/a-b-testing)
- [Braintrust A/B Testing](https://www.braintrust.dev/articles/ab-testing-llm-prompts)
- [DuckDB Performance Tuning](https://duckdb.org/docs/current/guides/performance/how_to_tune_workloads)
- [DuckDB Speed Optimization Tips](https://medium.com/@hadiyolworld007/duckdb-speed-secrets-10-tricks-for-2026-29c990a8701d)
- [React WebSocket Real-Time Dashboards](https://oneuptime.com/blog/post/2026-01-15-websockets-react-real-time-applications/view)
- [React Real-Time Performance Optimization](https://medium.com/@SanchezAllanManuel/optimizing-real-time-performance-websockets-and-react-js-integration-part-ii-4a3ada319630)

---

## Summary

No blockers or critical gaps identified. Phase 1 tech stack is well-positioned for 30-day continuous eval run. Top priority: **prompt caching implementation** (immediate cost savings). Secondary win: **real-time AIS integration** (improves ground truth). Tertiary: **Promptfoo adoption** (speeds prompt iteration). All three are low-risk, additive improvements that enhance rather than refactor core architecture.
