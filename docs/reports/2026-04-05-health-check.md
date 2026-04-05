# Parallax Phase 1 — Daily Health Check
**Date:** 2026-04-05
**Status:** RED

---

## Summary

The repository has reached **zero implementation for six consecutive days** since the Phase 1 spec and plan were committed on March 30. No `backend/` or `frontend/` directories exist; all 70+ source files and 18 test files remain unwritten. The project is now 6 days into a 30-day continuous eval window that has not started — every day of delay meaningfully compresses the window needed to demonstrate prediction calibration.

---

## Changes Since 2026-04-04

- **Added:** `docs/reports/2026-04-04-tech-research.md` — 5 categories of findings covering DuckDB spatial types, deck.gl `highPrecision` auto-switching, Claude Batch API + prompt caching combo, AIS data integration, and React performance. None actioned.
- **No code committed.** `backend/` and `frontend/` directories still do not exist. Task 1 of the implementation plan (project scaffold + DuckDB schema) has not been started for the sixth consecutive day.

---

## Issues Found

### Critical

- **[CRITICAL] Zero implementation — Day 6.** Neither `backend/` nor `frontend/` directories exist. All 70+ source files and 18 test files remain unwritten. The implementation plan's Task 1 (project scaffold + DuckDB schema) has not been started. The 30-day continuous eval window required to demonstrate prediction calibration begins only when the first live GDELT event flows through the agent swarm — this window is now 6 days shorter than planned.

- **[CRITICAL] No tests.** 0 / 18 planned test files exist. All 18 specified in the plan remain missing: `test_schema.py`, `test_writer.py`, `test_h3_utils.py`, `test_gdelt_filter.py`, `test_dedup.py`, `test_cascade.py`, `test_circuit_breaker.py`, `test_world_state.py`, `test_config.py`, `test_agent_schemas.py`, `test_agent_router.py`, `test_agent_runner.py`, `test_scoring.py`, `test_predictions.py`, `test_prompt_versioning.py`, `test_auth.py`, `test_budget_tracker.py`, `test_integration.py`.

- **[CRITICAL] No DuckDB schema.** All 10 tables (`world_state_delta`, `world_state_snapshot`, `agent_memory`, `agent_prompts`, `decisions`, `predictions`, `curated_events`, `raw_gdelt`, `eval_results`, `simulation_state`) remain unimplemented. This is the critical-path blocker for every other backend task.

### High

- **[HIGH] No dependency manifests.** `backend/pyproject.toml` and `frontend/package.json` do not exist. No dependency pinning, version floor enforcement, or CVE audit is possible. Day 6 carry-forward.

- **[HIGH] No `.gitignore`.** `.DS_Store` files (`docs/.DS_Store`, `docs/superpowers/.DS_Store`) are still tracked in git. No `.gitignore` exists to exclude `.DS_Store`, `__pycache__/`, `.venv/`, `node_modules/`, `.env`, `*.duckdb`. Day 6 carry-forward.

- **[HIGH] GitHub Actions permissions gap.** Both `.github/workflows/claude.yml` and `.github/workflows/claude-code-review.yml` have `pull-requests: read` and `issues: read`. Both workflows need `pull-requests: write` and `issues: write` for Claude to post review comments and issue replies. Confirmed present in both files today. Day 6 carry-forward; requires a 2-line fix per file.

- **[HIGH] Plan amendment: prompt caching approach.** The April 2 recommendation to remove `cache_control` headers from `runner.py` was incorrect (flagged in the April 4 health check). Explicit `cache_control: { type: "ephemeral" }` blocks are required on system prompts for the Claude API to cache them — workspace-level isolation does not remove this requirement. This incorrect amendment must not be applied when `runner.py` is written.

- **[HIGH] Six unacted plan amendments accumulating.** The following amendments have been validated across research reports (April 1–4) and must be applied before coding begins:

  | Gap | Plan State | Correct Action |
  |-----|-----------|----------------|
  | Agent output validation | Ad-hoc JSON in `schemas.py` | Use Pydantic + Claude Structured Outputs (GA Jan 2026) |
  | Cold-start cost | Live LLM calls, ~$30–50 one-time | Use Batch API + prompt caching; target ~$2–5 one-time |
  | `highPrecision` flag | Not in `HexMap.tsx` task | Add `highPrecision: false` (or `'auto'`) to all `H3HexagonLayer` instances |
  | Prompt caching | Incorrect amendment to remove headers | **Keep explicit `cache_control: { type: "ephemeral" }` on system prompts in `runner.py`** |
  | R-tree spatial index | Not in `schema.py` DDL | Add `CREATE INDEX cell_rtree ON world_state_delta (cell_id) USING RTREE` |
  | AIS integration | Not in plan | Add AIS ingestion task (week 2–3); use free aishub.net initially |

### Medium

- **[MEDIUM] `pytest.ini` duplication.** The plan specifies both `[tool.pytest.ini_options]` in `pyproject.toml` and a standalone `pytest.ini`. `pytest.ini` takes precedence and will silently shadow the `pyproject.toml` config. Use `pyproject.toml` only; drop standalone `pytest.ini` from the plan. Day 6 carry-forward.

- **[MEDIUM] DuckDB H3 community extension version not pinned.** The spec (Section 1) explicitly requires pinning the H3 community extension version in deployment config. No deployment config exists yet, but this must be addressed on first deploy. Day 6 carry-forward.

- **[MEDIUM] No cold-start bootstrap task in implementation plan.** Spec Section 11 describes the one-time batch bootstrap job (~$2–5 with Batch API, per the April 3–4 research). The plan has no tracked task for it. Without it, first deploy has no world state and the demo is non-functional.

- **[MEDIUM] `deck.gl` version unspecified.** The `frontend/package.json` task specifies no version floor for `deck.gl`. Must pin to `>=8.8` for `Tileset2D`, `useWidget`, and confirmed `highPrecision` auto-switching support.

- **[MEDIUM] Research backlog now 5 reports deep.** Five tech research reports (March 31, April 1–4) have produced 30+ findings and 6 actionable plan amendments. Without code to test findings against, the backlog compounds and risks contradictions (the April 2 cache-header error is already an example). No additional research reports are useful until Task 1–2 are implemented.

### Low

- **[LOW] R-tree spatial index absent from DDL plan.** `CREATE INDEX ... USING RTREE` on `world_state_delta.cell_id` provides ~58x speedup for H3 proximity queries per April 3 research. Not currently in the `schema.py` DDL task.

- **[LOW] DuckDB query caching not in API plan.** A `@cache_with_ttl(60s)` decorator on indicator card endpoints would reduce backend load ~20–30% at near-zero cost. Not in the `api/routes.py` task.

- **[LOW] `RESEARCH.md` at repo root is unreferenced.** Not linked from spec or plan. Should be moved to `docs/` or explicitly linked. Day 6 carry-forward.

- **[LOW] `react-window` virtualization absent from agent feed task.** 50 agents × 5 decisions/hour = ~250 entries/day in `AgentFeed.tsx`. Without virtualization, this degrades during active crisis periods.

- **[LOW] Promptfoo not in eval plan.** April 3 research recommends Promptfoo for automated A/B prompt testing. Current plan relies solely on manual admin dashboard review.

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

**Planned version floors (from Task 1 of the implementation plan):**

| Package | Floor | Notes |
|---------|-------|-------|
| `fastapi` | >=0.115 | Acceptable — current latest 0.115.x |
| `uvicorn[standard]` | >=0.34 | Acceptable |
| `duckdb` | >=1.2 | Acceptable; H3 community extension last updated 2026-03-25 |
| `h3` | >=4.1 | Acceptable; H3-py v4.4.2 released Jan 2026 |
| `anthropic` | >=0.52 | Acceptable; Structured Outputs GA Jan 2026; Batch API GA |
| `pydantic` | >=2.10 | Stable |
| `sentence-transformers` | >=3.4 | Acceptable; all-MiniLM-L6-v2 confirmed optimal |
| `deck.gl` | **unspecified** | **Must pin to >=8.8** |

No CVE audit possible until manifests exist.

---

## Test Coverage

**0 / 18 planned test files — all missing.** Day 6, no change from Days 1–5.

---

## Recommendations

1. **Start Task 1 today (Day 6 — critical).** Create `backend/pyproject.toml`, `backend/src/parallax/db/schema.py`, and `backend/tests/conftest.py`. The DuckDB schema is the critical-path blocker for everything else. The plan provides exact code — there is no ambiguity about what to write.

2. **Add `.gitignore` as the very first file in Task 1.** Include `.DS_Store`, `__pycache__/`, `*.pyc`, `.venv/`, `node_modules/`, `.env`, `*.duckdb`, `*.db`. Run `git rm --cached docs/.DS_Store docs/superpowers/.DS_Store` to stop tracking existing junk files.

3. **Apply the 6 validated plan amendments before writing code.** Particularly the prompt-caching correction (keep `cache_control` headers), R-tree index addition to `schema.py`, and Structured Outputs in `schemas.py`. Doing this after code is written creates rework.

4. **Fix GitHub Actions permissions now.** Add `pull-requests: write` and `issues: write` to both workflow files (`claude.yml` and `claude-code-review.yml`). This is a 4-line total change across 2 files and has been open for 6 days.

5. **Halt tech research.** The research backlog (30+ findings, 6 amendments) is already sufficient to guide implementation through Task 6+. The next research report should wait until Task 2–3 is complete so findings can be validated against real code behavior. Continued research without implementation deepens the contradiction risk (see the April 2 cache-header error).

6. **Track the 30-day eval window explicitly.** The window to demonstrate calibration accuracy started March 30 and ends approximately April 29. With zero implementation on Day 6, the window to collect meaningful real-world predictions is shrinking. Add a milestone marker to the implementation plan tracking expected live-data start date.

---

*No tech research report today — research backlog is sufficient. Research resumes when Task 2 (single-writer DB layer) is committed.*
