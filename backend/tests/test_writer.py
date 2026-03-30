import asyncio
import duckdb
import pytest
from parallax.db.schema import create_tables
from parallax.db.writer import DbWriter


@pytest.fixture
def db():
    conn = duckdb.connect(":memory:")
    conn.execute("INSTALL spatial; LOAD spatial;")
    conn.execute("INSTALL h3 FROM community; LOAD h3;")
    create_tables(conn)
    yield conn
    conn.close()


@pytest.mark.asyncio
async def test_writer_processes_single_write(db):
    writer = DbWriter(db)
    task = asyncio.create_task(writer.run())

    await writer.enqueue(
        "INSERT INTO simulation_state (key, value) VALUES (?, ?)",
        ["current_tick", '"0"'],
    )

    # Give writer time to process
    await asyncio.sleep(0.05)
    writer.stop()
    await task

    rows = db.execute("SELECT key, value FROM simulation_state").fetchall()
    assert len(rows) == 1
    assert rows[0][0] == "current_tick"


@pytest.mark.asyncio
async def test_writer_processes_batch_of_writes(db):
    writer = DbWriter(db)
    task = asyncio.create_task(writer.run())

    for i in range(10):
        await writer.enqueue(
            "INSERT INTO world_state_delta (cell_id, tick, status) VALUES (?, ?, ?)",
            [i, 1, "open"],
        )
    await asyncio.sleep(0.1)
    writer.stop()
    await task

    count = db.execute("SELECT count(*) FROM world_state_delta").fetchone()[0]
    assert count == 10


@pytest.mark.asyncio
async def test_writer_queue_depth_reported(db):
    writer = DbWriter(db)
    # Don't start the runner — just enqueue
    await writer.enqueue("INSERT INTO simulation_state (key, value) VALUES (?, ?)", ["a", '"1"'])
    assert writer.queue_depth() == 1
