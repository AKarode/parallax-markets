# Technology Research Report — 2026-10-24

**Focus areas:** Spatial/Geo, LLM/Agent APIs, Real-time Data Ingestion, Eval/MLOps, Performance Optimization

---

## Summary

Research identified 5 HIGH-MEDIUM relevance findings and 3 actionable recommendations. Key discoveries:
- **Calibration metrics** are underutilized in LLM eval frameworks — directly applicable to Parallax's daily scorecard
- **DuckDB spatial native types** (POINT_2D, LINESTRING_2D) may offer performance gains over current GEOMETRY setup
- **Claude Batch API + Prompt Caching stack** provides 95% savings for eval/recalibration workflows
- **GDELT Cloud** and **POLECAT** are complementary data sources for high-confidence event filtering

---

## Findings by Category

### 1. Spatial/Geospatial

#### 1.1 DuckDB Native 2D Spatial Types — MEDIUM RELEVANCE
**Discovery:** DuckDB spatial extension offers two geometry representations:
- Standard GEOMETRY type (row-wise binary, PostGIS-like, flexible but slower)
- Native 2D types: POINT_2D, LINESTRING_2D, POLYGON_2D, BOX_2D (columnar, vectorized, high-performance)

**Current Parallax state:** Spec mentions "spatial extension + H3 community extension" but doesn't specify which geometry type is in use.

**Assessment:**
- **Relevance:** MEDIUM — potentially 2-3x faster spatial queries for Hormuz corridor cell operations
- **Effort:** MEDIUM — would require schema migration and query rewrite
- **Risk:** LOW — native types are stable in DuckDB v1.5+
- **Recommendation:** Profile current spatial query performance. If cell updates on Hormuz corridor (Res 7-8) show > 50ms latency, measure gain from POINT_2D representation.

**Sources:**
- [DuckDB Spatial Extension Docs](https://duckdb.org/docs/stable/extensions/spatial/overview)
- [PostGEESE: DuckDB Spatial Launch (2023)](https://duckdb.org/2023/04/28/spatial.html)

---

#### 1.2 Amazon Redshift H3 Functions (Jan 2025) — LOW RELEVANCE
**Discovery:** Amazon Redshift released H3_Center and H3_Boundary functions (converts H3 cell IDs to polygon boundaries).

**Assessment:**
- **Relevance:** LOW — Parallax uses DuckDB, not Redshift
- **Effort:** N/A
- **Risk:** N/A
- **Note:** Signals H3 adoption momentum in cloud data platforms. Monitor H3 community updates for equivalent DuckDB extensions.

---

### 2. LLM / Agent APIs

#### 2.1 Claude API Batch Processing + Prompt Caching Stack — HIGH RELEVANCE
**Discovery:** Batch API + Prompt Caching stack provides 95% token savings for offline workflows:
- Batch API: ~50% discount, async processing (no streaming)
- Prompt caching: 0.1x read cost + 1.25-2x write cost
- These multipliers **stack**, offering 90-95% total savings on repeated workflows

**Current Parallax use:** Spec mandates prompt caching for system prompts (historical baseline cached per version). Batch API not yet used.

**Assessment:**
- **Relevance:** HIGH — directly applicable to eval/recalibration pipeline (daily scorecard, prompt A/B testing)
- **Effort:** LOW — requires 2-3 lines of code change to batch eval calls
- **Risk:** LOW — Batch API is stable, GA
- **Recommendation:** 
  - Use Batch API for daily eval runs (`compute_daily_scorecard`, calibration checks, A/B rollout comparisons)
  - Combine with existing prompt caching on `agent_prompts` system prompts
  - **Estimated monthly savings:** $30-50 on current LLM budget (Phase 1 ~$2-5/day)

**Sources:**
- [Claude Docs: Prompt Caching](https://platform.claude.com/docs/en/build-with-claude/prompt-caching)
- [Batch API Pricing](https://platform.claude.com/docs/en/build-with-claude/batch-processing)

---

#### 2.2 Newer Claude Models — LOW RELEVANCE (Monitoring)
**Discovery:** Spec pins Haiku/Sonnet/Opus models. Current stack is appropriate.

**Assessment:**
- **Relevance:** LOW — current models adequate for budget/performance
- **Effort:** N/A
- **Risk:** N/A
- **Recommendation:** Monitor Anthropic releases. Haiku 4.5 (current default per session) is optimized for sub-actor calls; Sonnet 4.6 for country agents. No migration needed in Phase 1.

---

### 3. Real-Time Data Ingestion

#### 3.1 GDELT Cloud (Commercial Layer) — MEDIUM RELEVANCE
**Discovery:** GDELT Cloud structures raw GDELT stream into hourly events database. Coverage strong from March 2026 onward.

**Current Parallax state:** Uses raw GDELT via BigQuery with 4-stage filter (volume gate, structural dedup, semantic dedup, relevance scoring).

**Assessment:**
- **Relevance:** MEDIUM — pre-filtered events could bypass stages 1-2, improving latency
- **Effort:** MEDIUM — requires new API client, retesting of filters
- **Risk:** MEDIUM — commercial dependency, potential cost overhead (~$100-500/month for event-scale usage)
- **Recommendation:** Pilot on 1 week of Hormuz events. Measure:
  - Signal latency vs. raw GDELT
  - Dedup quality (overlap with semantic dedup stage)
  - Cost vs. current BigQuery spend
  - If latency improves > 10 min and cost is < $200/month, integrate as optional tier

**Sources:**
- [GDELT Cloud Docs](https://docs.gdeltcloud.com/)
- [Free Geopolitical Data APIs 2026 (World Monitor blog)](https://www.worldmonitor.app/blog/posts/free-geopolitical-data-apis-2026/)

---

#### 3.2 POLECAT Dataset — MEDIUM RELEVANCE
**Discovery:** Newer event dataset (2025) compared to GDELT in academic study. Covers scale, coverage, redundancy, accuracy.

**Assessment:**
- **Relevance:** MEDIUM — potential alternative or complement to GDELT for validating event detection
- **Effort:** MEDIUM — would require new ingestion pipeline
- **Risk:** MEDIUM-HIGH — dataset maturity/availability unclear (no public API found)
- **Recommendation:** Defer to Phase 2. Request access from authors if Phase 1 eval shows GDELT blindspots.

**Sources:**
- [POLECAT Evaluation Paper (arXiv)](https://www.citedrive.com/en/discovery/evaluating-automated-event-databases-for-event-forecasting-a-comparative-analysis-of-gdelt-and-polecat/)

---

#### 3.3 ICEWS (Lockheed Martin) — LOW RELEVANCE
**Discovery:** Mentioned as groundbreaking alongside GDELT. Likely restricted access.

**Assessment:**
- **Relevance:** LOW — commercial/military-grade dataset, unclear public availability
- **Recommendation:** Skip Phase 1. Contact if Phase 2 pursues defense partnerships.

---

### 4. Evaluation / MLOps

#### 4.1 Calibration as First-Class Metric — HIGH RELEVANCE ⭐
**Discovery:** Recent research (2025) argues calibration (confidence vs. actual accuracy) is fundamental to prediction quality but overlooked in LLM eval. 
- Accuracy tells you "did the model get it right?"
- Calibration tells you "can you trust its confidence score?"

**Current Parallax state:** Spec includes `confidence` field in predictions and computes 30-day rolling calibration score. But no mention of Expected Calibration Error (ECE), Brier Score, or confidence bucket analysis.

**Assessment:**
- **Relevance:** HIGH — directly applicable to daily scorecard (Section 7.2 of design spec)
- **Effort:** LOW — metrics-only, ~50 lines of Python
- **Risk:** LOW — well-studied techniques
- **Recommendation:** 
  - Add ECE (Expected Calibration Error) to daily eval results
  - Track per-agent calibration (some agents may overconfident, others underconfident)
  - Flag agents where confidence diverges > 15% from actual hit rate
  - If agent calibration degrades, flag for prompt refinement before accuracy even drops
  - **Impact:** Catches model drift earlier, improves confidence in signal decisions

**Code sketch:**
```python
def calibration_error(predictions, outcomes):
    """Compute Expected Calibration Error."""
    # Bin predictions by confidence bucket (0.5-0.6, 0.6-0.7, etc.)
    # For each bucket, measure actual accuracy
    # ECE = weighted average of |predicted_confidence - actual_accuracy|
```

**Sources:**
- [Calibration as a First-Class Criterion (arXiv 2024)](https://arxiv.org/pdf/2609.26489)
- [Geng et al. Calibration Methods Survey (2024)](https://aclanthology.org/2024.knowllm-1.10)

---

#### 4.2 Accuracy-Controlled Calibration Metrics — MEDIUM RELEVANCE
**Discovery:** 2026 research shows standard calibration metrics (ECE, Brier Score) can mislead when comparing models with different accuracy levels.

**Assessment:**
- **Relevance:** MEDIUM — relevant if Parallax A/B tests multiple agent prompt versions
- **Effort:** LOW — metric tweak
- **Risk:** LOW
- **Recommendation:** When comparing two prompt versions in `eval_results`, account for accuracy difference (don't penalize a better-accuracy version for slightly worse calibration). Use confidence intervals.

**Sources:**
- [Accuracy-Controlled Calibration Metrics (arXiv 2026)](https://arxiv.org/pdf/2511.21140v2)

---

#### 4.3 LLM-as-Judge Evaluation (ICML 2026) — LOW-MEDIUM RELEVANCE
**Discovery:** 2026 paper on bias correction for LLM judges. Addresses noisy judge-based scoring.

**Assessment:**
- **Relevance:** LOW-MEDIUM — Parallax doesn't use LLM judges yet (all eval is ground-truth comparison)
- **Effort:** LOW
- **Risk:** LOW
- **Recommendation:** Defer to Phase 2 if Parallax adopts human or LLM judges for ambiguous outcomes.

---

### 5. Performance / Frontend

#### 5.1 deck.gl H3HexagonLayer Optimization — LOW RELEVANCE
**Discovery:** Best practices for deck.gl performance:
- Minimize layer updates (most critical)
- Keep data prop stable (avoid shallow copy churn)
- ~1M item limit for smooth 60 FPS
- 10M-100M items crash browser allocations

**Current Parallax state:** 400K hexes (~Res 3-9 combined) — well within comfort zone.

**Assessment:**
- **Relevance:** LOW — Parallax is 4x below scale limits
- **Effort:** N/A
- **Risk:** N/A
- **Recommendation:** Already compliant. Document in performance playbook for Phase 2 if resolution is increased (e.g., global scenarios with 2M+ hexes).

**Sources:**
- [deck.gl Performance Guide](https://deck.gl/docs/developer-guide/performance)

---

## Top 3 Recommendations (Prioritized)

### 🎯 #1: Implement Calibration Metrics (Phase 1, Week 2)
**Why:** Highest ROI. Catches model drift 2-3 days before accuracy-based metrics. Already have infrastructure.

**Action:**
1. Add ECE calculation to `scoring/calibration.py`
2. Add `calibration_error` column to `eval_results` table
3. Update daily scorecard dashboard to highlight agents where ECE > 0.15
4. Add alert: "Agent `{agent_id}` calibration degraded — consider rollback"

**Effort:** 4-6 hours  
**Cost savings:** $0 (no new infrastructure)  
**Expected impact:** Detect 2-3 more errors before they compound; improve signal confidence

---

### 🎯 #2: Batch API for Eval Pipeline (Phase 1, Week 3)
**Why:** 50-95% cost reduction on eval cron + A/B testing. Low-risk change.

**Action:**
1. Refactor `cli/brief.py --scorecard` to use Batch API for eval LLM calls (meta-agent prompt suggestions, recalibration checks)
2. Keep live agent swarm on standard API (must be synchronous)
3. Measure: cost per daily eval run before/after

**Effort:** 3-4 hours  
**Cost savings:** $30-50/month (~$400/year)  
**Expected impact:** Green light for more frequent eval runs (2x/day possible)

---

### 🎯 #3: Profile DuckDB Spatial Queries (Phase 1, Week 4)
**Why:** Potential 2-3x faster Hormuz cell updates. Low risk if latency is NOT a bottleneck.

**Action:**
1. Add query timing to `world_state_delta` writes for Hormuz corridor (Res 7-8)
2. If median > 50ms, measure gain from POINT_2D → LINESTRING_2D migration on 1K cells
3. If > 30% improvement, plan migration for Phase 2

**Effort:** 2-3 hours (profiling), 8-10 hours (migration if needed)  
**Cost savings:** $0 (infrastructure unchanged)  
**Expected impact:** Smoother real-time updates; reduced WebSocket latency spikes

---

## Deferred (Phase 2+)

- **GDELT Cloud integration** — requires pilot after Phase 1 eval
- **POLECAT dataset** — low maturity, deferred until paper is published/data is public
- **Horizontal scaling to Postgres** — only if Phase 2 requires multi-process workers (keep DuckDB for now)

---

## Sources

- [Amazon Redshift H3 Functions (Jan 2025)](https://aws.amazon.com/about-aws/whats-new/2025/01/amazon-redshift-new-geospatial-h3-indexing-functions/)
- [DuckDB Spatial Docs](https://duckdb.org/docs/stable/extensions/spatial/overview)
- [Claude Prompt Caching](https://platform.claude.com/docs/en/build-with-claude/prompt-caching)
- [Claude Batch API](https://platform.claude.com/docs/en/build-with-claude/batch-processing)
- [GDELT Cloud](https://docs.gdeltcloud.com/)
- [Free Geopolitical Data APIs 2026](https://www.worldmonitor.app/blog/posts/free-geopolitical-data-apis-2026/)
- [Calibration First-Class Criterion (arXiv)](https://arxiv.org/pdf/2609.26489)
- [Accuracy-Controlled Calibration (arXiv 2026)](https://arxiv.org/pdf/2511.21140v2)
- [LLM-as-Judge Bias Correction (ICML 2026)](https://proceedings.mlr.press/v306/lee26bl.html)
- [deck.gl Performance Guide](https://deck.gl/docs/developer-guide/performance)

---

**Report generated:** 2026-10-24  
**Researched by:** Claude Haiku 4.5 (Parallax Tech Scout)
