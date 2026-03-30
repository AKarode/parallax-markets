# External Integrations

**Analysis Date:** 2026-03-30

## APIs & External Services

**AI & Language Models:**
- Anthropic Claude API - Agent decision-making and reasoning
  - SDK/Client: `anthropic>=0.52`
  - Auth: `ANTHROPIC_API_KEY` environment variable
  - Used by: Country agents and sub-actor agents for cascade decision logic
  - Model versions: Claude 3.x (determined by client library defaults)

**Data Enrichment:**
- Energy Information Administration (EIA) API - Oil/energy data
  - Status: Integration planned, not yet implemented
  - Auth: `EIA_API_KEY` environment variable
  - Purpose: Historical oil flow rates, strategic reserve data
  - Note: Optional integration, scenario config currently uses hardcoded values

**Maritime & Route Optimization:**
- searoute package - Sea route distance and transit calculations
  - No external API call; local package provides algorithms
  - Used by: Simulation engine for chokepoint rerouting logic
  - Provides: Distance calculations (Hormuz→Suez vs Cape of Good Hope routes)

## Data Storage

**Databases:**
- DuckDB (embedded OLAP database)
  - Connection: File path via `DUCKDB_PATH` env var (default: `/app/data/parallax.duckdb`)
  - Client: `duckdb>=1.2`
  - Type: Embedded, file-based (no separate server)
  - Extensions required at runtime:
    - `spatial` - Geospatial querying (ST_Within, etc.)
    - `h3` - Hexagonal geospatial indexing

**Optional - Data Warehouse:**
- Google Cloud BigQuery
  - Client: `google-cloud-bigquery>=3.27`
  - Auth: `GOOGLE_APPLICATION_CREDENTIALS` (path to service account JSON)
  - Status: Integration prepared, not yet implemented
  - Planned use: Historical world state snapshots, audit trail archival

**File Storage:**
- Local filesystem only (no cloud storage)
- DuckDB persists to: `/app/data/parallax.duckdb` (Docker named volume in production)
- Scenario YAML configs: `backend/config/`

**Caching:**
- None detected - DuckDB serves as both database and cache layer
- Future consideration: Agent memory context (rolling_context JSON column) may benefit from Redis

## Authentication & Identity

**Auth Provider:**
- Custom authentication (no third-party OAuth/SAML)
- Admin password: `PARALLAX_ADMIN_PASSWORD` env var
- Invite system seed: `PARALLAX_INVITE_SEED` env var
- Implementation approach: TBD (infrastructure prepared in `agent_memory` and `agent_prompts` tables)

## Monitoring & Observability

**Error Tracking:**
- None detected (no Sentry, Rollbar, or similar)
- Logging: Python stdlib `logging` module
  - Logger instances: `logging.getLogger(__name__)` pattern
  - Observed in: `parallax.db.writer` (DB write errors)

**Logs:**
- Stdout/stderr (captured by Docker)
- Log format: Python logging defaults (can be configured via handlers)
- No external log aggregation

**Health Checks:**
- Docker healthcheck: `curl http://localhost:8000/health`
  - Endpoint: Not yet implemented (infrastructure ready in docker-compose)

## CI/CD & Deployment

**Hosting:**
- Docker containers (self-hosted or cloud-agnostic)
- Development: Docker Compose (local dev environment)
- Production: Docker Compose compatible (can run on any Docker host, K8s, or cloud VMs)

**CI Pipeline:**
- GitHub Actions configured
  - Workflows: `.github/workflows/claude.yml` and `claude-code-review.yml` (Claude agent workflows)
- Docker build step includes test verification: `pytest tests/ -v --tb=short`
- Pre-deployment requirements: All tests must pass during container build

**Deployment Model:**
- Container-first: Backend and frontend both containerized
- Backend: Python 3.12-slim + Uvicorn ASGI server
- Frontend: nginx + static files from Vite build
- State: Persistent DuckDB volume

## Environment Configuration

**Required environment variables (production):**
- `ANTHROPIC_API_KEY` - Claude API authentication (mandatory)
- `DUCKDB_PATH` - Database file path

**Optional environment variables:**
- `GOOGLE_APPLICATION_CREDENTIALS` - GCP service account key path (for BigQuery)
- `EIA_API_KEY` - Energy data API key
- `PARALLAX_ADMIN_PASSWORD` - Admin auth (defaults to `admin`)
- `PARALLAX_INVITE_SEED` - Invitation token seed (defaults to `dev-seed`)

**Secrets location:**
- Environment variables only (no .env files in git)
- Docker Compose reads from shell environment
- Production: Use container orchestration secrets (K8s secrets, Docker Swarm secrets, etc.)

## Webhooks & Callbacks

**Incoming:**
- WebSocket endpoint: `/ws` (real-time simulation updates)
  - Bidirectional connection from frontend to backend
  - Proxied through nginx in production
  - Protocol: JSON messages (format TBD, simulation events expected)

**API Endpoints (inferred from nginx config):**
- REST API: `/api/*` proxies to backend `http://backend:8000/`
  - Endpoints: Not yet documented (implementation in progress)
  - Expected: Simulation control, state queries, configuration endpoints

**Outgoing:**
- Anthropic API calls - Agent requests to Claude
  - Async HTTP via `httpx>=0.28`
  - Format: OpenAI-compatible messages API
  - Streaming: Likely supported via Anthropic SDK

## Data Flow

**Scenario & Configuration:**
1. Scenario YAML loaded from `backend/config/scenario_hormuz.yaml`
2. Parsed into `ScenarioConfig` dataclass
3. Used to initialize simulation engine with parameters

**Simulation Execution:**
1. `SimulationEngine` (DES core) generates events on tick schedule
2. Events dispatched to handlers (agents, cascade logic)
3. World state deltas written to DuckDB via `DbWriter` (async queue)
4. State snapshots stored periodically (configurable interval)

**API Communication:**
1. Frontend WebSocket connects to `/ws` endpoint
2. Simulation ticks generate events broadcast via WebSocket
3. Frontend renders world state (H3 hexagons on map via deck.gl)
4. User actions sent back via REST API to backend

**Agent Integration:**
1. Simulation event arrives at agent handler
2. Agent queries rolling context from `agent_memory` table
3. Agent constructs prompt with context + world state
4. Anthropic API call (async via httpx)
5. Response updates agent memory and generates actions
6. Actions written to DuckDB and broadcast to frontend

---

*Integration audit: 2026-03-30*
