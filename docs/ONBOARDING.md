# Onboarding

For **@skalakuntla1**, joining for the cross-venue arbitrage work.

Target: cloned, installed, tests running, and one scanner call made against
fake books — inside ten minutes, with no API keys and no money anywhere near it.

---

## 1. What this repository is

Read [README.md](../README.md) first, then skim
[ARCHITECTURE.md](ARCHITECTURE.md). The short version:

An earlier project here tried to beat prediction markets with LLM forecasting.
It failed, thoroughly and on purpose — the experiments were pre-registered with
kill criteria, and they killed it. See [POSTMORTEM.md](POSTMORTEM.md).

**We are not retrying that.** The current question needs no forecast at all:
*do Kalshi and Polymarket ever price the same event inconsistently enough to
clear both venues' fees?* That is `parallax.arb`.

You can ignore about 90% of the code. The arbitrage path is `markets/` plus
`arb/`, roughly 1,700 lines.

## 2. Setup

Requires Python 3.11+ and [uv](https://docs.astral.sh/uv/).

```bash
git clone <repo-url> parallax-markets
cd parallax-markets/backend
uv sync --extra dev --extra bench
```

The `bench` extra pulls numpy/pandas/sklearn. It is not optional for running
tests — four modules fail at *import* without it, and pytest reports a
collection error rather than a test result.

## 3. Run the tests

```bash
uv run --extra dev --extra bench pytest -q
```

Expect **523 passed, 24 failed, 13 skipped**. The 24 failures are pre-existing
Phase 1 debt (mostly DuckDB schema drift in `test_scorecard.py`) and are
documented in ARCHITECTURE.md. Nothing on the arbitrage path fails.

To run only what we care about:

```bash
uv run --extra dev pytest tests/test_arb_fees.py tests/test_arb_scanner.py \
                         tests/test_kalshi.py tests/test_polymarket.py -q
```

Those should be **fully green**. If they are not, stop and say so — that is a
real regression, unlike the 24.

## 4. Make the scanner do something

No keys needed; this prices two fabricated books.

```python
from datetime import datetime, timezone
from decimal import Decimal

from parallax.arb.fees import KalshiFees, PolymarketFees, POLITICS_TAKER_RATE
from parallax.arb.pairs import MarketPair
from parallax.arb.scanner import evaluate
from parallax.arb.venue import Level, OutcomeRef, Quote

now = datetime.now(timezone.utc)

yes = OutcomeRef(venue="kalshi", market_id="KXDEMO-26", side="yes")
no = OutcomeRef(venue="polymarket", market_id="0xdemo", side="no")

pair = MarketPair(
    name="demo",
    yes_leg=yes,
    no_leg=no,
    deadline=datetime(2026, 12, 31, 23, 59, tzinfo=timezone.utc),
    resolution_source="demo source",
    void_rules="demo",
    reviewed=True,              # see section 5 — this is the whole ballgame
    reviewed_by="you",
)

def book(ref, price, size):
    return Quote(outcome=ref, bids=(),
                 asks=(Level(price=Decimal(price), quantity=size),),
                 observed_at=now)

class V:
    def __init__(self, name, fees): self.name, self.fees = name, fees

opp = evaluate(
    pair,
    book(yes, "0.47", 200),
    book(no, "0.47", 200),
    V("kalshi", KalshiFees()),
    V("polymarket", PolymarketFees(rate=POLITICS_TAKER_RATE)),
    now=now,
)
print(opp.packages, opp.net_profit, opp.profit_per_package)
```

Then go break it deliberately — these teach more than the happy path:

- Set both asks to `0.50`. The gross edge vanishes; so does the opportunity.
- Set them to `0.495`. There *is* a cent of gross edge, and Kalshi's fee
  rounding eats it. You should get zero packages.
- Make one book 5 deep and the other 500. Package count follows the thin side.
- Backdate one `observed_at` by two minutes. `StaleQuoteError`.
- Flip `reviewed=False`. `UnreviewedPairError`.

## 5. The part that is actually hard

The code is the easy half. **`pairs.REGISTRY` is empty, and filling it is human
work.**

Registering a pair is a claim that two contracts on two different venues have
*identical payouts*. Not "about the same event" — identical. Before setting
`reviewed=True` you have to read both rule books and confirm:

- **Polarity** — which side on each venue equals which real-world outcome.
- **Deadline** — the exact settlement instant, in an explicit timezone. "End of
  2026" is not a date.
- **Resolution source** — whose published number decides it, and what happens
  when that source revises.
- **Void rules** — if one venue can cancel and refund while the other settles,
  your "hedge" pays on one leg only. This is the one that bites.

Anything you find and accept anyway goes in `known_differences`. That field is
basis risk the profit number does not capture.

If we get this wrong, we are not arbitraging. We are holding a directional bet
and calling it a hedge.

## 6. Ground rules

- **Paper first, and for a while.** `parallax.arb` cannot place an order. That
  is deliberate; don't add it to make a demo work.
- **A reported opportunity is an upper bound**, not a fill. Two venues give no
  atomic execution. One leg fills, the other moves, and you are unwinding a
  naked position.
- **Fee rates are per-market and get verified, not assumed.** Polymarket's 4%
  is politics-specific; the default rate in the code is deliberately zero.
  Every schedule carries `as_of` and `source` — if the date looks old, re-read
  the venue's page before trusting a number.
- **Pre-register kill criteria before the live pilot.** The Phase 1 work is
  trustworthy precisely because it was willing to call itself dead, on
  criteria written in advance. `docs/PROFITABILITY-STRATEGY-2026-06.md` is the
  prior for what we are up against.

## 7. Where things are

| Want | Look at |
|---|---|
| How the pieces fit | [ARCHITECTURE.md](ARCHITECTURE.md) |
| Why the LLM thesis died | [POSTMORTEM.md](POSTMORTEM.md) |
| The single-venue arb probe and its null result | [COHERENCE-ARB-PROBE-RESULTS.md](COHERENCE-ARB-PROBE-RESULTS.md) |
| What the literature says about beating these markets | [PROFITABILITY-STRATEGY-2026-06.md](PROFITABILITY-STRATEGY-2026-06.md) |
| Running things on the droplet | [JARVIS-RUNBOOK.md](JARVIS-RUNBOOK.md) |
| Old session logs | `docs/archive/` |
