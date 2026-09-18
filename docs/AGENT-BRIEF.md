# Agent brief

A work order for an autonomous coding agent picking up this repository.

Read [ARCHITECTURE.md](ARCHITECTURE.md) before writing code, and
[ONBOARDING.md](ONBOARDING.md) for setup and expected test results. This file
tells you what to work on and — more importantly — what not to.

---

## Context in one paragraph

This repository ran a forecasting experiment (Phase 1, March–June 2026) that
was falsified and is now closed. It has been reopened for a different question
that needs no forecasting edge: **do Kalshi and Polymarket ever price the same
event inconsistently enough to clear both venues' fees?** That work lives in
`backend/src/parallax/arb/`. The measurement machinery exists and is tested.
Nothing trades.

## Hard constraints

These are not style preferences. Each one is load-bearing, and violating it
produces code that reports profit that does not exist.

1. **Do not add order execution.** `parallax.arb` is read-only by design. If a
   task seems to need placing an order, it is out of scope — stop and say so.

2. **Do not populate `pairs.REGISTRY`.** Registering a pair asserts that two
   contracts on two venues have *identical payouts* — polarity, settlement
   instant, resolution source and void rules all matching. That requires a
   human reading both venues' rule books. An agent-registered pair is basis
   risk wearing a hedge costume. The registry ships empty on purpose.

3. **Do not port `PaperBook` from `scripts/coherence_arb_probe.py`,** and do not
   introduce any notion of "locked profit". It assumes both legs always fill.
   Two independent venues offer no atomic execution: one leg fills, the other
   moves, and the position is naked. An `ArbOpportunity` is an upper bound on
   what was *quotable*, not a fill.

4. **Do not assume a Polymarket fee rate.** It is per-category. `PolymarketFees`
   defaults to `rate=0` deliberately so nothing silently inherits the politics
   rate. If a task needs a rate, read it from the venue and record `as_of`.

5. **Do not delete, skip, or `xfail` a failing test to make the suite green.**
   The 24 known failures are real debt (see below). Fix them or leave them.

6. **Money arithmetic is `Decimal`, never `float`.** Kalshi rounds fees up to
   the next cent per order; float cannot represent that faithfully.

## Baseline

```bash
cd backend
uv sync --extra dev --extra bench
uv run --extra dev --extra bench pytest -q
```

Expected: **523 passed, 24 failed, 13 skipped**. The `bench` extra is required
for collection — without numpy, four modules fail at import.

A change is a regression if it moves any number other than passed-count upward.

## Tasks, highest value first

### 1. Fix the 24 failing Phase 1 tests

`test_scorecard.py` (10), `test_phase1_critical.py` (4),
`test_crisis_context_db.py` (4), `test_brief_resilience.py` (3), and one each in
`test_selective.py`, `test_ops_events.py`, `test_llm_usage.py`.

Mostly DuckDB schema drift: the tests assert against tables whose shape moved.
Diagnose per file; several will share one root cause. Fix the code or the
schema, not the assertion, unless the assertion is provably wrong — and say
which you did.

### 2. Make `PolymarketClient` symmetric with `KalshiClient`

`KalshiClient.get_orderbook()` returns a normalized `Orderbook`;
`PolymarketClient.get_book()` returns a raw CLOB dict, so `arb/adapters.py`
does normalization that belongs in the client. Also remove the Phase 1
leftover `get_iran_markets()`.

Success: `PolymarketVenue` shrinks to roughly what `KalshiVenue` is, and
`tests/test_polymarket.py` still passes.

### 3. Add snapshot persistence for scan results

There is currently nowhere to put an `ArbOpportunity`. A long-running scan is
worthless without a durable, append-only record of what each poll saw —
including the polls that found nothing, which are the majority and are the
evidence.

Store the **raw observed book** (both sides, with timestamps), not only the
computed edge. A derived number cannot be re-audited; a raw snapshot can.
`scripts/coherence_arb_probe.py` has a reasonable sqlite shape to imitate —
imitate the storage, not the `PaperBook`.

### 4. Support the mirror package

`scanner.evaluate` prices one direction: buy the YES leg on venue A plus the
complementary NO leg on venue B. The mirror — buying the opposite outcome on
each venue — needs all four outcome references, and `MarketPair` currently
carries two. Extending it means extending the settlement-equivalence review to
cover both, so treat the schema change as the real work.

## Conventions

- Branch from `feat/kalshibench-calibration-harness`, one branch per task.
- Conventional commits (`fix:`, `feat:`, `docs:`, `chore:`), scope where useful.
- Explain *why* in the commit body. The reasoning is what git cannot recover.
- Report the test numbers you measured, before and after. Do not describe a
  suite as passing without having run it.
- If a task turns out to be blocked or a constraint above makes it impossible,
  say so plainly rather than working around the constraint.
