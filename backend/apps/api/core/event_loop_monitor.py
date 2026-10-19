import asyncio

import structlog

logger = structlog.get_logger(__name__)

EVENT_LOOP_SAMPLE_SECONDS = 0.1
EVENT_LOOP_LAG_WARNING_SECONDS = 0.05
MILLISECONDS_PER_SECOND = 1000


async def monitor_event_loop_lag(
    sample_seconds: float = EVENT_LOOP_SAMPLE_SECONDS,
    warning_seconds: float = EVENT_LOOP_LAG_WARNING_SECONDS,
) -> None:
    """Logs a warning when a fixed sleep wakes late, which means the loop was blocked."""
    event_loop = asyncio.get_running_loop()
    while True:
        sleep_started_at = event_loop.time()
        await asyncio.sleep(sample_seconds)
        lag_seconds = event_loop.time() - sleep_started_at - sample_seconds
        if lag_seconds > warning_seconds:
            logger.warning("event_loop_lag", lag_ms=round(lag_seconds * MILLISECONDS_PER_SECOND))
