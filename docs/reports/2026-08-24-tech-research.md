# Tech Research Report: 2026-08-24

**Research Focus:** Spatial/geo visualization, LLM/agent orchestration, real-time event data, eval/MLOps, performance optimization

---

## Executive Summary

Research identified **three high-impact opportunities** for Parallax Phase 2+:
1. **Claude Batch API + Prompt Caching**: Can reduce LLM inference costs by 95%+ (prediction models + eval pipeline)
2. **Real-time AIS shipping APIs**: Supplement GDELT with granular maritime tracking for Hormuz corridor (high confidence signals)
3. **Helicone/equivalent for prompt versioning**: Native A/B testing + regression detection for the agent swarm

Current stack (H3, DuckDB, deck.gl, FastAPI) remains solid with no immediate replacements needed. Extensions exist but are additive rather than critical.

---

## Findings by Category

### 1. Spatial/Geo: H3 and DuckDB Spatial

**Status:** Healthy ecosystem, no urgent changes needed

#### DuckDB H3 Community Extension
- **Current status**: Actively maintained community extension ([h3 – DuckDB Community Extensions](https://duckdb.org/community_extensions/extensions/h3))
- **2024 adoption**: FOSS4G NA 2024 featured talks on using H3-DuckDB for geospatial operations; Isaac Brodsky maintains the bindings
- **What it does**: Full H3 API exposed to SQL; hierarchical hexagonal indexing for geospatial data
- **Parallax use**: Already pinned in deployment — no action needed
- **Relevance**: MEDIUM (already integrated)
- **Effort**: 0 (no change required)
- **Risk**: LOW

#### DuckDB Spatial Extension (GEOMETRY type)
- **Status**: Core extension in DuckDB ([Spatial Extension – DuckDB](https://duckdb.org/docs/current/core_extensions/spatial/overview))
- **What it does**: Simple Features geometry model + specialized columnar native types
- **Parallax use**: Currently optional; could enhance port/chokepoint indexing
- **Relevance**: LOW-MEDIUM (nice to have, not blocking)
- **Effort**: LOW (library is mature)
- **Risk**: LOW
- **Note**: Parallax could use GEOMETRY for port polygons and chokepoint boundaries, reducing custom JSON parsing

#### Recommendation
No changes for Phase 1. For Phase 2, if Parallax scales to multi-scenario support, adopt DuckDB Spatial for cleaner querying of static infrastructure (ports, zones).

---

### 2. LLM/Agent Orchestration: Claude API Batch + Caching

**Status:** Massive cost savings opportunity; Swarm Mode emerging

#### Prompt Caching (Announced Aug 2024, GA Dec 2024)
- **Status**: Generally available on Claude API ([Batch processing - Claude Platform Docs](https://platform.claude.com/docs/en/build-with-claude/batch-processing))
- **Cost reduction**: 90% off cached tokens; cache writes cost 2x but read discount exceeds write cost
- **Cache TTL**: 5-minute default, 1-hour option for $0.30 per million tokens vs $0.15 for 5-min
- **Parallax fit**: ✓ EXCELLENT — system prompts (agent historical baseline) are static per version
- **Current implementation**: Already using prompt caching per spec (Section 8 mentions "Use Anthropic's prompt caching for system prompts")
- **Relevance**: HIGH (already implemented; verify usage)
- **Effort**: MINIMAL (verify cache TTL config)
- **Risk**: LOW

#### Batch Processing API (2024)
- **Status**: Generally available ([Claude Batch API: Process Thousands of Requests at 50% Lower Cost](https://claudeimplementation.com/blog/claude-batch-api))
- **Cost reduction**: 50% off batch requests + stacks with prompt caching (95%+ combined savings possible)
- **Throughput**: Asynchronous, processes 10K+ requests overnight at lower cost
- **Max tokens**: Raised to 300k for Claude Opus/Sonnet on batches
- **Parallax fit**: ✓ EXCELLENT — eval pipeline, nightly scorecard computation, historical replay
- **Current implementation**: Unknown — not mentioned in spec
- **Relevance**: HIGH (not yet implemented)
- **Effort**: MEDIUM (refactor eval pipeline to batch format; ~1-2 days)
- **Risk**: MEDIUM (eval pipeline is critical path; requires testing before rollout)
- **Estimated savings**: $200-500/month on evaluation calls alone

**Recommendation**: Adopt Batch API for nightly eval pipeline and monthly historical replayback. Can defer to Phase 2 if under budget pressure in Phase 1.

#### Claude Code Swarm Mode (Early 2026)
- **Status**: New feature for multi-agent orchestration via Claude Code ([Claude Code Swarm Orchestration Skill](https://gist.github.com/kieranklaassen/4f2aba89594a4aea4ad64d753984b2ea))
- **What it does**: Parallelize independent agents via TeammateTool (13 core operations), automatic worktree isolation to prevent conflicts
- **Parallax fit**: ✓ GOOD — Agent swarm (50 agents) could split work across dedicated agents per country
- **Current implementation**: Custom asyncio-based swarm; LangGraph explicitly out-of-scope in Phase 1
- **Relevance**: MEDIUM (nice optimization; not required)
- **Effort**: HIGH (would require rearchitecting agent swarm to Claude Code semantics)
- **Risk**: MEDIUM-HIGH (new feature; less proven than custom asyncio)
- **Recommendation**: Monitor for Phase 2+. Custom asyncio swarm is proven and stays. Swarm Mode is for teams using Claude Code CLI, not backend services.

---

### 3. Real-Time Data: GDELT + AIS Shipping APIs

**Status:** GDELT remains dominant; new maritime supplement emerging

#### GDELT Ecosystem (Remains Primary)
- **Status**: Still the academic/commercial standard ([The GDELT Project](https://www.gdeltproject.org/solutions.html))
- **Coverage**: 100% global, ~63M records/year, 15-min update cycle
- **Recent additions**: GDELT Guru (AI context understanding layer) ([GDELT Guru - AI-Powered Global Intelligence Platform](https://gdelt.guru/))
- **Relevance**: HIGH (core data source)
- **Effort**: 0 (already integrated)
- **Risk**: LOW (GDELT is stable)
- **Note**: No replacements exist; GDELT's scale and coverage are unmatched

#### AIS Shipping Data APIs (NEW OPPORTUNITY)
- **Providers**: Kpler (dominant, 13K+ receivers), MarineTraffic (unified under Kpler Sept 2025), VesselFinder, VesselAPI (free tier), Data Docked
- **Data**: Real-time vessel positions, port events, emissions, historical AIS
- **Parallax fit**: ✓ EXCELLENT — Hormuz corridor detail; current shipping flow ground-truth
- **Relevance**: HIGH (fills gap in maritime signal quality)
- **Effort**: MEDIUM (integrate Kpler or VesselAPI; ~2-3 days)
- **Risk**: LOW (APIs are mature; cost ~$100-500/month depending on volume)
- **Use case**: Validate GDELT "tanker seizure" signals against real Hormuz traffic drop; ground-truth for predictions
- **Reference**: [50 Best Ship Tracking APIs 2026 - Strait of Hormuz](https://hormuzmonitor.com/50-best-ship-tracking-apis-2026/), [VesselAPI: AIS Tracking & Maritime Data REST API](https://vesselapi.com/)

**Recommendation**: Add Kpler or VesselAPI integration for Phase 2. AIS data is **ground truth** for predictions; validates GDELT events. VesselAPI offers free tier for pilot; Kpler is gold standard for financial clients.

#### Open-Source Option: OpenAIS
- **Status**: Set of tools for deriving insight from vessel data ([OpenAIS](https://open-ais.org/))
- **Fit**: Good for data preprocessing; not a replacement for live APIs
- **Effort**: LOW (if deploying self-hosted AIS receiver)
- **Relevance**: LOW-MEDIUM (supplementary, requires infrastructure)

---

### 4. Eval/MLOps: Prompt Versioning and A/B Testing

**Status:** Mature frameworks available; Parallax has manual process

#### Helicone (Open-Source + Hosted)
- **Status**: Comprehensive monitoring, versioning, and eval ([Helicone](https://www.helicone.ai/blog/prompt-evaluation-frameworks))
- **Features**: Prompt experiment tracking, A/B testing, regression detection, LLM-as-judge evaluation
- **Parallax fit**: ✓ GOOD — Could automate the "Admin reviews and approves/rejects" step in eval pipeline
- **Current implementation**: Manual dashboard per spec (Section 7)
- **Relevance**: MEDIUM (improves eval workflow; not required for MVP)
- **Effort**: MEDIUM (integrate API; wire into prediction log)
- **Risk**: LOW
- **Cost**: Open-source (self-hosted) or $50-500/month (hosted)
- **Recommendation**: Defer to Phase 2 if satisfactory with manual eval dashboard. Use for scaling multi-scenario evals.

#### PromptLayer, Braintrust, Agenta
- **Status**: Similar to Helicone; ecosystem converging on common patterns
- **Parallax fit**: GOOD (all support versioning + A/B testing + human review)
- **Relevance**: MEDIUM (alternative to Helicone; pick one)
- **Effort**: MEDIUM
- **Recommendation**: If adopting external platform, Helicone or Braintrust are industry defaults.

#### GDELT Guru (AI Context Layer)
- **Status**: New AI-powered GDELT wrapper ([GDELT Guru](https://gdelt.guru/))
- **What it does**: Adds semantic understanding, predicts outcomes, identifies hidden connections
- **Parallax fit**: ✓ INTERESTING — Could feed into agent reasoning or eval scoring
- **Relevance**: LOW-MEDIUM (exploratory)
- **Effort**: LOW (API integration)
- **Risk**: MEDIUM (early product; not proven in production)
- **Recommendation**: Monitor; not a dependency for Phase 1.

**Recommendation**: Stay manual for Phase 1 (dashboard is sufficient). Integrate Helicone or Braintrust for Phase 2 if scaling to multi-scenario evals or adopting Swarm Mode agents.

---

### 5. Performance: DuckDB, WebSocket, React

**Status:** Current architecture is sound; optimization patterns proven

#### DuckDB Vectorized Execution (Already Leveraged)
- **Status**: Core strength of DuckDB ([DuckDB in Depth](https://endjin.com/blog/duckdb-in-depth-how-it-works-what-makes-it-fast))
- **What it does**: Processes data in 1024-2048 item batches (vectors) in CPU L1 cache; 10-50x faster than row-at-a-time
- **Parallax use**: Already used implicitly (DuckDB default)
- **Relevance**: HIGH (core strength)
- **Effort**: 0 (automatic)
- **Risk**: NONE
- **Actionable**: Ensure delta + snapshot strategy respects batch sizes (1K row inserts per batch preferred)

#### WebSocket Message Batching (Already Specified)
- **Status**: Best practice for real-time dashboards ([Optimizing Real-Time Performance Part I](https://medium.com/@SanchezAllanManuel/optimizing-real-time-performance-websockets-and-react-js-integration-part-i-e563664647d3))
- **Parallax spec**: Section 5 already specifies "buffer incoming updates for 100ms, then flush as a single mutation"
- **Implementation**: ✓ Already in design
- **Relevance**: HIGH (critical for render performance)
- **Effort**: 0 (already specified)
- **Risk**: NONE

#### React State Decoupling via useRef (Already Specified)
- **Status**: Standard optimization for high-frequency updates ([Real-time Updates with WebSockets and React Hooks](https://www.geeksforgeeks.org/reactjs/real-time-updates-with-websockets-and-react-hooks/))
- **Parallax spec**: Section 5 specifies "H3 hex data lives in a mutable useRef, not useState"
- **Implementation**: ✓ Already in design
- **Relevance**: HIGH (prevents render thrashing)
- **Effort**: 0 (already specified)
- **Risk**: NONE

#### deck.gl Performance (Verified)
- **Status**: Mature library; no critical issues ([deck.gl Performance Guide](https://deck.gl/docs/developer-guide/performance))
- **Parallax use**: H3HexagonLayer with 400K hexes (within 500K comfort zone)
- **Relevance**: HIGH (core viz)
- **Effort**: 0 (already integrated)
- **Risk**: LOW

**Recommendation**: No changes needed. Current architecture already incorporates proven patterns. Verify in Phase 1 testing that WebSocket batching actually works as designed (common pitfall: batching breaks if not implemented carefully).

---

## Top 3 Recommendations

### 1. **Adopt Claude Batch API for Eval Pipeline** (PRIORITY: HIGH)
- **Why**: 50% cost reduction on eval LLM calls; stacks with prompt caching for 95%+ savings
- **Timeline**: Implement early Phase 2 (or late Phase 1 if budget allows)
- **Effort**: 2-3 days (refactor nightly scorecard ETL to batch format)
- **ROI**: $200-500/month saved; eval pipeline remains deterministic and replayable
- **Risk**: MEDIUM (requires testing before rollout; eval pipeline is critical)
- **Implementation**: 
  - Refactor `scoring/scorecard.py` to collect prediction IDs overnight
  - Submit batch via Anthropic API before sleep
  - Poll for results in morning cron
  - Falls back to immediate API if timeline pressure

### 2. **Integrate AIS Shipping APIs (Kpler or VesselAPI) for Hormuz Ground Truth** (PRIORITY: HIGH)
- **Why**: GDELT events are noisy; real vessel tracking is ground-truth for Hormuz corridor signals
- **Timeline**: Phase 2 or late Phase 1 (pairs with eval improvements)
- **Effort**: 2-3 days (API integration + data schema)
- **Cost**: $100-500/month (VesselAPI free tier available for pilot)
- **ROI**: Higher-confidence predictions; validates cascade model against real flows
- **Risk**: LOW (mature APIs; optional supplement to GDELT)
- **Implementation**:
  - Add `ingestion/ais_shipping.py` (hourly fetch from Kpler or VesselAPI)
  - Parse vessel positions, compute aggregate flow in H3 cells per Hormuz band
  - Compare predicted flow vs actual AIS traffic in post-event analysis
  - Feed into calibration_score() comparisons

### 3. **Adopt Helicone for Phase 2 Multi-Scenario Eval** (PRIORITY: MEDIUM)
- **Why**: Manual eval dashboard works for one scenario; breaks at scale (multiple countries, multiple prediction types)
- **Timeline**: Phase 2 (not blocking Phase 1)
- **Effort**: MEDIUM (1-2 weeks to integrate fully; can start with lightweight logging)
- **Cost**: $50-500/month (hosted) or free (self-hosted)
- **ROI**: Automated regression detection; faster prompt iteration cycles
- **Risk**: LOW (many production users; well-maintained)
- **Implementation**:
  - Begin with lightweight logging (`scoring/calibration.py` sends eval results to Helicone)
  - Gradually move manual dashboard queries to Helicone's built-in views
  - Build A/B testing workflow for prompt versions

---

## Candidates Reconsidered (and Why Not)

### Claude Code Swarm Mode
- **Why not now**: Custom asyncio swarm is proven and faster to ship than rearchitecting for Swarm Mode
- **When**: Phase 2+ if Parallax team expands and needs parallel agent development within Claude Code IDE
- **Status**: Monitor; not urgent

### LangGraph Integration
- **Why not**: Explicitly out-of-scope in Phase 1 spec; custom DES works well
- **Status**: No immediate value over asyncio-based swarm
- **When**: Phase 3+ if agent reasoning becomes bottleneck (currently under budget)

### DuckDB Spatial Extension
- **Why not now**: H3 community extension + JSON attributes sufficient for Phase 1
- **When**: Phase 2 if infra team wants cleaner SQL semantics for port/zone queries
- **Status**: Additive, not critical

---

## Research Sources

- DuckDB Spatial: [Awesome-DuckDB-Spatial](https://github.com/alperdincer/Awesome-DuckDB-Spatial), [DuckDB Spatial Docs](https://duckdb.org/docs/current/core_extensions/spatial/overview)
- Claude API: [Batch Processing Docs](https://platform.claude.com/docs/en/build-with-claude/batch-processing), [Release Notes](https://platform.claude.com/docs/en/release-notes/overview), [Prompt Caching Guide](https://www.aifreeapi.com/en/posts/claude-api-prompt-caching-guide)
- Claude Swarm Mode: [Swarm Orchestration Guide](https://gist.github.com/kieranklaassen/4f2aba89594a4aea4ad64d753984b2ea), [2026 Multi-Agent Guide](https://www.eesel.ai/blog/claude-code-multiple-agent-systems-complete-2026-guide)
- GDELT & AIS: [GDELT Project](https://www.gdeltproject.org/solutions.html), [Ship Tracking APIs 2026](https://hormuzmonitor.com/50-best-ship-tracking-apis-2026/), [VesselAPI](https://vesselapi.com/), [GDELT Guru](https://gdelt.guru/)
- Eval Frameworks: [Helicone](https://www.helicone.ai/blog/prompt-evaluation-frameworks), [PromptBench](https://www.getmaxim.ai/articles/top-5-prompt-evaluation-tools-in-2025/), [LLM Evaluation Guide 2025](https://www.xbytesolutions.com/llm-evaluation-metrics-framework-best-practices/)
- Performance: [DuckDB In Depth](https://endjin.com/blog/duckdb-in-depth-how-it-works-what-makes-it-fast), [WebSocket Optimization](https://medium.com/@SanchezAllanManuel/optimizing-real-time-performance-websockets-and-react-js-integration-part-i-e563664647d3), [deck.gl Performance](https://deck.gl/docs/developer-guide/performance)

---

**Report date**: 2026-08-24  
**Next research cycle**: 2026-09-07 (14 days)
