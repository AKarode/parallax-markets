import asyncio
import logging
from dataclasses import dataclass

import duckdb

logger = logging.getLogger(__name__)


@dataclass
class WriteOp:
    sql: str
    params: list | None = None


class DbWriter:
    """Single-writer queue for DuckDB. All writes go through this."""

    def __init__(self, conn: duckdb.DuckDBPyConnection) -> None:
        self._conn = conn
        self._queue: asyncio.Queue[WriteOp | None] = asyncio.Queue()
        self._running = False

    async def enqueue(self, sql: str, params: list | None = None) -> None:
        await self._queue.put(WriteOp(sql=sql, params=params))

    def queue_depth(self) -> int:
        return self._queue.qsize()

    def stop(self) -> None:
        self._running = False
        self._queue.put_nowait(None)  # Sentinel to unblock

    async def run(self) -> None:
        self._running = True
        while self._running:
            op = await self._queue.get()
            if op is None:
                break
            try:
                if op.params:
                    self._conn.execute(op.sql, op.params)
                else:
                    self._conn.execute(op.sql)
            except Exception:
                logger.exception("DB write failed: %s", op.sql[:100])
            self._queue.task_done()
