from datetime import UTC, datetime
from decimal import Decimal
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from libs.auth.results import AuthUser
from libs.core.exceptions import NotFoundException
from libs.database.orm.generate_text_run import GenerateTextRunOrm
from libs.database.orm.llm_call import LlmCallOrm
from libs.generate_text.inputs import CreateGenerateTextRunInput
from libs.generate_text.results import (
    CreateGenerateTextRunResult,
    FindGenerateTextRunByIdentityResult,
)
from libs.generate_text.types import GenerateTextRunStatusType


class GenerateTextRunService:
    """Owns every write to pb_generate_text_run. Each write opens its own session and
    commits in its own transaction, so a row survives the caller's rollback. See
    fastapi-structure.md, Services > Records that must survive a rollback."""

    def __init__(self, db_session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._db_session_factory = db_session_factory

    async def create_run(
        self, create_generate_text_run_input: CreateGenerateTextRunInput, auth_user: AuthUser
    ) -> CreateGenerateTextRunResult:
        async with self._db_session_factory() as db_session, db_session.begin():
            run_record = GenerateTextRunOrm(
                text_type=create_generate_text_run_input.text_type,
                graph_name=create_generate_text_run_input.graph_name,
                graph_version=create_generate_text_run_input.graph_version,
                prompt_text=create_generate_text_run_input.prompt_text,
                persona_info=create_generate_text_run_input.persona_info,
                additional_context=create_generate_text_run_input.additional_context,
                options=create_generate_text_run_input.options,
                created_by_id=auth_user.id,
                updated_by_id=auth_user.id,
            )
            db_session.add(run_record)
            await db_session.flush()
            run_id = run_record.id
            run_identity = run_record.identity

        return CreateGenerateTextRunResult(id=run_id, identity=run_identity)

    async def start_run(self, run_id: int) -> None:
        async with self._db_session_factory() as db_session, db_session.begin():
            run_record = await self._get_run(db_session, run_id)
            run_record.status = GenerateTextRunStatusType.RUNNING
            run_record.started_at = datetime.now(UTC)
            await db_session.flush()

    async def complete_run(self, run_id: int) -> None:
        async with self._db_session_factory() as db_session, db_session.begin():
            run_record = await self._get_run(db_session, run_id)
            run_record.status = GenerateTextRunStatusType.COMPLETED
            run_record.finished_at = datetime.now(UTC)
            await self._apply_rollup(db_session, run_record)
            await db_session.flush()

    async def record_awaiting_review(self, run_id: int) -> None:
        # A paused run is exactly when someone looks at what it has cost so far.
        async with self._db_session_factory() as db_session, db_session.begin():
            run_record = await self._get_run(db_session, run_id)
            run_record.status = GenerateTextRunStatusType.AWAITING_REVIEW
            await self._apply_rollup(db_session, run_record)
            await db_session.flush()

    async def fail_run(
        self, run_id: int, error_code: str | None = None, error_message: str | None = None
    ) -> None:
        """The error is recorded here only when no step owns it — a graph that failed to
        run at all, say. A node's failure is recorded on its own step row, and the run
        just goes FAILED."""
        async with self._db_session_factory() as db_session, db_session.begin():
            run_record = await self._get_run(db_session, run_id)
            if run_record.status is GenerateTextRunStatusType.FAILED:
                # The first failure wins: a node's failure reaches here again as the
                # exception travels up, and it must not overwrite what recorded it.
                return

            run_record.status = GenerateTextRunStatusType.FAILED
            run_record.error_code = error_code
            run_record.error_message = error_message
            run_record.finished_at = datetime.now(UTC)
            await self._apply_rollup(db_session, run_record)
            await db_session.flush()

    async def find_run_by_identity(self, run_identity: UUID) -> FindGenerateTextRunByIdentityResult:
        async with self._db_session_factory() as db_session:
            query = select(GenerateTextRunOrm).where(GenerateTextRunOrm.identity == run_identity)
            query_result = await db_session.execute(query)
            run_record = query_result.scalar_one_or_none()

        if run_record is None:
            raise NotFoundException(f"Generate text run {run_identity} not found")
        return FindGenerateTextRunByIdentityResult.model_validate(run_record, from_attributes=True)

    async def _apply_rollup(self, db_session: AsyncSession, run_record: GenerateTextRunOrm) -> None:
        """Sums this run's pb_llm_call rows onto the run row itself. Aggregating by
        run_id, rather than summing the step rows, means a call made outside a step
        still counts."""
        query = select(
            func.count(LlmCallOrm.id),
            func.coalesce(func.sum(LlmCallOrm.input_tokens), 0),
            func.coalesce(func.sum(LlmCallOrm.output_tokens), 0),
            func.coalesce(func.sum(LlmCallOrm.cost_usd), 0),
        ).where(LlmCallOrm.run_id == run_record.id)
        query_result = await db_session.execute(query)
        llm_call_count, input_tokens, output_tokens, cost_usd = query_result.one()

        run_record.llm_call_count = llm_call_count
        run_record.input_tokens = input_tokens
        run_record.output_tokens = output_tokens
        run_record.cost_usd = Decimal(cost_usd)

    async def _get_run(self, db_session: AsyncSession, run_id: int) -> GenerateTextRunOrm:
        run_record = await db_session.get(GenerateTextRunOrm, run_id)
        if run_record is None:
            raise NotFoundException(f"Generate text run {run_id} not found")
        return run_record
