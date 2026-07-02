# Parallax Health Check — 2026-07-02

**Status: YELLOW**

## Summary

The project reached a formal conclusion yesterday: the core hypothesis (LLM cascade reasoning can find tradeable mispricing in prediction markets) was falsified by four experiments, and a postmortem was committed. The codebase is now in archival/research-platform mode. Tests remain at 433 passed / 0 failed / 13 skipped. However, two issues flagged in previous health checks remain unresolved: the `portfolio/simulator.py` P&L arithmetic bug (claimed fixed in a June 30 commit but not applied) inflates every backtest result — including the −$0.35 postmortem finding — and the DuckDB single-writer constraint continues to be violated across 13 production files.

---

## Repository State

```
HEAD:         456ff54  Merge remote-tracking branch 'origin/main'
Tests:        433 passed | 0 failed | 13 skipped | 1 warning
              (unchanged since 2026-07-01)
Project mode: Research concluded — postmortem committed 2026-07-01
```

---

## Changes Since Last Report (2026-07-01)

**New commits (all docs, no code):**
- `2598ca8` — `docs/POSTMORTEM.md`: formal project postmortem; hypothesis falsified, research concluded
- `d4eac76` — `README.md`: reframed as completed research platform with null-result findings
- `88ed98d` — `.planning/STATE.md` + quick-task planning artifacts
- `c64f1cb` — `docs/COHERENCE-ARB-PROBE-RESULTS.md` + `docs/PROFITABILITY-STRATEGY-2026-06.md`: supporting evidence docs referenced by postmortem

**No production code changes since `a98b2d4` (2026-06-30).**

---

## Issues Found

### HIGH

- **[HIGH] `portfolio/simulator.py:85` — P&L bug still unresolved (flagged 2 days running)**
  Line 85: `cash += payout - fees + (pos["quantity"] * pos["entry_price"])`
  This adds the original entry cost back on top of the resolution payout, inflating every closed-position P&L. The June 30 commit message (`a98b2d4`) stated this was fixed; the file is absent from that commit's diff. The bug remains at HEAD.

  This matters for archival credibility: the postmortem's backtest result (−$0.35 P&L, 46% win rate) was computed by the same backtesting engine. If the P&L inflation affects backtest settled positions, the stated figure is wrong. The conclusion (coin-flip minus fees = no edge) is likely correct in direction, but the specific number is untrustworthy until this is fixed.

  Fix (one line):
  ```python
  # Line 85 — drop the double-counted entry cost:
  cash += payout - fees
  ```

- **[HIGH] Single-writer pattern violated in 13 production files**
  `DbWriter` (`db/writer.py`) exists with the correct `asyncio.Queue` pattern but is bypassed by every live write path. Any concurrent caller pair (e.g., GDELT ingestion + eval cron) will hit `database is locked`. Current violators:
  - `scoring/tracker.py` — lines 460, 516, 672, 711, 744, 770
  - `scoring/ledger.py` — lines 225, 256
  - `scoring/prediction_log.py` — line 79
  - `scoring/resolution.py` — lines 60, 124
  - `scoring/scorecard.py` — line 21
  - `ingestion/crisis_ingester.py` — line 79
  - `ops/alerts.py` — line 106 (also blocks the asyncio event loop — sync write inside `async` method)
  - `budget/tracker.py` — line 43
  - `contracts/registry.py` — lines 85, 105, 198
  - `cli/brief.py` — lines 130, 149, 431
  - `backtest/runner.py` — lines 290, 308, 329, 356
  - `backtest/look_ahead_guard.py` — lines 96, 109 (CREATE/DROP VIEW)

---

### MEDIUM

- **[MEDIUM] 13 mapping-policy tests permanently skipped, no documented reason**
  All 13 are in `test_mapping_policy.py` covering the proxy-class discount and edge-computation logic. No `reason=` argument in any skip. These have been skipped for 10+ days. Given the project is now archival, they should either be formally removed with a comment, or the reason documented.

- **[MEDIUM] `ops/alerts.py:106` — blocking DuckDB write inside `async` method**
  `DuckDBAlertSink.send()` is declared `async` but executes `self.db_conn.execute(...)` synchronously. This stalls the asyncio event loop on every alert write. Still unresolved since it was first flagged.

- **[MEDIUM] Staleness penalty absent from `divergence/detector.py`**
  Columns `staleness_penalty_applied` and `penalty_factor` exist in the schema; `detector.py` has no staleness logic. Not a correctness issue for archival use, but the postmortem finding that 89% of signals were REFUSED was partly due to stale-context signals passing unpenalized through the detector.

---

### LOW

- **[LOW] `portfolio/__init__.py` missing**
  `/backend/src/parallax/portfolio/` contains `allocator.py`, `schemas.py`, `simulator.py` but no `__init__.py`. `from parallax.portfolio import ...` will fail. Likely works in the current codebase via direct file imports but violates Python package conventions.

- **[LOW] `parallax/config/__init__.py` missing**
  `/backend/src/parallax/config/` contains `risk.py` but no `__init__.py`, making it an implicit namespace package rather than a proper package.

- **[LOW] `requires-python = ">=3.11"` — still looser than spec**
  CLAUDE.md and the plan both specify Python 3.12. Not a correctness risk given the codebase uses only 3.10+ syntax, but inconsistent.

- **[LOW] `truthbrush>=0.2` unlocked minimum pin**
  No change since last report. Loose minimum pin on a third-party library; upstream API change could silently break Truth Social ingestion.

- **[LOW] httpx / Starlette deprecation warning**
  `StarletteDeprecationWarning: Using httpx with starlette.testclient is deprecated; install httpx2 instead.` Emitted on every test run, no change since last report.

---

## Spec/Plan Consistency

The project has formally pivoted away from the Phase 1 design spec. The POSTMORTEM.md documents the final state accurately. Key architectural facts for the record:

| Area | Spec | Actual | Notes |
|---|---|---|---|
| Single-writer DuckDB | ✓ Required | ✗ Violated (13 files) | Persistent across entire project lifetime |
| LLM agent swarm (~50 agents) | ✓ Required | ✗ Never built | Intentional pivot to 3 monolithic predictors |
| H3 / deck.gl / spatial module | ✓ Required | ✗ Never built | Intentional pivot; no spatial/ module |
| eval/ module | ✓ Required | ✗ Never built | Scoring distributed across scoring/ module |
| Prediction market trading | Not in spec | ✓ Built (Kalshi/Polymarket) | The actual pivot direction |
| Paper trading ledger | Not in spec | ✓ Built | Full lifecycle; P&L bug present |
| Budget enforcer | ✓ Required | ✓ Built | BudgetTracker functional |
| Calibration harness (KalshiBench) | Not in spec | ✓ Built | Most reusable artifact per postmortem |

---

## New Documentation (2026-07-01)

- **`docs/POSTMORTEM.md`** — Full project postmortem. Declares hypothesis falsified. Identifies what worked (evaluation discipline, calibration harness, Kalshi client, paper-trading ledger) and what would be done differently. Total cost: ~$40 API + $0 capital.
- **`docs/COHERENCE-ARB-PROBE-RESULTS.md`** — Results of Polymarket coherence-arb probe (0 fills, no gap ever exceeds 4% taker fee, kills the last structural trading angle).
- **`docs/PROFITABILITY-STRATEGY-2026-06.md`** — 7-agent research sweep + adversarial kill pass on 5 candidate pivot strategies; all returned "not promising."

---

## Recommendations (Priority Order)

1. **Fix `portfolio/simulator.py:85` before archiving** — One-line change. The postmortem's backtest number is derived from this code; leaving the bug means the stated P&L figure is wrong. Change `cash += payout - fees + (pos["quantity"] * pos["entry_price"])` to `cash += payout - fees`.

2. **Add `portfolio/__init__.py`** and `parallax/config/__init__.py` — Two empty files; prevents silent import failures if the package is used as a library.

3. **Document or remove the 13 skipped mapping-policy tests** — Either `pytest.mark.skip(reason="proxy-class discount logic superseded by mapping_policy.py refactor")` or delete them. They are noise in the test output.

4. **Consider a final fix pass on `ops/alerts.py:106`** — The async-blocking write is a correctness hazard if the codebase is ever reused. Low effort to route through `run_in_executor`.

5. **Single-writer violations (13 files)** — Not worth the refactor effort if the project is truly archived, but document the risk in CLAUDE.md so any future user knows why concurrent callers may deadlock.
