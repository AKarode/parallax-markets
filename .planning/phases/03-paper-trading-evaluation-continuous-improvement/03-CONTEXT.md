# Phase 3: Paper Trading Evaluation + Continuous Improvement - Context

**Gathered:** 2026-04-08
**Status:** Ready for planning

<domain>
## Phase Boundary

Automated daily pipeline runs (cron-scheduled), structured data accumulation, Streamlit dashboard for monitoring, prompt feedback injection (models see their own track record), and signal recalibration based on calibration data. Closes the loop: predictions -> outcomes -> better predictions.

4 plans:
- 3-01: Automated Operations (cron scheduling, --scheduled CLI flag, wrapper script, health checks)
- 3-02: Data Accumulation & Streamlit Dashboard (--report-card CLI, proxy_was_aligned backfill, dashboard)
- 3-03: Prompt Feedback Injection (track record in prompts, db_conn parameter)
- 3-04: Signal Filtering & Confidence Recalibration (bucket-based recalibration, edge threshold tuning, position sizing hints)

NOT in scope: React frontend (future phase), real-money trading, new prediction models, deployment hardening (Phase 4).

</domain>

<decisions>
## Implementation Decisions

### Scheduling (Plan 3-01)
- **D-01:** Use cron (not launchd). User keeps PC on, sleep is not an issue. Portable to VPS later. Three brief runs at 7:00 AM, 1:00 PM, 9:00 PM Pacific. Resolution checker at 11:00 PM. Calibration report at 11:30 PM.
- **D-02:** Wrapper shell script at `scripts/parallax-cron.sh` that sources `/tmp/parallax-env.sh`, runs the command, logs to `~/parallax-logs/YYYY-MM-DD-HHMM.log`. Exit code captured.
- **D-03:** New `--scheduled` CLI flag on brief.py. Writes structured JSON to `~/parallax-logs/runs/{run_id}.json` instead of printing formatted brief. Machine-readable for dashboard and analysis.
- **D-04:** Health check: on failure, write error marker file to `~/parallax-logs/errors/`. Nightly summary script prints what succeeded/failed.

### Dashboard (Plan 3-02)
- **D-05:** Streamlit single-page dashboard with expandable sections (not tabs). Sections: Today's Brief, Track Record / Calibration, Signal History, Market Prices.
- **D-06:** Data layer in a reusable module `parallax/dashboard/data.py` with functions like `get_latest_brief()`, `get_calibration_data()`, `get_signal_history()`. Streamlit calls these directly. Later, same functions become FastAPI endpoints for React frontend — zero query rewrite.
- **D-07:** Read directly from DuckDB (single source of truth). Reuse calibration.py queries where possible.
- **D-08:** New `--report-card` CLI command: per-model accuracy, calibration curve, edge conversion rate, proxy class performance, biggest wins/misses. Text output.

### Proxy Alignment (Plan 3-02)
- **D-09:** Populate `proxy_was_aligned` column in signal_ledger during resolution checking. When resolution comes in, check whether the proxy class assumption held (e.g., did ceasefire model → KXUSAIRANAGREEMENT mapping track actual ceasefire outcomes?).

### Track Record Injection (Plan 3-03)
- **D-10:** Rolling stats + last 3 individual resolved signals per model. Format: aggregate accuracy (X/Y correct, Z% hit rate, calibration bias) + 3 most recent individual outcomes with ticker, predicted probability, resolution, and whether model was correct. ~300 tokens.
- **D-11:** Per-model only (no cross-model stats). Each model sees its own track record.
- **D-12:** New function `_build_track_record(model_id, conn)` in each predictor (or shared utility). Returns formatted text for prompt injection via `{track_record}` placeholder.
- **D-13:** `predict()` methods get `db_conn: duckdb.DuckDBPyConnection | None = None` parameter. If None or no resolved signals, inject "No track record available yet."
- **D-14:** brief.py passes the DuckDB connection to predictors. Connection is already created for contract registry — reuse it.

### Recalibration (Plan 3-04)
- **D-15:** Hybrid approach: prompt self-correction (Phase 3-03) ships first. Mechanical linear bucket adjustment added in 3-04 with 10+ resolved signal minimum gate per model.
- **D-16:** Bucket-based recalibration: query calibration_curve() for the model, compute offset per bucket (predicted_avg - actual_rate), apply as post-processing step between LLM parse and PredictionOutput creation. Store both raw_probability and calibrated_probability.
- **D-17:** Auto-adjust `min_effective_edge_pct` in MappingPolicy based on edge_decay history. If edges under 8% historically never convert for a proxy class, raise threshold for that class. `MappingPolicy.update_thresholds_from_history(conn)` method.
- **D-18:** `suggested_size` field on signals: "full" for historically reliable edge/proxy combos, "half" for untested. Advisory only — displayed in brief output, not enforced in paper trading.

### Claude's Discretion
- Exact Streamlit layout and chart library choices (plotly, altair, or native streamlit charts)
- Cron entry format and exact timing adjustments
- Error marker file format (JSON vs plain text)
- Whether to add `raw_probability` column to signal_ledger or prediction_log
- Dashboard styling and color scheme

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Phase 2 outputs (foundation)
- `.planning/phases/02-prediction-persistence-calibration/02-CONTEXT.md` — Prediction persistence decisions, resolution polling approach, calibration query design
- `.planning/phases/02-prediction-persistence-calibration/02-01-SUMMARY.md` — Prediction log schema
- `.planning/phases/02-prediction-persistence-calibration/02-02-SUMMARY.md` — Resolution checker implementation
- `.planning/phases/02-prediction-persistence-calibration/02-03-SUMMARY.md` — Calibration queries (hit_rate_by_proxy_class, calibration_curve, edge_decay)

### Existing code (critical)
- `backend/src/parallax/scoring/calibration.py` — 3 SQL calibration queries to reuse in dashboard + recalibration
- `backend/src/parallax/scoring/ledger.py` — SignalLedger with resolution columns (proxy_was_aligned to populate)
- `backend/src/parallax/scoring/resolution.py` — Resolution checker (extend for proxy_was_aligned)
- `backend/src/parallax/cli/brief.py` — Pipeline entry point (add --scheduled, --report-card flags, pass db_conn to predictors)
- `backend/src/parallax/prediction/oil_price.py` — OilPricePredictor (add track_record injection)
- `backend/src/parallax/prediction/ceasefire.py` — CeasefirePredictor (add track_record injection)
- `backend/src/parallax/prediction/hormuz.py` — HormuzReopeningPredictor (add track_record injection)
- `backend/src/parallax/budget/tracker.py` — BudgetTracker (Opus pricing already configured)
- `backend/src/parallax/contracts/mapping_policy.py` — MappingPolicy (add update_thresholds_from_history)
- `backend/src/parallax/db/schema.py` — DuckDB tables (may need new columns)

### Research
- `.planning/research/contract-mapping/RESEARCH.md` — Contract mapping and proxy class rationale

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `calibration.py` — hit_rate_by_proxy_class(), calibration_curve(), edge_decay() — reuse for dashboard + report-card + recalibration
- `resolution.py` — check_resolutions() — extend to populate proxy_was_aligned
- `SignalLedger` — resolution columns exist, proxy_was_aligned column exists but never populated
- `BudgetTracker` — already has Opus pricing configured
- `MappingPolicy` — has min_effective_edge_pct parameter, can be made dynamic
- `PredictionOutput` — model for prediction data, used by all 3 predictors

### Established Patterns
- CLI flags on brief.py: `--dry-run`, `--no-trade`, `--check-resolutions`, `--calibration` — extend with `--scheduled`, `--report-card`
- DuckDB sync connection in run_brief() — reuse for passing to predictors
- Module-level logger: `logger = logging.getLogger(__name__)`
- Pydantic models for data structures
- Static methods for formatting in predictor classes

### Integration Points
- `run_brief()` — add JSON output mode for --scheduled, pass db_conn to predictors
- `predict()` methods — add db_conn parameter, inject track record into prompts
- `check_resolutions()` — extend with proxy_was_aligned logic
- New `parallax/dashboard/` package — Streamlit app + reusable data.py module
- New `scripts/parallax-cron.sh` — wrapper for cron execution
- `MappingPolicy` — add update_thresholds_from_history() method

</code_context>

<specifics>
## Specific Ideas

- Data layer in `parallax/dashboard/data.py` designed for reuse: Streamlit now, FastAPI endpoints for React later — same query functions, zero rewrite
- Track record format: "Last 5 predictions: 3/5 correct (60%). Calibration bias: you tend to overestimate by ~12%. Your BUY_NO signals have been more accurate than BUY_YES (75% vs 50%). Biggest miss: predicted 72% ceasefire, resolved at 0%."
- Recalibration only activates at 10+ resolved signals per model — before that, prompt self-correction is the only feedback mechanism

</specifics>

<deferred>
## Deferred Ideas

- React frontend dashboard (future phase — data layer designed for migration)
- Real-money trading activation based on proven P&L
- Cross-model correlation analysis (all models wrong on same day patterns)
- Platt scaling for recalibration (needs 50+ data points, unlikely by April 21)

</deferred>

---

*Phase: 03-paper-trading-evaluation-continuous-improvement*
*Context gathered: 2026-04-08*
