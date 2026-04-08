"""Tests for contract registry schemas and DuckDB table creation."""

import duckdb
import pytest

from parallax.contracts.schemas import ContractRecord, MappingResult, ProxyClass
from parallax.db.schema import create_tables


class TestProxyClass:
    def test_direct_from_string(self):
        assert ProxyClass("direct") == ProxyClass.DIRECT

    def test_none_from_string(self):
        assert ProxyClass("none") == ProxyClass.NONE

    def test_near_proxy_from_string(self):
        assert ProxyClass("near_proxy") == ProxyClass.NEAR_PROXY

    def test_loose_proxy_from_string(self):
        assert ProxyClass("loose_proxy") == ProxyClass.LOOSE_PROXY

    def test_has_exactly_four_members(self):
        assert len(ProxyClass) == 4


class TestContractRecord:
    def test_validates_with_all_required_fields(self):
        record = ContractRecord(
            ticker="TEST-TICKER",
            source="kalshi",
            event_ticker="KXTEST",
            title="Test Contract",
            resolution_criteria="Resolves YES if test passes",
            proxy_map={"ceasefire": ProxyClass.DIRECT},
        )
        assert record.ticker == "TEST-TICKER"
        assert record.source == "kalshi"
        assert record.is_active is True

    def test_default_discount_map(self):
        record = ContractRecord(
            ticker="TEST-TICKER",
            source="kalshi",
            event_ticker="KXTEST",
            title="Test Contract",
            resolution_criteria="Resolves YES if test passes",
            proxy_map={"ceasefire": ProxyClass.DIRECT},
        )
        assert record.discount_map == {
            "direct": 1.0,
            "near_proxy": 0.6,
            "loose_proxy": 0.3,
            "none": 0.0,
        }


class TestMappingResult:
    def test_effective_edge_computed(self):
        result = MappingResult(
            prediction_model_id="ceasefire",
            contract_ticker="TEST-TICKER",
            proxy_class=ProxyClass.NEAR_PROXY,
            raw_edge=0.15,
            confidence_discount=0.6,
            effective_edge=0.15 * 0.6,
            should_trade=True,
            reason="Edge exceeds threshold",
        )
        assert result.effective_edge == pytest.approx(0.09)


class TestDuckDBTables:
    def test_contract_registry_table_created(self):
        conn = duckdb.connect(":memory:")
        create_tables(conn)
        tables = [r[0] for r in conn.execute("SHOW TABLES").fetchall()]
        assert "contract_registry" in tables

    def test_contract_proxy_map_table_created(self):
        conn = duckdb.connect(":memory:")
        create_tables(conn)
        tables = [r[0] for r in conn.execute("SHOW TABLES").fetchall()]
        assert "contract_proxy_map" in tables
