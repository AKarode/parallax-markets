# Session Log: 2026-04-09 — Daily Feedback Loop + Scorecard (v1.3 Milestone)

## Summary

Closed out v1.2 milestone (Phases 4-5 deferred), created v1.3 milestone for the daily feedback loop and scorecard system. Completed Phase 6 (Telemetry Foundation) using parallel Claude + Codex execution, and Phase 7 (Scorecard CLI + Metrics). The system now has full run-level telemetry, LLM cost tracking, structured alert persistence, experiment tags, and a `--scorecard` CLI command computing 15+ metrics across 5 categories.

Also in this session: merged PR #18 (signal integrity fixes + Truth Social ingestion) to main, created GitHub issues #19-#23 for Sprint A work items.

## What Was Built

### Phase 6: Telemetry Foundation (5 requirements)

| Module | Purpose | Owner |
|--------|---------|-------|
| `db/schema.py` — `runs` table | Run-level metadata: run_id, timestamps, status, environment, counts | Claude |
| `db/schema.py` — `daily_scorecard` table | Metric storage: date + metric_name composite PK, upsert support | Claude |
| `db/schema.py` — `ops_events` table | Structured alert persistence from AlertDispatcher | Codex |
| `db/schema.py` — `llm_usage` table | Per-call token/cost tracking from BudgetTracker | Codex |
| `db/schema.py` — experiment columns | `experiment_id` + `variant` on prediction_log, signal_ledger, trade_orders, trade_positions | Codex |
| `ops/alerts.py` — `DuckDBAlertSink` | New sink class that INSERTs into ops_events on every emit() | Codex |
| `budget/tracker.py` — persistence | BudgetTracker.record() now persists to llm_usage when db_conn provided | Codex |
| `cli/brief.py` — run tracking | _persist_run_start/end write rows to runs table every pipeline execution | Claude |

### Phase 7: Scorecard CLI + Metrics (7 requirements)

| Module | Purpose |
|--------|---------|
| `scoring/scorecard.py` | 445-line module computing 15+ metrics across 5 categories |
| `cli/brief.py` — `--scorecard --date` | CLI wiring for scorecard command |

### Metrics Implemented

| Category | Metrics |
|----------|---------|
| **Signal Quality** | resolved_volume, counterfactual_mean_pnl, hit_rate, brier_score, calibration_max_gap, calibration_buckets, edge_decay, tradeability_funnel |
| **Execution Quality** | orders_attempted, orders_accepted, fill_rate, time_to_fill_p50, time_to_fill_p90, slippage_vs_reference, fees_per_contract |
| **Portfolio/Risk** | gross_exposure, max_concentration, daily_realized_pnl, loss_cap_utilization |
| **Data Quality** | executable_quote_coverage, quote_staleness_rate, avg_quote_age_seconds |
| **Ops/Runtime** | run_count, run_success_rate, latest_run_age_hours, llm_cost_usd, error_alert_count |

## Key Design Decisions

| Decision | Rationale |
|----------|-----------|
| Composite PK (score_date, metric_name) on daily_scorecard | Enables upsert — rerunning scorecard overwrites, doesn't duplicate |
| Codex for schema+wiring, Claude for orchestration | Schema/wiring tasks are self-contained; scorecard logic needs cross-module understanding |
| SUM() null handling with `or 0` pattern | DuckDB SUM returns NULL when no rows match, not 0 — caused initial test failures |
| All metrics computed even when empty | Scorecard shows "N/A (insufficient data)" rather than silently omitting metrics |
| No-run alert in scorecard, not separate cron | Scorecard is the daily heartbeat check — if you're running scorecard, you can check if brief ran |
| Loss cap hardcoded at $20 | Matches BudgetTracker daily cap; could parameterize later |

## Setbacks and Fixes

### 1. Codex `--quiet` flag doesn't exist
**Problem:** All 3 Codex tasks failed with `error: unexpected argument '--quiet' found`
**Root cause:** The Codex CLI doesn't have a `--quiet` flag. Only `--full-auto` is valid for non-interactive execution.
**Fix:** Relaunched with `codex exec --full-auto` (no `--quiet`)
**Lesson:** Check `codex --help` before assuming flags exist

### 2. SUM() returns NULL on empty result sets
**Problem:** All 12 scorecard tests failed with `TypeError: float() argument must be a string or a real number, not 'NoneType'`
**Root cause:** DuckDB `SUM(CASE WHEN ... THEN 1 ELSE 0 END)` returns NULL (not 0) when the WHERE clause matches zero rows
**Fix:** Changed `attempted, accepted, filled, partial = row` to use `row[0] or 0` pattern
**Lesson:** Always null-guard DuckDB aggregate results, even with CASE WHEN defaults

### 3. Experiment columns shifted positional test indexes
**Problem:** test_prediction_log failed — `assert row[2] == 'oil_price'` got `'live'` instead
**Root cause:** Codex added `data_environment` column at position 2, shifting model_id to position 3
**Fix:** Updated positional indexes and column list in test assertions
**Lesson:** Tests using `row[N]` positional access are fragile; named column access is safer

### 4. test_schema expected table set was stale
**Problem:** test_create_tables_creates_all_expected_tables failed — 4 new tables not in expected set
**Root cause:** Schema test hardcodes expected table names; adding tables requires updating the test
**Fix:** Added runs, daily_scorecard, llm_usage, ops_events to expected set
**Lesson:** Inevitable when adding tables; quick fix

## Current State

- **272 tests passing**, 14 pre-existing failures (mapping_policy + recalibration from signal integrity work — not from this session)
- Phase 6 and 7 complete (12/21 v1.3 requirements done)
- `parallax brief --scorecard --date 2026-04-09` works end-to-end
- `parallax brief --dry-run` writes to `runs` table
- All metrics write to `daily_scorecard` with upsert semantics
- GitHub issues #19-#23 created for Sprint A tracking

## Environment

No new env vars. Everything uses existing DuckDB path from `resolve_runtime_config()`.

## Known Limitations

- 14 pre-existing test failures in test_mapping_policy and test_recalibration (cost model edge calculations from signal integrity branch)
- Scorecard doesn't yet trigger alerts on threshold breaches (Phase 8)
- No dashboard yet (Phase 8: ALERT-04)
- Experiment tags exist in schema but nothing populates them yet (Phase 9: EXP-02)
- Loss cap ($20) is hardcoded, not configurable
- `--scorecard` is a subcommand of `parallax brief`, not a standalone `parallax scorecard` command

## Next Steps (Phases 8-9)

1. **Phase 8: Alerting + Dashboard** — wire scorecard threshold breaches into AlertDispatcher, add safety halts, `/api/scorecard` endpoint, minimal dashboard
2. **Phase 9: Feedback Automation + Experiments** — champion/challenger routing, bounded min_edge tightening, cost model auto-updates, sample size guards, sequential inference

## Commits

```
d595e48 feat(scorecard): add daily scorecard CLI with 5 metric categories
891d833 feat(tel): add ops_events, llm_usage tables and experiment tags
12580d4 feat(tel): add runs and daily_scorecard tables, wire run tracking into brief pipeline
979a614 docs: create milestone v1.3 roadmap (4 phases)
47a1917 docs: define milestone v1.3 requirements
35bf1ae docs: start milestone v1.3 Daily Feedback Loop + Scorecard
13d6dd0 Merge pull request #18 from AKarode/audit-fixes-signal-integrity
```
