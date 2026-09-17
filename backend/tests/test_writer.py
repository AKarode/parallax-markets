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


@pytest.mark.asyncio
async def test_writer_survives_failed_write(db):
    """Regression: an invalid SQL should NOT crash the writer or block subsequent writes."""
    writer = DbWriter(db)
    task = asyncio.create_task(writer.run())

    # First: a broken write (table doesn't exist)
    await writer.enqueue(
        "INSERT INTO nonexistent_table_xyz (col) VALUES (?)",
        ["bad"],
    )
    # Then: a valid write that must still succeed
    await writer.enqueue(
        "INSERT INTO simulation_state (key, value) VALUES (?, ?)",
        ["after_failure", '"1"'],
    )

    await asyncio.sleep(0.1)
    writer.stop()
    await task

    rows = db.execute(
        "SELECT key FROM simulation_state WHERE key = 'after_failure'"
    ).fetchall()
    assert len(rows) == 1, "writer must continue processing after a failed write"


@pytest.mark.asyncio
async def test_writer_rolls_back_failed_write(db):
    """Failed writes must not leave partial data committed."""
    writer = DbWriter(db)
    task = asyncio.create_task(writer.run())

    # Use a constraint-violating insert if possible — here use SQL syntax that begins
    # but cannot complete cleanly. Insert a single bad statement.
    await writer.enqueue(
        "INSERT INTO simulation_state (nonexistent_column) VALUES (?)",
        ["x"],
    )
    await asyncio.sleep(0.05)
    writer.stop()
    await task

    # Nothing should have been written
    rows = db.execute("SELECT count(*) FROM simulation_state").fetchone()
    assert rows[0] == 0


@pytest.mark.asyncio
async def test_writer_task_done_called_on_failure(db):
    """A failing write must still mark the queue item done so join() doesn't hang."""
    writer = DbWriter(db)
    task = asyncio.create_task(writer.run())

    await writer.enqueue(
        "INSERT INTO nonexistent_table (col) VALUES (?)",
        ["x"],
    )

    # If task_done isn't called, queue.join() will hang forever.
    try:
        await asyncio.wait_for(writer._queue.join(), timeout=1.0)
    finally:
        writer.stop()
        await task
