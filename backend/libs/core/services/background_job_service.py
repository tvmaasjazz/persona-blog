import asyncio
from collections.abc import Coroutine
from typing import Any

import structlog

logger = structlog.get_logger(__name__)


class BackgroundTaskService:
    """Runs coroutines as asyncio tasks that outlive the request that started them.
    Python only keeps a weak reference to a running task, so this holds a strong one until
    the task is done."""

    def __init__(self) -> None:
        self._running_tasks: set[asyncio.Task[Any]] = set()

    def start(self, background_coroutine: Coroutine[Any, Any, object]) -> None:
        background_task = asyncio.create_task(background_coroutine)
        self._running_tasks.add(background_task)
        background_task.add_done_callback(self._handle_task_done)

    async def drain(self, timeout_seconds: float) -> None:
        """Waits for the running tasks up to the timeout, then cancels what is left and
        waits for the cancellations to finish."""
        running_tasks = set(self._running_tasks)
        if not running_tasks:
            return

        _, pending_tasks = await asyncio.wait(running_tasks, timeout=timeout_seconds)
        for pending_task in pending_tasks:
            pending_task.cancel()
        if pending_tasks:
            await asyncio.gather(*pending_tasks, return_exceptions=True)

    def _handle_task_done(self, finished_task: asyncio.Task[Any]) -> None:
        self._running_tasks.discard(finished_task)
        if finished_task.cancelled():
            return

        task_exception = finished_task.exception()
        if task_exception is not None:
            logger.error("background_task_failed", exc_info=task_exception)
