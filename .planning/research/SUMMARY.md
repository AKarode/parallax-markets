# Research Summary: v1.4 Model Intelligence + Resolution Validation

**Project:** Parallax — Prediction Market Edge-Finder
**Researched:** 2026-04-12
**Confidence:** HIGH

## Executive Summary

The v1.4 milestone addresses structural flaws in the prediction pipeline that likely explain the system's inability to generate tradeable edge (46% win rate, -$0.35 P&L). Research across four dimensions reveals that the highest-ROI fixes are prompt-level (removing market price anchoring, separating facts from hypotheses) and data-level (filling the 6-month context gap, diversifying news sources). Architectural changes (model registry, unified ensemble) are enablers for new capabilities but lower priority than fixing what the existing models see and how they reason.

Only 1 new dependency is needed (`feedparser>=6.0.11`). All other changes use existing stack (httpx, DuckDB, stdlib). 6 dead dependencies should be removed (~2GB install savings).

## Key Findings

### Stack Additions
- **Only 1 new dependency:** `feedparser>=6.0.11` for RSS parsing of AP/Reuters feeds
- **Reuters RSS officially dead** (discontinued June 2020) — AP News has 40+ active feeds, use those first
- **Twitter/X costs ~$2/day** for 10 journalist accounts — viable under $20/day budget, use existing httpx (not tweepy/xdk)
- **Platts/Argus inaccessible** ($10K+/yr) — EIA weekly petroleum inventory (same API key, different endpoint) fills the oil data gap for free
- **Kalshi contract enumeration** uses existing `KalshiClient` — `GET /events/{ticker}?with_nested_markets=true` discovers all child markets
- **Model registry** is a 15-line stdlib Python pattern (dict + decorator), no external library needed
- **6 dead dependencies to remove:** h3, sentence-transformers, searoute, shapely, google-cloud-bigquery, websockets

### Feature Table Stakes
1. **Anchoring removal** — highest ROI fix, 30 min of work, research-backed (LLMs anchor 17-57% of time)
2. **Bypass flow fix** — always 0, never computed, biases oil model toward total disruption
3. **Track record sample size guards** — n<10 stats are noise, not signal
4. **Contract discovery** — 4 of 12+ event tickers registered, system blind to most contracts
5. **Model-contract alignment** — discovered contracts need proxy classification + fair-value estimators
6. **Resolution backtesting** — the ONLY valid test of hold-to-settlement thesis
7. **Crisis context gap fill** — 3 bullet points for 6 months of pre-war escalation

### Feature Differentiators
1. **Rolling daily context with self-correction** — temporal awareness + yesterday's prediction feedback
2. **Model registry pattern** — models as data, not hardcoded calls
3. **Unified ensemble aggregation** — extract from simulator, share with live pipeline
4. **New political transition model** — unlocks 6+ unmodeled contract families
5. **News source diversification** — AP RSS, Al Jazeera, EIA weekly, optional X journalist monitoring
6. **Prompt structure: facts vs hypotheses** — separate context from editorial

### Anti-Features (DO NOT BUILD)
- Superforecaster persona prompts (research shows they *reduce* accuracy)
- DSPy/automated prompt optimization (insufficient data, $20/day budget)
- Cross-platform arbitrage (paper trading only, can't execute)
- Complex ensemble methods (n<50, hit-rate-weighted mean is correct level)
- Active exit/sell trading (fee math kills it)
- Multi-scenario expansion (prove Iran edge first)
- Real-time latency optimization (edge is reasoning depth, not speed)

### Architecture Approach
- All 8 changes integrate cleanly via existing interfaces (PredictionOutput, NewsEvent, ContractRecord, get_crisis_context())
- No breaking changes to any interface
- **Critical gap:** live pipeline (brief.py) and simulator have split-brain aggregation — must unify
- **Build order:** Foundation (registry, context files, quick fixes) → New Capabilities (discovery, political model, rolling context) → Integration (ensemble, backtest)
- Parallel opportunities within each phase — changes touch different files/modules

### Critical Pitfalls
1. **C-1: Market price anchoring** — all 3 prompts inject prices before asking "what's the market missing?" Models cluster within +/-5% of market price. Highest-impact fix.
2. **C-2: Hypothesis injection** — "What The Market May Be Missing" section pre-loads conclusions across all 3 models, destroying ensemble diversity
3. **C-3: Split-brain aggregation** — brief.py and simulator.py use different signal-to-trade logic; backtest results don't predict live performance
4. **C-4: Lookahead bias in backtest** — timeline written with hindsight, scoring uses next-day movement instead of settlement
5. **C-5: Rolling context must be summarized** — raw 5-day window could reach 25K tokens, degrading accuracy. Summarize, don't accumulate.

## Watch Out For
- Kalshi "historical cutoff" — very old settled contracts may not be available via API. Test with Iran tickers before investing in backtest infrastructure.
- Prompt engineering has minimal effect on LLM forecasting (OSF 2025). Value is in preventing harm (anchoring) and information quality (context), not clever phrasing.
- Political contracts likely have very low base rates — model may be correct but untestable in near term.
- News deduplication needs upgrading before adding sources — URL-hash-only dedup will flood models with duplicate stories from different outlets.

## Implications for Roadmap

**Recommended phase structure (3 phases with internal parallelism):**

**Phase A — Foundation + Quick Fixes:**
- Anchoring removal (all 3 prompts)
- Bypass flow fix
- Track record sample size guards
- Hormuz dual-probability spec fix
- File-based context system (move strings to files)
- Model registry refactor in brief.py
- Dead dependency cleanup

**Phase B — Discovery + New Capabilities:**
- Contract discovery (enumerate all Kalshi child markets)
- Model-contract alignment (proxy classification for discovered contracts)
- Pre-crisis context research + writing (Aug 2025 - Feb 2026)
- News source diversification (AP RSS, Al Jazeera, EIA weekly)
- New political transition model
- Rolling daily context pipeline

**Phase C — Validation:**
- Unified ensemble (extract from simulator, share with live pipeline)
- Resolution backtest on settled contracts
- Settlement-based scoring metrics (Brier, hit rate, fee-adjusted P&L)

---
*Research completed: 2026-04-12*
*Ready for roadmap: yes*
