# Post-Implementation Review — 2026-05-06

**Reviewer:** Claude Opus 4.7 (1M)
**Scope:** Verify the work claimed in `docs/IMPLEMENTATION-2026-05-06.md` against the actual diff, run the test suite, and call out any regressions or new defects.
**Verdict (TL;DR):** Two of the three "high-severity" bug fixes landed correctly and are honest fixes. The third (cold-start floors) landed correctly. The crisis-context automation is mostly fine but has a schema-vs-doc inconsistency. **The look-ahead guard is decorative — `BacktestRunner` never routes queries through it, so the "core look-ahead prevention mechanism" provides zero protection in the only consumer that exists.** Several tests are wrong, weak, or order-dependent. The implementation doc undercounts failures (claimed 18, actual 19) and silently absorbed at least one new flaky failure.

---

## 1. Bug-fix verification

### Bug 1 — `asyncio.gather` lacks `return_exceptions=True` (brief.py)

**Status: ✅ Fixed correctly.**

- `backend/src/parallax/cli/brief.py:521-526` — data fetchers now use `return_exceptions=True` and the result tuple is unpacked with per-source `isinstance(..., Exception)` guards (lines 528-534). Exceptions are logged with index, not silently swallowed.
- `backend/src/parallax/cli/brief.py:539-544` — predictor gather has `return_exceptions=True`. Lines 547-555 walk the results, log per-model failures, and substitute a fallback prediction via `_get_fallback_prediction`.
- `_get_fallback_prediction` (`brief.py:44-78`) correctly excludes `data_environment = 'dry_run'` rows so a paper/live run cannot accidentally use a dry-run prediction as fallback.

**Caveats and one real defect:**

- **Defect (medium):** if a predictor fails and there is no prior prediction in `prediction_log` (true cold start, fresh DB), `_get_fallback_prediction` returns `None` and the failed prediction is silently dropped from `predictions`. The brief continues with a partial set. There is no log line at the call site distinguishing "failed and substituted" from "failed and dropped" — the only signal is the `INFO` log emitted only on success of the fallback (`brief.py:553`). On cold start with one transient Anthropic error, you lose a model's signal for the day and the brief looks normal. Add an explicit `logger.warning("No fallback for %s, dropping prediction", model_ids[i])` on the `else` branch where `fallback is None`.
- **Defect (low):** the fallback's `created_at` is set to `datetime.now(timezone.utc)` (`brief.py:77`). It should preserve the original timestamp from `prediction_log.created_at` and surface staleness through a separate field, otherwise downstream consumers (and the prediction_log re-write at `brief.py:574-580`) cannot tell the prediction is stale.
- **Sufficiency of the fallback strategy:** falling back to the *previous run's prediction* without any time gating means a 12-hour-old prediction will be used as if it were fresh. Combined with the fact that the `fallback` is then re-logged as a new `prediction_log` row at `brief.py:574-580`, the system risks creating a recursive chain of fallbacks (run N+1 fallback fetches the run N prediction, which itself was a fallback of run N-1, etc.). There is no guard against this. At minimum, store an `is_fallback` flag in `prediction_log` and refuse to fall back to a prediction that is itself a fallback.

### Bug 2 — `confidence_discount` hardcoded to 1.0 (mapping_policy.py)

**Status: ✅ Fixed correctly for tradable results. ⚠️ Still hardcoded to 1.0 on non-tradable results, with a misleading downstream consequence.**

- `mapping_policy.py:67` — loop variable renamed `_legacy_discount` → `confidence_discount`. ✓
- `mapping_policy.py:180` — passed into `_build_mapping_result(... confidence_discount=confidence_discount)`. ✓
- `mapping_policy.py:253-254` — `effective_edge = net_edge * confidence_discount`. ✓
- `mapping_policy.py:301` — emitted on `MappingResult.confidence_discount`. ✓

**Real issues:**

- **Defect (medium):** `_build_non_tradable_result` (`mapping_policy.py:316-364`) **still hardcodes `confidence_discount=1.0`** at line 351 regardless of the actual proxy class. So any `LOOSE_PROXY` mapping that fails because no fair-value estimator exists, or because the quote is stale, lands in the ledger with `confidence_discount=1.0`. The original audit's claim that "the discount_map data exists, looks like it's being applied, and is silently dead" is now **half-fixed**: tradable results use the correct discount, non-tradable results still claim 1.0. Calibration code that buckets by `confidence_discount` (`scoring/recalibration.py`, `signal_quality_evaluation` view at `db/schema.py:642-676`) will now see two populations — one correctly discounted, one not — and the analysis will be biased.
- **Defect (low):** `MappingResult.confidence_discount` for non-tradable results should be `None` or carry the actual proxy-class default, not a misleading `1.0`. Pick one and document it.

### Bug 3 — Cold-start edge floors not enforced (mapping_policy.py)

**Status: ✅ Fixed correctly.**

- `mapping_policy.py:32-36` — `COLD_START_EDGE_FLOORS = {"loose_proxy": 0.08, "near_proxy": 0.06, "direct": 0.04}` matches the doc.
- `mapping_policy.py:47` — `_per_class_min_edge` initialized from the floors instead of starting empty.
- `mapping_policy.py:172` — `min_edge=self._per_class_min_edge.get(proxy_class.value, self._min_edge)` is the right lookup, with `self._min_edge` as the fallback.

**Caveats:**

- **Latent issue:** `update_thresholds_from_history` at `mapping_policy.py:579-599` **only raises** the floor if observed win-rate is bad. It never lowers the floor. So if `LOOSE_PROXY` accumulates 50 trades at 70% win-rate, the system still gates loose proxies at 8% — possibly leaving good edge on the table. Acceptable as a conservative-by-default, but worth documenting.
- **Risk-of-regression:** if a future change resets `_per_class_min_edge` (e.g., calls `dict.clear()` or replaces with `{}`), a `KeyError` won't fire because of the `.get()` default in line 172 — the system silently falls back to the global 5%. The contract-tightening is invisible to a reader of the call site.

### "Bug fixes in allocator.py" — the user's prompt mentions this, the implementation doc does not

The implementation doc only touches `brief.py` and `mapping_policy.py`. **No changes to `portfolio/allocator.py`.** The original audit (§1.4 item 3) called out the cold-start proxy ruin scenario and item from §2.1 mentioned the allocator's theme-limit gap — neither was addressed. If the user expected an allocator fix here, **it did not happen.** Specifically the still-unaddressed allocator gaps from `AGENT-REVIEW-2026-05-06.md`:

- No drawdown circuit breaker on cumulative P&L (review §2.3).
- Theme limits keyed on `prediction.model_id`, so three correlated oil-direction models do not collide on a shared theme bucket (review §2.3).
- No correlation-adjusted Kelly.

Calling these out so the user does not assume "fix allocator.py" was completed.

---

## 2. Crisis-context automation

### `backend/src/parallax/ingestion/crisis_ingester.py` (new)

**Status: ⚠️ Works but has dedup and failure-handling weaknesses.**

- **Two-stage dedup is mostly correct** (`crisis_ingester.py:140-153`): exact match on `headline_hash`, then SequenceMatcher fuzzy match against an in-memory list of recent headlines. However, the in-memory list `existing_headlines` is bootstrapped from the **last 7 days** (`_get_recent_headlines(days=7)`, line 57) but the per-event SQL hash check has **no time bound**. So:
  - Exact-match dedup looks at the entire table forever — stale dupes caught, ✓.
  - Fuzzy-match dedup only looks at last 7 days — a slightly-rephrased headline 8 days later will be inserted as a duplicate.
- **Defect (medium):** `_is_duplicate` runs a SQL query **per event** (line 142-147). For an ingest of N events with M existing in last 7 days, this is N round-trips just for the hash check, plus the in-memory comparison loop is O(N×M). Fine for current volumes but will degrade quickly if you ever feed the daily news firehose through this.
- **Defect (medium):** the constructor takes `events.title` as both the headline and the dedup key. The `NewsEvent.title` is the **publisher's title** — Reuters and Bloomberg often syndicate identical stories with slightly different titles. The fuzzy matching at `>= 0.85` will catch most but not all. There is no URL-canonicalization step (matches the `LOW` issue #11 from the original review). A higher-leverage dedup would add canonicalization of `event.url` (drop tracking params, canonicalize hostname) and use that as a secondary dedup key.
- **Defect (low):** `ingest_events` catches `Exception` per insert (`crisis_ingester.py:87-88`) but the per-event `existing_headlines.append(event.title)` happens *only* on success. If insert succeeds but raises after the append, in-memory state diverges from DB. Currently safe because the exception path returns early, but fragile.
- **Schema mismatch:** the implementation doc (lines 50-61) declares `headline_hash VARCHAR NOT NULL`, but the actual schema (`db/schema.py:478-489`) defines it as nullable `TEXT`. The doc also reverses field order (`source` before `category`), and adds `url` which the doc does not mention. Tests in `tests/test_crisis_context_db.py` insert rows without `headline_hash` (e.g., line 36-42) — those rows would never be matched by the hash dedup, so a follow-up ingestion of the same headline would be inserted twice. Either tighten the schema to match the doc, or update the doc.

### `backend/src/parallax/prediction/crisis_context.py` (rewritten)

**Status: ✅ Mostly clean. One important behavioral difference from the doc.**

- `compute_staleness_penalty` (line 175-190) matches the spec: 0–24h is 1.0, linear decay to 0.0 by 72h.
- `render_crisis_context_from_db` returns `context_age_hours = float("inf")` and `context = ""` for empty DB (line 220-226). The fallback path then catches the empty result via `if result.event_count > 0` (line 276-277) and falls back to `CRISIS_TIMELINE`. ✓
- **Defect (medium):** **the staleness penalty is computed but never applied anywhere.** Grep for `compute_staleness_penalty` outside this module turns up zero callers. The original review §1.4 item 4 — "stale crisis context produces three correlated mispriced predictions" — is the exact ruin scenario this was supposed to mitigate, and the mitigation function exists but is not wired into the ensemble or prediction confidence. **The fix is half-done.** Until `compute_staleness_penalty` is multiplied into prediction confidence (or into the policy's confidence shrink), the architectural fix is cosmetic.
- **Defect (low):** the fallback path at `get_crisis_context_with_metadata` (line 304-308) returns `context_age_hours=0.0` for the **hardcoded** `CRISIS_TIMELINE`. That's a lie — the hardcoded text has "Last updated: 2026-04-12" baked in (line 50, 130-133). At the time of this review (2026-05-06), that's **24 days old** and `context_age_hours` should be ~576, not 0. Future code that uses staleness penalty against this fallback will incorrectly trust it as fresh. Either compute the age from the most recent `SEED_EVENTS` entry, or refuse to return the hardcoded fallback for live runs.

---

## 3. Backtest harness — the look-ahead guard

### `backend/src/parallax/backtest/look_ahead_guard.py`

**Status: ❌ Critical correctness gap. The mechanism is theoretically sound but practically broken in the consumer.**

The `LookAheadGuard` is a context manager with an `execute()` method that injects `WHERE <time_col> <= <sim_date>` into queries that mention temporal tables. **It only filters queries that go through `guard.execute(...)`. Anything that calls `conn.execute(...)` directly bypasses it.**

**The fatal flaw:** `BacktestRunner._run_day` activates the guard (`runner.py:126`) but then calls `self._get_historical_market_prices`, `self._get_historical_news`, `self._get_proxy_class`, and `self._simulate_prediction` — every one of which uses `self._conn.execute(...)` directly (`runner.py:164, 178, 201, 223`). **The guard is decorative.** A reviewer reading `with LookAheadGuard(self._conn, sim_date) as guard:` will assume the inner queries are protected; they are not.

In the current code the inner queries happen to filter manually (`WHERE fetched_at <= ?`, `WHERE event_time <= ?`), so the runner is "accidentally correct." But:

- Any new query added later that forgets the manual filter will silently leak future data, and `LookAheadGuard` will not catch it.
- `_backfill_resolutions` (`runner.py:240-253`) is *intentionally* unguarded — that's correct, because resolutions backfill is supposed to use post-sim-date data — but the current architecture has no way to distinguish "intentionally unguarded" from "forgot to use guard."
- `_simulate_prediction` (`runner.py:223-233`) queries `prediction_log` and only filters by `DATE(created_at) = ?`. If `prediction_log` ever contains predictions persisted *after* the sim_date with a backdated `created_at` (e.g., a backfill, a clock-skew incident, or a re-running of a historical scenario), they will leak. The guard would have caught it via the `prediction_log → created_at` mapping in `TEMPORAL_TABLES`. With direct `conn.execute`, it does not.

**Other defects in the guard itself, even if it were used:**

- **`_inject_temporal_filter` is a string mangler, not a SQL parser** (`look_ahead_guard.py:104-153`). Issues:
  - Only injects **one** filter clause and breaks out at the first match (line 151). For a query that joins `market_prices` and `crisis_events`, only the first table's time column is filtered — the joined table leaks future data unconditionally.
  - **Operator-precedence break**: line 119-126 inserts `<filter> AND` after `WHERE`. For `WHERE a = 1 OR b = 2`, the result is `WHERE filter AND a = 1 OR b = 2`, which by SQL precedence is `WHERE (filter AND a=1) OR b=2` — the filter is silently bypassed for any row where `b = 2`.
  - **Substring matching:** `_should_filter` calls `table in query` (line 100). A column name `fetched_at` containing the substring `prediction_log` (it doesn't, but a future schema change might) or a string literal containing a temporal-table name will match. A SELECT against an *unrelated* table whose name happens to contain a substring of a temporal table will be wrongly treated as needing a filter and the resulting SQL will be invalid (`WHERE fetched_at <= ...` against a table without that column).
  - **No alias support:** if a query uses `FROM market_prices AS mp` and refers to `mp.fetched_at`, the injected filter `fetched_at <= ...` is bare-column and may resolve ambiguously or wrongly in a JOIN.
  - **No subquery / CTE handling:** a query with a CTE that selects from a temporal table will not have the filter pushed into the CTE.
  - Branch ordering at lines 119-149 is fragile — if a query has both `ORDER BY` and `LIMIT`, the `WHERE` is injected before `ORDER BY` (correct) but the `LIMIT` branch is unreachable. Not a correctness bug, but the dead branch suggests the author did not test the combinatorics.
- The guard's `__enter__` raises `RuntimeError` if already active (line 56-57) but the `__exit__` does not undo `_active` until cleanup runs even if an inner exception occurred. Re-entry while an exception is in-flight would re-raise on top of the first exception, masking the underlying error. Minor.

**Recommended fix:** the only safe path for look-ahead protection in DuckDB is to (a) materialize sim-date-bounded views per simulated day and only query those, or (b) use a custom connection wrapper that intercepts `execute` and refuses to run unfiltered SELECTs against temporal tables. The string-mangler approach is too brittle to trust with any production-grade backtest claim.

### Other backtest issues

- **`_backfill_resolutions` always uses the "latest" resolution** (`runner.py:243-253`): the query orders by `resolved_at DESC LIMIT 1` regardless of which resolution corresponds to the prediction's contract horizon. For a contract with multiple historical resolutions (e.g., a weekly settling contract reused across simulated dates), this will pick the most recent and apply it to *every* sim_date prediction — silently injecting future-dated outcomes into past predictions. This is itself a look-ahead violation and the guard does not catch it because the function doesn't go through the guard.
- **`edge_realized` is mislabeled** (`runner.py:266`): the formula `actual_outcome - predicted_probability` computes a calibration error, not a tradable realized edge. Any reader of the `backtest_predictions` table comparing `edge_predicted` and `edge_realized` will draw wrong conclusions about strategy P&L.
- **`was_correct` collapses to ≥0.5 thresholding** (`runner.py:260-263`). A 51% prediction that resolved YES is "correct"; a 49% prediction that resolved YES is "wrong." For probabilistic forecasting that's a poor metric — Brier score is already there; the binary correctness count adds nothing and risks misuse.

---

## 4. Test review — correctness and sufficiency

### `tests/test_brief_resilience.py` (7 tests claimed; actual collection: 7)

- `TestFallbackPrediction` (4 tests): **adequate.** Covers no-history, success, dry-run exclusion, and most-recent ordering.
- `TestGatherExceptionHandling` (2 tests): **weak.** `test_predictor_exception_logged_not_raised` only patches `_fetch_gdelt_events` to return `[]`, then calls `run_brief(dry_run=True)` — but `dry_run=True` short-circuits the entire fetcher/predictor block (`brief.py:503-505`), so the patched function is never called and no exception path is exercised. **The test as written cannot fail.** A real test needs `dry_run=False` with the predictors patched to raise, then verify the brief still completes and the fallback path runs.
- `TestSignalSetValid` (1 test): equivalent to a smoke test of dry-run; provides minimal coverage of the resilience claim.

**Verdict:** the file is named "resilience" but tests almost no resilience behavior. The bug-fix it claims to validate (Bug 1) is essentially uncovered. **Strongly recommend rewriting the gather-failure tests with proper predictor mocks against `dry_run=False`.**

### `tests/test_mapping_discount.py` (5 tests collected; doc claimed 2 failures)

- All 5 pass when run in isolation. **2 fail intermittently in the full suite** (`test_loose_proxy_has_discount_applied`, `test_loose_proxy_effective_edge_is_discounted`). The failure is order-dependent — almost certainly related to `MarketStalenessPolicy.max_quote_age_seconds = 300.0` (`contracts/schemas.py:73`): markets created at the start of a long-running suite age past the threshold by the time an individual test executes, flipping tradable results into non-tradable ones (whose `confidence_discount` is hardcoded to `1.0`, see §1 Bug 2 caveat).
- **Defect (medium):** the test's market fixtures should pin `evaluated_at` explicitly (the `evaluated_at` parameter on `MappingPolicy.evaluate`) instead of relying on wall-clock — this would also make the test stable and document the time-sensitivity. Without that, **these tests will become flaky as the suite grows past 5 minutes** and CI will start reporting these as intermittent failures.
- The doc explained these two failures away as "Missing fair-value estimators for model/contract combinations" — that's only partially right. The real cause is staleness, not estimator coverage.

### `tests/test_cold_start_floors.py` (8 tests)

- Constants and initialization are well-tested.
- **Weakness:** `test_loose_proxy_below_8_percent_not_traded` and `test_direct_with_5_percent_edge_trades` use conditional asserts (`if result.effective_edge ... < 0.08: assert result.should_trade is False`). If the precondition is false, the test passes vacuously. **Replace with unconditional assertions** — pick prediction/market pairs whose math you've worked out, and assert the exact `effective_edge` and `should_trade`.
- No test for the failure mode that triggered this bug fix originally: a `LOOSE_PROXY` mapping that **would** trade at 5% under the old global threshold but **must not** trade at 8% under the new floor. That positive-control test is missing.

### `tests/test_crisis_context_db.py` (15 tests)

- Reasonable coverage of `render_crisis_context_from_db`, `compute_staleness_penalty`, and the seed/fallback logic.
- **Missing:** no test that the staleness penalty is actually applied anywhere in the prediction pipeline. Given that the penalty function exists but has zero callers (see §2 above), this is the test that would have caught the half-finished integration.
- `test_uses_db_when_events_exist` (line 117-131) passes because the DB context contains "DB crisis event" and "CRISIS TIMELINE (from database)" — but it does not assert that the **fallback `CRISIS_TIMELINE` text is excluded.** Two improvements would make this stronger: (a) assert the hardcoded "CRITICAL CONTEXT" header is *not* present, (b) assert the rendered context contains an explicit `event_count > 0` invariant.

### `tests/test_backtest_look_ahead.py` (12 tests)

- All 12 pass.
- **Critical gap:** every test exercises `guard.execute(...)` directly. **None test the actual `BacktestRunner.run()` flow** — and as documented in §3, that's where the guard is bypassed. The test suite *cannot* catch the bug that the runner uses `self._conn.execute` instead of `guard.execute`. So the look-ahead guard tests give a false sense of safety.
- **Defects in coverage:**
  - No test for JOIN queries (the most common real query pattern in the runner and report).
  - No test for the operator-precedence break (`WHERE a = 1 OR b = 2`).
  - No test for subquery / CTE injection.
  - No test for queries against tables whose name *contains* a temporal-table name as a substring (false-positive injection).
  - `test_query_with_limit` (line 230-240) uses a query without WHERE/ORDER BY, so it hits the `LIMIT` branch in `_inject_temporal_filter` — but the runner queries usually have `ORDER BY ... LIMIT` together; that combined branch is never tested.
- **Inaccurate test name:** `TestLookAheadDecorator` is wrapped around context-manager tests, not decorator tests. There is no decorator. Rename or rewrite.

---

## 5. Test suite results

```bash
cd backend && pytest tests/ -v
# 19 failed, 399 passed in 385.38s (0:06:25)
```

The implementation doc claimed `396 passed, 18 failed`. The actual count is **399 passed, 19 failed.** The doc is wrong by one failure. Of the 19:

| Test | Pre-existing? | Honest classification |
|------|--------------|----------------------|
| `test_brief.py::TestRunBriefDryRun::test_dry_run_produces_signals_through_registry` | yes | pre-existing |
| `test_google_news.py::TestFetchGoogleNews::test_fetches_and_deduplicates` | yes | pre-existing |
| `test_recalibration.py` (4 tests) | yes | pre-existing |
| `test_mapping_policy.py` (10 tests, mostly `TestDiscountFromHistory`) | yes — `update_discounts_from_history` was earlier disabled, tests assert recalibration behavior | pre-existing |
| `test_mapping_discount.py::TestLooseProxyDiscount` (2 tests) | **NEW — flaky** | **introduced by this implementation** |

So **1 test that the implementation doc treats as pre-existing was actually introduced by the implementation** (the doc lists `test_mapping_discount.py` as "pre-existing" — it cannot be, because the file was added in this commit). The 2 flaky failures are real regressions caused by relying on wall-clock in newly-added tests.

**Note on test_mapping_policy.py failures:** ten tests in `TestDiscountFromHistory` and the proxy-discount tests fail because `update_discounts_from_history` was disabled (`mapping_policy.py:573-577` returns immediately, ignoring history). Those tests assert that the function adjusts discounts based on win rate. The implementation doc does not call this out as part of its scope, so I'll classify it as pre-existing — but the tests are red and will stay red until either the recalibrator is wired back up or the tests are deleted/skipped. **Letting tests rot in `failed` state is a code-smell that masks future regressions.**

---

## 6. Regressions (vs. previous commit)

1. **2 new flaky tests** in `test_mapping_discount.py` (see §4 above) that pass alone, fail in suite. Will turn into intermittent CI failures.
2. **`MappingResult.confidence_discount = 1.0` lie on non-tradable results** (§1 Bug 2). Pre-fix the field was always `1.0`; post-fix it's correct for tradable results but *wrong* (claims 1.0 when it should be the proxy-class default) for non-tradable. Strictly worse from an analyst's perspective because the field looks like it carries information when it doesn't.
3. **`get_crisis_context_with_metadata` returns `context_age_hours=0.0` for the hardcoded fallback** (§2). This is a *new* misleading signal — previously there was no metadata function. Code that relies on the staleness penalty against the fallback will trust stale text as fresh.
4. **`LookAheadGuard` lull**: the codebase now has a context-manager named `LookAheadGuard` that suggests temporal safety, but the runner does not use it. Future code added to the runner can rely on this false guarantee. Net: previously, no claim of look-ahead safety; now, an unfounded one.

---

## 7. What I would land before another commit

In strict priority order:

1. **Wire `LookAheadGuard.execute` into `BacktestRunner._run_day`'s helper methods**, or rip out the guard and use a clearly-named "manually-bounded query" pattern with the date filter as an explicit argument. Pick one. The current half-state is worse than either.
2. **Wire `compute_staleness_penalty` into prediction confidence.** The function exists and is tested in isolation, but the actual ruin scenario (correlated wrong predictions on stale context) remains unmitigated.
3. **Fix the `_build_non_tradable_result` confidence_discount** — pass through the actual proxy-class default, or set to `None`.
4. **Pin `evaluated_at` in `test_mapping_discount.py` market fixtures** to eliminate the wall-clock dependency. This will stop the flake.
5. **Rewrite `test_brief_resilience.py::TestGatherExceptionHandling`** so it actually exercises the gather failure path (currently it tests dry-run, which short-circuits the gather entirely).
6. **Add a `is_fallback` flag on `prediction_log`** and refuse to fall back to a fallback. The current code can chain fallbacks across runs.
7. **Update the implementation doc** to reflect actual schema columns (`crisis_events.headline_hash` is nullable, `url` field exists, schema column ordering differs from the doc).

---

## 8. Honest closing take

The work that landed is real engineering — these aren't cosmetic edits. The two highest-EV bug fixes (asyncio.gather, confidence_discount on tradable results) are correct, and the cold-start floors are an actual risk mitigation. **The new infrastructure (crisis ingester, backtest harness) is the weak part.** The crisis ingester writes correct data but the staleness penalty it computes is never consumed; the backtest's "look-ahead prevention mechanism" is functionally inert because the only consumer bypasses it. Both pieces were validated by tests that test the *primitives* in isolation but not the *integration*, which is the failure pattern that makes look-ahead bugs and staleness bugs hard to catch in code review.

Treat this commit as Phase 1: bug fixes ship, infrastructure scaffolding lands. Phase 2 has to wire the scaffolding into the prediction and backtest paths, otherwise it's dead weight that gives future readers false confidence.

— *End of post-implementation review*
