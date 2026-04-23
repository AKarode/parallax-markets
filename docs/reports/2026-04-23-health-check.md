# Parallax Health Check — 2026-04-23

**Status: YELLOW**

Zero code commits since April 22. All P0/P1/P2 items from the previous report remain unaddressed. One new finding this cycle: `backtest/engine.py` is an undocumented module with no tests that references two data files that do not exist in the repo, making it dead code at runtime. All prior test failures (26) persist.

---

## Since Last Check (2026-04-22)

**Zero code commits since April 22.** Only commit since then is the April 22 health-check document itself.

- The 2-week ceasefire validation window (April 7–21) closed 2 days ago with no resolution data committed.
- All P0/P1/P2 items from April 22 carry forward unchanged.
- **New this cycle:** `backtest/engine.py` identified as undocumented, untested, and broken at runtime.

---

## Spec / Plan Consistency

Unchanged from April 22. The original spec (`2026-03-30-parallax-phase1-design.md`) describes a 50-agent geopolitical simulator with H3 spatial visualization and WebSocket frontend. The actual codebase is a 3-model prediction market edge-finder. The pivot is deliberate and described in CLAUDE.md, but the spec/plan docs remain stale and misleading.

- **[HIGH]** Spec and plan files describe a product that no longer exists. Missing modules from spec: `agents/`, `spatial/`, `api/`, `eval/`. Frontend is missing deck.gl, MapLibre GL, h3-js, WebSocket hooks.
- **[MEDIUM]** All plan checkboxes remain unchecked; the plan can no longer serve as a progress tracker.
- **[LOW]** CLAUDE.md module map is incomplete: `backtest/engine.py` and `scoring/track_record.py` exist in the codebase but are not listed.

---

## Dependency Audit

### Backend (`pyproject.toml`)

| Issue | Severity | Status |
|-------|----------|--------|
| **`pytz` not listed** — DuckDB raises `InvalidInputException` on `TIMESTAMPTZ` queries without it; blocks 11 tests | **HIGH** | Carry-forward (P0) |
| `requires-python = ">=3.11"` — CLAUDE.md and runtime use Python 3.12 | LOW | Carry-forward |
| `h3>=4.1`, `websockets>=14.0` in CLAUDE.md "Key Dependencies" but absent from `pyproject.toml` | MEDIUM | Carry-forward |
| `truthbrush>=0.2` — no upper-bound pin, low-maintenance library | LOW | Carry-forward |
| `anthropic>=0.52` — no upper bound; SDK breaking-changes risk | LOW | Carry-forward |

### Frontend (`package.json`)

React 18 + Recharts + Vite only. No CVE concerns. No changes since April 22.

---

## Test Coverage — 26 Failures (Unchanged)

**Total: 26 failed, 341 passed** (7% failure rate). No fixes landed since April 22.

### Root Cause 1: Missing `pytz` dependency — 11 failures

`test_scorecard.py` (10) and `test_ops_events.py` (1) crash with:
```
InvalidInputException: Required module 'pytz' failed to import
ModuleNotFoundError: No module named 'pytz'
```
Fix: add `pytz` to `pyproject.toml` dependencies.

### Root Cause 2: Stale `test_mapping_policy` assertions — 11 failures

Tests assert `effective_edge == raw_edge` (old behavior). Implementation now subtracts 2% transaction costs, so `effective_edge = raw_edge - 0.02`. Tests need updated expected values — the implementation is correct.

### Root Cause 3: `test_recalibration` seeding bug — 4 failures

Tests expect recalibration to fire but seed fewer than 10 resolved signals, below the `min_signals` threshold. Fix: insert ≥ 10 resolved rows in the fixture.

### Coverage Gaps

The following modules have no test file:

| Module | Risk |
|--------|------|
| `backtest/engine.py` | HIGH — untested and references missing data files |
| `ops/runtime.py` | MEDIUM |
| `config/risk.py` | LOW |
| `portfolio/schemas.py` | LOW |

---

## Code Quality Issues

### NEW — `backtest/engine.py` Is Broken Dead Code — **HIGH**

`backend/src/parallax/backtest/engine.py` is an undocumented module not listed in CLAUDE.md's module map and has no test file. It references two files that do not exist in the repo:

- `DATA_DIR / "backtest_prices.json"` — does not exist
- `Path(__file__).resolve().parent / "timeline.json"` — does not exist

The engine cannot run at all without these files. It is also not reachable from any CLI or API entrypoint. This module is dead code and a maintenance hazard.

### DuckDB Single-Writer Violations — **HIGH** (unresolved, P1)

`DbWriter` asyncio queue exists but is **not wired into any callsite**. The following modules write directly to DuckDB, bypassing the queue:

| Module | Violating Operations |
|--------|---------------------|
| `scoring/ledger.py` | INSERT to `signal_ledger`; UPDATE execution fields |
| `scoring/prediction_log.py` | INSERT to `prediction_log` |
| `scoring/tracker.py` | INSERT to `trade_orders`, `trade_fills`; UPDATE `trade_positions` |
| `scoring/resolution.py` | UPDATE `signal_ledger`; UPDATE `trade_positions` |
| `scoring/scorecard.py` | INSERT…ON CONFLICT to `daily_scorecard` |
| `contracts/registry.py` | INSERT OR REPLACE; DELETE; UPDATE |
| `cli/brief.py` | INSERT/UPDATE to `runs`, `market_prices` |
| `budget/tracker.py` | INSERT to `llm_usage` |
| `ops/alerts.py` | INSERT to `ops_events` |

Safe only because the CLI is single-threaded. Will cause `database is locked` errors if `/api/brief/run` is called concurrently with any other write path.

### Ensemble Budget Tracking Bug — **MEDIUM** (unresolved, P1)

`prediction/ensemble.py:122` hardcodes `"opus"` as the model tier in every `budget.record()` call regardless of which model is actually invoked. Sonnet calls are logged at Opus pricing, inflating reported LLM spend. The commit `ca52a42` switched ensemble back to Opus, so calls are now correctly Opus — but the hardcoded string is still a fragility: any future model change will silently mis-report.

### Ensemble Missing System Prompt / Prompt Caching — **MEDIUM** (unresolved, P2)

`ensemble_predict()` passes no `system=` argument to `client.messages.create()`. Prompt caching is not in use. Per-call cost is ~3× higher than the spec's estimate.

### No Transaction Wrapping in Scorecard — **MEDIUM** (unresolved, P2)

`compute_daily_scorecard()` calls `_upsert_metric()` in a loop with no transaction boundary. A mid-loop crash leaves partial metrics in `daily_scorecard`.

### No Idempotency Guard in Signal Ledger — **MEDIUM** (unresolved, P2)

Running `parallax-brief` twice in the same session appends duplicate rows to `signal_ledger` and `prediction_log`. No `UNIQUE(run_id, model_id)` constraint exists on either table.

---

## Architecture Drift

Unchanged from April 22. The pivot from spec to prediction market edge-finder is intentional. No new structural drift introduced this cycle.

`scoring/track_record.py` exists and is tested (`test_track_record.py`) but is absent from CLAUDE.md's module map — minor documentation gap only.

---

## Recommendations

Priority order (all carry-forward from April 22 unless marked NEW):

1. **[P0 — OPEN] Fix `pytz` missing dependency.** Add `pytz` to `pyproject.toml`. Unblocks 11 test failures. One-line fix.

2. **[P0 — OPEN] Fix `test_mapping_policy` stale assertions.** Update 11 test expected values to account for the 2% transaction cost deduction. Implementation is correct; tests are stale.

3. **[P0 — OPEN] Fix `test_recalibration` seeding bug.** Insert ≥ 10 resolved signal rows in the fixture before calling `recalibrate_probability()`.

4. **[P1 — OPEN, NEW] Remove or fix `backtest/engine.py`.** Either create `data/backtest_prices.json` + `backtest/timeline.json` and add a test, or delete the module. It is unreachable, untested, and references missing files.

5. **[P1 — OPEN] Wire `DbWriter` into the pipeline.** Refactor `SignalLedger`, `PredictionLogger`, `PaperTradeTracker`, `ContractRegistry`, `AlertDispatcher`, `BudgetTracker`, and `scorecard.py` to use `DbWriter.enqueue()`. Highest-risk issue for production stability under concurrent load.

6. **[P1 — OPEN] Fix ensemble budget model tier.** Change hardcoded `"opus"` in `ensemble.py:122` to a parameter so future model changes report correctly.

7. **[P2 — OPEN] Add `system=` param to ensemble calls.** Enables prompt caching, reduces per-call cost ~90% on repeated calls.

8. **[P2 — OPEN] Wrap scorecard writes in a transaction.** Add `BEGIN`/`COMMIT` around the `_upsert_metric()` loop in `compute_daily_scorecard()`.

9. **[P2 — OPEN] Add idempotency guard.** Add `UNIQUE(run_id, model_id)` to `prediction_log` or a pre-insert existence check to `signal_ledger`.

10. **[P3 — OPEN] Archive stale spec/plan docs.** Add deprecation headers pointing to CLAUDE.md as authoritative. Update CLAUDE.md module map to include `backtest/engine.py` and `scoring/track_record.py`. Update `requires-python` to `>=3.12`.
