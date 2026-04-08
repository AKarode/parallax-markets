# Parallax Phase 1 — Daily Health Check
**Date:** 2026-04-02
**Status:** RED

---

## Summary

The repository remains at zero implementation for the third consecutive day. No `backend/` or `frontend/` directories exist, no source code has been written, and none of the recommendations from the two prior health checks (2026-03-31, 2026-04-01) have been acted upon. The only repo activity since the last check is the addition of the April 1 tech research report — no code, no tests, no scaffolding.

---

## Changes Since 2026-04-01

- **Added:** `docs/reports/2026-04-01-tech-research.md` — 20 findings, 3 actionable recommendations. Useful context for implementation; none have been applied.
- **No code committed.** `backend/` and `frontend/` directories still do not exist. Task 1 of the implementation plan has not been started.

---

## Issues Found

### Critical

- **[CRITICAL] Zero implementation — Day 3.** Neither `backend/` nor `frontend/` directories exist. All 70+ source files and 18 test files remain unwritten. The implementation plan's Task 1 (project scaffold + DuckDB schema) has not been started for the third consecutive day. The project is accumulating runway risk with no executable deliverables.

- **[CRITICAL] No tests.** 0 / 18 planned test files exist. 0% coverage. All 18 test files specified in the plan remain missing: `test_schema.py`, `test_writer.py`, `test_h3_utils.py`, `test_gdelt_filter.py`, `test_dedup.py`, `test_cascade.py`, `test_circuit_breaker.py`, `test_world_state.py`, `test_config.py`, `test_agent_schemas.py`, `test_agent_router.py`, `test_agent_runner.py`, `test_scoring.py`, `test_predictions.py`, `test_prompt_versioning.py`, `test_auth.py`, `test_budget_tracker.py`, `test_integration.py`.

- **[CRITICAL] No DuckDB schema.** The single-writer topology and all 10 tables (`world_state_delta`, `world_state_snapshot`, `agent_memory`, `agent_prompts`, `decisions`, `predictions`, `curated_events`, `raw_gdelt`, `eval_results`, `simulation_state`) remain unimplemented. This is the critical path blocker for every other backend task.

### High

- **[HIGH] No dependency manifests.** `backend/pyproject.toml` and `frontend/package.json` do not exist. Cannot perform dependency, version floor, or CVE audit. Carries forward from Day 1.

- **[HIGH] No `.gitignore`.** `.DS_Store` files (`docs/.DS_Store`, `docs/superpowers/.DS_Store`) remain tracked. No `.gitignore` has been added to exclude `.DS_Store`, `__pycache__/`, `.venv/`, `node_modules/`, `.env`, `*.duckdb`. First code commit will likely introduce additional junk files without this.

- **[HIGH] GitHub Actions permissions gap (carry-forward).** Both `.github/workflows/claude.yml` and `.github/workflows/claude-code-review.yml` lack `pull-requests: write` and `issues: write` permissions. Claude cannot post review comments on PRs. Unblocked but unresolved for 3 days.

- **[HIGH] Unacted tech research findings.** The April 1 research report identified three HIGH/MEDIUM findings that should be incorporated into the plan before implementation begins:
  1. Structured Outputs GA (Jan 2026) — replace ad-hoc JSON validation in `agents/schemas.py` with Pydantic + Claude Structured Outputs. The spec's `schemas.py` task pre-dates this GA and doesn't account for it.
  2. Batch API for cold-start bootstrap — spec plans live LLM calls for historical replay; Batch API would cut one-time cost from ~$30–50 to ~$2–5.
  3. Auto-prefix cache matching (Feb 2026 update) — workspace-level isolation and 20-block lookback now available; affects `runner.py` implementation.

### Medium

- **[MEDIUM] `pytest.ini` duplication (carry-forward, Day 3).** The implementation plan specifies both `[tool.pytest.ini_options]` in `pyproject.toml` and a standalone `pytest.ini`. These conflict — `pytest.ini` takes precedence. Should be resolved before Task 1 is executed: use `pyproject.toml` only, remove `pytest.ini` from the plan.

- **[MEDIUM] DuckDB H3 extension version not pinned.** No deployment config or lock file enforces the H3 community extension version. The spec calls this out explicitly as required. Must be in the first deployment config. DuckDB H3 extension was last updated March 25, 2026 per the tech research report — confirm compatibility with the `duckdb>=1.2` floor specified in `pyproject.toml`.

- **[MEDIUM] `deck.gl highPrecision: false` absent from plan.** The April 1 research report (Finding 1.1) and March 31 research both confirm `highPrecision: false` on `H3HexagonLayer` is required to render 400K hexes without GPU stall. The `HexMap.tsx` task in the plan does not include this flag. Should be added to the task spec before implementation.

- **[MEDIUM] No cold-start bootstrap job planned for Phase 1 launch.** The spec describes a one-time batch bootstrap (Section 11) but the implementation plan has no explicit Task for it. Without this, the first deploy will have no world state, making the demo non-functional. Needs to be a tracked task before launch.

### Low

- **[LOW] R-tree spatial index absent from DDL plan.** Tech research (Finding 1.1 from March 31) identified a 58x speedup for H3 proximity queries via `CREATE INDEX ... USING RTREE` on `world_state_delta.cell_id`. The plan's `schema.py` task doesn't include this. Should be added to the DDL from the start — retrofitting indexes later is harder.

- **[LOW] `RESEARCH.md` at repo root is unreferenced.** Not linked from spec or plan. Should be moved to `docs/` or linked. Carries forward from Day 1.

- **[LOW] DuckDB query caching not in plan.** Research Finding 5.1 recommends `@cache_with_ttl(60s)` on indicator card endpoints for ~20–30% backend load reduction. No caching layer appears in the `api/routes.py` task. Low effort and high value at launch; add to plan.

---

## Spec / Plan Consistency

No code exists to check against the spec. The spec and plan remain internally consistent (no deviations introduced).

The accumulated tech research across two reports has identified **five gaps** between the current plan and best practice. None have been actioned:

| Gap | Spec/Plan State | Research Finding | Action Needed |
|-----|-----------------|------------------|---------------|
| Agent output validation | Ad-hoc JSON validation in `schemas.py` | Structured Outputs GA (Jan 2026) | Replace with Pydantic + Claude Structured Outputs |
| Cold-start cost | Live LLM calls for 30-day historical replay (~$30–50) | Batch API + caching = 95% savings (~$2–5) | Add batch bootstrap task to plan |
| `highPrecision` flag | Not mentioned in `HexMap.tsx` task | Required for 400K hex rendering | Add to `HexMap.tsx` task |
| Prompt caching | Manual cache-control headers in `runner.py` | Auto-caching on prompts >1,024 tokens (Feb 2026) | Simplify `runner.py` — no manual headers needed |
| R-tree index | Not in `schema.py` DDL | 58x speedup on H3 proximity queries | Add `CREATE INDEX USING RTREE` to schema DDL |

---

## Architecture Drift

Not applicable — no code exists.

---

## Dependency Audit

Not applicable — no `pyproject.toml` or `package.json` exist.

Version floors specified in the plan (from Task 1):
- `fastapi>=0.115`, `uvicorn[standard]>=0.34`, `duckdb>=1.2`, `h3>=4.1`, `anthropic>=0.52`, `pydantic>=2.10`
- `pytest>=8.3`, `pytest-asyncio>=0.25`, `pytest-httpx>=0.35`
- Frontend: React 18, deck.gl (version unspecified — should pin to v8.8+ for Tileset2D support), MapLibre GL

No CVE audit possible until manifests exist.

---

## Test Coverage

**0 / 18 planned test files — all missing.** Same as Days 1 and 2.

---

## Recommendations

1. **Start Task 1 today.** Create `backend/pyproject.toml`, `backend/src/parallax/db/schema.py`, and `backend/tests/conftest.py`. This is the only blocker that, once cleared, unblocks every other backend task. The DuckDB schema must exist before any simulation, ingestion, or agent code can be tested.

2. **Add `.gitignore` as the first commit in Task 1.** Include `.DS_Store`, `__pycache__/`, `*.pyc`, `.venv/`, `node_modules/`, `.env`, `*.duckdb`, `*.db`. Remove existing `.DS_Store` files from git tracking (`git rm --cached docs/.DS_Store docs/superpowers/.DS_Store`).

3. **Patch the plan before coding begins — 5 changes needed:**
   - Remove standalone `pytest.ini`; use `[tool.pytest.ini_options]` in `pyproject.toml` only.
   - Add `highPrecision: false` to `H3HexagonLayer` in the `HexMap.tsx` task.
   - Add `CREATE INDEX cell_rtree ON world_state_delta (cell_id) USING RTREE` to the `schema.py` DDL task.
   - Replace ad-hoc JSON validation in `agents/schemas.py` task with Pydantic + Claude Structured Outputs.
   - Simplify `runner.py` prompt caching — no manual `cache_control` headers needed; Sonnet 4.6 and Haiku 4.5 auto-cache prompts >1,024 tokens.

4. **Add a cold-start bootstrap task to the plan.** The spec describes it (Section 11) but the plan has no tracked task. Use Batch API + prompt caching for the 30-day historical replay job to cut cost from ~$30–50 to ~$2–5.

5. **Fix GitHub Actions permissions.** Add `pull-requests: write` and `issues: write` to both workflow files before the first PR. This is a 2-line change and has been open for 3 days.

6. **Pin `deck.gl` to v8.8+** in `frontend/package.json` when created (for `Tileset2D` and `useWidget` support). Unspecified version floor in the current plan.
