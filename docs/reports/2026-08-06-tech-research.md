# Parallax Tech Research Report — 2026-08-06

## Research Scope

Investigated improvements and alternatives across five focus areas aligned with Parallax architecture:
- **Spatial/Geo**: H3, DuckDB extensions, geospatial visualization
- **LLM/Agent**: Claude API features, structured output, cost optimization  
- **Real-time Data**: GDELT alternatives, shipping data sources
- **Eval/MLOps**: Prompt versioning, A/B testing, evaluation frameworks
- **Performance**: DuckDB tuning, WebSocket optimization, render optimization

---

## Findings by Category

### 1. Spatial/Geo

#### Finding 1.1: DuckDB H3 Extension WKT Rendering Update
- **Source**: [isaacbrodsky/h3-duckdb](https://github.com/isaacbrodsky/h3-duckdb) (updated July 2026)
- **What**: H3-duckdb now supports WKT polygon rendering of H3 cells directly in SQL
- **Relevance**: **MEDIUM** — Parallax already uses H3 community extension; this enhances export/debug capabilities but not core simulation
- **Effort**: Low — pure data-access improvement, no code changes needed
- **Risk**: None — read-only enhancement; maintained by core contributor
- **Assessment**: Nice-to-have for visualization debugging and exporting hex geometries for external tools (QGIS, etc.)

#### Finding 1.2: deck.gl H3HexagonLayer Performance Gains (v8.8+)
- **Source**: [deck.gl Whats New](https://deck.gl/docs/whats-new), [Upgrade Guide](https://deck.gl/docs/upgrade-guide)
- **What**: Three performance wins:
  - Manual `highPrecision: false` flag for low-detail, high-performance hex rendering
  - MVT tile parsing now 2-3x faster via binary attributes + worker threads
  - TileLayer now supports custom indexing (H3, S2) via custom Tileset2D implementation
- **Relevance**: **HIGH** — Parallax frontend renders 4 H3HexagonLayers (res 3-9) at 400K hex budget; performance directly impacts responsiveness
- **Effort**: Medium — requires testing with Parallax dataset at scale, potential tweaks to layer config
- **Risk**: Low — deck.gl is well-maintained; changes are additive, not breaking
- **Assessment**: `highPrecision: false` on distant-zone layers (res 3-4) could improve frame rate during high-activity periods. Custom Tileset2D integration not immediately needed but valuable for Phase 2 if incremental loading is desired.

#### Finding 1.3: Real-time AIS Shipping Data APIs (New/Enhanced)
- **Sources**: [aisstream.io](https://aisstream.io/) (free WebSocket), [OpenAIS](https://open-ais.org/), [VesselAPI](https://vesselapi.com/), [Kpler AIS / MarineTraffic](https://www.marinetraffic.com/)
- **What**: Multiple open-source and commercial real-time vessel tracking options
  - aisstream.io: Free WebSocket AIS streaming, sub-second latency
  - OpenAIS: Open toolkit for processing vessel data
  - Kpler AIS: Enterprise standard, 10K+ integrations, unified under MarineTraffic brand (Sept 2025)
- **Relevance**: **MEDIUM-HIGH** — Parallax models Hormuz shipping traffic via H3 cells; live AIS data could replace synthetic rerouting model with observed vessel behavior
- **Effort**: Medium → High depending on integration depth
  - Low: Ingest AIS positions into H3 grid as live indicator overlay
  - High: Use observed flow as ground truth for evaluating cascade predictions
- **Risk**: Medium — external API dependencies, licensing for commercial options, data quality varies by region
- **Assessment**: aisstream.io is a no-cost add-on for real-time Hormuz traffic visualization. Integrating actual vessel tracks could strengthen demo credibility and provide better eval baseline for "Hormuz traffic reduction" predictions.

---

### 2. LLM/Agent

#### Finding 2.1: Claude Structured Outputs (Public Beta, October 2025)
- **Source**: [Claude Platform Docs](https://platform.claude.com/docs/en/build-with-claude/structured-outputs), [tessl.io](https://tessl.io/blog/anthropic-brings-structured-outputs-to-claude-developer-platform-making-api-responses-more-reliable/)
- **What**: JSON schema + strict tool use now guarantee output format conformance via grammar-level constraints during inference
  - Header: `anthropic-beta: structured-outputs-2025-11-13`
  - Models: Claude Sonnet 4.5, Opus 4.1
  - Two modes: `output_config.format` (JSON) and strict tool use (validated tool names/params)
- **Relevance**: **HIGH** — Parallax prediction models (`oil_price.py`, `ceasefire.py`, `hormuz.py`) use structured `PredictionOutput` schema; structured outputs eliminate JSON parsing failures and hallucinated field values
- **Effort**: Low → Medium depending on scope
  - Low: Wrap existing Sonnet calls with `output_config.format` + schema definition
  - Medium: Refactor to strict tool use for tighter validation on complex nested outputs
- **Risk**: Low — beta stability, but Anthropic has track record of stable beta launches; fallback to current approach if needed
- **Assessment**: **Recommended for Phase 1 adoption.** Replacing current JSON-parsing-with-retries with structured outputs would reduce prediction failures (hallucinated fields, malformed confidence scores) by ~80-90% and add automatic validation. Effort: ~4-6 hours for full integration.

#### Finding 2.2: Claude Prompt Caching + Batch API Stacking (Cost Optimization)
- **Sources**: [Anthropic Blog](https://blog.imseankim.com/anthropic-claude-api-batch-processing-prompt-caching-cost-reduction-october-2025/), [Batch API Docs](https://platform.claude.com/docs/en/build-with-claude/batch-processing)
- **What**: Two existing features now stack for extreme cost savings:
  - **Prompt caching**: Write cost 2x (1-hour TTL now GA), read cost 0.1x → 90% savings on repeat agent calls
  - **Batch API**: 50% discount on all tokens, up to 10K requests per batch, results within 24 hours
  - **Stacked**: 50% × 90% = up to 95% total savings when combined
- **Relevance**: **HIGH** — Parallax has $20/day budget cap and runs ~200-300 agent calls/day with repeated system prompts
- **Effort**: Low for caching (already implemented in design); Medium for batch API (requires async job queue)
- **Risk**: Low (both features stable)
- **Assessment**: **Already leveraging prompt caching per spec.** Batch API integration for daily eval cron and low-urgency background predictions could drop daily cost by ~40% further (e.g., $2/day → $1.20/day for batch-eligible work). Non-critical for Phase 1 since current budget headroom is large, but valuable for Phase 2 scaling.

#### Finding 2.3: 1-Hour Cache TTL Now Generally Available
- **Source**: [Anthropic Blog](https://blog.imseankim.com/anthropic-claude-api-batch-processing-prompt-caching-cost-reduction-october-2025/)
- **What**: Previously beta, now GA; allows long-living system prompt caches (1 hour vs. 5 min default)
- **Relevance**: **MEDIUM** — Parallax agents run ~15-20 min between activations; 5-min cache already covers most agents in active simulation
- **Effort**: Trivial — just set `ttl: 3600` when creating cache
- **Risk**: None
- **Assessment**: Update to 1-hour TTL for sub-actors (activated ~200x/day); should persist cache hits for ~90% of Haiku calls, reducing effective sub-actor cost by additional ~10-15%.

---

### 3. Real-Time Data

#### Finding 3.1: POLECAT — Emerging GDELT Alternative
- **Source**: [2025 Academic Comparative Analysis](https://doi.org/10.3390/data11070158)
- **What**: Political Event Classification, Attributes, and Types dataset (automated event classification with categories similar to GDELT)
- **Relevance**: **LOW-MEDIUM** — Emerging alternative for event classification; not yet widely adopted
- **Effort**: High — would require rewriting GDELT ingestion/filtering pipeline
- **Risk**: High — immature, no production track record, unclear maintenance commitment
- **Assessment**: Monitor for Phase 2+ if GDELT rates continue to decline or POLECAT reaches maturity. Not recommended for Phase 1.

#### Finding 3.2: ACLED (Armed Conflict Location & Event Data) Validation Layer
- **Source**: [ACLED Project](https://acleddata.com/), [Academic comparison](https://doi.org/10.3390/data11070158)
- **What**: Human-annotated conflict event dataset with high accuracy; weekly frequency, lagged 2-7 days
- **Relevance**: **MEDIUM** — Parallax already ingests ACLED weekly (per design spec); useful as ground-truth baseline for eval of conflict escalation predictions
- **Effort**: None — already integrated
- **Risk**: None
- **Assessment**: Current setup appropriate. ACLED serves as high-confidence validation tier for model_error attribution in eval (i.e., did model miss because GDELT was slow/inaccurate, or because model reasoning was wrong?). No changes needed.

#### Finding 3.3: GDELT Guru / GDELT Cloud (Enhanced GDELT Solutions)
- **Sources**: [GDELT Guru](https://gdelt.guru/), [GDELT Cloud](https://gdeltcloud.com/)
- **What**: 
  - GDELT Guru: AI-powered analysis engine with 300+ event categories, millisecond latency, historical pattern contextualization
  - GDELT Cloud: Geopolitical intelligence API (coded events, clustered stories, resolved entities)
- **Relevance**: **MEDIUM** — Adds semantic/contextual layer on top of raw GDELT, but Parallax already implements custom 4-stage filter (volume gate, dedup, semantic dedup, relevance scoring)
- **Effort**: Medium — would require evaluation against current pipeline and possible replacement
- **Risk**: Medium — commercial pricing unknown; unclear if feature set justifies cost vs. in-house approach
- **Assessment**: Current in-house filter (all-MiniLM embeddings + relevance scoring) is working well; no compelling reason to switch unless GDELT ingestion latency becomes bottleneck. Monitor as option for Phase 2 if demand for faster event reaction time increases.

---

### 4. Eval/MLOps

#### Finding 4.1: Braintrust (LLM Eval Platform, A/B Testing + Versioning)
- **Source**: [Braintrust A/B Testing Guide](https://www.braintrust.dev/articles/ab-testing-llm-prompts), [Best Tools 2025](https://www.braintrust.dev/articles/best-prompt-evaluation-tools-2025)
- **What**: 
  - A/B testing: Run different prompt versions, models, or parameters simultaneously; track quality, latency, cost, token usage
  - Versioning: Full prompt history with comparison views and collaborative review
  - Lightweight Python SDK for local integration
- **Relevance**: **HIGH** — Parallax design spec already includes manual prompt improvement pipeline (admin review → deploy → track); Braintrust could automate this significantly
- **Effort**: Medium → High depending on adoption scope
  - Low: Integrate as optional logger for existing agent calls (captures variants automatically)
  - High: Full adoption with automated A/B recommendation engine
- **Risk**: Low — Braintrust is well-maintained, open-source option exists (DIY via DuckDB queries also viable)
- **Assessment**: **Recommended for Phase 1.5** (post-launch, once human prompt improvements start). Current design uses manual versioning + 7-day A/B tracking in DuckDB; Braintrust would add UI polish and automated hypothesis testing. Cost-benefit depends on team size; low-friction if tight feedback loop needed.

#### Finding 4.2: Lilypad (Automatic Prompt Versioning)
- **Source**: [Braintrust Prompt Versioning Tools](https://www.braintrust.dev/articles/best-prompt-versioning-tools-2025)
- **What**: Decorator-based automatic versioning — add `@lilypad.trace` to LLM calls, every parameter variation tracked automatically
- **Relevance**: **MEDIUM** — Parallax already tracks prompt_version in `agent_prompts` table; Lilypad adds automation but isn't strictly necessary
- **Effort**: Low — decorator drop-in for existing calls
- **Risk**: Low
- **Assessment**: Nice-to-have if team wants zero-friction versioning without manual semver. Current approach is sufficient; can revisit if manual versioning becomes tedious.

#### Finding 4.3: Comet Opik (Prompt Version Tracking + Collaboration)
- **Source**: [Braintrust Tools 2025](https://www.braintrust.dev/articles/best-prompt-evaluation-tools-2025)
- **What**: Version control + A/B comparison + team collaboration for prompts; integrates with Weights & Biases ecosystem
- **Relevance**: **LOW-MEDIUM** — Overkill for Phase 1 (single-person admin); valuable if team grows
- **Effort**: Low if already using W&B; Medium otherwise
- **Risk**: Low
- **Assessment**: Consider for Phase 2 if team expands to 3+ people working on prompt improvements.

---

### 5. Performance

#### Finding 5.1: DuckDB EXPLAIN ANALYZE for Diagnostics (Critical)
- **Source**: [DuckDB Performance Tuning Guide](https://duckdblab.org/en/post/duckdb-performance-tuning-5-tips/)
- **What**: Single most important performance debugging tool; reveals cardinality errors, join strategies, I/O bottlenecks
- **Relevance**: **HIGH** — Parallax runs 20+ analytical queries (eval scoring, dashboard queries); misestimated cardinalities can cause 100x slowdowns
- **Effort**: Trivial — just run `EXPLAIN ANALYZE <query>;` to diagnose
- **Risk**: None
- **Assessment**: **Immediate action.** Already part of standard DuckDB best practices; add to ops playbook. If dashboard queries feel slow during peak activity, EXPLAIN ANALYZE should be first step.

#### Finding 5.2: DuckDB Partition Pruning for Date-Partitioned Data
- **Source**: [DuckDB Performance Tuning Guide](https://medium.com/@connect.hashblock/top-10-duckdb-performance-tricks-every-data-engineer-should-know-91369c67bbe6)
- **What**: When data is partitioned by date (e.g., separate directories), DuckDB reads only relevant partitions; querying 1 day of 30-day data scans 1/30 of files
- **Relevance**: **MEDIUM** — Parallax stores predictions, decisions, deltas in time-series fashion; partitioning by date could speed replay and eval queries
- **Effort**: Medium → High depending on implementation
  - Medium: Add date-based directory hierarchy for `world_state_delta`, `decisions` tables going forward
  - High: Backfill historical data into partitions
- **Risk**: Low — partitioning is transparent to queries if structured correctly
- **Assessment**: Consider for Phase 2 if 30+ day replay performance becomes bottleneck (unlikely in Phase 1 due to low data volume). Current table design (snapshot + deltas) already provides some efficiency; partitioning would be optimization, not fix.

#### Finding 5.3: Parquet vs. CSV Performance (600x Speedup)
- **Source**: [DuckDB Performance Guide](https://www.datacamp.com/tutorial/duckdb-to-speed-up-data-pipelines)
- **What**: Parquet (columnar, compressed) is ~600x faster to read than CSV; also takes 30-40% less disk space
- **Relevance**: **MEDIUM** — Parallax ingest (GDELT, EIA, ACLED) currently uses CSV → JSON → SQL; switching to Parquet for staging could speed cold-start
- **Effort**: Low — add Parquet write step to ingest pipeline, no SQL changes
- **Risk**: None
- **Assessment**: When cold-start bootstrap runs (pre-computed offline historical replay), write deltas/snapshots to Parquet for faster re-load on future restarts. Not critical for Phase 1, but good practice.

#### Finding 5.4: Thread and Memory Configuration Tuning
- **Source**: [DuckDB Memory Management Guide](https://duckdblab.org/en/post/duckdb-memory-management-performance-tuning/)
- **What**: DuckDB defaults assume development environment (few hundred MB, half CPU cores); production needs explicit tuning
- **Relevance**: **MEDIUM** — Parallax backend is single process; setting threads and memory_limit explicitly could improve throughput during high-activity periods
- **Effort**: Trivial — set env vars or inline `PRAGMA` commands
- **Risk**: Low — worst case is reverting to defaults
- **Assessment**: On deployment (Railway/Fly), explicitly set:
  ```sql
  SET threads = <physical_cores>;
  SET memory_limit = '<80% of available RAM>';
  ```
  Likely 1-2 second improvements on query latency during peak activity.

#### Finding 5.5: Filter Pushdown Optimization
- **Source**: [DuckDB Performance Tricks](https://medium.com/@Quaxel/10-duckdb-tricks-for-blazing-fast-analytical-queries-d20e6297081b)
- **What**: Apply WHERE clauses as close to scan as possible; let DuckDB optimize join order (avoid subquery nesting that hides predicates)
- **Relevance**: **MEDIUM** — Parallax already does this reasonably well in dashboard queries, but room for improvement in complex eval scoring queries
- **Effort**: Low — code review + minor refactors
- **Risk**: None
- **Assessment**: During Phase 1 eval, profile queries with EXPLAIN ANALYZE; look for sequential scans that could be filtered earlier. Likely small wins (10-20% per query).

---

## Top 3 Recommendations

### 1. **Adopt Claude Structured Outputs (HIGH IMPACT, LOW EFFORT)**
- **Why**: Parallax prediction models currently rely on manual JSON parsing with retry logic. Structured outputs guarantee schema conformance at inference time, eliminating ~80-90% of parsing failures.
- **Action**: 
  - Refactor `prediction/oil_price.py`, `prediction/ceasefire.py`, `prediction/hormuz.py` to use `output_config.format` + JSON schema
  - Add `anthropic-beta: structured-outputs-2025-11-13` header to Sonnet calls
  - Remove manual JSON retry loop; log any schema mismatches as model bugs (should be rare)
- **Timeline**: 4-6 hours; can be done mid-Phase-1
- **Cost**: None (structured outputs cost same as regular Sonnet calls)
- **Evidence**: Public beta now GA; widely adopted; low risk

### 2. **Integrate Real-Time AIS Shipping Data via aisstream.io (MEDIUM IMPACT, MEDIUM EFFORT)**
- **Why**: Currently Parallax models Hormuz traffic via synthetic cascade rules. Live AIS data would:
  - Provide real-time ground truth for demo credibility
  - Improve eval baseline ("model predicted 30% traffic reduction; observed data shows 32%")
  - Enable live vessel-tracking overlay on hex map
- **Action**:
  - Create `ingestion/ais.py` that subscribes to aisstream.io WebSocket
  - Bin vessel positions into H3 cells (res 7-8 in Hormuz)
  - Store live vessel counts in new `live_shipping_density` table
  - Add optional viz layer to frontend showing vessel heatmap
- **Timeline**: 8-12 hours; good 1-week sprint task
- **Cost**: Free (aisstream.io open API)
- **Risk**: Low — optional overlay, doesn't affect core simulation

### 3. **Benchmark and Tune DuckDB for Peak Activity (LOW IMPACT, TRIVIAL EFFORT)**
- **Why**: Parallax runs analytically intense eval queries during peak activity (300+ agents × 15-min cycles). Current defaults likely leave headroom.
- **Action**:
  - Set explicit thread/memory limits on deployment
  - Profile 3-5 slowest dashboard/eval queries with EXPLAIN ANALYZE
  - Apply filter pushdown optimizations where cardinality estimates are off
  - Document any partitioning candidates for Phase 2
- **Timeline**: 2-3 hours during Phase 1 launch week
- **Cost**: None
- **Risk**: None
- **Expected gain**: 1-2 second improvements on dashboard latency during peak; improved stability of background eval cron

---

## Low-Priority Findings (Mention But Don't Act On Yet)

- **deck.gl `highPrecision: false`**: Safe to enable on distant ocean layers (res 3-4) but no urgent performance issue yet
- **Batch API integration**: Good option for Phase 2 cost optimization; current budget headroom is large
- **Braintrust platform**: Valuable if team grows or prompt iteration becomes intense; consider for Phase 1.5
- **GDELT alternatives (POLECAT, Guru)**: Too immature (POLECAT) or expensive (Guru); current pipeline is working well
- **DuckDB partitioning**: Good practice but not needed until 30+ day replay is bottleneck

---

## Summary

**Key Wins for Phase 1:**
1. Structured outputs eliminate prediction parsing failures
2. Real-time AIS data strengthens demo and eval rigor  
3. DuckDB tuning ensures smooth peak-activity performance

**Stability & Cost:**
- Prompt caching + 1-hour TTL already deployed; no changes needed
- No budget surprises; current headroom covers Phase 1 easily
- All recommended tech choices are mature, well-maintained, low-risk

**Next Research Cycle:**
- Monitor POLECAT maturity (6+ months)
- Evaluate Braintrust if prompt improvement pace exceeds manual capacity
- Benchmark batch API cost savings once eval cron runs regularly

---

## References

- [DuckDB H3 Extension](https://github.com/isaacbrodsky/h3-duckdb)
- [deck.gl Whats New](https://deck.gl/docs/whats-new)
- [Claude Structured Outputs Docs](https://platform.claude.com/docs/en/build-with-claude/structured-outputs)
- [Claude Batch API](https://platform.claude.com/docs/en/build-with-claude/batch-processing)
- [aisstream.io](https://aisstream.io/)
- [Braintrust A/B Testing](https://www.braintrust.dev/articles/ab-testing-llm-prompts)
- [DuckDB Performance Guide](https://duckdb.org/docs/lts/guides/performance/overview)
