from parallax.db.schema import create_tables


def test_create_tables_creates_all_expected_tables(db):
    create_tables(db)
    tables = db.execute("SHOW TABLES").fetchall()
    table_names = {t[0] for t in tables}
    expected = {
        "world_state_delta",
        "world_state_snapshot",
        "agent_memory",
        "agent_prompts",
        "decisions",
        "predictions",
        "curated_events",
        "raw_gdelt",
        "eval_results",
        "simulation_state",
        "paper_trades",
        "market_prices",
        "contract_registry",
        "contract_proxy_map",
    }
    assert expected == table_names


def test_world_state_delta_columns(db):
    create_tables(db)
    cols = db.execute(
        "SELECT column_name FROM information_schema.columns "
        "WHERE table_name = 'world_state_delta' ORDER BY ordinal_position"
    ).fetchall()
    col_names = [c[0] for c in cols]
    assert col_names == ["cell_id", "tick", "influence", "threat_level", "flow", "status", "changed_at"]


def test_simulation_state_starts_empty(db):
    create_tables(db)
    rows = db.execute("SELECT * FROM simulation_state").fetchall()
    assert rows == []
