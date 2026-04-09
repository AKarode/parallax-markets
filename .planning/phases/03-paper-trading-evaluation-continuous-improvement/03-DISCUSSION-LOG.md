# Phase 3: Paper Trading Evaluation + Continuous Improvement - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-04-08
**Phase:** 03-paper-trading-evaluation-continuous-improvement
**Areas discussed:** Scheduling mechanism, Dashboard scope, Track record injection depth, Recalibration math

---

## Scheduling Mechanism

| Option | Description | Selected |
|--------|-------------|----------|
| launchd (Mac-native) | Survives reboots, can wake from sleep, built-in retry, system console logs | |
| cron | Universal, one-liner per job, portable to VPS, easy to edit | ✓ |
| Python scheduler (APScheduler) | In-process, cross-platform, no OS config | |

**User's choice:** cron (agreed with recommendation)
**Notes:** User keeps PC on, sleep not an issue. Portability to VPS matters. User later asked about running cron in WSL2 on their PC — updating D-01 to account for WSL2 environment.

---

## Dashboard Scope

| Option | Description | Selected |
|--------|-------------|----------|
| Single scrollable page | Everything visible at once, fast to build | |
| Multi-tab | Clean separation per view, scales well | |
| Single page with expandable sections | Compact default, drill into detail, best of both | ✓ |

**Sub-decision — Data source:**

| Option | Description | Selected |
|--------|-------------|----------|
| DuckDB directly | Single source of truth, reuse calibration.py queries | ✓ |
| JSON log files | Simple file reads, portable | |

**User's choice:** Single page with expandable sections, DuckDB-backed, with reusable data layer module for future React migration
**Notes:** User asked about future React frontend. Decision: data layer in `parallax/dashboard/data.py` with query functions that Streamlit calls directly, later exposed as FastAPI endpoints for React.

---

## Track Record Injection Depth

| Option | Description | Selected |
|--------|-------------|----------|
| Last 5 resolved signals | Concise, ~200 tokens, recent memory only | |
| Last 10 resolved signals | Better stats, ~400 tokens | |
| All resolved (summarized) | Full picture as aggregate stats, ~150 tokens | |
| Rolling stats + last 3 individual | Aggregate accuracy + specific recent examples, ~300 tokens | ✓ |

**Sub-decision — Cross-model:**

| Option | Description | Selected |
|--------|-------------|----------|
| Per-model only | Each model sees own record, focused | ✓ |
| Per-model + cross-model summary | System-wide patterns visible, extra tokens | |

**User's choice:** Rolling stats + last 3 individual, per-model only
**Notes:** None

---

## Recalibration Math

| Option | Description | Selected |
|--------|-------------|----------|
| Simple linear adjustment | Bucket-based offset, transparent, easy | |
| Platt scaling | Logistic regression, statistically principled | |
| Prompt self-correction only | Zero math, model adjusts from stats in prompt | |
| Hybrid (prompt now, linear later) | Ship fast with prompt injection, add mechanical recalibration at 10+ signals | ✓ |

**User's choice:** Hybrid — prompt self-correction in 3-03, linear bucket adjustment in 3-04 with 10+ signal gate
**Notes:** Platt scaling needs 50+ data points, unlikely by April 21 deadline.

---

## Claude's Discretion

- Streamlit chart library choices
- Cron timing adjustments
- Error marker file format
- raw_probability column placement
- Dashboard styling

## Deferred Ideas

- React frontend dashboard (data layer designed for migration)
- Real-money trading activation
- Cross-model correlation analysis
- Platt scaling (needs more data)
