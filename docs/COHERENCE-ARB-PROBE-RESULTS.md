# Coherence-Arbitrage Probe — Results

**Test:** Stage-A falsification of the Senate/House Balance-of-Power coherence-arbitrage thesis (the one structurally-defensible, forecasting-free angle from `PROFITABILITY-STRATEGY-2026-06.md` §9).
**Run:** Polymarket 2026-midterm markets, started 2026-06-04 10:03 UTC, on Jarvis (`parallax-coherence-probe.service`), $1,000 pretend paper book.
**Status:** Interim report at ~6h / 73 polls. Autonomous run continues to ~24h / 288 polls; the conclusion below is already decisive and is not expected to change.

---

## The thesis being tested

Polymarket prices the **Balance of Power: 2026 Midterms** event as 4 mutually-exclusive joint outcomes (+ "Other") that must sum to 1, and *also* prices standalone single-chamber control markets on the **same venue / same Nov-3-2026 resolution**. Two algebraic identities must therefore hold:

```
P(D House)  == P(Dem Sweep) + P(R-Senate / D-House)
P(D Senate) == P(Dem Sweep) + P(D-Senate / R-House)
```

If the standalone chamber market ever disagrees with the derived marginal **beyond the bid/ask spread and fees**, a riskless same-venue package exists. The thesis: a slow cron operator — disadvantaged on speed everywhere else — could harvest this because it needs *patience, not latency*.

**Kill criterion:** over a day, the violation never exceeds the spread at fillable size → the book is already coherent (bots arb it) → no edge. A clean null result is the expected modal outcome.

## Method

- Self-contained probe (`backend/scripts/coherence_arb_probe.py`, stdlib-only) polls the CLOB order books for all 7 relevant legs every 5 min.
- Computes both identities in **both directions**:
  - **Net taker gap** = gross cross-spread gap − Polymarket politics taker fee.
  - **Maker mid gap** = identity violation at mid prices, fee-free (makers pay 0) — the best case for the doc's maker-only thesis, ignoring fill/leg risk.
- Paper-trades the $1,000 book only on a **net-positive, fillable, riskless** taker gap.
- Arb algebra independently verified by Codex (riskless construction, correct signs).

### The fee correction (caught mid-build)

These markets are **not** fee-free. The live `feeSchedule` is `{rate: 0.04, takerOnly: true, rebateRate: 0.25}`:

```
taker fee per share = 0.04 × price × (1 − price)   (~1¢/share at 50¢; makers pay 0)
```

For the 3-leg taker package this is ~2.5¢/share of fees, so a taker arb needs a **gross gap > ~2.5¢** just to break even.

## Results (73 polls, 2026-06-04 10:03–16:06 UTC)

| Identity / direction | Net taker gap (after fee) | Maker best-case (mid, fee-free) | Distinct values |
|---|---|---|---|
| house / cheap  | **−4.50¢** | −0.50¢ | 1 |
| house / rich   | **−3.54¢** | +0.50¢ | 1 |
| senate / cheap | **−2.25¢** | +0.85¢ | 1 |
| senate / rich  | **−3.95¢** | −0.85¢ | 1 |

- **Best net taker gap ever:** −2.25¢ (needs > +0.5¢ to trade) → **no riskless taker arb at any poll.**
- **Best maker mid gap ever:** +0.85¢; cleared a full 1¢ tick in **0 of 292 observations** → maker incoherence is sub-tick.
- **Paper fills:** 0. **Capital deployed:** $0. **Pretend bankroll:** $1,000.00 intact.

### The book is frozen, not just coherent

Every leg's top-of-book price was **identical from the first poll to the last** (D-House ask 0.820, Dem-Sweep bid 0.440, R-Sen/D-House bid 0.360, …) — `distinct=1` on all four checks across 6 hours. This is *not* a data artifact: the *size* at each level churns poll-to-poll (e.g. D-House top size 1728 → 2047 → 2020), proving live order-book reads. Only the touch *prices* are sticky — deep queues on a 1¢ grid.

## Verdict

**The thesis is dead, in its strongest form.** Not merely "the gap is small" but "the book is so coherent and so static there is nothing to act on":

1. **As a taker:** doubly dead — gross gap already negative, and the 4% politics fee adds ~2.5¢. Would need a ~4¢ dislocation; never observed.
2. **As a maker (the doc's actual thesis):** the incoherence is **sub-tick** (±0.5–0.85¢ < 1¢ grid). You cannot even rest a limit at the price that would capture it, and any attempt carries un-modeled leg-fill / adverse-selection risk.
3. **No intraday churn to exploit.** On a deep $7.5M event 5 months from resolution, the marginal price doesn't move intraday. The "transient dislocation" the thesis would need either doesn't occur or is arbed sub-second by bots, invisible at a 5-min poll — and a slow operator can only act at cron cadence anyway.

This is the **modal outcome the strategy doc predicted**, reached for ~$0 and zero capital risk. It closes the last structurally-defensible trading angle: there is no slow-operator edge in same-venue election coherence on Polymarket.

### Honest caveat
5-min polling cannot see sub-5-min dislocations — but that is *faithful* to the strategy (a cron operator can't act faster anyway), not a flaw. The only thing that could revive a window is a genuine news shock (candidate drop-out, indictment, major poll) repricing one chamber before the joint legs catch up; the full-day run across all trading hours is the fair test for that, and the prior is now very low given how inert the book is.

---

*Final tally (288 polls) will be appended when the autonomous run completes ~2026-06-05 10:03 UTC. Live data: `ssh Jarvis 'tail -25 /root/parallax-data/coherence_check.log'`.*
