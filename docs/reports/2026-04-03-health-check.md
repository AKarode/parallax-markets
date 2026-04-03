# Parallax Phase 1 — Daily Health Check
**Date:** 2026-04-03
**Status:** RED

---

## Summary

The repository has reached **zero implementation for four consecutive days** since the Phase 1 spec and plan were committed on March 30. No `backend/` or `frontend/` directories exist; all 70+ source files and 18 test files remain unwritten. Accumulated tech research across four reports (March 31, April 1 × 2, April 2) has produced 25+ findings and 6 actionable plan amendments, none of which have been actioned. Runway risk is increasing daily.

---

## Changes Since 2026-04-02

- **Added:** `docs/reports/2026-04-02-tech-research.md` — 9 findings across 5 categories, 3 high-impact recommendations (AIS integration, Batch API for eval, Zustand refactor). None actioned.
- **No code committed.** `backend/` and `frontend/` directories still do not exist. Task 1 of the implementation plan has not been started for the fourth consecutive day.

---

## Issues Found

### Critical

- **[CRITICAL] Zero implementation — Day 4.** Neither `backend/` nor `frontend/` directories exist. All 70+ source files and 18 test files remain unwritten. The implementation plan's Task 1 (project scaffold + DuckDB schema) has not been started. Every day of delay shortens the 30-day continuous eval window and increases the cost of the cold-start bootstrap job.

- **[CRITICAL] No tests.** 0 / 18 planned test files exist. All 18 test files specified in the plan remain missing: `test_schema.py`, `test_writer.py`, `test_h3_utils.py`, `test_gdelt_filter.py`, `test_dedup.py`, `test_cascade.py`, `test_circuit_breaker.py`, `test_world_state.py`, `test_config.py`, `test_agent_schemas.py`, `test_agent_router.py`, `test_agent_runner.py`, `test_scoring.py`, `test_predictions.py`, `test_prompt_versioning.py`, `test_auth.py`, `test_budget_tracker.py`, `test_integration.py`.

- **[CRITICAL] No DuckDB schema.** All 10 tables (`world_state_delta`, `world_state_snapshot`, `agent_memory`, `agent_prompts`, `decisions`, `predictions`, `curated_events`, `raw_gdelt`, `eval_results`, `simulation_state`) remain unimplemented. This is the critical-path blocker for every other backend task.

### High

- **[HIGH] No dependency manifests.** `backend/pyproject.toml` and `frontend/package.json` do not exist. No dependency, version floor, or CVE audit is possible. Carries forward from Day 1.

- **[HIGH] No `.gitignore`.** `.DS_Store` files (`docs/.DS_Store`, `docs/superpowers/.DS_Store`) remain tracked in git. No `.gitignore` exists to exclude `.DS_Store`, `__pycache__/`, `.venv/`, `node_modules/`, `.env`, `*.duckdb`. Carries forward from Day 1.

- **[HIGH] GitHub Actions permissions gap (Day 4, unresolved).** Both `.github/workflows/claude.yml` and `.github/workflows/claude-code-review.yml` have `pull-requests: read` and `issues: read`. Both need `write` permission so Claude can post review comments and issue replies. This has been flagged in all four prior health checks. It is a 2-line change per file.

- **[HIGH] Six unacted plan amendments from four research reports.** Two tech research reports (April 1, April 2) identified six changes that should be made to the implementation plan before coding begins. None have been applied:

  | Gap | Plan State | Finding | Action Needed |
  |-----|-----------|---------|--------------|
  | Agent output validation | Ad-hoc JSON in `schemas.py` | Structured Outputs GA (Jan 2026) | Replace with Pydantic + Claude Structured Outputs |
  | Cold-start cost | Live LLM calls, ~$30–50 one-time | Batch API + prompt caching = ~$2–5 | Add batch bootstrap task to plan |
  | `highPrecision` flag | Not in `HexMap.tsx` task | Required for 400K hex rendering without GPU stall | Add `highPrecision: false` to `H3HexagonLayer` task |
  | Prompt caching headers | Manual `cache_control` in `runner.py` | Auto-caching on prompts >1,024 tokens (Sonnet 4.6 / Haiku 4.5) | Simplify `runner.py` — no manual headers needed |
  | R-tree spatial index | Not in `schema.py` DDL | 58x speedup on H3 proximity queries | Add `CREATE INDEX cell_rtree ... USING RTREE` to schema DDL |
  | AIS real-time data | Not in plan | aisstream.io (free) = ground truth for Hormuz flow validation | Add AIS ingestion task for week 2–3 of implementation |

### Medium

- **[MEDIUM] `pytest.ini` duplication (Day 4, unresolved).** The plan specifies both `[tool.pytest.ini_options]` in `pyproject.toml` and a standalone `pytest.ini`. `pytest.ini` takes precedence and the duplication will cause confusion. Use `pyproject.toml` only; drop the standalone `pytest.ini` from the plan before Task 1 is executed.

- **[MEDIUM] DuckDB H3 extension version not pinned.** No deployment config or lock file enforces the H3 community extension version. The spec calls this out as required. Must be addressed in the first deployment config. Community extensions may lag DuckDB major releases by days/weeks.

- **[MEDIUM] No cold-start bootstrap task in the implementation plan.** The spec describes the one-time batch bootstrap job (Section 11), but the plan has no tracked task for it. Without this, the first deploy will have no world state and the demo will be non-functional. Should use Batch API + prompt caching to cut cost from ~$30–50 to ~$2–5 one-time.

- **[MEDIUM] `deck.gl` version unspecified in plan.** The `frontend/package.json` task specifies no version floor for `deck.gl`. Should pin to v8.8+ for `Tileset2D` and `useWidget` support.

### Low

- **[LOW] R-tree spatial index absent from DDL plan.** `CREATE INDEX ... USING RTREE` on `world_state_delta.cell_id` provides a 58x speedup for H3 proximity queries. Not in the `schema.py` DDL task. Retrofitting indexes later is harder; add from the start.

- **[LOW] DuckDB query caching not in plan.** `@cache_with_ttl(60s)` on indicator card endpoints (oil price, Hormuz traffic, escalation index) would reduce backend load by ~20–30% at near-zero implementation cost. Not in the `api/routes.py` task.

- **[LOW] `RESEARCH.md` at repo root is unreferenced.** Not linked from spec or plan. Should be moved to `docs/` or linked. Carries forward from Day 1.

- **[LOW] `react-window` virtualization not in agent feed task.** 50 agents × 5 decisions/hour = ~250 entries/day in the agent activity feed. Without virtualization, the scrolling list will degrade during active crisis periods. Low-effort add; should be in the `AgentFeed.tsx` task.

---

## Spec / Plan Consistency

No code exists to check against the spec. The spec and plan remain internally consistent.

Six gaps between the current plan and best practice have accumulated across the research reports (see HIGH section above). All six need to be resolved before implementation begins to avoid technical debt on the first commit.

---

## Architecture Drift

Not applicable — no code exists. The planned file layout from the implementation plan remains the target:

```
backend/src/parallax/{db,spatial,ingestion,simulation,agents,eval,api,budget}/
backend/tests/ (18 test files)
frontend/src/{components,hooks,types,lib}/
```

No drift possible until code is written.

---

## Dependency Audit

Not applicable — no `pyproject.toml` or `package.json` exist.

**Planned version floors (from Task 1 of the implementation plan):**

| Package | Floor | Notes |
|---------|-------|-------|
| `fastapi` | >=0.115 | Current latest is 0.115.x — acceptable |
| `uvicorn[standard]` | >=0.34 | Current latest is 0.34.x — acceptable |
| `duckdb` | >=1.2 | Current is 1.2.x — acceptable; H3 community extension last updated 2026-03-25 |
| `h3` | >=4.1 | Python H3 lib — stable |
| `anthropic` | >=0.52 | Current SDK is 0.52.x — acceptable; Structured Outputs GA since Jan 2026 |
| `pydantic` | >=2.10 | Stable |
| `sentence-transformers` | >=3.4 | all-MiniLM-L6-v2 still optimal per April 2 research |
| `deck.gl` | unspecified | Must pin to >=8.8 for TileLayer H3 support |

No CVE audit possible until manifests exist.

---

## Test Coverage

**0 / 18 planned test files — all missing.** Same as Days 1, 2, and 3.

---

## Recommendations

1. **Start Task 1 today (Day 4 — critical).** Create `backend/pyproject.toml`, `backend/src/parallax/db/schema.py`, and `backend/tests/conftest.py`. The DuckDB schema is the critical-path blocker for every other backend task.

2. **Add `.gitignore` as the first commit in Task 1.** Include `.DS_Store`, `__pycache__/`, `*.pyc`, `.venv/`, `node_modules/`, `.env`, `*.duckdb`, `*.db`. Run `git rm --cached docs/.DS_Store docs/superpowers/.DS_Store` to stop tracking existing junk files.

3. **Apply six plan amendments before coding.** These five specific changes plus one additive task to make now (all documented in HIGH section above):
   - Remove standalone `pytest.ini`; use `[tool.pytest.ini_options]` in `pyproject.toml` only.
   - Add `highPrecision: false` to all `H3HexagonLayer` instances in the `HexMap.tsx` task.
   - Add `CREATE INDEX cell_rtree ON world_state_delta (cell_id) USING RTREE` to the `schema.py` DDL.
   - Replace ad-hoc JSON validation in `agents/schemas.py` task with Pydantic + Claude Structured Outputs.
   - Remove manual `cache_control` headers from `runner.py` task — Sonnet 4.6 and Haiku 4.5 auto-cache prompts >1,024 tokens.
   - Add cold-start bootstrap task using Batch API + prompt caching (target: $2–5 one-time, not $30–50).

4. **Fix GitHub Actions permissions.** Add `pull-requests: write` and `issues: write` to both workflow files. This is a 2-line change per file and has been open for 4 days. Do it now before the first PR.

5. **Pin `deck.gl` to v8.8+** in `frontend/package.json` when created. Add `aisstream.io` as a week 2–3 integration task in the implementation plan.

---

*No new tech research report today — the two reports from April 1 and April 2 provide sufficient context. Resuming research when first code is committed.*
