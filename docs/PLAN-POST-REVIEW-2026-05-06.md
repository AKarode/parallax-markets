# Parallax Implementation Plan
## Post-Review Fix Phase — ordered by criticality + dependency
**Source reviews:** AGENT-REVIEW-2026-05-06.md, IMPLEMENTATION-2026-05-06.md, REVIEW-POST-IMPLEMENTATION-2026-05-06.md
**Date:** 2026-05-06

---

## Phase 1: Critical correctness — wire the dead infrastructure (1 day)

### 1.1 Wire LookAheadGuard into BacktestRunner
**Files:** `backend/src/parallax/backtest/look_ahead_guard.py`, `backend/src/parallax/backtest/runner.py`
**Problem:** LookAheadGuard exists and is tested in isolation, but `BacktestRunner._run_day` bypasses it — all helper methods call `self._conn.execute(...)` directly instead of `guard.execute(...)`. Additionally, the guard's `_inject_temporal_filter` is a string mangler vulnerable to operator-precedence breaks (WHERE a=1 OR b=2 → guard injects before OR, silently bypassed), JOIN leaks (filters only first temporal table), no alias/CTE support.

**Design decision:** Rip out the string-mangling approach. Replace with:
- **Option A (recommended):** Materialize sim-date-bounded views per simulated day. Runner creates `CREATE VIEW market_prices_sim AS SELECT * FROM market_prices WHERE fetched_at <= ?`, then all helpers query the view. Drop view at day end. Deterministic, no SQL surgery.
- **Option B:** Connection wrapper that `self._conn` delegates through — intercepts `.execute(sql, params)` and validates against temporal tables.

**Steps:**
1. Add `_create_sim_views(sim_date)` and `_drop_sim_views()` to BacktestRunner
2. Rewrite `_run_day` to create views before helper calls, drop after
3. Remove LookAheadGuard class entirely OR mark it deprecated
4. Update `tests/test_backtest_look_ahead.py` to test the new view-based approach
5. Add test that `_backfill_resolutions` correctly handles multi-resolution contracts
6. Add tests for: JOIN queries, subqueries, tables with temporal-table substrings in name

**Depends on:** nothing
**Blocks:** all future backtest work

### 1.2 Wire compute_staleness_penalty into prediction confidence
**Files:** `backend/src/parallax/prediction/crisis_context.py`, `backend/src/parallax/prediction/ensemble.py`, `backend/src/parallax/cli/brief.py`
**Problem:** `compute_staleness_penalty` exists and is tested in isolation but has ZERO callers outside its own module. The staleness-based ruin scenario is unmitigated.

**Steps:**
1. Trace actual call chain: `brief.py` → crisis_context → ensemble. Find the gap.
2. Add `context_age_hours` pass-through at the gap
3. Fix `crisis_context.py:304-308` — set `context_age_hours` to actual age for hardcoded fallback
4. Add integration test: stale context → reduced confidence → smaller Kelly sizing
5. Add test that staleness penalty IS applied in `tests/test_crisis_context_db.py`

**Depends on:** nothing
**Blocks:** Phase 3 (allocator sizing depends on correct confidence)

---

## Phase 2: Bug fixes with known correct fixes (1 day)

### 2.1 Fix _backfill_resolutions look-ahead violation
**File:** `backend/src/parallax/backtest/runner.py`
**Problem:** `_backfill_resolutions()` picks the LATEST resolution for each (sim_date, ticker) pair. For multi-expiry contracts (weekly options), this means a sim_date=Monday backtest can see the Friday resolution — information that didn't exist on Monday. This silently biases all backtest Brier scores.

**Fix:** Pick the EARLIEST resolution at or after sim_date:
```python
rows = conn.execute("""
    SELECT contract_ticker, MIN(resolution_price)
    FROM signal_ledger
    WHERE contract_ticker = ANY(?)
      AND resolved_at >= ?
    GROUP BY contract_ticker
""", [tickers, sim_date_ts]).fetchall()
```

**Steps:**
1. Change MAX → MIN in the `_backfill_resolutions` query (or restructure to use `ORDER BY resolved_at ASC LIMIT 1` per ticker)
2. Add test: two resolutions at different dates, assert earliest is used

**Depends on:** 1.1
**Blocks:** any backtest validity

### 2.2 Fix confidence_discount propagation
**File:** `backend/src/parallax/contracts/mapping_policy.py`
**Problem:** Already fixed in current commit. Adding here for completeness.
**Status:** DONE (commit merged)

### 2.3 Fix cold-start edge floors
**File:** `backend/src/parallax/contracts/mapping_policy.py`
**Problem:** Already fixed in current commit. Adding here for completeness.
**Status:** DONE (commit merged)

### 2.4 Align recalibrate_probability predicate
**File:** `backend/src/parallax/scoring/recalibration.py`
**Problem:** Count gate uses `model_was_correct IS NOT NULL`; calibration view uses `resolution_price IS NOT NULL`. Mismatch allows silent no-op.

**Fix:** Add `AND resolution_price IS NOT NULL` to count query at line 71.

**Depends on:** nothing

---

## Phase 3: Architecture improvements (2-3 days)

### 3.1 Restore meaningful confidence_discount adaptation
**File:** `backend/src/parallax/contracts/mapping_policy.py`
**Problem:** `update_discounts_from_history()` was disabled. The cold-start floors are now correct but the discount never adapts to empirical hit rates. Phase 3 replaces the EMA heuristic with a bucketed Bayesian update.

**Design:** For each proxy class with N≥10 resolved signals:
- Compute `actual_hit_rate = correct_signals / total_signals` per 10-bucket calibration curve
- Use Bayesian update with Beta prior: `posterior = (prior_alpha + correct) / (prior_alpha + prior_beta + total)`
- Clamp to class-specific floors/ceilings (DIRECT: [0.8, 1.0], NEAR_PROXY: [0.4, 0.8], LOOSE_PROXY: [0.2, 0.5])

**Steps:**
1. Re-enable `update_discounts_from_history()` with the Bayesian logic
2. Add `min_signals=10` gate (already present)
3. Update `TestDiscountFromHistory` tests to expect new Bayesian values
4. Wire into daily brief run after signal resolution

**Depends on:** 1.2 (staleness penalty must be correct before calibration data is meaningful)

### 3.2 Add DbWriter to remaining direct-write modules
**Files:** `ops/alerts.py`, `scoring/ledger.py`, `scoring/prediction_log.py`, `scoring/resolution.py`, `budget/tracker.py`, `scoring/scorecard.py`, `cli/brief.py`, `ingestion/crisis_ingester.py`
**Problem:** 8 modules still write directly via `conn.execute()`. Risk is LOW now but HIGH under concurrent FastAPI load.

**Design:** Either:
- Route all writes through `DbWriter` via async queue (correct)
- Add startup guard: raise if concurrent mode detected without single-writer

**Steps:**
1. Add `# SINGLE_PROCESS_ONLY: direct conn.execute write; safe while CLI is sequential` comment to all direct-write sites
2. Add runtime check in `main.py` (FastAPI startup): if `DbWriter` not initialized, refuse to start
3. Phase 3.2.2: gradually migrate sites to `DbWriter`

**Depends on:** nothing

### 3.3 Portfolio simulator replay mode
**File:** `backend/src/parallax/portfolio/simulator.py`
**Problem:** `PortfolioSimulator.run()` exists but doesn't feed its outputs into the backtest harness. The signal ledger replay and Kelly-weighted PnL simulation are disconnected from the look-ahead-safe backtest.

**Steps:**
1. Add `BacktestRunner._run_portfolio_simulation(sim_date, predictions)` method
2. Feed MappingResult outputs to `PortfolioSimulator` with historical market prices
3. Record realized PnL per day in `backtest_predictions` table
4. Surface in `BacktestReport` as PnL curve

**Depends on:** 1.1, 2.1

---

## Phase 4: Production hardening (ongoing)

### 4.1 Add pytz to pyproject.toml
**One-line fix.** 26+ days unactioned. Unblocks scorecard on clean installs.

### 4.2 Fix deprecated Claude model ID
**Five-minute fix.** Replace `"claude-opus-4-20250514"` with `"claude-opus-4-7"` in 3 files.

### 4.3 Update crisis_context.py with current events
**Required before any live run is meaningful.** Monthly maintenance task.

### 4.4 Fix test_google_news.py fixture
**Replace hardcoded April 8 pubDates with relative dates.** Prevents monthly expiry of test fixtures.

### 4.5 Python 3.12 runtime
**Update `requires-python = ">=3.12"` and upgrade deployment environment.**

### 4.6 Update CLAUDE.md tech stack section
**Remove H3/deck.gl/MapLibre/searoute/shapely references. Replace with actual Recharts polling stack.**

---

## Execution Order

```
Week 1, Day 1:  Phase 1 (1.1 + 1.2) + Phase 4.1 + Phase 4.2
Week 1, Day 2:  Phase 2 (2.1 + 2.4)
Week 2:         Phase 3 (3.1 + 3.2 + 3.3)
Ongoing:        Phase 4 (4.3 monthly, 4.4 on test expiry)
```

## Success Metrics

- All tests passing (0 failures, 0 pre-existing failures)
- BacktestRunner producing time-bounded results with look-ahead guard active
- Staleness penalty measurably reducing Kelly size when context > 24h old
- Live prediction runs producing outputs without API errors
- Recalibration actually firing when N >= 10 resolved signals exist
