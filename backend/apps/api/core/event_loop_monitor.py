import asyncio

import structlog

logger = structlog.get_logger(__name__)

EVENT_LOOP_SAMPLE_SECONDS = 0.1
EVENT_LOOP_LAG_WARNING_SECONDS = 0.05
MILLISECONDS_PER_SECOND = 1000


async def monitor_event_loop_lag() -> None:
    """Sleeps a fixed interval and measures how late it wakes: a blocked loop wakes late.
    Runs until cancelled."""
    event_loop = asyncio.get_running_loop()
    while True:
        sleep_started_at = event_loop.time()
        await asyncio.sleep(EVENT_LOOP_SAMPLE_SECONDS)
        lag_seconds = event_loop.time() - sleep_started_at - EVENT_LOOP_SAMPLE_SECONDS
        if lag_seconds > EVENT_LOOP_LAG_WARNING_SECONDS:
            logger.warning("event_loop_lag", lag_ms=round(lag_seconds * MILLISECONDS_PER_SECOND))
