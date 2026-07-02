---
status: complete
---

# Quick Task 260701-uqn: Postmortem + README rewrite — Summary

## What was done

1. **docs/POSTMORTEM.md** (new, commit 2598ca8) — full project postmortem: hypothesis, build scope (~16k LOC, 535 tests, 244 commits, Mar 30–Jun 4 2026), the experiments (live run: 75 signals / 89% REFUSED / 4 resolved / 0 trades; 13-day backtest: 46% win rate, −$0.35; KalshiBench audit: isotonic beats raw 3/3, bucket-offset non-monotonic 3/3, leakage caveat; coherence probe: sub-tick incoherence, null), five root causes, what-I'd-do-differently, salvage list, cost table ($0 capital, ~$40 API).
2. **README.md** (rewritten, commit d4eac76) — reframed from active edge-finder to concluded research platform: status banner linking postmortem, Findings section replacing the aspirational Roadmap, evaluation-rigor lead in "What Makes It Interesting", test count 265+ → 535, bench harness added to architecture and quick start, Project History section.

## Verification

- Codex cross-review (read-only) found 7 issues — claim overstatements ("four independent angles", "the loop works", "pre-registered" scope), an interim-vs-final probe framing error, a 4-vs-5 resolved-count inconsistency (source doc itself inconsistent; used 4, the live-DB count), overbroad news-context claim, and self-certifying tone ("honest record", "produced vibes"). All 7 fixed before commit.

## Deviations

- Executed inline rather than via gsd-executor subagent, per user's standing feedback that worktree executor agents are unreliable (report success, make zero commits).
