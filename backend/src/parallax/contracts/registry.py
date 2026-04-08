"""Contract registry with DuckDB persistence and proxy classification.

Manages the mapping between prediction model outputs and tradeable
market contracts. Each contract has a proxy classification per model type,
determining how directly the model's prediction applies.
"""

from __future__ import annotations

import json
import logging

import duckdb

from parallax.contracts.schemas import ContractRecord, ProxyClass

logger = logging.getLogger(__name__)


INITIAL_CONTRACTS = [
    ContractRecord(
        ticker="KXUSAIRANAGREEMENT-27",
        source="kalshi",
        event_ticker="KXUSAIRANAGREEMENT-27",
        title="US-Iran Agreement",
        resolution_criteria="Resolves YES if US and Iran reach a formal agreement.",
        proxy_map={
            "ceasefire": ProxyClass.NEAR_PROXY,
            "hormuz_reopening": ProxyClass.LOOSE_PROXY,
            "oil_price": ProxyClass.NONE,
        },
        discount_map={"direct": 1.0, "near_proxy": 0.6, "loose_proxy": 0.3, "none": 0.0},
        invert_probability={"ceasefire": False, "hormuz_reopening": False, "oil_price": False},
    ),
    ContractRecord(
        ticker="KXCLOSEHORMUZ-27JAN",
        source="kalshi",
        event_ticker="KXCLOSEHORMUZ-27JAN",
        title="Strait of Hormuz Closure",
        resolution_criteria="Resolves YES if Strait of Hormuz is closed to commercial shipping.",
        proxy_map={
            "hormuz_reopening": ProxyClass.DIRECT,
            "oil_price": ProxyClass.NEAR_PROXY,
            "ceasefire": ProxyClass.LOOSE_PROXY,
        },
        discount_map={"direct": 1.0, "near_proxy": 0.6, "loose_proxy": 0.3, "none": 0.0},
        invert_probability={"hormuz_reopening": True, "oil_price": False, "ceasefire": False},
    ),
    ContractRecord(
        ticker="KXWTIMAX-26DEC31",
        source="kalshi",
        event_ticker="KXWTIMAX-26DEC31",
        title="WTI Oil Price Maximum by Year End",
        resolution_criteria="Resolves YES if WTI crude reaches target price by Dec 31 2026.",
        proxy_map={
            "oil_price": ProxyClass.NEAR_PROXY,
            "hormuz_reopening": ProxyClass.LOOSE_PROXY,
            "ceasefire": ProxyClass.NONE,
        },
        discount_map={"direct": 1.0, "near_proxy": 0.6, "loose_proxy": 0.3, "none": 0.0},
        invert_probability={"oil_price": False, "hormuz_reopening": False, "ceasefire": False},
    ),
    ContractRecord(
        ticker="KXWTIMIN-26DEC31",
        source="kalshi",
        event_ticker="KXWTIMIN-26DEC31",
        title="WTI Oil Price Minimum by Year End",
        resolution_criteria="Resolves YES if WTI crude drops to target price by Dec 31 2026.",
        proxy_map={
            "oil_price": ProxyClass.NEAR_PROXY,
            "hormuz_reopening": ProxyClass.LOOSE_PROXY,
            "ceasefire": ProxyClass.NONE,
        },
        discount_map={"direct": 1.0, "near_proxy": 0.6, "loose_proxy": 0.3, "none": 0.0},
        invert_probability={"oil_price": False, "hormuz_reopening": False, "ceasefire": False},
    ),
]


class ContractRegistry:
    """CRUD operations for contract registry and proxy classification in DuckDB."""

    def __init__(self, conn: duckdb.DuckDBPyConnection) -> None:
        self._conn = conn

    def upsert(self, contract: ContractRecord) -> None:
        """Insert or update a contract in the registry and its proxy mappings."""
        metadata_json = json.dumps(contract.metadata) if contract.metadata else None

        self._conn.execute(
            """
            INSERT OR REPLACE INTO contract_registry
            (ticker, source, event_ticker, title, resolution_criteria,
             resolution_date, is_active, last_checked, metadata)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                contract.ticker,
                contract.source,
                contract.event_ticker,
                contract.title,
                contract.resolution_criteria,
                contract.resolution_date.isoformat() if contract.resolution_date else None,
                contract.is_active,
                contract.last_checked.isoformat() if contract.last_checked else None,
                metadata_json,
            ],
        )

        # Delete existing proxy mappings for this ticker, then re-insert
        self._conn.execute(
            "DELETE FROM contract_proxy_map WHERE ticker = ?",
            [contract.ticker],
        )

        invert_map = contract.invert_probability or {}
        for model_type, proxy_class in contract.proxy_map.items():
            discount = contract.discount_map.get(proxy_class.value, 0.0)
            invert = invert_map.get(model_type, False)
            self._conn.execute(
                """
                INSERT INTO contract_proxy_map
                (ticker, model_type, proxy_class, confidence_discount, invert_probability)
                VALUES (?, ?, ?, ?, ?)
                """,
                [contract.ticker, model_type, proxy_class.value, discount, invert],
            )

        logger.debug("Upserted contract %s with %d proxy mappings",
                      contract.ticker, len(contract.proxy_map))

    def get_active_contracts(self) -> list[ContractRecord]:
        """Return all active contracts with their proxy mappings."""
        rows = self._conn.execute(
            """
            SELECT ticker, source, event_ticker, title, resolution_criteria,
                   resolution_date, is_active, last_checked, metadata
            FROM contract_registry
            WHERE is_active = true
            """
        ).fetchall()

        contracts = []
        for row in rows:
            ticker = row[0]
            proxy_map, discount_map, invert_map = self._load_proxy_map(ticker)
            contracts.append(ContractRecord(
                ticker=ticker,
                source=row[1],
                event_ticker=row[2],
                title=row[3],
                resolution_criteria=row[4],
                resolution_date=row[5],
                is_active=row[6],
                last_checked=row[7],
                metadata=json.loads(row[8]) if row[8] else None,
                proxy_map=proxy_map,
                discount_map=discount_map,
                invert_probability=invert_map,
            ))

        return contracts

    def get_contracts_for_model(
        self, model_type: str,
    ) -> list[tuple[ContractRecord, ProxyClass, float, bool]]:
        """Return active contracts relevant to a model type.

        Returns tuples of (contract, proxy_class, confidence_discount, invert_probability)
        for contracts where proxy_class != NONE for the given model_type.
        """
        rows = self._conn.execute(
            """
            SELECT cpm.ticker, cpm.proxy_class, cpm.confidence_discount, cpm.invert_probability
            FROM contract_proxy_map cpm
            JOIN contract_registry cr ON cr.ticker = cpm.ticker
            WHERE cpm.model_type = ?
              AND cpm.proxy_class != 'none'
              AND cr.is_active = true
            """,
            [model_type],
        ).fetchall()

        results = []
        for row in rows:
            ticker, proxy_class_str, discount, invert = row
            contract = self._load_contract(ticker)
            if contract is None:
                continue
            results.append((
                contract,
                ProxyClass(proxy_class_str),
                discount,
                bool(invert),
            ))

        return results

    def get_proxy_class(self, ticker: str, model_type: str) -> ProxyClass | None:
        """Look up the proxy class for a specific ticker and model type."""
        row = self._conn.execute(
            "SELECT proxy_class FROM contract_proxy_map WHERE ticker = ? AND model_type = ?",
            [ticker, model_type],
        ).fetchone()

        if row is None:
            return None
        return ProxyClass(row[0])

    def mark_inactive(self, ticker: str) -> None:
        """Mark a contract as inactive."""
        self._conn.execute(
            "UPDATE contract_registry SET is_active = false WHERE ticker = ?",
            [ticker],
        )
        logger.info("Marked contract %s as inactive", ticker)

    def seed_initial_contracts(self) -> int:
        """Populate the registry with known Iran/Hormuz contracts.

        Returns:
            Number of contracts seeded.
        """
        for contract in INITIAL_CONTRACTS:
            self.upsert(contract)
        logger.info("Seeded %d initial contracts", len(INITIAL_CONTRACTS))
        return len(INITIAL_CONTRACTS)

    def _load_proxy_map(
        self, ticker: str,
    ) -> tuple[dict[str, ProxyClass], dict[str, float], dict[str, bool]]:
        """Load proxy mappings for a ticker from the proxy map table."""
        rows = self._conn.execute(
            """
            SELECT model_type, proxy_class, confidence_discount, invert_probability
            FROM contract_proxy_map
            WHERE ticker = ?
            """,
            [ticker],
        ).fetchall()

        proxy_map: dict[str, ProxyClass] = {}
        discount_map: dict[str, float] = {
            "direct": 1.0, "near_proxy": 0.6, "loose_proxy": 0.3, "none": 0.0,
        }
        invert_map: dict[str, bool] = {}

        for model_type, proxy_class_str, discount, invert in rows:
            proxy_map[model_type] = ProxyClass(proxy_class_str)
            discount_map[proxy_class_str] = discount
            invert_map[model_type] = bool(invert)

        return proxy_map, discount_map, invert_map

    def _load_contract(self, ticker: str) -> ContractRecord | None:
        """Load a single contract by ticker."""
        row = self._conn.execute(
            """
            SELECT ticker, source, event_ticker, title, resolution_criteria,
                   resolution_date, is_active, last_checked, metadata
            FROM contract_registry
            WHERE ticker = ?
            """,
            [ticker],
        ).fetchone()

        if row is None:
            return None

        proxy_map, discount_map, invert_map = self._load_proxy_map(ticker)
        return ContractRecord(
            ticker=row[0],
            source=row[1],
            event_ticker=row[2],
            title=row[3],
            resolution_criteria=row[4],
            resolution_date=row[5],
            is_active=row[6],
            last_checked=row[7],
            metadata=json.loads(row[8]) if row[8] else None,
            proxy_map=proxy_map,
            discount_map=discount_map,
            invert_probability=invert_map,
        )
