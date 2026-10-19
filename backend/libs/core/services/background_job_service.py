import asyncio
from collections.abc import Coroutine
from typing import Any

import structlog

logger = structlog.get_logger(__name__)


class BackgroundJobService:
    """Runs jobs as asyncio tasks, holding a strong reference since Python keeps only a weak one."""

    def __init__(self, worker_id: str) -> None:
        self._worker_id = worker_id
        self._is_stopping = False
        self._running_job_tasks: set[asyncio.Task[Any]] = set()

    @property
    def worker_id(self) -> str:
        """The id of the worker process this service runs jobs for."""
        return self._worker_id

    @property
    def is_stopping(self) -> bool:
        """True once request_stop() has been called, so jobs should take on no new work."""
        return self._is_stopping

    def start(self, job_coroutine: Coroutine[Any, Any, object]) -> None:
        """Runs the coroutine as a task without waiting; a failure is logged, never raised."""
        job_task = asyncio.create_task(job_coroutine)
        self._running_job_tasks.add(job_task)
        job_task.add_done_callback(self._handle_job_done)

    def request_stop(self) -> None:
        """Tells running jobs to stop at their next safe point."""
        self._is_stopping = True

    async def drain(self, timeout_seconds: float) -> None:
        """Waits for running jobs up to the timeout, then cancels the rest."""
        running_job_tasks = set(self._running_job_tasks)
        if not running_job_tasks:
            return

        _, pending_job_tasks = await asyncio.wait(running_job_tasks, timeout=timeout_seconds)
        for pending_job_task in pending_job_tasks:
            pending_job_task.cancel()
        if pending_job_tasks:
            await asyncio.gather(*pending_job_tasks, return_exceptions=True)

    def _handle_job_done(self, finished_job_task: asyncio.Task[Any]) -> None:
        self._running_job_tasks.discard(finished_job_task)
        if finished_job_task.cancelled():
            return

        job_exception = finished_job_task.exception()
        if job_exception is not None:
            logger.error("background_job_failed", exc_info=job_exception)
