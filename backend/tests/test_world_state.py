from parallax.simulation.world_state import WorldState


def test_initial_state_empty():
    ws = WorldState()
    assert ws.get_cell(123456) is None
    assert ws.tick == 0


def test_update_cell_tracks_delta():
    ws = WorldState()
    ws.update_cell(123456, influence="iran", threat_level=0.5, status="patrolled")
    ws.advance_tick()

    cell = ws.get_cell(123456)
    assert cell["influence"] == "iran"
    assert cell["threat_level"] == 0.5
    assert cell["status"] == "patrolled"

    deltas = ws.flush_deltas()
    assert len(deltas) == 1
    assert deltas[0]["cell_id"] == 123456
    assert deltas[0]["tick"] == 1


def test_unchanged_cells_not_in_delta():
    ws = WorldState()
    ws.update_cell(100, influence="iran", status="open")
    ws.update_cell(200, influence="usa", status="open")
    ws.advance_tick()
    ws.flush_deltas()  # Clear first tick deltas

    # Only update cell 100 on tick 2
    ws.update_cell(100, threat_level=0.8)
    ws.advance_tick()
    deltas = ws.flush_deltas()

    assert len(deltas) == 1
    assert deltas[0]["cell_id"] == 100
    assert deltas[0]["threat_level"] == 0.8


def test_snapshot_returns_all_cells():
    ws = WorldState()
    ws.update_cell(100, influence="iran", status="open")
    ws.update_cell(200, influence="usa", status="open")
    ws.advance_tick()

    snapshot = ws.snapshot()
    assert len(snapshot) == 2
    cell_ids = {s["cell_id"] for s in snapshot}
    assert cell_ids == {100, 200}


def test_load_from_snapshot():
    ws = WorldState()
    snapshot_data = [
        {"cell_id": 100, "influence": "iran", "threat_level": 0.5, "flow": 1000.0, "status": "open"},
        {"cell_id": 200, "influence": "usa", "threat_level": 0.1, "flow": 2000.0, "status": "open"},
    ]
    ws.load_snapshot(snapshot_data, tick=50)
    assert ws.tick == 50
    assert ws.get_cell(100)["influence"] == "iran"
    assert ws.get_cell(200)["flow"] == 2000.0
