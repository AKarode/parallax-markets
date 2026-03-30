"""Discrete Event Simulation (DES) engine.

Key design decisions:
- Event queue uses heapq with (tick, monotonic_counter, event) tuples
  to prevent TypeError on tie-breaking when events share the same tick.
- Clock modes:
  - LIVE: wall-clock anchored via `start_time + tick * tick_duration`
    (NOT asyncio.sleep which drifts).
  - REPLAY: instant playback from recorded deltas, no real-time delay.
- Lazy deletion: cancelled events are marked and skipped when popped.
"""

import asyncio
import heapq
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Awaitable, Callable


class ClockMode(Enum):
    LIVE = "live"
    REPLAY = "replay"


@dataclass
class SimEvent:
    """A simulation event to be processed at a given tick."""

    tick: int
    event_type: str
    payload: dict[str, Any] = field(default_factory=dict)
    source: str | None = None
    # Set by the engine when scheduling; gives handler access back to engine
    _engine_ref: Any = field(default=None, repr=False)


class SimulationEngine:
    """Discrete event simulation with priority queue and async event handler.

    Events are ordered by (tick, insertion_order) to guarantee FIFO
    within the same tick.
    """

    def __init__(
        self,
        handler: Callable[[SimEvent], Awaitable[None]],
        clock_mode: ClockMode = ClockMode.REPLAY,
        tick_duration_seconds: float = 900.0,  # 15 minutes default
    ) -> None:
        self._handler = handler
        self._clock_mode = clock_mode
        self._tick_duration = tick_duration_seconds

        # Priority queue: (tick, sequence_id, event)
        self._queue: list[tuple[int, int, SimEvent]] = []
        self._sequence: int = 0
        self._current_tick: int = 0

        # Lazy deletion: set of cancelled sequence IDs
        self._cancelled: set[int] = set()

        # Wall-clock anchor for LIVE mode
        self._start_time: float | None = None

    @property
    def current_tick(self) -> int:
        return self._current_tick

    def schedule(self, event: SimEvent) -> int:
        """Schedule an event. Returns a sequence ID that can be used to cancel it."""
        seq = self._sequence
        self._sequence += 1
        event._engine_ref = self
        heapq.heappush(self._queue, (event.tick, seq, event))
        return seq

    def cancel(self, sequence_id: int) -> None:
        """Mark an event as cancelled. It will be skipped when popped."""
        self._cancelled.add(sequence_id)

    def pending_count(self) -> int:
        """Number of events in the queue (including cancelled ones)."""
        return len(self._queue)

    async def run_until_tick(self, target_tick: int) -> None:
        """Process all events up to and including target_tick."""
        if self._clock_mode == ClockMode.LIVE:
            self._start_time = time.monotonic()

        while self._queue:
            tick, seq, event = self._queue[0]
            if tick > target_tick:
                break

            heapq.heappop(self._queue)

            # Lazy deletion: skip cancelled events
            if seq in self._cancelled:
                self._cancelled.discard(seq)
                continue

            # Wall-clock anchoring for LIVE mode
            if self._clock_mode == ClockMode.LIVE and self._start_time is not None:
                target_time = self._start_time + tick * self._tick_duration
                now = time.monotonic()
                wait = target_time - now
                if wait > 0:
                    await asyncio.sleep(wait)

            self._current_tick = event.tick
            await self._handler(event)

    async def step(self) -> bool:
        """Process the next event. Returns False if queue is empty."""
        while self._queue:
            tick, seq, event = heapq.heappop(self._queue)

            # Skip cancelled
            if seq in self._cancelled:
                self._cancelled.discard(seq)
                continue

            self._current_tick = event.tick
            event._engine_ref = self
            await self._handler(event)
            return True

        return False
