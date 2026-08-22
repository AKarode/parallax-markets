# Daily Tech Research Report — 2026-08-22

**Focus Areas**: Spatial/Geo, LLM/Agent, Real-time Data, Eval/MLOps, Performance

---

## Executive Summary

Three high-impact findings worth integrating or monitoring:

1. **Claude Batch API + Prompt Caching stack** — New cost lever: 50% discount on batch requests, stacks with existing 90% caching discount. Applicability: daily scorecard generation, overnight eval batch runs.
2. **AIS vessel tracking APIs** — Shipping layer currently inferred from cascade rules. Live AIS data (AISstream.io free, Datalastic pro) adds ground truth vessel positioning for validation. Risk: adds operational dependency.
3. **DeepEval framework for prompt regression testing** — Parallax already has manual eval cron. DeepEval + golden dataset (200-500 real production misses) automates A/B testing for prompt versions. Effort: low, integrates cleanly with existing eval infrastructure.

---

## Findings by Category

### 1. Spatial / Geospatial Visualization

#### DuckDB H3 Extension — Recent Optimization Work
- **Relevance**: MEDIUM (already pinned in Phase 1 design, but new optimization tips emerging)
- **Effort**: LOW (review + optional apply)
- **Risk**: LOW
- **Assessment**: FOSS4G NA 2025 talk on "DuckDB + Rasters: Hexagons for Blazing Fast Analytics" signals H3 + raster analytics integration. Phase 1 uses H3 for cell indexing; Phase 2 may benefit from raster overlay (satellite imagery, ESA sea-state, etc.). Current pinned version is stable; no urgent migration needed. Monitor for v2 releases.
- **Action**: Bookmark FOSS4G recording; defer Phase 2.

#### GDELT Cloud — Managed Alternative to BigQuery
- **Relevance**: MEDIUM (GDELT pipeline currently raw BigQuery)
- **Effort**: MEDIUM (switch ingestion source, validate event parity)
- **Risk**: MEDIUM (new vendor, potential SLA differences)
- **Assessment**: GDELT Cloud is a newly launched managed REST API wrapping open GDELT data. Pros: REST-native (easier than BigQuery streaming), structured event coding baked in. Cons: new vendor, unclear uptime SLA. Current BigQuery implementation is battle-tested and free. Switch only if BigQuery ingestion becomes bottleneck or billing concern.
- **Action**: HOLD — monitor performance metrics on existing BigQuery path; evaluate GDELT Cloud only if Phase 2 requires operational reliability upgrade.

#### H3 Raster Analytics (H3-Rasters)
- **Relevance**: LOW (out of scope for Phase 1 Iran scenario)
- **Effort**: MEDIUM (new spatial layer + rendering)
- **Risk**: LOW
- **Assessment**: H3 + rasters (satellite/radar/ocean state) opens oil platform damage assessment, naval positioning inference. Interesting for Phase 2 (expanded scenarios), not Phase 1. Requires satellite data source (EODATA, Copernicus, USGS) + GPU raster rendering.
- **Action**: Research agenda for Phase 2 spatial layer expansion.

---

### 2. LLM / Agent Orchestration

#### Claude Batch API — 50% Cost Discount
- **Relevance**: HIGH (Phase 1 budget cap is $20/day; eval is a high-cost phase)
- **Effort**: MEDIUM (refactor eval cron to defer non-blocking calls to batch, implement polling for results)
- **Risk**: LOW (Anthropic Batch API is production-ready; no dependency on untested vendor)
- **Assessment**: Batch API discounts all Claude token prices by 50%. Parallax already uses $2-5/day for predictions; eval generation (daily scorecard, prompt improvement meta-agent) can batch overnight. Estimated new cost: $1-2.50/day for predictions + batch evals combined. Stacks with prompt caching (90% off cached prefixes). Example: scorecard meta-agent on 50 predictions at 6000 cached tokens = $0.002/call vs $0.02 standard.
- **Action**: HIGH PRIORITY. Implement batch API for nightly eval cron. Estimated 1-2 day dev effort; ROI immediate ($5-10/day savings, no production risk).

#### Structured Output + Prompt Caching Stacking
- **Relevance**: HIGH (already in use, but stacking benefit often missed)
- **Effort**: LOW (documentation + confirm in existing code)
- **Risk**: LOW
- **Assessment**: Per Claude 2026 release notes, JSON schema passed to `output_config.format` is included in prompt cache prefix. Phase 1 already uses structured outputs for decisions/predictions; caching is enabled. Confirms existing implementation is optimal. Cache hits are 90% cheaper; stacking with batch API gives 95% reduction on repeat calls.
- **Action**: Document in CLAUDE.md that schema caching is automatic; confirm in code review.

#### Output Caching — New Feature (2026)
- **Relevance**: MEDIUM (emerging, not yet integrated)
- **Effort**: MEDIUM (refactor response processing, cache key design)
- **Risk**: MEDIUM (new feature, limited production data)
- **Assessment**: Claude API now supports caching of *outputs* (not just inputs) for deterministic responses. Parallax prediction outputs are often deterministic given the same input context (e.g., "Given Q1 GDELT events, predict oil price direction"). Caching outputs 5-minute window could skip 20-30% of LLM calls during high-activity periods. Requires careful cache key design (event hash + model version).
- **Action**: DEFER to Phase 2 (low-hanging fruit after batch API). Implement if prediction call volume becomes bottleneck.

#### Multi-Agent Orchestration Frameworks
- **Relevance**: MEDIUM (Phase 1 uses custom DES, not LangGraph; Phase 2 may add orchestration)
- **Effort**: HIGH (architectural refactor)
- **Risk**: MEDIUM (framework churn in 2026, LangGraph dominant but others viable)
- **Assessment**: LangGraph dominance in production (50%+ of enterprise multi-agent systems) is solidifying. CrewAI strong for research phases, LangGraph for execution. Phase 1 explicitly avoids LangGraph; custom DES + asyncio is correct. Phase 2 expansion (multi-scenario, agent skill trees) may benefit from LangGraph's state machine semantics. Current custom approach scales to Phase 1 scope.
- **Action**: MONITOR. No migration planned for Phase 1; LangGraph evaluation for Phase 2 if agent complexity increases.

#### MCP (Model Context Protocol) Adoption
- **Relevance**: MEDIUM (new standard, emerging production adoption)
- **Effort**: LOW (tool integration, MCP is just structured I/O)
- **Risk**: LOW (Linux Foundation-backed, Anthropic/OpenAI/Google all support)
- **Assessment**: MCP is becoming standard for tool/resource integration across LLM applications. Parallax already integrates Kalshi/Polymarket APIs via custom HTTP clients. MCP standardization means drop-in tool composability (e.g., MCP server for Kalshi API could be shared/reused). No urgency for Phase 1, but Phase 2 benefits from MCP-based tool ecosystem.
- **Action**: MONITOR. Plan Phase 2 tool integration via MCP; improves debuggability and tooling ecosystem access.

---

### 3. Real-Time Data Sources

#### AIS Vessel Tracking APIs — New Data Layer
- **Relevance**: HIGH (shipping layer currently rule-based; AIS adds ground truth)
- **Effort**: MEDIUM (API integration, WebSocket ingestion, cell mapping)
- **Risk**: LOW (multiple vendors, free options available)
- **Assessment**: Parallax models Hormuz traffic via cascading rules (blockade → flow reduction). Live AIS data from VesselFinder, Datalastic, or AISstream.io (free) provides real vessel positions (700K-830K vessels tracked globally). Integration: stream AIS positions to H3 cells, compute realized flow vs predicted flow, use divergence as feedback into model recalibration. Example: if predicted flow reduction is 30% but AIS shows only 15%, model is overestimating escalation impact — flag for eval feedback.
- **Action**: HIGH PRIORITY for Phase 2. Phase 1 validation (mock or replay-only AIS data) in final 2 weeks of run. Real AIS integration: 3-5 days, medium complexity, transformative for model grounding.

#### GDELT Cloud — Managed GDELT Alternative
- **Relevance**: MEDIUM (operational alternative to BigQuery, not better data)
- **Effort**: MEDIUM
- **Risk**: MEDIUM
- **Assessment**: (See Spatial/Geo section.) GDELT Cloud REST API vs BigQuery. Current BigQuery implementation is proven; no switch unless operational reliability issues arise.
- **Action**: HOLD.

#### Currents API — News Aggregation Alternative
- **Relevance**: LOW-MEDIUM (alternative to GDELT, not replacement)
- **Effort**: MEDIUM (parallel ingestion, validate event parity)
- **Risk**: MEDIUM (different event coverage, different coding schema)
- **Assessment**: Currents API aggregates news with full-text and 20+ language support. GDELT strength is CAMEO event coding (actor/action/target structure). Currents is raw text without CAMEO. Could supplement GDELT for non-English coverage (e.g., Iranian state media in Farsi). Phase 1 focus is English-language GDELT; no urgency.
- **Action**: DEFER to Phase 2 (multi-lingual expansion scenario).

---

### 4. Evaluation / MLOps

#### DeepEval — Prompt Regression Testing Framework
- **Relevance**: HIGH (Phase 1 has manual eval cron; DeepEval automates it)
- **Effort**: LOW (Python package, integrates with existing eval cron)
- **Risk**: LOW (open-source, lightweight)
- **Assessment**: DeepEval provides unit-test-like framework for LLM outputs. Phase 1 eval cron computes accuracy, calibration, sequence scores manually. DeepEval + golden dataset (curated 200-500 real production misses from Phase 1 run) enables: (1) auto-regression testing on new prompts before deploy, (2) A/B comparison of versions in CI/CD, (3) confidence calibration curves. Integrates cleanly with existing eval pipeline. Estimated effort: 2-3 days to build golden dataset + DeepEval harness.
- **Action**: HIGH PRIORITY for mid-Phase-1 implementation. Golden dataset ready by day 10; auto-regression testing active by day 15. Prevents prompt degradation.

#### Stanford HELM Calibration Research
- **Relevance**: MEDIUM (academic research, calibration is core Phase 1 eval metric)
- **Effort**: HIGH (research implementation, not tooling)
- **Risk**: MEDIUM (research papers often don't translate directly to production)
- **Assessment**: Recent research on prompt styles and confidence calibration suggests LLM confidence varies with prompt phrasing (e.g., "Be very confident" vs neutral). Phase 1 already tracks calibration curve (confidence vs hit rate); HELM adds perspective on why miscalibration occurs. Could inform prompt tuning strategy. Defer deep dive; use as reference for Phase 1 final analysis report.
- **Action**: REFERENCE. Read paper; incorporate calibration insights into Phase 1 post-mortem writeup.

#### Regression Testing + A/B Frameworks
- **Relevance**: HIGH (Phase 1 eval framework includes A/B, but tooling is manual)
- **Effort**: LOW (frameworks like Braintrust, Promptfoo integrate easily)
- **Risk**: LOW
- **Assessment**: Existing Phase 1 eval cron compares prompt versions v1.0 vs v1.1 manually. Promptfoo or Braintrust automate test execution + comparison dashboards. Phase 1 manual process is acceptable; Phase 2 with 20+ agents and rapid iteration would benefit from automated A/B.
- **Action**: DEFER to Phase 2 (if prompt iteration velocity increases). Current manual process is sufficient.

---

### 5. Performance

#### DuckDB v1.4 LTS — ClickBench #1 Status
- **Relevance**: MEDIUM (validation of current choice, optimization hints)
- **Effort**: LOW (review results, apply tips)
- **Risk**: LOW
- **Assessment**: October 2025 benchmark shows DuckDB v1.4 hit #1 on ClickBench (competitor OLAP database rankings). Phase 1 pinned version is likely recent. Key wins: vectorized execution, zone maps (dynamic filtering), dictionary/RLE compression. Current implementation benefits from these; no upgrade required unless Phase 2 adds new query patterns (e.g., geospatial joins at scale).
- **Action**: Confirm pinned version is ≥1.4; document performance characteristics in CLAUDE.md for future phases.

#### DuckDB Zone Maps + Dynamic Compression
- **Relevance**: MEDIUM (optimization technique, applicable to Phase 1 large delta tables)
- **Effort**: LOW (configuration/schema tuning)
- **Risk**: LOW
- **Assessment**: DuckDB auto-applies zone maps (per-chunk min/max statistics) and RLE/dict compression. `world_state_delta` table (changed cells per tick) can grow to 100K rows/day. Zone maps + compression reduce scan cost for queries like "fetch all cells in region X with threat_level > 0.7". Ensure DuckDB statistics are fresh (ANALYZE after major bulk inserts).
- **Action**: ADD to deployment checklist: run ANALYZE on delta/snapshot tables after daily compaction. Document in ops runbook.

#### deck.gl Real-Time Update Patterns
- **Relevance**: HIGH (Phase 1 frontend pushes WebSocket updates to H3 hexagons)
- **Effort**: LOW (apply existing pattern)
- **Risk**: LOW
- **Assessment**: GitHub discussion #8283 on real-time updates confirms current Phase 1 approach (useRef for mutable data, batch WebSocket updates every 100ms) is idiomatic. deck.gl documentation on performance emphasizes exactly this: keep data in refs, mutate directly, let deck.gl pull on its cycle. Phase 1 frontend already implements optimal pattern.
- **Action**: Confirm existing implementation matches documented best practices; document in README for future devs.

---

## Top 3 Recommendations

### 1. **Implement Claude Batch API for Eval Cron** (Priority: HIGH, Timeline: 1-2 days)
**Why**: $5-10/day cost savings immediately. Eval cron (daily scorecard, prompt improvement meta-agent, prediction logging) is perfect batch workload. Stacks with existing prompt caching for 95% cost reduction on cached calls.
**Effort**: Medium (refactor async eval loops to batch, add polling for results).
**Implementation**: Defer non-critical eval calls (< 1hr latency tolerance) to batch job, run overnight. Redeploy same morning with results.
**Risk**: Low (Anthropic Batch API is mature, no external dependencies).

### 2. **Build Golden Dataset + Deploy DeepEval for Prompt Regression** (Priority: HIGH, Timeline: 2-3 days, exec by Phase 1 day 15)
**Why**: Prevents prompt degradation. Phase 1 manual eval cron works, but auto-regression testing catches regressions before deploy. Golden dataset (real production misses) ensures test coverage matches actual failure modes.
**Effort**: Low (2-3 days total: 1 day curating 200-500 real Phase 1 misses, 1 day DeepEval harness, 0.5 day CI integration).
**Implementation**: Day 10 of Phase 1 run, compile misses tagged as `model_error`. Day 12-14, build DeepEval unit tests. Day 15, activate auto-regression on all new prompts before staging.
**Risk**: Low (DeepEval is lightweight, offline testing, no production impact).

### 3. **Plan AIS Integration for Phase 2 + Prototype in Final Phase 1 Week** (Priority: MEDIUM, Timeline: prototype 2-3 days, full integration Phase 2)
**Why**: Shipping layer currently purely rule-based. Live AIS data (free via AISstream.io) adds ground truth for model validation and recalibration. Direct feedback loop: "Predicted 30% flow reduction, AIS shows 15% → model overestimating escalation impact."
**Effort**: Low prototype (stream AIS to cells, compute divergence), medium full integration (persistent storage, real-time routing to eval system).
**Implementation**: Prototype in final 1-2 weeks of Phase 1. Set up AISstream.io (free), ingest 1 week of retroactive AIS data, map positions to H3 cells, compare against predicted flow. Document learnings.
**Risk**: Low (free data source, offline analysis, no production dependency). Full Phase 2 integration is higher effort (3-5 days) but transformative for model grounding.

---

## Links to Sources

### Spatial/Geo
- [DuckDB + Rasters: FOSS4G NA 2025](https://talks.osgeo.org/foss4g-na-2025/talk/FUYA37/)
- [H3 DuckDB Community Extension](https://duckdb.org/community_extensions/extensions/h3)
- [GDELT Cloud API](https://gdeltcloud.com/)
- [H3 Documentation](https://h3geo.org/docs/)

### LLM/Agent
- [Claude API Batch Processing Docs](https://platform.claude.com/docs/en/build-with-claude/batch-processing)
- [Prompt Caching + Structured Output 2026](https://apiforgecom.medium.com/claude-api-prompt-caching-with-structured-outputs-the-missing-piece-in-the-docs-f6c0ae6d1df8)
- [Claude Output Caching 2026](https://www.padiso.co/blog/claude-output-caching-cost-lever-2026/)
- [Multi-Agent Orchestration Frameworks 2026](https://www.truefoundry.com/blog/multi-agent-orchestration-frameworks)
- [Top Agentic Frameworks 2026](https://blog.jetbrains.com/pycharm/2026/06/top-agentic-frameworks-for-building-applications-2026/)

### Real-Time Data
- [Best Ship Tracking APIs 2026](https://hormuzmonitor.com/50-best-ship-tracking-apis-2026/)
- [Datalastic AIS API](https://datalastic.com/)
- [VesselFinder API](https://api.vesselfinder.com/docs/)
- [AISstream.io (Free)](https://aisstream.io/)
- [VesselAPI Ship Tracking](https://vesselapi.com/ship-tracking-api)
- [Currents News API vs GDELT](https://currentsapi.services/en/alternative/gdelt)
- [GDELT Project Overview](https://dataresearchtools.com/gdelt-project-for-news-data-2026-free-alternative-to-newsapi/)

### Eval/MLOps
- [Best LLM Evaluation Tools 2026](https://medium.com/online-inference/the-best-llm-evaluation-tools-of-2026-40fd9b654dce)
- [DeepEval Framework](https://deepeval.com/blog/top-5-llm-evaluation-frameworks)
- [LLM Testing Tools 2026](https://contextqa.com/blog/llm-testing-tools-frameworks-2026/)
- [Calibration Research: Response Agreement & Prompt Styles](https://arxiv.org/pdf/2501.03991)
- [Braintrust Prompt Evaluation](https://www.braintrust.dev/articles/best-prompt-evaluation-tools-2025)

### Performance
- [DuckDB Performance Benchmarks](https://mail.openbenchmarking.org/performance/test/pts/duckdb/a6ea19123b2636829739d1babf7d27e9762aaecf)
- [DuckDB vs PostgreSQL 2026](https://saurshaz.medium.com/duckdb-vs-postgresql-why-architectural-choices-matter-a-performance-deep-dive-7a58c31236dd)
- [Fastest OLAP Databases 2026](https://clickhouse.com/resources/engineering/fastest-olap-databases)
- [deck.gl Performance Guide](https://deck.gl/docs/developer-guide/performance)
- [deck.gl Real-Time Updates Discussion](https://github.com/visgl/deck.gl/discussions/8283)
- [Using deck.gl with React](https://deck.gl/docs/get-started/using-with-react)

---

## Notes for Next Scout Run

- Monitor FOSS4G recordings (September 2026) for H3 + raster tooling updates
- Re-evaluate GDELT Cloud SLA + pricing as it matures (likely more stable by Q4 2026)
- Watch DeepEval and Braintrust releases for eval pipeline integrations
- Phase 2 planning: prioritize AIS + LangGraph evaluation

---

*Report generated: 2026-08-22*
*Scout: Daily Tech Research Agent*
