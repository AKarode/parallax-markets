<!-- GSD:project-start source:PROJECT.md -->
## Project

**Parallax**

A prediction market edge-finder for the Iran-Hormuz crisis. Ingests real-world news (Google News RSS, GDELT DOC API, EIA oil prices), runs 3 focused AI prediction models (oil price, ceasefire, Hormuz reopening) with cascade reasoning, compares predictions against Kalshi/Polymarket market prices, and flags divergences as trade signals. Validated via paper trading on Kalshi sandbox.

**Core Value:** Find mispriced prediction market contracts on Iran war outcomes by reasoning about second-order cascade effects faster and deeper than headline-scraping bots.

### How It Works

```
News (Google RSS + GDELT) → 3 Prediction Models (Claude Sonnet) → Probabilities
Kalshi/Polymarket APIs    → Market Prices                        → Probabilities
                                                                        ↓
                                                          Divergence Detector
                                                    BUY_YES / BUY_NO / HOLD signals
                                                                        ↓
                                                          Paper Trading (Kalshi sandbox)
```

### Running

```bash
# Dry run (mock data, no API calls)
cd backend && python -m parallax.cli.brief --dry-run

# Live predictions + real market prices, no trades
python -m parallax.cli.brief --no-trade

# Full pipeline with paper trade execution
python -m parallax.cli.brief

# Daily scorecard (computes 15+ metrics, writes to daily_scorecard table)
python -m parallax.cli.brief --scorecard --date 2026-04-09

# FastAPI server
uvicorn parallax.main:app --reload

# Dashboard (React SPA, proxies /api to backend)
cd frontend && npm run dev  # port 3000
```

### Constraints

- **Budget**: $20/day cap on LLM calls — 3 Sonnet calls ~$0.02/run, massive headroom
- **Tech stack**: Python/FastAPI backend, DuckDB, React/Vite/TypeScript dashboard.
- **Data sources**: Google News RSS (free, 5-15min), GDELT DOC API (free, 15-60min), EIA API v2, Kalshi API, Polymarket API
- **Deployment**: Docker Compose locally — no cloud infra for v1
- **Timeline**: 2-week ceasefire window (April 7-21 2026) is the validation deadline
- **Trading**: Paper trading only via Kalshi sandbox. No real money until edge is proven.

### Environment Variables

```bash
ANTHROPIC_API_KEY        # Required — Claude API for prediction models
KALSHI_API_KEY           # Required — Kalshi API key ID
KALSHI_PRIVATE_KEY_PATH  # Required — Path to RSA private key PEM file (~/.kalshi/private_key.pem)
EIA_API_KEY              # Optional — EIA oil price data
```

### Kalshi API Notes

- **Two endpoints**: Production (`api.elections.kalshi.com`) for reading real market prices, Demo (`demo-api.kalshi.co`) for paper trading
- Demo sandbox does NOT have geopolitical markets — only sports/crypto
- Auth: RSA-PSS signature on every request (timestamp + method + path)
- v2 API uses `_dollars` suffix fields (e.g., `yes_bid_dollars`, `volume_fp`)
- Market discovery: use `event_ticker` parameter, not unfiltered `/markets`
<!-- GSD:project-end -->

<!-- GSD:stack-start source:codebase/STACK.md -->
## Technology Stack

## Languages
- Python 3.12 - Backend API, simulation engine, spatial computing
- TypeScript/JavaScript - Frontend visualization (under development)
- YAML - Scenario configuration
- SQL - DuckDB schema and queries
## Runtime
- Python 3.12+ (backend)
- Node.js 22+ (frontend, for build only)
- pip + setuptools/hatchling (Python)
- npm (JavaScript/TypeScript)
## Frameworks
- FastAPI 0.115+ - REST/WebSocket API server
- Uvicorn 0.34+ - ASGI application server
- React 18.3.1 - UI framework
- Vite 6.0.0 - Build tool and dev server
- TypeScript 5.6.2 - Type safety for frontend
- deck.gl 9.1.0 - High-performance visualization (core, geo-layers, layers, react)
- MapLibre GL 4.7.0 - Map rendering (open-source Mapbox alternative)
- react-map-gl 7.1.8 - React wrapper for map rendering
- H3 (h3-js) - Hexagonal hierarchical geospatial indexing (frontend for viz)
- pytest 8.3 - Python test runner
- pytest-asyncio 0.25 - Async test support
- pytest-httpx 0.35 - HTTP mocking
- Vite 6.0.0 - JavaScript bundler and dev server
- @vitejs/plugin-react 4.3.4 - React JSX support in Vite
- Babel 7.29.0 - JavaScript transpilation (indirect dependency)
- Rollup 4+ - Module bundler (indirect dependency)
## Key Dependencies
- duckdb 1.2+ - Embedded OLAP database for world state and deltas
- h3 4.1+ - Hexagonal geospatial indexing for ocean/chokepoint zones
- searoute 1.3+ - Sea route optimization and distance calculations
- shapely 2.0+ - Geometric operations for spatial analysis
- anthropic 0.52+ - Claude API client for agent reasoning
- sentence-transformers 3.4+ - Embedding models for semantic analysis
- pydantic 2.10+ - Data validation and serialization
- websockets 14.0+ - WebSocket support for real-time simulation updates
- httpx 0.28+ - Async HTTP client for external API calls
- pyyaml 6.0+ - YAML scenario configuration parsing
- google-cloud-bigquery 3.27+ - BigQuery integration for historical data
## Configuration
- `ANTHROPIC_API_KEY` - Claude API authentication (required for agents)
- `GOOGLE_APPLICATION_CREDENTIALS` - GCP service account JSON path (optional, for BigQuery)
- `EIA_API_KEY` - Energy Information Administration API key (optional)
- `DUCKDB_PATH` - File path for DuckDB database (default: `/app/data/parallax.duckdb`)
- `PARALLAX_ADMIN_PASSWORD` - Admin authentication password (default: `admin`)
- `PARALLAX_INVITE_SEED` - Seed for invitation token generation (default: `dev-seed`)
- Scenario config: `backend/config/scenario_hormuz.yaml`
- Vite config: `frontend/vite.config.ts` (proxy /api to localhost:8000)
- TypeScript config: `frontend/tsconfig.json`
## Platform Requirements
- Docker + Docker Compose (for containerized dev environment)
- Python 3.12 runtime with build tools (gcc, make)
- Node.js 22+ for frontend builds
- curl (for health checks in Docker)
- Docker containers (backend: Python 3.12-slim, frontend: nginx:alpine)
- DuckDB file storage (persistent volume: `duckdb-data`)
- Anthropic API access (Claude 3.x models)
- Optional: Google Cloud BigQuery for data warehousing
## Package Management
- Installation: `pip install -e ".[dev]"` (editable install with dev dependencies)
- Testing: `pytest tests/`
- DuckDB extensions preloaded in Docker build step
- Installation: `npm ci` (clean install from lock file)
- Build: `npm run build` (Vite production build to `/dist`)
- Artifacts served by nginx in production
## Infrastructure Stack
- Docker Compose orchestrates 2 services:
- Backend exposes port 8000 internally
- Frontend proxy layer (nginx) on port 3000 (public)
- WebSocket upgrade support in nginx (for real-time simulation)
- API proxying: `/api/*` routes to backend
- WebSocket proxying: `/ws` routes to backend with connection upgrade headers
- Named volume: `duckdb-data` (mounted at `/app/data` in backend)
- DuckDB file path configurable via env var
<!-- GSD:stack-end -->

<!-- GSD:conventions-start source:CONVENTIONS.md -->
## Conventions

## Naming Patterns
- Lowercase with underscores: `engine.py`, `circuit_breaker.py`, `h3_utils.py`
- Test files follow pattern: `test_<module>.py`
- Module names match concept names (e.g., `cascade.py` for cascade logic)
- Snake case: `apply_blockade()`, `compute_price_shock()`, `lat_lng_to_cell_for_zone()`
- Descriptive verb-first pattern: `get_`, `compute_`, `apply_`, `activate_`, `allow_`, `record_`
- Private methods prefixed with `_`: `_handler`, `_queue`, `_cells`
- Snake case for all variables: `cell_id`, `supply_loss`, `threat_level`, `bypass_flow`
- Descriptive names preferred over abbreviations: `shock_threshold` not `sthresh`
- Collection suffixes indicate plurals: `dependencies`, `deltas`, `cells`, `coords`
- PascalCase for classes: `SimulationEngine`, `CascadeEngine`, `WorldState`, `CircuitBreaker`
- PascalCase for enums: `ClockMode`, `ResolutionBand`
- Frozen dataclasses used for immutable value types: `@dataclass(frozen=True)`
- SCREAMING_SNAKE_CASE for module-level constants: `PRICE_ELASTICITY`, `RESOLUTION_BANDS`
## Code Style
- No explicit formatter configured (no `.prettierrc`, `.black`, `pyproject.toml [tool.black]`)
- Style is clean and consistent: 4-space indentation, PEP 8 compliant
- Line length appears to follow standard conventions (~100-120 chars)
- No explicit linter configuration detected
- Code follows Python idioms: type hints, docstrings, clean imports
- Type hints present throughout: `def schedule(self, event: SimEvent) -> int:`
- Module-level docstrings at file head: `"""Discrete Event Simulation (DES) engine."""`
- Function docstrings with Args/Returns when helpful (especially for public APIs)
- Example: `cascade.py` includes detailed docstrings explaining the cascade chain
- Concise docstrings for obvious methods; detailed for complex logic
## Import Organization
- Absolute imports from package root: `from parallax.simulation.config import...`
- No relative imports (no `from ..config import`)
- Imports are explicit, not wildcard: `from dataclasses import dataclass, field`
## Error Handling
- Defensive checks return default values rather than raising: `if cell is None: return None`
- Example: `apply_blockade()` returns `{"supply_loss": 0.0}` for nonexistent cells
- Async errors logged via logger: `logger.exception("DB write failed: %s", op.sql[:100])`
- No try-except at function boundary unless needed for recovery
- Standard `logging` module: `logger = logging.getLogger(__name__)`
- Log exceptions at ERROR level: `logger.exception()` for failures
- Partial info in logs (SQL[:100]) to avoid logging huge payloads
## Comments
- Block comments explain design decisions (e.g., "Lazy deletion: cancelled events are marked...")
- Inline comments rare; code is self-documenting via naming
- Comments appear in docstrings at module and class level, not scattered
- Python uses docstrings, not JSDoc
- Multi-line docstrings follow format: description, then blank line, then Args/Returns/Raises
- Example from `cascade.py`:
## Function Design
- Functions are focused and single-purpose
- Most functions under 30 lines; longest about 50 lines
- Complex logic broken into named steps (e.g., `compute_downstream_effects` has clear phases)
- Named parameters preferred over positional: `CascadeEngine(config=config_obj)`
- Optional parameters use defaults: `tick_duration_seconds: float = 900.0`
- Type hints on all parameters: `def __init__(self, conn: duckdb.DuckDBPyConnection)`
- Single return type (no union of different structures)
- Dicts used for structured returns with consistent keys: `{"supply_loss": 0.0}`
- Falsy returns for "not found": `None` for missing cell, `False` for queue empty
## Module Design
- All public classes/functions defined at module level
- Private utilities prefixed with `_` (Python convention)
- No `__all__` declarations; rely on naming convention
- `__init__.py` files empty or minimal
- Import from specific modules: `from parallax.simulation.engine import SimulationEngine`
## Domain-Specific Patterns
- Frozen dataclasses for immutable configs: `@dataclass(frozen=True) class ScenarioConfig`
- Mutable dataclasses for state: `@dataclass class CellState`
- Field factories for defaults: `payload: dict[str, Any] = field(default_factory=dict)`
- All DB operations and simulation engine use async/await
- Handlers are async callbacks: `async def handler(event: SimEvent): ...`
- Queue operations: `await self._queue.put()` and `await self._queue.get()`
- Union types use `|` syntax (Python 3.10+): `str | None` not `Optional[str]`
- Dict keys/values typed: `dict[str, float]`, `dict[int, CellState]`
- Full signature typing: `Callable[[SimEvent], Awaitable[None]]`
<!-- GSD:conventions-end -->

<!-- GSD:architecture-start source:ARCHITECTURE.md -->
## Architecture

### Module Map (backend/src/parallax/)

| Module | Purpose | Key Classes/Functions |
|--------|---------|---------------------|
| `cli/brief.py` | **Main entry point** — daily brief + scorecard CLI | `run_brief()`, `_run_scorecard()`, `--scorecard --date` |
| `main.py` | FastAPI REST API (14 endpoints) | `/api/health`, `/api/predictions`, `/api/markets`, `/api/divergences`, `/api/trades`, `/api/brief/run`, `/api/scorecard`, `/api/contracts`, `/api/signals`, `/api/edge-decay`, `/api/price-history`, `/api/prediction-history`, `/api/portfolio`, `/api/latest-signals` |
| `ingestion/google_news.py` | Google News RSS poller (free, 5-15min) | `fetch_google_news()`, `NewsEvent` |
| `ingestion/gdelt_doc.py` | GDELT DOC 2.0 API poller (free, 15-60min) | `fetch_gdelt_docs()` |
| `ingestion/oil_prices.py` | EIA API v2 fetcher (Brent/WTI) | `fetch_brent()`, `fetch_wti()` |
| `ingestion/entities.py` | 30+ critical entity list for filtering | `matches_critical_entity()` |
| `ingestion/truth_social.py` | Truth Social POTUS feed via truthbrush | `fetch_truth_social()` |
| `markets/kalshi.py` | Kalshi API client (RSA-PSS auth) | `KalshiClient`, `IRAN_EVENT_TICKERS` |
| `markets/polymarket.py` | Polymarket read-only client | `PolymarketClient` |
| `markets/schemas.py` | Shared market data models | `MarketPrice`, `Orderbook`, `Position`, `PaperTrade` |
| `prediction/oil_price.py` | Oil price direction predictor | `OilPricePredictor` (cascade + LLM) |
| `prediction/ceasefire.py` | Ceasefire probability predictor | `CeasefirePredictor` (LLM) |
| `prediction/hormuz.py` | Hormuz reopening predictor | `HormuzReopeningPredictor` (cascade + LLM) |
| `prediction/schemas.py` | Prediction output model | `PredictionOutput` |
| `contracts/registry.py` | Contract registry + proxy classification | `ContractRegistry`, `ProxyClass` |
| `contracts/mapping_policy.py` | Proxy-aware signal mapping with cost model | `MappingPolicy`, `MappingResult` |
| `contracts/schemas.py` | Contract + mapping data models | `ContractRecord`, `MappingCostInputs` |
| `divergence/detector.py` | Model vs market comparison | `DivergenceDetector`, `Divergence` |
| `scoring/ledger.py` | Signal ledger — append-only signal records | `SignalLedger`, `SignalRecord` |
| `scoring/tracker.py` | Paper trade execution + order lifecycle | `PaperTradeTracker` |
| `scoring/prediction_log.py` | Prediction persistence with run_id | `PredictionLogger` |
| `scoring/calibration.py` | Hit rate, calibration curve, edge decay queries | `calibration_report()` |
| `scoring/report_card.py` | P&L report card by proxy class | `generate_report_card()` |
| `scoring/recalibration.py` | Bucket-based probability recalibration | `recalibrate_probability()` |
| `scoring/resolution.py` | Settlement polling + outcome backfill | `check_resolutions()` |
| `scoring/scorecard.py` | **Daily scorecard ETL** — 15+ metrics across 5 categories | `compute_daily_scorecard()` |
| `portfolio/allocator.py` | Quarter-Kelly position sizing | `PortfolioAllocator` |
| `portfolio/simulator.py` | **Portfolio simulator** — replays signal_ledger with weighted ensemble | `PortfolioSimulator`, `run()` |
| `dashboard/data.py` | Dashboard query layer (13 functions) | `get_scorecard_metrics()`, `get_latest_signals_with_markets()`, `get_prediction_history()` |
| `budget/tracker.py` | $20/day LLM budget + cost persistence | `BudgetTracker` (writes to `llm_usage`) |
| `ops/alerts.py` | Alert dispatcher with DuckDB + webhook sinks | `AlertDispatcher`, `DuckDBAlertSink` |
| `ops/runtime.py` | Runtime config (data/execution environment) | `RuntimeConfig`, `resolve_runtime_config()` |
| `simulation/cascade.py` | 6-rule cascade engine | `CascadeEngine` (blockade→flow→bypass→price→downstream→insurance) |
| `simulation/world_state.py` | In-memory world state | `WorldState`, `CellState` |
| `simulation/config.py` | YAML scenario config | `ScenarioConfig`, `load_scenario_config()` |
| `dashboard/data.py` | Reusable query functions for dashboard/API | `get_latest_brief()`, `get_signal_history()` |
| `db/schema.py` | DuckDB schema (20+ tables) + migrations | `create_tables()` |
| `db/writer.py` | Async single-writer queue | `DbWriter` |
| `db/runtime.py` | DuckDB path + environment resolution | `RuntimeConfig` |

### Data Flow

```
Google News RSS ──┐                                    Kalshi Prod API ──┐
                  ├→ News Events → 3 Prediction Models                   ├→ Market Prices
GDELT DOC API ────┘     │              │                Polymarket API ───┘       │
                        │        Claude Sonnet                                   │
EIA Oil Prices ─────────┘              │                                         │
                                       ↓                                         ↓
                              PredictionOutput ──→ Ticker Mapping ──→ DivergenceDetector
                                                                            │
                                                                   BUY_YES / BUY_NO / HOLD
                                                                            │
                                                                   Paper Trade (Kalshi Demo)
```

### Key Gotchas

- **Kalshi Demo vs Production**: Demo has sports/crypto only. Use production for market reads, demo for paper trades.
- **Kalshi API v2 fields**: Use `yes_bid_dollars` (float 0-1), NOT `yes_bid` (old cents format). Same for `volume_fp`.
- **Ticker mapping**: Predictions don't hardcode tickers. `_map_predictions_to_markets()` in brief.py maps at runtime.
- **AsyncAnthropic**: Always use `anthropic.AsyncAnthropic()` (not `Anthropic()`) since all prediction code is async.
- **GDELT DOC rate limits**: Gets 429 frequently. Google News RSS is the reliable primary source.
- **Env vars across processes**: Claude Code shell doesn't share env with user terminal. Use `/tmp/parallax-env.sh` pattern.
<!-- GSD:architecture-end -->

<!-- GSD:workflow-start source:GSD defaults -->
## GSD Workflow Enforcement

Before using Edit, Write, or other file-changing tools, start work through a GSD command so planning artifacts and execution context stay in sync.

Use these entry points:
- `/gsd:quick` for small fixes, doc updates, and ad-hoc tasks
- `/gsd:debug` for investigation and bug fixing
- `/gsd:execute-phase` for planned phase work

Do not make direct repo edits outside a GSD workflow unless the user explicitly asks to bypass it.
<!-- GSD:workflow-end -->



<!-- GSD:profile-start -->
## Developer Profile

> Profile not yet configured. Run `/gsd:profile-user` to generate your developer profile.
> This section is managed by `generate-claude-profile` -- do not edit manually.
<!-- GSD:profile-end -->
