# Phase 1 — Critical Fixes Done — 2026-05-07

**Author:** Claude Opus 4.7 (1M)
**Scope:** Address the two critical defects called out in
`docs/REVIEW-POST-IMPLEMENTATION-2026-05-06.md`:

1. `LookAheadGuard` is decorative — `BacktestRunner` bypasses it; the string
   mangler is brittle even where it does run; `_backfill_resolutions` injects
   future-dated outcomes into past predictions.
2. `compute_staleness_penalty` exists with tests but has zero callers; the
   ruin scenario it was meant to mitigate (correlated wrong predictions on
   stale context) remains unmitigated; the hardcoded fallback lies and
   reports `context_age_hours = 0.0`.

---

## 1. Look-ahead guard rebuilt as sim-date-bounded views

### What changed

`backend/src/parallax/backtest/look_ahead_guard.py`

- Rewrote `LookAheadGuard` so `__enter__` materializes one `TEMP VIEW` per
  temporal table, pre-filtered to `<time_col> <= sim_date_end_of_day`. The
  views are dropped on `__exit__`.
- Added `view_for(table_name) -> str` returning the bounded view name (e.g.
  `lookahead_market_prices`). Raises `RuntimeError` when called outside an
  active context, `KeyError` for non-temporal tables.
- Kept `execute(query, params)` for backwards compatibility — it now does
  word-boundary substitution from bare table names to bounded view names
  rather than string-injecting `WHERE` clauses. The previous regex/heuristic
  approach (`OR`-precedence break, single-table-only injection, no JOIN
  support, no CTE/subquery handling, false-positive substring matches) is
  gone.

`backend/src/parallax/backtest/runner.py`

- `BacktestRunner._run_day` now passes the active guard to its helpers so they
  read from `lookahead_market_prices`, `lookahead_crisis_events`, and
  `lookahead_prediction_log` instead of the raw tables. The temporal bound is
  enforced by the database, not by each call site remembering to add a
  `WHERE` clause.
- Removed the `sim_date` parameter from `_get_historical_market_prices`,
  `_get_historical_news`, and `_simulate_prediction` — they take the guard
  instead, since the bound now lives in the view.
- `_simulate_prediction` still keeps `WHERE model_id = ? AND DATE(created_at)
  = ?` because it still needs to pick the correct historical day; but the
  bounded view ensures any `created_at` after sim-date end-of-day is invisible
  regardless. Backdated/clock-skewed/backfilled predictions cannot leak.

### Why views, not query rewriting

- Views push the bound into the query plan. JOINs, CTEs, subqueries,
  aliases — all work because the filter sits inside the view definition and
  the planner applies it once per view reference.
- The old string mangler had no way to safely inject the bound through a
  subquery or filter both sides of a JOIN. It was also vulnerable to
  operator-precedence breaks (`WHERE filter AND a=1 OR b=2`) and false
  positives from substring matches.
- DuckDB temp views are connection-scoped and free, so creating six on each
  `_run_day` and dropping them on exit is cheap. They're invisible to other
  connections.

## 2. `_backfill_resolutions` multi-resolution bug

`backend/src/parallax/backtest/runner.py:_backfill_resolutions`

- Old query: `ORDER BY resolved_at DESC LIMIT 1` for every prediction. For a
  weekly-settling contract reused across many sim_dates, this picked the
  most-recent resolution — silently injecting future outcomes into past
  predictions. That is itself a look-ahead violation.
- New query: `WHERE resolved_at >= sim_date_min ORDER BY resolved_at ASC
  LIMIT 1`. Picks the FIRST resolution that occurred at or after the
  prediction's sim_date — which is the resolution of the contract instance
  that the prediction was actually for.
- Edge case: if no resolution exists at or after sim_date, the prediction is
  left unresolved (`resolution_price is None`) instead of being misattributed
  to a stale historical outcome.

## 3. Staleness penalty wired into the prediction path

### Hardcoded fallback no longer lies

`backend/src/parallax/prediction/crisis_context.py`

- Added `_latest_seed_event_time()` returning the most recent `event_time`
  from `SEED_EVENTS` (currently `2026-04-12T00:00:00Z`).
- `get_crisis_context_with_metadata(None)` (and the DB-empty fallback path)
  now returns `context_age_hours` computed as `(now - latest_seed).hours`
  and populates `latest_event_time`. The previous hardcoded `0.0` would have
  caused downstream `apply_context_staleness_penalty` to skip the penalty
  entirely on the day the crisis ingester broke, exactly the failure mode
  the penalty is designed to catch.

### Predictors pass `context_age_hours` to `ensemble_predict`

`backend/src/parallax/prediction/oil_price.py`
`backend/src/parallax/prediction/ceasefire.py`
`backend/src/parallax/prediction/hormuz.py`

- Each predictor now imports `get_crisis_context_with_metadata` (instead of
  `get_crisis_context`), captures the `CrisisContextResult`, uses
  `crisis.context` for prompt assembly, and passes
  `context_age_hours=crisis.context_age_hours` to `ensemble_predict(...)`.
- `ensemble.py:ensemble_predict` already accepted `context_age_hours` and
  applies `apply_context_staleness_penalty` to the parsed
  `confidence` field when age > 24h, also flagging
  `staleness_penalty_applied=True`. That existing wiring is now actually
  exercised because callers supply the value.

### Why this matters

- Before: stale context (> 24h) produced three correlated high-confidence
  predictions; the fallback hardcoded text reported as 0h old. Both the
  ruin scenario (§1.4 item 4 of the original audit) and the
  trust-the-fallback footgun were live.
- After: any context older than 24h linearly shrinks the parsed confidence
  toward 0.0 by 72h. The fallback text reports an honest age (months, in
  practice), so the shrink kicks in immediately when the DB ingest is
  unavailable.

---

## 4. Tests

### New file: `backend/tests/test_phase1_critical.py`

Sections:

- `TestBoundedViews` (7 tests) — view name conventions, drop-on-exit,
  bare-table substitution via `execute()`, JOIN handling with bounded views
  (a case the string mangler couldn't do).
- `TestRunnerUsesBoundedViews` (2 tests) — positive: runner reads only past
  market prices; negative: a prediction_log row dated after sim_date end-of-day
  is invisible to `_simulate_prediction`.
- `TestBackfillResolutions` (2 tests) — positive: with two resolutions,
  picks the earliest at-or-after sim_date (not the latest); negative:
  resolutions strictly before sim_date are skipped.
- `TestStalenessFallbackAge` (1 test) — fallback `context_age_hours` matches
  `(now - latest SEED_EVENTS entry).hours`.
- `TestEnsemblePenaltyWiring` (2 tests) — `ensemble_predict` shrinks
  `parsed["confidence"]` at 48h staleness and sets
  `staleness_penalty_applied=True`; preserves it at 12h.
- `TestPredictorPassesContextAge` (4 tests) — each of the three predictors
  (oil_price, ceasefire, hormuz) calls `ensemble_predict` with
  `context_age_hours`; one positive control verifies that with a fresh DB
  event the predictor uses the DB-derived age, not the seed-derived age.
- `TestApplyStalenessPenalty` (4 tests) — sanity checks at 24h, 48h, 72h,
  and `None`.

Updated: `tests/test_crisis_context_db.py::test_returns_fallback_metadata`
to reflect the corrected `context_age_hours` (no longer 0.0).

### Test results

```
tests/test_phase1_critical.py:  21 passed
tests/test_crisis_context_db.py: 19 passed (was 19; one updated assertion)
tests/test_backtest_look_ahead.py: 13 passed
```

Full suite:

```
17 failed, 423 passed in 244.24s
```

vs. the pre-fix baseline reported in the post-implementation review:

```
19 failed, 399 passed in 385.38s
```

Net change: **+24 passing, -2 failing**. Failure breakdown unchanged from
the review's classification — all 17 remaining failures are pre-existing in
files this work did not touch (`test_mapping_policy::TestDiscountFromHistory`,
`test_recalibration`, `test_brief::TestRunBriefDryRun`, `test_google_news`).
None of the new failures are in `tests/test_phase1_critical.py`,
`tests/test_crisis_context_db.py`, `tests/test_backtest_look_ahead.py`, or
the predictor/runner tests.

---

## 5. What's still on the post-review punch list

Not addressed in this phase (called out in the review §7 priorities 3–7):

1. `_build_non_tradable_result` still hardcodes `confidence_discount=1.0`
   (review §1 Bug 2 caveat).
2. `test_mapping_discount.py` flake from wall-clock-dependent fixtures
   (review §4, §6 item 1) — no test added to pin `evaluated_at`.
3. `test_brief_resilience.py::TestGatherExceptionHandling` still uses
   `dry_run=True` and short-circuits the gather block (review §4) — not
   rewritten.
4. `is_fallback` flag on `prediction_log` to prevent fallback-of-fallback
   chaining (review §1 Bug 1 caveat) — not added.
5. Allocator gaps (drawdown circuit breaker, theme-bucket correlation,
   correlation-adjusted Kelly) — not in scope for this phase.

---

## 6. Files touched

```
M backend/src/parallax/backtest/look_ahead_guard.py   rewritten
M backend/src/parallax/backtest/runner.py             _run_day, helpers, _backfill_resolutions
M backend/src/parallax/prediction/crisis_context.py   _latest_seed_event_time + fallback fix
M backend/src/parallax/prediction/oil_price.py        ensemble_predict gets context_age_hours
M backend/src/parallax/prediction/ceasefire.py        ensemble_predict gets context_age_hours
M backend/src/parallax/prediction/hormuz.py           ensemble_predict gets context_age_hours
M backend/tests/test_crisis_context_db.py             fallback assertion updated
A backend/tests/test_phase1_critical.py               new integration tests (21)
```
