# Technology Stack

**Project:** Parallax v1.4 -- Model Intelligence + Resolution Validation
**Researched:** 2026-04-12
**Focus:** RSS diversification, Twitter/X journalist monitoring, oil-specific feeds, file-based context, rolling JSON context, Kalshi contract enumeration, model registry pattern
**Overall Confidence:** HIGH (verified against official docs, PyPI, Kalshi API docs)

## Existing Stack (Locked In -- DO NOT CHANGE)

| Technology | Version | Purpose |
|------------|---------|---------|
| Python | 3.12 | Backend runtime |
| FastAPI | 0.115+ | REST API server |
| DuckDB | 1.2+ | Embedded OLAP database |
| Anthropic SDK | 0.52+ | Claude API for predictions |
| Pydantic | 2.10+ | Data validation |
| httpx | 0.28+ | Async HTTP client |
| cryptography | 44.0+ | Kalshi RSA-PSS auth |
| truthbrush | 0.2+ | Truth Social ingestion |
| React/Vite/TS | 18.3/6.0/5.6 | Frontend dashboard |

## Recommended Stack Additions

### 1. RSS Feed Parsing: feedparser

| Technology | Version | Purpose | Why |
|------------|---------|---------|-----|
| feedparser | >=6.0.11 | Universal RSS/Atom parser | Battle-tested (15+ years), handles malformed XML, auto-detects feed format. Replaces manual `xml.etree.ElementTree` parsing in `google_news.py`. |

**Confidence:** HIGH (verified on PyPI -- v6.0.12 released Sep 2025, production-stable)

**Rationale:** The existing `google_news.py` hand-rolls RSS parsing with `xml.etree.ElementTree`. This works for Google News (clean XML) but will break on edge-case feeds from Reuters/AP RSS generators. feedparser handles encoding issues, malformed dates, namespace variations, and CDF/Atom feeds that raw ET cannot.

**Integration point:** New `ingestion/rss_feeds.py` module. Same `NewsEvent` dataclass output as `google_news.py`. Plugs into `_fetch_gdelt_events()` in `brief.py` alongside existing sources.

**What NOT to do:** Do not replace the Google News RSS parser with feedparser. Google News feeds are clean and the existing ET parser is fast. Use feedparser only for new third-party feeds where XML quality is unknown.

### 2. Twitter/X Journalist Monitoring: httpx (existing) + manual API calls

| Technology | Version | Purpose | Why |
|------------|---------|---------|-----|
| (no new dependency) | -- | X API v2 via httpx | httpx already handles async HTTP. X API v2 is a simple REST API with bearer token auth. Adding tweepy or xdk for 2-3 endpoints is unnecessary bloat. |

**Confidence:** HIGH (X API v2 docs verified, httpx already in stack)

**Rationale -- why NOT tweepy or xdk:**

- **tweepy** (community library, mature): Adds a large dependency for what amounts to `GET /2/users/:id/tweets` with a bearer token. The project already uses httpx for every external API call. Adding tweepy introduces a second HTTP client with its own connection pooling, retry logic, and rate limiting that conflicts with httpx patterns.

- **xdk** (official X SDK, launched early 2026): Too young. Documentation is thin. Auto-generated code means poor error messages. The project's API usage is read-only and simple enough that raw httpx calls with a thin wrapper suffice.

**X API pricing reality (as of Feb 2026):**
- Free tier is dead. Pay-per-use is the only option for new developers.
- Cost: $0.005 per post read. No search endpoint on pay-per-use.
- For monitoring ~10 journalist accounts, 2x/day, reading last 20 tweets each: ~400 reads/day = $2/day = $60/month.
- **This is viable under the $20/day budget** (LLM calls are ~$0.02/run, leaving $19.98/day headroom).
- However: no search endpoint means you MUST use user timeline lookups, not keyword search.

**Implementation approach:** Create `ingestion/x_journalists.py` that:
1. Accepts a list of X user IDs (not handles -- API v2 requires IDs)
2. Calls `GET /2/users/:id/tweets` with bearer token auth via httpx
3. Filters for Iran/oil keywords (same pattern as `truth_social.py`)
4. Returns `NewsEvent` objects

**Env var needed:** `X_BEARER_TOKEN` (from X Developer Portal pay-per-use account)

### 3. Oil-Specific Data Feeds: EIA API v2 (existing) + no new deps

| Technology | Version | Purpose | Why |
|------------|---------|---------|-----|
| (no new dependency) | -- | EIA API v2 weekly petroleum data | Already using EIA for daily spot prices. Weekly inventory data uses the same API, different endpoint path. |

**Confidence:** HIGH (EIA API v2 structure verified)

**Rationale -- what to add vs what to skip:**

**ADD: EIA Weekly Petroleum Status Report** (free, same API key)
- Endpoint: `https://api.eia.gov/v2/petroleum/sum/sndw/data/` (weekly supply/demand)
- Facets: `process=SAX` (crude oil stocks), `process=SABS` (total petroleum), etc.
- Provides: crude inventory changes, imports, refinery utilization
- Oil traders treat the Wednesday 10:30 AM EST release as a major event. This data directly feeds oil price predictions.
- Integration: Extend existing `ingestion/oil_prices.py` with `fetch_weekly_inventory()` function.

**SKIP: Platts/Argus** (enterprise pricing, inaccessible)
- S&P Global Platts: Enterprise-only. Minimum ~$10K/year. Rate limit 5000 queries/day but requires accreditation. Not viable for a $20/day budget project.
- Argus Media: Same tier. Enterprise API access only.
- OilPriceAPI.com: Free tier is 1000 requests/month. Provides real-time Brent/WTI. Could supplement EIA for intraday prices but EIA daily spot is sufficient for twice-daily cron.

**SKIP: Additional oil price APIs** -- EIA daily spot (already integrated) + EIA weekly inventory (same API) covers the need. The models run twice daily, not intraday. Real-time Brent prices from a third-party API add cost and complexity for minimal signal improvement.

### 4. File-Based Context Management: stdlib pathlib + json (no new deps)

| Technology | Version | Purpose | Why |
|------------|---------|---------|-----|
| (no new dependency) | -- | Load crisis context from .md/.json files instead of Python strings | stdlib `pathlib.Path.read_text()` and `json` module are sufficient. No template engine needed. |

**Confidence:** HIGH (pure Python, no external dependencies)

**Rationale:** The current `crisis_context.py` stores a 3KB+ string literal as `CRISIS_TIMELINE`. This works but has problems:
1. Updating context requires editing Python code (syntax errors possible)
2. Cannot be updated by non-developers or automated processes
3. No separation between the context data and the code that loads it

**Implementation approach:**
- Move `CRISIS_TIMELINE` content to `backend/data/context/crisis_timeline.md` (Markdown file)
- Move pre-crisis gap context to `backend/data/context/pre_crisis_aug25_feb26.md`
- `crisis_context.py` becomes a loader: `Path("data/context/crisis_timeline.md").read_text()`
- Context files are version-controlled like code but editable as plain text

**What NOT to do:**
- Do not use Jinja2 or any template engine. Context files are plain text injected verbatim into prompts. Template syntax adds complexity and attack surface for prompt injection.
- Do not store context in DuckDB. These are static reference documents, not queryable data. Filesystem is simpler and version-controllable.

### 5. Rolling JSON Context: stdlib json + DuckDB (no new deps)

| Technology | Version | Purpose | Why |
|------------|---------|---------|-----|
| (no new dependency) | -- | Append-per-run structured context, read-last-N-days window | DuckDB already stores run data. JSON serialization is stdlib. No need for a separate time-series store. |

**Confidence:** HIGH (pure Python + existing DuckDB)

**Rationale:** Each cron run should append a structured summary (predictions, key news, market state) that subsequent runs can read for multi-day context. Two viable approaches:

**Option A: JSON files on disk** (simpler, recommended for v1.4)
- Write `backend/data/context/rolling/{date}.json` per run
- Read last N files by sorting filenames
- Pros: Human-readable, git-trackable, trivial to inspect/edit
- Cons: No query capability, manual cleanup of old files

**Option B: DuckDB table** (more queryable, recommended for v2.0)
- New `rolling_context` table with `run_id`, `run_date`, `context_json` columns
- Query: `SELECT context_json FROM rolling_context WHERE run_date >= ? ORDER BY run_date DESC LIMIT ?`
- Pros: SQL queries, atomic writes, no file system management
- Cons: Harder to manually inspect, tied to DB lifecycle

**Recommendation:** Use Option A (JSON files) for v1.4. The rolling context is model input, not analytical data. Files are easier to debug and manually correct during the validation window (April 7-21). Migrate to DuckDB table in v2.0 when the system is proven.

**Schema for rolling context JSON:**
```json
{
  "run_id": "uuid",
  "run_date": "2026-04-12",
  "run_time": "08:00:00Z",
  "predictions": {
    "oil_price": {"probability": 0.72, "direction": "increase"},
    "ceasefire": {"probability": 0.62, "direction": "stable"},
    "hormuz": {"probability": 0.35, "direction": "increase"}
  },
  "key_news": ["headline 1", "headline 2"],
  "market_snapshot": {
    "KXWTIMAX-26DEC31": {"yes_price": 0.42},
    "KXUSAIRANAGREEMENT-27": {"yes_price": 0.48}
  },
  "self_correction": {
    "previous_oil_prob": 0.68,
    "actual_market_move": "+2.3%",
    "calibration_note": "Overestimated by 4%"
  }
}
```

### 6. Kalshi Contract Enumeration: httpx (existing) + Kalshi API v2 (already integrated)

| Technology | Version | Purpose | Why |
|------------|---------|---------|-----|
| (no new dependency) | -- | Enumerate all child contracts from event tickers via Kalshi API v2 | `KalshiClient` already calls `/markets` with `event_ticker` param. Contract enumeration is a new method on the existing client, not a new dependency. |

**Confidence:** HIGH (verified against Kalshi API docs at docs.kalshi.com)

**Key API endpoints for contract discovery:**

1. **`GET /events/{event_ticker}?with_nested_markets=true`** -- returns event metadata + all child market objects in a single call. This is the primary endpoint for discovery.

2. **`GET /events?series_ticker={series}&with_nested_markets=true`** -- list all events in a series with their markets. Useful for finding new event tickers.

3. **`GET /markets?event_ticker={ticker}&status=open&limit=200`** -- already used in `brief.py` `_fetch_kalshi_markets()`. Extend with `status=settled` to find resolved contracts for backtesting.

4. **Pagination:** Cursor-based. Response includes `cursor` field. Pass as query param for next page. Empty cursor = no more results. Limit: 1-200 for events, 1-1000 for markets.

**Implementation approach:** Add methods to existing `KalshiClient`:
- `discover_contracts(event_ticker) -> list[dict]` -- calls GET /events with nested markets
- `get_settled_contracts(event_ticker) -> list[dict]` -- calls GET /markets with status=settled
- `get_event_details(event_ticker) -> dict` -- calls GET /events/{ticker}

**Important caveat from Kalshi docs:** "Historical markets settled before the historical cutoff will not be included." This means very old settled contracts may not be available. Test with known Iran event tickers to confirm availability.

### 7. Model Registry Pattern: No external library needed

| Technology | Version | Purpose | Why |
|------------|---------|---------|-----|
| (no new dependency) | -- | Registry pattern with decorator-based self-registration | Pure Python pattern using a dict registry + `@register` decorator. No framework needed. |

**Confidence:** HIGH (well-established Python pattern, no dependencies)

**Rationale:** The current `brief.py` hardcodes 3 model instantiations:
```python
oil_pred = OilPricePredictor(cascade, budget, anthropic_client)
ceasefire_pred = CeasefirePredictor(budget, anthropic_client)
hormuz_pred = HormuzReopeningPredictor(cascade, budget, anthropic_client)
```

Adding a 4th model (Iran political transition) requires editing `brief.py`. The registry pattern makes models self-registering:

```python
# prediction/registry.py
MODEL_REGISTRY: dict[str, type] = {}

def register_model(model_id: str):
    def decorator(cls):
        MODEL_REGISTRY[model_id] = cls
        return cls
    return decorator

def get_registered_models() -> dict[str, type]:
    return dict(MODEL_REGISTRY)

# prediction/oil_price.py
@register_model("oil_price")
class OilPricePredictor:
    ...

# brief.py (simplified)
for model_id, model_cls in get_registered_models().items():
    predictions.append(await model_cls(...).predict(...))
```

**What NOT to add:**
- Do not add `registries` PyPI package (0.0.3, last updated 2023). It is overengineered for this use case. A 15-line registry module in stdlib Python is sufficient.
- Do not use `importlib.import_module()` for dynamic loading. Models are known at development time. Explicit imports with decorator registration gives the same flexibility without the debugging nightmare of dynamic imports.
- Do not use ABC/abstract base class enforcement. The models already share a common `predict()` interface by convention. Adding ABC adds boilerplate without catching real bugs.

## Dependencies to REMOVE from pyproject.toml

These are dead dependencies from earlier phases that should be cleaned up:

| Package | Why Remove |
|---------|------------|
| `h3>=4.1` | Spatial visualization deleted April 8. No code imports h3. |
| `sentence-transformers>=3.4` | Semantic dedup deleted April 8. No code imports it. |
| `searoute>=1.3` | Sea route calculations deleted. No code imports it. |
| `shapely>=2.0` | Geometric operations deleted. No code imports it. |
| `google-cloud-bigquery>=3.27` | BigQuery GDELT pipeline deleted. No code imports it. |
| `websockets>=14.0` | WebSocket support not used (CLI-first tool). No code imports it. |

**Impact:** These 6 packages (plus their transitive dependencies, especially `torch` from sentence-transformers) add ~2GB to the install. Removing them dramatically speeds up `pip install` and Docker builds.

## Summary: What to Add

| New Dependency | Version | Purpose | Cost |
|---------------|---------|---------|------|
| feedparser | >=6.0.11 | RSS parsing for Reuters/AP feeds | ~50KB, zero transitive deps |

**Total new dependencies: 1**

Everything else uses existing stack (httpx, DuckDB, stdlib json/pathlib) or pure Python patterns (registry, file-based context).

## Installation

```bash
# Add to pyproject.toml dependencies:
# "feedparser>=6.0.11",

# Full install (after cleanup):
pip install -e ".[dev]"
```

## Environment Variables

| Variable | Required | Purpose |
|----------|----------|---------|
| `X_BEARER_TOKEN` | For Twitter/X monitoring | X API v2 bearer token (pay-per-use account) |
| `EIA_API_KEY` | Already exists | Same key works for weekly petroleum data |
| All existing vars | Already configured | No changes needed |

**Cost impact of X API:** ~$2/day for monitoring 10 journalist accounts 2x/day. Well within $20/day budget (LLM calls use ~$0.02/run).

## New File Structure

```
backend/
  data/
    context/
      crisis_timeline.md          # Moved from Python string
      pre_crisis_aug25_feb26.md   # New: fills Claude's knowledge gap
      rolling/
        2026-04-12_08.json        # Per-run rolling context
        2026-04-12_20.json
  src/parallax/
    ingestion/
      rss_feeds.py                # NEW: Reuters/AP RSS via feedparser
      x_journalists.py            # NEW: X API v2 journalist monitoring
      oil_prices.py               # EXTENDED: weekly inventory function
    prediction/
      registry.py                 # NEW: model registry pattern
      crisis_context.py           # MODIFIED: loads from files
      iran_political.py           # NEW: political transition model
    markets/
      kalshi.py                   # EXTENDED: contract discovery methods
```

## Alternatives Considered

| Category | Recommended | Alternative | Why Not |
|----------|-------------|-------------|---------|
| RSS parsing | feedparser | raw xml.etree | ET breaks on malformed XML from third-party feeds |
| X API client | httpx (existing) | tweepy 4.x | Unnecessary dependency; httpx already in stack |
| X API client | httpx (existing) | xdk (official) | Too new (early 2026), thin docs, auto-generated code |
| Oil data | EIA API v2 (existing) | Platts API | Enterprise pricing ($10K+/yr), inaccessible |
| Oil data | EIA API v2 (existing) | OilPriceAPI.com | Free tier (1K req/mo) sufficient but EIA already covers the need |
| Context storage | Markdown files | Jinja2 templates | Prompt injection risk, unnecessary complexity |
| Context storage | JSON files on disk | DuckDB table | Files are easier to debug during validation window |
| Model registry | stdlib dict + decorator | `registries` PyPI | Abandoned package (2023), 15 lines of stdlib code suffices |
| Model registry | explicit imports | importlib dynamic | Dynamic imports are a debugging nightmare for 4-5 models |

## Sources

- [feedparser on PyPI](https://pypi.org/project/feedparser/) -- v6.0.12 (Sep 2025), production-stable
- [Kalshi Get Event API](https://docs.kalshi.com/api-reference/events/get-event) -- with_nested_markets param verified
- [Kalshi Get Markets API](https://docs.kalshi.com/api-reference/market/get-markets) -- pagination and filtering verified
- [Kalshi Get Events API](https://docs.kalshi.com/api-reference/events/get-events) -- series_ticker filter verified
- [X API Pay-Per-Use Pricing](https://devcommunity.x.com/t/announcing-the-launch-of-x-api-pay-per-use-pricing/256476) -- $0.005/read, no free tier
- [X Python XDK](https://docs.x.com/xdks/python/overview) -- official SDK, launched early 2026
- [EIA Open Data Portal](https://www.eia.gov/opendata/) -- API v2 documentation
- [EIA Weekly Petroleum Status Report](https://www.eia.gov/petroleum/supply/weekly/) -- Wednesday release schedule confirmed
- [Reuters RSS feeds status](https://www.fivefilters.org/2021/reuters-rss-feeds/) -- officially discontinued June 2020
- [AP News RSS feeds](https://rss.feedspot.com/associated_press_rss_feeds/) -- 40+ active feeds confirmed
