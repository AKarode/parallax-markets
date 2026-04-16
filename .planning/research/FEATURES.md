# Feature Landscape: Model Intelligence + Resolution Validation

**Domain:** Prediction market edge-finding system (LLM-based, Iran-Hormuz crisis focus)
**Researched:** 2026-04-12
**Milestone:** v1.4 Model Intelligence + Resolution Validation

---

## Table Stakes

Features that the system MUST have for model outputs to be trustworthy and tradeable. Missing any of these means the edge-finding pipeline is structurally broken -- not just suboptimal, but producing signals you cannot trust.

### 1. Full Contract Discovery via API

| Aspect | Detail |
|--------|--------|
| **Why Expected** | Currently only 4 contracts are hardcoded in `INITIAL_CONTRACTS`. Kalshi has 12 event tickers with dozens of child contracts. The system is literally blind to most tradeable instruments. |
| **What It Is** | Programmatic enumeration of all child markets under each event ticker using Kalshi's `/markets?event_ticker=X` and `/events?with_nested_markets=true` endpoints. Catalog resolution criteria, settlement dates, status, volume, and liquidity for each. |
| **Complexity** | Low |
| **Depends On** | Existing `KalshiClient._request()` -- already works for authenticated calls |
| **Existing Code** | `brief.py` lines 773-789 already iterate `IRAN_EVENT_TICKERS` and call `/markets?event_ticker=...`. The gap is that discovered contracts are used for market prices only, never registered in the contract registry. |
| **Implementation** | Extend `_fetch_kalshi_markets()` to also call `registry.upsert()` for every discovered contract. Store `rules_primary`, `rules_secondary` (resolution criteria text), `close_time`, `settlement_timer_seconds`, `volume_fp`, `open_interest_fp`. Mark inactive when status is "closed" or "settled". |
| **Confidence** | HIGH -- Kalshi API docs confirm `/markets` returns `rules_primary`, `rules_secondary`, `settlement_value_dollars`, `status`, `volume_fp`, `open_interest_fp`. Already fetching this data; just not persisting it. |
| **Key Metadata** | Volume (liquidity filter), open interest (market participation), settlement date (time horizon), resolution criteria text (model alignment), price level structure (for oil strike contracts like T80, T135, T140). |

### 2. Model-Contract Alignment: Resolution Criteria Mapping

| Aspect | Detail |
|--------|--------|
| **Why Expected** | The system currently maps models to contracts via hardcoded `proxy_map` dicts. When new contracts are discovered, they have no proxy classification. The mapping policy has no way to handle contracts it has never seen. |
| **What It Is** | Every contract's resolution criteria text (`rules_primary`) must be parsed to determine which model(s) can generate fair-value estimates for it, and at what proxy class (DIRECT, NEAR_PROXY, LOOSE_PROXY, NONE). |
| **Complexity** | Medium |
| **Depends On** | Contract Discovery (above), existing `ProxyClass` enum and `MappingPolicy._estimate_fair_value()` |
| **Existing Code** | `MappingPolicy._classify_contract_family()` already does keyword-based classification into `ContractFamily` enum. `_estimate_fair_value()` dispatches on `(model_id, contract_family)` pairs. |
| **Implementation** | Two-layer approach: (a) rule-based classification using ticker patterns + resolution criteria keywords (extend `_classify_contract_family`), (b) manual override table for edge cases. For each new `ContractFamily` value, add a corresponding fair-value estimator in `_estimate_fair_value()`. New families needed: `IRAN_DEMOCRACY`, `IRAN_LEADERSHIP`, `IRAN_EMBASSY`, `OIL_RIG_COUNT`. |
| **Confidence** | HIGH -- The pattern is already established. The gap is just coverage, not architecture. |
| **Critical Detail** | Oil contracts have a `price_level_structure` (e.g., T80 = $80 strike). Must parse this from the ticker to parameterize the oil extreme probability estimator. Currently only handled for KXWTIMAX/KXWTIMIN parent tickers, not child strike contracts. |

### 3. Market Price Anchoring Removal from Prompts

| Aspect | Detail |
|--------|--------|
| **Why Expected** | All three model prompts currently inject `Current market prices: {market_prices_text}`. Research confirms LLMs exhibit anchoring bias -- presenting market prices before asking for probability estimates systematically biases the model toward the market's view, which is exactly the opposite of finding edge. |
| **What It Is** | Remove market price injection from the prediction prompt. The model should estimate probabilities from fundamentals (news, cascade analysis, crisis context), then the MappingPolicy compares model output to market prices. |
| **Complexity** | Low |
| **Depends On** | Nothing -- this is a prompt change only |
| **Existing Code** | `OIL_PRICE_SYSTEM_PROMPT`, `CEASEFIRE_SYSTEM_PROMPT`, `HORMUZ_SYSTEM_PROMPT` all include `{market_prices_text}`. `_format_market_prices()` in each predictor formats current market state. |
| **Implementation** | Remove `{market_prices_text}` from all three system prompts. Remove the `market_prices` parameter from `predict()` methods. Keep market data flowing to `MappingPolicy.evaluate()` where it belongs -- for edge calculation, not probability estimation. |
| **Research Evidence** | Springer (2025): "forecasts are significantly influenced by prior mention of high or low values." SSRN (2025): "LLM answers are sensitive to biased hints... they anchor their judgments on that information." This is the single highest-ROI prompt fix. |
| **Confidence** | HIGH -- Both research and first-principles reasoning confirm this is a structural flaw. |

### 4. Crisis Context Gap Fill (Aug 2025 - Feb 2026)

| Aspect | Detail |
|--------|--------|
| **Why Expected** | `crisis_context.py` currently has "Background: 2025 Iran-US Tensions" with 3 bullet points covering 6 months. Claude's training cutoff is Aug 2025. The escalation from failed Geneva talks through the June 2025 air conflict to the Feb 2026 war onset is critical context the model lacks. |
| **What It Is** | Research and document the escalation timeline from August 2025 through February 2026: failed nuclear talks, IAEA reports, Iranian enrichment milestones, Israeli intelligence assessments, US force posture changes, Gulf state diplomatic moves. Convert from monolithic string to file-based context system. |
| **Complexity** | Medium (research-intensive, not code-intensive) |
| **Depends On** | Nothing -- standalone research task |
| **Existing Code** | `crisis_context.py` is a single `CRISIS_TIMELINE` string literal, ~130 lines. `get_crisis_context()` returns the whole string. |
| **Implementation** | (a) Research Aug 2025 - Feb 2026 escalation events from news archives. (b) Split context into YAML/JSON files: `context/pre_crisis.yaml`, `context/war_phase.yaml`, `context/ceasefire_phase.yaml`. (c) `get_crisis_context()` assembles from files, with date-gating for backtests. (d) Add market-specific context per contract family. |
| **Confidence** | HIGH for code approach; MEDIUM for historical accuracy (requires manual verification of events) |

### 5. Resolution Backtesting Against Settled Contracts

| Aspect | Detail |
|--------|--------|
| **Why Expected** | The backtest engine (`backtest/engine.py`) currently scores against next-day price movement, not settlement outcomes. This measures day-trading edge, but the actual strategy is hold-to-settlement. Without settlement-based scoring, we cannot validate the core thesis. |
| **What It Is** | Run improved models against historical market prices, generate signals, then score against actual Kalshi settlement outcomes (YES=1.0, NO=0.0). Compute settlement P&L, not mark-to-market P&L. |
| **Complexity** | Medium |
| **Depends On** | Contract Discovery (to know which contracts have settled), Resolution Checker (already exists in `scoring/resolution.py`) |
| **Existing Code** | `backtest/engine.py` has `SETTLEMENT_DATA` dict with `settled: None` for 9 contracts. `_score_results()` compares to next-day price. `scoring/resolution.py` can poll Kalshi for actual settlements. |
| **Implementation** | (a) Populate `SETTLEMENT_DATA` with actual settlement outcomes from Kalshi API. (b) Add `_score_against_settlement()` function that computes: signal correctness (BUY_YES on YES-settled = win), settlement P&L (resolution_price - entry_price), fee-adjusted P&L. (c) Compute aggregate metrics: hit rate, Brier score, calibration gap, fee-adjusted Sharpe, maximum drawdown. |
| **Key Metrics** | Settlement hit rate, Brier score (target < 0.15), calibration bucket gaps, fee-adjusted cumulative P&L, win rate by proxy class. These align with PredictionMarketBench evaluation framework metrics. |
| **Confidence** | HIGH -- `resolution.py` already knows how to check Kalshi settlements. Backtest engine already generates predictions per day. Gap is purely in the scoring function. |

### 6. Track Record Sample Size Guards

| Aspect | Detail |
|--------|--------|
| **Why Expected** | Track records are injected into prompts (e.g., "You predicted X% ceasefire probability 3 times and were right 1 time"). With < 10 data points, these stats are noise. Presenting them to the model as "your track record" could reinforce bad calibration or cause overcorrection. |
| **What It Is** | Only inject track record into prompts when sample size exceeds a minimum threshold (e.g., n >= 10). Below that threshold, inject "Insufficient data for track record (n=X). Rely on your analysis." |
| **Complexity** | Low |
| **Depends On** | Existing `scoring/track_record.py` |
| **Implementation** | Add `min_sample_size` parameter to `build_track_record()`. If count < threshold, return cautionary text instead of misleading statistics. |
| **Confidence** | HIGH -- straightforward guard |

### 7. Bypass Flow Fix in Cascade Engine

| Aspect | Detail |
|--------|--------|
| **Why Expected** | `bypass_flow` is always 0 in the oil price predictor because the cascade engine computation path does not populate it. This means the model sees "bypass_flow=0 bbl/day" even when Saudi/UAE rerouting is happening, giving an artificially pessimistic supply picture. |
| **What It Is** | Actually compute bypass flow from the cascade engine and inject the result into the oil price prompt. |
| **Complexity** | Low |
| **Depends On** | Cascade engine understanding |
| **Existing Code** | `oil_price.py` line 93: `bypass_flow = 0.0`. Never updated. `cascade.py` has bypass computation but it is never called in the predictor. |
| **Implementation** | Call the cascade bypass computation after blockade analysis and feed the result into the prompt. |
| **Confidence** | HIGH -- known bug, clear fix |

---

## Differentiators

Features that create real edge over other prediction market bots. Not expected by baseline, but each one compounds into the system's core value proposition: reasoning depth on second-order effects.

### 1. Rolling Daily Context with Self-Correction

| Aspect | Detail |
|--------|--------|
| **Value Proposition** | Most LLM prediction bots treat each run as stateless -- the model sees today's news but has no memory of what it predicted yesterday or how events evolved. Rolling context gives the model multi-day narrative awareness, enabling detection of trend inflection points that single-snapshot analysis misses. |
| **Complexity** | Medium |
| **Depends On** | Crisis context refactor (file-based system), `prediction_log` table |
| **How It Works** | After each cron run, append a structured JSON summary to a rolling context file: `{date, predictions: {model: prob}, market_prices: {ticker: price}, key_events: [...], outcome_if_known: ...}`. Load the last 5 days of context into prompts. Include self-correction prompt: "Here is what you predicted on previous days and what actually happened. Where were you wrong? What should you update?" |
| **Anti-Anchoring Design** | Present yesterday's prediction AFTER the model has made its initial estimate. Use a two-pass prompt: (1) estimate from fundamentals only, (2) review against yesterday's prediction and revise if warranted with explicit rationale. This avoids self-anchoring while enabling learning. |
| **Research Support** | Temporal pipelines that "embed time as a core dimension of the memory layer, ensuring retrieval that is chronologically coherent" outperform stateless approaches. Sliding window with rolling summaries is the established pattern for LLM memory systems. |
| **Confidence** | MEDIUM -- the approach is well-established in LLM memory research, but the specific implementation for prediction market prompts is novel. Need to test whether self-correction actually improves calibration or just adds noise. |

### 2. Model Registry Pattern (Models as Data)

| Aspect | Detail |
|--------|--------|
| **Value Proposition** | `brief.py` currently hardcodes 3 model instantiations and manually orchestrates calls. Adding a 4th model (e.g., Iran political transition) requires editing brief.py in multiple places. A registry pattern makes models pluggable: add a model by registering it, not by rewriting the pipeline. |
| **Complexity** | Medium |
| **Depends On** | Nothing -- refactoring existing code |
| **How It Works** | Define `ModelSpec` dataclass: `{model_id, predictor_class, contract_families, dependencies, weight}`. Registry stores specs. `run_brief()` iterates registry, instantiates predictors, gathers predictions. New models require only (a) a Predictor class and (b) a registry entry. |
| **Why Not MLflow/Heavy Infra** | This is a single-analyst tool running 3-5 models, not a company-scale ML platform. A simple Python registry (dict of ModelSpec) is the right abstraction. MLflow/Vertex AI model registries are for 100+ models with team collaboration -- massive overkill here. |
| **Confidence** | HIGH -- standard software pattern, low risk |

### 3. Unified Ensemble Aggregation

| Aspect | Detail |
|--------|--------|
| **Value Proposition** | Currently, the portfolio simulator (`simulator.py`) has its own weighted ensemble logic (`_aggregate_signals`) that is completely separate from the live pipeline in `brief.py`. Live signals are evaluated per-model without aggregation. This means backtest results do not reflect live behavior and vice versa. |
| **Complexity** | Medium |
| **Depends On** | Model Registry (above) |
| **How It Works** | Extract the aggregation logic from `simulator.py._aggregate_signals()` into a shared `ensemble/aggregator.py`. Both `brief.py` and `simulator.py` call the same function. Weight signals by `(model_id, proxy_class)` hit rate from `signal_quality_evaluation`. |
| **Research Support** | "Multi-model combination techniques can reduce average Brier score and total number of false alarms, resulting in improved reliability of forecasts." LLM ensemble predictions "rival human crowd accuracy" (Science Advances, 2024). |
| **Key Decision** | Use hit-rate-weighted mean, not equal weighting. The simulator already does this. The gap is that live signals skip this step. |
| **Confidence** | HIGH -- code already exists in simulator. This is extraction + sharing, not invention. |

### 4. New Political Transition Model

| Aspect | Detail |
|--------|--------|
| **Value Proposition** | Kalshi has 6+ event tickers for Iran political outcomes (democracy, Pahlavi, elections, embassy, leadership succession) that currently have `proxy_class: NONE` for all models. These are untradeable because no model generates fair-value estimates for them. Adding a political transition model unlocks 6+ new contract families. |
| **Complexity** | Medium-High |
| **Depends On** | Model Registry, Contract Discovery, Context Gap Fill |
| **How It Works** | New `PoliticalTransitionPredictor` class, same pattern as ceasefire model but focused on regime change, elections, and diplomatic recognition. Input: crisis context + news events. Output: probabilities for regime transition, democratic elections, Pahlavi return, US embassy reopening. |
| **Contract Families** | `IRAN_DEMOCRACY` (KXIRANDEMOCRACY), `IRAN_LEADERSHIP` (KXNEXTIRANLEADER), `PAHLAVI_HEAD` (KXPAHLAVIHEAD), `PAHLAVI_VISIT` (KXPAHLAVIVISITA), `IRAN_EMBASSY` (KXIRANEMBASSY), `RECOGNIZED_PERSON` (KXRECOGPERSONIRAN), `IRAN_ELECTION` (KXELECTIRAN) |
| **Confidence** | MEDIUM -- the model pattern is proven, but political transition probability estimation is harder than oil/ceasefire because base rates are much lower and outcomes more speculative. |

### 5. News Source Diversification

| Aspect | Detail |
|--------|--------|
| **Value Proposition** | Currently dependent on Google News RSS (primary, working) and GDELT DOC API (secondary, frequently 429s). Single-source dependency means blind spots. Wire services and specialist feeds catch stories Google News misses or delays. |
| **Complexity** | Low per source, Medium total |
| **Depends On** | Existing `ingestion/` framework with `NewsEvent` dataclass and `event_hash` dedup |

#### News Source Priority List

| Source | Type | Cost | Latency | Value | Priority |
|--------|------|------|---------|-------|----------|
| Reuters World RSS | RSS | Free | 5-15min | Wire service quality, geopolitical depth | P1 |
| AP News RSS | RSS | Free | 5-15min | Wire service, US policy focus | P1 |
| Al Jazeera Middle East RSS | RSS | Free | 5-15min | Regional perspective, Iran coverage | P1 |
| EIA "This Week in Petroleum" RSS | RSS | Free | Weekly | Official US energy analysis | P1 |
| BBC Middle East RSS | RSS | Free | 5-15min | Global perspective | P2 |
| ACLED API | REST | Free tier | Daily | Structured conflict event data with actors/locations | P2 |
| NewsData.io | REST | Free 200/day | Minutes | 88K sources, geopolitical filter | P2 |
| Oilprice.com RSS | RSS | Free | 15-60min | Oil market specialist | P2 |
| S&P Global Platts | Paid API | $$$$ | Seconds | Gold standard for oil pricing | Out of scope for v1 |
| Bloomberg Terminal API | Paid API | $$$$ | Seconds | Institutional grade | Out of scope for v1 |

| **Confidence** | HIGH for RSS feeds (trivial to implement, same pattern as Google News); MEDIUM for REST APIs (rate limits, auth requirements vary) |

### 6. Prompt Structure: Facts vs Hypothesis Separation

| Aspect | Detail |
|--------|--------|
| **Value Proposition** | Current prompts mix factual context (crisis timeline, news events) with hypothesis injection ("Consider what the market may be missing"). This blurs the line between what the model knows and what it is speculating about. Explicit separation improves reasoning quality by giving the model clear epistemic grounding. |
| **Complexity** | Low |
| **Depends On** | Crisis context refactor |
| **How It Works** | Structure prompts in explicit sections: `## FACTS (verified events)`, `## CURRENT DATA (prices, flows, volumes)`, `## YOUR TASK (estimate probability)`, `## REASONING GUIDELINES (how to think, not what to think)`. Remove suggestive language like "What the market may be missing" -- let the model discover that through analysis. |
| **Research Support** | "Frequency-Based Reasoning, Base Rate First, and Step-Back demonstrated significant benefits relative to the minimalistic control." However: "prompt engineering has a minimal to nonexistent effect on the forecasting performance of LLMs." Takeaway: structure matters for preventing harm (anchoring, suggestion), but do not expect prompt tricks to be magic. Focus on getting the facts right, not the phrasing clever. |
| **Confidence** | MEDIUM -- research is mixed on prompt engineering impact. The value here is more about preventing harm than creating benefit. |

---

## Anti-Features

Features to explicitly NOT build. Common mistakes in this domain that waste time or actively harm signal quality.

### 1. Real-Time Latency Optimization

| Anti-Feature | Why Avoid |
|--------------|-----------|
| **What it is** | Sub-second market data polling, WebSocket streaming, low-latency order submission |
| **Why tempting** | "30%+ of Polymarket wallets are AI bots" -- sounds like a speed race |
| **Why wrong for Parallax** | Edge is reasoning depth, not speed. The system runs 2x/day on cron. Market prices are 5-15min stale by design. The value proposition is finding structural mispricings that persist for hours/days, not arbitraging 400ms information advantages. Round-trip fees (5.5c) already kill active trading. |
| **What to do instead** | Keep 2x/day cron cadence. Focus on reasoning quality over data freshness. |

### 2. Cross-Platform Arbitrage

| Anti-Feature | Why Avoid |
|--------------|-----------|
| **What it is** | Detecting price differences between Kalshi and Polymarket on "equivalent" contracts, buying low on one and selling high on the other |
| **Why tempting** | "Risk-free" profit, multiple GitHub repos show this pattern |
| **Why wrong for Parallax** | (a) Kalshi is paper-trading only -- cannot execute real arb. (b) Contract matching across platforms is a full-time engineering problem (different resolution criteria, different settlement dates). (c) Fees and settlement risk eat the spread. (d) Bots already arbitrage obvious mispricings in milliseconds. |
| **What to do instead** | Use Polymarket as a second price signal for calibration. Compare model outputs to both markets. Do not try to trade the spread. |

### 3. Superforecaster Persona Prompts

| Anti-Feature | Why Avoid |
|--------------|-----------|
| **What it is** | Instructing the LLM to "respond as a superforecaster" or follow "the 10 commandments of superforecasting" |
| **Why tempting** | Sounds like it should improve forecasting quality |
| **Why research says no** | "Superforecaster-authored prompts actually reduced forecasting accuracy." "Prompt engineering has a minimal to nonexistent effect on the forecasting performance of LLMs." The 2025 research across OSF, ICLR, and arxiv is clear: LLM forecasting quality comes from model capability and information quality, not prompt persona tricks. |
| **What to do instead** | Focus on information quality (better context, more sources, accurate facts). Use structured reasoning prompts (base rate, decomposition) but do not expect them to be transformative. Measure actual calibration instead of prompt complexity. |

### 4. Automated Prompt Optimization / DSPy

| Anti-Feature | Why Avoid |
|--------------|-----------|
| **What it is** | Using DSPy or similar frameworks to auto-optimize prompts via gradient descent on forecasting metrics |
| **Why tempting** | "Let the computer figure out the best prompt" |
| **Why wrong now** | (a) Requires hundreds of labeled examples -- we have < 50 signal evaluations. (b) Overfitting to small samples produces prompts that "work" on training data but fail on new events. (c) The cost of running optimization loops against Claude Opus is prohibitive ($20/day budget). (d) Research shows prompt structure matters less than information quality for forecasting. |
| **What to do instead** | Manual A/B testing on specific prompt changes (e.g., anchoring removal). Compare Brier scores before/after. When sample size exceeds 100, revisit automated optimization. |

### 5. Multi-Scenario Expansion (Non-Iran)

| Anti-Feature | Why Avoid |
|--------------|-----------|
| **What it is** | Expanding to predict other domains (elections, crypto, weather) before proving edge on Iran |
| **Why tempting** | More markets = more opportunities |
| **Why wrong now** | The entire system architecture is tuned for the Iran-Hormuz crisis: cascade engine, crisis context, domain-specific models. Generalizing before validating on the core domain is premature abstraction. The ceasefire window ends April 21 -- this is the validation deadline. |
| **What to do instead** | Prove edge on Iran first. If settlement P&L is positive and Brier < 0.15, then consider expansion in v2.0. |

### 6. Complex Ensemble Methods (Bayesian Model Averaging, Stacking)

| Anti-Feature | Why Avoid |
|--------------|-----------|
| **What it is** | Sophisticated ensemble techniques that weight models dynamically based on posterior probabilities or learned meta-models |
| **Why tempting** | "More sophisticated = more accurate" |
| **Why wrong now** | With 3-5 models and < 50 resolved signals, there is not enough data to train a meta-model or compute meaningful Bayesian posteriors. Hit-rate-weighted mean is the right level of sophistication for the current sample size. |
| **What to do instead** | Use hit-rate-weighted ensemble (already in simulator). Track per-model Brier scores. When sample size exceeds 200 per model, consider Bayesian model averaging. |

### 7. Active Exit/Sell Trading

| Anti-Feature | Why Avoid |
|--------------|-----------|
| **What it is** | Selling positions before settlement based on mark-to-market P&L or model probability changes |
| **Why established as wrong** | Round-trip fees of 5.5c vs hold-to-settlement fees of 2.8c. Fee math kills active exits. This was already validated and documented as a key decision in PROJECT.md. |
| **What to do instead** | Hold to settlement. Track edge decay data. Revisit only if fee structure changes or sample size reveals specific conditions where early exit is profitable net of fees. |

---

## Feature Dependencies

```
Contract Discovery
    |
    +---> Model-Contract Alignment (needs contracts to classify)
    |         |
    |         +---> New Political Model (needs contract families defined)
    |         |
    |         +---> Resolution Backtest (needs settlement data from discovered contracts)
    |
    +---> Bypass Flow Fix (independent, but tested against discovered contracts)

Crisis Context Gap Fill
    |
    +---> Rolling Daily Context (needs file-based context system)
    |
    +---> New Political Model (needs pre-crisis political context)

Anchoring Removal  <-- INDEPENDENT, can ship immediately
Track Record Guards <-- INDEPENDENT, can ship immediately
Bypass Flow Fix    <-- INDEPENDENT, can ship immediately

Model Registry
    |
    +---> Unified Ensemble (needs registry to iterate models)
    |
    +---> New Political Model (registered as new model spec)

News Diversification <-- INDEPENDENT per source, can ship incrementally

Prompt Structure Refactor
    |
    +---> Anchoring Removal (specific case of prompt restructuring)
```

---

## MVP Recommendation

For this milestone, prioritize in this order:

### Must Ship (validates core thesis)

1. **Anchoring Removal** -- Highest ROI fix. Research-backed. 30 minutes of work. Removes structural bias from every prediction.
2. **Bypass Flow Fix** -- Known bug producing incorrect cascade analysis. Quick fix.
3. **Track Record Guards** -- Prevents small-sample noise from polluting predictions. Quick fix.
4. **Contract Discovery** -- Unlocks visibility into 12 event tickers and all child contracts. Required foundation for everything else.
5. **Model-Contract Alignment** -- Makes discovered contracts tradeable. Requires new proxy classifications and fair-value estimators for each contract family.
6. **Resolution Backtesting** -- Validates hold-to-settlement thesis. Required to know if the system has actual edge.
7. **Crisis Context Gap Fill** -- Fills the 6-month knowledge hole. Research-intensive but high impact on model accuracy.

### Should Ship (improves signal quality)

8. **Model Registry** -- Enables adding new models without pipeline surgery. Required before political model.
9. **Unified Ensemble** -- Makes backtest and live pipeline consistent. Straightforward extraction from existing simulator code.
10. **Prompt Structure Refactor** -- Facts vs hypothesis separation. Moderate impact, low risk.
11. **News Diversification (P1 sources)** -- Reuters, AP, Al Jazeera RSS feeds. Same implementation pattern as existing Google News, low effort per source.

### Defer to post-validation

12. **Rolling Daily Context** -- High value but needs careful anti-anchoring design. Ship after settlement-based validation proves the base system works.
13. **New Political Model** -- Depends on registry + context + alignment. Ship after core models are validated against settlements.
14. **News Diversification (P2 sources)** -- ACLED, NewsData.io, etc. Incremental value, ship after core pipeline is solid.

---

## Scoring Metrics for Settlement-Based Validation

Based on PredictionMarketBench evaluation framework and forecasting research, these are the metrics that matter for a hold-to-settlement strategy:

| Metric | What It Measures | Target | Current State |
|--------|-----------------|--------|---------------|
| Settlement Hit Rate | % of BUY signals that settle in the money | > 55% | Unknown (no settlement scoring) |
| Brier Score | Calibration + discrimination combined | < 0.15 | Unknown |
| Calibration Gap | Max |predicted - actual| across probability buckets | < 0.10 | N/A (insufficient data) |
| Fee-Adjusted P&L | Cumulative settlement P&L minus all fees | > $0 | -$0.35 (next-day scoring, not settlement) |
| Sharpe Ratio | Risk-adjusted return | > 0.5 annualized | N/A |
| Win Rate by Proxy Class | Hit rate for DIRECT vs NEAR_PROXY vs LOOSE_PROXY | DIRECT > NEAR > LOOSE | Unknown |
| Edge Size vs Outcome | Correlation between predicted edge size and actual profit | Positive | Unknown |

Note: Prediction markets historically achieve Brier scores near 0.09. The system's target of < 0.15 is deliberately conservative -- achieving it would indicate the models are producing useful probability estimates, even if not yet at market-aggregate quality.

---

## Sources

### Contract Discovery
- [Kalshi Get Events API](https://docs.kalshi.com/api-reference/events/get-events) -- `with_nested_markets` parameter, HIGH confidence
- [Kalshi Get Markets API](https://docs.kalshi.com/api-reference/market/get-markets) -- `event_ticker`, `status`, `volume_fp`, `rules_primary` fields, HIGH confidence
- [Kalshi API Guide 2026](https://pm.wiki/learn/kalshi-api) -- four-level hierarchy (Categories > Series > Events > Markets), MEDIUM confidence

### Anchoring Bias
- [Anchoring Bias in LLMs (Springer, 2025)](https://link.springer.com/article/10.1007/s42001-025-00435-2) -- "forecasts significantly influenced by prior mention of high or low values", HIGH confidence
- [Anchoring Bias in LLMs (arxiv, 2024)](https://arxiv.org/html/2412.06593v1) -- "like humans, they anchor their judgments on that information", HIGH confidence
- [Human Bias in AI Models (ScienceDirect)](https://www.sciencedirect.com/science/article/pii/S2214635024000868) -- mitigation strategies have mixed effectiveness, MEDIUM confidence

### Prompt Engineering for Forecasting
- [Prompt Engineering LLM Forecasting (OSF, 2025)](https://osf.io/mcr78/) -- "prompt engineering has minimal to nonexistent effect on forecasting performance", HIGH confidence
- [LLM vs Superforecasters (arxiv, 2025)](https://arxiv.org/html/2507.04562v3) -- "experts achieve Brier 0.023 vs o3's 0.135", HIGH confidence
- [LLM Ensemble Prediction (Science Advances, 2024)](https://www.science.org/doi/10.1126/sciadv.adp1528) -- ensemble predictions rival human crowd accuracy, HIGH confidence

### Backtesting Framework
- [PredictionMarketBench (arxiv, Jan 2026)](https://arxiv.org/html/2602.00133) -- standardized metrics for prediction market agent evaluation including P&L, drawdown, Sharpe, fees, fill ratio, HIGH confidence
- [PredictionMarketBench GitHub](https://github.com/Oddpool/PredictionMarketBench) -- open source framework with Kalshi replay data, HIGH confidence

### News Sources
- [Free News APIs 2026 (NewsData.io)](https://newsdata.io/blog/best-free-news-api/) -- tested APIs with rate limits and limitations, MEDIUM confidence
- [Reuters RSS Feeds](https://rss.feedspot.com/reuters_rss_feeds/) -- feed URLs for world, business, politics, HIGH confidence
- [ACLED Conflict Data](https://acleddata.com/) -- structured conflict event data with actors/locations, MEDIUM confidence

### Ensemble and Calibration
- [Brier Score (Wikipedia)](https://en.wikipedia.org/wiki/Brier_score) -- scoring rule definition and decomposition, HIGH confidence
- [Multi-Model Ensemble Review (ScienceDirect, 2026)](https://www.sciencedirect.com/science/article/abs/pii/S1474706526001245) -- 89-study survey of aggregation methods, MEDIUM confidence
- [Weighted Brier Score (PMC)](https://pmc.ncbi.nlm.nih.gov/articles/PMC12523994/) -- clinical utility weighted variants, MEDIUM confidence

### Temporal Context / Memory
- [LLM Context Problem 2026 (LogRocket)](https://blog.logrocket.com/llm-context-problem/) -- sliding windows, rolling summaries, hierarchical compression, MEDIUM confidence
- [Temporal Cognification (Cognee)](https://www.cognee.ai/blog/cognee-news/unlock-your-llm-s-time-awareness-introducing-temporal-cognification) -- time-aware memory, temporal knowledge graphs, LOW confidence
- [Memory for AI Agents (ICLR 2026 Workshop)](https://openreview.net/pdf?id=U51WxL382H) -- agent memory survey, MEDIUM confidence

### Model Registry
- [MLflow Model Registry](https://mlflow.org/docs/latest/ml/model-registry/) -- centralized lifecycle management pattern, HIGH confidence (for understanding pattern; actual tool is overkill for this project)
