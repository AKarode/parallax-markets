"""Tests for ContractRegistry CRUD operations and seed data."""

import duckdb
import pytest

from parallax.contracts.registry import INITIAL_CONTRACTS, ContractRegistry
from parallax.contracts.schemas import ContractRecord, ProxyClass
from parallax.db.schema import create_tables


@pytest.fixture
def db_conn():
    """Create an in-memory DuckDB connection with schema."""
    conn = duckdb.connect(":memory:")
    create_tables(conn)
    return conn


@pytest.fixture
def registry(db_conn):
    """Create a ContractRegistry with an in-memory database."""
    return ContractRegistry(db_conn)


@pytest.fixture
def sample_contract():
    """A sample contract for testing."""
    return ContractRecord(
        ticker="TEST-TICKER-01",
        source="kalshi",
        event_ticker="KXTEST-01",
        title="Test Contract",
        resolution_criteria="Resolves YES if test passes",
        proxy_map={
            "ceasefire": ProxyClass.DIRECT,
            "oil_price": ProxyClass.NONE,
        },
        discount_map={"direct": 1.0, "near_proxy": 0.6, "loose_proxy": 0.3, "none": 0.0},
        invert_probability={"ceasefire": False, "oil_price": False},
    )


class TestUpsert:
    def test_inserts_into_both_tables(self, registry, sample_contract, db_conn):
        registry.upsert(sample_contract)

        rows = db_conn.execute(
            "SELECT ticker, source, title FROM contract_registry WHERE ticker = ?",
            [sample_contract.ticker],
        ).fetchall()
        assert len(rows) == 1
        assert rows[0][0] == "TEST-TICKER-01"
        assert rows[0][1] == "kalshi"

        proxy_rows = db_conn.execute(
            "SELECT ticker, model_type, proxy_class FROM contract_proxy_map WHERE ticker = ?",
            [sample_contract.ticker],
        ).fetchall()
        assert len(proxy_rows) == 2

    def test_upsert_updates_existing(self, registry, sample_contract, db_conn):
        registry.upsert(sample_contract)
        sample_contract.title = "Updated Title"
        registry.upsert(sample_contract)

        rows = db_conn.execute(
            "SELECT title FROM contract_registry WHERE ticker = ?",
            [sample_contract.ticker],
        ).fetchall()
        assert len(rows) == 1
        assert rows[0][0] == "Updated Title"


class TestGetActiveContracts:
    def test_returns_only_active(self, registry, sample_contract, db_conn):
        registry.upsert(sample_contract)

        inactive = ContractRecord(
            ticker="INACTIVE-01",
            source="kalshi",
            event_ticker="KXINACTIVE",
            title="Inactive Contract",
            resolution_criteria="Should not appear",
            proxy_map={"ceasefire": ProxyClass.NONE},
            is_active=False,
        )
        registry.upsert(inactive)

        active = registry.get_active_contracts()
        tickers = [c.ticker for c in active]
        assert "TEST-TICKER-01" in tickers
        assert "INACTIVE-01" not in tickers


class TestGetContractsForModel:
    def test_returns_non_none_contracts(self, registry):
        registry.seed_initial_contracts()
        results = registry.get_contracts_for_model("ceasefire")

        # All returned contracts should have proxy_class != NONE for ceasefire
        for contract, proxy_class, discount, invert in results:
            assert proxy_class != ProxyClass.NONE

    def test_excludes_none_proxy(self, registry):
        registry.seed_initial_contracts()
        results = registry.get_contracts_for_model("ceasefire")
        tickers = [c.ticker for c, _, _, _ in results]

        # KXWTIMAX and KXWTIMIN have ceasefire=NONE, should not appear
        assert "KXWTIMAX-26DEC31" not in tickers
        assert "KXWTIMIN-26DEC31" not in tickers


class TestGetProxyClass:
    def test_returns_correct_proxy_class(self, registry):
        registry.seed_initial_contracts()
        result = registry.get_proxy_class("KXUSAIRANAGREEMENT-27", "ceasefire")
        assert result == ProxyClass.NEAR_PROXY

    def test_returns_none_for_missing(self, registry):
        result = registry.get_proxy_class("NONEXISTENT", "ceasefire")
        assert result is None


class TestSeedInitialContracts:
    def test_populates_registry(self, registry):
        count = registry.seed_initial_contracts()
        assert count == len(INITIAL_CONTRACTS)
        assert count >= 4

        active = registry.get_active_contracts()
        assert len(active) == count

    def test_initial_contracts_have_expected_tickers(self):
        tickers = [c.ticker for c in INITIAL_CONTRACTS]
        assert "KXUSAIRANAGREEMENT-27" in tickers
        assert "KXCLOSEHORMUZ-27JAN" in tickers
        assert "KXWTIMAX-26DEC31" in tickers
        assert "KXWTIMIN-26DEC31" in tickers


class TestMarkInactive:
    def test_sets_inactive(self, registry, sample_contract):
        registry.upsert(sample_contract)
        registry.mark_inactive(sample_contract.ticker)

        active = registry.get_active_contracts()
        tickers = [c.ticker for c in active]
        assert sample_contract.ticker not in tickers
