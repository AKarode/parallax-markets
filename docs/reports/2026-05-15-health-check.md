# Parallax Health Check — 2026-05-15

**Status: YELLOW**

No new commits since yesterday's health check — only the `f19faa9` health-check commit itself landed
since `3adcf3c`. All issues from 2026-05-14 carry forward unchanged. The two HIGH blockers
(deprecated model ID, missing `pytz`) remain unactioned at 17 and 30+ days respectively. The
within-batch fuzzy dedup partial fix from `69c5c56` is confirmed: exact duplicate headlines within a
batch are now caught by the updated `fuzzy_candidate_headlines` list, but the hash-set side
(`existing_hashes`) is still not updated after each insert.

---

## Changes Since Last Report

**One commit** since `f19faa9` (yesterday's health check):

| Hash | Description |
|---|---|
| `f19faa9` | chore: daily health check 2026-05-14 (YELLOW) |

No code changes. All issues from 2026-05-14 persist.

---

## Test Results

- Last known state: **429 passed, 13 skipped, 0 failed** (from commit `a5cd92c`)
- Local test runner still blocked: `pip install -e .` fails with `Cannot uninstall cryptography 41.0.7,
  RECORD file not found` (Debian system package conflict; `cryptography 41.0.7` is below the declared
  minimum `>=44.0`)
- No new test failures introduced (no new commits)

---

## Issues Found

### HIGH (ESCALATING — 17 days) — Deprecated Claude Model ID Blocks Live Prediction Runs

`oil_price.py:143`, `ceasefire.py:116`, and `hormuz.py:118` all pass `model="claude-opus-4-20250514"`
to `ensemble_predict()`. This is not a valid Anthropic model ID. Current valid IDs:
`claude-opus-4-7`, `claude-sonnet-4-6`, `claude-haiku-4-5-20251001`. Every live prediction run fails
at the API call with an authentication/routing error.

`ensemble.py:89` (docstring) also references the invalid model string — misleads future callers.

- **Severity**: HIGH — production blocker; all live runs fail
- **Fix**: Replace `"claude-opus-4-20250514"` with `"claude-opus-4-7"` in `oil_price.py:143`,
  `ceasefire.py:116`, `hormuz.py:118`; update `ensemble.py:89` docstring
- **Open since**: 2026-04-28 (17 days unactioned)

---

### HIGH (ESCALATING — 30+ days) — `pytz` Missing from `pyproject.toml`

DuckDB raises `InvalidInputException: Required module 'pytz' failed to import` on any query returning
a `TIMESTAMPTZ` column in clean-install environments. `pytz` is not listed in `[project] dependencies`
in `backend/pyproject.toml`, so `pip install -e .` does not install it.

The `--scorecard` CLI path, all `TIMESTAMPTZ`-returning queries, and approximately 11 tests remain
broken in any fresh clone.

- **Severity**: HIGH — blocks scorecard pipeline on clean installs
- **Fix**: Add `"pytz>=2024.1"` to `[project] dependencies` in `backend/pyproject.toml`
- **Open since**: ~2026-04-15 (30+ days unactioned)

---

### MEDIUM (PERSISTENT — 3 days) — Missing Migration for `crisis_events.headline_hash`

The `crisis_events` DDL (added in `69c5c56`) includes `headline_hash TEXT`, but
`_migrate_legacy_tables()` in `db/schema.py` has no `_add_column_if_missing` call for this column.
Any database created before `69c5c56` will raise `InvalidInputException: Referenced column
"headline_hash" not found` the first time `CrisisIngester.ingest_events()` runs the batch hash
check query.

All other recently added columns have migration guards; this one was missed.

- **Severity**: MEDIUM — breaks ingestion on upgrade; new installs unaffected
- **Fix**: Add to `_migrate_legacy_tables()` in `db/schema.py`:
  ```python
  if _table_exists(conn, "crisis_events"):
      _add_column_if_missing(conn, "crisis_events", "headline_hash", "TEXT")
  ```
- **Open since**: 2026-05-13 (introduced in `69c5c56`)

---

### MEDIUM (PERSISTENT — 3 days) — Within-Batch Hash Dedup Still Incomplete

`CrisisIngester.ingest_events()` fetches `existing_hashes` from the DB once before the insert loop.
After a successful insert, `fuzzy_candidate_headlines` is updated (line 107 — fixed in `69c5c56`) but
`existing_hashes` is not. If a batch contains two headlines with the same MD5 hash (same normalized
headline), the second one passes the hash check.

**Practical impact is low**: the fuzzy dedup (`_headlines_similar` with SequenceMatcher ratio ≥ 0.85)
now catches within-batch exact duplicates because the title is appended to `fuzzy_candidate_headlines`
after each insert. However, the `existing_hashes` omission is a latent correctness gap and violates
the stated dedup contract.

- **Severity**: MEDIUM (reduced from yesterday — fuzzy side partially mitigates)
- **Fix**: Add `existing_hashes.add(headline_hash)` after `inserted += 1` at
  `crisis_ingester.py:106`
- **Open since**: 2026-05-13 (introduced in `69c5c56`; fuzzy side fixed same commit)

---

### MEDIUM (PERSISTENT) — Staleness Penalty Does Not Penalize `probability`

`ensemble_predict()` applies the staleness penalty only to `confidence`; `probability` is returned
unmodified. `DivergenceDetector` uses `probability` to compute edge and generate BUY/SELL signals.
With context currently ~32 days stale (`penalty_factor = 0.0`), signals are generated at full
model strength despite the context being over a month old.

- **Severity**: MEDIUM — stale-context signals carry no visible discount in the divergence detector
- **Fix**: In `ensemble_predict()`, clamp `ensemble_result["probability"]` toward 0.5 proportionally
  to `penalty_factor`, or gate signal generation in `DivergenceDetector` when
  `staleness_penalty_applied=True` and `penalty_factor < threshold`
- **Introduced**: `53f93b1` (staleness logic added but incomplete)

---

### MEDIUM (PERSISTENT) — Calibration Predicate Mismatch

`recalibrate_probability()` counts qualifying signals at `recalibration.py:71` with
`WHERE model_id = ? AND model_was_correct IS NOT NULL`. The `calibration_curve()` function queries
from `signal_quality_evaluation` view, which requires `resolution_price IS NOT NULL`. Signals with
`model_was_correct` set but `resolution_price = NULL` can pass the count gate while returning empty
buckets from the calibration curve, causing recalibration to silently no-op. Test fixtures default
`resolution_price=1.0` which masks the bug.

- **Severity**: MEDIUM — production recalibration may silently no-op
- **Fix**: Add `AND resolution_price IS NOT NULL` to count query at `scoring/recalibration.py:71`

---

### MEDIUM (PERSISTENT) — Direct DB Writes Bypass `DbWriter` Single-Writer Pattern

Spec mandates all writes go through `asyncio.Queue → DbWriter`. The following modules write directly
via `conn.execute()`, violating the single-writer topology:

| File | Write Lines | Table(s) |
|---|---|---|
| `ops/alerts.py` | 106 | `ops_events` |
| `scoring/prediction_log.py` | 95 | `prediction_log` |
| `scoring/resolution.py` | 60, 124 | `signal_ledger` |
| `scoring/scorecard.py` | ~21 | `daily_scorecard` |
| `budget/tracker.py` | 43 | `llm_usage` |
| `cli/brief.py` | 130, 149, 431 | `runs`, `market_prices` |
| `ingestion/crisis_ingester.py` | 89 | `crisis_events` |

Risk is LOW while CLI runs are sequential; HIGH if any path runs concurrently with the FastAPI server.

- **Severity**: MEDIUM (latent HIGH under concurrent load)

---

### LOW (PERSISTENT) — `test_google_news.py` Uses Workaround, Not Root Fix

Hardcoded `pubDate` strings from April 2026 were worked around by expanding `max_age_hours` to
`24 * 365` rather than replacing them with relative dates. The test no longer exercises the realistic
default `max_age_hours=24` path used in production.

- **Severity**: LOW — test coverage gap; no production impact
- **Fix**: Replace hardcoded dates with `datetime.now()` relative strings; restore realistic
  `max_age_hours` per test case

---

### LOW (PERSISTENT) — Python Version Requirement Weaker Than Spec

`pyproject.toml` declares `requires-python = ">=3.11"`. CLAUDE.md and Phase 1 spec state Python 3.12.
System runtime is Python 3.11.15. No current breakage; cosmetic drift.

- **Severity**: LOW
- **Fix**: Update to `requires-python = ">=3.12"` in `backend/pyproject.toml`

---

### LOW (PERSISTENT) — `CLAUDE.md` Tech Stack Lists Uninstalled Dependencies

CLAUDE.md lists `deck.gl`, `MapLibre GL`, `h3-js`, `react-map-gl`, `sentence-transformers`,
`searoute`, `shapely`, `google-cloud-bigquery`, and `websockets` as active dependencies. None appear
in `pyproject.toml` or `frontend/package.json`. The frontend is a Recharts REST-polling dashboard.

- **Severity**: LOW — onboarding confusion only
- **Fix**: Update CLAUDE.md Technology Stack section to reflect actual implementation

---

## Spec / Plan Consistency

The Phase 1 spec described ~50 LLM agents with H3 spatial visualization. The implementation
deliberately pivoted to 3 Claude prediction models + prediction-market arbitrage. No new regressions
from prior reports on these items.

| Spec Item | Status |
|---|---|
| `agents/` — 50-agent country/sub-actor swarm | Out of scope (deliberate pivot) |
| `spatial/` — H3 hexagon model, deck.gl | Out of scope (deliberate pivot) |
| `simulation/circuit_breaker.py` | Not implemented |
| `simulation/engine.py` — DES core | Not implemented (replaced by cascade-only model) |
| `api/auth.py` — invite codes, admin password | Not implemented |
| `api/websocket.py` — real-time push | Not implemented; frontend uses polling |
| `ingestion/dedup.py` — semantic deduplication | Not implemented; fuzzy dedup via SequenceMatcher |
| `ingestion/gdelt.py` — BigQuery GDELT | Not implemented; replaced by GDELT DOC API + Google RSS |
| Prediction models (oil_price, ceasefire, hormuz) | Implemented; **deprecated model ID blocks runs** |
| Kalshi + Polymarket clients | Implemented and tested |
| Signal ledger, paper trading, portfolio allocator | Implemented and tested |
| Divergence detector | Implemented and tested |
| Contract registry + mapping policy | Implemented and tested |
| Daily scorecard ETL | Implemented; `pytz` missing blocks clean installs |
| Backtest harness with look-ahead guard | Implemented and tested |
| Crisis context staleness tracking | Implemented; staleness penalty incomplete (see above) |

---

## Dependency Audit

| Package | `pyproject.toml` | Status | Action |
|---|---|---|---|
| `pytz>=2024.1` | **MISSING** | Not in declared deps | **Add immediately** |
| `fastapi>=0.115` | Present | OK | No action |
| `uvicorn[standard]>=0.34` | Present | OK | No action |
| `duckdb>=1.2` | Present | OK | No action |
| `anthropic>=0.52` | Present | OK | No action |
| `pydantic>=2.10` | Present | OK | No action |
| `truthbrush>=0.2` | Present | OK | No action |
| `cryptography>=44.0` | Present (>=44.0) | **41.0.7 installed** (Debian system) | Blocks `pip install -e .` in this env |

Frontend (`react ^18.3.1`, `recharts ^2.15.0`, `vite ^6.0.0`, `typescript ~5.6.2`): current, no
known CVEs.

---

## Positive Findings

- **Backtest harness** with `LookAheadGuard` temporal isolation fully implemented and tested
- **Staleness penalty end-to-end**: context age computed from DB, propagated through ensemble,
  logged to `prediction_log` with `context_age_hours`, `penalty_factor`, `staleness_penalty_applied`
- **Crisis ingester fuzzy dedup** now correctly blocks within-batch duplicate headlines
- **429 tests passing** (last known state from `a5cd92c`) — no regressions
- **No secrets in repo** — `.env.example` uses placeholders only
- **`AsyncAnthropic` client** used everywhere — no sync instantiations
- **RSA-PSS Kalshi auth** — correct implementation
- **Runtime kill switch + live-execution ACK** — correctly implemented and tested

---

## Recommendations (Priority Order)

1. **[5 min] Fix model ID** — replace `"claude-opus-4-20250514"` with `"claude-opus-4-7"` in
   `oil_price.py:143`, `ceasefire.py:116`, `hormuz.py:118`, and update `ensemble.py:89` docstring.
   Silent production blocker for 17 days.
2. **[1 min] Add `pytz`** — append `"pytz>=2024.1"` to `[project] dependencies` in
   `backend/pyproject.toml`. Unblocks scorecard pipeline on clean installs. 30+ days unactioned.
3. **[10 min] Add `crisis_events.headline_hash` migration** — add
   `_add_column_if_missing(conn, "crisis_events", "headline_hash", "TEXT")` in
   `_migrate_legacy_tables()` inside `db/schema.py`. Prevents upgrade breakage.
4. **[5 min] Fix within-batch hash dedup** — add `existing_hashes.add(headline_hash)` after
   `inserted += 1` at `crisis_ingester.py:106`. Closes the remaining gap left after `69c5c56`.
5. **[30 min] Apply staleness penalty to `probability`** — in `ensemble_predict()`, clamp
   `ensemble_result["probability"]` toward 0.5 when `penalty_factor < 1.0`, or suppress signal
   generation in `DivergenceDetector` when staleness penalty is applied.
6. **[15 min] Align `recalibrate_probability()` predicate** — add `AND resolution_price IS NOT NULL`
   to the count query at `scoring/recalibration.py:71`.
7. **[2 hrs] Wire `DbWriter` or annotate direct-write sites** — prevents future locking under
   concurrent load.
8. **[30 min] Fix `test_google_news.py` fixture dates** — use relative dates, restore realistic
   `max_age_hours` per test case.
9. **[5 min] Update `pyproject.toml`** `requires-python` to `>=3.12`.
10. **[30 min] Update `CLAUDE.md`** tech stack to reflect actual Recharts polling frontend.
