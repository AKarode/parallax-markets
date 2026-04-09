"""DuckDB schema bootstrap and lightweight migrations."""

from __future__ import annotations

import duckdb


def _column_exists(
    conn: duckdb.DuckDBPyConnection,
    table_name: str,
    column_name: str,
) -> bool:
    row = conn.execute(
        """
        SELECT COUNT(*)
        FROM information_schema.columns
        WHERE table_name = ? AND column_name = ?
        """,
        [table_name, column_name],
    ).fetchone()
    return bool(row and row[0])


def _table_exists(
    conn: duckdb.DuckDBPyConnection,
    table_name: str,
) -> bool:
    row = conn.execute(
        """
        SELECT COUNT(*)
        FROM information_schema.tables
        WHERE table_name = ?
        """,
        [table_name],
    ).fetchone()
    return bool(row and row[0])


def _add_column_if_missing(
    conn: duckdb.DuckDBPyConnection,
    table_name: str,
    column_name: str,
    column_type: str,
) -> None:
    if not _column_exists(conn, table_name, column_name):
        conn.execute(
            f"ALTER TABLE {table_name} ADD COLUMN {column_name} {column_type}",
        )


def _create_core_tables(conn: duckdb.DuckDBPyConnection) -> None:
    conn.execute("""
        CREATE TABLE IF NOT EXISTS world_state_delta (
            cell_id BIGINT NOT NULL,
            tick INTEGER NOT NULL,
            influence VARCHAR,
            threat_level DOUBLE,
            flow DOUBLE,
            status VARCHAR,
            changed_at TIMESTAMP DEFAULT current_timestamp
        )
    """)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS world_state_snapshot (
            cell_id BIGINT NOT NULL,
            tick INTEGER NOT NULL,
            influence VARCHAR,
            threat_level DOUBLE,
            flow DOUBLE,
            status VARCHAR,
            snapshot_at TIMESTAMP DEFAULT current_timestamp
        )
    """)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS agent_memory (
            agent_id VARCHAR NOT NULL,
            prompt_version VARCHAR NOT NULL,
            rolling_context JSON,
            weight DOUBLE DEFAULT 1.0,
            last_activated TIMESTAMP,
            PRIMARY KEY (agent_id)
        )
    """)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS agent_prompts (
            agent_id VARCHAR NOT NULL,
            version VARCHAR NOT NULL,
            system_prompt TEXT NOT NULL,
            historical_baseline TEXT,
            created_at TIMESTAMP DEFAULT current_timestamp,
            PRIMARY KEY (agent_id, version)
        )
    """)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS decisions (
            decision_id VARCHAR NOT NULL PRIMARY KEY,
            agent_id VARCHAR NOT NULL,
            tick INTEGER NOT NULL,
            action_type VARCHAR NOT NULL,
            target_h3_cells JSON,
            intensity DOUBLE,
            description TEXT,
            reasoning TEXT,
            confidence DOUBLE,
            prompt_version VARCHAR,
            created_at TIMESTAMP DEFAULT current_timestamp
        )
    """)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS predictions (
            prediction_id VARCHAR NOT NULL PRIMARY KEY,
            agent_id VARCHAR NOT NULL,
            prediction_type VARCHAR NOT NULL,
            direction VARCHAR NOT NULL,
            magnitude_range JSON,
            unit VARCHAR,
            timeframe VARCHAR NOT NULL,
            confidence DOUBLE NOT NULL,
            reasoning TEXT,
            prompt_version VARCHAR NOT NULL,
            created_at TIMESTAMP DEFAULT current_timestamp,
            resolve_by TIMESTAMP NOT NULL,
            ground_truth JSON,
            score_direction BOOLEAN,
            score_magnitude BOOLEAN,
            miss_tag VARCHAR,
            scored_at TIMESTAMP
        )
    """)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS curated_events (
            event_id VARCHAR NOT NULL PRIMARY KEY,
            source VARCHAR NOT NULL,
            actor1 VARCHAR,
            actor2 VARCHAR,
            action VARCHAR,
            goldstein_scale DOUBLE,
            num_mentions INTEGER,
            num_sources INTEGER,
            lat DOUBLE,
            lng DOUBLE,
            h3_cell BIGINT,
            relevance_score DOUBLE,
            summary TEXT,
            raw_event JSON,
            ingested_at TIMESTAMP DEFAULT current_timestamp
        )
    """)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS raw_gdelt (
            global_event_id VARCHAR NOT NULL PRIMARY KEY,
            raw_data JSON NOT NULL,
            fetched_at TIMESTAMP DEFAULT current_timestamp
        )
    """)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS eval_results (
            eval_id VARCHAR NOT NULL PRIMARY KEY,
            agent_id VARCHAR NOT NULL,
            prompt_version VARCHAR NOT NULL,
            eval_date DATE NOT NULL,
            direction_accuracy DOUBLE,
            magnitude_accuracy DOUBLE,
            calibration_score DOUBLE,
            num_predictions INTEGER,
            num_correct INTEGER,
            details JSON
        )
    """)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS simulation_state (
            key VARCHAR NOT NULL PRIMARY KEY,
            value JSON NOT NULL,
            updated_at TIMESTAMP DEFAULT current_timestamp
        )
    """)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS market_prices (
            ticker VARCHAR NOT NULL,
            source VARCHAR NOT NULL,
            data_environment VARCHAR NOT NULL DEFAULT 'live',
            venue_timestamp TIMESTAMP,
            quote_timestamp TIMESTAMP,
            best_yes_bid DOUBLE,
            best_yes_ask DOUBLE,
            best_no_bid DOUBLE,
            best_no_ask DOUBLE,
            yes_bid_ask_spread DOUBLE,
            no_bid_ask_spread DOUBLE,
            yes_price DOUBLE,
            no_price DOUBLE,
            derived_price_kind VARCHAR,
            volume DOUBLE,
            depth_summary JSON,
            fetched_at TIMESTAMP NOT NULL
        )
    """)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS contract_registry (
            ticker VARCHAR PRIMARY KEY,
            source VARCHAR NOT NULL,
            event_ticker VARCHAR NOT NULL,
            title VARCHAR NOT NULL,
            resolution_criteria TEXT NOT NULL,
            resolution_date TIMESTAMP,
            is_active BOOLEAN DEFAULT true,
            contract_family VARCHAR,
            expected_fee_rate DOUBLE,
            expected_slippage_rate DOUBLE,
            staleness_threshold_seconds DOUBLE,
            allow_fetched_at_fallback BOOLEAN,
            oil_move_scale_usd DOUBLE,
            last_checked TIMESTAMP,
            metadata JSON
        )
    """)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS contract_proxy_map (
            ticker VARCHAR NOT NULL,
            model_type VARCHAR NOT NULL,
            proxy_class VARCHAR NOT NULL,
            confidence_discount DOUBLE NOT NULL DEFAULT 1.0,
            invert_probability BOOLEAN DEFAULT false,
            notes TEXT,
            PRIMARY KEY (ticker, model_type)
        )
    """)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS prediction_log (
            log_id VARCHAR PRIMARY KEY,
            run_id VARCHAR NOT NULL,
            data_environment VARCHAR NOT NULL DEFAULT 'live',
            model_id VARCHAR NOT NULL,
            probability DOUBLE NOT NULL,
            direction VARCHAR NOT NULL,
            confidence DOUBLE NOT NULL,
            reasoning TEXT,
            evidence JSON,
            timeframe VARCHAR NOT NULL,
            news_context JSON,
            cascade_inputs JSON,
            created_at TIMESTAMP NOT NULL
        )
    """)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS signal_ledger (
            signal_id VARCHAR PRIMARY KEY,
            run_id VARCHAR,
            created_at TIMESTAMP NOT NULL,
            data_environment VARCHAR NOT NULL DEFAULT 'live',
            execution_environment VARCHAR NOT NULL DEFAULT 'none',
            venue VARCHAR,
            model_id VARCHAR NOT NULL,
            model_claim TEXT NOT NULL,
            model_probability DOUBLE NOT NULL,
            raw_probability DOUBLE,
            model_timeframe VARCHAR NOT NULL,
            model_reasoning TEXT,
            contract_ticker VARCHAR NOT NULL,
            contract_title VARCHAR,
            proxy_class VARCHAR NOT NULL,
            confidence_discount DOUBLE NOT NULL,
            contract_family VARCHAR,
            pricing_estimator VARCHAR,
            fair_value_yes DOUBLE,
            fair_value_no DOUBLE,
            gross_edge DOUBLE,
            expected_fee_rate DOUBLE,
            expected_slippage_rate DOUBLE,
            expected_total_cost DOUBLE,
            net_edge DOUBLE,
            quote_age_seconds DOUBLE,
            staleness_threshold_seconds DOUBLE,
            quote_is_stale BOOLEAN DEFAULT false,
            market_best_yes_bid DOUBLE,
            market_best_yes_ask DOUBLE,
            market_best_no_bid DOUBLE,
            market_best_no_ask DOUBLE,
            market_yes_spread DOUBLE,
            market_no_spread DOUBLE,
            market_yes_price DOUBLE,
            market_no_price DOUBLE,
            market_derived_yes_price DOUBLE,
            market_derived_no_price DOUBLE,
            market_derived_price_kind VARCHAR,
            market_volume DOUBLE,
            market_quote_timestamp TIMESTAMP,
            buy_yes_edge DOUBLE,
            buy_no_edge DOUBLE,
            raw_edge DOUBLE,
            effective_edge DOUBLE,
            signal VARCHAR NOT NULL,
            tradeability_status VARCHAR NOT NULL DEFAULT 'unknown',
            entry_side VARCHAR,
            entry_price DOUBLE,
            entry_price_kind VARCHAR,
            entry_price_is_executable BOOLEAN DEFAULT false,
            entry_order_id VARCHAR,
            trade_id VARCHAR,
            position_id VARCHAR,
            traded BOOLEAN DEFAULT false,
            trade_refused_reason TEXT,
            execution_status VARCHAR DEFAULT 'not_attempted',
            suggested_size VARCHAR,
            resolution_price DOUBLE,
            resolved_at TIMESTAMP,
            realized_pnl DOUBLE,
            counterfactual_pnl DOUBLE,
            model_was_correct BOOLEAN,
            proxy_was_aligned BOOLEAN
        )
    """)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS trade_orders (
            order_id VARCHAR PRIMARY KEY,
            signal_id VARCHAR,
            run_id VARCHAR,
            ticker VARCHAR NOT NULL,
            venue VARCHAR NOT NULL,
            venue_environment VARCHAR NOT NULL,
            side VARCHAR NOT NULL,
            quantity INTEGER NOT NULL,
            intended_price DOUBLE,
            intended_price_kind VARCHAR,
            executable_reference_price DOUBLE,
            order_type VARCHAR NOT NULL DEFAULT 'limit',
            status VARCHAR NOT NULL,
            venue_order_id VARCHAR,
            submitted_at TIMESTAMP NOT NULL,
            accepted_at TIMESTAMP,
            rejected_at TIMESTAMP,
            rejected_reason TEXT,
            cancelled_at TIMESTAMP,
            cancellation_reason TEXT,
            last_update_at TIMESTAMP,
            filled_quantity INTEGER DEFAULT 0,
            avg_fill_price DOUBLE,
            raw_response JSON
        )
    """)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS trade_fills (
            fill_id VARCHAR PRIMARY KEY,
            order_id VARCHAR NOT NULL,
            signal_id VARCHAR,
            position_id VARCHAR,
            ticker VARCHAR NOT NULL,
            venue VARCHAR NOT NULL,
            venue_environment VARCHAR NOT NULL,
            side VARCHAR NOT NULL,
            quantity INTEGER NOT NULL,
            fill_price DOUBLE,
            fee_amount DOUBLE,
            liquidity VARCHAR,
            filled_at TIMESTAMP NOT NULL,
            venue_fill_id VARCHAR
        )
    """)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS trade_positions (
            position_id VARCHAR PRIMARY KEY,
            signal_id VARCHAR,
            run_id VARCHAR,
            ticker VARCHAR NOT NULL,
            venue VARCHAR NOT NULL,
            venue_environment VARCHAR NOT NULL,
            side VARCHAR NOT NULL,
            quantity INTEGER NOT NULL,
            open_quantity INTEGER NOT NULL,
            entry_price DOUBLE NOT NULL,
            opened_at TIMESTAMP NOT NULL,
            exit_price DOUBLE,
            settlement_price DOUBLE,
            closed_at TIMESTAMP,
            status VARCHAR NOT NULL,
            realized_pnl DOUBLE,
            unrealized_pnl DOUBLE,
            resolution_price DOUBLE,
            resolution_source VARCHAR
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS paper_trades (
            trade_id VARCHAR PRIMARY KEY,
            ticker VARCHAR NOT NULL,
            side VARCHAR NOT NULL,
            quantity INTEGER NOT NULL,
            entry_price DOUBLE NOT NULL,
            current_price DOUBLE,
            exit_price DOUBLE,
            pnl DOUBLE DEFAULT 0,
            status VARCHAR DEFAULT 'open',
            opened_at TIMESTAMP NOT NULL,
            closed_at TIMESTAMP,
            divergence_edge DOUBLE NOT NULL,
            model_id VARCHAR NOT NULL
        )
    """)


def _migrate_legacy_tables(conn: duckdb.DuckDBPyConnection) -> None:
    if _table_exists(conn, "prediction_log"):
        _add_column_if_missing(conn, "prediction_log", "data_environment", "VARCHAR DEFAULT 'live'")

    if _table_exists(conn, "market_prices"):
        _add_column_if_missing(conn, "market_prices", "data_environment", "VARCHAR DEFAULT 'live'")
        _add_column_if_missing(conn, "market_prices", "venue_timestamp", "TIMESTAMP")
        _add_column_if_missing(conn, "market_prices", "quote_timestamp", "TIMESTAMP")
        _add_column_if_missing(conn, "market_prices", "best_yes_bid", "DOUBLE")
        _add_column_if_missing(conn, "market_prices", "best_yes_ask", "DOUBLE")
        _add_column_if_missing(conn, "market_prices", "best_no_bid", "DOUBLE")
        _add_column_if_missing(conn, "market_prices", "best_no_ask", "DOUBLE")
        _add_column_if_missing(conn, "market_prices", "yes_bid_ask_spread", "DOUBLE")
        _add_column_if_missing(conn, "market_prices", "no_bid_ask_spread", "DOUBLE")
        _add_column_if_missing(conn, "market_prices", "derived_price_kind", "VARCHAR")
        _add_column_if_missing(conn, "market_prices", "depth_summary", "JSON")

    if _table_exists(conn, "signal_ledger"):
        _add_column_if_missing(conn, "signal_ledger", "data_environment", "VARCHAR DEFAULT 'live'")
        _add_column_if_missing(conn, "signal_ledger", "execution_environment", "VARCHAR DEFAULT 'none'")
        _add_column_if_missing(conn, "signal_ledger", "venue", "VARCHAR")
        _add_column_if_missing(conn, "signal_ledger", "market_best_yes_bid", "DOUBLE")
        _add_column_if_missing(conn, "signal_ledger", "market_best_yes_ask", "DOUBLE")
        _add_column_if_missing(conn, "signal_ledger", "market_best_no_bid", "DOUBLE")
        _add_column_if_missing(conn, "signal_ledger", "market_best_no_ask", "DOUBLE")
        _add_column_if_missing(conn, "signal_ledger", "market_yes_spread", "DOUBLE")
        _add_column_if_missing(conn, "signal_ledger", "market_no_spread", "DOUBLE")
        _add_column_if_missing(conn, "signal_ledger", "market_yes_price", "DOUBLE")
        _add_column_if_missing(conn, "signal_ledger", "market_no_price", "DOUBLE")
        _add_column_if_missing(conn, "signal_ledger", "market_derived_yes_price", "DOUBLE")
        _add_column_if_missing(conn, "signal_ledger", "market_derived_no_price", "DOUBLE")
        _add_column_if_missing(conn, "signal_ledger", "market_derived_price_kind", "VARCHAR")
        _add_column_if_missing(conn, "signal_ledger", "market_quote_timestamp", "TIMESTAMP")
        _add_column_if_missing(conn, "signal_ledger", "buy_yes_edge", "DOUBLE")
        _add_column_if_missing(conn, "signal_ledger", "buy_no_edge", "DOUBLE")
        _add_column_if_missing(conn, "signal_ledger", "tradeability_status", "VARCHAR DEFAULT 'unknown'")
        _add_column_if_missing(conn, "signal_ledger", "entry_side", "VARCHAR")
        _add_column_if_missing(conn, "signal_ledger", "entry_price", "DOUBLE")
        _add_column_if_missing(conn, "signal_ledger", "entry_price_kind", "VARCHAR")
        _add_column_if_missing(conn, "signal_ledger", "entry_price_is_executable", "BOOLEAN DEFAULT false")
        _add_column_if_missing(conn, "signal_ledger", "entry_order_id", "VARCHAR")
        _add_column_if_missing(conn, "signal_ledger", "trade_id", "VARCHAR")
        _add_column_if_missing(conn, "signal_ledger", "position_id", "VARCHAR")
        _add_column_if_missing(conn, "signal_ledger", "execution_status", "VARCHAR DEFAULT 'not_attempted'")
        _add_column_if_missing(conn, "signal_ledger", "realized_pnl", "DOUBLE")
        _add_column_if_missing(conn, "signal_ledger", "counterfactual_pnl", "DOUBLE")
        _add_column_if_missing(conn, "signal_ledger", "contract_family", "VARCHAR")
        _add_column_if_missing(conn, "signal_ledger", "pricing_estimator", "VARCHAR")
        _add_column_if_missing(conn, "signal_ledger", "fair_value_yes", "DOUBLE")
        _add_column_if_missing(conn, "signal_ledger", "fair_value_no", "DOUBLE")
        _add_column_if_missing(conn, "signal_ledger", "gross_edge", "DOUBLE")
        _add_column_if_missing(conn, "signal_ledger", "expected_fee_rate", "DOUBLE")
        _add_column_if_missing(conn, "signal_ledger", "expected_slippage_rate", "DOUBLE")
        _add_column_if_missing(conn, "signal_ledger", "expected_total_cost", "DOUBLE")
        _add_column_if_missing(conn, "signal_ledger", "net_edge", "DOUBLE")
        _add_column_if_missing(conn, "signal_ledger", "quote_age_seconds", "DOUBLE")
        _add_column_if_missing(conn, "signal_ledger", "staleness_threshold_seconds", "DOUBLE")
        _add_column_if_missing(conn, "signal_ledger", "quote_is_stale", "BOOLEAN DEFAULT false")

        if _table_exists(conn, "contract_registry"):
            _add_column_if_missing(conn, "contract_registry", "contract_family", "VARCHAR")
            _add_column_if_missing(conn, "contract_registry", "expected_fee_rate", "DOUBLE")
            _add_column_if_missing(conn, "contract_registry", "expected_slippage_rate", "DOUBLE")
            _add_column_if_missing(conn, "contract_registry", "staleness_threshold_seconds", "DOUBLE")
            _add_column_if_missing(conn, "contract_registry", "allow_fetched_at_fallback", "BOOLEAN")
            _add_column_if_missing(conn, "contract_registry", "oil_move_scale_usd", "DOUBLE")

        if _column_exists(conn, "signal_ledger", "market_yes_price"):
            conn.execute("""
                UPDATE signal_ledger
                SET market_derived_yes_price = COALESCE(market_derived_yes_price, market_yes_price),
                    market_derived_no_price = COALESCE(market_derived_no_price, market_no_price),
                    market_derived_price_kind = COALESCE(market_derived_price_kind, 'legacy_snapshot')
                WHERE market_derived_yes_price IS NULL
                   OR market_derived_no_price IS NULL
                   OR market_derived_price_kind IS NULL
            """)
            conn.execute("""
                UPDATE signal_ledger
                SET market_yes_price = COALESCE(market_yes_price, market_derived_yes_price),
                    market_no_price = COALESCE(market_no_price, market_derived_no_price)
                WHERE market_yes_price IS NULL OR market_no_price IS NULL
            """)
        if _column_exists(conn, "signal_ledger", "trade_id"):
            conn.execute("""
                UPDATE signal_ledger
                SET position_id = COALESCE(position_id, trade_id)
                WHERE trade_id IS NOT NULL AND position_id IS NULL
            """)
            conn.execute("""
                UPDATE signal_ledger
                SET trade_id = COALESCE(trade_id, position_id)
                WHERE position_id IS NOT NULL AND trade_id IS NULL
            """)
        if _column_exists(conn, "signal_ledger", "realized_pnl"):
            conn.execute("""
                UPDATE signal_ledger
                SET counterfactual_pnl = COALESCE(counterfactual_pnl, realized_pnl)
                WHERE realized_pnl IS NOT NULL AND counterfactual_pnl IS NULL
            """)
            conn.execute("""
                UPDATE signal_ledger
                SET realized_pnl = COALESCE(realized_pnl, counterfactual_pnl)
                WHERE counterfactual_pnl IS NOT NULL AND realized_pnl IS NULL
            """)


def _create_views(conn: duckdb.DuckDBPyConnection) -> None:
    conn.execute("""
        CREATE OR REPLACE VIEW signal_quality_evaluation AS
        SELECT
            signal_id,
            run_id,
            created_at,
            data_environment,
            execution_environment,
            venue,
            model_id,
            contract_ticker,
            contract_title,
            proxy_class,
            model_probability,
            confidence_discount,
            buy_yes_edge,
            buy_no_edge,
            raw_edge,
            effective_edge,
            signal,
            tradeability_status,
            entry_side,
            entry_price,
            entry_price_kind,
            entry_price_is_executable,
            resolution_price,
            resolved_at,
            COALESCE(counterfactual_pnl, realized_pnl) AS counterfactual_pnl,
            model_was_correct,
            proxy_was_aligned
        FROM signal_ledger
        WHERE signal IN ('BUY_YES', 'BUY_NO')
          AND resolution_price IS NOT NULL
    """)

    conn.execute("""
        CREATE OR REPLACE VIEW trade_evaluation AS
        SELECT
            p.position_id,
            p.signal_id,
            p.run_id,
            p.ticker AS contract_ticker,
            p.venue,
            p.venue_environment,
            p.side,
            p.quantity,
            p.entry_price,
            p.exit_price,
            p.settlement_price,
            p.opened_at,
            p.closed_at,
            p.status,
            p.realized_pnl,
            p.unrealized_pnl,
            p.resolution_price,
            s.model_id,
            s.proxy_class,
            s.effective_edge
        FROM trade_positions AS p
        LEFT JOIN signal_ledger AS s
          ON s.position_id = p.position_id
    """)


def create_tables(conn: duckdb.DuckDBPyConnection) -> None:
    _create_core_tables(conn)
    _migrate_legacy_tables(conn)
    _create_views(conn)
