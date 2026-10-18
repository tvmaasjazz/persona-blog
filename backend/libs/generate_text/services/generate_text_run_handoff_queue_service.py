from redis.asyncio import Redis

from libs.generate_text.constants import RUN_HANDOFF_QUEUE_KEY


class GenerateTextRunHandoffQueueService:
    """Sends and receives handed-off run ids on a Redis list."""

    def __init__(self, redis_client: Redis) -> None:
        self._redis_client = redis_client

    async def push_run(self, run_id: int) -> None:
        await self._redis_client.rpush(RUN_HANDOFF_QUEUE_KEY, run_id)

    async def wait_for_run(self, timeout_seconds: float) -> int | None:
        """Returns the next handed-off run id, or None when none arrives in time."""
        pop_result = await self._redis_client.blpop([RUN_HANDOFF_QUEUE_KEY], timeout_seconds)
        if pop_result is None:
            return None
        _, run_id = pop_result
        return int(run_id)
