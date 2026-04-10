# Model Intelligence Improvements -- Design Spec

**Date:** 2026-04-09
**Status:** Deferred (depends on dashboard completion)
**Scope:** Three improvements to prediction model quality: multi-day context, reflection calls, news impact tracking

## Context

The prediction models currently operate on single-run snapshots. Each run fetches today's headlines, generates probabilities, and forgets everything. This limits the system in three ways:

1. Models can't distinguish novel developments from recurring noise
2. Models never learn from their own mistakes across runs
3. We don't know which news events actually move markets

These improvements are deferred until after the dashboard is built -- the dashboard provides the visualization layer to validate whether these changes actually improve calibration.

## Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| News window size | 3-5 days rolling | Matches ceasefire validation window cadence; beyond 5 days, geopolitical context shifts too much |
| Reflection model | Single Sonnet call, not a separate model | Cost is ~$0.007/call, keeps total under $0.10/day |
| Impact tracking granularity | Per-event, per-contract | Need to know which event types move which contracts, not just aggregate impact |
| Storage | DuckDB (existing) | Already have 20+ tables, schema migration pattern established |
| News dedup strategy | Title similarity + source + 24h window | RSS feeds repeat headlines; GDELT returns overlapping articles |

## What We Are NOT Building

- **Fine-tuned models.** We use Claude Sonnet via API. No training, no embeddings for prediction.
- **Real-time news processing.** Still batch (2x/day cron). Not streaming.
- **Automated prompt tuning.** Reflection informs the human operator, not a self-modifying prompt loop.
- **Cross-model ensemble.** Each predictor (oil, ceasefire, hormuz) stays independent. Cascade reasoning already connects them.

---

## Improvement 1: Multi-Day News Context

### Problem

Models see a flat list of today's headlines. They can't tell:
- "First mention of naval exercises" (big signal) vs "day 5 of same exercises" (priced in)
- Three consecutive days of hawkish rhetoric (escalation pattern) vs one-off statement
- Whether a headline is genuinely new or a rehash of yesterday's story

### Architecture

```
Google News RSS ──┐
                  ├──> news_events table (DuckDB, deduplicated)
GDELT DOC API ────┘           |
                              v
                    Rolling Context Builder
                    (query last N days, group by topic/entity,
                     label "new" vs "recurring")
                              |
                              v
                    Structured context block
                    injected into prediction prompts
```

### Schema Addition

```sql
CREATE TABLE IF NOT EXISTS news_events (
    event_id        VARCHAR PRIMARY KEY,  -- hash of title + source + date
    title           VARCHAR NOT NULL,
    source          VARCHAR,
    url             VARCHAR,
    published_at    TIMESTAMP NOT NULL,
    ingested_at     TIMESTAMP DEFAULT now(),
    entities        VARCHAR[],            -- matched critical entities
    topic_cluster   VARCHAR,              -- assigned during context build
    first_seen_date DATE,                 -- earliest appearance of this topic cluster
    raw_snippet     VARCHAR
);
```

### Context Builder Output

The context builder produces a structured block per topic cluster:

```
[TOPIC: Iranian naval exercises in Strait of Hormuz]
- Status: RECURRING (first seen 2026-04-05, day 4)
- Trajectory: STABLE (similar coverage volume each day)
- Today's developments: None new
- Key entities: IRGC Navy, Strait of Hormuz, USS Eisenhower

[TOPIC: Saudi-Iran backchannel talks]
- Status: NEW (first seen today)
- Trajectory: N/A
- Today's developments: Reuters exclusive citing unnamed diplomats
- Key entities: Saudi Arabia, Iran, Oman (mediator)
```

### Prompt Integration

Replace the current raw headline dump in each predictor's prompt with:

```
## News Context (rolling 5-day window)

### New Developments (weight heavily)
{new_topic_blocks}

### Ongoing Situations (already partially priced in)
{recurring_topic_blocks}

### Trajectory Signals
- Escalation indicators: {count} new hawkish events vs {count} dovish
- Coverage volume trend: {rising/stable/falling}
```

### Modules Touched

| File | Change |
|------|--------|
| `db/schema.py` | Add `news_events` table |
| `ingestion/google_news.py` | Write events to `news_events` with dedup |
| `ingestion/gdelt_doc.py` | Write events to `news_events` with dedup |
| `prediction/oil_price.py` | Accept structured context instead of raw headlines |
| `prediction/ceasefire.py` | Same |
| `prediction/hormuz.py` | Same |
| `cli/brief.py` | Build rolling context before prediction calls |

### New Module

`ingestion/context_builder.py` -- queries `news_events` for last N days, clusters by entity overlap, labels new vs recurring, formats structured context block.

---

## Improvement 2: Reflection Model Call

### Problem

Each run is stateless. The model never sees:
- Whether yesterday's prediction was right or wrong
- Whether today's evidence is genuinely new or the same data repackaged
- Whether the edge that justified a trade entry still exists

### Architecture

```
Yesterday's predictions ──┐
  (from predictions table) │
                           ├──> Reflection Prompt (Claude Sonnet)
Today's predictions ───────┤         |
  (just computed)          │         v
                           │    ReflectionOutput
Market price deltas ───────┤    - accuracy_assessment
  (yesterday vs today)    │    - edge_status (growing/shrinking/gone)
                           │    - novelty_flag (new_signal / same_signal)
New events since ──────────┘    - reasoning (free text)
  yesterday
```

### Data Model

```python
@dataclass
class ReflectionOutput:
    run_id: str
    model_name: str                          # "oil_price" | "ceasefire" | "hormuz"
    accuracy_assessment: str                  # free text: what was right/wrong
    edge_status: str                         # "growing" | "stable" | "shrinking" | "gone"
    novelty_flag: str                        # "new_signal" | "same_signal" | "mixed"
    confidence_adjustment: float             # suggested delta to apply (-0.1 to +0.1)
    reasoning: str                           # full reasoning chain
    timestamp: datetime
```

### Schema Addition

```sql
CREATE TABLE IF NOT EXISTS reflections (
    reflection_id   VARCHAR PRIMARY KEY,
    run_id          VARCHAR NOT NULL,
    model_name      VARCHAR NOT NULL,
    accuracy_note   VARCHAR,
    edge_status     VARCHAR,              -- growing | stable | shrinking | gone
    novelty_flag    VARCHAR,              -- new_signal | same_signal | mixed
    confidence_adj  DOUBLE,
    reasoning       VARCHAR,
    created_at      TIMESTAMP DEFAULT now()
);
```

### Prompt Template (sketch)

```
You are reviewing your own prediction performance.

## Yesterday's Prediction ({model_name})
- Probability: {yesterday_prob}
- Reasoning: {yesterday_reasoning}
- Market price at time: {yesterday_market_price}

## Today's Prediction ({model_name})
- Probability: {today_prob}
- Reasoning: {today_reasoning}
- Market price now: {today_market_price}

## What happened in between
- Market price moved: {price_delta} ({direction})
- New events: {new_events_summary}

Answer these three questions:
1. Was yesterday's prediction directionally correct? What did you miss?
2. Has the edge (model vs market divergence) grown or shrunk? Is the trade thesis still intact?
3. Is today's prediction based on genuinely new evidence, or are you seeing the same signal and reaching the same conclusion?

Respond as JSON with fields: accuracy_assessment, edge_status, novelty_flag, confidence_adjustment, reasoning.
```

### Cost

- 1 extra Sonnet call per run: ~$0.007
- 2 runs/day: $0.014/day additional
- Total daily spend moves from ~$0.06 to ~$0.074 (vs $20/day budget cap)

### Exit Logic Connection

The `edge_status` field from reflection is the missing piece for intelligent exits. When edge_status is "gone" for a position we hold, that is a reasoned signal to exit -- fundamentally better than the mechanical edge decay tracker currently collecting data in `scoring/calibration.py`.

### Modules Touched

| File | Change |
|------|--------|
| `db/schema.py` | Add `reflections` table |
| `cli/brief.py` | Add reflection call after predictions, before trade signals |
| `scoring/calibration.py` | Incorporate reflection data into calibration reports |

### New Module

`prediction/reflection.py` -- takes yesterday's and today's predictions + market data, runs the reflection prompt, parses structured output, writes to `reflections` table.

---

## Improvement 3: News-to-Market Impact Tracking

### Problem

We don't know which news events actually move markets. A headline about Trump tweeting might cause a 5% price swing on ceasefire contracts, while detailed IAEA reports might cause zero movement. Without this data, models weight all evidence equally.

### Architecture

```
news_events table ──────────────────────────┐
  (with ingested_at timestamp)              │
                                            v
market_snapshots table ──────> Impact Calculator
  (price at time of ingestion,             │
   price at next run)                      v
                                    event_impacts table
                                    (event_id, contract, price_delta, lag)
                                            │
                                            v
                                    Aggregated weights
                                    (event_type X avg moves contract Y by Z%)
                                            │
                                            v
                                    Injected into prediction prompts
                                    as evidence weighting guidance
```

### Schema Additions

```sql
CREATE TABLE IF NOT EXISTS market_snapshots (
    snapshot_id     VARCHAR PRIMARY KEY,
    run_id          VARCHAR NOT NULL,
    contract_ticker VARCHAR NOT NULL,
    yes_price       DOUBLE,
    no_price        DOUBLE,
    snapshot_at     TIMESTAMP DEFAULT now()
);

CREATE TABLE IF NOT EXISTS event_impacts (
    impact_id       VARCHAR PRIMARY KEY,
    event_id        VARCHAR REFERENCES news_events(event_id),
    contract_ticker VARCHAR NOT NULL,
    price_before    DOUBLE,
    price_after     DOUBLE,
    price_delta     DOUBLE,
    hours_elapsed   DOUBLE,
    created_at      TIMESTAMP DEFAULT now()
);
```

### Impact Calculation

On each run:
1. Snapshot all tracked contract prices into `market_snapshots`
2. For each `news_event` ingested since last run, compute delta between the market snapshot closest before the event and the current snapshot
3. Write to `event_impacts`
4. Periodically aggregate: "headlines mentioning IRGC cause avg +3.2% on hormuz contracts"

### Feedback Into Models

After accumulating 2+ weeks of data, add a section to prediction prompts:

```
## Historical Evidence Weights (from observed market reactions)
- IRGC military activity: avg +3.2% on hormuz contracts, +1.1% on oil contracts
- Diplomatic backchannel reports: avg -2.8% on ceasefire contracts
- Trump social media posts: avg +/- 4.5% (high variance, directional)
- EIA inventory reports: avg +/- 0.8% on oil contracts (low signal)
```

### Limitations

- Correlation, not causation. Multiple events happen between runs.
- 2x/day cadence means 12-hour lag between snapshot and measurement.
- Small sample sizes early on. Need 20+ observations per category before weights are meaningful.
- This is guidance for the LLM, not a quantitative trading signal.

### Modules Touched

| File | Change |
|------|--------|
| `db/schema.py` | Add `market_snapshots` and `event_impacts` tables |
| `cli/brief.py` | Add snapshot step at start of run, impact calc at end |

### New Module

`scoring/impact.py` -- snapshots market prices, computes event-to-price deltas, aggregates impact statistics, formats evidence weight block for prompts.

---

## Implementation Sequence

All three improvements depend on `news_events` persistence (Improvement 1 is prerequisite).

```
Phase 1: Multi-Day News Context
  - news_events table + dedup logic
  - context_builder module
  - prompt integration in 3 predictors
  - Validate: do predictions change meaningfully with context?

Phase 2: Reflection Model Call
  - reflections table
  - reflection.py module
  - Wire into brief.py after prediction step
  - Validate: does edge_status correlate with actual P&L?

Phase 3: News-to-Market Impact Tracking
  - market_snapshots + event_impacts tables
  - impact.py module
  - Needs 2+ weeks of data before prompt integration
  - Validate: do computed weights match intuition? Do they improve calibration?
```

### Dependencies

- **Dashboard must be built first.** These improvements generate new data (reflections, impact scores, context clusters) that need visualization to validate.
- Improvement 2 depends on Improvement 1 (needs news events to compare against).
- Improvement 3 depends on Improvement 1 (needs `news_events` table with timestamps).
- Improvement 3's prompt integration depends on 2+ weeks of accumulated data.

### Budget Impact

| Component | Cost/Run | Cost/Day (2 runs) |
|-----------|----------|--------------------|
| Current (3 Sonnet calls) | ~$0.021 | ~$0.042 |
| Reflection (1 Sonnet call) | ~$0.007 | ~$0.014 |
| Context building (no LLM) | $0.000 | $0.000 |
| Impact calc (no LLM) | $0.000 | $0.000 |
| **Total after improvements** | **~$0.028** | **~$0.056** |
| **Budget cap** | | **$20.00** |

Massive headroom. Cost is not a constraint for any of these improvements.
