---
phase: 02
slug: prediction-persistence-calibration
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-04-08
---

# Phase 02 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 8.3 |
| **Config file** | backend/pyproject.toml |
| **Quick run command** | `cd backend && python -m pytest tests/ -x -q` |
| **Full suite command** | `cd backend && python -m pytest tests/ -v` |
| **Estimated runtime** | ~5 seconds |

---

## Sampling Rate

- **After every task commit:** Run `cd backend && python -m pytest tests/ -x -q`
- **After every plan wave:** Run `cd backend && python -m pytest tests/ -v`
- **Before `/gsd-verify-work`:** Full suite must be green
- **Max feedback latency:** 5 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 02-01-01 | 01 | 1 | PERS-01 | T-02-01 / — | Prediction data validated by Pydantic before DB insert | unit | `cd backend && python -m pytest tests/test_prediction_log.py -x` | ❌ W0 | ⬜ pending |
| 02-02-01 | 02 | 2 | PERS-02 | T-02-02 / — | Resolution checker validates API responses before updating signal_ledger | unit | `cd backend && python -m pytest tests/test_resolution.py -x` | ❌ W0 | ⬜ pending |
| 02-03-01 | 03 | 3 | PERS-03 | — | Calibration queries return correct aggregates | unit | `cd backend && python -m pytest tests/test_calibration.py -x` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `backend/tests/test_prediction_log.py` — stubs for PERS-01
- [ ] `backend/tests/test_resolution.py` — stubs for PERS-02
- [ ] `backend/tests/test_calibration.py` — stubs for PERS-03

*Existing infrastructure covers test framework. Only test files needed.*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| 7-day prediction accumulation | PERS-04 | Time-dependent — requires real calendar time | Run pipeline daily for 7 days, then verify `SELECT COUNT(*) FROM prediction_log` > 21 |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 5s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
