# Architecture

Two codebases live in this repository, and telling them apart is the single
most useful thing to know before reading any of it.

**Phase 1 (March–June 2026)** built a geopolitical forecasting pipeline: ingest
news, run LLM ensembles, compare against market prices, paper-trade the
divergences. Its thesis was falsified. The code is kept because the evaluation
machinery is genuinely good and because the null result is only trustworthy
while the machinery that produced it still exists.

**Phase 2 (September 2026–)** asks whether two venues price the same event
inconsistently. It needs no forecast. It is `parallax.arb` plus the two market
clients, and nothing else.

If you are here for arbitrage, you need roughly 1,700 lines of the ~15,000.

---

## The Phase 2 path

```
  pairs.py                     venue.py / adapters.py
  ────────                     ─────────────────────
  MarketPair                   KalshiVenue ──▶ KalshiClient ──▶ Kalshi API
   ├─ yes_leg  ──────────┐                                         │
   ├─ no_leg   ────────┐ │     PolymarketVenue ──▶ PolymarketClient┘
   ├─ deadline         │ │              │
   ├─ resolution_source│ │              ▼
   ├─ void_rules       │ │           Quote  (sorted executable depth,
   └─ reviewed ✋       │ │                   stamped with observed_at)
         │             │ │              │
         │             ▼ ▼              ▼
         └────────▶  scanner.evaluate(pair, yes_quote, no_quote, …)
                            │
                            │  walk both ask ladders in parallel
                            │  subtract BOTH venues' fees per step
                            │  stop where the edge dies
                            ▼
                     ArbOpportunity   (packages, net_profit, quote ages)
```

### The unit is a package, not a price

A price difference between venues means nothing on its own. What is tradable is
a **package**: one contract of the YES leg on venue A plus one contract of the
complementary NO leg on venue B. If the legs are true complements, exactly one
settles at $1.00, so a filled package is worth exactly $1.00 regardless of
outcome.

```
profit_per_package = 1.00 − ask_yes − ask_no − fee_yes − fee_no
```

Depth is walked in parallel across both ladders, so the package count is capped
by the thinner venue at every step. A thousand contracts on Kalshi behind five
on Polymarket is a five-package opportunity.

### Three gates that exist to stop fake edges

| Gate | Where | Refuses |
|---|---|---|
| Settlement review | `pairs.MarketPair.require_reviewed()` | Scanning a pair whose rule sets no human has read. Same-event ≠ same-payout, and basis risk reported as arbitrage is worse than no signal. |
| Staleness | `scanner.evaluate(max_quote_age_seconds=30)` | Books too old to be executable. Cross-venue scans on stale quotes are the classic source of phantom edge. |
| Fees, per step | `fees.KalshiFees` / `fees.PolymarketFees` | Depth that is profitable gross and unprofitable net. Kalshi rounds fees **up to the next cent per order**, so thin packages are structurally dead. |

### What `arb` deliberately does not do

It does not execute, and it does not contain a paper-trading book. The Phase 1
probe had one, and its notion of "locked profit" assumed both legs always fill.
Two independent venues offer no atomic execution: one leg fills, the other
moves, and the hedge becomes a naked position unwound at a loss. An
`ArbOpportunity` is an **upper bound on what was quotable**, not a fill. Leg
risk, latency, partial fills and adverse selection are unmodeled — a live
attempt has to add them, not assume them away.

---

## Module map

### Shared — used by both phases

| Module | Lines | What it does |
|---|---|---|
| `markets/kalshi.py` | 460 | Kalshi client, RSA-PSS request signing. Normalizes into `Orderbook` / `MarketPrice`. Search narrows server-side on ticker-shaped queries, then paginates with a page cap. |
| `markets/polymarket.py` | 273 | Polymarket read-only client. **Returns raw CLOB dicts** — normalization lives in `arb/adapters.py`. Still carries `get_iran_markets()`, a Phase 1 leftover. |
| `markets/schemas.py` | 137 | `Orderbook`, `MarketPrice`, `OrderbookLevel`, `DepthSummary`. Draws the line between executable quotes and derived display prices. |
| `db/` | 833 | DuckDB schema (20+ tables) and writers. |
| `config/` | 116 | Settings and environment loading. |

### Phase 2

| Module | What it does |
|---|---|
| `arb/venue.py` | The `Venue` protocol: outcome-addressed, read-only, sorted depth, mandatory timestamps, `None` (never an empty book) for missing data. |
| `arb/adapters.py` | `KalshiVenue` and `PolymarketVenue`. Wraps both clients without modifying either; converts prices via `str` into `Decimal` so no float error leaks in. |
| `arb/fees.py` | Exact fee arithmetic. Kalshi: `ceil_to_cent(0.07 × C × P × (1−P))`, maker = 25% of the *rate*, rounded independently. Polymarket: `rate × P × (1−P)`, taker-only, **rate defaults to zero** so no market inherits the politics rate by accident. |
| `arb/pairs.py` | `MarketPair` + the review gate. Registry ships empty on purpose. |
| `arb/scanner.py` | Package accounting and the depth walk. |

### Phase 1 — concluded, retained as evidence

| Module | Lines | Note |
|---|---|---|
| `scoring/` | 3,575 | Ledger, calibration, recalibrators, scorecard, resolution. The most reusable Phase 1 work; `calibration.py` and the recalibrators were spun out into the `calibration-arena` repo. |
| `cli/` | 1,754 | `brief.py` orchestrates the whole Phase 1 pipeline. |
| `dashboard/` | 1,317 | Query layer for the deleted React dashboard. FastAPI endpoints still serve. |
| `backtest/` | 1,313 | Look-ahead-safe backtester. |
| `prediction/` | 1,257 | LLM ensemble and the three crisis models. |
| `contracts/` | 1,042 | Registry and proxy-aware mapping with edge discounting. |
| `portfolio/` | 974 | Quarter-Kelly sizing. |
| `ingestion/` | 841 | Google News RSS, GDELT, EIA oil prices, Truth Social. |
| `ops/` | 537 | Run events and health. |
| `simulation/` | 345 | The 6-rule physical cascade engine. |
| `bench/` | 336 | KalshiBench calibration harness — standalone, needs no market access. |
| `divergence/` | 144 | Model-vs-market divergence detection. |
| `budget/` | 84 | $20/day LLM spend cap. |

### Scripts

| Script | Note |
|---|---|
| `scripts/coherence_arb_probe.py` | The Phase 1 probe. Ran live on Jarvis; found the Polymarket book coherent to sub-tick precision across 292 observations. **Superseded by `parallax.arb`** — it bypasses the clients entirely and is single-venue. Kept for reproducibility. |
| `scripts/coherence_arb_report.py` | Report generator for the above. |
| `scripts/cron_pipeline.sh` | Phase 1 unattended run wrapper. |

---

## Known debt

- **24 failing tests**, all in the Phase 1 pipeline (`test_scorecard.py` ×10,
  `test_phase1_critical.py` ×4, `test_crisis_context_db.py` ×4,
  `test_brief_resilience.py` ×3, plus three singletons). Mostly DuckDB schema
  drift. Nothing on the Phase 2 path fails.
- **`PolymarketClient` is not symmetric with `KalshiClient`** — it returns raw
  dicts where Kalshi returns models, and it still carries the crisis-specific
  `get_iran_markets()`. `arb/adapters.py` papers over this; fixing the client
  properly would let the adapter shrink.
- **`pairs.REGISTRY` is empty.** Phase 2 cannot report anything until somebody
  reads two rule books and registers a reviewed pair. That is the actual next
  task, and it is human work, not code.
