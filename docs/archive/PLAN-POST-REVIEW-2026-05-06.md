# Parallax Implementation Plan
## Post-Review Fix Phase — ordered by criticality + dependency
**Source reviews:** AGENT-REVIEW-2026-05-06.md, IMPLEMENTATION-2026-05-06.md, REVIEW-POST-IMPLEMENTATION-2026-05-06.md
**Date:** 2026-05-06

---

## Phase 1: Critical correctness — wire the dead infrastructure (1 day)

### 1.1 Wire LookAheadGuard into BacktestRunner
**Files:** `backend/src/parallax/backtest/look_ahead_guard.py`, `backend/src/parallax/backtest/runner.py`
**Problem:** LookAheadGuard exists and is tested in isolation, but `BacktestRunner._run_day` bypasses it — all helper methods call `self._conn.execute(...)` directly instead of `guard.execute(...)`. Additionally, the guard's `_inject_temporal_filter` is a string mangler vulnerable to operator-precedence breaks (WHERE a=1 OR b=2 → guard injects before OR, silently bypassed), JOIN leaks (filters only first temporal table), no alias/CTE support.

**Design decision:** Rip out the string-mangling approach. Replace with one of:
- **Option A (recommended):** Materialize sim-date-bounded views per simulated day. Runner creates `CREATE VIEW market_prices_sim AS SELECT * FROM market_prices WHERE fetched_at <= ?`, then all helpers query the view. Drop view at day end. Deterministic, no SQL surgery.
- **Option B:** Connection wrapper that `self._conn` delegates through — intercepts `.execute(sql, params)` and validates against temporal tables. More complex but reusable across modules.

**Steps:**
1. Add `_create_sim_views(sim_date)` and `_drop_sim_views()` to BacktestRunner
2. Rewrite `_run_day` to create views before helper calls, drop after
3. Remove LookAheadGuard class entirely OR mark it deprecated with a clear comment
4. Update `tests/test_backtest_look_ahead.py` to test the new view-based approach
5. Add test that `_backfill_resolutions` correctly handles multi-resolution contracts (currently picks latest resolution for ALL sim dates — look-ahead violation)
6. Add tests for: JOIN queries, subqueries, tables with temporal-table substrings in name

**Depends on:** nothing
**Blocks:** all future backtest work

### 1.2 Wire compute_staleness_penalty into prediction confidence
**Files:** `backend/src/parallax/prediction/crisis_context.py`, `backend/src/parallax/prediction/ensemble.py`, `backend/src/parallax/cli/brief.py`
**Problem:** `compute_staleness_penalty` exists and is tested in isolation but has ZERO callers outside its own module. The staleness-based ruin scenario (3 predictors all fed stale context → correlated wrong predictions → ensemble doesn't flag instability → full confidence applied) is unmitigated.

**Design decision:** The ensemble.py already has `apply_context_staleness_penalty` and `ensemble_predict()` accepts `context_age_hours`. Need to check if brief.py passes it through. If not, wire it:
1. In `brief.py`, after `get_crisis_context_with_metadata()`, pass `context_age_hours` to `ensemble_predict()`
2. Verify the penalty multiplies prediction confidence (not probability — direction stays, bet size shrinks)
3. Fix fallback lying about `context_age_hours=0.0` for 24-day-old hardcoded CRISIS_TIMELINE. Compute actual age from most recent SEED_EVENTS entry's date, or refuse fallback for live runs.

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

### 2.1 Fix non-tradable confidence_discount hardcoded to 1.0
**Files:** `backend/src/parallax/contracts/mapping_policy.py` (lines 316-364)
**Problem:** `_build_non_tradable_result` hardcodes `confidence_discount=1.0` regardless of proxy class. Calibration code buckets by `confidence_discount` and will see two populations (tradable correctly discounted, non-tradable at 1.0) — biased analysis.

**Fix:** Pass through actual proxy-class default from the discount_map, OR set to `None` to signal "not applicable." Document choice.
- If None: update calibration code to skip None rows
- If actual value: one-line change at line 351

**Steps:**
1. Change `_build_non_tradable_result` to accept and propagate `confidence_discount`
2. Update callers to pass proxy-class discount
3. Update `scoring/recalibration.py` or `signal_quality_evaluation` view to handle the new value
4. Pin `evaluated_at` in `test_mapping_discount.py` market fixtures (currently wall-clock dependent → 2 flaky tests in suite)

**Depends on:** nothing

### 2.2 Fix fallback prediction defects
**Files:** `backend/src/parallax/cli/brief.py` (lines 44-78, 547-555)
**Three defects:**
1. **Cold-start silent drop:** `_get_fallback_prediction` returns None on empty DB → predictor silently dropped. Add `logger.warning("No fallback for %s, dropping prediction", model_id)` on else branch.
2. **Recursive fallback chain:** fallback is re-logged at `brief.py:574-580` as a new prediction_log row. Run N+1 fallback fetches run N's prediction which was itself a fallback → infinite chain. Add `is_fallback BOOLEAN` column to prediction_log, refuse to fall back to a fallback.
3. **Timestamp preservation:** `_get_fallback_prediction` sets `created_at = datetime.now(timezone.utc)` — loses original staleness. Preserve original timestamp, surface staleness separately.

**Steps:**
1. Add `is_fallback BOOLEAN DEFAULT FALSE` to prediction_log schema
2. Add warning log on cold-start drop
3. Check `is_fallback` in `_get_fallback_prediction` — skip fallback rows
4. Preserve `created_at` from original prediction_log row
5. Update `test_brief_resilience.py::TestGatherExceptionHandling` — rewrite to use `dry_run=False` with mocked predictor exceptions (currently tests dry-run which short-circuits the gather entirely → vacuous pass)

**Depends on:** nothing

### 2.3 Fix crisis_ingester dedup weaknesses
**Files:** `backend/src/parallax/ingestion/crisis_ingester.py`
**Three issues:**
1. **Per-event SQL query** (line 142-147): N round-trips for N events. Batch the hash check — `SELECT headline_hash FROM crisis_events WHERE headline_hash IN (...)` — single query.
2. **Fuzzy dedup only looks back 7 days** (line 57): a rephrased headline at day 8 is a duplicate. Extend lookback or add URL canonicalization as secondary key.
3. **Schema mismatch:** doc says `headline_hash VARCHAR NOT NULL`, actual is nullable `TEXT`. Tighten schema to NOT NULL.

**Steps:**
1. Batch the hash check into one query
2. Extend fuzzy dedup lookback to 21 days (matches crisis_context lookback)
3. Add URL canonicalization (strip tracking params, normalize hostname) as secondary dedup key
4. Add `NOT NULL` to `headline_hash` column
5. Update tests in `test_crisis_context_db.py` to insert with `headline_hash`
6. Update implementation doc to match actual schema

**Depends on:** nothing

---

## Phase 3: Allocator hardening (1-2 days)

### 3.1 Add drawdown circuit breaker
**Files:** `backend/src/parallax/portfolio/allocator.py` (new or modify existing), `backend/src/parallax/cli/brief.py`
**Problem:** `daily_loss_limit=$50` gates one day but not a streak. 5-day losing streak = −$250 = 100% of `max_notional`. No cumulative P&L guard.

**Design:** If 7-day rolling P&L < −20% of bankroll → halve position sizes for 30 days. Configurable thresholds.

**Steps:**
1. Add `_compute_rolling_pnl(conn, window_days=7)` query
2. Add circuit breaker check in allocator before sizing: `if rolling_loss > threshold: scale *= 0.5`
3. Log when breaker triggers
4. Add test with simulated losing streak

**Depends on:** Phase 1.2 (staleness penalty — allocator needs correct confidence inputs)

### 3.2 Fix theme limits for correlated models
**Files:** `backend/src/parallax/cli/brief.py` (line 578), `backend/src/parallax/portfolio/allocator.py`
**Problem:** Theme limits key on `prediction.model_id` — 3 oil-direction models have different model_ids so theme limits never catch correlated oil bets. Need a shared theme bucket (e.g., all three map to "energy" or "oil").

**Design:** Add `theme_group` field to AllocationRequest or derive from contract characteristics. Map: `oil_price` + `hormuz_reopening` + `ceasefire` → shared "iran_oil" theme group. Single group gets shared notional cap.

**Steps:**
1. Add `THEME_GROUPS` mapping in allocator config
2. Modify theme limit check to aggregate by group
3. Add correlation-aware test: 3 oil-direction signals from different models → capped as group

### 3.3 Add correlation-adjusted Kelly
**Files:** `backend/src/parallax/portfolio/allocator.py`
**Problem:** Two correlated signals on oil-up sized independently at 2×. Should be ~1.4× (√2 for perfectly correlated). Quarter-Kelly helps but doesn't address correlation.

**Design:** Detect correlation between signals in same run: if 2+ signals share a theme group AND have same direction (BUY_YES or BUY_NO), apply correlation penalty: `effective_kelly = kelly / sqrt(N_correlated)`.

**Steps:**
1. Group signals by theme_group + direction before sizing
2. Apply 1/√N penalty per correlated group
3. Add test: 2 correlated oil-up signals → combined size < sum of individual sizes

---

## Phase 4: Test suite remediation (0.5 day)

### 4.1 Fix flaky tests
**Files:** `tests/test_mapping_discount.py`, `tests/test_brief_resilience.py`
- Pin `evaluated_at` in all `test_mapping_discount.py` market fixtures (wall-clock dependency → 2 flaky tests)
- Rewrite `test_brief_resilience.py::TestGatherExceptionHandling` to use `dry_run=False` with mocked exceptions
- Rewrite `test_cold_start_floors.py` conditional asserts → unconditional (pick known math pairs)

### 4.2 Fix vacuous tests
**Files:** `tests/test_backtest_look_ahead.py`
- Add integration test: `BacktestRunner.run()` actually respects temporal bounds (currently only tests guard primitives in isolation)
- Add JOIN query test, operator-precedence test, CTE test
- Rename `TestLookAheadDecorator` → `TestLookAheadGuard`

### 4.3 Standardize test state
- Either re-enable `update_discounts_from_history` or delete/skip the 10 `TestDiscountFromHistory` tests. Don't let tests rot in `failed`.
- Doc should claim 19 failures (not 18). `test_mapping_discount.py` is NEW, not pre-existing.

---

## Phase 5: Documentation + schema alignment (0.25 day)
1. Update IMPLEMENTATION-2026-05-06.md: actual crisis_events schema (nullable headline_hash, url field, column order)
2. Document confidence_discount semantics (tradable=actual, non-tradable=None/actual — pick one)
3. Document LookAheadGuard deprecation / view-based replacement
4. Mark `INSURANCE_THREAT_MULTIPLIER` in cascade.py as dead code or wire it up

---

## Dependency graph
```
Phase 1.1 (guard)     Phase 1.2 (staleness)
       ↓                      ↓
       └──────────┬───────────┘
                  ↓
         Phase 2 (bug fixes) — parallelizable
                  ↓
         Phase 3 (allocator) — needs 1.2 + 2.1
                  ↓
         Phase 4 (tests) — can start after 2.x, finish after 3.x
                  ↓
         Phase 5 (docs)
```

## Not in scope (future Phases)
- Kalshi clock-skew tolerance (MED, AGENT-REVIEW item 8)
- API auth/CORS on /api/brief/run (MED, item 7)
- Order-insertion-before-rejection-check race (MED, item 9)
- Kalshi resolution polling retry (item 5 in §1.4)
- E2E "bad-data day" test
- Idempotency test for signal pipeline
- Live-execution authorization gate hardening

---

## Phase 0: Elections domain bootstrapping (parallel track, 1-2 days)
**Goal:** Make Parallax work on US primaries/midterms via Polymarket, not just Iran-Hormuz on Kalshi.

### Why elections > Iran-Hormuz
- Polymarket: $100M+ presidential liquidity, $10M+ midterms. Kalshi geopolitical: ~$5K-20K.
- Recurring, predictable events — not a one-time 2-week crisis window.
- Multiple correlated contracts (president + Senate + House + governor) — correlation-adjusted Kelly actually matters.
- The cascade pattern (deterministic model → LLM prediction) is a cleaner fit for polling data than for oil blockade math.

### What transfers directly (no code changes)
- Signal ledger + scorecard ETL — fully domain-agnostic ✓
- Proxy-aware mapping policy — just needs new proxy_map data ✓
- Trimmed-mean ensemble + instability flag ✓
- Recalibration via bucketed offset ✓
- Backtest harness (with guard fix from Phase 1.1) ✓
- News ingestion (Google News + GDELT) — different RSS feeds, same mechanism ✓
- Paper trading infrastructure ✓

### What needs domain-specific work

#### 0.1 Contract registry + Polymarket adapter
**Files:** `backend/src/parallax/contracts/` (new election config), `backend/src/parallax/markets/polymarket.py` (verify)
- Replace hardcoded `INITIAL_CONTRACTS` (4 Iran contracts) with election contracts
- Example: `PRESIDENT-2028-DEM-NOM`, `SENATE-CONTROL-2026`, `HOUSE-CONTROL-2026`, `GOV-NY-2026`
- Proxy classes: DIRECT (candidate win), NEAR_PROXY (party control), LOOSE_PROXY (policy impact)
- Polymarket adapter already exists — verify it handles election contract discovery
- Polymarket has no RSA-PSS clock-skew issue that Kalshi does

#### 0.2 Election cascade engine
**Files:** `backend/src/parallax/simulation/` (new election_cascade.py)
- Replace: blockade → flow → bypass → price → downstream → insurance
- With: polling-average → state-correlation → EV-projection → momentum → turnout-model
- Same config-driven rule chain feeding into LLM prompt
- Inputs: FiveThirtyEight polling averages, RCP averages, prediction market cross-reference
- Deterministic first pass: EV projection from state-level polling before LLM sees it

#### 0.3 Election context feed
**Files:** `backend/src/parallax/prediction/election_context.py` (new)
- Replace CRISIS_TIMELINE with automated election event feed
- Sources: AP election calls, FEC filings, debate schedules, endorsement tracker
- Same staleness penalty mechanism (fixed in Phase 1.2) — even more important here
- Poll freshness matters: a poll from 3 days ago in a fast-moving primary is stale

#### 0.4 Prediction model refactor
**Files:** `backend/src/parallax/prediction/` (new election models)
- Replace: oil_price.py, ceasefire.py, hormuz_reopening.py
- With: candidate_win.py, party_control.py, turnout.py
- Same ensemble pattern, same cascade→LLM architecture
- Key difference: election models can cross-validate against live Polymarket prices which are much more efficient than Kalshi geopolitical markets

### Phase 0 priority
This runs **in parallel with Phases 1-2.** The infrastructure fixes in Phase 1-2 make the election domain *possible* — without the guard and staleness fixes, the same bugs would poison election predictions too. But the domain bootstrapping can start immediately because it touches separate files (new contracts, new cascade, new models).
