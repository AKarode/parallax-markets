---
phase: 01-contract-registry-mapping-policy-evaluation-ledger
verified: 2026-04-08T08:30:00Z
status: passed
score: 4/4 must-haves verified
overrides_applied: 0
---

# Phase 1: Contract Registry + Mapping Policy + Evaluation Ledger Verification Report

**Phase Goal:** Every trade signal has explicit proposition alignment, proxy quality tracking, and confidence discounting -- replacing the heuristic `_map_predictions_to_markets()`.
**Verified:** 2026-04-08T08:30:00Z
**Status:** passed
**Re-verification:** No -- initial verification

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | Contract registry in DuckDB stores every contract with resolution criteria and proxy classification per model type | VERIFIED | `contract_registry` and `contract_proxy_map` tables in schema.py (lines 169-193). ContractRegistry class with full CRUD in registry.py. 4 contracts seeded with proxy maps for all 3 model types. |
| 2 | Mapping policy replaces `_map_predictions_to_markets()` with explicit proxy-aware decision logic that discounts edge for non-DIRECT mappings | VERIFIED | MappingPolicy.evaluate() in mapping_policy.py applies discount (DIRECT=1.0, NEAR=0.6, LOOSE=0.3). brief.py uses `policy.evaluate()` (line 242). Old function renamed `_map_predictions_to_markets_legacy` (line 299), zero active calls to original. |
| 3 | Signal ledger records every signal with full provenance (model claim, contract mapped, proxy class, market state, trade decision) | VERIFIED | SignalLedger.record_signal() in ledger.py persists 18 fields per signal including model_claim, proxy_class, market_yes_price, effective_edge, signal direction. signal_ledger table has 25 columns (lines 196-223 of schema.py). |
| 4 | Pipeline runs end-to-end using new contract-aware mapping instead of heuristic ticker matching | VERIFIED | `python -m parallax.cli.brief --dry-run` produces full output with SIGNAL AUDIT section showing 7 evaluated mappings across 3 models and 4 contracts. All 165 tests pass. |

**Score:** 4/4 truths verified

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `backend/src/parallax/contracts/schemas.py` | ProxyClass, ContractRecord, MappingResult models | VERIFIED | 63 lines. ProxyClass enum with 4 values, ContractRecord with proxy_map/discount_map/invert_probability, MappingResult with effective_edge computation. |
| `backend/src/parallax/contracts/registry.py` | ContractRegistry with DuckDB CRUD | VERIFIED | 285 lines. 6 public methods (upsert, get_active_contracts, get_contracts_for_model, get_proxy_class, mark_inactive, seed_initial_contracts). 4 seed contracts. |
| `backend/src/parallax/contracts/mapping_policy.py` | MappingPolicy replacing heuristic mapping | VERIFIED | 113 lines. evaluate() method with proxy discounting, probability inversion, threshold filtering, sorted audit trail. |
| `backend/src/parallax/scoring/ledger.py` | SignalLedger for append-only signal tracking | VERIFIED | 244 lines. record_signal(), get_signals(), get_actionable_signals(), mark_traded(). SignalRecord with 25 fields. |
| `backend/src/parallax/db/schema.py` | contract_registry + contract_proxy_map + signal_ledger tables | VERIFIED | All 3 tables present in create_tables() (lines 169-223). |
| `backend/src/parallax/cli/brief.py` | Pipeline using MappingPolicy + SignalLedger | VERIFIED | Imports MappingPolicy, ContractRegistry, SignalLedger. Uses policy.evaluate() and ledger.record_signal() in run_brief(). SIGNAL AUDIT section in output. |
| `backend/tests/test_registry.py` | Registry CRUD tests | VERIFIED | Exists, tests pass. |
| `backend/tests/test_mapping_policy.py` | Mapping policy tests | VERIFIED | Exists, tests pass. |
| `backend/tests/test_ledger.py` | Signal ledger tests | VERIFIED | Exists, tests pass. |
| `backend/tests/test_brief.py` | Brief pipeline tests | VERIFIED | Exists, tests pass. |

### Key Link Verification

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| mapping_policy.py | registry.py | `self._registry.get_contracts_for_model` | WIRED | Line 66: `candidates = self._registry.get_contracts_for_model(prediction.model_id)` |
| mapping_policy.py | schemas.py | `from parallax.contracts.schemas import` | WIRED | Line 12: imports MappingResult, ProxyClass |
| brief.py | mapping_policy.py | `policy.evaluate()` | WIRED | Line 242: `mappings = policy.evaluate(pred, market_prices)` |
| brief.py | ledger.py | `ledger.record_signal()` | WIRED | Line 255: `signal = ledger.record_signal(pred, mapping, mp, ...)` |
| ledger.py | db/schema.py | signal_ledger table | WIRED | INSERT INTO signal_ledger (line 119-148) |

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| Dry-run pipeline produces signals | `python -m parallax.cli.brief --dry-run` | Output contains SIGNAL AUDIT with 7 mappings (BUY_YES, BUY_NO, REFUSED) | PASS |
| All tests pass | `python -m pytest tests/ -x -q` | 165 passed in 3.91s | PASS |
| Phase-specific tests pass | `python -m pytest tests/test_registry.py tests/test_mapping_policy.py tests/test_ledger.py tests/test_brief.py -x -q` | 49 passed in 1.11s | PASS |
| Schemas importable | `from parallax.contracts.schemas import ProxyClass, ContractRecord, MappingResult` | Success | PASS |

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|-----------|-------------|--------|----------|
| REG-01 | 01-01 | Contract registry stores ticker, source, event_ticker, title, resolution_criteria, etc. | SATISFIED | contract_registry table in schema.py with all required columns |
| REG-02 | 01-01 | Proxy classification per model type (ProxyClass enum) in contract_proxy_map | SATISFIED | ProxyClass enum with 4 values. contract_proxy_map table with ticker+model_type composite PK |
| REG-03 | 01-02 | MappingPolicy replaces heuristic mapping with proxy-aware discounting | SATISFIED | MappingPolicy.evaluate() with discount by proxy class. Old function renamed to _legacy. |
| REG-04 | 01-03 | Signal ledger persists every signal as append-only records | SATISFIED | SignalLedger.record_signal() inserts into signal_ledger table with 25 fields of provenance |
| REG-05 | 01-03 | Pipeline integration -- brief.py uses MappingPolicy + SignalLedger | SATISFIED | brief.py lines 230-256 use registry, policy, and ledger. No active calls to old heuristic. |

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| None | - | - | - | No anti-patterns detected |

### Human Verification Required

None. All phase goals are verifiable programmatically and have been verified.

### Gaps Summary

No gaps found. All 4 roadmap success criteria verified. All 5 requirements (REG-01 through REG-05) satisfied. Pipeline runs end-to-end with contract-aware mapping, proxy discounting, probability inversion, and signal ledger persistence. 165 tests passing.

---

_Verified: 2026-04-08T08:30:00Z_
_Verifier: Claude (gsd-verifier)_
