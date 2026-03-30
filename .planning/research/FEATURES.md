# Feature Landscape

**Domain:** Geopolitical crisis simulation and live intelligence platform (single-analyst tool)
**Researched:** 2026-03-30
**Focus:** Features needed to go from working subsystems to end-to-end live intelligence tool

## Context

Parallax already has: simulation engine, cascade rules, GDELT ingestion, agent swarm (50 agents), budget tracker, frontend shell with H3 map, and DuckDB persistence. These exist on parallel feature branches, not yet integrated. The question is: what features turn these subsystems into a working intelligence tool that produces evaluated predictions against the live Iran-Hormuz crisis?

Reference platforms considered: Good Judgment Project, Metaculus, IARPA ACE/SAGE programs, Recorded Future, Stratfor, Palantir Gotham, Polymarket (for scoring mechanics), Premise Data.

---

## Table Stakes

Features the analyst expects. Missing any of these means the tool does not function as an intelligence product.

| Feature | Why Expected | Complexity | Notes |
|---------|--------------|------------|-------|
| **End-to-end data pipeline** | GDELT events must flow through agents to cascade to world state to frontend without manual steps | High | This is integration work -- all subsystems exist but are not wired together. The main orchestration loop (ingest -> route -> agent decide -> cascade -> persist -> push) does not exist yet. |
| **FastAPI REST endpoints** | Frontend needs to fetch current world state, agent decisions, predictions, indicators on page load | Medium | Schema and queries exist. Need CRUD endpoints for world state, decisions, predictions, events, agent status. Standard REST wrapping of existing `queries.py`. |
| **WebSocket live push** | The tool is "live" -- analyst expects real-time updates without refreshing. Agent decisions, new events, indicator changes must push to frontend. | Medium | Frontend has WebSocket hook already. Backend needs to emit events when state changes. Pattern: simulation engine emits to a broadcast channel, WebSocket handler fans out. |
| **Prediction logging with structured schema** | Predictions must be structured (direction, magnitude, timeframe, confidence) not free-text, or they cannot be scored | Medium | Schema exists in `predictions` table. Need: agent output parsing into this schema, validation, dedup of near-identical predictions. Pydantic output schemas for agents already exist on agent branch. |
| **Ground truth fetching** | Predictions are worthless without resolution. Need automated fetching of actual outcomes (oil prices from EIA, event occurrence from GDELT, shipping data) | Medium | EIA fetcher exists. Need: a resolver that matches prediction types to ground truth sources, runs on schedule, populates `ground_truth` column in predictions table. |
| **Prediction scoring (Brier score)** | Core value prop is "predictions that beat human intuition, continuously evaluated." Without scoring, there is no evaluation. | Medium | Use Brier score for probabilistic predictions (standard in forecasting: GJP, Metaculus, IARPA all use it). Direction accuracy is binary. Magnitude accuracy needs a continuous error metric. Schema has `score_direction`, `score_magnitude`, `miss_tag` columns ready. |
| **Daily eval cron** | Scoring must happen automatically. Analyst should not have to trigger evaluation manually. | Low | Scheduled task (asyncio periodic or APScheduler) that: finds predictions past `resolve_by`, fetches ground truth, scores, writes to `eval_results`. |
| **Frontend wired to real data** | Dashboard panels currently show placeholders. Agent activity, live indicators, and map must show actual simulation state. | High | Multiple panels need data binding: agent activity feed, oil price indicator, threat level indicator, H3 map colors from world state. Each panel is a separate integration task. |
| **Agent prompt versioning** | When prompts are refined based on eval, need to track which version produced which predictions. Already in schema (`prompt_version` on decisions and predictions). | Low | Schema supports this. Need: version incrementing logic, storage of prompt text per version in `agent_prompts` table, association on every agent call. |

---

## Differentiators

Features that make Parallax more valuable than reading news + making mental predictions. Not expected in MVP but each one meaningfully increases tool value.

| Feature | Value Proposition | Complexity | Notes |
|---------|-------------------|------------|-------|
| **Automated prompt improvement loop** | Agents whose predictions score poorly get their prompts refined automatically. This is the "continuously improved" part of the value prop. No other tool does this. | High | Pipeline: eval scores per agent -> identify worst performers -> generate prompt patches (meta-LLM call) -> A/B test new prompt vs old -> promote winner. Must respect $20/day budget. This is the hardest and most novel feature. |
| **Per-agent accuracy leaderboard** | Shows which agents (IRGC analyst, CENTCOM analyst, MBS/Aramco) are most accurate. Reveals which actors the system models well vs poorly. | Low | Aggregate query over `eval_results` grouped by `agent_id`. Frontend component to display. Low effort, high insight. |
| **Calibration curve visualization** | When agents say "70% confidence," are they right 70% of the time? Calibration plots are standard in forecasting evaluation (GJP, Metaculus). | Medium | Bucket predictions by stated confidence, compute actual hit rate per bucket, plot. Requires enough predictions to be statistically meaningful (50+ per bucket). |
| **Cascade trace visualization** | Show the chain: "IRGC seized tanker -> flow reduced 30% -> price spiked $8 -> Saudi activated pipeline -> price settled at +$5." This is the unique simulation value. | Medium | Cascade engine returns effect dictionaries. Need to persist the full chain, then render as a timeline/flow diagram in frontend. |
| **Prediction timeline / track record** | Scrollable history of predictions with outcomes. "On March 15, IRGC agent predicted oil above $95 by March 20 at 80% confidence -- CORRECT." | Low | Query `predictions` table with scores, render chronologically. Standard but very useful for analyst trust-building. |
| **Counterfactual simulation** | "What if Iran blockades tomorrow?" -- run simulation forward from current state with injected event, compare to baseline. | High | Engine supports REPLAY mode. Need: snapshot current state, fork, inject event, run N ticks, diff outcomes. UI for event injection and comparison view. Defer to post-MVP. |
| **Confidence-weighted aggregation** | Combine predictions from multiple agents into a single probability estimate, weighted by past accuracy. Ensemble forecast. | Medium | Standard technique: inverse Brier-score weighting or log-scoring. Produces a "Parallax consensus" prediction that should outperform any single agent. |
| **Anomaly detection on incoming events** | Flag when GDELT event patterns deviate significantly from baseline (sudden spike in Iran-related military events). Alerting the analyst to "something unusual is happening." | Medium | Sliding window over curated_events, compute z-score on event frequency/Goldstein scale by actor pair. Alert when threshold exceeded. |
| **Scenario comparison dashboard** | Side-by-side view of "current trajectory" vs "escalation scenario" vs "de-escalation scenario." | High | Requires multiple parallel simulation runs, state diffing, comparative visualization. Powerful but complex. Defer. |
| **Source attribution on predictions** | Each prediction links back to the specific GDELT events that triggered the agent's reasoning. Analyst can verify the chain. | Low | Agent runner already receives events. Need to store event IDs alongside decision/prediction records, render in UI. |

---

## Anti-Features

Features to explicitly NOT build. Common mistakes in intelligence/prediction platforms.

| Anti-Feature | Why Avoid | What to Do Instead |
|--------------|-----------|-------------------|
| **Multi-user / auth system** | PROJECT.md explicitly scopes this as single-analyst tool. Auth adds complexity with zero value for v1. | Single-user, localhost only. Docker Compose already handles this. |
| **Free-text prediction entry** | Unstructured predictions cannot be scored automatically. Every prediction platform that started with free-text had to retrofit structure later. | Force structured output from agents: direction (up/down/stable), magnitude range, timeframe, confidence float. Schema already enforces this. |
| **Real-time LLM streaming to frontend** | Tempting to show agent "thinking" in real-time. But at 50 agents, this creates noise, burns budget on display tokens, and distracts from signal. | Batch agent decisions, push completed decisions only. Show "N agents processing..." loading state, then results. |
| **Manual prediction scoring** | Analyst manually marking predictions as correct/incorrect does not scale and introduces bias. | Automated ground truth resolution from data sources (EIA, GDELT). Manual override only for edge cases. |
| **Overly granular agent personas** | Tempting to model 200+ sub-actors. But each agent costs LLM tokens, and marginal agents (e.g., "Oman Foreign Ministry spokesperson") add noise without signal. | 50 agents across 12 countries is already aggressive. Focus on making existing agents better via eval, not adding more agents. |
| **Historical backfill / backtesting UI** | Backend supports REPLAY mode, but building a full backtesting UI is a rabbit hole. The crisis is happening NOW. | Keep REPLAY mode as a developer/debugging tool. Ship forward-looking features first. |
| **Complex notification system** | Push notifications, email alerts, SMS -- overengineered for a single-analyst local tool. | Simple in-app alert banner for anomalies and high-confidence predictions. No external notification channels. |
| **Multi-scenario support** | Other conflicts (Ukraine, Taiwan) are out of scope for v1. Building generic scenario support prematurely abstracts the Hormuz-specific cascade rules. | Hard-code Hormuz scenario. Refactor to multi-scenario only if v1 succeeds and there is demand. |
| **Explanation generation via separate LLM calls** | Do not make a separate LLM call to "explain" what happened. This doubles cost. | Agents already provide `reasoning` in their structured output. Use that directly. |

---

## Feature Dependencies

```
Ground Truth Fetching ─────────────┐
                                   v
Prediction Logging ──────> Prediction Scoring ──────> Eval Results
                                   │                       │
                                   v                       v
                           Daily Eval Cron          Per-Agent Leaderboard
                                                           │
                                                           v
                                                    Prompt Improvement Loop
                                                           │
                                                           v
                                                    Agent Prompt Versioning

End-to-End Pipeline ──────> WebSocket Live Push ──────> Frontend Wired to Real Data
       │                                                       │
       v                                                       v
FastAPI REST Endpoints                              Cascade Trace Visualization
                                                    Prediction Timeline
                                                    Calibration Curve

Prediction Scoring + Agent Leaderboard ──────> Confidence-Weighted Aggregation
```

**Critical path:** End-to-end pipeline must come first. Nothing else works without the orchestration loop running. Then prediction logging + scoring, because the core value prop is evaluated predictions. Then prompt improvement, because that is the flywheel.

**Parallel tracks possible:**
- API + WebSocket (backend) can develop in parallel with frontend data binding
- Scoring + ground truth (eval track) can develop in parallel with pipeline integration
- Leaderboard + calibration (visualization) can develop after scoring exists

---

## MVP Recommendation

For MVP (the tool is usable by the analyst to gain insight on the live crisis):

**Phase 1 -- Pipeline Integration (must be first):**
1. End-to-end data pipeline (orchestration loop)
2. FastAPI REST endpoints
3. WebSocket live push

**Phase 2 -- Eval Foundation:**
4. Prediction logging with structured schema (parsing agent output)
5. Ground truth fetching (EIA prices, GDELT event verification)
6. Prediction scoring (Brier score + direction/magnitude)
7. Daily eval cron

**Phase 3 -- Frontend + Visibility:**
8. Frontend panels wired to real data
9. Per-agent accuracy leaderboard
10. Prediction timeline / track record
11. Source attribution on predictions

**Phase 4 -- Intelligence Flywheel:**
12. Automated prompt improvement loop
13. Confidence-weighted aggregation
14. Calibration curve visualization
15. Cascade trace visualization

**Defer to post-MVP:**
- Counterfactual simulation
- Scenario comparison dashboard
- Anomaly detection (nice-to-have, not core)

**Rationale:** The ordering follows the data flow. You cannot score predictions that do not exist. You cannot improve prompts without scores. You cannot show data in the frontend without an API. Each phase unlocks the next.

---

## Complexity Budget

Given the $20/day LLM budget and single-developer context:

| Feature Category | Estimated Effort | LLM Cost Impact |
|-----------------|-----------------|-----------------|
| Pipeline integration | 2-3 days | None (wiring work) |
| API + WebSocket | 1-2 days | None |
| Prediction scoring | 2-3 days | None (computation only) |
| Ground truth fetching | 1-2 days | None (API calls to EIA/GDELT) |
| Frontend data binding | 3-4 days | None |
| Prompt improvement loop | 3-5 days | +$2-5/day for meta-LLM calls (must fit in $20 cap) |
| Calibration + leaderboard | 1-2 days | None |
| Cascade trace viz | 2-3 days | None |

**Total MVP estimate:** 15-24 days of focused development.

**Budget note:** The prompt improvement loop is the only new feature that consumes LLM budget. Meta-prompting calls (analyzing agent performance, generating prompt patches) should use Haiku to stay within the $20/day cap. Allocate ~$3/day for meta-prompting, leaving $17/day for the 50 agent swarm.

---

## Scoring System Design Notes

This section provides detail on the scoring approach since it is central to the platform's value.

**Brier Score** (standard for probabilistic forecasting):
- Formula: BS = (forecast_probability - outcome)^2
- Range: 0 (perfect) to 1 (worst)
- Used by: GJP, Metaculus, IARPA ACE program
- Apply to: binary predictions (will X happen by date Y?)

**Direction Accuracy** (for directional predictions):
- Did the agent correctly predict up/down/stable?
- Simple binary scoring per prediction
- Apply to: oil price direction, escalation/de-escalation, flow changes

**Magnitude Accuracy** (for quantitative predictions):
- Agent predicts range [low, high]. Ground truth falls in range = full credit.
- Outside range: score decays with distance (normalized by range width)
- Apply to: oil price level, flow reduction percentage

**Calibration Score:**
- Group predictions by stated confidence bucket (50-60%, 60-70%, etc.)
- Compare average stated confidence to actual hit rate
- Perfect calibration: 70% confidence predictions are correct 70% of the time
- Requires 30+ predictions per bucket to be meaningful -- will take weeks to accumulate

**Miss Tags** (for learning from errors):
- When a prediction is wrong, categorize the miss: `timing` (right direction, wrong timeframe), `magnitude` (right direction, wrong scale), `direction` (completely wrong), `black_swan` (unpredictable exogenous event)
- Feed miss tags into prompt improvement: "Agent X consistently has timing misses -- adjust temporal reasoning in prompt"

---

## Sources

- Domain knowledge of forecasting evaluation: Good Judgment Project methodology (Tetlock, "Superforecasting"), IARPA ACE/SAGE program design, Metaculus scoring rules
- Brier score is the standard metric in probabilistic forecasting literature (Brier 1950, widely adopted)
- Calibration curves are standard in weather forecasting and have been adapted by GJP and Metaculus
- Existing Parallax codebase: `schema.py` (prediction and eval_results tables), `queries.py`, `config.py`
- PROJECT.md active requirements list

**Confidence:** MEDIUM -- Feature categorization is based on established forecasting platform patterns and the specific project requirements. Scoring methodology (Brier score, calibration) is HIGH confidence as these are well-established standards. Effort estimates are MEDIUM confidence (single-developer, integration complexity is hard to estimate precisely). The prompt improvement loop is LOW confidence for effort -- this is novel and the hardest feature to get right.
