from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from libs.auth.results import AuthUser
from libs.database.orm.generate_text_run import GenerateTextRunOrm
from libs.generate_text.exceptions import GenerateTextActiveRunLimitException
from libs.generate_text.types import GenerateTextRunStatusType


class GenerateTextValidationService:
    """Holds the generate-text checks a validation guard calls."""

    def __init__(self, db_session: AsyncSession) -> None:
        self._db_session = db_session

    async def validate_active_run_count_below_limit(
        self, auth_user: AuthUser, max_active_runs_per_user: int
    ) -> None:
        """Passes while the user has fewer PENDING or RUNNING runs than the limit;
        GenerateTextActiveRunLimitException otherwise."""
        active_run_count_query = select(func.count()).where(
            GenerateTextRunOrm.created_by_id == auth_user.id,
            GenerateTextRunOrm.status.in_(
                [GenerateTextRunStatusType.PENDING, GenerateTextRunStatusType.RUNNING]
            ),
        )
        active_run_count_query_result = await self._db_session.execute(active_run_count_query)
        active_run_count = active_run_count_query_result.scalar_one()

        if active_run_count >= max_active_runs_per_user:
            raise GenerateTextActiveRunLimitException(
                f"At most {max_active_runs_per_user} generate text runs can be active at once"
            )
