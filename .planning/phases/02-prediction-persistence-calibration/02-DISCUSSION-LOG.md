# Phase 2: Prediction Persistence + Calibration - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-04-08
**Phase:** 02-prediction-persistence-calibration
**Areas discussed:** Prediction Storage, Resolution Polling, Calibration Queries, News Context Capture
**Mode:** --auto (all decisions auto-selected as recommended defaults)

---

## Prediction Storage

| Option | Description | Selected |
|--------|-------------|----------|
| New prediction_log table | Separate table for prediction history, keeps PredictionOutput as in-flight schema | ✓ |
| Extend PredictionOutput | Add persistence fields directly to existing model | |
| Append to signal_ledger | Store prediction data alongside signals | |

**User's choice:** [auto] New prediction_log table (recommended default)
**Notes:** Keeps concerns separate. PredictionOutput stays a clean in-memory model. prediction_log is the persistence layer.

---

## Resolution Polling

| Option | Description | Selected |
|--------|-------------|----------|
| CLI command (--check-resolutions) | On-demand resolution check, callable from cron | ✓ |
| Background daemon | Continuous polling process | |
| Webhook listener | Wait for Kalshi to notify (not available) | |

**User's choice:** [auto] CLI command (recommended default)
**Notes:** Matches CLI-first architecture. User can set up cron externally.

---

## Calibration Queries

| Option | Description | Selected |
|--------|-------------|----------|
| On-demand SQL queries | Run calibration analysis when requested | ✓ |
| Materialized views | Pre-computed calibration tables updated on insert | |
| Separate analytics DB | Export to analytics-optimized store | |

**User's choice:** [auto] On-demand SQL queries (recommended default)
**Notes:** Data volume is tiny (~100 rows/week). Materialized views add complexity for no benefit.

---

## News Context Capture

| Option | Description | Selected |
|--------|-------------|----------|
| References only (title+URL) | Light storage, articles available via URL | ✓ |
| Full article text | Store complete article content | |
| Embeddings + references | Store semantic embeddings alongside URLs | |

**User's choice:** [auto] References only (recommended default)
**Notes:** Full text storage would 10x the DB size for marginal benefit. URLs are sufficient for replay.

---

## Claude's Discretion

- Exact JSON structure for cascade_inputs and news_context columns
- Index strategy for prediction_log
- Error handling for Kalshi API polling failures

## Deferred Ideas

None
