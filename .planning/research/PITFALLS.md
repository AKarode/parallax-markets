# Domain Pitfalls: v1.4 Model Intelligence + Resolution Validation

**Domain:** Adding model intelligence, contract discovery, news diversification, and resolution backtesting to an existing prediction market edge-finder
**Project:** Parallax
**Researched:** 2026-04-12
**Overall Confidence:** HIGH (grounded in direct codebase analysis + verified domain research)

---

## Critical Pitfalls

Mistakes that cause wrong predictions, bad trades, or require significant rework.

---

### Pitfall C-1: Market Price Anchoring Bias in LLM Prompts

**What goes wrong:** All 3 prediction model prompts currently inject current market prices _before_ asking the model "what is the market missing?" Research confirms LLMs exhibit anchoring bias in 17.8-57.3% of instances -- the model locks onto initial parameters and rarely challenges them. The oil_price prompt (line 37 of oil_price.py) includes `Current market prices: {market_prices_text}` followed by `Consider what the market may already be pricing in`. The ceasefire and hormuz prompts have the identical pattern. The LLM reads market YES at 48%, then outputs 45-52% -- never deviating far because it is cognitively anchored to the number it just read.

**Why it happens:** The prompts were designed with good intent -- "tell the model what the market thinks so it can spot disagreements." But LLM anchoring research (2025 ACL, Springer) shows this is backwards: providing the anchor constrains the output. Reasoning models are less prone to anchoring when given a long chain of thought, but the prompts request 500-1000 words of reasoning _after_ the anchor is injected, not before.

**Consequences:**
- Model predictions cluster near market prices, producing tiny edges that are eaten by fees (2.8c hold-to-settlement cost)
- The system generates HOLD signals for 80%+ of contracts because divergences never exceed the 5% minimum edge threshold
- The entire value proposition (reasoning deeper than headline bots) is nullified because the model is just parroting the market price it was shown

**Warning signs:**
- Model probability within +/-5% of market price on >70% of predictions
- Edge distribution heavily clustered at 0-3% (below fee threshold)
- Backtest results show model predictions track market prices rather than leading them

**Prevention:**
1. Remove market prices from prediction prompts entirely. Let models reason independently first
2. If market context is needed, inject it _after_ the model has committed to a probability: "You predicted X%. The market says Y%. Would you revise?" as a separate follow-up call
3. Add an anchoring detection metric: correlate model output probability with market price input across runs. If correlation > 0.7, the model is anchored
4. For the backtest engine, verify that removing market prices changes model outputs -- if removing them does NOT change outputs, the anchoring was minimal and this pitfall is less severe than expected

**Which phase should address it:** Phase 1 (Prompt Optimization). This is the single highest-ROI fix -- it directly affects whether the system generates any tradable edge at all.

**Confidence:** HIGH -- visible in oil_price.py:37, ceasefire.py:40, hormuz.py:48 (all inject `{market_prices_text}`). Anchoring research confirmed via ACL 2025 paper and Springer 2025 study.

---

### Pitfall C-2: Hypothesis Injection Masquerading as Context

**What goes wrong:** `crisis_context.py` ends with a section titled "What The Market May Be Missing" (lines 117-125) that contains 5 editorial opinions:
- "Pakistan talks produced no agreement after 21 hours -- market may be slow to price in failure"
- "Hormuz 'reopening' is theater -- 8 ships vs 100+/day pre-war"
- "Ceasefire window is only 10 days -- pressure mounts daily"
- "Iran's 10-point counterproposal includes sanctions relief -- very ambitious asks"
- "Even if ceasefire holds, formal agreement is a much higher bar"

These are conclusions, not facts. They pre-load the model's reasoning direction. Combined with the market price anchoring (C-1), the model is told both WHAT the market thinks AND what it SHOULD think differently. The "independent reasoning" step is illusory.

**Why it happens:** The analyst who wrote the context naturally included their own analysis alongside the facts. The line between "critical context Claude needs" and "conclusions Claude should reach independently" was not drawn.

**Consequences:**
- All 3 models converge on the same editorial viewpoint because they share the same injected hypothesis
- Model diversity (the reason for having 3 models) is destroyed -- they are 3 copies of the same opinion, not 3 independent perspectives
- When the analyst's hypothesis is wrong (e.g., market correctly prices the talk failure), all 3 models are wrong in the same direction
- No error-correcting benefit from the ensemble because errors are correlated

**Warning signs:**
- All 3 models cite the same reasoning themes in their output
- Model predictions move in the same direction for unrelated contracts (ceasefire and oil both shift bearish because of the same injected hypothesis)
- Removing the "What The Market May Be Missing" section changes all 3 models' outputs in the same direction

**Prevention:**
1. Split crisis_context.py into FACTS (timeline, prices, contract definitions) and ANALYSIS (hypotheses, opinions). Only inject FACTS into model prompts
2. If analysis is useful, create model-specific analysis. The oil model should get oil-specific analysis; the ceasefire model should get diplomacy-specific analysis. Never share the same editorial across all models
3. Add a peer-review step: before updating crisis_context.py, tag each bullet as FACT or OPINION. Only FACT bullets go in the base context
4. Test for hypothesis leakage: run models with and without the analysis section. If removing it changes the output direction, the model was anchored to the hypothesis

**Which phase should address it:** Phase 1 (Prompt Optimization), immediately after C-1. Facts go in context files; opinions stay out.

**Confidence:** HIGH -- directly visible in crisis_context.py lines 117-125. The "What The Market May Be Missing" header literally labels the content as editorial.

---

### Pitfall C-3: Split-Brain Aggregation Between Live Signals and Backtest Simulator

**What goes wrong:** `brief.py` (live pipeline) and `simulator.py` (backtest) both aggregate signals from multiple models into trading decisions, but they use completely different logic:

- **brief.py**: Iterates through predictions, maps each to contracts via MappingPolicy, records individual signals, applies oil deconfliction, then feeds to Kelly allocator. Signals are evaluated independently per model-contract pair. No weighted ensemble.
- **simulator.py**: Groups signals by run_id, then calls `_aggregate_signals()` which does weighted-average ensemble by hit rate: `combined_edge = sum(weight * edge) / total_weight`. Signals that individually would be HOLD can become BUY if their weighted average clears the threshold.

The two paths can produce different trade decisions on the same underlying data. A contract that gets HOLD in the live pipeline could get BUY in the simulator, or vice versa.

**Why it happens:** The simulator was built after the live pipeline, during the backtest phase, to support a new aggregation strategy. The live pipeline was not updated to match. The two evolved independently.

**Consequences:**
- Backtest results do not predict live performance because they use different decision logic
- The system has two "sources of truth" for what constitutes a tradable signal
- Any improvement to one path (e.g., fixing aggregation weights) must be manually replicated in the other
- Validation of the hold-to-settlement thesis via backtesting is unreliable because the simulated portfolio uses different entry criteria than live would

**Warning signs:**
- Backtest shows positive P&L but live pipeline generates mostly HOLD signals (or vice versa)
- Edge thresholds differ: simulator uses 5% (EDGE_THRESHOLD constant), live pipeline uses MappingPolicy's min_effective_edge_pct (also 5%, but after different cost deductions)
- Simulator uses a fixed DEFAULT_HIT_RATE=0.5 fallback; live pipeline has no such concept

**Prevention:**
1. Extract the aggregation logic into a shared module that both brief.py and simulator.py import
2. Define the canonical signal-to-trade path once: prediction -> mapping -> signal -> aggregation -> sizing -> trade. Both live and backtest must use this exact path
3. Add an integration test that feeds the same predictions through both paths and asserts identical trade decisions
4. When refactoring to model registry pattern, make aggregation part of the registry, not a separate concern in each entry point

**Which phase should address it:** Phase 2 (Unified Ensemble). This must be solved before running resolution backtests, otherwise backtest results are meaningless for predicting live performance.

**Confidence:** HIGH -- directly visible in brief.py lines 537-559 vs simulator.py lines 305-369. The code paths are completely different.

---

### Pitfall C-4: Lookahead Bias in Resolution Backtesting

**What goes wrong:** The backtest engine (backtest/engine.py) builds "date-limited context" using a timeline.json file that was written with full knowledge of how events unfolded. Even though the code truncates the timeline at the test date (line 69: `if entry["date"] <= as_of_date`), the timeline entries themselves were written with hindsight. For example, an entry for April 3 might say "F-15E shot down over Iran" -- but in real time on April 3, the full picture (pilot rescued, WSO missing 48hrs) wasn't known for hours or days.

Additionally, the backtest monkey-patches `crisis_context.get_crisis_context` (line 203-205), but the date-limited context includes the "Prediction Market Contract Context" section (line 102-106) with prices that reflect aggregate knowledge ("WTI max >$140 at ~42%"). If these market-level summaries were not available on the test date, this is information leakage.

**Why it happens:** It is extremely difficult to reconstruct "what was known at time T" from post-hoc summaries. The backtest engine makes a good-faith effort with date filtering, but the content quality of each entry carries unavoidable hindsight.

**Consequences:**
- Backtest results are optimistically biased -- the model performs better in backtests than it would have in real time because it has cleaner, more complete context
- Win rates and P&L from backtests overestimate real-world performance
- The validation window (April 7-21) produces false confidence in model accuracy

**Warning signs:**
- Backtest accuracy significantly exceeds live accuracy on the same time period
- Model reasoning in backtests cites facts that were not publicly available at the test date
- Backtest P&L is positive but live P&L is negative or flat

**Prevention:**
1. For each timeline entry, add a `known_at` timestamp (when the information was first publicly reported, not when the event occurred). Filter on `known_at <= as_of_date`, not `date <= as_of_date`
2. Source timeline entries from archived news snapshots (Google News RSS at time T, Internet Archive), not from retrospective summaries
3. Remove the "Prediction Market Contract Context" section from backtest context entirely -- or replace with actual market prices on that date (which the backtest already has in backtest_prices.json)
4. Add a "hindsight audit" step: for each backtest day, compare the context the model received vs. what a human analyst with only a news RSS feed would have known. Flag discrepancies
5. Score backtests conservatively: apply a "hindsight discount" of 10-20% to backtest accuracy when comparing to live performance expectations

**Which phase should address it:** Phase 5 (Resolution Backtesting). Must be addressed before drawing any conclusions from backtest results.

**Confidence:** HIGH -- directly visible in backtest/engine.py. The monkey-patching pattern (line 203-205) and the timeline structure make the lookahead risk architectural.

---

### Pitfall C-5: Hormuz Prompt Asks for Two Probabilities, JSON Captures One

**What goes wrong:** The Hormuz prompt (hormuz.py lines 46-47) asks the model to estimate:
- "(a) Probability of partial reopening (>25% flow restored) within 14 days"
- "(b) Probability of full reopening within 30 days"

But the JSON output schema (lines 49-55) only has a single `"probability"` field. The model outputs one number, and the code (line 141) captures it as `parsed["probability"]`. The second probability (full reopening within 30 days) is silently discarded -- it may appear in the reasoning text but is never captured as structured data.

**Why it happens:** The prompt was written with a richer output schema in mind, but the JSON format was simplified without updating the prompt text.

**Consequences:**
- The captured probability is ambiguous: is it partial reopening or full reopening? Different Claude runs may interpret the question differently
- The Hormuz model produces inconsistent outputs because the prompt and schema disagree
- The lost second probability (full reopening 30d) could be mapped to a different contract set but isn't

**Prevention:**
1. Either update the JSON schema to capture both probabilities: `"partial_reopening_14d": float, "full_reopening_30d": float`
2. Or simplify the prompt to ask for exactly one probability that matches the schema
3. If adding a second probability, update PredictionOutput schema or use the `metadata` field to carry the additional value
4. Map each probability to its corresponding contract set: partial reopening -> near-term Hormuz contracts, full reopening -> longer-dated contracts

**Which phase should address it:** Phase 1 (Prompt Optimization). This is a simple fix but the ambiguity actively degrades prediction quality right now.

**Confidence:** HIGH -- directly visible in hormuz.py prompt text vs JSON schema.

---

## Moderate Pitfalls

Mistakes that cause degraded signal quality, missed opportunities, or technical debt.

---

### Pitfall M-1: bypass_flow Always Zero, Oil Model Biased Toward Total Disruption

**What goes wrong:** In oil_price.py, `bypass_flow` is initialized to 0.0 (line 92) and never updated. The cascade engine computes supply_loss from blocked/restricted cells (lines 96-99), but there is no corresponding code to compute bypass flow through alternate routes (Suez, pipelines, SPR releases). The prompt receives `Bypass flow: 0 bbl/day through alternate routes`, telling the LLM that zero oil is flowing through alternatives -- which biases it toward maximum disruption scenarios.

**Why it happens:** The cascade engine has bypass computation logic (`compute_bypass_flow` or similar), but the oil_price predictor never calls it. The WorldState has no cells with "bypass" status because the H3 spatial layer was pruned.

**Consequences:**
- Oil price model systematically overestimates disruption impact
- Predictions skew bullish on oil, generating BUY_YES signals on KXWTIMAX contracts that may not materialize
- The cascade analysis provided to the LLM is incomplete -- it sees 2.5M bbl/day disruption with zero mitigation, when in reality 30-50% is bypassed

**Prevention:**
1. Either compute bypass_flow from real data (EIA Strategic Petroleum Reserve releases, pipeline capacity, tanker rerouting data) and inject it
2. Or remove bypass_flow from the prompt entirely if it cannot be computed accurately -- a missing field is better than a wrong one
3. If keeping the field, add a hardcoded conservative estimate based on known bypass capacity (e.g., 5-8M bbl/day through non-Hormuz routes) until real-time data is available
4. Add a validation check: if supply_loss > 0 and bypass_flow == 0, log a warning -- this combination means zero mitigation, which is almost never true

**Which phase should address it:** Phase 1 (Prompt Optimization). Quick fix: either remove or hardcode a reasonable estimate.

**Confidence:** HIGH -- directly visible in oil_price.py line 92. `bypass_flow = 0.0` is never reassigned.

---

### Pitfall M-2: Track Record Injection Without Minimum Sample Size

**What goes wrong:** `track_record.py` injects hit rate statistics into model prompts with no minimum sample size guard. With 3 resolved signals, a 3/3 record becomes "Your track record: 3/3 correct (100% hit rate)." This makes the model overconfident. With 1/3, it says "33% hit rate" and may make the model overly cautious. In both cases, 3 signals is far too few for meaningful statistics.

**Why it happens:** The function returns results for `total > 0` (line 46: `if row is None or row[0] == 0`). There is no minimum threshold.

**Consequences:**
- With a small winning streak, the model becomes overconfident and takes larger positions
- With a small losing streak, the model becomes excessively conservative and misses real edges
- The track record noise dominates the signal at small sample sizes, effectively randomizing model behavior based on a handful of early outcomes

**Prevention:**
1. Add a minimum sample size of 10-20 resolved signals before injecting track record. Below that threshold, return the "No track record available yet" fallback
2. Include confidence intervals: "3/3 correct (100% hit rate, but only 3 samples -- could be 30-100% with reasonable confidence)"
3. Weight recent signals more heavily than old ones (recency bias is actually desirable here -- recent calibration data is more relevant)
4. Separate track record by proxy class: a model's accuracy on DIRECT contracts tells you nothing about its accuracy on LOOSE_PROXY contracts

**Which phase should address it:** Phase 1 (Prompt Optimization). Add a 10-signal minimum guard to build_track_record().

**Confidence:** HIGH -- directly visible in track_record.py line 46. No sample size check exists.

---

### Pitfall M-3: News Source SPOF -- Google News RSS Is the Only Working Source

**What goes wrong:** GDELT DOC API returns 429 errors frequently (confirmed dead in milestone analysis). Truth Social feed (`truth_social.py`) was added for POTUS signals but only covers one account. Google News RSS is the sole reliable news source. If Google changes their RSS format, adds rate limiting, or blocks the IP, the system has zero news input and all 3 models run with "No recent events available" context.

**Why it happens:** GDELT was the secondary source but died. No replacement was added. The system has graceful degradation (models still run with empty events), but empty-context predictions are essentially random.

**Consequences:**
- Single point of failure for the most critical input (news events)
- No diversity of perspective -- Google News RSS has its own editorial selection bias
- Missing non-English language sources (Persian media, Arabic media) that may carry signals before English-language outlets
- During a fast-moving crisis, 5-15 minute RSS latency may be too slow vs real-time sources

**Warning signs:**
- Google News fetch returns 0 events for multiple consecutive runs
- All models cite only Google News headlines in their evidence fields
- Predictions fail to react to events that broke on Twitter/X hours before appearing in Google News

**Prevention:**
1. Add Reuters/AP RSS feeds as parallel sources (these are free via RSS, same pattern as Google News)
2. Add oil-specific feeds: OilPrice.com RSS, Argus Media RSS, Platts RSS
3. For Twitter/X: avoid the $100/mo API. Use RSS Bridge or Nitter-alternative scraping for key journalist lists (10-20 accounts like @BarakRavid, @Joyce_Karam, @LOABORAMI). Rate limit carefully
4. Implement source health monitoring: if any source returns 0 events for 3 consecutive runs, alert and switch to backup
5. Add a "news diversity score" metric: count unique sources per run. If <2, flag degraded coverage
6. Stagger RSS fetches across sources to avoid simultaneous failures

**Which phase should address it:** Phase 3 (News Diversification). High priority because it reduces the SPOF risk.

**Confidence:** HIGH for the SPOF diagnosis. MEDIUM for Twitter/X alternatives (rate limits and scraping reliability are unpredictable).

---

### Pitfall M-4: Contract Discovery Registering Stale or Illiquid Contracts

**What goes wrong:** The Kalshi client fetches child markets for 12 event tickers, but only 4 are registered in INITIAL_CONTRACTS (registry.py lines 20-77). When expanding to register all discovered contracts, the system may register:
- Settled contracts (status "determined"/"finalized") that can no longer be traded
- Illiquid contracts with zero volume or wide spreads (>10c) where the model's edge cannot be profitably executed
- Expired contracts past their resolution date
- Duplicate child contracts that resolve on the same underlying event at different thresholds (e.g., KXWTIMAX-26DEC31-T135, -T140, -T150 are all oil max contracts at different strikes)

Currently, `_fetch_kalshi_markets()` in brief.py (line 781) filters for `status in ("open", "active")`, but the registry has no liquidity or volume filter.

**Why it happens:** The registry was designed for manual curation of 4 well-understood contracts. Automated discovery at scale introduces contracts the system has never been classified for proxy mapping.

**Consequences:**
- Signals generated for illiquid contracts waste LLM budget and cannot be executed
- Stale contracts in the registry produce confusing signals ("BUY_YES on a settled contract")
- Too many low-quality contracts dilute the signal-to-noise ratio of the output
- Without proxy classification for new contracts, they all get mapped as GENERIC_BINARY with no fair-value estimator, producing non-tradable results

**Prevention:**
1. Add discovery filters: minimum volume (>1000 contracts traded), maximum spread (<8c), status must be "open" or "active", resolution date must be in the future
2. For each discovered contract, auto-classify the contract family from the ticker pattern (WTIMAX -> OIL_PRICE_MAX, etc.) but require manual proxy classification before trading
3. Add a "discovered but unclassified" state in the registry -- contracts are fetched and tracked for market prices but not traded until classified
4. Implement periodic staleness checks: if a registered contract goes inactive or settles, mark it inactive in the registry
5. For threshold variants (T135, T140, T150), implement a "best strike" selector that picks the contract closest to the model's predicted level, not all of them

**Which phase should address it:** Phase 4 (Contract Discovery). The discovery-classification-activation pipeline must be phased -- discover first, classify second, activate for trading third.

**Confidence:** HIGH -- the 4-of-12 gap is documented in milestone analysis. The API behavior (fetched but discarded) is visible in brief.py lines 773-789.

---

### Pitfall M-5: Rolling Context JSON Unbounded Growth

**What goes wrong:** The planned rolling daily context feature auto-appends structured JSON per cron run with a 5-day rolling window. At 2 runs/day for 5 days, that's 10 context snapshots. Each snapshot includes: news events (20 headlines), predictions (3 models with reasoning), market prices (12+ tickers), and signals. Conservative estimate: 1,500-2,500 tokens per snapshot. Five days: 15,000-25,000 tokens of context prepended to every model call.

Combined with the crisis timeline (~3,000 tokens), track record (~200 tokens), cascade analysis (~500 tokens), and market prices (~300 tokens), the total context reaches 20,000-30,000 tokens before the model even starts reasoning. This is fine for Opus's 200K context window, but research shows LLM performance degrades as context grows -- accuracy can drop from 95% to 60% past certain thresholds, and the "lost in the middle" problem means context placed in the middle of long inputs gets 30%+ accuracy drops.

**Why it happens:** The instinct is "more context = better predictions." But research on context rot (Chroma 2025) shows that semantically similar but irrelevant content actively misleads the model, and the effective context window is far below the advertised limit.

**Consequences:**
- Model accuracy degrades as rolling context grows, despite the system having more information
- Older context entries (day 1 of 5) are in the "lost in the middle" zone and effectively ignored
- Token costs increase linearly -- at 25K extra tokens per call, 3 models per run, 2 runs/day = 150K extra tokens/day at ~$0.005/run overhead (manageable under $20 budget, but measurable)
- Stale predictions from 3-4 days ago may contradict current evidence, confusing the model

**Prevention:**
1. Implement aggressive summarization: don't carry raw snapshots. Summarize each day's context into 200-300 tokens using a cheap model (Haiku) before injecting into prediction prompts
2. Use a recency-weighted structure: most recent run gets full detail (500 tokens), yesterday gets summary (200 tokens), 2-3 days ago get key changes only (100 tokens each). Total: ~1,000 tokens instead of 25,000
3. Place rolling context near the END of the prompt, not the beginning -- this puts it in the "recency" attention zone instead of the "lost in the middle" zone
4. Add a "delta-only" mode: instead of full snapshots, carry only what changed since last run. "Oil up $3, ceasefire talks stalled, no new signals" is 20 tokens vs 2,500
5. Set a hard token budget for rolling context (e.g., 3,000 tokens max) and enforce truncation at insertion time

**Which phase should address it:** Phase 3 (Rolling Context). Design the summarization pipeline before building the accumulation pipeline.

**Confidence:** MEDIUM-HIGH. The token arithmetic is straightforward. The performance degradation claim is backed by Chroma 2025 research, but the exact impact on this system's specific prompts is unknown without testing.

---

### Pitfall M-6: 4th Model (Iran Political Transition) Conflicting with Existing Models

**What goes wrong:** Adding a 4th model for "Iran political transition" / regime change contracts creates signal conflicts with the existing ceasefire model. Both models reason about Iranian domestic politics: the ceasefire model asks "will there be a formal agreement?" and the political transition model asks "will there be a regime change?" These are partially correlated but not identical -- a regime change could accelerate or delay a formal agreement depending on who takes power. If both models generate signals on overlapping contracts (e.g., KXUSAIRANAGREEMENT), their signals may conflict (one says BUY_YES, the other says BUY_NO on the same contract).

**Why it happens:** The existing 3 models have well-separated domains (oil, ceasefire, Hormuz). A 4th model breaks this clean separation by overlapping with the ceasefire model's domain.

**Consequences:**
- Conflicting signals on the same contract without a clear resolution mechanism
- The oil deconfliction logic (`_deconflict_oil_signals` in brief.py) only handles oil contract conflicts -- no equivalent exists for ceasefire vs political transition
- Without a weighted ensemble, the system may execute both conflicting signals, opening opposing positions on the same contract
- Prompt token budget increases by ~4,000 tokens per run (crisis context + prompt), pushing total to ~20K tokens per run across 4 models

**Prevention:**
1. Define strict domain boundaries: the political transition model owns KXIRANDEMOCRACY, KXELECTIRAN, KXPAHLAVIHEAD, KXPAHLAVIVISITA, KXNEXTIRANLEADER contracts. The ceasefire model does NOT generate signals on these contracts
2. For contracts that both models are relevant to (e.g., KXUSAIRANAGREEMENT), define one as primary and one as secondary via proxy classification. Primary generates the signal; secondary contributes to ensemble weighting
3. Add a generalized deconfliction function (not just oil): for any contract with conflicting signals from different models, keep the signal from the model with the DIRECT or NEAR_PROXY classification and suppress the LOOSE_PROXY signal
4. Add the 4th model to the model registry pattern (not hardcoded like the current 3)
5. Budget check: 4 Opus calls at ~5K tokens each = ~$0.04/run. Still within budget but track it

**Which phase should address it:** Phase 4 (Model Registry + 4th Model). Design the deconfliction generalization before adding the new model.

**Confidence:** MEDIUM -- the domain overlap is architectural, but the exact contracts and signal patterns depend on how the 4th model is scoped.

---

### Pitfall M-7: File-Based Context System Path Resolution Across Environments

**What goes wrong:** Converting the hardcoded `CRISIS_TIMELINE` string in crisis_context.py to a file-based system (e.g., `backend/data/context/crisis_timeline.md`) introduces path resolution issues across 3 environments:
- **Local development**: `python -m parallax.cli.brief` from repo root -- relative paths work
- **Docker**: backend runs from `/app/` -- file must be in the Docker image or mounted volume
- **Tests**: pytest runs from various working directories -- path must resolve from test context
- **Backtest**: engine.py monkey-patches `get_crisis_context()` (line 203) -- file-based system needs a different override mechanism

Currently, crisis_context.py uses a Python string literal, so it works everywhere. Moving to files introduces a deployment and testing surface area that does not currently exist.

**Why it happens:** Python string constants are zero-deployment-cost. File-based systems require the file to exist at the expected path in every environment.

**Consequences:**
- FileNotFoundError in Docker if context files are not COPY'd into the image
- Tests that mock context need a different mocking strategy (no more monkey-patching a function)
- Backtest date-limited context injection breaks if the file-reading function doesn't accept date parameters
- Context updates require redeploying/restarting (no hot-reload) unless a file watcher is added

**Prevention:**
1. Use `importlib.resources` or `pkg_resources` to bundle context files as package data, avoiding absolute path issues
2. Or keep the default context as a Python constant (fallback) with an optional file override path via environment variable: `PARALLAX_CONTEXT_DIR=/path/to/context/`
3. Add a `--context-dir` CLI argument to brief.py for easy local override
4. For Docker: add context files to `COPY` in Dockerfile and set the env var
5. For backtest: instead of monkey-patching, pass a `context_override: str | None` parameter through the prediction call chain. If provided, use it instead of file/default
6. Add a startup check: if context files are expected but missing, fail fast with a clear error, not silently fall back to empty context

**Which phase should address it:** Phase 2 (Pre-Crisis Context + File System). Design the resolution strategy before migrating any content to files.

**Confidence:** HIGH -- the backtest monkey-patching pattern (backtest/engine.py line 203-205) confirms that context injection needs a clean override mechanism. The Docker COPY requirement is standard.

---

### Pitfall M-8: New RSS Sources Producing Duplicate or Irrelevant Events

**What goes wrong:** Adding Reuters, AP, oil-specific feeds, and Twitter/X lists alongside Google News RSS multiplies the volume of ingested events. The current deduplication is URL-hash based (google_news.py line 46: `hashlib.md5(self.url.encode())`). This catches exact URL duplicates but NOT:
- Same story from different publishers (Reuters headline vs AP headline about the same press conference)
- Same underlying event with different URLs (Google News redirect URL vs direct publisher URL)
- Translated duplicates (Persian/Arabic source in English translation)
- Twitter thread summarizing a Reuters story

Without content-level deduplication, the models receive 5x more events but the same number of unique incidents, causing the "media attention bias" problem (Pitfall 4 from original PITFALLS.md, still relevant).

**Why it happens:** URL-hash dedup was sufficient when Google News RSS was the only source. With multiple sources covering the same events, content-level dedup becomes necessary.

**Consequences:**
- Models weight heavily-covered events more than genuinely important but under-covered events
- Token budget consumed on redundant news items (20 events at ~50 tokens each = 1,000 tokens wasted if 50% are duplicates)
- Diplomatic keyword filter in ceasefire model (ceasefire.py `_filter_diplomatic()`) may over-trigger on duplicate diplomatic coverage, biasing the ceasefire model

**Prevention:**
1. Add title-level fuzzy dedup: normalize titles (lowercase, remove punctuation, strip source attributions), compute SimHash or Jaccard similarity. Threshold: 0.85 similarity = duplicate
2. Group events by incident: (actor, action, timeframe) clustering. "Iran talks" + "Islamabad negotiations" + "Vance meets Iranian delegation" should cluster as one incident
3. Add a source diversity score per event cluster: prefer clusters with 3+ sources (broad coverage = more important) but emit only one representative event per cluster
4. For Twitter/X sources: mark with lower weight or "supplementary" flag -- tweets should add context to existing events, not create new standalone events
5. Set a per-source rate limit: max 10 events per source per run to prevent any single source from dominating
6. The current `seen_hashes` pattern (shared across Google News, GDELT, Truth Social) is good -- extend it to new sources

**Which phase should address it:** Phase 3 (News Diversification). Implement dedup upgrades BEFORE adding new sources, not after.

**Confidence:** MEDIUM-HIGH. The URL-hash-only dedup is visible in google_news.py. The duplicate problem at scale is well-documented in news aggregation literature. The exact duplication rate across planned sources is unknown without testing.

---

## Minor Pitfalls

Mistakes that cause debugging time, minor regressions, or incremental tech debt.

---

### Pitfall L-1: Model Registry Refactor Breaking Existing Test Mocks

**What goes wrong:** Refactoring brief.py from hardcoded model calls (lines 491-499) to a registry pattern changes the import structure, constructor signatures, and call patterns that existing tests mock. Tests that mock `OilPricePredictor.predict()` directly will break when the predictor is instantiated via a registry lookup instead of explicit construction.

**Prevention:**
1. Keep the existing test interface stable: the registry wraps the existing predictor classes, it does not replace them
2. Use dependency injection: the registry accepts predictor instances at construction time (for testing) or auto-discovers them (for production)
3. Add registry-level integration tests alongside existing unit tests, don't delete unit tests
4. Refactor incrementally: first make the registry call the same 3 predictors in the same way, verify tests pass, THEN add 4th model

**Which phase should address it:** Phase 4 (Model Registry). Incremental refactoring with test preservation.

**Confidence:** HIGH -- the test suite (192 tests) depends on the current structure. Any refactor risk is proportional to the number of tests that mock prediction internals.

---

### Pitfall L-2: Kalshi API Rate Limits During Contract Discovery

**What goes wrong:** Enumerating child contracts for 12 event tickers requires at least 12 GET /markets requests (one per event_ticker), plus individual GET /markets/{ticker} calls for each discovered child contract to get orderbook data. At 12 events x ~5-10 child contracts each = 60-120 API calls. Kalshi's Basic tier allows 20 reads/second, so a full discovery sweep takes 3-6 seconds. But if the discovery runs as part of the normal brief pipeline (every cron run), that's 60-120 extra API calls per run on top of existing market price fetches.

**Prevention:**
1. Run contract discovery separately from the brief pipeline -- a daily or weekly discovery cron, not every run
2. Cache discovered contracts in DuckDB. Only re-fetch if the contract wasn't checked in the last 24 hours
3. Add exponential backoff for 429 responses. Kalshi returns 429 on rate limit; the current client (kalshi.py) raises KalshiAPIError without retry
4. Batch discovery: fetch all child markets per event_ticker in one call (the `/markets?event_ticker=X` endpoint already does this), don't make individual calls
5. Monitor API usage: track calls per minute and alert if approaching tier limits

**Which phase should address it:** Phase 4 (Contract Discovery). Separate discovery from the hot path.

**Confidence:** HIGH -- Kalshi rate limits confirmed at 20 reads/sec for Basic tier via official docs.

---

### Pitfall L-3: Pre-Crisis Context Gap (Aug 2025 - Feb 2026) Poorly Researched

**What goes wrong:** crisis_context.py has only 3 bullet points for the 6-month pre-war escalation (Aug 2025 - Feb 2026): "failed nuclear negotiations," "brief 12-day air conflict," "tensions continued to escalate." This period is critical for the models' understanding of WHY the war started and what diplomatic/military patterns preceded it. Without this context, models cannot reason about historical precedent ("the last time talks failed, X happened within 2 weeks").

**Prevention:**
1. Research and write 15-20 bullet points covering Aug 2025 - Feb 2026, sourced from archived news
2. Key events to cover: Geneva talks timeline, June 2025 air conflict details (what started it, how it ended, market reaction), uranium enrichment milestones, sanctions changes, IAEA reports, key diplomatic personnel changes
3. Structure chronologically with clear dates
4. Separate from the Feb 2026+ timeline -- this is "background" context, not "crisis" context
5. Keep it factual (learning from C-2: no editorial in context)

**Which phase should address it:** Phase 2 (Pre-Crisis Context). Research task that produces a data file.

**Confidence:** MEDIUM -- the gap is visible in crisis_context.py lines 20-24. The impact on model quality is uncertain without A/B testing with vs without the expanded context.

---

### Pitfall L-4: Backtest Scoring Uses Next-Day Price Movement, Not Settlement

**What goes wrong:** The backtest scoring function (`_score_results` in backtest/engine.py, lines 277-377) evaluates model accuracy by comparing today's prediction to tomorrow's market price movement: `correct = model_says_buy_yes == market_went_up`. But the system's actual strategy is hold-to-settlement, not day-trading. A contract can move against the position for days and still settle in your favor. Scoring on next-day price movement penalizes correct long-term predictions that happen to have short-term adverse movement.

**Prevention:**
1. Score backtests against actual settlement outcomes (where available), not next-day price movements
2. For unsettled contracts, score against the final market price at the end of the backtest window as a proxy for eventual settlement
3. Add a "hold-to-settlement" scoring mode that ignores intermediate price movements entirely
4. Report both metrics separately: "directional accuracy" (next-day) and "settlement accuracy" for different analytical purposes
5. The existing P&L calculation (`pnl = next_close - today_close`) should be replaced with settlement P&L for realistic performance assessment

**Which phase should address it:** Phase 5 (Resolution Backtesting). The scoring methodology must match the actual trading strategy.

**Confidence:** HIGH -- directly visible in backtest/engine.py lines 306 and 316. The scoring logic explicitly uses `next_close` instead of settlement price.

---

## Phase-Specific Warnings

| Phase | Likely Pitfall | Severity | Mitigation |
|-------|---------------|----------|------------|
| 1: Prompt Optimization | Market price anchoring (C-1), hypothesis injection (C-2), Hormuz dual-probability (C-5), bypass_flow=0 (M-1), track record sample size (M-2) | CRITICAL | Remove anchoring, split facts from opinions, fix schema mismatch |
| 2: Pre-Crisis Context + File System | Path resolution across environments (M-7), context gap (L-3) | MODERATE | Use pkg_resources or env var override, research Aug 2025-Feb 2026 events |
| 2: Unified Ensemble | Split-brain aggregation (C-3) | CRITICAL | Extract shared aggregation module, add cross-path tests |
| 3: News Diversification | News SPOF (M-3), duplicate events (M-8), Twitter/X rate limits | MODERATE | Add feeds incrementally, implement content-level dedup first |
| 3: Rolling Context | JSON unbounded growth (M-5), context rot | MODERATE | Summarize before injecting, set hard token budget, recency-weight |
| 4: Contract Discovery | Stale/illiquid contracts (M-4), API rate limits (L-2) | MODERATE | Separate discovery from hot path, add liquidity filters, cache results |
| 4: Model Registry + 4th Model | Test breakage (L-1), signal conflicts (M-6) | MODERATE | Incremental refactor, generalize deconfliction |
| 5: Resolution Backtesting | Lookahead bias (C-4), next-day scoring (L-4) | CRITICAL | Use point-in-time data, score against settlement not price movement |

---

## Integration-Specific Meta-Pitfall: Fixing Prompts Without Measuring the Baseline

**What goes wrong:** The milestone involves fixing multiple prompt issues (anchoring, hypothesis injection, bypass_flow, dual probability, track record). If all fixes are applied simultaneously, there is no way to attribute improvements or regressions to specific changes. Did the model improve because anchoring was removed, or worsen because the hypothesis injection was also removed? Without baselines and isolated testing, prompt optimization becomes guesswork.

**Prevention:**
1. Before making any prompt changes, run the current prompts through the backtest suite and record baseline accuracy metrics per model
2. Apply changes one at a time, rerunning backtests after each change
3. Track prompt versions with hashes or sequential IDs -- log which prompt version produced each prediction
4. At minimum, measure: (a) prediction variance (are outputs less clustered near market prices?), (b) edge magnitude (are edges larger?), (c) directional accuracy (are predictions more often correct?)
5. If testing one-at-a-time is too expensive (each backtest costs ~$0.50 in Opus calls), at least do: baseline -> all changes -> measure delta. Then selectively revert changes that seem harmful

**Which phase should address it:** Phase 1 (Prompt Optimization). Baseline measurement is the FIRST step, before any prompt edits.

---

## Sources

### Codebase (PRIMARY -- HIGH confidence)
- `backend/src/parallax/prediction/oil_price.py` -- market price injection, bypass_flow=0
- `backend/src/parallax/prediction/ceasefire.py` -- market price injection, diplomatic filtering
- `backend/src/parallax/prediction/hormuz.py` -- dual probability spec mismatch
- `backend/src/parallax/prediction/crisis_context.py` -- hypothesis injection, pre-crisis gap
- `backend/src/parallax/cli/brief.py` -- live signal pipeline, no ensemble aggregation
- `backend/src/parallax/portfolio/simulator.py` -- backtest aggregation, split-brain logic
- `backend/src/parallax/contracts/registry.py` -- 4 of 12 contracts registered
- `backend/src/parallax/contracts/mapping_policy.py` -- fair value estimation, cost model
- `backend/src/parallax/scoring/track_record.py` -- no sample size minimum
- `backend/src/parallax/scoring/resolution.py` -- settlement backfill logic
- `backend/src/parallax/backtest/engine.py` -- lookahead bias, next-day scoring
- `backend/src/parallax/markets/kalshi.py` -- 12 event tickers, API client
- `backend/src/parallax/ingestion/google_news.py` -- URL-hash-only dedup
- `backend/src/parallax/ingestion/gdelt_doc.py` -- dead source (429s)

### Research (MEDIUM confidence)
- ACL 2025 / Springer 2025: LLM anchoring bias -- models influenced by initial parameters 17-57% of instances
- Chroma 2025: Context rot -- irrelevant content actively misleads models, performance degrades with context length
- Paulsen 2025: Effective context windows fall far below advertised limits, up to 99% on complex tasks
- Kalshi official docs: Basic tier rate limits at 20 reads/sec, 10 writes/sec
- News aggregation literature: URL dedup insufficient for multi-source; SimHash/Jaccard needed for content dedup
- Backtesting literature: lookahead bias is the most common mistake; point-in-time data required

---

*Pitfalls audit: 2026-04-12 (v1.4 milestone: model intelligence + resolution validation)*
