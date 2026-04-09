---
phase: 03
slug: paper-trading-evaluation-continuous-improvement
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-04-08
---

# Phase 03 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 8.3 |
| **Config file** | backend/pytest.ini |
| **Quick run command** | `cd backend && python -m pytest tests/ -x -q` |
| **Full suite command** | `cd backend && python -m pytest tests/ -v` |
| **Estimated runtime** | ~6 seconds |

---

## Sampling Rate

- **After every task commit:** Run `cd backend && python -m pytest tests/ -x -q`
- **After every plan wave:** Run `cd backend && python -m pytest tests/ -v`
- **Before `/gsd-verify-work`:** Full suite must be green
- **Max feedback latency:** 10 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | Status |
|---------|------|------|-------------|-----------|-------------------|--------|
| 03-01-01 | 01 | 1 | TRAD-04 | integration | `crontab -l \| grep parallax` | ⬜ pending |
| 03-01-02 | 01 | 1 | TRAD-04 | unit | `python -m pytest tests/test_brief_scheduled.py -x` | ⬜ pending |
| 03-02-01 | 02 | 2 | TRAD-01, TRAD-02 | unit | `python -m pytest tests/test_report_card.py -x` | ⬜ pending |
| 03-02-02 | 02 | 2 | TRAD-03 | integration | `streamlit run backend/src/parallax/dashboard/app.py --server.headless true` | ⬜ pending |
| 03-03-01 | 03 | 3 | TRAD-05 | unit | `python -m pytest tests/test_track_record.py -x` | ⬜ pending |
| 03-04-01 | 04 | 4 | TRAD-05 | unit | `python -m pytest tests/test_recalibration.py -x` | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

*Existing infrastructure covers all phase requirements. 192 tests passing. pytest configured.*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Cron runs at scheduled times | TRAD-04 | Requires waiting for cron trigger | Verify `~/parallax-logs/` has new entries after scheduled time |
| Streamlit dashboard renders | TRAD-03 | Visual verification | Open http://localhost:8501, check all sections expand |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 10s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
