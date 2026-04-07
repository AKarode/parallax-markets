# Parallax Phase 1 — Daily Health Check
**Date:** 2026-04-07
**Status:** RED

---

## Summary

The repository has reached **zero implementation for eight consecutive days** since the Phase 1 spec and plan were committed on March 30. No `backend/` or `frontend/` directories exist; all 70+ source files and 18 test files remain unwritten. A seventh tech research report was committed on April 6, directly defying the explicit recommendation in the April 6 health check to halt research until Task 2 (single-writer DB layer) is committed. Tomorrow (Day 9) marks the threshold beyond which a full 30-day prediction calibration window becomes impossible within Phase 1.

---

## Changes Since 2026-04-06

- **Added:** `docs/reports/2026-04-06-tech-research.md` — 5 categories of findings (H3 v4 ecosystem, DuckDB experimental 2D types/Vortex format, Claude Batch API, AIS integration, deck.gl GPU aggregation). Committed despite the April 6 health check explicitly closing with *"No tech research report — recommendation to halt research has been repeated daily since April 3 without effect."*
- **No code committed.** `backend/` and `frontend/` directories still do not exist. Task 1 of the implementation plan (project scaffold + DuckDB schema) has not been started for the **eighth consecutive day**.

---

## Issues Found

### Critical

- **[CRITICAL] Zero implementation — Day 8.** Neither `backend/` nor `frontend/` directories exist. All 70+ source files and 18 test files remain unwritten. The implementation plan's Task 1 (project scaffold + DuckDB schema) has not been started. The spec requires 30 days of real-world predictions to demonstrate calibration accuracy; 8 days have elapsed with zero data collected. **22 days remain of the 30-day eval window.**

- **[CRITICAL] No tests.** 0 / 18 planned test files exist. All 18 specified in the plan remain missing: `test_schema.py`, `test_writer.py`, `test_h3_utils.py`, `test_gdelt_filter.py`, `test_dedup.py`, `test_cascade.py`, `test_circuit_breaker.py`, `test_world_state.py`, `test_config.py`, `test_agent_schemas.py`, `test_agent_router.py`, `test_agent_runner.py`, `test_scoring.py`, `test_predictions.py`, `test_prompt_versioning.py`, `test_auth.py`, `test_budget_tracker.py`, `test_integration.py`.

- **[CRITICAL] No DuckDB schema.** All 10 tables (`world_state_delta`, `world_state_snapshot`, `agent_memory`, `agent_prompts`, `decisions`, `predictions`, `curated_events`, `raw_gdelt`, `eval_results`, `simulation_state`) remain unimplemented. This is the critical-path blocker for every other backend task.

- **[CRITICAL] 30-day eval window threshold crossed tomorrow.** The April 6 health check stated that below 21 days remaining (Day 9), the spec's 30-day calibration target becomes unachievable for Phase 1. Day 9 is tomorrow. If Task 1 is not committed today, the 30-day eval window is permanently forfeit for Phase 1.

### High

- **[HIGH] Research halt recommendation ignored for the fifth consecutive day.** The April 3 health check first recommended halting research. Every health check since (April 4, 5, 6) repeated this recommendation. A seventh tech research report was committed on April 6. The research backlog now spans 7 reports (March 31, April 1–6) with 40+ findings, of which at least one confirmed error exists (April 2 cache-header recommendation). No further tech research should be added.

- **[HIGH] No dependency manifests.** `backend/pyproject.toml` and `frontend/package.json` do not exist. No dependency pinning, version floor enforcement, or CVE audit is possible. Day 8 carry-forward.

- **[HIGH] No `.gitignore`.** `.DS_Store` files (`docs/.DS_Store`, `docs/superpowers/.DS_Store`) are tracked in git. No `.gitignore` exists to exclude `.DS_Store`, `__pycache__/`, `.venv/`, `node_modules/`, `.env`, `*.duckdb`. Day 8 carry-forward.

- **[HIGH] GitHub Actions permissions gap — Day 8, unresolved.** Both `.github/workflows/claude.yml` and `.github/workflows/claude-code-review.yml` have `pull-requests: read` and `issues: read`. Both need `pull-requests: write` and `issues: write` for Claude to post review comments and issue replies. This is a 2-line change per file and has been flagged every day for eight days without action.

- **[HIGH] Prompt caching correction still unresolved.** The April 2 health check incorrectly recommended removing `cache_control` headers from `runner.py`. The April 3–5 research confirmed this was wrong: explicit `cache_control: { type: "ephemeral" }` blocks are required on system prompts for the Claude API to cache them. The incorrect amendment must not be applied when `runner.py` is written.

- **[HIGH] Eight unacted plan amendments accumulating.** The following amendments have been validated across research reports (April 1–6) and must be applied before or during coding:

  | Gap | Plan State | Correct Action |
  |-----|-----------|----------------|
  | Agent output validation | Ad-hoc JSON in `schemas.py` | Use Pydantic + Claude Structured Outputs (GA Jan 2026) |
  | Cold-start cost | Live LLM calls, ~$30–50 one-time | Use Batch API + prompt caching; target ~$2–5 one-time |
  | `highPrecision` flag | Not in `HexMap.tsx` task | Add `highPrecision: false` (or `'auto'`) to all `H3HexagonLayer` instances |
  | Prompt caching | Incorrect amendment to remove headers | **Keep explicit `cache_control: { type: "ephemeral" }` on system prompts in `runner.py`** |
  | R-tree spatial index | Not in `schema.py` DDL | Add `CREATE INDEX cell_rtree ON world_state_delta (cell_id) USING RTREE` |
  | AIS integration | Not in plan | Add AIS ingestion task (week 2–3); use aisstream.io WebSocket |
  | GPU aggregation | Not in `HexMap.tsx` task | Add `gpuAggregation: true` to H3HexagonLayer instances |
  | DuckDB 2D types | Not in plan | Profile GEOMETRY vs POINT_2D for hot paths when schema exists (April 6 finding) |

### Medium

- **[MEDIUM] `pytest.ini` duplication.** The plan specifies both `[tool.pytest.ini_options]` in `pyproject.toml` and a standalone `pytest.ini`. `pytest.ini` takes precedence and will silently shadow the `pyproject.toml` config. Use `pyproject.toml` only; drop standalone `pytest.ini`. Day 8 carry-forward.

- **[MEDIUM] DuckDB H3 community extension version not pinned.** The spec (Section 1) explicitly requires pinning the H3 community extension version in deployment config. Must be addressed on first deploy. Day 8 carry-forward.

- **[MEDIUM] No cold-start bootstrap task in implementation plan.** Spec Section 11 describes the one-time batch bootstrap job (~$2–5 with Batch API per the April 3–4 research). The plan has no tracked task for it. Without it, first deploy has no world state and the demo is non-functional. Day 8 carry-forward.

- **[MEDIUM] `deck.gl` version unspecified.** The `frontend/package.json` task specifies no version floor for `deck.gl`. Must pin to `>=9.2` to match the deck.gl 9.2.6 release (Feb 2026) and for GPU aggregation support. Day 8 carry-forward.

### Low

- **[LOW] R-tree spatial index absent from DDL plan.** `CREATE INDEX ... USING RTREE` on `world_state_delta.cell_id` provides ~58x speedup for H3 proximity queries (DuckDB v1.3.0+ SPATIAL_JOIN operator). Not currently in the `schema.py` DDL task. Day 8 carry-forward.

- **[LOW] DuckDB query caching not in API plan.** A `@cache_with_ttl(60s)` decorator on indicator card endpoints reduces backend load ~20–30% at near-zero cost. Not in the `api/routes.py` task. Day 8 carry-forward.

- **[LOW] `RESEARCH.md` at repo root is unreferenced.** Not linked from spec or plan. Should be moved to `docs/` or explicitly linked. Day 8 carry-forward.

- **[LOW] `react-window` virtualization absent from agent feed task.** 50 agents × 5 decisions/hour = ~250 entries/day in `AgentFeed.tsx`. Without virtualization, DOM growth degrades during active crisis periods. Day 8 carry-forward.

- **[LOW] Promptfoo not in eval plan.** Recommended for automated A/B prompt testing; current plan relies solely on manual admin dashboard review. Day 8 carry-forward.

- **[LOW] OilPriceAPI fallback not in ingestion plan.** Recommended as a real-time fallback when EIA API lags or is unavailable for `oil_prices.py`. Day 8 carry-forward.

- **[LOW] DuckDB Vortex format not in replay plan.** April 6 research identifies Vortex columnar format (DuckDB 2026) as a potential replacement for Parquet in replay/archive workflow. Low-effort evaluation item for Phase 2 planning.

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

**Planned version floors (from Task 1 of the implementation plan) with accumulated research updates:**

| Package | Planned Floor | Recommended Floor | Notes |
|---------|--------------|-------------------|-------|
| `fastapi` | >=0.115 | >=0.115 | Acceptable |
| `uvicorn[standard]` | >=0.34 | >=0.34 | Acceptable |
| `duckdb` | >=1.2 | **>=1.3** | v1.3.0+ required for SPATIAL_JOIN 58x perf improvement |
| `h3` | >=4.1 | >=4.1 | h3-4.4.2 stable (Jan 2026) |
| `anthropic` | >=0.52 | >=0.52 | Structured Outputs GA Jan 2026; Batch API GA |
| `pydantic` | >=2.10 | >=2.10 | Stable |
| `sentence-transformers` | >=3.4 | >=3.4 | all-MiniLM-L6-v2 confirmed |
| `deck.gl` | **unspecified** | **>=9.2** | GPU aggregation requires 9.2.6+ (Feb 2026) |

No CVE audit possible until manifests exist.

---

## Test Coverage

**0 / 18 planned test files — all missing.** Day 8, no change from Days 1–7.

---

## Recommendations

1. **Start Task 1 today — final day before 30-day eval window is forfeit.** Create `backend/pyproject.toml`, `backend/src/parallax/db/schema.py`, and `backend/tests/conftest.py`. The plan provides exact code for all three files. This is copy-paste work. Day 9 makes the 30-day calibration window unachievable.

2. **Add `.gitignore` as the very first commit.** Include `.DS_Store`, `__pycache__/`, `*.pyc`, `.venv/`, `node_modules/`, `.env`, `*.duckdb`, `*.db`. Then run `git rm --cached docs/.DS_Store docs/superpowers/.DS_Store`.

3. **Apply the 8 validated plan amendments before writing code.** Priority order: (a) `duckdb >=1.3` in `pyproject.toml`, (b) R-tree index in `schema.py`, (c) `cache_control` headers kept in `runner.py`, (d) Structured Outputs in `schemas.py`, (e) `deck.gl >=9.2` in `package.json`, (f) GPU aggregation + `highPrecision` in `HexMap.tsx`.

4. **Fix GitHub Actions permissions now.** Add `pull-requests: write` and `issues: write` to both workflow files. 4-line total change. Flagged for 8 consecutive days.

5. **Absolute moratorium on tech research until Task 2 is committed.** Seven reports have been written with zero code produced. The research backlog is now a liability — it contains at least one confirmed error and requires integration judgment that cannot be exercised without working code. No new `*-tech-research.md` files until `backend/src/parallax/db/writer.py` exists with passing tests.

---

*No tech research report. Research resumes only after Task 2 (single-writer DB layer) produces committed, tested code.*
