# Session Log: 2026-04-09 — Daily Feedback Loop, Scorecard, Dashboard, Exit Research

## Summary

Major session covering the full v1.3 milestone sprint. Merged PR #18 (signal integrity + Truth Social), created GitHub issues #19-#23, initialized v1.3 milestone with 4-phase roadmap. Completed Phase 6 (Telemetry Foundation) using parallel Claude + Codex execution, Phase 7 (Scorecard CLI + Metrics), and most of Phase 8 (Dashboard). Also researched exit/sell logic feasibility — conclusion: hold to settlement is better than active exit trading given Kalshi's fee structure. Added edge-decay-over-time tracker to collect empirical data.

## What Was Built

### Phase 6: Telemetry Foundation (Claude + Codex parallel)

| Module | Purpose | Owner |
|--------|---------|-------|
| `db/schema.py` — `runs` table | Run-level metadata per pipeline execution | Claude |
| `db/schema.py` — `daily_scorecard` table | Metric storage with composite PK + upsert | Claude |
| `db/schema.py` — `ops_events` table | Structured alert persistence | Codex |
| `db/schema.py` — `llm_usage` table | Per-call LLM token/cost tracking | Codex |
| `db/schema.py` — experiment columns | `experiment_id` + `variant` on 4 tables + migrations | Codex |
| `ops/alerts.py` — `DuckDBAlertSink` | Persists alerts to DuckDB on every emit() | Codex |
| `budget/tracker.py` — persistence | BudgetTracker.record() writes to llm_usage | Codex |
| `cli/brief.py` — run tracking | _persist_run_start/end for every pipeline run | Claude |

### Phase 7: Scorecard CLI + Metrics

| Module | Purpose |
|--------|---------|
| `scoring/scorecard.py` | 445-line module: 15+ metrics across 5 categories, upsert to daily_scorecard |
| `cli/brief.py` — `--scorecard --date` | CLI wiring for scorecard command |

### Phase 8: Dashboard (partial)

| Module | Purpose |
|--------|---------|
| `dashboard/app.py` | Streamlit dashboard with 3 tabs: Overview, Scorecard, Trades |
| Scorecard tab | KPI tiles, Brier timeseries, reliability diagram, order funnel, tradeability funnel, hit rate by proxy |
| Trades tab | Order journal with side, qty, limit, fill, status, PnL |

### Exit Logic Research + Edge Decay Tracker

| Module | Purpose |
|--------|---------|
| `.planning/research/exit-logic/RESEARCH.md` | Full feasibility analysis: fee math, infrastructure audit, recommendation |
| `scoring/calibration.py` — `edge_decay_over_time()` | Pairs consecutive signals per contract, measures edge change between runs |
| `scoring/calibration.py` — `edge_decay_summary()` | One-line verdict: is exit trading worth building? |

### Infrastructure

| Module | Purpose |
|--------|---------|
| `scripts/cron_pipeline.sh` | Portable cron script: brief → resolutions → scorecard |
| `.env.example` | Template for API keys |
| `README.md` | WSL/Linux deployment instructions |

## Metrics Implemented (Scorecard)

| Category | Metrics |
|----------|---------|
| **Signal Quality** | resolved_volume, counterfactual_mean_pnl, hit_rate, brier_score, calibration_max_gap, calibration_buckets, edge_decay, tradeability_funnel |
| **Execution Quality** | orders_attempted, orders_accepted, fill_rate, time_to_fill_p50/p90, slippage_vs_reference, fees_per_contract |
| **Portfolio/Risk** | gross_exposure, max_concentration, daily_realized_pnl, loss_cap_utilization |
| **Data Quality** | executable_quote_coverage, quote_staleness_rate, avg_quote_age_seconds |
| **Ops/Runtime** | run_count, run_success_rate, latest_run_age_hours, llm_cost_usd, error_alert_count |

## Key Design Decisions

| Decision | Rationale |
|----------|-----------|
| Codex for schema+wiring, Claude for orchestration | Schema/wiring tasks are self-contained; scorecard logic needs cross-module understanding |
| Composite PK (score_date, metric_name) | Enables upsert — rerunning scorecard overwrites, doesn't duplicate |
| Hold-to-settlement over active exit trading | Round-trip fee ~5.5c vs settlement fee ~2.8c. Exit needs >5.5c edge decay to be profitable. |
| Edge decay tracker (data-first) over building exit engine | Collect empirical data to prove the opportunity before building complexity |
| v1.2 Phases 4-5 deferred | Deployment fixes not critical for CLI-first; thesis expansion blocked on proving edge |
| 2x daily cron (8am + 8pm UTC) | Matches news cycle cadence; more frequent wouldn't produce more resolved signals |

## Setbacks and Fixes

### 1. Codex `--quiet` flag doesn't exist
**Problem:** All 3 Codex tasks failed with `error: unexpected argument '--quiet' found`
**Root cause:** Codex CLI has `--full-auto` but not `--quiet`. Skill template assumed it existed.
**Fix:** Relaunched with `codex exec --full-auto`
**Lesson:** Check `codex --help` before assuming flags

### 2. SUM() returns NULL on empty DuckDB result sets
**Problem:** All 12 scorecard tests failed with `TypeError: float() argument must be a string or a real number, not 'NoneType'`
**Root cause:** `SUM(CASE WHEN ... THEN 1 ELSE 0 END)` returns NULL when WHERE matches zero rows
**Fix:** Changed to `row[0] or 0` pattern for all aggregate results
**Lesson:** Always null-guard DuckDB aggregates

### 3. Experiment columns shifted positional test indexes
**Problem:** test_prediction_log failed — `row[2]` was `'live'` not `'oil_price'`
**Root cause:** Codex added `data_environment` at position 2, shifting subsequent columns
**Fix:** Updated positional indexes in test assertions
**Lesson:** Positional `row[N]` access is fragile; named access is safer

### 4. Calibration bucket is a string, not float
**Problem:** Dashboard Scorecard tab crashed with `ValueError: Unknown format code '%' for object of type 'str'`
**Root cause:** `calibration_curve()` returns bucket as `"60-80%"` string, not a float. Dashboard used `f"{c['bucket']:.0%}"`
**Fix:** Changed to `str(c['bucket'])` and parsed midpoints from the string for the perfect-calibration line
**Lesson:** Always check return types from query functions before formatting

### 5. Streamlit port already in use
**Problem:** Dashboard wouldn't start — port 8501 occupied by previous process
**Root cause:** Previous streamlit process not cleaned up
**Fix:** `lsof -ti:8501 | xargs kill -9` before restart
**Lesson:** Kill old processes before relaunching

## Current State

- **281 tests passing**, 14 pre-existing failures (mapping_policy + recalibration from signal integrity branch)
- Phase 6 complete (5/5 requirements), Phase 7 complete (7/7 requirements)
- Phase 8 partially complete: dashboard done (ALERT-04), threshold alerting (ALERT-01/02/03) still needed
- `parallax brief --scorecard --date 2026-04-09` works end-to-end
- Dashboard at `localhost:8501` with Overview, Scorecard, Trades tabs
- Cron script ready for WSL/Mac deployment
- Edge decay tracker collecting data from day 1
- GitHub issues #19-#23 created for Sprint A tracking
- Exit logic research complete — verdict: hold to settlement, collect edge decay data first

## Environment

No new env vars. Same as before:
```
ANTHROPIC_API_KEY, KALSHI_API_KEY, KALSHI_PRIVATE_KEY_PATH, EIA_API_KEY (optional)
```

Dashboard: `DUCKDB_PATH=data/parallax.duckdb streamlit run src/parallax/dashboard/app.py`

## Known Limitations

- 14 pre-existing test failures in test_mapping_policy and test_recalibration
- Phase 8 incomplete: ALERT-01 (threshold breaches), ALERT-02 (safety halts), ALERT-03 (/api/scorecard endpoint)
- No exit/sell logic — intentionally deferred pending edge decay data
- Kalshi demo sandbox has no geopolitical markets — paper trading is counterfactual only
- Loss cap ($20) hardcoded in scorecard, not configurable
- Brier timeseries needs 2+ days of scorecard data to render
- Dashboard reads DuckDB in read-only mode — can't compute scorecard from the dashboard

## Next Steps

1. **Deploy cron on WSL** — clone repo, set up .env, install crontab, start accumulating data
2. **Phase 8 remaining** — wire threshold breaches into AlertDispatcher, safety halts, /api/scorecard endpoint
3. **Phase 9** — champion/challenger experiments, bounded parameter updates, sequential inference
4. **After 1 week of data** — check `--calibration` edge decay section to decide on exit logic
5. **After 50 resolved signals** — evaluate Brier score, decide if Sonnet predictions are good enough or try Opus challenger

## Commits

```
35c0a89 feat(calibration): add edge decay over time tracking for exit-logic feasibility
125a12f feat(dashboard): add scorecard and trades tabs to Streamlit dashboard
7c4ecca feat: add cron pipeline script and WSL deployment instructions
aef395c docs: session log and CLAUDE.md update for v1.3 scorecard milestone
d595e48 feat(scorecard): add daily scorecard CLI with 5 metric categories
891d833 feat(tel): add ops_events, llm_usage tables and experiment tags
12580d4 feat(tel): add runs and daily_scorecard tables, wire run tracking into brief pipeline
979a614 docs: create milestone v1.3 roadmap (4 phases)
47a1917 docs: define milestone v1.3 requirements
35bf1ae docs: start milestone v1.3 Daily Feedback Loop + Scorecard
13d6dd0 Merge pull request #18 from AKarode/audit-fixes-signal-integrity
```
