# Parallax Health Check — 2026-10-31

**Status: YELLOW**

No code commits since 2026-10-30. The two persistent MEDIUM/LOW carry-over issues from previous reports remain unresolved — DuckDB single-writer violations in live-path modules (Day 6) and missing `streamlit`/`plotly` in `pyproject.toml`. The daily tech research scout commit (ca3fb2f) is the only change since yesterday's report; no regressions introduced.

---

## Summary

The project is architecturally stable. The prediction-market signal pipeline (3 models → Kalshi/Polymarket comparison → divergence detection → paper trades) is coherent and well-tested. The Phase 1 design spec described a 50-agent LLM swarm with H3 spatial simulation; the codebase has productively pivoted to a focused prediction-market edge-finder, well-documented in CLAUDE.md. The original spec's `agents/`, `spatial/`, and `eval/` modules are absent but intentionally replaced by the current `prediction/`, `scoring/`, `contracts/`, and `divergence/` architecture.

The only actionable issues are the persistent MEDIUM concurrency risk in live-path write code and three LOW housekeeping items.

---

## Spec / Plan vs. Implementation

### Architecture Pivot (by design, not a defect)
The original Phase 1 spec (`2026-03-30-parallax-phase1-design.md`) described a ~50-agent LLM swarm with H3 hexagonal spatial visualization and a BigQuery-based GDELT pipeline. The implemented codebase is a focused prediction-market edge-finder as documented in CLAUDE.md. This pivot is intentional and coherent.

**Spec modules absent from codebase (replaced by equivalent):**
- `agents/` (registry, runner, router, country_agent) → replaced by `prediction/` (3 focused predictors)
- `spatial/` (h3_utils, loader) → H3 visualization deferred
- `ingestion/gdelt.py` (BigQuery) → replaced by `ingestion/gdelt_doc.py` (REST API, lower friction)
- `ingestion/dedup.py` (sentence-transformers) → not implemented; `sentence-transformers` not in deps
- `eval/` (scoring, prompt_versioning, improvement) → replaced by `scoring/` module suite

**Modules present in codebase beyond spec (all productive additions):**
- `backtest/` — look-ahead guard + replay engine
- `bench/` — Kalshi calibration benchmarking harness
- `contracts/` — contract registry with proxy-class signal mapping
- `divergence/` — model-vs-market divergence detector
- `markets/` — Kalshi + Polymarket clients
- `portfolio/` — quarter-Kelly position sizing + portfolio simulator
- `scoring/` — full ledger, tracker, calibration, recalibration, scorecard, report card

---

## Issues Found

### MEDIUM Severity — Carry-Over (Day 6)

- **[BUG] DuckDB single-writer violations in live-path modules**
  Six modules write to DuckDB directly via `conn.execute()` / `_conn.execute()` outside the `asyncio.Queue → DbWriter` pattern mandated by the spec. Under concurrent FastAPI requests (e.g. `/api/brief/run` + `/api/scorecard` hitting simultaneously), these paths contend and can raise `database is locked` non-deterministically.

  Confirmed violators in live pipeline:
  - `scoring/ledger.py` — signal persistence
  - `scoring/prediction_log.py` — prediction persistence
  - `scoring/resolution.py` — settlement write-back
  - `scoring/tracker.py` — trade lifecycle (4 write sites)
  - `ops/alerts.py:106` — **highest risk; executed on every alert dispatch**
  - `budget/tracker.py:43` — LLM cost persistence

  Lower-risk (offline/batch context — acceptable as-is):
  - `backtest/runner.py`, `backtest/look_ahead_guard.py`
  - `scoring/scorecard.py`, `scoring/track_record.py`, `scoring/report_card.py`
  - `scoring/calibration.py`, `scoring/recalibration.py`

  **Fix:** Route all live-path writes through `DbWriter.enqueue()`. The `DbWriter` class in `db/writer.py` is correctly implemented — it just needs to be wired in to the five violating live-path modules.

### LOW Severity — Carry-Over

- **[DEP] `streamlit` and `plotly` missing from `pyproject.toml`**
  `dashboard/app.py:16–17` imports both at module level. Neither appears in any dependency group. A fresh `pip install -e "."` will raise `ModuleNotFoundError` for any path touching `dashboard/app.py`.
  **Fix:** Add `dashboard = ["streamlit>=1.36", "plotly>=5.22"]` to `[project.optional-dependencies]`.

- **[CONFIG] `requires-python = ">=3.11"` vs Python 3.12 target**
  CLAUDE.md specifies Python 3.12+; the runtime is 3.12. No functional impact but misleading.
  **Fix:** Change to `requires-python = ">=3.12"` in `pyproject.toml:4`.

- **[SMELL] 13 permanently skipped tests**
  6 from `test_mapping_policy.py` (pre-refactor stubs) plus others. Erodes coverage signal without CI alerts.
  **Fix:** Remove stubs or convert to `pytest.mark.xfail` with a reason string.

---

## Dependency Audit

| Dependency | Status | Notes |
|---|---|---|
| `fastapi>=0.115` | OK | |
| `uvicorn[standard]>=0.34` | OK | |
| `duckdb>=1.2` | OK | v1.4 available (see tech research 2026-10-31) — upgrade is optional |
| `anthropic>=0.52` | OK | |
| `pydantic>=2.10` | OK | |
| `httpx>=0.28` | OK | |
| `scikit-learn>=1.3` | OK | Fixed 2026-10-29 |
| `numpy>=1.26` | OK | Fixed 2026-10-29 |
| `h3`, `searoute`, `shapely` | Not in deps | Not used in current codebase (pivot); no action needed |
| `sentence-transformers` | Not in deps | Not used; semantic dedup not implemented |
| `google-cloud-bigquery` | Not in deps | GDELT uses REST API now; no action needed |
| `websockets` | Not in deps | WebSocket not used; HTTP polling in frontend |
| `streamlit`, `plotly` | **Missing** | Used in `dashboard/app.py`; not in any dep group |

---

## Test Coverage vs. Plan

Plan-specified tests that exist: `test_schema.py`, `test_writer.py`, `test_config.py`, `test_cascade.py`, `test_world_state.py`, `test_gdelt_filter.py` (via `test_gdelt_doc.py`).

Plan-specified tests absent (due to architecture pivot — acceptable):
`test_h3_utils.py`, `test_dedup.py`, `test_agent_schemas.py`, `test_agent_router.py`, `test_agent_runner.py`, `test_auth.py`, `test_prompt_versioning.py`, `test_integration.py`

Additional tests beyond the plan (good coverage of pivoted architecture):
`test_brief.py`, `test_calibration.py`, `test_contracts_schemas.py`, `test_crisis_context.py`, `test_divergence.py`, `test_ensemble.py`, `test_ledger.py`, `test_mapping_policy.py`, `test_portfolio.py`, `test_scorecard.py`, `test_simulator.py`, `test_backtest_look_ahead.py`, and ~20 more.

---

## Recommendations

1. **(MEDIUM — highest priority)** Wire `DbWriter.enqueue()` into `ops/alerts.py`, `scoring/ledger.py`, `scoring/prediction_log.py`, `scoring/resolution.py`, `scoring/tracker.py`, and `budget/tracker.py`. This is the only live-risk bug; the fix pattern is clear.
2. **(LOW)** Add `streamlit` + `plotly` to `pyproject.toml` optional deps.
3. **(LOW)** Change `requires-python = ">=3.12"`.
4. **(LOW)** Clean up 13 skipped tests.
