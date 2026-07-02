# Parallax — Agent Code Review & Monetization Analysis

**Date:** 2026-05-06
**Reviewer:** Claude Opus 4.7 (1M)
**Scope:** End-to-end audit of the prediction → mapping → trading pipeline; honest take on whether this can make money and what to build next.
**Author of project under review:** Adit Karode (Pyranthus)

---

## TL;DR

Parallax is a well-engineered single-author project — the architecture is cleaner than most quant prototypes, test coverage is real (35 test files, 265+ cases), and the design choices (proxy-aware mapping, ensemble + cascade hybrid, append-only signal ledger with full provenance) are exactly what a serious prediction-market shop would build. The hard problem isn't engineering. It's that the universe is tiny (4 contracts in `INITIAL_CONTRACTS`), the crisis window is closing, the sample size is too small to have proven edge, and three structural bugs would convert any real edge into noise once real money is on the line.

**Can it make money right now?** Almost certainly not at scale. The realistic ceiling on Kalshi geopolitical contracts in this thesis window is ~$5k–$20k of nominal exposure across a handful of contracts before liquidity vanishes. Even at a (hopeful) 8% net edge after costs, that's ~$400–$1,600 of expected value over the remaining ceasefire window — gross of taxes, time, and any adverse selection. **The signal ledger doesn't yet have enough resolved trades to distinguish 8% edge from 0%.** That is the binding constraint, not the code.

**The IP that *could* make money** is the cascade engine + proxy-aware mapping policy + ensemble pipeline as a *general harness* for any binary prediction market. Iran/Hormuz is the wrong target market to monetize on — the right play is to use this as the proof-of-concept and port the harness to broader, more liquid domains (Polymarket politics, Kalshi macro, weather), or sell signals/calibration as a service.

---

## 1. Code Review

### 1.1 Architectural Assessment

**Strengths (load-bearing, keep):**

- **Append-only signal ledger with full provenance** (`scoring/ledger.py`, `scoring/prediction_log.py`). Every signal has a `run_id`, `raw_probability`, `calibrated_probability`, mapping rationale, and resolved outcome. This is the single most important piece of infrastructure for a prediction shop and most teams skip it.
- **Proxy classification as a first-class concept** (`contracts/registry.py:20–77`, `contracts/schemas.py`). Recognising that "ceasefire prediction → Hormuz closure contract" is a `LOOSE_PROXY` and not a `DIRECT` mapping is the right abstraction.
- **Cascade engine separated from LLM** (`simulation/cascade.py`). The discipline of running deterministic supply-loss math *before* the LLM call gives the model a numerical anchor and produces an audit trail. This is the single biggest differentiator from "GPT-wrapper" predictors.
- **Trimmed-mean ensemble with instability flagging** (`prediction/ensemble.py`). Three calls at different temperatures, drop the extremes, flag if std-dev > 10pp. Conceptually correct.
- **Bucket-based recalibration** (`scoring/recalibration.py`) and a `daily_scorecard` ETL with 25+ metrics. Most teams ship without either.
- **Run/data/execution-environment separation** (`ops/runtime.py`). Lets you reuse the same code for dry-run / paper / (eventual) live, distinguished by env tags on every row written.

**Weak points:**

1. **The contract universe is hardcoded and tiny.** Exactly 4 contracts: `KXUSAIRANAGREEMENT-27`, `KXCLOSEHORMUZ-27JAN`, `KXWTIMAX-26DEC31`, `KXWTIMIN-26DEC31`. No contract-discovery loop. With only 4 contracts and 3 prediction models, you have at most 12 model→contract evaluations per run.
2. **Predictions feed exactly one prompt template per model.** No A/B'd prompt variants, no scenario decomposition, no hypothesis generation step.
3. **No latency budget or freshness contract.** News fetched in `brief.py` is passed straight into prediction prompts with no staleness check.
4. **Single DuckDB writer + public FastAPI.** `main.py` exposes 14 endpoints with zero authentication. `/api/brief/run` can be invoked by anyone and triggers a real prediction + paper-trade run.
5. **Crisis context is a hand-maintained Markdown variable.** `prediction/crisis_context.py` carries a "Last updated: 2026-04-12" string as the only timestamp.

### 1.2 Specific Bugs and Fragile Assumptions (verified)

| # | Severity | Location | Issue | Real impact |
|---|----------|----------|-------|-------------|
| 1 | **HIGH** | `cli/brief.py:484, 495` | `asyncio.gather` without `return_exceptions=True` for predictor and fetch calls | Any single predictor or data-fetcher exception aborts the entire brief. |
| 2 | **HIGH** | `cli/brief.py:533–534` | `_per_class_min_edge` starts empty and is only raised once observed `LOOSE_PROXY` win-rate is bad. | At cold start every proxy class trades at the same 5% min-edge floor. |
| 3 | **HIGH** | `contracts/mapping_policy.py:61, 290` | The legacy per-contract `discount_map` is destructured into `_legacy_discount` and ignored. `confidence_discount=1.0` is hardcoded. | You think loose-proxy contracts get a 0.3 multiplier on edge; they do not. |
| 4 | **HIGH** | `prediction/crisis_context.py` | Manually-edited timeline string with literal "Last updated: 2026-04-12" as the only freshness signal. All three predictors share it. | One stale context → three correlated wrong predictions → ensemble doesn't flag instability. |
| 5 | **MED** | `simulation/cascade.py:35` | `PRICE_ELASTICITY = 3.0` hardcoded. At 100% Hormuz blockade, yields ~4× price multiplier. | LLM sees a price anchor that's roughly 2× too aggressive at the tail. |
| 6 | **MED** | `prediction/ensemble.py:122` | Budget recorded only for non-exception responses. | Slow drift between accounting and reality. |
| 7 | **MED** | `main.py` | No auth on any endpoint, no CORS lock-down, no rate limit on `/api/brief/run`. | Fine localhost; not fine when dashboard goes online. |
| 8 | **MED** | `markets/kalshi.py:124–140` | RSA-PSS signature uses `int(time.time() * 1000)`. No clock-skew tolerance. | Under any clock drift > 1s, every order is rejected. |
| 9 | **MED** | `scoring/tracker.py:141–157` | Order is inserted into DB *before* rejection check; on rejection, ledger and order row diverge. | Ghost-rejected orders in reconciliation reports. |
| 10 | **LOW** | `simulation/cascade.py:38` | `INSURANCE_THREAT_MULTIPLIER = 5.0` defined but never called from the prediction path. | Dead code that looks load-bearing. |
| 11 | **LOW** | `ingestion/google_news.py:46` | URL hash for dedup; no hostname normalization, no canonical-URL resolution. | Same story via 3 mirror domains → 3 "independent" pieces of evidence. |
| 12 | **LOW** | `ingestion/oil_prices.py` | No freshness check on EIA `period` field. | Predictor sees stale $-anchor and doesn't know. |

### 1.3 Test Coverage

35 test files; coverage hits the right areas (cascade, ensemble, mapping policy, ledger, recalibration, scorecard, tracker). Notable gaps:

- **No end-to-end "bad-data day" test.** What happens when GDELT 429s, Google News returns empty, and EIA is stale?
- **No idempotency test for the signal pipeline.** Two runs with the same `run_id` should be either rejected or upserted.
- **No correlation/concentration test in the allocator.**
- **No clock-skew test for Kalshi auth.**
- **No proxy-class discount test.** `test_mapping_policy.py` doesn't assert that `LOOSE_PROXY` results in a smaller edge gate than `DIRECT`.

### 1.4 What Breaks First Under Real-Money Live Trading

In approximate order:

1. **Kalshi auth fails on clock drift.** (`markets/kalshi.py:124`)
2. **One predictor hangs, the entire run aborts, you miss a signal.** (`cli/brief.py:484, 495`)
3. **Bad proxy mapping triggers oversized correlated bets.**
4. **Stale crisis context produces three correlated mispriced predictions.**
5. **No retry/backoff on Kalshi resolution polling** (`scoring/resolution.py:194–223`).
6. **`/api/brief/run` triggered externally** burns LLM budget and triggers trades.

---

## 2. Monetization Analysis

### 2.1 Can this make money right now? Honest take.

**No — at least, not enough to matter, and not provably.**

Edge estimate: bid-ask on Kalshi geopolitical contracts is often 4–8¢ on a $1 contract, Kalshi takes 1–3% fee. Round-trip cost is **3.5%–8% of notional**. `min_effective_edge_pct` is set to 5%. **You are gating at the cost level, not above it.**

Whether the system *finds* 8–12% edges is unknown: not enough resolved trades to compute reliable hit rates, no held-out backtest of the cascade engine, and the crisis context is hand-maintained (any apparent edge is contaminated by hindsight).

### 2.2 Fastest Path to First Real Dollar — Blockers in Order

1. **Fix the proxy discount bug** (`mapping_policy.py:290`). One-line fix. Non-negotiable.
2. **Fix `asyncio.gather` failure handling** (`cli/brief.py:484, 495`). Add `return_exceptions=True` and per-predictor fallback.
3. **Add a proxy-class edge gate from day one.** `LOOSE_PROXY` ≥ 8% net edge, `NEAR_PROXY` ≥ 6%, `DIRECT` ≥ 4%.
4. **Hard-cap real-money bankroll at $500–$1,000 for the first 4 weeks.**
5. **Resolve the Kalshi clock-skew issue.** Either run NTP sync or add a ±5s retry loop.
6. **Add live-execution authorization gate** (`LIVE_EXECUTION_ACK` pattern in `ops/runtime.py:217` is already there).
7. **Before any real-money order**, run `--no-trade` mode for at least 30 paper trades. If realized edge < 0.6 × predicted edge consistently, do not flip live.

### 2.3 Risk of Ruin

- **Quarter-Kelly with a default 50% hit rate prior.** Until you have meaningful resolved-trade history, every position is sized on a prior, not on data.
- **No drawdown circuit breaker on cumulative P&L.** `daily_loss_limit` defaults to $50 — that gates one day, not a streak.
- **Theme limits map by `prediction.model_id`.** All three model IDs are different; theme limits will not catch "oil-correlated bets across models."
- **No correlation-adjusted Kelly.** Two correlated signals on oil-up should be sized as ~1× a single signal, not 2×.

**Realistic ruin scenarios:**

1. **The "stale context streak":** crisis context goes stale, all three predictors miscalibrate in the same direction, ensemble doesn't flag instability, allocator sizes 5–7 trades at full Kelly fraction, all 5–7 lose. Loss: 30–50% of bankroll in one weekend.
2. **The "cold-start proxy" ruin:** loose-proxy bets fire at full size for the first 20 trades because `_per_class_min_edge` is empty; expected edge is overstated by ~3×; loss ~30% drawdown.
3. **The "Kalshi clock-skew" ruin:** every order rejected, but ledger updates as if they went through. Miscalibrated recalibration.

### 2.4 Modularity to Other Domains

| Component | Transferable? | Why / Why not |
|-----------|--------------|---------------|
| **Append-only signal ledger + scorecard ETL** | **Fully** | Domain-agnostic infrastructure. |
| **Proxy-aware contract mapping policy** | **Mostly** | The *concept* is universal; the data (which contracts, proxy classes) is per-domain. |
| **Trimmed-mean ensemble + instability flag** | **Fully** | Generic LLM aggregation. |
| **Recalibration via bucketed offset** | **Fully** | Standard isotonic-style recalibration. |
| **Cascade engine** | **Partially** | The harness (config-driven rule chain feeding into LLM prompt) is reusable; the 6 rules are Hormuz-specific. |
| **Crisis context injection** | **Concept transfers** | Every domain has post-cutoff context that LLMs lack. Mechanism needs automation. |
| **Kalshi/Polymarket clients** | **Polymarket fully; Kalshi already venue-agnostic** | `markets/schemas.py` abstraction is fine. |
| **News ingestion (Google News + GDELT)** | **Fully** | Generic; works for any domain with public coverage. |

**Highest-EV ports:** Polymarket politics (large markets, lots of training data) and Kalshi macro (clean numerical cascades, regular cadence).

### 2.5 Other Monetization Angles Beyond Direct Trading

1. **Signal-as-a-Service for prop traders / hedge funds.** Sell JSON output of `/api/predictions` and `/api/signals`. $500–$3,000/month per seat. You already have everything needed in `dashboard/data.py` and `scoring/scorecard.py`. Effort: ~3–4 weeks. **Highest-leverage path.**
2. **White-label "binary-market edge engine" for prop trading desks.** $5–15k/month. ~2–3 month effort.
3. **Calibration / track-record SaaS.** General "Brier score + reliability diagram + edge-decay" service. ~1 month to extract.
4. **Fund strategy.** Tiny ($100k–$1M) pooled fund. Don't do until ≥6 months of paper-trading data with statistically significant edge.

---

## 3. What To Build Next — Top 5 Highest-Leverage Improvements

### #1 — Fix the three HIGH-severity bugs (loose-proxy discount, brief.py gather, brief retry/fallback)
- **Effort:** ~1 day total.
- **EV:** Avoids ~30% loss in the first ruin scenario. Without this, nothing else matters.

### #2 — Automated, timestamped crisis context with staleness penalty
- **What:** Replace hand-edited `crisis_context.py` with an ingestion pipeline that pulls structured event records into a `crisis_events` table; render context from rows with `event_time ≥ now() − 14d`; surface `context_age_seconds` to the LLM and confidence calculation.
- **Effort:** ~1.5 weeks.
- **EV:** Eliminates the highest-correlation failure mode. Enables 24/7 unattended operation. Necessary precondition for live trading.

### #3 — Resolution-scored backtest harness
- **What:** A `backtest/` runner that replays news/prices through the prediction pipeline and produces hit-rate, Brier, edge-realized-vs-predicted, and calibration curve. Critical: strict no-look-ahead guarantee.
- **Effort:** ~2 weeks.
- **EV:** Unlocks every other improvement. You cannot say "the new prompt is better" without it.

### #4 — Port the harness to Polymarket politics (US 2026 midterms)
- **Effort:** ~3–4 weeks.
- **EV:** Only path to enough resolved trades to distinguish signal from noise within a quarter. Polymarket has 10–100× the liquidity of Kalshi geo.

### #5 — Productize a signal API + track record dashboard for a paying audience of one
- **Effort:** ~3 weeks.
- **EV:** $500/month is meaningless as income, but the *fact* of an external paying user is worth $50k of resume value.

---

## Honest Closing Take

This is a strong solo project. The architecture is better than 80% of single-author quant prototypes. The thesis (cascade reasoning beats headline scraping) is defensible.

**The three things that matter most, in order:**

1. Fix the bugs that would convert real edge into noise (proxy discount, gather failure, brief retry).
2. Automate the crisis context — it's the silent ceiling on everything.
3. Treat Iran/Hormuz as the proof-of-concept it is, and port the harness somewhere with enough resolved trades to actually measure edge (Polymarket politics or Kalshi macro).

If I were Adit, I'd freeze new feature work for one week, ship the bug fixes and the gather-failure handling, then spend the next month porting to Polymarket politics in parallel with running Iran on paper. The Iran data is your résumé piece. Politics is where the dollars come from.

— *End of review*
