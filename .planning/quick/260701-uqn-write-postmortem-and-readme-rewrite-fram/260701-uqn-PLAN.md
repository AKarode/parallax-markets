# Quick Task 260701-uqn: Postmortem + README rewrite

**Goal:** Frame Parallax as a completed research project with a rigorously tested null result, suitable as a portfolio piece.

## Tasks

### Task 1: Write docs/POSTMORTEM.md
- **Files:** docs/POSTMORTEM.md (new)
- **Action:** Full project postmortem: hypothesis, what was built (~16k LOC, 535 tests, 244 commits, Mar 30–Jun 4 2026), the four experiments and their results (signal ledger 89% REFUSED; 13-day backtest 46% win rate; KalshiBench calibration audit; coherence-arb probe null), root-cause analysis of why the edge thesis failed, what worked, what I'd do differently, cost accounting.
- **Sources:** docs/PROFITABILITY-STRATEGY-2026-06.md, docs/COHERENCE-ARB-PROBE-RESULTS.md, docs/KALSHIBENCH-CALIBRATION.md, docs/reports/kalshibench-2026-06-04/REPORT.md, memory (backtest results).
- **Done:** Postmortem reads as disciplined research engineering, every number traceable to a source doc.

### Task 2: Rewrite README.md
- **Files:** README.md
- **Action:** Reframe from "active edge-finder with roadmap" to "completed prediction-market research platform." Add status banner + findings section linking to postmortem, replace the aspirational roadmap with a project-status/findings section, update stale numbers (265+ → 535 tests), keep architecture/quick-start/testing sections.
- **Done:** README presents the project as finished research with a defensible null result; no claims of trading edge anywhere.

## Constraints
- Commit each task atomically (docs-only changes).
- No Co-Authored-By trailers (user standing preference).
- Stay on current branch (branch_name null).
