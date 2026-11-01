# Parallax Health Check — 2026-11-01

**Status: YELLOW**

No code commits since 2026-10-31. All three carry-over issues from previous reports remain unresolved — DuckDB single-writer violations in live-path modules (MEDIUM, Day 7) and two LOW housekeeping items. The two most recent commits are docs-only (health check + tech research reports); no regressions introduced.

---

## Summary

The project is architecturally stable and unchanged from yesterday. The prediction-market signal pipeline (3 models → Kalshi/Polymarket comparison → divergence detection → paper trades) is coherent and well-tested. All issues flagged since 2026-10-26 remain open with no fix activity. The MEDIUM concurrency bug in `ops/alerts.py` and live-path scoring modules is the sole actionable risk.

---

## Spec / Plan vs. Implementation

No changes since 2026-10-31 report. Architecture pivot from 50-agent LLM swarm to focused prediction-market edge-finder is intentional and coherent (documented in CLAUDE.md). Absent spec modules (`agents/`, `spatial/`, `eval/`) are superseded by `prediction/`, `scoring/`, `contracts/`, `divergence/`, and `portfolio/` — all productive additions.

---

## Issues Found

### MEDIUM Severity — Carry-Over (Day 7)

- **[BUG] DuckDB single-writer violations in live-path modules**
  Six modules write to DuckDB directly via `conn.execute()` / `_conn.execute()` outside the `asyncio.Queue → DbWriter` pattern. Under concurrent FastAPI requests, these paths can raise `database is locked` non-deterministically.

  Confirmed violators (verified unchanged today):
  - `ops/alerts.py:106` — **highest risk; executes on every alert dispatch**
  - `scoring/ledger.py:225,256,271,294,305,318`
  - `scoring/prediction_log.py:79`
  - `budget/tracker.py:43`
  - `scoring/tracker.py`, `scoring/resolution.py` (confirmed in prior reports)

  **Fix:** Route all live-path writes through `DbWriter.enqueue()`. The `DbWriter` class in `db/writer.py` is correctly implemented; it just needs wiring into the five live-path modules.

### LOW Severity — Carry-Over

- **[DEP] `streamlit` and `plotly` missing from `pyproject.toml`**
  `dashboard/app.py:16–17` imports both at module level. Neither appears in any dependency group. A fresh `pip install -e "."` will raise `ModuleNotFoundError`.
  **Fix:** Add `dashboard = ["streamlit>=1.36", "plotly>=5.22"]` to `[project.optional-dependencies]` in `pyproject.toml`.

- **[CONFIG] `requires-python = ">=3.11"` vs Python 3.12 target**
  `pyproject.toml:4` specifies `>=3.11`; CLAUDE.md and runtime specify Python 3.12+. No functional impact but misleading.
  **Fix:** Change to `requires-python = ">=3.12"`.

- **[SMELL] 7 permanently skipped tests in `test_mapping_policy.py`**
  All marked `_PRE_REFACTOR_REASON` — stubs from before the contract mapping refactor. Erodes coverage signal.
  **Fix:** Remove stubs or convert to `pytest.mark.xfail` with a reason string.

---

## Dependency Audit

No dependency changes since 2026-10-31 report.

| Dependency | Status | Notes |
|---|---|---|
| `fastapi>=0.115` | OK | |
| `uvicorn[standard]>=0.34` | OK | |
| `duckdb>=1.2` | OK | v1.4 available (2026-10-31 tech research) — upgrade optional |
| `anthropic>=0.52` | OK | |
| `pydantic>=2.10` | OK | |
| `httpx>=0.28` | OK | |
| `scikit-learn>=1.3` | OK | Fixed 2026-10-29 |
| `numpy>=1.26` | OK | Fixed 2026-10-29 |
| `streamlit`, `plotly` | **Missing** | Used in `dashboard/app.py`; not in any dep group |

---

## Test Coverage vs. Plan

No new tests added since 2026-10-31. Coverage posture unchanged — plan-specified tests exist; architecture-pivot tests (H3, dedup, agent routing) absent by design. 7 skipped stubs in `test_mapping_policy.py` remain.

---

## Recommendations

1. **(MEDIUM — highest priority)** Wire `DbWriter.enqueue()` into `ops/alerts.py`, `scoring/ledger.py`, `scoring/prediction_log.py`, `scoring/resolution.py`, `scoring/tracker.py`, and `budget/tracker.py`. This is a live concurrency risk; the fix pattern is clear.
2. **(LOW)** Add `streamlit` + `plotly` to `pyproject.toml` optional deps.
3. **(LOW)** Change `requires-python = ">=3.12"` in `pyproject.toml:4`.
4. **(LOW)** Remove or convert 7 skipped stubs in `test_mapping_policy.py`.
