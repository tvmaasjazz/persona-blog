import structlog
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from libs.generate_text.services.generate_text_run_service import GenerateTextRunService

logger = structlog.get_logger(__name__)


async def fail_user_unfinished_runs(
    db_session_factory: async_sessionmaker[AsyncSession],
    user_id: int,
    error_code: str,
    error_message: str,
) -> None:
    """Fails every unfinished run of the user, after the change that called for it has
    committed; a run that can't be failed is logged and the rest still are."""
    generate_text_run_service = GenerateTextRunService(db_session_factory=db_session_factory)
    unfinished_run_ids = await generate_text_run_service.find_unfinished_run_ids(user_id)

    for run_id in unfinished_run_ids:
        try:
            await generate_text_run_service.fail_run(run_id, error_code, error_message)
        except Exception:
            logger.exception("user_unfinished_run_fail_failed", user_id=user_id, run_id=run_id)
