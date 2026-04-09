---
phase: 03-paper-trading-evaluation-continuous-improvement
plan: 01
subsystem: cli, infra
tags: [cron, scheduling, json-output, bash, automation]

# Dependency graph
requires:
  - phase: 02-prediction-persistence-calibration
    provides: CLI with --dry-run, --no-trade, --check-resolutions, --calibration flags
provides:
  - "--scheduled flag writing structured JSON to ~/parallax-logs/runs/{run_id}.json"
  - "Cron wrapper script with env sourcing, logging, and error markers"
  - "Health check script reporting daily run status"
  - "Crontab installer with 5 scheduled entries and WSL2 advisory"
affects: [03-02, 03-03, 03-04]

# Tech tracking
tech-stack:
  added: []
  patterns: ["Scheduled JSON output alongside human-readable brief", "Error marker pattern for cron failure detection"]

key-files:
  created:
    - scripts/parallax-cron.sh
    - scripts/cron-health-check.sh
    - scripts/install-cron.sh
  modified:
    - backend/src/parallax/cli/brief.py
    - backend/tests/test_brief.py

key-decisions:
  - "log_dir parameter allows test injection without touching ~/parallax-logs"
  - "Scheduled output uses getattr() for signal fields to handle varying signal record types"
  - "T-03-01 mitigation: env var presence checks only, never log API key values"

patterns-established:
  - "Cron wrapper pattern: source env -> run command -> log output -> write error marker on failure"
  - "Health check pattern: count logs and error markers by date prefix"

requirements-completed: [TRAD-04]

# Metrics
duration: 6min
completed: 2026-04-08
---

# Phase 03 Plan 01: Automated Cron Operations Summary

**--scheduled flag with JSON run output, cron wrapper with env sourcing and error markers, health check and crontab installer with 5 daily entries**

## Performance

- **Duration:** 6 min
- **Started:** 2026-04-09T01:21:58Z
- **Completed:** 2026-04-09T01:28:21Z
- **Tasks:** 2
- **Files modified:** 5

## Accomplishments
- Added --scheduled flag to brief.py that writes structured JSON to ~/parallax-logs/runs/{run_id}.json alongside normal brief output
- Created cron wrapper script that sources /tmp/parallax-env.sh, logs output, and writes error markers on failure
- Created health check script and crontab installer with 5 entries (3 briefs, resolution, calibration) plus WSL2 advisory

## Task Commits

Each task was committed atomically:

1. **Task 1: Add --scheduled flag with JSON output** - `ff1414c` (test: RED), `6f1c5d7` (feat: GREEN)
2. **Task 2: Create cron scripts** - `ad2736e` (feat)

## Files Created/Modified
- `backend/src/parallax/cli/brief.py` - Added _write_scheduled_output(), scheduled/log_dir params to run_brief(), --scheduled argparse flag
- `backend/tests/test_brief.py` - 3 new tests for scheduled flag, JSON output, and integrated dry-run
- `scripts/parallax-cron.sh` - Cron wrapper: env sourcing, logging, error markers
- `scripts/cron-health-check.sh` - Nightly health summary of runs and failures
- `scripts/install-cron.sh` - Crontab installer with 5 entries and WSL2 detection

## Decisions Made
- Used `log_dir` parameter on both `_write_scheduled_output()` and `run_brief()` to enable test injection without touching user home directory
- Used `getattr()` for signal field access in JSON serialization to handle varying signal record types gracefully
- Applied T-03-01 threat mitigation: cron wrapper checks env var presence with `[ -z ]` but never logs actual values

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Reinstalled editable package for worktree**
- **Found during:** Task 1 (TDD GREEN phase)
- **Issue:** Python editable install pointed to main repo, not worktree -- imports resolved to stale code without _write_scheduled_output
- **Fix:** Ran `pip install -e ".[dev]"` in the worktree backend directory
- **Files modified:** None (pip metadata only)
- **Verification:** Import from parallax.cli.brief now resolves to worktree path

---

**Total deviations:** 1 auto-fixed (1 blocking)
**Impact on plan:** Infrastructure fix only, no scope change.

## Issues Encountered
None beyond the editable install path issue documented above.

## User Setup Required
None - no external service configuration required. To activate cron scheduling, run `scripts/install-cron.sh` and ensure `/tmp/parallax-env.sh` exists with required environment variables.

## Next Phase Readiness
- Automated pipeline scheduling ready for daily accumulation of prediction history
- JSON run outputs available for report card dashboard (plan 03-02)
- Health check monitoring in place for failure detection

---
*Phase: 03-paper-trading-evaluation-continuous-improvement*
*Completed: 2026-04-08*
