# Parallax Phase 1 — Daily Health Check
**Date:** 2026-04-06
**Status:** RED

---

## Summary

The repository has reached **zero implementation for seven consecutive days** since the Phase 1 spec and plan were committed on March 30. No `backend/` or `frontend/` directories exist; all 70+ source files and 18 test files remain unwritten. The April 5 health check recommended halting tech research until Task 1–2 were implemented — this recommendation was ignored: a sixth tech research report was committed the same day, compounding an already-excessive backlog. The 30-day continuous eval window has now lost 23% of its intended runtime with zero ground truth collected.

---

## Changes Since 2026-04-05

- **Added:** `docs/reports/2026-04-05-tech-research.md` — 5 categories of findings (H3/spatial, Claude API prompt caching, AIS via aisstream.io, eval dashboards, React 19/Vite 6). Committed despite the April 5 health check explicitly stating "No tech research report today — research backlog is sufficient."
- **No code committed.** `backend/` and `frontend/` directories still do not exist. Task 1 of the implementation plan (project scaffold + DuckDB schema) has not been started for the seventh consecutive day.

---

## Issues Found

### Critical

- **[CRITICAL] Zero implementation — Day 7.** Neither `backend/` nor `frontend/` directories exist. All 70+ source files and 18 test files remain unwritten. The implementation plan's Task 1 (project scaffold + DuckDB schema) has not been started. The spec requires 30 days of real-world predictions to demonstrate calibration accuracy; 7 days have elapsed with zero data collected, leaving at most 23 days of the eval window.

- **[CRITICAL] No tests.** 0 / 18 planned test files exist. All 18 specified in the plan remain missing: `test_schema.py`, `test_writer.py`, `test_h3_utils.py`, `test_gdelt_filter.py`, `test_dedup.py`, `test_cascade.py`, `test_circuit_breaker.py`, `test_world_state.py`, `test_config.py`, `test_agent_schemas.py`, `test_agent_router.py`, `test_agent_runner.py`, `test_scoring.py`, `test_predictions.py`, `test_prompt_versioning.py`, `test_auth.py`, `test_budget_tracker.py`, `test_integration.py`.

- **[CRITICAL] No DuckDB schema.** All 10 tables (`world_state_delta`, `world_state_snapshot`, `agent_memory`, `agent_prompts`, `decisions`, `predictions`, `curated_events`, `raw_gdelt`, `eval_results`, `simulation_state`) remain unimplemented. This is the critical-path blocker for every other backend task.

### High

- **[HIGH] Research halt recommendation ignored — backlog now 6 reports deep.** The April 5 health check concluded "No tech research report today — research backlog is sufficient. Research resumes when Task 2 (single-writer DB layer) is committed." A sixth tech research report was committed on the same day. The research backlog now spans 6 reports (March 31, April 1–5) with 35+ findings and 7 actionable plan amendments. Every report written before code exists risks introducing contradictions (the April 2 cache-header error is a confirmed example). No further tech research should be added until Task 2 is committed.

- **[HIGH] No dependency manifests.** `backend/pyproject.toml` and `frontend/package.json` do not exist. No dependency pinning, version floor enforcement, or CVE audit is possible. Day 7 carry-forward.

- **[HIGH] No `.gitignore`.** `.DS_Store` files (`docs/.DS_Store`, `docs/superpowers/.DS_Store`) are still tracked in git. No `.gitignore` exists to exclude `.DS_Store`, `__pycache__/`, `.venv/`, `node_modules/`, `.env`, `*.duckdb`. Day 7 carry-forward.

- **[HIGH] GitHub Actions permissions gap — Day 7, unresolved.** Both `.github/workflows/claude.yml` and `.github/workflows/claude-code-review.yml` have `pull-requests: read` and `issues: read`. Both need `pull-requests: write` and `issues: write` for Claude to post review comments and issue replies. This is a 2-line change per file and has been flagged every day for seven days without action.

- **[HIGH] Prompt caching correction still unresolved.** The April 2 health check incorrectly recommended removing `cache_control` headers from `runner.py`. The April 3–5 research confirmed this was wrong: explicit `cache_control: { type: "ephemeral" }` blocks are required on system prompts for the Claude API to cache them. The incorrect amendment must not be applied when `runner.py` is written.

- **[HIGH] Seven unacted plan amendments accumulating.** The following amendments have been validated across research reports (April 1–5) and must be applied before coding begins:

  | Gap | Plan State | Correct Action |
  |-----|-----------|----------------|
  | Agent output validation | Ad-hoc JSON in `schemas.py` | Use Pydantic + Claude Structured Outputs (GA Jan 2026) |
  | Cold-start cost | Live LLM calls, ~$30–50 one-time | Use Batch API + prompt caching; target ~$2–5 one-time |
  | `highPrecision` flag | Not in `HexMap.tsx` task | Add `highPrecision: false` (or `'auto'`) to all `H3HexagonLayer` instances |
  | Prompt caching | Incorrect amendment to remove headers | **Keep explicit `cache_control: { type: "ephemeral" }` on system prompts in `runner.py`** |
  | R-tree spatial index | Not in `schema.py` DDL | Add `CREATE INDEX cell_rtree ON world_state_delta (cell_id) USING RTREE` |
  | AIS integration | Not in plan | Add AIS ingestion task (week 2–3); use aisstream.io WebSocket |
  | GPU aggregation | Not in `HexMap.tsx` task | Add `gpuAggregation: true` to H3HexagonLayer instances (April 5 finding) |

### Medium

- **[MEDIUM] `pytest.ini` duplication.** The plan specifies both `[tool.pytest.ini_options]` in `pyproject.toml` and a standalone `pytest.ini`. `pytest.ini` takes precedence and will silently shadow the `pyproject.toml` config. Use `pyproject.toml` only; drop standalone `pytest.ini` from the plan. Day 7 carry-forward.

- **[MEDIUM] DuckDB H3 community extension version not pinned.** The spec (Section 1) explicitly requires pinning the H3 community extension version in deployment config. No deployment config exists yet, but this must be addressed on first deploy. Day 7 carry-forward.

- **[MEDIUM] No cold-start bootstrap task in implementation plan.** Spec Section 11 describes the one-time batch bootstrap job (~$2–5 with Batch API per the April 3–4 research). The plan has no tracked task for it. Without it, first deploy has no world state and the demo is non-functional. Day 7 carry-forward.

- **[MEDIUM] `deck.gl` version unspecified.** The `frontend/package.json` task specifies no version floor for `deck.gl`. Must pin to `>=9.2` to match the deck.gl 9.2.6 release (Feb 2026, confirmed by April 5 research) and for GPU aggregation support.

- **[MEDIUM] 30-day eval window compressing daily.** The prediction accuracy window to demonstrate calibration runs from first live GDELT event through 30 days. With no implementation started on Day 7, at most 23 days remain in a clean March 30 window. A compressed eval window weakens the calibration story. Below 21 days remaining (Day 9), the spec's 30-day target becomes unachievable for Phase 1.

### Low

- **[LOW] R-tree spatial index absent from DDL plan.** `CREATE INDEX ... USING RTREE` on `world_state_delta.cell_id` provides ~58x speedup for H3 proximity queries (DuckDB v1.3.0+ SPATIAL_JOIN operator, confirmed April 4–5 research). Not currently in the `schema.py` DDL task.

- **[LOW] DuckDB query caching not in API plan.** A `@cache_with_ttl(60s)` decorator on indicator card endpoints would reduce backend load ~20–30% at near-zero cost. Not in the `api/routes.py` task. Day 7 carry-forward.

- **[LOW] `RESEARCH.md` at repo root is unreferenced.** Not linked from spec or plan. Should be moved to `docs/` or explicitly linked. Day 7 carry-forward.

- **[LOW] `react-window` virtualization absent from agent feed task.** 50 agents × 5 decisions/hour = ~250 entries/day in `AgentFeed.tsx`. Without virtualization, DOM growth degrades during active crisis periods. Day 7 carry-forward.

- **[LOW] Promptfoo not in eval plan.** April 3 research recommends Promptfoo for automated A/B prompt testing. Current plan relies solely on manual admin dashboard review. Low-effort improvement worth adding to the eval tasks.

- **[LOW] OilPriceAPI fallback not in ingestion plan.** April 5 research recommends OilPriceAPI as a real-time fallback when EIA API lags or is unavailable. Low-effort resilience improvement for `oil_prices.py`.

---

## Spec / Plan Consistency

No code exists to check against the spec. The spec and plan remain internally consistent except for one confirmed plan-amendment error (April 2 recommendation to remove `cache_control` headers — **must not be applied**).

---

## Architecture Drift

Not applicable — no code exists. Target layout per the plan:

```
backend/src/parallax/{db,spatial,ingestion,simulation,agents,eval,api,budget}/
backend/tests/ (18 test files)
frontend/src/{components,hooks,types,lib}/
```

---

## Dependency Audit

Not applicable — no `pyproject.toml` or `package.json` exist.

**Planned version floors (from Task 1 of the implementation plan) with April 5 research updates:**

| Package | Planned Floor | Recommended Floor | Notes |
|---------|--------------|-------------------|-------|
| `fastapi` | >=0.115 | >=0.115 | Acceptable — current latest 0.115.x |
| `uvicorn[standard]` | >=0.34 | >=0.34 | Acceptable |
| `duckdb` | >=1.2 | >=1.3 | v1.3.0+ required for SPATIAL_JOIN 58x perf improvement |
| `h3` | >=4.1 | >=4.1 | H3-py v4.4.2 released Jan 2026; stable |
| `anthropic` | >=0.52 | >=0.52 | Structured Outputs GA Jan 2026; Batch API GA |
| `pydantic` | >=2.10 | >=2.10 | Stable |
| `sentence-transformers` | >=3.4 | >=3.4 | all-MiniLM-L6-v2 confirmed optimal |
| `deck.gl` | **unspecified** | **>=9.2** | **Updated from >=8.8: GPU aggregation requires 9.2.6+ (Feb 2026)** |

No CVE audit possible until manifests exist.

---

## Test Coverage

**0 / 18 planned test files — all missing.** Day 7, no change from Days 1–6.

---

## Recommendations

1. **Start Task 1 today (Day 7 — critical path deadline approaching).** Create `backend/pyproject.toml`, `backend/src/parallax/db/schema.py`, and `backend/tests/conftest.py`. The DuckDB schema is the critical-path blocker for everything else. The plan provides exact code — there is no ambiguity. Below Day 9, a 30-day calibration window becomes impossible.

2. **Add `.gitignore` as the very first commit.** Include `.DS_Store`, `__pycache__/`, `*.pyc`, `.venv/`, `node_modules/`, `.env`, `*.duckdb`, `*.db`. Then run `git rm --cached docs/.DS_Store docs/superpowers/.DS_Store`.

3. **Apply the 7 validated plan amendments before writing code.** Especially: prompt caching (`cache_control` headers kept), R-tree index in `schema.py`, Structured Outputs in `schemas.py`, `deck.gl >=9.2` in `package.json`, and GPU aggregation in `HexMap.tsx`.

4. **Fix GitHub Actions permissions now.** Add `pull-requests: write` and `issues: write` to both workflow files. This is a 4-line total change across 2 files and has been flagged for 7 consecutive days.

5. **No further tech research until Task 2 is committed.** The April 5 health check recommended halting research; the recommendation was ignored and a sixth report was written. The research backlog is now a risk in itself — its contradictions (the cache-header error) outweigh its value. Research resumes only after `backend/src/parallax/db/writer.py` is committed and tested.

6. **Upgrade `duckdb` floor to `>=1.3`.** The April 4–5 research confirms DuckDB v1.3.0 introduced the SPATIAL_JOIN operator delivering 58x performance improvement for H3 proximity queries. Update the planned floor in `pyproject.toml` from `>=1.2` to `>=1.3`.

---

*No tech research report — recommendation to halt research has been repeated daily since April 3 without effect. The next research report will be written only after Task 2 (single-writer DB layer) produces committed, tested code.*
