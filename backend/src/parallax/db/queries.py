import duckdb


def get_current_tick(conn: duckdb.DuckDBPyConnection) -> int:
    row = conn.execute(
        "SELECT value FROM simulation_state WHERE key = 'current_tick'"
    ).fetchone()
    if row is None:
        return 0
    return int(row[0].strip('"'))


def get_latest_snapshot_tick(conn: duckdb.DuckDBPyConnection) -> int | None:
    row = conn.execute(
        "SELECT MAX(tick) FROM world_state_snapshot"
    ).fetchone()
    return row[0] if row and row[0] is not None else None


def get_world_state_at_tick(
    conn: duckdb.DuckDBPyConnection, target_tick: int
) -> list[dict]:
    """Reconstruct world state at a given tick from nearest snapshot + deltas."""
    snapshot_tick = conn.execute(
        "SELECT MAX(tick) FROM world_state_snapshot WHERE tick <= ?",
        [target_tick],
    ).fetchone()[0]

    if snapshot_tick is None:
        return []

    # Start from snapshot
    cells = {}
    rows = conn.execute(
        "SELECT cell_id, influence, threat_level, flow, status "
        "FROM world_state_snapshot WHERE tick = ?",
        [snapshot_tick],
    ).fetchall()
    for r in rows:
        cells[r[0]] = {
            "cell_id": r[0],
            "influence": r[1],
            "threat_level": r[2],
            "flow": r[3],
            "status": r[4],
        }

    # Apply deltas forward
    deltas = conn.execute(
        "SELECT cell_id, influence, threat_level, flow, status "
        "FROM world_state_delta "
        "WHERE tick > ? AND tick <= ? ORDER BY tick",
        [snapshot_tick, target_tick],
    ).fetchall()
    for d in deltas:
        cell_id = d[0]
        if cell_id not in cells:
            cells[cell_id] = {"cell_id": cell_id}
        if d[1] is not None:
            cells[cell_id]["influence"] = d[1]
        if d[2] is not None:
            cells[cell_id]["threat_level"] = d[2]
        if d[3] is not None:
            cells[cell_id]["flow"] = d[3]
        if d[4] is not None:
            cells[cell_id]["status"] = d[4]

    return list(cells.values())


def get_recent_decisions(
    conn: duckdb.DuckDBPyConnection, limit: int = 50
) -> list[dict]:
    rows = conn.execute(
        "SELECT decision_id, agent_id, tick, action_type, description, "
        "confidence, created_at "
        "FROM decisions ORDER BY created_at DESC LIMIT ?",
        [limit],
    ).fetchall()
    return [
        {
            "decision_id": r[0],
            "agent_id": r[1],
            "tick": r[2],
            "action_type": r[3],
            "description": r[4],
            "confidence": r[5],
            "created_at": str(r[6]),
        }
        for r in rows
    ]
