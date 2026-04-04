# Parallax Phase 1 — Daily Health Check
**Date:** 2026-04-04
**Status:** RED

---

## Summary

The repository has reached **zero implementation for five consecutive days** since the Phase 1 spec and plan were committed on March 30. No `backend/` or `frontend/` directories exist; all 70+ source files and 18 test files remain unwritten. The only commits since inception are six reports (5 health checks, 4 tech research), none of which have triggered any code work — the gap between planning documentation and actual implementation is now the primary project risk.

---

## Changes Since 2026-04-03

- **Added:** `docs/reports/2026-04-03-tech-research.md` — 5 categories of findings with 3 top recommendations (prompt caching, AIS integration, Promptfoo). None actioned.
- **No code committed.** `backend/` and `frontend/` directories still do not exist. Task 1 of the implementation plan has not been started for the fifth consecutive day.

---

## Issues Found

### Critical

- **[CRITICAL] Zero implementation — Day 5.** Neither `backend/` nor `frontend/` directories exist. All 70+ source files and 18 test files remain unwritten. The implementation plan's Task 1 (project scaffold + DuckDB schema) has not been started. Every additional day of delay shortens the 30-day continuous eval window, increases cold-start bootstrap cost, and risks the system never getting enough real-world predictions to demonstrate calibration accuracy.

- **[CRITICAL] No tests.** 0 / 18 planned test files exist. All 18 remain missing: `test_schema.py`, `test_writer.py`, `test_h3_utils.py`, `test_gdelt_filter.py`, `test_dedup.py`, `test_cascade.py`, `test_circuit_breaker.py`, `test_world_state.py`, `test_config.py`, `test_agent_schemas.py`, `test_agent_router.py`, `test_agent_runner.py`, `test_scoring.py`, `test_predictions.py`, `test_prompt_versioning.py`, `test_auth.py`, `test_budget_tracker.py`, `test_integration.py`.

- **[CRITICAL] No DuckDB schema.** All 10 tables (`world_state_delta`, `world_state_snapshot`, `agent_memory`, `agent_prompts`, `decisions`, `predictions`, `curated_events`, `raw_gdelt`, `eval_results`, `simulation_state`) remain unimplemented. This is the critical-path blocker for every other backend task.

### High

- **[HIGH] No dependency manifests.** `backend/pyproject.toml` and `frontend/package.json` do not exist. No dependency, version floor, or CVE audit is possible. Carries forward from Day 1.

- **[HIGH] No `.gitignore`.** `.DS_Store` files (`docs/.DS_Store`, `docs/superpowers/.DS_Store`) remain tracked in git. No `.gitignore` exists to exclude `.DS_Store`, `__pycache__/`, `.venv/`, `node_modules/`, `.env`, `*.duckdb`. Carries forward from Day 1.

- **[HIGH] GitHub Actions permissions gap (Day 5, unresolved).** Both `.github/workflows/claude.yml` and `.github/workflows/claude-code-review.yml` have `pull-requests: read` and `issues: read`. Both need `write` permission for Claude to post review comments and issue replies. This is a 2-line change per file and has been flagged every day for five days.

- **[HIGH] Plan-amendment contradiction: prompt caching.** The April 2 health check recommended "Remove manual `cache_control` headers from `runner.py` task — Sonnet 4.6 and Haiku 4.5 auto-cache prompts >1,024 tokens." The April 3 tech research contradicts this, recommending "Add `cache_control: { type: 'ephemeral' }` to system prompt block." The tech research is correct for the Claude API: explicit `cache_control` blocks are required to enable prompt caching on API calls; the workspace-level isolation announced Feb 5, 2026 affects cache scope, not whether the header is required. **The April 2 plan amendment about removing cache headers was incorrect and must not be applied.** The `runner.py` task should include explicit `cache_control` blocks on system prompts.

- **[HIGH] Six unacted plan amendments accumulating.** Five amendments from the April 1–2 research (minus the incorrect cache-header one above), plus the corrected prompt-caching guidance from April 3, need to be applied to the implementation plan before coding begins:

  | Gap | Plan State | Correct Action |
  |-----|-----------|----------------|
  | Agent output validation | Ad-hoc JSON in `schemas.py` | Use Pydantic + Claude Structured Outputs (GA Jan 2026) |
  | Cold-start cost | Live LLM calls, ~$30–50 one-time | Use Batch API + prompt caching; target ~$2–5 one-time |
  | `highPrecision` flag | Not in `HexMap.tsx` task | Add `highPrecision: false` to all `H3HexagonLayer` instances |
  | Prompt caching | Removed from runner (incorrect) | **Keep explicit `cache_control: { type: "ephemeral" }` on system prompts in `runner.py`** |
  | R-tree spatial index | Not in `schema.py` DDL | Add `CREATE INDEX cell_rtree ON world_state_delta (cell_id) USING RTREE` |
  | AIS integration | Not in plan | Add AIS ingestion task (week 2–3); use free aishub.net initially |

### Medium

- **[MEDIUM] `pytest.ini` duplication (Day 5, unresolved).** The plan specifies both `[tool.pytest.ini_options]` in `pyproject.toml` and a standalone `pytest.ini`. `pytest.ini` takes precedence; the duplication will cause confusion. Use `pyproject.toml` only; drop the standalone `pytest.ini` from the plan before Task 1 is executed.

- **[MEDIUM] DuckDB H3 extension version not pinned.** No deployment config or lock file enforces the H3 community extension version. The spec calls this out as required. Must be addressed in the first deployment config.

- **[MEDIUM] No cold-start bootstrap task in the implementation plan.** The spec describes the one-time batch bootstrap job (Section 11), but the plan has no tracked task for it. Without it, first deploy has no world state and the demo is non-functional.

- **[MEDIUM] `deck.gl` version unspecified in plan.** The `frontend/package.json` task specifies no version floor for `deck.gl`. Must pin to v8.8+ for `Tileset2D` and `useWidget` support.

- **[MEDIUM] Five days of unacted research creating decision backlog.** Four tech research reports (March 31, April 1, April 2, April 3) have generated 25+ findings. The backlog compounds daily. If implementation begins without reviewing and resolving these findings, technical debt will be introduced on the first commit.

### Low

- **[LOW] R-tree spatial index absent from DDL plan.** `CREATE INDEX ... USING RTREE` on `world_state_delta.cell_id` provides a 58x speedup for H3 proximity queries. Not in the `schema.py` DDL task.

- **[LOW] DuckDB query caching not in plan.** `@cache_with_ttl(60s)` on indicator card endpoints would reduce backend load ~20–30% at near-zero implementation cost. Not in the `api/routes.py` task.

- **[LOW] `RESEARCH.md` at repo root is unreferenced.** Not linked from spec or plan. Should be moved to `docs/` or linked. Carries forward from Day 1.

- **[LOW] `react-window` virtualization not in agent feed task.** 50 agents × 5 decisions/hour = ~250 entries/day. Without virtualization, `AgentFeed.tsx` will degrade during active crisis periods.

- **[LOW] Promptfoo not in eval plan.** April 3 tech research recommends Promptfoo for automated A/B prompt testing; current plan relies on manual admin dashboard review. Low-effort improvement worth adding to the eval tasks.

---

## Spec / Plan Consistency

No code exists to check against the spec. The spec and plan remain internally consistent, with one confirmed plan-amendment error: the April 2 recommendation to remove `cache_control` headers from `runner.py` was incorrect and must not be applied (see HIGH section above).

---

## Architecture Drift

Not applicable — no code exists. Target layout remains:

```
backend/src/parallax/{db,spatial,ingestion,simulation,agents,eval,api,budget}/
backend/tests/ (18 test files)
frontend/src/{components,hooks,types,lib}/
```

---

## Dependency Audit

Not applicable — no `pyproject.toml` or `package.json` exist.

**Planned version floors (from Task 1 of the implementation plan):**

| Package | Floor | Status |
|---------|-------|--------|
| `fastapi` | >=0.115 | Acceptable — current latest is 0.115.x |
| `uvicorn[standard]` | >=0.34 | Acceptable |
| `duckdb` | >=1.2 | Acceptable; H3 community extension last updated 2026-03-25 |
| `h3` | >=4.1 | Acceptable; H3-py v4.4.2 released Jan 2026 |
| `anthropic` | >=0.52 | Acceptable; Structured Outputs GA Jan 2026 |
| `pydantic` | >=2.10 | Stable |
| `sentence-transformers` | >=3.4 | Acceptable; all-MiniLM-L6-v2 confirmed optimal |
| `deck.gl` | **unspecified** | **Must pin to >=8.8** |

No CVE audit possible until manifests exist.

---

## Test Coverage

**0 / 18 planned test files — all missing.** Same as Days 1–4.

---

## Recommendations

1. **Start Task 1 today (Day 5 — critical).** Create `backend/pyproject.toml`, `backend/src/parallax/db/schema.py`, and `backend/tests/conftest.py`. The DuckDB schema is the critical-path blocker for every other backend task. No further research is needed before coding begins.

2. **Add `.gitignore` as the first commit in Task 1.** Include `.DS_Store`, `__pycache__/`, `*.pyc`, `.venv/`, `node_modules/`, `.env`, `*.duckdb`, `*.db`. Run `git rm --cached docs/.DS_Store docs/superpowers/.DS_Store` to stop tracking existing junk files.

3. **Correct the prompt-caching plan amendment.** The April 2 recommendation to remove `cache_control` headers was wrong. The correct approach is to keep explicit `cache_control: { type: "ephemeral" }` blocks on system prompts in `runner.py`. Verify this before writing any agent runner code.

4. **Apply remaining plan amendments before coding.** Apply the five valid amendments (Structured Outputs, cold-start Batch API, `highPrecision: false`, R-tree index, AIS integration task) to the plan now. Doing it during implementation creates debt.

5. **Fix GitHub Actions permissions.** Add `pull-requests: write` and `issues: write` to both workflow files. This is a 4-line total change and has been open for 5 days.

6. **Stop accumulating tech research without implementation.** Research reports are valuable but generate diminishing returns without code to test against. The next research report should wait until Task 2 or 3 of the implementation plan is complete, so findings can be validated against real code behavior.

---

*No new tech research report today — sufficient context exists. Research resumes when first code is committed.*
