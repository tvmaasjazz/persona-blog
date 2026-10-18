import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import datetime
from typing import Any

import structlog

from libs.core.services import BackgroundJobService
from libs.core.utils import DateTimeUtils
from libs.generate_text.results import ClaimExpiredGenerateTextRunResult
from libs.generate_text.services.generate_text_run_handoff_queue_service import (
    GenerateTextRunHandoffQueueService,
)
from libs.generate_text.services.generate_text_run_service import GenerateTextRunService
from libs.generate_text.settings import GenerateTextSettings

logger = structlog.get_logger(__name__)


class GenerateTextRunLeaseService:
    """Takes, renews and releases this process's leases on generate-text runs."""

    def __init__(
        self,
        run_service: GenerateTextRunService,
        handoff_queue_service: GenerateTextRunHandoffQueueService,
        background_job_service: BackgroundJobService,
        generate_text_settings: GenerateTextSettings,
    ) -> None:
        self._run_service = run_service
        self._handoff_queue_service = handoff_queue_service
        self._background_job_service = background_job_service
        self._generate_text_settings = generate_text_settings

    @property
    def worker_id(self) -> str:
        return self._background_job_service.worker_id

    def build_lease_expires_at(self) -> datetime:
        return DateTimeUtils.seconds_from_now(self._generate_text_settings.lease_seconds)

    async def claim_paused_run(self, run_id: int) -> bool:
        return await self._run_service.claim_paused_run(
            run_id, self.worker_id, self.build_lease_expires_at()
        )

    async def claim_expired_run(
        self, run_id: int | None = None
    ) -> ClaimExpiredGenerateTextRunResult | None:
        return await self._run_service.claim_expired_run(
            self.worker_id, self.build_lease_expires_at(), run_id
        )

    async def hand_off_run(self, run_id: int) -> None:
        """Releases the run's lease and wakes a live process to pick the run up."""
        # Release the lease, sending nothing when another process owns the run now
        is_released = await self._run_service.release_lease(run_id, self.worker_id)
        if not is_released:
            return

        # Wake a listener, leaving a failed send to the pickup loop
        try:
            await self._handoff_queue_service.push_run(run_id)
        except Exception:
            logger.warning("run_handoff_send_failed", run_id=run_id, exc_info=True)

    @asynccontextmanager
    async def keep_lease_alive(self, run_id: int) -> AsyncIterator[None]:
        """Renews the run's lease while the block runs, and hands the run off if the block
        is cancelled."""
        job_task = asyncio.current_task()
        heartbeat_task = asyncio.create_task(self._renew_lease_until_lost(run_id, job_task))
        try:
            yield
        except asyncio.CancelledError:
            await self.hand_off_run(run_id)
            raise
        finally:
            heartbeat_task.cancel()
            await asyncio.gather(heartbeat_task, return_exceptions=True)

    async def _renew_lease_until_lost(
        self, run_id: int, job_task: asyncio.Task[Any] | None
    ) -> None:
        """Renews the lease every heartbeat, and cancels the job if another process owns
        the run now."""
        while True:
            await asyncio.sleep(self._generate_text_settings.lease_heartbeat_seconds)

            # Renew the lease, trying again next beat if the write fails
            try:
                is_renewed = await self._run_service.renew_lease(
                    run_id, self.worker_id, self.build_lease_expires_at()
                )
            except Exception:
                logger.warning("lease_renewal_failed", run_id=run_id, exc_info=True)
                continue

            # Cancel the job so two processes never run the same run
            if not is_renewed:
                logger.warning("lease_lost", run_id=run_id, worker_id=self.worker_id)
                if job_task is not None:
                    job_task.cancel()
                return
