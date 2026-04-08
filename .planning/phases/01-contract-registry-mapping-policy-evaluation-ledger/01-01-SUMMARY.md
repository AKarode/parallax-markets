---
phase: 01-contract-registry-mapping-policy-evaluation-ledger
plan: 01
subsystem: database
tags: [duckdb, pydantic, enum, proxy-classification, contract-registry]

requires: []
provides:
  - ProxyClass enum (DIRECT, NEAR_PROXY, LOOSE_PROXY, NONE)
  - ContractRecord and MappingResult Pydantic models
  - contract_registry and contract_proxy_map DuckDB tables
  - ContractRegistry class with CRUD operations
  - Seed data for 4 Iran/Hormuz contracts with proxy classifications
affects: [01-02-mapping-policy, 01-03-signal-ledger]

tech-stack:
  added: []
  patterns: [proxy-classification-per-model, discount-map-for-edge-adjustment, delete-reinsert-for-proxy-map-upsert]

key-files:
  created:
    - backend/src/parallax/contracts/__init__.py
    - backend/src/parallax/contracts/schemas.py
    - backend/src/parallax/contracts/registry.py
    - backend/tests/test_contracts_schemas.py
    - backend/tests/test_registry.py
  modified:
    - backend/src/parallax/db/schema.py
    - backend/tests/test_schema.py

key-decisions:
  - "Delete-and-reinsert for proxy map upsert instead of INSERT OR REPLACE on composite key"
  - "Default discount map as module-level constant rather than per-contract override"

patterns-established:
  - "ProxyClass enum: str-backed enum for proxy classification levels"
  - "ContractRegistry: DuckDB CRUD with _load_proxy_map helper for reconstructing models from normalized tables"

requirements-completed: [REG-01, REG-02]

duration: 5min
completed: 2026-04-08
---

# Phase 1 Plan 01: Contract Registry Summary

**DuckDB-backed contract registry with proxy classification per prediction model type, seeded with 4 Iran/Hormuz contracts**

## Performance

- **Duration:** 5 min
- **Started:** 2026-04-08T08:05:23Z
- **Completed:** 2026-04-08T08:10:20Z
- **Tasks:** 2/2
- **Files modified:** 7

## Accomplishments

### Task 1: Contract schemas and DuckDB tables
- Created `ProxyClass` enum with 4 values: DIRECT, NEAR_PROXY, LOOSE_PROXY, NONE
- Created `ContractRecord` Pydantic model with proxy_map, discount_map, invert_probability fields
- Created `MappingResult` Pydantic model with effective_edge computation
- Added `contract_registry` and `contract_proxy_map` tables to `create_tables()`
- 10 tests for schemas and table creation

### Task 2: ContractRegistry CRUD and seed data
- Created `ContractRegistry` class with 6 public methods: upsert, get_active_contracts, get_contracts_for_model, get_proxy_class, mark_inactive, seed_initial_contracts
- Seeded 4 contracts: KXUSAIRANAGREEMENT-27 (ceasefire=NEAR_PROXY), KXCLOSEHORMUZ-27JAN (hormuz=DIRECT), KXWTIMAX-26DEC31 (oil=NEAR_PROXY), KXWTIMIN-26DEC31 (oil=NEAR_PROXY)
- Each contract has proxy classifications for all 3 model types (ceasefire, hormuz_reopening, oil_price)
- 10 tests covering all CRUD operations

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Updated test_schema.py expected table set**
- **Found during:** Task 2
- **Issue:** Existing test_schema.py asserts exact table count; new tables caused test failure
- **Fix:** Added contract_registry and contract_proxy_map to expected set
- **Files modified:** backend/tests/test_schema.py
- **Commit:** 55246a8

## Verification

- All 167 tests passing (120 original + 20 new + 27 existing that were already counted)
- Imports verified: `ProxyClass`, `ContractRecord`, `MappingResult`, `ContractRegistry`, `INITIAL_CONTRACTS`
- DuckDB creates all 14 tables including contract_registry and contract_proxy_map
- Seed data loads 4 contracts with correct proxy classifications
- Proxy class lookup returns expected values (e.g., KXUSAIRANAGREEMENT-27/ceasefire = NEAR_PROXY)

## Commits

| Hash | Message |
|------|---------|
| 8c15d66 | test(01-01): add failing tests for contract schemas and DuckDB tables |
| a490609 | feat(01-01): add contract schemas and DuckDB tables |
| f634f3e | test(01-01): add failing tests for ContractRegistry CRUD and seed data |
| 55246a8 | feat(01-01): add ContractRegistry with CRUD operations and seed data |

## Self-Check: PASSED
