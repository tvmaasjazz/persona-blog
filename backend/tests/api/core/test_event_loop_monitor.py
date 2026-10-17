import asyncio
from collections.abc import AsyncIterator

import pytest
import structlog.testing

from apps.api.core.event_loop_monitor import monitor_event_loop_lag


@pytest.fixture
async def event_loop_monitor_task() -> AsyncIterator[asyncio.Task[None]]:
    # A short sample and a generous threshold, so only a deliberate block trips it.
    monitor_task = asyncio.create_task(
        monitor_event_loop_lag(sample_seconds=0.01, warning_seconds=0.2)
    )
    yield monitor_task
    monitor_task.cancel()
    await asyncio.gather(monitor_task, return_exceptions=True)


def _block_event_loop(blocked_seconds: float) -> None:
    event_loop = asyncio.get_running_loop()
    unblock_at = event_loop.time() + blocked_seconds
    while event_loop.time() < unblock_at:
        pass


@pytest.mark.usefixtures("event_loop_monitor_task")
async def test_monitor_event_loop_lag_blocked_loop_logs_event_loop_lag() -> None:
    with structlog.testing.capture_logs() as captured_log_events:
        await asyncio.sleep(0)
        _block_event_loop(0.4)
        for _ in range(3):
            await asyncio.sleep(0)

    event_loop_lag_events = [
        log_event for log_event in captured_log_events if log_event["event"] == "event_loop_lag"
    ]
    assert len(event_loop_lag_events) == 1
    assert event_loop_lag_events[0]["log_level"] == "warning"
    assert 300 <= event_loop_lag_events[0]["lag_ms"] <= 1000


@pytest.mark.usefixtures("event_loop_monitor_task")
async def test_monitor_event_loop_lag_unblocked_loop_logs_nothing() -> None:
    with structlog.testing.capture_logs() as captured_log_events:
        await asyncio.sleep(0.05)

    event_loop_lag_events = [
        log_event for log_event in captured_log_events if log_event["event"] == "event_loop_lag"
    ]
    assert event_loop_lag_events == []
