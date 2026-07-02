# Parallax — Path to Profitability: Theses, Failure Gates & Plan

_Author: strategy research session, 2026-06-03. Evidence base: 7 web-grounded research agents + Codex + Gemini cross-checks + primary-source fee/billing verification + the project's own logged data + an independent break-even model. Every non-obvious claim below was triangulated across ≥2 independent sources._

---

## 0. TL;DR — the honest verdict

**The original Parallax thesis — "LLM forecasts an outcome, we trade the divergence from the market price" — is the configuration the evidence says _loses_.** There is, as of mid-2026, **zero documented case of a standalone LLM-reasoning system profitably trading a real-money prediction market.** Frontier LLMs now beat the _generic_ crowd but consistently lose to elite forecasters **and to the liquid-market consensus they would be betting against** (Metaculus AI Benchmark Q2'25: humans crushed bots, p=0.00001, and the gap is _widening_; AIA Forecaster — the strongest published agentic forecaster — still underperforms the market on hard liquid questions).

**The binding constraint is not prediction skill. It is execution.** Parallax's own logged data is the loudest signal in the project: **75 signals, 67 of them `REFUSED` (89%) for having no executable quote, only 5 ever resolved, and realized P&L is entirely `NULL` — zero executed trades, zero validated edge.** The system has never demonstrated it can even _find a fillable, resolvable, correctly-mapped market_, let alone beat it.

**Realistic financial ceiling:** on a $5k bankroll, **$0–300/month _if_ a genuine net-of-fee edge exists**, realized only _after_ ~6 months and 300+ settled trades prove the edge is real. The most likely honest outcome is **~$0 or slightly negative while you learn.** The base rate is brutal: across 2.5M Polymarket wallets, **84% lost money; durable winners are <1% and are almost all speed/arbitrage bots, not reasoners.** Treat this as an **R&D / skill-building project**, not a revenue stream.

**An adversarial kill-pass on all five candidate strategies returned _zero_ "promising" verdicts** — two are **dead-on-arrival** (cross-venue arb; sports props) and three are **high-risk / structurally doomed** (favorite-longshot harvest; niche-LLM edge; slow-news depth). The single most important correction the adversary forced: **even _makers_ lose ~12% on average on Kalshi** (takers −31%; Burgi/Deng/Whelan) — the exchange's rake is the house edge, and the favorite-longshot "edge" is microscopic (+1–3% gross, capital-locked, _weakening_ in 2025 data, possibly a rake artifact, not alpha). So there is **no structural free lunch.**

**The only intellectually-honest framing left is: treat this as a cheap, falsify-first R&D experiment, not a strategy you commit to.** If anything survives, it survives _only_ under this exact doctrine (the common "survives-only-if" across every adversary):
1. **Maker-only**, resting limits away from 50¢, held to settlement (takers are negative-EV by construction).
2. **LLM as a market-anchored _tilt_, never ground truth** — gate on a blend ≈ ⅔ market + ⅓ LLM, cap how far the LLM moves off the market price. (Divergence-override = the documented losing config.)
3. **Hard tradability + resolution-clarity gate _before_ the LLM runs** (fixes the 89% `REFUSED`; CFTC-cleared Kalshi preferred; avoid UMA whale-capture).
4. **Validate on CLV (closing-line value) + net-of-cost calibration over 100+ resolved markets with realistic-fill simulation — before risking one dollar.**
5. **Accept the ceiling is beer money** (single-digit-to-low-hundreds $/mo), and **run the $0 falsification tests _first_** — most angles die there, for under $10.

**On the Claude Max cron lever:** it both **closes in 12 days and was never needed.** As of **June 15, 2026**, headless `claude -p` / Agent SDK on a subscription is metered at API rates (Max 20x = ~$200/mo credit, then fails closed) — confirmed in Anthropic's own docs. But Parallax's forecasting hot path costs **~$1–5/month at plain metered API rates** (3 Sonnet calls ×2/day). The move is: **switch the cron to a static `ANTHROPIC_API_KEY` now** (also fixes the fact that headless OAuth tokens die every ~8h and Anthropic won't fix it — `claude -p` on a subscription token is fundamentally broken for unattended cron). Claude Code cron remains the right _scheduler_; just don't depend on the Max "free compute" loophole.

---

## 1. What the evidence actually says (the findings that drive everything)

| # | Finding | Implication | Confidence |
|---|---------|-------------|-----------|
| 1 | **LLMs don't beat liquid markets.** No documented profitable LLM-reasoning directional trader. AIA Forecaster (best published) loses to market consensus on hard markets. Metaculus gap to humans _widening_. | Stop treating the LLM probability as alpha/ground-truth. | High |
| 2 | **But a market-anchored _blend_ beats the market.** AIA: ≈⅔ market + ⅓ LLM Brier-beats market-alone on hard sets. The LLM adds _diversifying_ info even when it loses head-to-head. | Re-architect the signal: LLM may _nudge_ the price by a bounded amount; trade only when the _blend_ diverges. | High |
| 3 | **News context _backfires_ for LLM forecasts** (recency bias, rumor overweighting; documented accuracy drops). Parallax is 100% news-RSS-driven — the exact failure pattern. | Add a base-rate/outside-view anchor the news cannot override; ablation-test with/without news on resolved markets. | Med-High |
| 4 | **Takers lose ~32%, makers ~-10%** (UCD Jan'26, 300k contracts; a 72M-trade study found makers +2.5%/trade). Kalshi maker fee = 25% of taker ≈ **$0** after rounding. Polymarket US makers get a **rebate**. | **Maker-only execution is non-negotiable.** Any strategy needing immediate fills is structurally dead. | High |
| 5 | **Favorite-longshot bias is the cleanest documented edge.** Kalshi 5¢ longshots win ~4%; 80–95¢ favorites win 96–98% and yield small _positive_ net-of-fee returns. Persists across categories. | A portfolio tilt that needs no prediction genius — fade longshots / favor favorites, as a maker. _But it's now public (UCD paper) → decaying._ | High |
| 6 | **Cross-venue arbitrage is dead for you.** Windows ~2.7s avg, median spread ~0.3%, 73% of profit to <100ms bots. Deep global Polymarket is **geofenced from US**; legal access (Polymarket US/QCEX) is **thin**. Resolution mismatches can lose _both_ legs (documented Kalshi Rule 6.3(c) vs UMA case). | **Kill Thesis A (cross-venue).** A cron droplet cannot compete on speed, and the juicy book is one you can't legally trade. | High |
| 7 | **Soft money lives in niche/long-tail politics, policy & geopolitics** (Polymarket: 121 legislation, 590 geopolitics markets). Concrete mispricings (CLARITY Act 82→46→73%; House-district markets move 2–3¢/trade, 40–80% returns in weeks). **Macro/crypto/weather/sports are efficient or speed-bot-owned.** Mid-tier ($50k–250k volume) is the sweet spot. | This is where your existing engine already points. But the best liquidity is on Polymarket (US-thin), and thin markets cap size. | High |
| 8 | **Kalshi does NOT ban winners** (CFTC DCM, doesn't take the other side) — unlike sportsbooks, which limit/ban sharps within 6–12 months. | **The prior "pivot to NFL/NBA props via SportsGameOdds $99/mo" is a step _down_ in durability** — it inherits the ban treadmill. De-prioritize it. | High |
| 9 | **Resolution risk (Polymarket): 1,150+ disputed markets in 2026; UMA "whale capture"** (>50% of votes from 10 largest wallets). You can be _right and still lose_. | Prefer CFTC-cleared Kalshi, or only crisply-worded, objective-source Polymarket questions. Add a resolution-clarity gate. | High |
| 10 | **Base rate: 84% of traders lose; durable winners <1%, mostly bots.** Realistic $ at $5k even with a real 3–5% edge: tens-to-low-hundreds/mo. | EV is plausibly ~$0/negative. Validate before funding. Frame as R&D. | High |

---

## 2. The reframe: invert the funnel

Today Parallax runs **news → LLM forecast → _try_ to find a contract** — which is why 89% of signals are `REFUSED`. Both independent reviewers (Codex, Gemini) and the research converge on the same fix:

```
  markets universe
      │  (1) TRADABILITY GATE  — liquidity depth ≥ target, spread ≤ target, objective resolution, CFTC-cleared or crisply-worded
      ▼
  fillable, mappable, resolvable candidates only   ← the LLM never wakes up before here
      │  (2) MAPPING — exact contract definition, settlement source + date
      ▼
  (3) MARKET-ANCHORED BLEND — p_blend = w·p_market + (1-w)·p_LLM,  w≈⅔,  |p_LLM−p_market| capped
      │  (4) FEE/SPREAD EV GATE — net_edge = p_blend − price − maker_fee − (spread only if forced to take)
      ▼
  (5) MAKER ORDER (resting limit, away from 0.50 where fees peak), hold to settlement
      ▼
  (6) LOG → SETTLE → calibration feedback → recalibrate
```

**Your real product is a fillable-market discovery + EV-accounting engine, with the LLM as a calibrated tilt — not an LLM forecaster.** This single inversion is the highest-leverage change in the whole plan.

---

## 3. The five candidate strategies, graded by adversarial kill-pass

An independent adversary was tasked to _kill_ each angle. **None survived as "promising."** Ranked by what's left standing:

### 🟧 Least-doomed (HIGH-RISK, worth a _cheap_ test) — Thesis 2: Niche/long-tail policy & geopolitics, market-anchored blend, maker-only, hold-to-settlement
**Mechanism:** Be the marginal _informed_ trader in under-covered, slow-moving markets (legislation, confirmations, sanctions, foreign elections, conflict outcomes), using compute for _depth_, but trading the **blend** (⅔ market + ⅓ LLM), holding to settlement.
**Why it's the best of a bad set:** It's literally what Parallax already does; geopolitics is the LLM's _strongest_ domain (~84%); slow resolution means fees matter less.
**Adversary's fatal flaws:** (1) liquidity-vs-edge squeeze is self-defeating — the softest markets are the thinnest (median ~$9k total staked; $500–1,000 walks the book 3–5¢); (2) AIA evidence says the LLM _loses_ to consensus head-to-head (only the blend helps); (3) resolution risk (1,150+ UMA disputes, "right and still lose"); (4) dollar ceiling = beer money; (5) institutions are now here (Galaxy's $10M CLARITY Act bet; Polymarket's first institutional block trade, June 2 2026). **Verdict: high-risk.**

### 🟧 Second (HIGH-RISK) — Thesis 3: Slow-news depth on crisp, objective, document-resolving markets
**Mechanism:** Claude reads long primary docs overnight; trade markets that resolve objectively on them before the slow crowd digests.
**Adversary's fatal flaws:** (1) this is **PEAD** (post-earnings drift) "on event contracts" — and PEAD on structured public disclosures **died ~2006** once machines focused on it; (2) a U-Chicago study of a SCOTUS market found long briefs produced **zero** price movement (the market moved live at oral argument); (3) the "slow crowd" now includes event-driven/policy desks running the _same_ LLM stack; (4) finance/numeric/document resolution is the LLM's **worst** domain. **Verdict: high-risk.** _But it has the single cheapest $0 falsification test (see §4)._

### 🟥 Demoted from "strongest" to a portfolio _prior_, NOT a thesis — Favorite-longshot harvest
I initially ranked this first. **The adversary killed it (dead-on-arrival)** and the correction is decisive: the academic source shows **makers lose ~12% on average** (the rake is the house edge); the favorite over-performance is only **+1–3% gross, capital-locked, concentrated above 70–90¢, and _weakening_ in 2025**; a credible critique argues it's a **rake artifact, not exploitable alpha**; and capturing even that requires winning the adverse-selection fight against Susquehanna on resting orders a cron droplet refreshes too slowly. **Keep only as a small _directional prior_ inside the blend (lean to favorites, avoid extreme longshots), never as a standalone income strategy.**

### 🟥 Dead-on-arrival — Thesis A: Cross-venue arbitrage
Speed wall (~2.7s windows, 73% to <100ms bots); the deep global Polymarket book is **US-geofenced** (the divergences you'd trade are on a venue you can't legally access); resolution mismatch loses _both_ legs (Khamenei ouster: Polymarket paid $529M YES while Kalshi is _barred from listing_ the contract — no hedge leg exists). A neutral tracker showed **0 validated arbs on 2026-06-03.** **Dead.**

### 🟥 Dead-on-arrival — Thesis E: Sports player-props via SportsGameOdds ($99/mo)
The SGO consensus **is the input the prop market-makers already use** — you'd pay $99/mo to see what the counterparty already priced; props are a sub-minute latency game (wrong machine); sports/finance is the LLM's worst domain; ~15% hold and **accept-only RFQ pricing** (you can't be a maker on props); plus the sportsbook ban-treadmill and live SCOTUS delisting risk. **Dead. This formally retires the prior "pivot to sports props" recommendation.**

---

## 4. The failure-gate gauntlet — fail fast, fail free

The goal of the next ~6 months is **not profit — it is to answer, as cheaply as possible: _does a net-of-fee, market-anchored edge exist at all?_** The structure is deliberately back-to-front: **the cheapest, highest-kill-probability tests run first**, several with **$0 and no bankroll**, _before_ you build anything. Most angles are expected to die in Stage A. That is the gauntlet _working_.

### Stage A — The $0 falsification gauntlet (Weeks 0–3, ~$10 of API, zero capital)
Run these _before_ building the trading harness. Each is a pre-registered kill switch (tests lifted directly from the adversarial kill-pass).

| Test | What you do (no capital, ~no LLM) | KILL if… | Kills |
|------|-----------------------------------|----------|-------|
| **A1 · Slow-news lag** | For 15–25 _already-resolved_ document-driven markets, scrape the market price 1h before / 1h after / 24h after the resolving document's public release timestamp. | Price already moved to within ~3–5¢ of final resolution **within 1h** of release → no tradeable digestion window exists. | Thesis 3 |
| **A2 · Cross-venue gap** | 14-day read-only logger polling Kalshi + Polymarket-US every ~5 min for identically-defined, same-source, same-date contracts; record net divergence after both venues' fees + slippage to fill a $500 ticket, and how long any net-positive gap persists. | Zero same-event pairs clear net-positive beyond one 5-min poll over 14 days (the live tracker already shows 0 on 2026-06-03). | Thesis A |
| **A3 · Sports-prop CLV** | 2–3 weeks (skip the $99 SGO feed): log Kalshi single-game prop mid-prices at your cron-fire times; record closing price + resolution; compute CLV + net EV after fee+spread, accept-only execution. | Cron-timed entries don't beat the closing prop line by **more than round-trip cost**. | Thesis E |
| **A4 · Maker fill realism** | 60-day paper: place _only_ resting limit (maker) buy orders on ≥70¢ favorites across 30–50 crisp Kalshi contracts; record **fill rate** and each fill's timestamp **relative to news**. | Your good prices don't fill while bad ones do (adverse selection), OR fill-inclusive return after ceil-rounded fee + lockup isn't clearly positive over 100+ settled. | Favorite-longshot prior |

**Expected Stage-A result, stated honestly up front:** A2 and A3 almost certainly return "dead" (they're already known-dead from the research). A1 likely returns "no window." A4 likely returns "flat-to-negative" (consistent with the −12% maker average). **If all of Stage A dies — which is the modal outcome — you stop here, having spent ~$10 and risked $0.** Only an angle that _survives_ Stage A earns Stage B.

### Stage B — Build + forward-validate the survivor(s) (Months 1–4)
Only if something survived Stage A. Build the inverted-funnel harness (§5) and run a forward paper-trade validation.

| Gate | Must clear | KILL if… |
|------|-----------|----------|
| **B0 · Plumbing** (wk 1) | Cron on static API key; tradability gate surfaces ≥ **40 tradable, mapped, resolvable candidates/week** (vs today's 89% REFUSED). | < 20/week sustained → the funnel can't feed itself. |
| **B1 · Calibration** (≥ 80 resolved) | Blend (⅔ market + ⅓ LLM) is **not worse-calibrated than the market**; Brier(blend) ≤ Brier(market). | Blend ECE materially worse than market → LLM adds noise, not signal. |
| **B2 · CLV + net-of-fee P&L** (≥ 150 resolved, realistic-fill sim: ~6¢ realized spread, 3–5¢ slippage on $500–1,000) | Entries beat the **closing/settlement-converging price (CLV > 0)** AND cumulative net-of-fee paper P&L > 0. | CLV ≤ 0 or net P&L ≤ 0 → no real edge. _This is where most survivors die._ |
| **B3 · Significance + robustness** (≥ 200–380 resolved, per §6) | Win-rate distinguishable from break-even at ~90%+; edge **stable across ≥ 2 categories**. | Not significant, or edge is one-theme luck. |

### Stage C — Live micro-stakes, then decision (Months 5–6)
| Gate | Must clear | KILL if… |
|------|-----------|----------|
| **C1 · Micro-stakes** | Deploy **$200–500 real** at maker prices; live net-of-fee P&L tracks paper within tolerance. | Live materially worse than paper (real resting orders get adverse-selected). |
| **C2 · Decision** | Scale toward the $5k bankroll **only** if B1–B3 + C1 all cleared. | Any gate unmet → stop, or stay permanently at micro-stakes as a hobby. |

**Brutally honest expectation:** the modal outcome is death in **Stage A or at B2 (CLV/net-P&L)**. Treat reaching that verdict for **<$50 and $0 bankroll risk** as the _success case_ of this entire effort — it's the difference between learning "no edge" for the price of a coffee vs. bleeding the $5k to find out.

---

## 5. The concrete build plan (in order)

**Phase 0 — Stop the bleeding & re-point the engine _(days, do before June 15)_**
- Migrate the cron from Max-OAuth / `claude -p` to a **static `ANTHROPIC_API_KEY`** (Commercial Terms): fixes the 8-hour OAuth-token-death cron failure and the June-15 billing cliff. Forecasting stays ~$1–5/mo.
- Switch forecasting model **Opus → Sonnet** (numeric/finance reasoning isn't Opus-worthy here; cost ↓ ~5×). Wire `budget/tracker.py` to real metered spend with an alert.
- **Demote the oil-price (numeric/finance) model to context-only** — it's in the single worst LLM forecasting category and is likely negative-EV.
- Generalize the 3 hard-coded Iran models into **one parameterized "event-probability" model** (topic + resolution criteria + evidence as inputs), so the engine can point at any policy/geopolitics market.

**Phase A — The $0 falsification scrapers (Weeks 0–3, BEFORE the trading harness)**
- Build only **read-only scripts**, not the trading engine: A1 a document-release-vs-price scraper, A2 a Kalshi↔Polymarket-US divergence logger, A3 a Kalshi prop-price-vs-close logger, A4 a maker-fill paper simulator (resting limits on favorites, fill-rate + news-timestamp logging). These reuse the existing Kalshi/Polymarket read clients; none needs the LLM forecaster.
- Run the **Stage-A gauntlet (§4)**. **Stop here if all four die — the modal outcome.** Only build Phase 1+ for a survivor.

**Phase 1 — Tradability gate (the funnel inversion) _(1–2 weeks; survivors only)_**
- Market scanner that pulls Kalshi + Polymarket-US universes and **filters BEFORE forecasting**: min book depth (category-appropriate), max spread, objective/CFTC-cleared resolution, crisp wording. Output: a daily list of fillable candidates.
- Add a **resolution-clarity classifier** (LLM scores wording ambiguity + whale-resolution exposure; skip subjective questions).
- Direct fix for the 89% `REFUSED` rate — tradable-candidate count is the KPI (Gate B0).

**Phase 2 — Market-anchored blend + calibration _(1–2 weeks; survivors only)_**
- Replace the divergence-override with `p_blend = w·p_market + (1−w)·p_LLM` (start w≈0.67), with `|p_LLM − p_market|` **capped** so the LLM can only nudge.
- Make `scoring/recalibration.py` **gating, not optional**: multiple LLM runs per question, post-hoc isotonic/Platt calibration before any sizing.
- Encode the **favorite-longshot tilt** as a prior in the blend (lean toward favorites, fade extreme longshots).

**Phase 3 — Maker paper-trading harness _(1 week; survivors only)_**
- Execution = **resting limit (maker) orders**, never market orders; prefer conviction prices **away from 0.50**; hold to settlement.
- EV gate: trade only if `p_blend − price − maker_fee − realistic_slippage > threshold` (threshold ≥ ~3pts to absorb model error/adverse selection).
- Realistic fill simulation (don't assume you get filled at mid — apply ~6¢ realized spread / 3–5¢ slippage).

**Phases 4–5 — Run Stage B (forward validation, months 1–4) → Stage C (micro-stakes, months 5–6) → the decision**, exactly per the gates in §4.

---

## 6. The numbers (your own break-even & validation math)

**Break-even gross edge you must beat the price by (Kalshi, hold-to-settlement, entry-only):**

| Price | Maker fee | **Taker** fee (¢) | Fee as % of capital-at-risk | BE edge @2¢ spread (taker) |
|------|-----------|-------------------|------------------------------|----------------------------|
| 0.10 | ~$0 | 0.63 | **6.3%** (longshot tax) | 1.63 pt |
| 0.50 | ~$0 | 1.75 | 3.5% | 2.75 pt |
| 0.90 | ~$0 | 0.63 | 0.7% | 1.63 pt |

→ As a **maker**, the fee ≈ $0, so break-even ≈ your slippage only. As a **taker** at 50¢ you need ~2.8pt just to break even. **Avoid mid-priced takes; prefer maker orders at the extremes** (cheap fee + favorite-longshot aligned).

**Realistic monthly P&L on $5k (only if net edge is real):**

| Scenario | trades/day | avg stake | net edge | **$/mo** | %/mo |
|----------|-----------|-----------|----------|----------|------|
| Pessimistic | 2 | $30 | 2.0 pt | **$80** | 1.6% |
| Base | 3 | $50 | 3.5 pt | **$350** | 7.0% |

_(The "5–8 trades/day at 5–6pt edge" fantasy that yields 20–50%/mo compounds two improbable things — ignore it.)_

**Validation sample size (distinguish a true win-rate from a coin-flip, 95% conf):**

| True win-rate | Settled trades needed | Months @3/day |
|---------------|----------------------|----------------|
| 0.52 | ~2,400 | 27 |
| 0.55 | ~380 | 4.2 |
| 0.60 | ~92 | 1.0 |

→ **A 55% edge needs ~380 settled trades to _prove_ — roughly the entire 6-month window.** This is why the gauntlet is about validation, not income, and why a thin 52% "edge" is effectively unprovable at retail volume. (An independent quant pass put the range at **~1,000–60,000 settled trades** depending on how thin the net edge is — i.e. _years_ for the slow markets the LLM actually fits.)

**Per-thesis realistic monthly P&L on $5k (independent quant agent, consistent with the above):**

| Thesis | Req. gross edge | Realistic $/mo | Clears fees? |
|--------|----------------|----------------|--------------|
| Favorite-longshot tilt (prior) | ~2 pp | **+$50–90** (most reliable, capital-locked, weakening) | medium |
| Niche/illiquid LLM blend | ~8 pp | +$40–80 _if_ a real 3% edge exists; realistically ~0 or negative | low |
| Slow-news depth | ~6 pp | +$20–40 _if_ 1.5% net edge holds; plausibly ~0 | low |
| Cross-venue RV | ~6 pp | $0 to −$30 (net edge ≈ 0 after costs) | very-low |
| Sports props (SGO $99/mo) | ~6 pp | **−$200 to −$350** (data cost + fee drag + losing to SIG oddsmakers) | very-low |

Quant's verdict, verbatim in spirit: _"expected financial value near 0 or negative, with the favorite-longshot tilt as the one defensible small positive-EV component."_ Note the one nuance vs the adversary: the quant is slightly **more** charitable to the favorite-longshot tilt — it's the single component with a small _positive_ after-fee expectation (~+$50–90/mo) — but only as a capital-locked, weakening, favorite-side-only _tilt_, never income. Both agree it cannot be a business.

---

## 7. The Claude Max / cron question, answered directly

- **The "free Max 20x cron compute" lever closes June 15, 2026** (Anthropic docs, confirmed): headless `claude -p` / Agent SDK draws from a metered credit (Max 20x ≈ $200/mo at API rates, then **fails closed** silently). It also **never auto-refreshes OAuth tokens** for unattended use (dies ~8h; Anthropic marked the fix "won't do").
- **You don't need it.** Forecasting is ~$1–5/month at plain metered API rates. **Use a static `ANTHROPIC_API_KEY`** — cheaper than the sub for this workload, no ToS gray area, no token-death cron failures, no fail-closed surprise.
- **Keep ingestion deterministic & free** (Google News RSS, GDELT, EIA, official APIs). Do **not** use an LLM agent to scrape — that's the only thing that would burn real money.
- **Claude Code cron is still the right _mechanism_** for scheduling ingestion → forecast → paper-trade → settle. Just authenticate with the API key and run Sonnet. Heavy "read a 200-page filing" deep-research runs (Thesis 3) can still go through Claude Code, but budget them and keep them rare.

---

## 8. Bottom line — when to walk away

Pursue this as a **disciplined R&D project with a hard kill-switch**, not an income play. Build Phases 0–3, run the gauntlet, and **let the gates make the decision for you.** If Gate 2 (calibration) or Gate 3 (net-of-fee paper P&L) fails — which is the most probable outcome — **stop**, having spent <$50 and risked $0 of bankroll. If they pass, you'll have something genuinely rare: a _validated_, fee-inclusive, market-anchored edge worth scaling. Either way, you'll _know_, instead of hoping.

---

## 9. Addendum (2026-06-03b): new angles evaluated — Perplexity, Senate, World Cup, social media, AI-bots

A second 11-agent research+adversary workflow (+ Gemini cross-check) evaluated five new ideas the operator raised. **New 2026 evidence strengthens the prior:** live trials now exist — **Prediction Arena: all 6 frontier LLMs (incl. Claude Opus 4.5) _lost_ 16–31% live-trading Kalshi; PolyBench: any LLM profit is a micro-lot artifact that collapses to a loss at $1k positions; MixMCP: only a ~70%-market/30%-LLM blend beats the market, by ~0.005 Brier (mid-confidence only).** Also: the "news degrades forecasts" effect is **domain-dependent** (helps Finance/Sports, hurts Entertainment/Tech). And a key fee fact: **Polymarket US pays makers a ~0.20% _rebate_** (negative fee), while **Kalshi charges 0.25% maker fee on election contracts** (punishing on cheap legs).

### ⭐ The one genuinely new, defensible idea — Senate "Balance-of-Power" coherence arbitrage
This is the standout of both research turns, because it **exploits structure (algebra), not prediction** — the one place a slow cron operator is _not_ disadvantaged (needs patience, not latency; beats no informed trader, only internal inconsistency).

- **Mechanism:** Polymarket's "Balance of Power 2026" event prices 4 mutually-exclusive joint outcomes that must sum to 1 (live June 3: Dem Sweep 45%, R-Senate/D-House 37%, R-Sweep 18%, D-Senate/R-House ~1.8%; ~$7.5M vol). Two **algebraic identities are true arbitrage**: `P(D House)=P(Dem Sweep)+P(R-Senate/D-House)` and `P(D Senate)=P(Dem Sweep)+P(D-Senate/R-House)`. When the standalone House-control / Senate-control markets disagree with these derived marginals beyond fees, post **maker-only limits to assemble the full offsetting package, same-venue, same-rules.**
- **Venue:** Polymarket US (un-geofenced since Dec 2025, CFTC DCM) — maker **rebate** makes assembling the package free-to-paid. _Avoid Kalshi legs_ (0.25% election maker fee).
- **Guardrails (Codex/adversary):** trade ONLY the fully-fillable same-venue same-rules package. **Exclude** the individual-race-vs-aggregate version ("a forecast in disguise") and the cross-venue version (basis risk). Verify all legs share identical resolution language/source/date (Perplexity's job, off-path).
- **Falsification (~50 lines, $0 capital, 2–3 wks):** daily cron pulls the 4 joint legs + 2 standalone chamber mids, computes the two identities, logs the after-fee/after-spread gap **and the maker-fillable size at top-of-book**. **Kill if** the violation never exceeds the maker spread at fillable size (book already coherent — bots arb it). Reuses the existing `DivergenceDetector`, inverted as a coherence tripwire.
- **Ceiling:** beer money (capped by passive fills) — _or_ a clean null result proving the book is coherent, which is itself a cheap, valuable finding. **Bonus:** Nov 3 2026 gives a dated validation deadline to replace the dead Hormuz window.

### The other four — graded
| Angle | Verdict | Why |
|---|---|---|
| **Perplexity API** | ✅ **Yes — but strictly OFF the trading path** | Three offline uses only: (1) **resolution-criteria due diligence** (pull rule text + resolution source + prior UMA-dispute precedent — risk mgmt, given 1,150+ disputes), (2) one-time **base-rate gathering** (as a vetted static number, leakage-checked), (3) niche-market discovery. **HARD NO on wiring it into the forecaster** — it amplifies recency/rumor/definition-drift _and_ has a **~37% citation-error rate that cites real URLs with fabricated claims**. Marginal cost ~$0 with your credits. Not currently wired in your repo; keep it behind a thin swappable interface (CNN litigation + vendor churn). |
| **US Senate individual-race forecasting** | 🟥 **Dead** | Forecast edge ≠ trade edge; Ohio Senate has **$87k total volume / ~11¢ spread** (you _are_ the book); informed insider/staffer flow concentrates here (NPR: staffers betting internal polls; CFTC complaints); correlated national-polling-miss tail risk; live delisting risk (MN's first state ban, WA suit, CFTC rulemaking). Only the **coherence-arb reframe above** survives. |
| **World Cup 2026 retail-fade** | 🟥 **Skip as profit** / 🟧 free CLV lab | Sports trap in a costume: the soft money sits exactly where the book is deepest/tightest; bias is already arbed to "efficient within tx costs" on CLOBs; 8 days to kickoff = no time; N=1 window sunsets July 19. _Only_ honest use: point the existing pipeline at WC group-stage markets in **paper/`--no-trade` mode with live-news DISABLED** to harvest a big fast calibration dataset (CLV/Brier) — expect it to lose to consensus. |
| **Social media as signal** | 🟥 **Dead as fast** / 🟧 slow-narrative only | The fast single-post trigger is a sub-second HFT game ("first agent wins"); durable effect sizes are single-digit cents that mean-revert; real-time X/Reddit firehoses cost $4.5k–$42k/mo. Only defensible residue: a **structured event-detector on SLOW multi-day narrative markets** (resignation/withdrawal that reprice over days, the Biden 25%→42%→80% archetype), using your free truthbrush(POTUS)+Bluesky feeds, paper-CLV-gated. |

### AI-trading-bot landscape (2026) — what to borrow vs ignore
- **The only verified large-P&L bots are sub-100ms latency-arb on crypto 15-min markets** (2.7s windows, Polygon-colocated) — structurally inaccessible to a cron droplet, and US-geofenced.
- **The most defensible _solo_ edge surfaced isn't LLM at all:** automated **maker market-making + correlation/logical arbitrage** (mutually-exclusive legs must sum to ~1; `YES+NO<$1`) on thin Kalshi/Polymarket — pure math, maker-only, latency-tolerant, no LLM alpha. **The Senate coherence play is the cleanest live instance of this whole class.**
- **Borrow architecture, not the alpha premise:** market-anchored blending as a calibration layer, **LLM-as-risk-filter not forecaster**, quarter-Kelly.

### Net recommendation (this addendum)
Spend a weekend on **two $0 probes**: (1) the **Senate Balance-of-Power coherence tripwire** (the one structurally-sound new idea), and (2) the **World Cup paper-CLV laboratory** (a free, time-boxed, large calibration dataset — now or never until 2030). Wire **Perplexity only as off-path market-intake/resolution-DD tooling.** Treat **CLV, not P&L, as the success metric**, and expect both probes to return null-or-beer-money — which, learned for ~$0, is still the win.

---

## 10. What is this repo actually good for? (Repurposing beyond trading — 2026-06-04)

A 9-agent code-deep-dive + landscape workflow asked: **if trading is dead, what is this codebase genuinely useful for — even open-sourced — and can it make an AI system smarter?**

### The one transferable asset
**The closed forecasting-accountability loop**, verified end-to-end in code: structured probabilistic forecast (with self-confidence + 3-temp ensemble std-dev, `prediction/ensemble.py`) → timestamped → **auto-resolved against ground truth** (`scoring/resolution.py`) → scored (Brier `scorecard.py`, reliability curve `calibration.py`) → **mechanically recalibrated** (`recalibration.py`) → recalibrated prob **+ track-record fed back into the next prompt**. That self-closing `predict→resolve→score→recalibrate→feedback` spine is rare in OSS (netcal/sklearn have the math but no outcome-grounded loop; ForecastBench/KalshiBench have leaderboards but no self-hostable recalibration daemon). **Everything else is discard:** `cascade.py` (oil-physics), `divergence/`, `contracts/`, `portfolio/`, `markets/kalshi.py` are trading/domain-locked. `ensemble.py` and the news-dedup are independently reusable today.

### ⚠️ The decisive caveat: the loop has never actually run
Live DB: **75 signals (89% REFUSED), only 4 ever resolved; `prediction_log` = 108 rows, 0 resolved; recalibrator (gated at 10 samples) has fired 0 times.** The "crown jewel" has scored 4 forecasts in its life and recalibrated zero. It also scores only the **BUY-only, edge-positive subset** (`signal_quality_evaluation` view) — the clean generic `prediction_log` is never resolved, so **today's calibration stats are selection-biased** (a latent correctness bug *and* the #1 repurposing blocker). It's a promising primitive attached to a dead domain **with no data** — not a product.

### Three honest hard limits (strategist + adversaries agree)
1. **Calibration ≠ competence.** Recalibration makes stated confidence *honest*, not the agent smarter; on weak-discrimination domains the output collapses to "abstain more often." Pitching "makes any AI smarter" fails buyer scrutiny — frame it as *better epistemics / trustworthy act-or-escalate*, not higher IQ.
2. **Thin moat.** netcal (~377★) + sklearn already ship Brier/ECE/Platt/isotonic; the repo doesn't even have ECE/log-loss/isotonic. A competent engineer reglues the core in ~a week. Only defensible edge = breadth of ground-truth adapters + polished longitudinal drift reporting.
3. **Tiny audience.** Category leaders sit at 23–72★ (ForecastBench 68, Metaculus forecasting-tools 72, PrediBench 23). Anchor payoff on **résumé line + interview walkthrough + personal utility**, not stars or revenue.

### The verdict — what it's actually good for, ranked
- **#1 (reliable payoff): a portfolio/credibility artifact for the "AI Evals Engineer" / Forward-Deployed-Engineer hiring category** (FDE postings +800% in 2025; Anthropic FDE interviews reportedly center on eval harnesses). **Reposition the repo, leading with the honest negative result** ("no trading alpha — market priors are hard to beat; here's how (mis)calibrated the model is"). The dead trading thesis becomes a *credibility asset* instead of a scam-adjacent liability. Effort: ~½–3 days (README + one polished demo).
- **#2 (the "make AI smarter" play, honestly scoped): extract a `calibrate` library** — a deployment-time, **outcome-grounded recalibration + abstention-gate** for frozen API models (log forecast → resolve via pluggable adapter → recalibrate → `should_abstain()`/act/escalate on the corrected number). This hits a **real, thin gap**: labs bake calibration in at *training* time (RLCR, self-play DPO, Mantic); almost nobody offers a drop-in layer that recalibrates *your* frozen model against *your* accumulated resolutions. Audience: ML-ops running high-volume repeated decisions that eventually get objective labels (ticket auto-resolution, fraud triage, moderation). Effort: 1–2 weeks (re-point at `prediction_log`, generalize off Kalshi, add ECE/log-loss/isotonic via netcal, rename trading nouns).
- **#3 (dogfood, not a product): a private "world-model brief" feeding Jarvis** — proves #2 on fresh real labels. *Caveat the adversary caught:* there is **zero actual integration** with Hermes today (they just share a box), so "feeds the second brain" is aspirational, and the calibration loop is inert for personal predictions (no market behind them) until you add a manual/pluggable resolver.

### The cheapest proof-of-value (do this FIRST — ~1 day, $0, no refactor)
All three adversaries converged here: **don't extract anything yet.** Point the *existing* loop at a public, already-resolved set — **KalshiBench's 1,531 questions on HuggingFace** — for 2–3 frontier models. Produce one reliability diagram + Brier/ECE table, and answer the only question that matters: **does fitting a recalibration map on a held-out slice measurably beat raw model confidence (lower ECE/Brier, more auto-handled at fixed error rate)?** Then post it with the honest "I proved there's no trading edge — here's a calibration-audit harness" framing and watch whether any AI-eval/FDE person asks *"can I run this on my agent?"* This sidesteps the fatal no-data problem (pre-resolved labels, not a months-long live loop) and tests **both** the technical claim and real demand for the price of a day — and you keep the portfolio artifact regardless of the outcome.
