# Parallax Health Check — 2026-04-22

**Status: YELLOW**

The system remains functional for its actual purpose (prediction market edge-finder), but **26 test failures** surfaced this cycle that were not previously tracked — including a missing `pytz` runtime dependency that breaks all scorecard and ops-event tests. All P0/P1 items from the April 21 report remain unaddressed; no code commits have landed since April 21.

---

## Since Last Check (2026-04-21)

**Zero code commits since April 21.** Only commit since then is the April 21 health-check document itself.

- The 2-week ceasefire validation window (April 7–21) has now closed with no resolution data or scorecard run results committed to the repo.
- All P0/P1 items from April 21 carry forward.
- **New this cycle:** quantified test failure count and identified two new root causes not previously reported.

---

## Spec / Plan Consistency

Unchanged from April 21. The original spec (`2026-03-30-parallax-phase1-design.md`) describes a 50-agent geopolitical simulator with H3 spatial visualization and WebSocket frontend. The actual codebase is a 3-model prediction market edge-finder. The pivot is deliberate and described in CLAUDE.md, but the spec/plan docs remain stale.

- **[HIGH]** Spec and plan files describe a product that no longer exists. Missing modules from spec: `agents/`, `spatial/`, `api/`, `eval/`. Frontend is missing deck.gl, MapLibre GL, h3-js, WebSocket hooks — none of which are planned for the current direction.
- **[MEDIUM]** All plan checkboxes remain unchecked; plan can no longer serve as a progress tracker.

---

## Dependency Audit

### Backend (`pyproject.toml`)

| Issue | Severity | Status |
|-------|----------|--------|
| **`pytz` not listed as a dependency** — DuckDB raises `InvalidInputException` when querying `TIMESTAMPTZ` columns without `pytz` installed; blocks 11 tests | **HIGH** | **NEW** |
| `requires-python = ">=3.11"` — CLAUDE.md and runtime are Python 3.12 | LOW | Carry-forward |
| `h3>=4.1`, `websockets>=14.0` listed in CLAUDE.md "Key Dependencies" but absent from `pyproject.toml` | MEDIUM | Carry-forward |
| `truthbrush>=0.2` — no upper-bound pin, low-maintenance library | LOW | Carry-forward |
| `anthropic>=0.52` — no upper bound; SDK breaking-changes risk | LOW | Carry-forward |

### Frontend (`package.json`)

React 18 + Recharts + Vite. No CVE concerns. No changes since April 21.

---

## Test Coverage — **26 Failures (NEW)**

**Total: 26 failed, 341 passed** (7% failure rate). All failures existed before April 22 but were not previously counted or categorized.

### Root Cause 1: Missing `pytz` dependency — 11 failures

`test_scorecard.py` (10 failures) and `test_ops_events.py` (1 failure) all crash with:

```
_duckdb.InvalidInputException: Required module 'pytz' failed to import
ModuleNotFoundError: No module named 'pytz'
```

DuckDB requires `pytz` at runtime whenever a query touches `TIMESTAMPTZ` columns. The `runs`, `llm_usage`, and `ops_events` tables all use `TIMESTAMPTZ`, and `_compute_ops_runtime()` in `scorecard.py` is the first call that trips this. Fix: add `pytz` to `pyproject.toml` dependencies.

### Root Cause 2: Stale test assertions vs. evolved `MappingPolicy` — 11 failures

`test_mapping_policy.py` has 11 failures. Tests were written when `effective_edge == raw_edge * confidence_discount` for a `DIRECT` proxy (discount = 1.0), so tests assert `effective_edge == raw_edge`. The implementation now **subtracts transaction costs** (2% fee+slippage) from gross edge, producing `effective_edge = raw_edge - 0.02`. The test tolerance of `1e-9` catches this 0.02 gap consistently.

Example failure:
```
assert abs(result.effective_edge - result.raw_edge) < 1e-9
# effective_edge=0.14, raw_edge=0.16 → delta=0.02
```

Tests need to be updated to account for the cost model, or assertions need an updated expected value. This is a test/implementation drift issue — the implementation behavior appears correct.

### Root Cause 3: `recalibrate_probability()` logic mismatch — 4 failures

`test_recalibration.py` seeds a small number of resolved signals (< 10) and expects recalibration to fire, but the function returns `(raw_prob, raw_prob)` when `count < min_signals` (default 10). Tests assert calibrated ≠ raw, but the function correctly returns raw. The tests have a **seeding bug** — they do not insert enough resolved-signal rows to cross the `min_signals` threshold.

---

## Code Quality Issues

### DuckDB Single-Writer Violations — **HIGH** (unresolved from April 21)

`DbWriter` asyncio queue exists but is **not wired into the pipeline**. The following modules write directly to DuckDB via `_conn.execute()` or `conn.execute()`, bypassing the queue:

| Module | Violating Write Operations |
|--------|---------------------------|
| `scoring/ledger.py` | INSERT to `signal_ledger`; UPDATE execution fields |
| `scoring/prediction_log.py` | INSERT to `prediction_log` |
| `scoring/tracker.py` | INSERT to `trade_orders`, `trade_fills`; UPDATE `trade_positions` |
| `scoring/resolution.py` | UPDATE `signal_ledger`; UPDATE `trade_positions` |
| `scoring/scorecard.py` | INSERT…ON CONFLICT to `daily_scorecard` |
| `contracts/registry.py` | INSERT OR REPLACE + UPDATE |
| `cli/brief.py` | INSERT/UPDATE to `runs` |

Currently safe only because the CLI is single-threaded. Will cause `database is locked` if the FastAPI `/api/brief/run` endpoint is called concurrently with any other write path.

### Ensemble Budget Tracking Bug — **MEDIUM** (unresolved from April 21)

`prediction/ensemble.py` hardcodes `"opus"` as the model tier in `budget.record()` regardless of which model is actually called. Sonnet calls are logged at Opus pricing, inflating reported LLM spend.

### Ensemble Missing System Prompt / Prompt Caching — **MEDIUM** (unresolved from April 21)

`ensemble_predict()` passes no `system=` argument. Prompt caching is not in use. Per-call cost is ~3× higher than the spec's estimate.

### No Transaction Wrapping in Scorecard — **MEDIUM** (unresolved from April 21)

`compute_daily_scorecard()` calls `_upsert_metric()` in a loop with no transaction boundary. A mid-loop crash leaves partial metrics in `daily_scorecard`.

### No Idempotency Guard in Signal Ledger — **MEDIUM** (unresolved from April 21)

Running `parallax-brief` twice in the same session appends duplicate rows to `signal_ledger` and `prediction_log`. No `UNIQUE(run_id, model_id)` constraint exists.

---

## Architecture Drift

Unchanged from April 21. The pivot from spec to prediction market edge-finder is deliberate. No new structural drift introduced.

---

## Validation Window Closed

The 2-week ceasefire validation window (April 7–21) closed yesterday. Status at close:

- No resolved signals in `signal_ledger` committed to repo.
- No scorecard output files in repo.
- `scoring/resolution.py` backfill logic exists but was never run against real outcomes.
- Paper trading on Kalshi Demo is wired up but Demo sandbox lacks geopolitical contracts; real trades require production execution which runtime guards block.

---

## Recommendations

Priority order:

1. **[P0 — OPEN] Fix `pytz` missing dependency.** Add `pytz` to `pyproject.toml` dependencies. Unblocks 11 test failures with zero code changes. One-line fix.

2. **[P0 — OPEN] Fix test_mapping_policy stale assertions.** Update 11 test expected values in `test_mapping_policy.py` to account for the 2% transaction cost deduction from `effective_edge`. Tests reflect old behavior; implementation is correct.

3. **[P0 — OPEN] Fix test_recalibration seeding bug.** Insert ≥ 10 resolved signal rows in the test fixture before calling `recalibrate_probability()`, so the `min_signals` threshold is crossed and recalibration fires as expected.

4. **[P1 — OPEN] Wire `DbWriter` into the pipeline.** Refactor `SignalLedger`, `PredictionLogger`, `PaperTradeTracker`, `ContractRegistry`, and `scorecard.py` to use `DbWriter.enqueue()` instead of direct `conn.execute()`. Highest-risk issue for production stability.

5. **[P1 — OPEN] Fix ensemble budget model tier.** Change hardcoded `"opus"` in `ensemble.py:122` to pass the actual model tier. Add `model_tier: str` parameter to `ensemble_predict()`.

6. **[P2 — OPEN] Add `system=` param to ensemble calls.** Enables prompt caching and reduces per-call cost by ~90% on repeated calls.

7. **[P2 — OPEN] Wrap scorecard writes in a transaction.** Add `BEGIN`/`COMMIT` around the `_upsert_metric()` loop in `compute_daily_scorecard()`.

8. **[P2 — OPEN] Add idempotency guard.** Add `UNIQUE(run_id, model_id)` to `prediction_log` or add pre-insert existence check to `signal_ledger`.

9. **[P3 — OPEN] Archive stale spec/plan docs.** Add deprecation header pointing to CLAUDE.md as authoritative reference. Update `requires-python` to `>=3.12`.
