# Parallax — Agent Code Review & Monetization Analysis

**Date:** 2026-05-06
**Reviewer:** Claude Opus 4.7 (1M)
**Scope:** End-to-end audit of the prediction → mapping → trading pipeline; honest take on whether this can make money and what to build next.
**Author of project under review:** Adit Karode (Pyranthus)

---

## TL;DR

Parallax is a well-engineered single-author project — the architecture is cleaner than most quant prototypes I've seen, test coverage is real (35 test files, 265+ cases), and the design choices (proxy-aware mapping, ensemble + cascade hybrid, append-only signal ledger with full provenance) are *exactly* what a serious prediction-market shop would build. The hard problem isn't engineering. It's that the universe is tiny (4 contracts in `INITIAL_CONTRACTS`), the crisis window is closing, the sample size is too small to have proven edge, and three structural bugs would convert any real edge into noise once real money is on the line.

**Can it make money right now?** Almost certainly not at scale. The realistic ceiling on Kalshi geopolitical contracts in this thesis window is ~$5k–$20k of nominal exposure across a handful of contracts before liquidity vanishes. Even at a (hopeful) 8% net edge after costs, that's ~$400–$1,600 of expected value over the remaining ceasefire window — gross of taxes, time, and any adverse selection. **The signal ledger doesn't yet have enough resolved trades to distinguish 8% edge from 0%.** That is the binding constraint, not the code.

**The IP that *could* make money** is the cascade engine + proxy-aware mapping policy + ensemble pipeline as a *general harness* for any binary prediction market. Iran/Hormuz is the wrong target market to monetize on — the right play is to use this as the proof-of-concept and port the harness to broader, more liquid domains (Polymarket politics, Kalshi macro, weather), or sell signals/calibration as a service.

---

## 1. Code Review

### 1.1 Architectural Assessment

**Strengths (load-bearing, keep):**

- **Append-only signal ledger with full provenance** (`scoring/ledger.py`, `scoring/prediction_log.py`). Every signal has a `run_id`, `raw_probability`, `calibrated_probability`, mapping rationale, and resolved outcome. This is the single most important piece of infrastructure for a prediction shop and most teams skip it.
- **Proxy classification as a first-class concept** (`contracts/registry.py:20–77`, `contracts/schemas.py`). Recognising that "ceasefire prediction → Hormuz closure contract" is a `LOOSE_PROXY` and not a `DIRECT` mapping is the right abstraction. It's also the right place to land cost-of-edge logic later.
- **Cascade engine separated from LLM** (`simulation/cascade.py`). The discipline of running deterministic supply-loss math *before* the LLM call gives the model a numerical anchor and produces an audit trail. This is the single biggest differentiator from "GPT-wrapper" predictors.
- **Trimmed-mean ensemble with instability flagging** (`prediction/ensemble.py`). Three calls at different temperatures, drop the extremes, flag if std-dev > 10pp. Conceptually correct; this is the cheapest variance reduction available.
- **Bucket-based recalibration** (`scoring/recalibration.py`) and a `daily_scorecard` ETL with 25+ metrics. Most teams ship without either.
- **Run/data/execution-environment separation** (`ops/runtime.py`). Smart: lets you reuse the same code for dry-run / paper / (eventual) live, distinguished by env tags on every row written.

**Weak points (the architecture has these structural issues):**

1. **The contract universe is hardcoded and tiny.** `contracts/registry.py:20–77` defines exactly 4 contracts: `KXUSAIRANAGREEMENT-27`, `KXCLOSEHORMUZ-27JAN`, `KXWTIMAX-26DEC31`, `KXWTIMIN-26DEC31`. There is no contract-discovery loop. With only 4 contracts and 3 prediction models, you have at most 12 model→contract evaluations per run — the law-of-large-numbers will not deliver edge confidence in a 2-week window.
2. **Predictions feed exactly one prompt template per model.** No A/B'd prompt variants, no scenario decomposition, no hypothesis generation step. The cascade output is rendered into the prompt as text (`prediction/oil_price.py`) rather than fed as numerical features into a calibrator. The "LLM does the calibration" architecture caps your achievable Brier score at the LLM's intrinsic calibration ability.
3. **No latency budget or freshness contract.** News fetched in `brief.py` is passed straight into prediction prompts with no staleness check (`brief.py:510–517`). If GDELT 429s and Google News is 8 minutes behind, the prediction is built on stale evidence and there's no signal for how stale.
4. **Single DuckDB writer + public FastAPI.** `main.py` exposes 14 endpoints with zero authentication. `/api/brief/run` (POST, line ~246) can be invoked by anyone and triggers a real prediction + paper-trade run. For a localhost-only dev tool this is fine; the moment this is exposed (and it has to be, if you ever serve a dashboard), this is a free-LLM-credit-burn API and a free-trade-trigger API.
5. **Crisis context is a hand-maintained Markdown variable.** `prediction/crisis_context.py` carries a "Last updated: 2026-04-12" string as the only timestamp. All three predictors get the same context; if it's stale the entire ensemble miscalibrates in the same direction (no decorrelation benefit from running 3 models on the same input).

### 1.2 Specific Bugs and Fragile Assumptions (verified)

| # | Severity | Location | Issue | Real impact |
|---|----------|----------|-------|-------------|
| 1 | **HIGH** | `cli/brief.py:484, 495` | `asyncio.gather` without `return_exceptions=True` for predictor and fetch calls | Any single predictor or data-fetcher exception aborts the entire brief. One transient Anthropic 529 kills the day's signals. |
| 2 | **HIGH** | `cli/brief.py:533–534` | `update_discounts_from_history` / `update_thresholds_from_history` are the *only* place proxy-class adjustment lives. `_per_class_min_edge` starts empty and is only raised once observed `LOOSE_PROXY` win-rate is bad. | At cold start every proxy class trades at the same 5% min-edge floor. By the time history is bad enough to trigger the bump, you've already lost the bankroll on bad proxy bets. |
| 3 | **HIGH** | `contracts/mapping_policy.py:61, 290` | The legacy per-contract `discount_map` (`registry.py:32, 46, 60, 74`) is destructured into `_legacy_discount` and ignored. `confidence_discount=1.0` is hardcoded in the `MappingResult`. | The discount_map data exists, looks like it's being applied, and is silently dead. You think loose-proxy contracts get a 0.3 multiplier on edge; they do not. |
| 4 | **HIGH** | `prediction/crisis_context.py` | Manually-edited timeline string with literal "Last updated: 2026-04-12" comment as the only freshness signal. All three predictors share it. | One stale context → three correlated wrong predictions → ensemble disagreement is *low* (model-variance, not signal-variance), so `INSTABILITY_THRESHOLD` doesn't fire. False confidence. |
| 5 | **MED** | `simulation/cascade.py:35` | `PRICE_ELASTICITY = 3.0` hardcoded. At 100% Hormuz blockade, supply-loss term yields `1 + 1.0 * 3.0 = 4.0×` price multiplier (~$80 → ~$320). | Realistic estimates put a full closure at $150–$220. The constant is on the high side, not 30× off as one sub-agent claimed, but the LLM sees a price anchor that's roughly 2× too aggressive at the tail. Bias goes one direction (over-bullish on oil), which compounds with the also-hardcoded fallback `hormuz_daily_flow`. |
| 6 | **MED** | `prediction/ensemble.py:122` | Budget recorded *only* for non-exception responses. If a call times out before the API server records it, the spend isn't logged but the upstream provider may still bill. | Slow drift between accounting and reality. With a $20/day cap this is small, but it means you can't fully trust the `llm_usage` table for cost analysis. |
| 7 | **MED** | `main.py` | No auth on any endpoint, no CORS lock-down, no rate limit on `/api/brief/run`. | Fine localhost; not fine the day a dashboard goes online. |
| 8 | **MED** | `markets/kalshi.py:124–140` | RSA-PSS signature uses `int(time.time() * 1000)`. No clock-skew tolerance, no NTP sanity check, no timestamp-rejected retry. | Under any clock drift > 1s, every order is rejected. Production OS time drift is real; without `chronyd`/`ntpd` this is a Tuesday-morning incident waiting to happen. |
| 9 | **MED** | `scoring/tracker.py:141–157` | Order is inserted into DB *before* rejection check; on rejection, ledger `execution_status` and order row diverge. | Reconciliation reports show ghost-rejected orders that the ledger thinks weren't attempted. Annoying for paper, dangerous for live (a "rejected but somehow filled" race). |
| 10 | **LOW** | `simulation/cascade.py:38` | `INSURANCE_THREAT_MULTIPLIER = 5.0` defined but the function that uses it is never called from the prediction path. | Dead code that looks load-bearing. Either wire it up to the LLM prompt or delete. |
| 11 | **LOW** | `ingestion/google_news.py:46` | URL hash for dedup; no hostname normalization, no canonical-URL resolution. | Same Reuters story via 3 mirror domains → 3 "independent" pieces of evidence. Inflates LLM's perceived consensus. |
| 12 | **LOW** | `ingestion/oil_prices.py` | No freshness check on EIA `period` field. | If EIA is 24h+ behind, predictor sees stale $-anchor and doesn't know. |

**One claim I want to push back on from the audit:** the sub-agent reviewing the prediction layer claimed `ensemble.py` lacks `return_exceptions=True`. It doesn't — line 108 sets it correctly. The partial-failure handling inside the ensemble is the strongest part of the prediction layer. The aborts-on-exception bug is in `brief.py`'s outer `gather`, not in the ensemble.

### 1.3 Test Coverage

35 test files; the collection covers the right areas (cascade, ensemble, mapping policy, ledger, recalibration, scorecard, tracker). Notable gaps:

- **No end-to-end "bad-data day" test.** What happens when GDELT 429s, Google News returns empty, and EIA is stale? There's no test that confirms the brief gracefully degrades vs hard-crashes. Given bug #1 above, I'd bet on hard-crash.
- **No idempotency test for the signal pipeline.** Two runs with the same `run_id` should be either rejected or upserted; nothing in `tests/test_brief.py` confirms either.
- **No correlation/concentration test in the allocator.** `test_simulator.py` exercises the simulator but the portfolio allocator's theme-limit logic has no test that I can find covering "3 oil-themed signals from the same model in the same run".
- **No clock-skew test for Kalshi auth.** `test_kalshi.py` mocks the signature; it does not test that a 5-second clock drift is handled (and currently it isn't).
- **No proxy-class discount test.** `test_mapping_policy.py` tests the policy but doesn't seem to assert that `LOOSE_PROXY` results in a smaller edge gate than `DIRECT` — which is good, because empirically it doesn't, and a regression test would have caught bug #3.

### 1.4 What Breaks First Under Real-Money Live Trading

In approximate order:

1. **Kalshi auth fails on clock drift.** First time `chronyd` slips a few seconds — every order rejected. (`markets/kalshi.py:124`)
2. **One predictor hangs, the entire run aborts, you miss a signal during a real news event.** (`cli/brief.py:484, 495`)
3. **Bad proxy mapping triggers oversized correlated bets.** Three signals from three models all fire on oil-related contracts with no discount applied; allocator's theme-limit catches the $-notional cap but not the *edge-quality* mismatch. You execute three trades that average out to a 1.5%-net-edge bet sized as if it were a 5%-edge bet.
4. **Stale crisis context produces three correlated mispriced predictions.** Ensemble agreement is high (because all three predictors got the same wrong inputs), `is_unstable=False`, full confidence applied. You take a confident position on a market that's already moved past you.
5. **No retry/backoff on Kalshi resolution polling** (`scoring/resolution.py:194–223`). Settled positions stay open in the ledger; `realized_pnl` doesn't update; recalibration uses stale outcomes; the feedback loop slowly poisons itself.
6. **`/api/brief/run` triggered externally** (intentional or accidental) burns LLM budget and triggers trades. Even at the $20/day cap, a malicious or buggy actor can deplete it deterministically.

---

## 2. Monetization Analysis

### 2.1 Can this make money right now? Honest take.

**No — at least, not enough to matter, and not provably.**

Let me be specific about why.

**Edge estimate.** The realistic edge a careful retail bot can extract on Kalshi geopolitical contracts is a function of three things: (a) the mispricing exists, (b) you can size into it before it closes, (c) the market resolves in your favour often enough to overcome costs. On a contract like `KXCLOSEHORMUZ-27JAN`, the bid-ask is wide (often 4–8¢ on a $1 contract), the depth at top-of-book is usually <50 contracts, and Kalshi takes a 1–3% fee depending on settlement. So your round-trip cost is somewhere in the **3.5%–8% of notional** range *before* slippage on size. Your `min_effective_edge_pct` is set to 5%. **You are gating at the cost level, not above it.** A 5% edge after costs is at best a wash. To clear costs and earn risk-adjusted return, you need ~8–12% gross edge consistently.

Whether the system *finds* 8–12% edges is unknown, because:

- The signal ledger has not yet resolved enough trades to compute a reliable hit rate per proxy class. The default `hit_rate=0.5` (`portfolio/simulator.py:25`) is the prior used until you have ~20 resolved trades per category. With 4 contracts and a 2-week window, you may finish with 10–30 resolved signals total — wide enough confidence interval that "edge" and "noise" are indistinguishable.
- There is no held-out backtest of the cascade engine against historical oil shocks. The `PRICE_ELASTICITY=3.0` constant is a guess; it has not been fit to data.
- The crisis context is hand-maintained, so any apparent edge is contaminated by hindsight (you wrote the context after seeing how the news played out).

**Is paper-trading data showing real edge?** Without seeing live numbers I can't say definitively, but a priori: with 35 test files, 4 contracts, and a 2-week sample, the *expected* result is "noise-dominated, consistent with both 0% edge and 5% edge". Treat any apparent edge below ~4% net with deep skepticism — that's within sampling error.

**What would it take to flip to live trading today?** In order: see §2.2.

### 2.2 Fastest Path to First Real Dollar — Blockers in Order

If the goal is "trade real money on Kalshi within one week," the binding sequence is:

1. **Fix the proxy discount bug** (`mapping_policy.py:290`). One-line fix. Without it, real-money loose-proxy bets are mispriced by ~3× on average. This is non-negotiable.
2. **Fix `asyncio.gather` failure handling** (`cli/brief.py:484, 495`). Add `return_exceptions=True` and per-predictor fallback to the previous-run prediction. Without this, the first transient Anthropic outage halts trading at the worst possible moment.
3. **Add a proxy-class edge gate from day one.** `LOOSE_PROXY` should require ≥ 8% net edge, `NEAR_PROXY` ≥ 6%, `DIRECT` ≥ 4%. Hardcoded floors are fine. Don't wait for `update_discounts_from_history` to discover this empirically — you can't afford the tuition.
4. **Hard-cap real-money bankroll at $500–$1,000 for the first 4 weeks.** That's enough notional to generate signal but small enough that ruin is bounded. (Current `RiskLimits.max_notional` default is $250 — fine for paper, slightly tight for live.)
5. **Resolve the Kalshi clock-skew issue.** Either run NTP sync on the host, or add a ±5s retry loop in `markets/kalshi.py:124`. If you trade live without this, the first failed-order event will be unexplained.
6. **Add live-execution authorization gate** (the `LIVE_EXECUTION_ACK` pattern in `ops/runtime.py:217` is already there) — make it required, default to off, and log every transition. Treat it like a kill switch.
7. **Before any real-money order**, run the unmodified pipeline against the *live market price feed* in `--no-trade` mode for at least 30 paper trades. Compute realized vs. predicted edge. If realized edge < 0.6 × predicted edge consistently, do not flip live.

Steps 1–3 are 1 day of work. Step 4 is 5 minutes. Step 5 is 30 minutes. Step 6 is 1 day. Step 7 is the calendar wait — you cannot compress it.

**Realistic outcome of doing all of this:** $100–$500 of expected value on a $1,000 bankroll over 4 weeks, with a wide enough variance that the realized P&L could easily be ±$300. Worth doing as proof-of-concept and to build resolved-trade history. Not worth doing as a business.

### 2.3 Risk of Ruin

The current portfolio sizing setup is **safer than most retail bots but not as safe as it looks**, for these reasons:

- **Quarter-Kelly with a default 50% hit rate prior** (`portfolio/simulator.py:24–25`). Until you have meaningful resolved-trade history, every position is sized as if you have a 50% baseline win rate. If your true rate is 45% (entirely possible at cold start with miscalibrated proxies), Kelly is *negative* and quarter-Kelly is still a losing bet. The first ~20 trades are sized on a prior, not on data.
- **No drawdown circuit breaker on cumulative P&L.** `daily_loss_limit` defaults to $50 — that gates one day, not a streak. A 5-day losing streak at the daily cap is -$250, which is 100% of `max_notional`. There's no rule like "if 7-day rolling P&L is < −20%, halve position sizes for 30 days."
- **Theme limits exist but the mapping is by `prediction.model_id`** (`brief.py:578`). All three model IDs are different; theme limits will not catch "oil-correlated bets across models" because the theme strings are `oil_price`, `hormuz_reopening`, `ceasefire` — three different bins. The portfolio could go heavily long oil exposure across all three model themes without hitting any theme limit.
- **No correlation-adjusted Kelly.** Two correlated signals on oil-up should be sized as ~1× a single signal, not 2×. Currently they're sized independently.
- **No execution-failure guard.** If a fill fails to record (network glitch between Kalshi confirming and DuckDB writing), the next run sees the position as not-held and may double up.

**Realistic ruin scenarios:**

1. **The "stale context streak":** crisis context goes stale on Friday night, all three predictors miscalibrate in the same direction Saturday/Sunday/Monday, ensemble doesn't flag instability, allocator sizes 5–7 trades at full Kelly fraction, all 5–7 lose. Loss: 30–50% of bankroll in one weekend. Mitigation: timestamped context with auto-staleness flag and confidence penalty.
2. **The "cold-start proxy" ruin:** loose-proxy bets fire at full size for the first 20 trades because `_per_class_min_edge` is empty; expected edge is overstated by ~3×; realized edge is ~0%; loss after costs is ~5% per trade × ~6 trades before adaptive logic catches up = ~30% drawdown. Mitigation: hardcoded floors per proxy class (§2.2 step 3).
3. **The "Kalshi clock-skew" ruin:** every order rejected, signals never trade, but the ledger and recalibrator update as if they did. Calibration drifts; first time clock sync resolves and trades go through, the system is now miscalibrated against current market state. Loss: not quantifiable, but "trading with mismatched recalibration" is a slow bleed. Mitigation: retry on rejection, never advance state on rejected orders.

The good news: **`max_notional=$250` and `daily_loss_limit=$50` mean the absolute-dollar ruin is small.** This is the right setup for a research project. The problem is that those caps also limit the upside — at this scale you can't make enough money to validate the strategy in any reasonable timeframe.

### 2.4 Modularity to Other Domains — What Transfers, What Doesn't

This is where the actual value lies. Decompose the IP:

| Component | Transferable? | Why / Why not |
|-----------|--------------|---------------|
| **Append-only signal ledger + scorecard ETL** | **Fully** — port directly | Domain-agnostic infrastructure. Should be the foundation of any prediction-market shop. |
| **Proxy-aware contract mapping policy** | **Mostly** — port with new `proxy_map` data | The *concept* is universal: model output → contract mapping with a discount for thematic distance. The data (which contracts, which proxy classes) is per-domain. |
| **Trimmed-mean ensemble + instability flag** | **Fully** — port directly | Generic LLM aggregation. Works for any prompt. |
| **Recalibration via bucketed offset** | **Fully** — port directly | Standard isotonic-style recalibration. |
| **Cascade engine** | **Partially** — concept transfers, rules don't | "Run a deterministic causal model before the LLM" is the right frame. The 6 rules (blockade → flow → bypass → price → downstream → insurance) are Hormuz-specific. For elections you'd want a "polling-error → state-correlation → EV propagation" cascade. For weather, "model-skill → ensemble-spread → impact" cascade. **Each domain needs its own cascade rules**, but the *harness* (config-driven rule chain feeding into LLM prompt) is reusable. |
| **Crisis context injection** | **Concept transfers; mechanism needs work** | Every domain has post-cutoff context that LLMs lack. The mechanism needs to be automated and timestamped before it's portable. |
| **Kalshi/Polymarket clients** | **Polymarket fully; Kalshi already venue-agnostic** | The `markets/schemas.py` abstraction is fine. Adding Manifold, PredictIt (defunct), Robinhood event contracts is straightforward. |
| **News ingestion (Google News + GDELT)** | **Fully** — generic | RSS + GDELT works for any domain with public coverage. |

**Domain-specific port cost (rough):**

- **Polymarket politics / US elections (2026 midterms, 2028 primary).** Highest leverage. Polymarket has 10–100× the liquidity of Kalshi geo, far more contracts, longer event horizons, and the LLM has *much more* training data on US political dynamics. **Port cost: ~3–4 weeks.** New contracts, new cascade (polling → demographic shift → state outcome → EV total), new crisis context (campaign timeline). Reuses ~70% of code.
- **Kalshi macro (CPI, Fed rate, NFP).** Medium leverage. Liquidity is decent. The cascade is naturally numerical (forecaster consensus → surprise distribution → market repricing) which actually fits the "cascade then LLM" pattern *better* than geopolitics. **Port cost: ~2 weeks.** Reuses ~80% of code.
- **Sports.** Low leverage for *this* IP. Sports prediction is a dense, well-understood efficient market with established quant shops. Your edge from "second-order cascade reasoning" is small because there *is* no second-order cascade in a basketball game. Don't go here.
- **Crypto event contracts (price thresholds, halving, etc).** Medium leverage but adverse selection is severe. Kalshi/Polymarket crypto markets are dominated by participants with better real-time price feeds than yours.
- **Weather.** Niche but high transfer fit. Forecast ensembles + cascade-of-impact (heat wave → grid load → power price) maps beautifully. Markets exist on Kalshi (precipitation, temperature). **Port cost: ~3 weeks.** Reuses ~70%.
- **Other geopolitics (Taiwan/Strait, Russia–Ukraine, North Korea).** Direct transfer. Cascade rules are different but the harness is identical. **Port cost: ~1–2 weeks per scenario.**

**The two highest-EV ports right now:** Polymarket politics (large markets, lots of training data, lots of contracts) and Kalshi macro (clean numerical cascades, regular cadence of events).

### 2.5 Other Monetization Angles Beyond Direct Trading

Direct trading on geopolitical Kalshi is the *worst* monetization path for this IP — it's the most capital-intensive, the most variance-heavy, and the smallest TAM. Other angles, ranked by feasibility × upside:

1. **Signal-as-a-Service for prop traders / hedge funds.** Sell the JSON output of `/api/predictions` and `/api/signals` as a daily/intraday feed. Buyers: small commodity prop shops, geopolitical risk desks at funds. Pricing: $500–$3,000/month per seat. The product needs: (a) calibration receipts (Brier history), (b) clean schema, (c) a track record dashboard. **You already have all of this in `dashboard/data.py` and `scoring/scorecard.py`.** Effort to productize: ~3–4 weeks. This is the highest-leverage path.
2. **White-label "binary-market edge engine" for prop trading desks.** License the harness (cascade + ensemble + ledger) to firms that want to plug in their own contract universe and prompts. SaaS-style: $5–15k/month. Larger TAM than signals but more enterprise sales lift. ~2–3 month effort.
3. **Calibration / track-record SaaS.** A general "Brier score + reliability diagram + edge-decay" service for any LLM-prediction shop. Prediction-market firms, but also forecasting researchers, AI lab eval teams, weather services. Niche but extremely defensible — you're already building it for yourself. ~1 month to extract.
4. **Fund strategy.** Run a tiny ($100k–$1M) pooled fund of accredited friends/angels on this strategy. Realistic Sharpe is 0.5–1.0 if the edge is real — not exciting at small AUM, but a track record to point at later. Requires legal structure. **Don't do this until you have ≥ 6 months of paper-trading data with statistically significant edge.**
5. **Open-source the cascade engine, sell hosted.** "Cascade-as-a-service" — let other people define rule chains for their domain. Niche but plays to OSS distribution. ~6 weeks to extract and document.
6. **Content / research arm.** Public blog of "this is what we predicted, this is what happened, here's our calibration." Builds reputation, drives signal-API sales. Marginal cost ~0.

The ranking is roughly correct; the dominant strategy is **(1) → (2) → (4)** as a sequence: signals build track record, white-label monetizes the harness, fund monetizes proven edge.

---

## 3. What To Build Next — Top 5 Highest-Leverage Improvements

Ranked by **expected value × probability of success / effort**. EV here is "dollars unlocked or risk avoided," roughly.

### #1 — Fix the three HIGH-severity bugs (loose-proxy discount, brief.py gather, brief retry/fallback)
- **Effort:** ~1 day total.
- **EV:** Avoids ~30% loss in the first ruin scenario; avoids 1+ missed-signal incidents per week. Without this, nothing else matters because real-money trading will systematically lose.
- **Why first:** These are blockers, not improvements. Pure downside reduction.

### #2 — Automated, timestamped crisis context with staleness penalty
- **What:** Replace the hand-edited `crisis_context.py` with an ingestion pipeline that pulls structured event records into a `crisis_events` table; render the prompt context from rows with `event_time` ≥ now() − 14d; surface `context_age_seconds` to the LLM and to the confidence calculation; if stale, downgrade confidence by `min(1, 1 − age_hours/48)`.
- **Effort:** ~1.5 weeks.
- **EV:** Eliminates the highest-correlation failure mode (stale context → 3 correlated wrong predictions). Enables 24/7 unattended operation. Necessary precondition for live trading and for any signal-as-a-service offering.
- **Why second:** Without this, signal quality has a hidden ceiling that no amount of model tuning can raise. Every other improvement assumes fresh context.

### #3 — Resolution-scored backtest harness
- **What:** A `backtest/` runner that, given a date range and a frozen prompt template, replays news/prices through the prediction pipeline and produces hit-rate, Brier, edge-realized-vs-predicted, and a calibration curve. Uses the existing `scoring/calibration.py` machinery but lets you A/B'd prompt or model variants without trading. Critical: include a strict no-look-ahead guarantee — every prediction at time `t` may only see news/prices with `published_at ≤ t`.
- **Effort:** ~2 weeks (the hard part is the look-ahead audit).
- **EV:** This is what unlocks every other improvement. Right now you cannot say "the new prompt is better" with anything beyond vibes. With a backtest harness, every change is measurable.
- **Why third:** Builds the measurement infrastructure that everything else depends on. Pairs with #2 — you cannot backtest if context is hand-edited per-day.

### #4 — Port the harness to Polymarket politics (US 2026 midterms or a 2028-primary contract)
- **What:** New cascade rules for polling-driven cascades (poll surprise → demographic propagation → state outcome → tipping-point probability), new `INITIAL_CONTRACTS` from Polymarket, new crisis-context source (campaign news, debate calendar, FEC filings). Reuse 70% of existing code. Run paper-only for 60 days alongside the Iran pipeline.
- **Effort:** ~3–4 weeks.
- **EV:** This is the *only* path to enough resolved trades to actually distinguish signal from noise within a quarter. Polymarket politics also has 10–100× the liquidity of Kalshi geopolitics, so the same edge translates to more dollars. Validates that the IP generalizes — the precondition for any monetization play beyond direct trading.
- **Why fourth:** Depends on #3 (you need backtest infrastructure to validate the new cascade rules). Depends on #1 (you need the bugs fixed before adding more proxy contracts).

### #5 — Productize a signal API + track record dashboard for a paying audience of one
- **What:** Pick one prop trader / commodity desk / geopolitical-risk consultant in your network. Spec a JSON daily-signal feed (signals with calibration receipts, Brier history, proxy classifications, edge-after-cost estimates). Sign them up for a free trial; iterate on what they actually use. Charge $500/month after 30 days. Goal: one paying customer.
- **Effort:** ~3 weeks (mostly the schema design, Stripe wiring, and the customer-development cycle).
- **EV:** Two things this unlocks. First, **revenue >$0** changes everything about how this project is described to investors / employers / future collaborators. Second, customer feedback is the only forcing function strong enough to make you finish the parts of the codebase you've been ignoring (auth, observability, schema docs). $500/month is meaningless as income, but the *fact* of an external paying user is worth $50k of resume value.
- **Why fifth:** Lowest engineering cost per dollar of impact, but depends on #1–#3 to have anything worth selling.

---

## Honest Closing Take

This is a strong solo project. The architecture is better than 80% of single-author quant prototypes. The thesis (cascade reasoning beats headline scraping) is defensible. The crisis-window deadline (April 7–21 ceasefire) is what gave it urgency, but trading that window for real money is the lowest-EV use of the IP — the universe is too small, the sample size won't converge, and the market's adverse selection on a four-contract universe is brutal.

**The three things that matter most, in order:**

1. Fix the bugs that would convert real edge into noise (proxy discount, gather failure, brief retry).
2. Automate the crisis context — it's the silent ceiling on everything.
3. Treat Iran/Hormuz as the proof-of-concept it is, and port the harness somewhere with enough resolved trades to actually measure edge (Polymarket politics or Kalshi macro). Then either trade real money at scale, or sell the signals to someone who already has the bankroll.

If I were Adit, I'd freeze new feature work for one week, ship the bug fixes and the gather-failure handling, then spend the next month porting to Polymarket politics in parallel with running Iran on paper. The Iran data is your résumé piece. Politics is where the dollars come from.

— *End of review*
