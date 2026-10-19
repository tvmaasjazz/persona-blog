import asyncio

import structlog

from libs.core.services import BackgroundJobService
from libs.generate_text.constants import (
    RUN_NEVER_STARTED_ERROR_CODE,
    RUN_NEVER_STARTED_ERROR_MESSAGE,
    RUN_PICKED_UP_TOO_OFTEN_ERROR_CODE,
    RUN_PICKED_UP_TOO_OFTEN_ERROR_MESSAGE,
)
from libs.generate_text.results import ClaimExpiredGenerateTextRunResult
from libs.generate_text.services.generate_text_run_handoff_queue_service import (
    GenerateTextRunHandoffQueueService,
)
from libs.generate_text.services.generate_text_run_lease_service import (
    GenerateTextRunLeaseService,
)
from libs.generate_text.services.generate_text_run_service import GenerateTextRunService
from libs.generate_text.services.generate_text_service import GenerateTextService
from libs.generate_text.settings import GenerateTextSettings
from libs.generate_text.types import GenerateTextRunStatusType

logger = structlog.get_logger(__name__)


class GenerateTextRunPickupService:
    """Picks up generate-text runs that another process stopped or abandoned."""

    def __init__(
        self,
        generate_text_service: GenerateTextService,
        lease_service: GenerateTextRunLeaseService,
        handoff_queue_service: GenerateTextRunHandoffQueueService,
        run_service: GenerateTextRunService,
        background_job_service: BackgroundJobService,
        generate_text_settings: GenerateTextSettings,
    ) -> None:
        self._generate_text_service = generate_text_service
        self._lease_service = lease_service
        self._handoff_queue_service = handoff_queue_service
        self._run_service = run_service
        self._background_job_service = background_job_service
        self._generate_text_settings = generate_text_settings

    async def pick_up_expired_runs(self) -> None:
        """Picks up expired runs at startup and every pickup interval, until cancelled."""
        while True:
            try:
                is_run_picked_up = True
                while is_run_picked_up:
                    is_run_picked_up = await self.pick_up_next_expired_run()
            except Exception:
                # A failed pickup is logged, and the next one tries again
                logger.exception("run_pickup_failed")
            await asyncio.sleep(self._generate_text_settings.run_pickup_interval_seconds)

    async def pick_up_handed_off_runs(self) -> None:
        """Picks up a run as soon as another process hands one off, until cancelled."""
        wait_seconds = self._generate_text_settings.run_handoff_wait_seconds
        while True:
            try:
                # Wait for a handoff, then pick up that run
                handed_off_run_id = await self._handoff_queue_service.wait_for_run(wait_seconds)
                if handed_off_run_id is not None:
                    await self.pick_up_handed_off_run(handed_off_run_id)
            except Exception:
                # Wait before retrying so a Redis outage doesn't spin the loop
                logger.exception("run_handoff_pickup_failed")
                await asyncio.sleep(wait_seconds)

    async def pick_up_handed_off_run(self, run_id: int) -> None:
        """Claims the handed-off run and fails or continues it."""
        # A stopping process takes on no new runs
        if self._background_job_service.is_stopping:
            return

        # Claim the run; a duplicate or stale message may name one already taken
        claim_expired_run_result = await self._lease_service.claim_expired_run(run_id)
        if claim_expired_run_result is None:
            return

        await self._fail_or_continue_run(claim_expired_run_result)

    async def pick_up_next_expired_run(self) -> bool:
        """Claims one expired run and fails or continues it; returns whether it claimed one."""
        # A stopping process takes on no new runs
        if self._background_job_service.is_stopping:
            return False

        # Claim the run whose lease expired longest ago
        claim_expired_run_result = await self._lease_service.claim_expired_run()
        if claim_expired_run_result is None:
            return False

        await self._fail_or_continue_run(claim_expired_run_result)
        return True

    async def _fail_or_continue_run(
        self, claim_expired_run_result: ClaimExpiredGenerateTextRunResult
    ) -> None:
        """Fails a claimed run that can't be continued, and continues the rest."""
        # Fail a run whose job never started, since it has no checkpoint to continue from
        run_id = claim_expired_run_result.id
        if claim_expired_run_result.status is GenerateTextRunStatusType.PENDING:
            await self._run_service.fail_run(
                run_id, RUN_NEVER_STARTED_ERROR_CODE, RUN_NEVER_STARTED_ERROR_MESSAGE
            )
            return

        # Fail a run that keeps being interrupted
        if claim_expired_run_result.pickup_count > self._generate_text_settings.max_run_pickups:
            await self._run_service.fail_run(
                run_id, RUN_PICKED_UP_TOO_OFTEN_ERROR_CODE, RUN_PICKED_UP_TOO_OFTEN_ERROR_MESSAGE
            )
            return

        # Continue the run from its last checkpoint
        await self._generate_text_service.continue_generate_text(claim_expired_run_result)
