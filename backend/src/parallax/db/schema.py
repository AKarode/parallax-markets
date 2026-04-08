import duckdb


def create_tables(conn: duckdb.DuckDBPyConnection) -> None:
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

    conn.execute("""
        CREATE TABLE IF NOT EXISTS market_prices (
            ticker VARCHAR NOT NULL,
            source VARCHAR NOT NULL,
            yes_price DOUBLE,
            no_price DOUBLE,
            volume DOUBLE,
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
            model_id VARCHAR NOT NULL,
            model_claim TEXT NOT NULL,
            model_probability DOUBLE NOT NULL,
            model_timeframe VARCHAR NOT NULL,
            model_reasoning TEXT,
            contract_ticker VARCHAR NOT NULL,
            contract_title VARCHAR,
            proxy_class VARCHAR NOT NULL,
            confidence_discount DOUBLE NOT NULL,
            market_yes_price DOUBLE NOT NULL,
            market_no_price DOUBLE NOT NULL,
            market_volume DOUBLE,
            raw_edge DOUBLE NOT NULL,
            effective_edge DOUBLE NOT NULL,
            signal VARCHAR NOT NULL,
            trade_id VARCHAR,
            traded BOOLEAN DEFAULT false,
            trade_refused_reason TEXT,
            resolution_price DOUBLE,
            resolved_at TIMESTAMP,
            realized_pnl DOUBLE,
            model_was_correct BOOLEAN,
            proxy_was_aligned BOOLEAN
        )
    """)
