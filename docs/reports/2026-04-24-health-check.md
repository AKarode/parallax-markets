# Parallax Health Check — 2026-04-24

**Status: YELLOW**

Zero code commits since April 23. All 26 test failures are unchanged. Two new findings this cycle: (1) unpinned dependencies auto-upgraded to major/significant versions (`anthropic` 0.97.0, `starlette` 1.0.0, `duckdb` 1.5.2, `websockets` 16.0) with no test regressions yet but latent breakage risk; (2) model IDs throughout the codebase use the deprecated date-based format `claude-opus-4-20250514` rather than the current `claude-opus-4-7` format, creating a future deprecation risk. The April 7–21 ceasefire validation window closed 3 days ago with no resolution data committed.

---

## Since Last Check (2026-04-23)

**Zero code commits since April 23.** The only commit since then is the April 23 health-check document itself.

- All P0/P1/P2 items from April 23 carry forward unchanged.
- **New this cycle:** Unpinned dependencies silently upgraded to major new versions (see Dependency Audit below).
- **New this cycle:** Model IDs in prediction code use deprecated date-based format.
- The ceasefire validation window (April 7–21) has been closed for 3 days. No settlement/resolution data committed.

---

## Spec / Plan Consistency

Unchanged from April 23. The original spec (`2026-03-30-parallax-phase1-design.md`) describes a 50-agent geopolitical simulator with H3 spatial visualization and WebSocket frontend. The actual codebase is a 3-model prediction market edge-finder. The pivot is deliberate and described in CLAUDE.md, but the spec/plan docs remain stale and misleading.

- **[HIGH]** Spec and plan describe a product that no longer exists. Missing modules from spec: `agents/`, `spatial/`, `api/`, `eval/`. Frontend missing deck.gl, MapLibre GL, h3-js, WebSocket hooks.
- **[MEDIUM]** All plan checkboxes remain unchecked; the plan can no longer serve as a progress tracker.
- **[LOW]** CLAUDE.md module map is incomplete: `backtest/engine.py` and `scoring/track_record.py` are not listed.

---

## Dependency Audit

### Backend (`pyproject.toml`)

| Issue | Severity | Status |
|-------|----------|--------|
| **`pytz` not listed** — DuckDB raises `InvalidInputException` on `DATE(TIMESTAMPTZ)` queries; blocks 11 tests | **HIGH** | Carry-forward (P0) |
| **`anthropic` auto-upgraded to 0.97.0** — no upper-bound pin; jumped from >=0.52 baseline; tests pass but API surface has changed significantly | **MEDIUM** | NEW |
| **`starlette` auto-upgraded to 1.0.0** — major version bump from 0.x.x; no test regressions yet | **MEDIUM** | NEW |
| **`duckdb` auto-upgraded to 1.5.2** — no upper-bound pin; pytz issue unchanged across versions | **LOW** | NEW |
| **`websockets` auto-upgraded to 16.0** — no upper-bound pin; no tests cover WS | **LOW** | NEW |
| `requires-python = ">=3.11"` — CLAUDE.md and runtime use Python 3.12 | LOW | Carry-forward |
| `h3>=4.1` in CLAUDE.md "Key Dependencies" but absent from `pyproject.toml` | MEDIUM | Carry-forward |
| `truthbrush>=0.2` — no upper-bound pin, low-maintenance library | LOW | Carry-forward |

**Installed versions (as of this check):**
```
anthropic   0.97.0   (pin spec: >=0.52, no upper bound)
duckdb      1.5.2    (pin spec: >=1.2,  no upper bound)
fastapi     0.136.1  (pin spec: >=0.115, no upper bound)
starlette   1.0.0    (indirect; major version bump)
websockets  16.0     (indirect via uvicorn; no pin)
```

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
Triggered by `DATE(TIMESTAMPTZ)` queries in `scorecard.py:328`. DuckDB 1.5.2 still requires pytz for timezone-aware date extraction even though basic `TIMESTAMPTZ` creation now works without it.

Fix: add `pytz` to `pyproject.toml` dependencies.

### Root Cause 2: Stale `test_mapping_policy` assertions — 11 failures

Tests assert `effective_edge == raw_edge` (old behavior). Implementation now subtracts 2% transaction costs, so `effective_edge = raw_edge - 0.02`. Tests also assert `confidence_discount` values of 0.6/0.3 for near/loose proxies that are now 1.0 in the implementation. Implementation is correct; tests are stale.

### Root Cause 3: `test_recalibration` seeding bug — 4 failures

Tests expect recalibration to fire but seed fewer than 10 resolved signals, below the `min_signals` threshold.

Fix: insert ≥ 10 resolved rows in the fixture before calling `recalibrate_probability()`.

### Coverage Gaps

| Module | Risk |
|--------|------|
| `backtest/engine.py` | HIGH — untested, references missing data files, unreachable from any entrypoint |
| `ops/runtime.py` | MEDIUM |
| `config/risk.py` | LOW |
| `portfolio/schemas.py` | LOW |

---

## Code Quality Issues

### NEW — Model IDs Use Deprecated Date-Based Format — **MEDIUM**

All three prediction models hardcode `model="claude-opus-4-20250514"` (the original Claude Opus 4 release from May 2025). The current model ID format per CLAUDE.md is `claude-opus-4-7`. The old date-based format may be deprecated by Anthropic and would cause `invalid_model` API errors silently at runtime. No unit test covers model ID validity.

Affected files:
- `prediction/oil_price.py:133`
- `prediction/ceasefire.py:106`
- `prediction/hormuz.py:108`
- `prediction/ensemble.py:86` (docstring only)

Fix: update all four to `"claude-opus-4-7"`.

### `backtest/engine.py` Is Broken Dead Code — **HIGH** (carry-forward, P1)

No change from April 23. References `data/backtest_prices.json` and `backtest/timeline.json`, neither of which exists. Not reachable from any CLI or API entrypoint. No tests. Not listed in CLAUDE.md module map.

### DuckDB Single-Writer Violations — **HIGH** (carry-forward, P1)

`DbWriter` asyncio queue exists but is not wired into any callsite. The following modules write directly to DuckDB, bypassing the queue:

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

Safe only because the CLI is single-threaded today. Will cause `database is locked` errors if `/api/brief/run` is called concurrently with any other write path.

### Ensemble Budget Tracking Bug — **MEDIUM** (carry-forward, P1)

`prediction/ensemble.py:122` hardcodes `"opus"` as the model tier in every `budget.record()` call. Any future model change will silently mis-report cost.

### Ensemble Missing System Prompt / Prompt Caching — **MEDIUM** (carry-forward, P2)

`ensemble_predict()` passes no `system=` argument to `client.messages.create()`. Prompt caching is not in use. Per-call cost is ~3× higher than the spec's estimate.

### No Transaction Wrapping in Scorecard — **MEDIUM** (carry-forward, P2)

`compute_daily_scorecard()` calls `_upsert_metric()` in a loop with no transaction boundary. A mid-loop crash leaves partial metrics in `daily_scorecard`.

### No Idempotency Guard in Signal Ledger — **MEDIUM** (carry-forward, P2)

Running `parallax-brief` twice in the same session appends duplicate rows to `signal_ledger` and `prediction_log`. No `UNIQUE(run_id, model_id)` constraint on either table.

---

## Architecture Drift

Unchanged from April 23. The pivot from spec to prediction market edge-finder is intentional. No new structural drift introduced this cycle.

`scoring/track_record.py` exists and is tested (`test_track_record.py`) but is absent from CLAUDE.md's module map — minor documentation gap only.

---

## Recommendations

Priority order:

1. **[P0 — OPEN] Fix `pytz` missing dependency.** Add `pytz` to `pyproject.toml`. Unblocks 11 test failures. One-line fix.

2. **[P0 — OPEN] Fix `test_mapping_policy` stale assertions.** Update 11 test expected values to account for the 2% transaction cost deduction and current confidence_discount values. Implementation is correct; tests are stale.

3. **[P0 — OPEN] Fix `test_recalibration` seeding bug.** Insert ≥ 10 resolved signal rows in the fixture before calling `recalibrate_probability()`.

4. **[P1 — OPEN, NEW] Update model IDs from `claude-opus-4-20250514` to `claude-opus-4-7`.** Four occurrences in `prediction/`. Old date-based format is at risk of deprecation and causes silent runtime failures.

5. **[P1 — OPEN] Remove or fix `backtest/engine.py`.** Either create the two missing data files and add tests, or delete the module. It is unreachable, untested, and references missing files.

6. **[P1 — OPEN] Pin dependency upper bounds.** Add upper-bound pins for `anthropic`, `duckdb`, `starlette`/`fastapi` in `pyproject.toml` to prevent silent breaking upgrades. At minimum: `anthropic>=0.52,<2`, `duckdb>=1.2,<2`, `fastapi>=0.115,<1`.

7. **[P1 — OPEN] Wire `DbWriter` into the pipeline.** Refactor `SignalLedger`, `PredictionLogger`, `PaperTradeTracker`, `ContractRegistry`, `AlertDispatcher`, `BudgetTracker`, and `scorecard.py` to use `DbWriter.enqueue()`. Highest-risk issue for production stability under concurrent load.

8. **[P1 — OPEN] Fix ensemble budget model tier.** Change hardcoded `"opus"` in `ensemble.py:122` to a parameter so future model changes report correctly.

9. **[P2 — OPEN] Add `system=` param to ensemble calls.** Enables prompt caching, reduces per-call cost ~90% on repeated calls.

10. **[P2 — OPEN] Wrap scorecard writes in a transaction.** Add `BEGIN`/`COMMIT` around the `_upsert_metric()` loop in `compute_daily_scorecard()`.

11. **[P2 — OPEN] Add idempotency guard.** Add `UNIQUE(run_id, model_id)` to `prediction_log` or a pre-insert existence check to `signal_ledger`.

12. **[P3 — OPEN] Archive stale spec/plan docs.** Add deprecation headers pointing to CLAUDE.md as authoritative. Update CLAUDE.md module map to include `backtest/engine.py` and `scoring/track_record.py`. Update `requires-python` to `>=3.12`.
