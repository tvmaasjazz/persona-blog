import asyncio
from collections.abc import Callable

import structlog

from libs.generate_text.services import GenerateTextService

logger = structlog.get_logger(__name__)


async def sweep_expired_runs(
    build_generate_text_service: Callable[[], GenerateTextService],
    sweep_interval_seconds: float,
) -> None:
    """Sweeps once at startup, then every interval, picking up runs whose lease has
    expired until none are left. Runs until cancelled. A failed sweep is logged and the
    next one tries again."""
    while True:
        try:
            generate_text_service = build_generate_text_service()
            is_run_picked_up = True
            while is_run_picked_up:
                is_run_picked_up = await generate_text_service.pick_up_expired_run()
        except Exception:
            logger.exception("run_sweep_failed")
        await asyncio.sleep(sweep_interval_seconds)
