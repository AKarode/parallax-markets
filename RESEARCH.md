# Parallax — Technology Research Report
*Generated: March 30, 2026*

## Executive Summary

All core technologies in the proposed stack are **confirmed viable**. Two significant architecture changes recommended based on research:

1. **Drop LangGraph as simulation engine** → Use custom Python DES engine, call LangGraph only for AI-augmented decision points (Phase 2)
2. **Supplement Overture Maps** with Searoute + Natural Earth + NGA World Port Index for maritime data (Overture has no shipping routes)

No blockers for Phase 1. Ready to build.

---

## 1. DuckDB + H3 Extension — GO

**Status:** Community extension, wraps Uber H3 v4.x C library. Install via `INSTALL h3 FROM community; LOAD h3;`

**All required operations confirmed:**
| Operation | Function | Status |
|-----------|----------|--------|
| Cell from lat/lng | `h3_latlng_to_cell(lat, lng, res)` | Supported |
| K-ring neighbors | `h3_grid_disk(cell, k)` | Supported (returns LIST) |
| Parent/child cells | `h3_cell_to_parent()`, `h3_cell_to_children()` | Supported |
| Grid distance | `h3_grid_distance(a, b)` | Supported |
| Cell boundary (WKT) | `h3_cell_to_boundary_wkt(cell)` | Supported |
| Adjacency check | `h3_are_neighbor_cells(a, b)` | Supported |
| Path between cells | `h3_grid_path_cells(origin, dest)` | Supported |

**Spatial extension integration:** Works alongside `spatial` extension. Pattern for Overture data:
```sql
LOAD spatial; LOAD h3;
SELECT *, h3_latlng_to_cell(ST_Y(ST_Centroid(geometry)), ST_X(ST_Centroid(geometry)), 7) as h3_cell
FROM read_parquet('overture_places.parquet');
```

**Performance:** Millions of rows in seconds for cell indexing. Hash joins on H3 BIGINT IDs are sub-second. Parquet predicate pushdown + H3 = fast pipeline.

**Gotchas:**
- No built-in polygon polyfill (fill polygon with H3 cells) — use Python `h3` library for this
- `h3_grid_disk` returns LIST — use `UNNEST()` for joins
- Community extension may lag behind DuckDB major releases by days/weeks
- `h3_cell_to_children` expands ~7x per resolution level — be careful with large deltas

---

## 2. Overture Maps — GO (with supplements)

**License:** CDLA Permissive 2.0 (very permissive). Places theme has ODbL from OSM (attribution + share-alike for derivative databases).

**Available for Middle East:**
- Places/POIs: ports, airports, fuel stations, government buildings — HIGH relevance
- Transportation: road networks — HIGH relevance
- Administrative boundaries: country/state/district — HIGH relevance
- Buildings: footprints globally — MEDIUM relevance
- Base (land/water): coastlines — MEDIUM relevance

**NOT available:** Military bases (not tagged), shipping lanes, naval infrastructure, maritime routes.

**Access:** GeoParquet on S3/Azure. Query directly with DuckDB:
```sql
SELECT * FROM read_parquet('s3://overturemaps-us-west-2/release/2024-*/theme=places/type=place/*')
WHERE bbox.xmin > 44 AND bbox.xmax < 60 AND bbox.ymin > 12 AND bbox.ymax < 40;
```

**Coverage quality:** UAE/Saudi/Qatar/Kuwait strong. Iran moderate (major cities). Yemen weakest (conflict zone). Updates roughly quarterly.

**Required supplements:**
| Gap | Source | License |
|-----|--------|---------|
| Shipping routes | Searoute (Eurostat) | Open source |
| Shipping lane geometry | Natural Earth | Public domain |
| Port metadata | NGA World Port Index | Free/public |
| Military bases | OSM `military=*` tags via Overpass API | ODbL |
| Vessel density | Global Fishing Watch (BigQuery) | Free for research |
| Nautical data | OpenSeaMap | Open source |

---

## 3. deck.gl H3HexagonLayer — GO

**Native H3 support** via `@deck.gl/geo-layers`. Stable since v8+.

**Scale:** 200K-500K hexes render smoothly out of the box. Our estimate (~350K total across resolutions) is well within comfort zone.

**Variable resolution strategy — CRITICAL:**
Split into separate layers per resolution band, each with `highPrecision: false`:
```
Ocean/shipping (res 3-4):    ~100K hexes → Layer 1
Contested zones (res 6-7):   ~200K hexes → Layer 2
Infrastructure (res 8-9):     ~50K hexes → Layer 3
```
Do NOT mix resolutions in a single layer (`highPrecision: true` is 3-5x slower).

**Temporal animation:** Built-in via `transitions` prop:
```js
new H3HexagonLayer({
  data: simulationSteps[currentStep],
  getFillColor: d => influenceToColor(d.influence),
  transitions: { getFillColor: 600 },  // smooth GPU interpolation
  updateTriggers: { getFillColor: [currentStep] },
})
```

**Base map:** Use MapLibre GL (free, open source) instead of Mapbox.

**React integration:** First-class via `@deck.gl/react`.

---

## 4. GDELT — CONDITIONAL GO (supplement with ACLED)

**Precision:** ~60-70% of events geocoded only to country/city level. Sub-city precision is rare and depends on source article quality.

**Noise:** ~30%+ false positive rate on individual event records. Filter with `NumMentions > 3` or `NumSources > 2`.

**Lag:** 15-minute update cadence. Real-world-to-GDELT: ~1-4 hours for major events.

**Access:** Google BigQuery (1TB/month free tier). Also direct CSV downloads (15-min update files).

**For Iran specifically:** Good coverage of major cities (Tehran, Isfahan, Bandar Abbas). Weak on specific bases, rural locations, and Persian-language media. FIPS country codes (not ISO).

**Recommendation:**
- GDELT → real-time trend detection, event volume tracking, media attention signals
- ACLED → validated conflict events with precise geocoding (days-weeks lag)
- Curated sources (Wikipedia timelines, Reuters RSS) → ground truth for demo scenario

---

## 5. OASIS / MiroFish — SKIP FOR PHASE 1

**OASIS** (Apache 2.0): Social media simulation framework, not geopolitical. Gives ~40% of what we need. Built on CAMEL multi-agent framework.

**MiroFish** (AGPL-3.0): Adds geopolitical domain layer on OASIS. AGPL contaminates any derivative work.

**Better alternative for Phase 2:** **Concordia** (Google DeepMind, Apache 2.0) — game-master architecture maps well to geopolitical scenario management. Worth evaluating when we build the agent layer.

**Phase 1 decision:** None of these matter. Phase 1 is spatial cascade computation with zero LLM agents.

---

## 6. Strait of Hormuz Data — GO

**Shipping route generation:** `searoute` (Eurostat, open source Python/npm) — generates realistic routes between any two ports as GeoJSON LineStrings. Perfect for H3 cell mapping.

**Vessel density:** Global Fishing Watch via BigQuery (free, 2012-present, lat/lon positions).

**Traffic volume:** ~20-21M barrels oil/day through Hormuz. ~50-80 vessels/day. ~20-30 oil tankers/day.

**Rerouting model:**
- Hormuz → Suez → Europe: ~6,300 NM
- Cape of Good Hope → Europe: ~11,600 NM (+84% distance, +10-14 days)
- Pipeline bypass capacity: ~6.5M bbl/day (only ~30% of normal Hormuz flow)
  - Saudi East-West pipeline: 5M bbl/day to Yanbu (Red Sea)
  - UAE Habshan-Fujairah pipeline: 1.5M bbl/day to Gulf of Oman

**Energy dependency data:**
| Source | Format | Cost |
|--------|--------|------|
| Energy Institute Statistical Review | XLSX | Free |
| EIA International | CSV/API | Free |
| UN COMTRADE | CSV/JSON API | Free |
| Chatham House Resource Trade | CSV | Free |

---

## 7. LangGraph for Simulation — NO (for DES engine)

**Assessment:** LangGraph is a workflow graph framework optimized for chatbot/agent patterns. Using it as a discrete event simulation engine would fight the framework.

**Mismatch points:**
- No native event queue / priority scheduling concept
- Graph topology designed for branching workflows, not dynamic event dispatch
- State serialization overhead at every step (irrelevant for LLM calls, wasteful for pure computation)
- No simulation clock concept
- Forking requires checkpoint + new thread (vs simple deepcopy)

**Where LangGraph adds value:** Tool-calling agent loops, multi-agent supervisor patterns, structured output parsing. These are Phase 2 concerns.

**Recommendation — Hybrid architecture:**
```
Custom DES Engine (Python/asyncio + heapq)
├── Event Queue (priority-ordered)
├── World State (Python dataclass)
├── Simulation Clock
├── Fork Manager (deepcopy + asyncio.gather)
│
├── AI Decision Points (Phase 2):
│   └── LangGraph sub-graph (agent + spatial DB tools)
│
└── Pure Computation Steps (Phase 1):
    └── Direct Python (no LLM, no overhead)
```

---

## Revised Tech Stack

| Layer | Technology | Change from Spec? |
|-------|-----------|-------------------|
| Spatial computation | DuckDB + H3 extension | No change |
| Base map data | Overture Maps + Searoute + Natural Earth + NGA WPI | **Added supplements** |
| Event ingestion | GDELT (BigQuery) + ACLED + curated RSS | No change |
| Economic data | Energy Institute Statistical Review + EIA API + UN COMTRADE | No change |
| Simulation engine | **Custom Python DES (asyncio + heapq)** | **Changed from LangGraph** |
| Agent reasoning (Phase 2) | LangGraph sub-graphs for tool-calling agents | **Scoped to agent layer only** |
| Agent framework (Phase 2) | Evaluate Concordia (DeepMind) | **New recommendation** |
| Visualization | deck.gl H3HexagonLayer (3 resolution-band layers) | **Optimized architecture** |
| Base map rendering | MapLibre GL | **Changed from Mapbox (free)** |
| Frontend | React + deck.gl | No change |
| Backend | Python (FastAPI) | No change |
| Deployment | Vercel (frontend) + Railway/Fly (backend) | No change |

---

## Key Design Decisions Resolved

1. **H3 resolution strategy:** Res 3-4 ocean, res 6-7 contested, res 8-9 infrastructure. Split into 3 deck.gl layers.
2. **Shipping routes as H3 cells:** Use `searoute` to generate route GeoJSON → sample points along LineString → convert to H3 cells → store as chain with capacity/flow attributes.
3. **Partial blockade modeling:** Iran selectively allowing some vessels (e.g., Pakistani-flagged). Model as flow reduction percentage per cell, not binary open/closed. Pipeline bypass adds 6.5M bbl/day capacity outside Hormuz.
4. **Simulation engine:** Custom Python DES, not LangGraph. LangGraph reserved for Phase 2 agent reasoning.

---

## Ready to Build: Phase 1 Checklist

- [ ] Initialize Python project (FastAPI backend + React frontend)
- [ ] Set up DuckDB with H3 + spatial extensions
- [ ] Load Overture Maps data for Middle East bounding box
- [ ] Generate Hormuz shipping routes via Searoute → H3 cells
- [ ] Load energy dependency data (Energy Institute Statistical Review)
- [ ] Build energy flow disruption model (rule-based)
- [ ] Build price shock propagation logic (dependency ratios)
- [ ] Stand up deck.gl frontend with 3 H3 resolution-band layers
- [ ] Add temporal playback (simulation step slider + transitions)
- [ ] Add scenario injection UI (toggle Hormuz status, adjust parameters)
- [ ] Deploy MVP
- [ ] Log first predictions, begin weekly verification
