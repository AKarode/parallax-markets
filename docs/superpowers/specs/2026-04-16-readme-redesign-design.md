# README Redesign Spec

## Goal

Rewrite README.md to be outward-facing for recruiters and hiring engineers at Bay Area tech companies. Primary framing: systems thinker who builds real things and validates them before shipping.

## Target Audience

Mixed: non-technical recruiters scan for 30 seconds, engineers dig into architecture. Structure goes from plain English to progressively technical.

## Framing Decisions

- Lead with the general system ("prediction market edge detection"), mention geopolitics as the application domain rather than the headline
- Be transparent about paper trading. "Validate before risking capital" reads as disciplined, not incomplete
- Show architectural decisions and why they were made (ensemble, cascade, proxy mapping)
- For Anduril/Palantir specifically, lean into geopolitical angle via resume/cover letter, not the README itself

## Structure

### 1. Opening (recruiter-readable)

Headline: "Prediction market edge detection for geopolitical events"

Two paragraphs: what it does in plain English, then the systems hook (cascade reasoning over physical supply chain effects).

### 2. How It Works (diagram)

Three-column pipeline: data sources, models + cascade engine, signals + paper trading. No specific tickers or parameters.

### 3. What Makes It Interesting (5 bullets)

Each bullet is a design decision + why it matters:

1. Ensemble predictions (3 calls, trimmed mean, instability detection)
2. Cascade reasoning (6-rule physical supply chain simulation)
3. Proxy-aware contract mapping (explicit classification, edge discounting)
4. Crisis context injection (fills Claude's knowledge gap)
5. Paper trading with real execution semantics (bid/ask, slippage, full lifecycle)

### 4. Architecture

Module tree showing package structure. Clean, scannable.

### 5. Tech Stack

Table: Python/FastAPI/DuckDB, Claude Opus 4, React/TypeScript/Vite/deck.gl, data sources, testing.

### 6. Roadmap

Two milestones with one-line bullets. No internal phase numbers or dates.
- v1.4 (in progress): prompt fixes, ensemble, risk gates, context foundation, contract discovery, resolution validation
- v1.5 (planned): Bayesian evidence aggregation, multi-provider ensemble, cascade engine upgrade
- Future: live trading, additional thesis domains, real-time dashboard

### 7. Quick Start

Setup commands + run commands. Short.

## Omitted (internal ops, not recruiter-facing)

- Storage model / table details
- Data environment docs
- Cron deployment instructions
- API endpoint table
- Detailed testing breakdown

## Excluded for sensitivity

- Specific tickers or contract families
- Cascade parameters
- Budget or position sizing details
- Prompt content
- Calibration data

## Tone

Professional mode. Sounds like a real engineer, not a marketing page. Direct, specific, no fluff. Confident without being dramatic.
