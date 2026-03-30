# Domain Pitfalls

**Domain:** Geopolitical crisis simulation with real-time intelligence, LLM agent swarm, and prediction evaluation
**Project:** Parallax
**Researched:** 2026-03-30

---

## Critical Pitfalls

Mistakes that cause rewrites, data loss, or fundamentally broken simulation output.

---

### Pitfall 1: Silent State Divergence Between In-Memory and Persisted World State

**What goes wrong:** The `WorldState` flushes deltas and immediately clears its dirty set (line 73 of `world_state.py`) without confirming the `DbWriter` actually persisted them. Meanwhile, `DbWriter` swallows all exceptions (line 45-46 of `writer.py`). The simulation continues running with in-memory state that has no durable backing. After a crash or restart, checkpoint/restore loads stale or incomplete state. The analyst sees predictions based on a world state that no longer matches what was recorded.

**Why it happens:** The flush-then-clear pattern is natural for in-memory caches. The danger is invisible until a restart occurs, because in-memory state looks correct while the process is alive. DuckDB write failures are rare enough that the bare `except Exception` never fires during development -- but under load (queue backpressure, disk full, concurrent connection issues), they will.

**Consequences:**
- Predictions scored against corrupted world state produce meaningless eval results
- Snapshot/restore puts the simulation into an impossible state (e.g., blockade active but flow unchanged)
- The analyst trusts outputs that diverged from recorded ground truth days ago
- Debugging requires replaying the full event journal, which may itself be incomplete

**Warning signs:**
- `DbWriter` queue depth grows monotonically during a run
- `get_world_state_at_tick()` returns different values than `WorldState.snapshot()` for the same tick
- After restart, agent decisions reference cells/states that don't exist in the database

**Prevention:**
1. Add write-acknowledgment: `flush_deltas()` returns a future/callback; dirty set clears only after DB confirmation
2. Replace bare `except Exception` in `DbWriter` with specific handlers; re-raise on critical failures
3. Add a periodic consistency check: reconstruct state from DB every N ticks, compare to in-memory state, halt if diverged
4. Implement a dead-letter queue for failed writes with retry and disk overflow

**Which phase should address it:** First integration phase. This is a prerequisite before wiring any live data through the pipeline. If the persistence layer is unreliable, every downstream component (eval, frontend, agent memory) builds on sand.

**Confidence:** HIGH -- this is directly visible in the current codebase (`writer.py:45-46`, `world_state.py:61-74`) and documented in CONCERNS.md.

---

### Pitfall 2: LLM Budget Exhaustion Halts the Entire Pipeline Mid-Day

**What goes wrong:** The $20/day budget cap is a hard constraint. With 50 agents, each making Haiku calls (~$0.003-0.01 per call), a single full sweep costs $0.15-$0.50. But during a crisis spike (e.g., IRGC seizure of a tanker), GDELT ingests dozens of high-relevance events in a short window. The event-to-agent router fans out each event to multiple agents. If a 4-hour crisis spike triggers 15 events routed to an average of 10 agents each, that is 150 LLM calls in a burst -- potentially $3-7 including any Sonnet escalations. A few such bursts and the daily budget is exhausted by noon, leaving the simulation blind for the rest of the day -- exactly when the crisis is still unfolding.

**Why it happens:** Budget tracking operates per-call but the cost driver is event volume, which is bursty and unpredictable. Auto-degrade (Sonnet to Haiku fallback) reduces per-call cost but not call volume. No mechanism exists to throttle call volume itself.

**Consequences:**
- Simulation goes dark during the most analytically valuable period
- Predictions become stale; eval scores reflect budget gaps, not model quality
- The analyst loses trust in the tool at exactly the moment it should be most useful

**Warning signs:**
- Budget consumption rate exceeds $2/hour during any window
- More than 20 agent calls dispatched within a single tick
- Budget tracker enters cooldown mode before 6pm

**Prevention:**
1. Implement event-level budget gating: before routing an event to N agents, estimate total cost and decide how many agents actually need to respond. Not every event needs all 50 agents.
2. Add priority tiers to the event-to-agent router: critical events (Goldstein > 7) get full agent sweep; routine events get top-5 relevant agents only
3. Implement hourly budget pacing: divide $20 into hourly buckets (e.g., $1/hour baseline, $3 reserve for spikes). Don't allow a single hour to consume more than 25% of daily budget.
4. Cache agent context aggressively: if an agent was just called 2 ticks ago with similar context, skip or use cached reasoning with a brief delta prompt

**Which phase should address it:** Must be solved during the pipeline wiring phase, specifically when connecting GDELT ingestion to the agent runner. The router is the control point.

**Confidence:** HIGH -- the budget constraint ($20/day) and agent count (50) are documented in PROJECT.md. The math on burst costs is straightforward.

---

### Pitfall 3: Cascade Feedback Loops Produce Unrealistic Runaway Scenarios

**What goes wrong:** The cascade engine applies rules sequentially and statefully: blockade reduces flow, flow loss triggers price shock, price shock triggers downstream effects, downstream effects inform agent decisions, agent decisions trigger new blockades or escalations. Without sufficient damping, the simulation spirals: a moderate blockade event produces a catastrophic price spike, which triggers extreme agent responses, which produce more escalation, which overrides the circuit breaker via "exogenous shock" loophole. Within a few ticks, oil is at the $300 ceiling and every agent is at maximum escalation.

**Why it happens:** The PRICE_ELASTICITY of 3.0 means a 10% supply loss produces a 30% price jump. If an agent responds by escalating (increasing blockade severity), the next tick compounds: 20% loss produces 60% price jump. The circuit breaker has a loophole: events with high Goldstein scores bypass all limits (line 45 of `circuit_breaker.py`). Agent-generated escalations that coincide with real high-Goldstein events get free passes. Additionally, the cascade engine has no rollback (CONCERNS.md: "applies rules statefully without rollback") -- partial failures leave the world in an inconsistent intermediate state.

**Consequences:**
- Simulation outputs are so extreme they are useless for analysis
- The analyst dismisses the tool as broken
- Predictions are systematically biased toward extreme outcomes, ruining eval scores
- No way to recover without manual intervention or restart

**Warning signs:**
- Oil price hits ceiling within 5 ticks of a blockade event
- More than 3 agents escalate in the same tick
- Circuit breaker override fires more than once per day

**Prevention:**
1. Add cumulative damping to cascade rules: each successive tick of escalation has diminishing marginal effect (e.g., multiply PRICE_ELASTICITY by 0.8 per consecutive escalation tick)
2. Separate the exogenous shock override from agent-initiated escalations: real-world events bypass the breaker, but the cascade effects they produce should still be subject to rate limiting
3. Implement cascade transaction boundaries: compute all rule outputs as deltas first, validate the total delta against reality bounds (circuit breaker's `reality_check`), then apply atomically or reject
4. Add a global escalation velocity metric: if total escalation across all agents exceeds a threshold per tick, force a cooldown regardless of individual agent state
5. Make PRICE_ELASTICITY and INSURANCE_THREAT_MULTIPLIER config-driven (currently hardcoded -- documented in CONCERNS.md) so they can be tuned without code changes

**Which phase should address it:** Must be addressed before the end-to-end pipeline goes live. The cascade engine and circuit breaker need hardening before agents are connected. Specifically: (a) cascade transaction boundaries in the simulation engine phase, (b) escalation velocity limits when wiring agents to cascade.

**Confidence:** HIGH -- visible in cascade.py (PRICE_ELASTICITY=3.0, no damping), circuit_breaker.py (exogenous override bypasses all limits), and CONCERNS.md (stateful mutation without rollback).

---

### Pitfall 4: GDELT Noise Overwhelms the Signal Pipeline

**What goes wrong:** GDELT ingests global events at 15-minute cadence. Even with the 4-stage noise filter and semantic dedup at 0.90 threshold, a major geopolitical event generates hundreds of articles across sources, each slightly different. The dedup catches exact/near duplicates, but GDELT also produces structurally distinct events about the same incident (e.g., "Iran seizes tanker" vs "UK condemns tanker seizure" vs "Oil prices surge after tanker seizure"). These pass dedup but represent the same underlying incident from different angles. Each gets routed to agents as a separate event, causing: (a) redundant LLM calls, (b) agents weighting the same incident multiple times in their reasoning, (c) budget burn on reprocessing.

**Why it happens:** Semantic dedup at 0.90 catches paraphrases but not perspective shifts. GDELT's Goldstein scale and actor codes differ across these articles, so structural dedup misses them too. The "same incident, different angle" problem is fundamental to news data and is not solved by pairwise similarity alone.

**Consequences:**
- Agent reasoning is biased toward whatever event generates the most articles (media attention bias, not geopolitical significance)
- Budget consumed on redundant calls
- The simulation overweights media-friendly events and underweights quietly significant developments

**Warning signs:**
- More than 10 curated events in a single 15-minute window referencing the same actors
- Agent decisions in consecutive ticks cite nearly identical reasoning
- Event relevance scores cluster tightly for a batch (all high or all medium)

**Prevention:**
1. Add incident-level clustering on top of semantic dedup: group curated events by (actor1, actor2, action_category, time_window) and emit one representative event per cluster with a `mention_count` field
2. Weight agent routing by incident, not by event: one incident = one agent activation cycle, regardless of how many GDELT articles describe it
3. Add a "novelty score" to curated events: how different is this from the last 6 hours of events? Low-novelty events get batched for a periodic summary rather than routed individually
4. Tune the semantic dedup threshold down to 0.85 for same-actor pairs (events about the same actors within the same hour are likely about the same incident even at lower similarity)

**Which phase should address it:** During the GDELT-to-agent-router integration. The clustering layer should sit between ingestion and routing. This is not a GDELT problem or an agent problem -- it is a pipeline design problem at the integration boundary.

**Confidence:** MEDIUM -- the 4-stage filter and 0.90 dedup threshold are documented as existing, but the actual false-negative rate on incident-level dedup is unknown without testing against real GDELT data during a crisis spike. The architectural problem (pairwise dedup is insufficient for incident clustering) is well-understood in NLP/IR literature.

---

### Pitfall 5: WebSocket Frontend Drowns in High-Frequency State Updates

**What goes wrong:** The simulation ticks every 15 minutes in LIVE mode, but each tick can produce dozens of world state deltas, agent decisions, cascade effects, and indicator updates. The frontend receives all of these via WebSocket as JSON batches. During a crisis cascade, a single tick might produce: 50 cell updates + 15 agent decisions + 6 cascade rule outputs + indicator changes = 70+ messages. The frontend attempts to re-render the deck.gl map and update all panels for each batch. The browser freezes, the WebSocket buffer grows, the auto-reconnect fires spuriously, and the user sees a frozen map followed by a jarring state jump.

**Why it happens:** The backend pushes state changes as they happen (event-driven), but the frontend is render-bound. deck.gl H3 hex map re-renders are expensive for large cell sets. The WebSocket hook has auto-reconnect but no backpressure or throttling.

**Consequences:**
- The dashboard becomes unusable during the most interesting moments
- The analyst misses the cascade as it unfolds because the UI is frozen
- Auto-reconnect can cause duplicate message processing or state gaps

**Warning signs:**
- Frontend frame rate drops below 10fps during simulation ticks
- WebSocket message queue grows beyond 100 pending messages
- Browser dev tools show "long task" warnings during deck.gl renders

**Prevention:**
1. Server-side throttling: batch all updates within a tick into a single WebSocket message per tick, not per-update. Send a consolidated "tick summary" frame.
2. Client-side rendering budget: use `requestAnimationFrame` gating so deck.gl re-renders at most once per frame, accumulating deltas between frames
3. Differential updates: send only changed cells, not full state. The frontend maintains local state and applies deltas.
4. Priority channels: separate WebSocket channels (or message types) for map updates vs. agent activity vs. indicators. The frontend can process high-priority updates (indicators, alerts) immediately and batch map updates.
5. Add explicit backpressure: if the client hasn't acknowledged the last N messages, the server buffers instead of flooding

**Which phase should address it:** During the WebSocket server and frontend wiring phase. The message protocol design must happen before the first real-time data flows to the frontend. Retrofitting throttling into an already-built push pipeline is significantly harder.

**Confidence:** HIGH -- deck.gl rendering costs are well-documented, and the project has 50 agents + multi-resolution H3 grid + cascade rules all producing output simultaneously. The WebSocket hook exists but has no throttling (documented in PROJECT.md).

---

### Pitfall 6: Prediction Eval Loop Scores Against Stale or Missing Ground Truth

**What goes wrong:** The eval framework scores predictions against "ground truth" -- but for geopolitical predictions, ground truth is ambiguous, delayed, and often contested. A prediction like "Iran will increase naval patrols in the Strait within 48 hours" requires: (a) a clear definition of what constitutes "increase," (b) a reliable source confirming it happened or didn't, (c) timely availability of that source. GDELT provides event data, but GDELT reports media coverage, not ground truth. EIA provides oil prices (clear ground truth for price predictions) but with 1-week lag on some data series. For military/political predictions, there may be no programmatic ground truth source at all.

**Why it happens:** The prediction schema has `ground_truth JSON` and `resolve_by TIMESTAMP` fields, but no mechanism to populate them automatically. The "daily cron scoring predictions against reality" requirement assumes ground truth is fetchable, but for most geopolitical predictions it requires manual analyst input or inference from downstream indicators.

**Consequences:**
- Predictions sit unscored indefinitely, making the eval loop meaningless
- Automated scoring produces false positives/negatives based on incomplete ground truth
- Agent prompt refinement based on bad scores makes agents worse, not better
- The analyst loses trust in the eval system and stops using it

**Warning signs:**
- More than 50% of predictions past their `resolve_by` date have NULL `ground_truth`
- Automated scores cluster at 0.0 or 1.0 (binary, no nuance) instead of continuous calibration scores
- Agent prompt refinement produces agents that game the scoring rubric rather than making better predictions

**Prevention:**
1. Categorize predictions by ground-truth availability at creation time:
   - **Auto-scorable**: oil price direction/magnitude (EIA data), shipping traffic changes (AIS data if available)
   - **Semi-auto**: event occurrence (GDELT can confirm media reports of an event, even if not ground truth)
   - **Manual-only**: military posture changes, diplomatic shifts, intent predictions
2. Only auto-score the auto-scorable category. Surface manual-only predictions in the analyst dashboard for human scoring.
3. For the eval-to-prompt-refinement loop, use only high-confidence scored predictions (auto-scored with clear ground truth). Do not feed ambiguous scores into prompt tuning.
4. Add a "ground truth confidence" field alongside `ground_truth` in the predictions table. Scores weighted by ground truth confidence prevent low-quality scores from polluting the feedback loop.
5. Start with oil price predictions only for the automated eval loop -- this is the one domain where ground truth is unambiguous and timely.

**Which phase should address it:** Eval framework phase. The prediction categorization and ground truth sourcing strategy must be designed before the scoring cron is implemented. Starting with oil-price-only eval is the pragmatic first step.

**Confidence:** MEDIUM -- the schema and requirements are documented, but the actual ground truth availability for this specific crisis scenario hasn't been tested. The general problem of geopolitical prediction evaluation is well-known in forecasting literature (see: Good Judgment Project, Metaculus scoring challenges).

---

## Moderate Pitfalls

Mistakes that cause delays, degraded output quality, or significant rework.

---

### Pitfall 7: Parallel Feature Branches Create Integration Nightmare

**What goes wrong:** PROJECT.md documents "10 feature branches (feat/01 through feat/10) with substantial code, but branches are parallel (not merged together)" with status "Revisit." Each branch developed a subsystem in isolation (ingestion, agents, budget, simulation, frontend, etc.). When wiring them together, interface mismatches emerge: the agent runner expects events in format X, but GDELT ingestion produces format Y. The DbWriter expects to be the sole writer, but two branches both create their own connections. Schema assumptions diverge across branches.

**Why it happens:** Parallel development without integration contracts. Each branch likely tested against its own mocks/stubs that don't match the real interface of the other subsystem.

**Prevention:**
1. Before merging any branch, define integration contracts: shared Pydantic models for events, decisions, predictions, and world state updates that all subsystems import from a common module
2. Merge in dependency order: DB schema first, then simulation engine, then ingestion, then agents, then eval, then API, then frontend wiring
3. Write integration tests at each merge boundary: "GDELT event -> curated_events table -> agent router -> agent decision -> cascade -> world state delta" as an end-to-end test with real (not mocked) subsystem instances
4. Expect and budget time for interface adaptation: each merge will likely require 1-2 days of glue code and contract alignment

**Which phase should address it:** The very first integration phase. This is THE critical path item. Nothing else works until the branches are reconciled.

**Confidence:** HIGH -- the parallel branch situation is documented in PROJECT.md and the git log confirms separate feature branches.

---

### Pitfall 8: DuckDB Single-Writer Bottleneck Under Real-Time Load

**What goes wrong:** The `DbWriter` processes writes serially via a single asyncio.Queue. In LIVE mode, a single tick can produce: world state deltas (dozens of cells), agent decisions (up to 50), curated events (variable), predictions (variable). If write latency is 5-10ms per statement and a tick generates 100 writes, the queue needs 500ms-1s to drain -- but the next tick may arrive in 900s (15 min) so this seems fine. The real problem is burst writes during cascade: all 6 cascade rules fire, each updating multiple cells, plus agent decisions, all enqueued within milliseconds. If any write blocks (DuckDB WAL sync, disk I/O spike), the queue backs up and subsequent ticks' writes pile on.

**Why it happens:** DuckDB is single-process by design. The single-writer pattern is correct for DuckDB, but the individual-statement-per-write pattern is not. CONCERNS.md already identifies this: "If write latency is 10ms and simulation generates 1000 deltas/tick, queue backs up."

**Prevention:**
1. Batch writes: collect all deltas/decisions/events for a tick into a single INSERT statement with multiple value rows. DuckDB handles batch inserts far more efficiently than individual ones.
2. Use DuckDB's `executemany()` or prepared statements for repeated insert patterns
3. Add queue depth monitoring with alerts: if queue depth > 50, log a warning; if > 200, trigger write batching automatically
4. Add bounded queue with backpressure: if queue exceeds threshold, simulation pauses until writes catch up (better to slow the simulation than lose data)

**Which phase should address it:** During the pipeline wiring phase, as part of hardening the DbWriter before connecting real subsystems to it.

**Confidence:** HIGH -- directly visible in writer.py architecture and documented in CONCERNS.md.

---

### Pitfall 9: Agent Memory Context Window Overflow

**What goes wrong:** Each agent has a `rolling_context` (JSON in `agent_memory` table) that accumulates events, decisions, and world state summaries over time. In a multi-day simulation, agents that are frequently activated (e.g., IRGC, CENTCOM) accumulate large context windows. When the agent runner constructs the LLM prompt, it includes: system prompt + historical baseline + rolling context + current event + world state summary. For a highly-active agent after 3 days, this can exceed the model's context window or, more practically, exceed the budget tracker's `max_input_tokens` limit (configured per agent tier in ScenarioConfig).

**Why it happens:** Rolling context grows monotonically without summarization or eviction. The "rolling" in the name implies a window, but without explicit truncation logic, it just accumulates.

**Prevention:**
1. Implement a context window budget: before each LLM call, calculate total token count of the assembled prompt. If it exceeds 80% of max_input_tokens, summarize the oldest rolling context entries into a compressed summary.
2. Use a sliding window: keep only the last N events/decisions in full detail; everything older gets summarized into a paragraph.
3. Prioritize by relevance: keep full context for events related to the agent's domain; summarize peripheral events aggressively.
4. Implement periodic context compaction: every N ticks, run a cheap (Haiku) summarization pass on each agent's context to compress it.

**Which phase should address it:** During the agent-to-pipeline integration, before agents start receiving continuous real events. Must be solved before the system runs for more than 24 hours.

**Confidence:** MEDIUM -- the schema shows `rolling_context JSON` in `agent_memory` but the actual agent runner code is on a separate branch and wasn't inspectable. The pattern is a well-known problem in LLM agent architectures.

---

### Pitfall 10: Clock Drift Between GDELT Ingestion and Simulation Ticks

**What goes wrong:** GDELT updates every 15 minutes. The simulation engine ticks every 15 minutes (default `tick_duration_seconds: 900`). These two clocks are independent: GDELT fetches are triggered by cron/timer, simulation ticks by the DES engine's wall-clock anchor. If GDELT fetch takes 30 seconds (BigQuery + dedup + insert) and the simulation tick fires at the same wall-clock moment, the current tick's events may include last-fetch's data (stale) or next-fetch's data (not yet available). Over hours, drift accumulates: events arrive "late" relative to the tick they should influence.

**Why it happens:** Two independent time sources (GDELT API timestamps, simulation engine monotonic clock) with no synchronization protocol.

**Prevention:**
1. Event timestamping at source: GDELT events carry their own timestamps. Route events to the correct tick based on event timestamp, not fetch timestamp.
2. Tick-gated ingestion: the simulation engine signals "tick N starting" and the ingestion pipeline delivers all events with timestamps in [tick_N_start, tick_N_end). Events arriving after the window are queued for the next tick.
3. Add a "data readiness" gate: a tick doesn't process until its ingestion window is confirmed complete (all GDELT data for that window has been fetched and deduplicated).
4. Log and monitor event-to-tick latency: how many seconds/ticks late are events being processed relative to their source timestamp?

**Which phase should address it:** During the GDELT-to-simulation wiring phase. The tick/ingestion synchronization protocol must be designed before connecting the pipeline end-to-end.

**Confidence:** HIGH -- the two independent timing systems (engine.py's monotonic clock, GDELT's 15-min cadence) are visible in the codebase. No synchronization mechanism exists.

---

### Pitfall 11: Anthropic API Rate Limits and Transient Failures Break Agent Sweep

**What goes wrong:** The agent runner makes parallel LLM calls to Anthropic's API. With 50 agents and burst routing, the system can attempt 10-30 concurrent API calls. Anthropic's rate limits (requests per minute, tokens per minute) can throttle or reject calls. A single 429 (rate limit) or 529 (overloaded) response during an agent sweep means some agents don't produce decisions for that tick. The simulation proceeds with partial agent output, creating an asymmetric state where some actors responded and others didn't.

**Why it happens:** Parallel LLM calls are necessary for throughput, but API rate limits are shared across the account. Prompt caching helps with token throughput but not request count limits.

**Prevention:**
1. Implement retry with exponential backoff for 429/529 responses, with a per-tick deadline (if retries exceed tick duration, skip gracefully)
2. Add a semaphore to limit concurrent API calls to a safe number (e.g., 10 concurrent requests, configurable)
3. For partial agent sweeps, log which agents were skipped and include a "confidence reduction" flag on the tick's outputs
4. Consider request batching: if Anthropic's batch API is available, submit all agent calls as a batch and poll for results
5. Add circuit breaker at the API level: if error rate exceeds 30% in a window, pause agent calls for 60 seconds rather than burning budget on failing requests

**Which phase should address it:** During agent runner integration, before the first live pipeline run.

**Confidence:** MEDIUM -- Anthropic rate limits depend on the account tier, which is unknown. The parallel call pattern is documented in PROJECT.md. The failure modes (partial sweep, asymmetric state) are architectural consequences.

---

## Minor Pitfalls

Mistakes that cause annoyance, debugging time, or incremental tech debt.

---

### Pitfall 12: Nondeterministic Cascade Rule Ordering

**What goes wrong:** CONCERNS.md documents: "What happens if two cascade rules modify the same cell in the same tick? Who wins? Is the order deterministic?" The cascade engine's 6 rules are called in a fixed code order, but if the handler processes multiple events in the same tick (FIFO within tick via sequence counter), each event independently triggers cascade rules. The second event's cascade sees the first event's mutations, making output order-dependent.

**Prevention:** Process all events for a tick, collect all cascade deltas without applying them, resolve conflicts (e.g., last-write-wins or max-severity-wins), then apply atomically. This is the "cascade transaction boundary" mentioned in Pitfall 3.

**Which phase should address it:** Simulation engine hardening, before agents are connected.

**Confidence:** HIGH -- documented in CONCERNS.md test coverage gaps.

---

### Pitfall 13: Frontend State Desync After WebSocket Reconnect

**What goes wrong:** The WebSocket hook has auto-reconnect, but after reconnection, the frontend has stale state. If it missed 3 ticks of updates during the disconnect, the map shows old influence colors and indicators show old values. Without a "catch-up" mechanism, the frontend is silently wrong until the next full state push.

**Prevention:** On WebSocket reconnect, the client sends its last-known tick number. The server responds with a full state snapshot or delta bundle from that tick to current. Don't rely on the live update stream to eventually correct stale state.

**Which phase should address it:** WebSocket server and frontend wiring phase.

**Confidence:** HIGH -- auto-reconnect without state sync is a well-known WebSocket anti-pattern, and the current hook is documented as having auto-reconnect without this capability.

---

### Pitfall 14: Scenario Config Not Versioned with Simulation Runs

**What goes wrong:** The ScenarioConfig is loaded from a YAML file at startup. If the analyst tweaks parameters between runs (adjusting price elasticity, cooldown ticks, etc.), there is no record of which config was used for which simulation run. Eval results from different config versions are compared as if equivalent.

**Prevention:** Hash the loaded config and store it in `simulation_state` at run start. Include config hash in eval_results for filtering. Reject comparisons across config versions in the eval dashboard.

**Which phase should address it:** Eval framework phase.

**Confidence:** HIGH -- visible in config.py (no versioning) and schema.py (simulation_state table exists but no config tracking).

---

### Pitfall 15: Docker Volume State Persists Across Schema Migrations

**What goes wrong:** The DuckDB volume (`duckdb-data`) persists across container rebuilds. If a schema migration adds columns or changes table structures, the old `.duckdb` file doesn't update. `CREATE TABLE IF NOT EXISTS` silently succeeds even if the existing table has a different schema. New code writes columns that don't exist, or reads columns that were renamed.

**Prevention:** Add a schema version table. On startup, check version and run migrations sequentially. For development, add a `--reset-db` flag that drops and recreates all tables. Document that `docker volume rm duckdb-data` is needed after breaking schema changes.

**Which phase should address it:** First integration phase, before the schema is modified during branch merges.

**Confidence:** HIGH -- `CREATE TABLE IF NOT EXISTS` pattern visible in schema.py, Docker volume persistence visible in docker-compose.yml.

---

## Phase-Specific Warnings

| Phase Topic | Likely Pitfall | Mitigation |
|-------------|---------------|------------|
| Branch merging / integration | Interface mismatches across 10 parallel branches (#7) | Define shared contracts first; merge in dependency order |
| GDELT-to-agent pipeline | Noise overwhelming signal (#4), clock drift (#10) | Incident clustering, tick-gated ingestion |
| Agent runner integration | Budget exhaustion (#2), API rate limits (#11), context overflow (#9) | Event-level budget gating, priority routing, context windowing |
| Cascade engine hardening | Feedback loops (#3), nondeterministic ordering (#12) | Damping, cascade transactions, velocity limits |
| World state persistence | Silent divergence (#1), DuckDB bottleneck (#8) | Write acknowledgment, batch writes, consistency checks |
| WebSocket / frontend | Update flooding (#5), reconnect desync (#13) | Tick-batched messages, catch-up on reconnect |
| Eval framework | Stale/missing ground truth (#6), unversioned configs (#14) | Categorize by scoreability, start with oil prices only |
| Docker / deployment | Volume state across migrations (#15) | Schema versioning, migration runner |

---

## Integration-Specific Meta-Pitfall: Testing Individual Modules Is Not Testing the Pipeline

**What goes wrong:** Each subsystem has its own tests (51 tests documented). But the integration boundary -- where GDELT events flow into agents which produce decisions which trigger cascades which update world state which pushes to frontend -- has zero test coverage. Each module works in isolation but fails at the seams. The most common integration bugs are: (a) data format mismatches, (b) timing assumptions (async vs sync, tick boundaries), (c) error propagation (one module's exception is another's silent failure), (d) resource contention (multiple modules competing for the single DbWriter queue).

**Prevention:** Before declaring integration complete, write at least one end-to-end test that:
1. Ingests a synthetic GDELT event
2. Routes it to at least one agent
3. Processes the agent decision through cascade
4. Verifies world state updated correctly in both memory and DB
5. Verifies a WebSocket message was emitted with the correct delta
6. Verifies the prediction was logged for later eval

This single test will catch more integration bugs than 50 unit tests.

**Which phase should address it:** Every integration phase should include at least one end-to-end test covering its boundary.

---

## Sources

- `/Users/adit/Personal Projects/Parallax-Geopolitcal-Swarm/.planning/PROJECT.md` -- project requirements, constraints, key decisions
- `/Users/adit/Personal Projects/Parallax-Geopolitcal-Swarm/.planning/codebase/CONCERNS.md` -- documented tech debt, bugs, performance bottlenecks, fragile areas
- `/Users/adit/Personal Projects/Parallax-Geopolitcal-Swarm/backend/src/parallax/db/writer.py` -- DbWriter implementation
- `/Users/adit/Personal Projects/Parallax-Geopolitcal-Swarm/backend/src/parallax/db/schema.py` -- DuckDB schema
- `/Users/adit/Personal Projects/Parallax-Geopolitcal-Swarm/backend/src/parallax/simulation/engine.py` -- DES engine
- `/Users/adit/Personal Projects/Parallax-Geopolitcal-Swarm/backend/src/parallax/simulation/cascade.py` -- cascade rules
- `/Users/adit/Personal Projects/Parallax-Geopolitcal-Swarm/backend/src/parallax/simulation/circuit_breaker.py` -- escalation control
- `/Users/adit/Personal Projects/Parallax-Geopolitcal-Swarm/backend/src/parallax/simulation/world_state.py` -- world state manager
- `/Users/adit/Personal Projects/Parallax-Geopolitcal-Swarm/backend/src/parallax/simulation/config.py` -- scenario config
- `/Users/adit/Personal Projects/Parallax-Geopolitcal-Swarm/docker-compose.yml` -- Docker setup
- General domain knowledge: DES simulation patterns, LLM agent architectures, WebSocket real-time systems, GDELT data characteristics, geopolitical forecasting evaluation (Good Judgment Project, Metaculus)

**Note:** WebSearch was unavailable during this research session. Pitfalls are derived from direct codebase analysis, documented concerns, and domain knowledge from training data. Confidence levels reflect this -- findings grounded in visible code are HIGH; findings about runtime behavior of components on unmerged branches are MEDIUM.

---

*Concerns audit: 2026-03-30*
