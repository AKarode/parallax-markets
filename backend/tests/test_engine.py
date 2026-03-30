import asyncio
import time

import pytest

from parallax.simulation.engine import SimulationEngine, SimEvent, ClockMode


@pytest.mark.asyncio
async def test_engine_processes_events_in_tick_order():
    processed = []

    async def handler(event: SimEvent):
        processed.append(event.tick)

    engine = SimulationEngine(handler=handler)
    engine.schedule(SimEvent(tick=3, event_type="test", payload={}))
    engine.schedule(SimEvent(tick=1, event_type="test", payload={}))
    engine.schedule(SimEvent(tick=2, event_type="test", payload={}))

    await engine.run_until_tick(3)
    assert processed == [1, 2, 3]


@pytest.mark.asyncio
async def test_engine_stops_at_target_tick():
    calls = []

    async def handler(event: SimEvent):
        calls.append(event.tick)

    engine = SimulationEngine(handler=handler)
    for t in range(1, 10):
        engine.schedule(SimEvent(tick=t, event_type="test", payload={}))

    await engine.run_until_tick(5)
    assert calls == [1, 2, 3, 4, 5]
    assert engine.current_tick == 5


@pytest.mark.asyncio
async def test_engine_tick_accessible():
    async def handler(event: SimEvent):
        pass

    engine = SimulationEngine(handler=handler)
    assert engine.current_tick == 0
    engine.schedule(SimEvent(tick=1, event_type="test", payload={}))
    await engine.run_until_tick(1)
    assert engine.current_tick == 1


@pytest.mark.asyncio
async def test_monotonic_counter_tiebreaking():
    """Events at the same tick are processed in insertion order (FIFO)."""
    processed = []

    async def handler(event: SimEvent):
        processed.append(event.payload.get("label"))

    engine = SimulationEngine(handler=handler)
    engine.schedule(SimEvent(tick=1, event_type="test", payload={"label": "first"}))
    engine.schedule(SimEvent(tick=1, event_type="test", payload={"label": "second"}))
    engine.schedule(SimEvent(tick=1, event_type="test", payload={"label": "third"}))

    await engine.run_until_tick(1)
    assert processed == ["first", "second", "third"]


@pytest.mark.asyncio
async def test_lazy_deletion_cancelled_events():
    """Cancelled events are skipped when popped from the queue."""
    processed = []

    async def handler(event: SimEvent):
        processed.append(event.payload.get("label"))

    engine = SimulationEngine(handler=handler)
    engine.schedule(SimEvent(tick=1, event_type="test", payload={"label": "keep"}))
    eid = engine.schedule(
        SimEvent(tick=2, event_type="test", payload={"label": "cancel_me"})
    )
    engine.schedule(SimEvent(tick=3, event_type="test", payload={"label": "also_keep"}))

    engine.cancel(eid)

    await engine.run_until_tick(3)
    assert processed == ["keep", "also_keep"]


@pytest.mark.asyncio
async def test_step_processes_single_event():
    processed = []

    async def handler(event: SimEvent):
        processed.append(event.tick)

    engine = SimulationEngine(handler=handler)
    engine.schedule(SimEvent(tick=1, event_type="test", payload={}))
    engine.schedule(SimEvent(tick=2, event_type="test", payload={}))

    result = await engine.step()
    assert result is True
    assert processed == [1]
    assert engine.current_tick == 1


@pytest.mark.asyncio
async def test_step_returns_false_on_empty():
    async def handler(event: SimEvent):
        pass

    engine = SimulationEngine(handler=handler)
    result = await engine.step()
    assert result is False


@pytest.mark.asyncio
async def test_pending_count():
    async def handler(event: SimEvent):
        pass

    engine = SimulationEngine(handler=handler)
    assert engine.pending_count() == 0
    engine.schedule(SimEvent(tick=1, event_type="test", payload={}))
    engine.schedule(SimEvent(tick=2, event_type="test", payload={}))
    assert engine.pending_count() == 2

    await engine.step()
    assert engine.pending_count() == 1


@pytest.mark.asyncio
async def test_replay_mode_no_sleep():
    """Replay mode should process events without any real-time delay."""
    processed = []

    async def handler(event: SimEvent):
        processed.append(event.tick)

    engine = SimulationEngine(handler=handler, clock_mode=ClockMode.REPLAY)
    for t in range(1, 20):
        engine.schedule(SimEvent(tick=t, event_type="test", payload={}))

    start = time.monotonic()
    await engine.run_until_tick(19)
    elapsed = time.monotonic() - start

    assert len(processed) == 19
    # Replay should be near-instant (well under 1 second for 19 events)
    assert elapsed < 1.0


@pytest.mark.asyncio
async def test_live_mode_wall_clock_anchoring():
    """Live mode uses wall-clock anchoring, not asyncio.sleep drift."""
    processed = []

    async def handler(event: SimEvent):
        processed.append(event.tick)

    # Very short tick duration for testing (10ms)
    engine = SimulationEngine(
        handler=handler,
        clock_mode=ClockMode.LIVE,
        tick_duration_seconds=0.01,
    )
    for t in range(1, 4):
        engine.schedule(SimEvent(tick=t, event_type="test", payload={}))

    start = time.monotonic()
    await engine.run_until_tick(3)
    elapsed = time.monotonic() - start

    assert processed == [1, 2, 3]
    # Should take roughly 3 ticks * 0.01s, not much more
    assert elapsed < 0.5  # generous upper bound


@pytest.mark.asyncio
async def test_handler_can_schedule_new_events():
    """Handler should be able to schedule follow-up events during processing."""
    processed = []

    async def handler(event: SimEvent):
        processed.append(event.payload.get("label"))
        if event.payload.get("label") == "trigger":
            event._engine_ref.schedule(
                SimEvent(tick=event.tick + 1, event_type="test", payload={"label": "follow_up"})
            )

    engine = SimulationEngine(handler=handler)
    engine.schedule(SimEvent(tick=1, event_type="test", payload={"label": "trigger"}))

    await engine.run_until_tick(5)
    assert "trigger" in processed
    assert "follow_up" in processed


@pytest.mark.asyncio
async def test_cancel_nonexistent_event_is_safe():
    """Cancelling a non-existent event ID should not raise."""
    async def handler(event: SimEvent):
        pass

    engine = SimulationEngine(handler=handler)
    engine.cancel(9999)  # Should not raise
