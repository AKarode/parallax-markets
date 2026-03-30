# Technology Stack

**Analysis Date:** 2026-03-30

## Languages

**Primary:**
- Python 3.12 - Backend API, simulation engine, spatial computing
- TypeScript/JavaScript - Frontend visualization (under development)

**Tooling & Config:**
- YAML - Scenario configuration
- SQL - DuckDB schema and queries

## Runtime

**Environment:**
- Python 3.12+ (backend)
- Node.js 22+ (frontend, for build only)

**Package Manager:**
- pip + setuptools/hatchling (Python)
  - Lockfile: Not explicitly tracked (dependencies in pyproject.toml)
- npm (JavaScript/TypeScript)
  - Lockfile: `frontend/package-lock.json` (present)

## Frameworks

**Core API:**
- FastAPI 0.115+ - REST/WebSocket API server
- Uvicorn 0.34+ - ASGI application server

**Frontend:**
- React 18.3.1 - UI framework
- Vite 6.0.0 - Build tool and dev server
- TypeScript 5.6.2 - Type safety for frontend

**Visualization & Geospatial:**
- deck.gl 9.1.0 - High-performance visualization (core, geo-layers, layers, react)
- MapLibre GL 4.7.0 - Map rendering (open-source Mapbox alternative)
- react-map-gl 7.1.8 - React wrapper for map rendering
- H3 (h3-js) - Hexagonal hierarchical geospatial indexing (frontend for viz)

**Testing:**
- pytest 8.3 - Python test runner
- pytest-asyncio 0.25 - Async test support
- pytest-httpx 0.35 - HTTP mocking

**Build & Dev Tools:**
- Vite 6.0.0 - JavaScript bundler and dev server
- @vitejs/plugin-react 4.3.4 - React JSX support in Vite
- Babel 7.29.0 - JavaScript transpilation (indirect dependency)
- Rollup 4+ - Module bundler (indirect dependency)

## Key Dependencies

**Critical - Data & Simulation:**
- duckdb 1.2+ - Embedded OLAP database for world state and deltas
  - Extensions required: spatial, h3 (loaded at runtime)
- h3 4.1+ - Hexagonal geospatial indexing for ocean/chokepoint zones
- searoute 1.3+ - Sea route optimization and distance calculations
- shapely 2.0+ - Geometric operations for spatial analysis

**Critical - AI & Language:**
- anthropic 0.52+ - Claude API client for agent reasoning
  - Used for country agents and sub-actor decision-making
- sentence-transformers 3.4+ - Embedding models for semantic analysis
  - Required for agent memory context retrieval

**Critical - Infrastructure:**
- pydantic 2.10+ - Data validation and serialization
- websockets 14.0+ - WebSocket support for real-time simulation updates
- httpx 0.28+ - Async HTTP client for external API calls
- pyyaml 6.0+ - YAML scenario configuration parsing

**Optional - Data Integration:**
- google-cloud-bigquery 3.27+ - BigQuery integration for historical data
  - EIA (Energy Information Administration) data integration planned

## Configuration

**Environment Variables:**
- `ANTHROPIC_API_KEY` - Claude API authentication (required for agents)
- `GOOGLE_APPLICATION_CREDENTIALS` - GCP service account JSON path (optional, for BigQuery)
- `EIA_API_KEY` - Energy Information Administration API key (optional)
- `DUCKDB_PATH` - File path for DuckDB database (default: `/app/data/parallax.duckdb`)
- `PARALLAX_ADMIN_PASSWORD` - Admin authentication password (default: `admin`)
- `PARALLAX_INVITE_SEED` - Seed for invitation token generation (default: `dev-seed`)

**Runtime Configuration:**
- Scenario config: `backend/config/scenario_hormuz.yaml`
  - Loaded via `parallax.simulation.config.load_scenario_config()`
  - Contains agent token budgets, simulation parameters, oil flow rates

**Build Configuration:**
- No Vite config file detected in frontend (using defaults)
- No TypeScript config detected (tsconfig.tsbuildinfo present from previous build)

## Platform Requirements

**Development:**
- Docker + Docker Compose (for containerized dev environment)
- Python 3.12 runtime with build tools (gcc, make)
- Node.js 22+ for frontend builds
- curl (for health checks in Docker)

**Production:**
- Docker containers (backend: Python 3.12-slim, frontend: nginx:alpine)
- DuckDB file storage (persistent volume: `duckdb-data`)
- Anthropic API access (Claude 3.x models)
- Optional: Google Cloud BigQuery for data warehousing

## Package Management

**Backend:**
- Installation: `pip install -e ".[dev]"` (editable install with dev dependencies)
- Testing: `pytest tests/`
- DuckDB extensions preloaded in Docker build step

**Frontend:**
- Installation: `npm ci` (clean install from lock file)
- Build: `npm run build` (Vite production build to `/dist`)
- Artifacts served by nginx in production

## Infrastructure Stack

**Containerization:**
- Docker Compose orchestrates 2 services:
  1. Backend: `backend:8000` (Python FastAPI/Uvicorn)
  2. Frontend: `frontend:3000` (nginx serving static + proxying WebSocket/API)

**Networking:**
- Backend exposes port 8000 internally
- Frontend proxy layer (nginx) on port 3000 (public)
- WebSocket upgrade support in nginx (for real-time simulation)
- API proxying: `/api/*` routes to backend
- WebSocket proxying: `/ws` routes to backend with connection upgrade headers

**Data Persistence:**
- Named volume: `duckdb-data` (mounted at `/app/data` in backend)
- DuckDB file path configurable via env var

---

*Stack analysis: 2026-03-30*
