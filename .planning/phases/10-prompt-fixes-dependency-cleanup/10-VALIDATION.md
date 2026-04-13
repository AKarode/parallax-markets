---
phase: 10
slug: prompt-fixes-dependency-cleanup
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-04-12
---

# Phase 10 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 8.3 |
| **Config file** | `backend/pyproject.toml` |
| **Quick run command** | `cd backend && python -m pytest tests/ -x -q --tb=short` |
| **Full suite command** | `cd backend && python -m pytest tests/ -v` |
| **Estimated runtime** | ~15 seconds |

---

## Sampling Rate

- **After every task commit:** Run `cd backend && python -m pytest tests/ -x -q --tb=short`
- **After every plan wave:** Run `cd backend && python -m pytest tests/ -v`
- **Before `/gsd-verify-work`:** Full suite must be green
- **Max feedback latency:** 15 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 10-01-01 | 01 | 1 | PROMPT-01 | — | N/A | unit | `python -m pytest tests/test_prediction/ -k anchoring -x` | ❌ W0 | ⬜ pending |
| 10-01-02 | 01 | 1 | PROMPT-02 | — | N/A | unit | `python -m pytest tests/test_prediction/ -k bypass -x` | ❌ W0 | ⬜ pending |
| 10-01-03 | 01 | 1 | PROMPT-03 | — | N/A | unit | `python -m pytest tests/test_prediction/ -k hormuz -x` | ❌ W0 | ⬜ pending |
| 10-01-04 | 01 | 1 | PROMPT-04 | — | N/A | unit | `python -m pytest tests/test_prediction/ -k track_record -x` | ❌ W0 | ⬜ pending |
| 10-01-05 | 01 | 1 | PROMPT-05 | — | N/A | unit | `python -m pytest tests/test_prediction/ -k crisis_context -x` | ❌ W0 | ⬜ pending |
| 10-01-06 | 01 | 1 | ARCH-04 | — | N/A | integration | `python -m pytest tests/ -k "not slow" -x` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/test_prediction/test_anchoring.py` — stubs for PROMPT-01
- [ ] `tests/test_prediction/test_bypass_flow.py` — stubs for PROMPT-02
- [ ] `tests/test_prediction/test_hormuz_spec.py` — stubs for PROMPT-03
- [ ] `tests/test_prediction/test_track_record_guard.py` — stubs for PROMPT-04
- [ ] `tests/test_prediction/test_crisis_editorial.py` — stubs for PROMPT-05

*Existing pytest infrastructure covers framework requirements.*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Prompt text reads naturally after edits | PROMPT-01..05 | Subjective quality | Read generated prompts from `--dry-run` output |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 15s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
