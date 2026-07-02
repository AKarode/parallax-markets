# Parallax — Project Postmortem

**Status:** Research concluded, June 2026.
**Verdict:** The core hypothesis — that an LLM reasoning system can find and profitably trade mispriced prediction-market contracts — was **falsified**. A live crisis-window run, a synthetic backtest, and a structural-arbitrage probe each returned a null, consistent with the published external evidence; a fourth experiment (a calibration audit) established which parts of the system are worth keeping. Total capital risked: **$0**. Total experiment cost: roughly $40 of API calls.

This document records what was hypothesized, what was built, what the experiments showed, why the thesis failed, and what survives.

---

## 1. The hypothesis

> During a fast-moving geopolitical crisis, prediction markets misprice contracts because most participants react to headlines. An LLM that reasons about **second-order cascade effects** (a Hormuz blockade disrupts oil flow → flow reroutes → prices shock → insurance spirals) can produce better probability estimates than the market, and the divergence between model probability and market price is a tradeable edge.

The test bed was the Iran–Hormuz crisis of early 2026 (Strait closed February 28; the April 7–21 ceasefire window was the validation deadline). Venues: Kalshi (production API for prices, demo sandbox for paper execution) and Polymarket (read-only).

## 2. What was built

About **16,000 lines of Python** across **244 commits** (March 30 – June 4, 2026), with **535 tests**, deployed and running unattended on a VPS via systemd timers:

- **Ingestion** — Google News RSS, GDELT DOC 2.0, EIA oil prices (Brent/WTI), Truth Social, with entity filtering and multi-layer deduplication (hash + 21-day fuzzy).
- **Prediction** — three Claude-powered models (oil price direction, ceasefire probability, Hormuz reopening), each an ensemble of 3 calls with trimmed-mean aggregation and instability flagging, fed by a 6-rule physical cascade simulation and a manually maintained crisis-context timeline (the crisis postdated the models' training cutoff).
- **Trading** — divergence detector, proxy-aware contract mapping with explicit edge discounting, quarter-Kelly position sizing, paper execution against real bid/ask quotes with fee and slippage modeling, full signal → order → fill → settlement lifecycle in an append-only ledger.
- **Evaluation** — daily scorecard ETL (15+ metrics), calibration curves, edge-decay tracking, settlement polling and outcome backfill, a $20/day LLM budget enforcer, and a React dashboard.
- **Infrastructure** — FastAPI (14 endpoints), DuckDB with an async single-writer queue, Docker Compose, systemd deployment with `--no-trade` as the fail-safe default.

## 3. The experiments and what they showed

### 3.1 Live crisis-window run: execution, not prediction, was the binding constraint

The pipeline ran twice daily through the crisis window. The signal ledger recorded **75 signals; 67 of them (89%) were REFUSED for having no executable quote**. Only 4 ever resolved — too few for the recalibration feedback loop (gated at 10 resolved samples) to fire even once. Realized P&L: entirely NULL — **zero executed trades**.

The architecture ran news → LLM forecast → *try to find a matching contract*, and most forecasts had nothing fillable to map to (the Kalshi demo sandbox carries no geopolitical markets at all, and production geopolitical books were thin). The loudest finding in the project's own data is that **the funnel was inverted**: tradability should gate the pipeline before the LLM ever runs.

### 3.2 Synthetic backtest: no directional skill demonstrated

A 13-day backtest over the crisis window replayed archived news through the prediction models against recorded market prices: **46% win rate, −$0.35 P&L**. Not a catastrophic loss — a coin flip minus fees, which is exactly what "no edge" looks like.

### 3.3 KalshiBench calibration audit: recalibration measurably improves stated LLM confidence

The live pipeline never accumulated enough resolved outcomes to test its forecast → resolve → score → recalibrate loop on its own data (§3.1). To test the loop at all, I pointed it at **KalshiBench-v2** (1,531 resolved Kalshi questions) across three Claude models, with grouped 5-fold out-of-fold cross-validation and cluster-bootstrap confidence intervals (`docs/KALSHIBENCH-CALIBRATION.md`, `docs/reports/kalshibench-2026-06-04/`):

- **Isotonic recalibration significantly beat raw model confidence on 3/3 models** (Brier, 95% CI excluding zero).
- The project's own bucket-offset recalibrator beat raw on 2/3 — but was **non-monotonic on 3/3 models**, a structural defect (it can re-order forecasts) that standard calibrators avoid by construction. The harness caught a real bug in the project's method.
- Honest caveat, stated first in the report: the benchmark's questions resolved inside the models' training cutoff, so this measures calibration of stated confidence, **not** forecasting skill on unknown futures.

### 3.4 Coherence-arbitrage probe: the last structurally-defensible angle, killed for $0

After the directional thesis died, the one remaining angle that needed patience rather than latency was same-venue coherence arbitrage: Polymarket prices the 2026 midterm balance-of-power as joint outcomes *and* as standalone chamber markets, and the two must algebraically agree. A stdlib-only probe polled all 7 legs every 5 minutes from a $1,000 paper book (`docs/COHERENCE-ARB-PROBE-RESULTS.md`):

- Best net taker gap ever observed: **−2.25¢** (negative — no riskless arb at any poll, even before the 4% taker fee made it worse).
- Maker-side incoherence was **sub-tick** (±0.85¢ on a 1¢ grid); it cleared a full tick in **0 of 292 observations**. You cannot even rest a limit order at the price that would capture it.
- Top-of-book prices were *identical* across the 6-hour interim window (73 polls; the probe continued autonomously to a 24-hour tally). The book isn't just coherent; it's inert.

### 3.5 External evidence converged on the same answer

A separate research pass (7 web-grounded agents, cross-checked by two independent LLM reviewers; `docs/PROFITABILITY-STRATEGY-2026-06.md`) found: as of mid-2026 there is **no documented case of a standalone LLM-reasoning system profitably trading a real-money prediction market**; the strongest published agentic forecaster still loses to liquid-market consensus on hard questions; Kalshi takers lose ~31% and even makers ~12% on average (the exchange rake is the house edge); and 84% of 2.5M Polymarket wallets lost money, with durable winners almost all being sub-second arbitrage bots. An adversarial kill-pass on five candidate pivot strategies returned zero "promising" verdicts.

## 4. Root causes

1. **The funnel was inverted.** Forecast-first, find-a-contract-second meant 89% of signals died at execution. Market-universe-first with a tradability gate should have been the day-one architecture.
2. **The LLM was treated as ground truth instead of a tilt.** The published evidence says LLM-alone loses to liquid consensus head-to-head; only a market-anchored blend (~⅔ market + ⅓ model) adds value. Trading the raw divergence — Parallax's core loop — is precisely the documented losing configuration.
3. **News-heavy context is a documented failure mode for LLM forecasts.** Recency bias and rumor overweighting degrade accuracy (with domain-dependent severity); the pipeline was 100% news-RSS-driven, with no base-rate anchor the news couldn't override.
4. **Fees are the house edge.** With takers at −31% and makers at −12% average, a strategy needs a large gross edge just to reach zero. No prediction-quality improvement fixes a structurally negative execution layer.
5. **Validation infrastructure was built after the trading loop instead of before it.** The scorecard, calibration, and resolution machinery — the parts that ultimately produced the real findings — arrived weeks after the first signals fired.

## 5. What I'd do differently

- Run the $0 falsification tests **first**. The coherence probe cost nothing and returned a decisive answer in six hours; the equivalent tests for the directional thesis (closing-line-value logging, maker-fill realism) were formulated only at the end.
- Gate on tradability before spending a single LLM token.
- Pre-register kill criteria from the start. The later experiments (coherence probe, KalshiBench) had explicit "KILL if…" conditions written down in advance and produced clean, arguable conclusions; the early trading loop did not, and its stopping point had to be reconstructed after the fact.
- Use standard calibrators (isotonic/Platt) instead of inventing a bucket-offset scheme — the invented one turned out non-monotonic.

## 6. What worked and what survives

- **The evaluation discipline.** Out-of-fold CV, cluster bootstrap CIs, pre-registered kill switches, adversarial review of every major claim, and leakage caveats stated before headline numbers. The null result is trustworthy *because* of this machinery.
- **The calibration harness** (`parallax.bench.kalshibench`) — a self-contained, reusable tool for auditing any LLM's probability calibration against resolved ground truth, with reliability diagrams and honest CIs.
- **The Kalshi client** — production-grade RSA-PSS request signing, pagination, v2 field handling.
- **The paper-trading ledger** — full-lifecycle signal provenance with real execution semantics (bid/ask, fees, slippage), reusable for any strategy that does deserve testing.
- **The operational pattern** — unattended cron pipeline with budget enforcement, fail-safe defaults, and alerting, running for months without intervention.

## 7. Cost accounting

| Item | Cost |
|---|---|
| Capital risked | $0 (paper only, by design) |
| LLM API (pipeline, ~2 runs/day for the crisis window) | ~$1–5/month |
| KalshiBench forecasts (3 models × 1,531 questions) | ~$10 |
| Research + probes | ~$10 of API, one $29 one-time data purchase |
| VPS | shared with other projects |

## 8. Conclusion

The strategy failed; the engineering didn't. The system did what a research platform is supposed to do: it made the hypothesis precise, built the machinery to test it, ran the tests, and believed the results — including the ones that said "stop." Most quant hypotheses are wrong. The valuable output of this project is not a trading edge; it is a falsified thesis with receipts, and a set of reusable evaluation tools that made the falsification cheap.
