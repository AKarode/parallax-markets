# Session Log: Dashboard Redesign Design — 2026-04-09

## Summary

Designed a complete React trading dashboard to replace both the Streamlit dashboard (metrics dump) and the simulation-focused React frontend (hex maps). Produced two design specs: dashboard redesign (in scope) and model intelligence improvements (next phase). No code written — pure design session.

## What Was Accomplished

| Output | Path | Status |
|--------|------|--------|
| Dashboard design spec | `docs/superpowers/specs/2026-04-09-dashboard-redesign-design.md` | Complete, committed |
| Model intelligence spec | `docs/superpowers/specs/2026-04-09-model-intelligence-design.md` | In progress |
| Visual mockups | `.superpowers/brainstorm/` | HTML mockups for all sections |
| Memory: model improvements | `memory/project_model_improvements.md` | Saved for next phase |

## Key Design Decisions

### 1. No Map
Tanker/AIS data is a lagging indicator — by the time ships reroute, the news is priced in. No real shipping data in the codebase. Map is cosmetic without it. Skip entirely.

### 2. Weighted Ensemble Signal Aggregation
When multiple models disagree on a contract, combine using hit-rate-based weights (not "strongest edge wins" or "majority vote"). Self-correcting — bad models auto-downweight as data accumulates. Used by Polymarket/agents and quant funds.

### 3. Simulated Portfolio ($1,000 Fake Capital)
Instead of just tracking signal-level P&L, run a full portfolio simulation: $1,000 starting capital, Quarter-Kelly sizing, hold-to-settlement. Shows equity curve, drawdown, Sharpe. Computed from existing signal_ledger + market_prices data — no new API calls.

### 4. Exit Analysis as Counterfactual Only
No sell engine. Track "would auto-sell have been profitable?" using edge decay data already collected. When enough data shows exits beat hold-to-settlement, the dashboard flags it. Then build the sell engine.

### 5. Sharp Terminal Aesthetic
Zero border-radius, 1px borders, 8-10px padding, dark background (#09090b). Inter for headers, JetBrains Mono for data. Every metric gets a label, target, and sample size.

## Architecture Designed

```
Sticky KPI Bar: Portfolio value | Hit rate | Signals | Last run | Budget
Model Cards (3): Oil Price | Ceasefire | Hormuz — with sparklines, hit rates, trends
Markets Table: Click-to-expand contract rows with full detail
  Expanded: Resolution criteria, order book, price chart, edge math, reasoning, signal history, exit analysis
Model Health | Portfolio Panel (side by side)
Ops Footer (single line)
```

- React + Vite + TypeScript, custom CSS (no framework)
- 7 new API endpoints on FastAPI backend
- New `portfolio/simulator.py` module for server-side portfolio computation
- Auto-poll every 5 minutes via `setInterval`

## Current State

- **Design complete**: Two specs written, mockups reviewed
- **No code written**: This was a design-only session
- **Existing code unchanged**: Streamlit dashboard and simulation frontend untouched
- **Data state**: 13 signals across 3 models, 3 pipeline runs, 4 contracts tracked, 0 trade executions

## Next Steps

### Immediate (Next Session)
1. Write implementation plan from dashboard design spec
2. Build backend first: 7 new API endpoints + portfolio simulator
3. Build frontend: React dashboard consuming those endpoints
4. Validate with real data from pipeline runs

### Next Phase (After Dashboard Ships)
Model intelligence improvements — documented in separate spec:
1. **Multi-day news context** — rolling 3-5 day news window with trajectory awareness
2. **Reflection model call** — compare yesterday vs today predictions, self-correct
3. **News-to-market impact tracking** — which headlines actually move prices

## Commits

- `2952dbd` — docs: add dashboard redesign design spec
