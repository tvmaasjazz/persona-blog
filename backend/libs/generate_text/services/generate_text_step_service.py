from decimal import Decimal

from sqlalchemy import func, insert, null, select, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from libs.auth.results import AuthUser
from libs.core.exceptions import NotFoundException
from libs.database.orm.generate_text_step import GenerateTextStepOrm
from libs.database.orm.llm_call import LlmCallOrm
from libs.database.utils import DatabaseClockUtils
from libs.generate_text.constants import STEP_OUTPUT_TEXT_KEY
from libs.generate_text.inputs import CreateGenerateTextStepInput
from libs.generate_text.results import (
    CreateGenerateTextStepResult,
    FindLatestGenerateTextStepResult,
    FindLlmCallRollupResult,
)
from libs.generate_text.types import GenerateTextStepStatusType, HumanDecisionType


class GenerateTextStepService:
    """Owns every write to pb_generate_text_step. Each write opens its own session and
    commits in its own transaction, so a row survives the caller's rollback. See
    fastapi-structure.md, Services > Records that must survive a rollback."""

    def __init__(self, db_session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._db_session_factory = db_session_factory

    async def create_step(
        self, create_generate_text_step_input: CreateGenerateTextStepInput, auth_user: AuthUser
    ) -> CreateGenerateTextStepResult:
        run_id = create_generate_text_step_input.run_id
        step_name = create_generate_text_step_input.step_name

        async with self._db_session_factory() as db_session, db_session.begin():
            # A review node runs again when the graph resumes. Its paused row is picked back
            # up rather than duplicated, so one pause stays one step.
            paused_step_record = await self._find_awaiting_review_step(
                db_session, run_id, step_name
            )
            if paused_step_record is not None:
                step_resume_update = (
                    update(GenerateTextStepOrm)
                    .where(GenerateTextStepOrm.id == paused_step_record.id)
                    .values(status=GenerateTextStepStatusType.RUNNING)
                )
                await db_session.execute(step_resume_update)
                return CreateGenerateTextStepResult(
                    id=paused_step_record.id, identity=paused_step_record.identity
                )

            # Number the step after the run's last one, and count this name's attempts
            next_step_number = await self._resolve_next_step_number(db_session, run_id)
            next_attempt = await self._resolve_next_attempt(db_session, run_id, step_name)

            # Insert the step as running
            step_insert = (
                insert(GenerateTextStepOrm)
                .values(
                    run_id=run_id,
                    step_number=next_step_number,
                    step_name=step_name,
                    attempt=next_attempt,
                    status=GenerateTextStepStatusType.RUNNING,
                    input=create_generate_text_step_input.input,
                    started_at=DatabaseClockUtils.build_utc_now_sql(),
                    created_by_id=auth_user.id,
                    updated_by_id=auth_user.id,
                )
                .returning(GenerateTextStepOrm.id, GenerateTextStepOrm.identity)
            )
            step_insert_result = await db_session.execute(step_insert)
            step_id, step_identity = step_insert_result.one()

        return CreateGenerateTextStepResult(id=step_id, identity=step_identity)

    async def complete_step(self, step_id: int, output: str, duration_ms: int) -> None:
        async with self._db_session_factory() as db_session, db_session.begin():
            # Sum what the step's LLM calls cost
            llm_call_rollup = await self._find_llm_call_rollup(db_session, step_id)

            # Mark the step succeeded. A node that produced no text — a review node, say —
            # stores nothing rather than an empty string, so "the latest output" skips it.
            step_completion_update = (
                update(GenerateTextStepOrm)
                .where(GenerateTextStepOrm.id == step_id)
                .values(
                    status=GenerateTextStepStatusType.SUCCEEDED,
                    # SQL NULL, not JSON null: a None here would store JSON null, which
                    # the latest-output query's IS NOT NULL doesn't skip
                    output={STEP_OUTPUT_TEXT_KEY: output} if output else null(),
                    duration_ms=duration_ms,
                    finished_at=DatabaseClockUtils.build_utc_now_sql(),
                    llm_call_count=llm_call_rollup.llm_call_count,
                    input_tokens=llm_call_rollup.input_tokens,
                    output_tokens=llm_call_rollup.output_tokens,
                    cost_usd=llm_call_rollup.cost_usd,
                )
            )
            step_completion_update_result = await db_session.execute(step_completion_update)
            if step_completion_update_result.rowcount == 0:
                raise NotFoundException(f"Generate text step {step_id} not found")

    async def fail_step(
        self, step_id: int, error_code: str, error_message: str, duration_ms: int
    ) -> None:
        step_failure_update = (
            update(GenerateTextStepOrm)
            .where(GenerateTextStepOrm.id == step_id)
            .values(
                status=GenerateTextStepStatusType.FAILED,
                error_code=error_code,
                error_message=error_message,
                duration_ms=duration_ms,
                finished_at=DatabaseClockUtils.build_utc_now_sql(),
            )
        )
        async with self._db_session_factory() as db_session, db_session.begin():
            step_failure_update_result = await db_session.execute(step_failure_update)
            if step_failure_update_result.rowcount == 0:
                raise NotFoundException(f"Generate text step {step_id} not found")

    async def record_decision(
        self,
        step_id: int,
        human_decision: HumanDecisionType,
        human_feedback: str | None,
        auth_user: AuthUser,
    ) -> None:
        step_decision_update = (
            update(GenerateTextStepOrm)
            .where(GenerateTextStepOrm.id == step_id)
            .values(
                human_decision=human_decision,
                human_feedback=human_feedback,
                decided_by_id=auth_user.id,
                decided_at=DatabaseClockUtils.build_utc_now_sql(),
                updated_by_id=auth_user.id,
            )
        )
        async with self._db_session_factory() as db_session, db_session.begin():
            step_decision_update_result = await db_session.execute(step_decision_update)
            if step_decision_update_result.rowcount == 0:
                raise NotFoundException(f"Generate text step {step_id} not found")

    async def find_awaiting_review_step_id(self, run_id: int) -> int | None:
        """The step a paused run is waiting on, or None when no step is paused."""
        async with self._db_session_factory() as db_session:
            query = (
                select(GenerateTextStepOrm.id)
                .where(
                    GenerateTextStepOrm.run_id == run_id,
                    GenerateTextStepOrm.status == GenerateTextStepStatusType.AWAITING_REVIEW,
                )
                .order_by(GenerateTextStepOrm.step_number.desc())
                .limit(1)
            )
            return await db_session.scalar(query)

    @staticmethod
    async def _find_awaiting_review_step(
        db_session: AsyncSession, run_id: int, step_name: str
    ) -> GenerateTextStepOrm | None:
        query = select(GenerateTextStepOrm).where(
            GenerateTextStepOrm.run_id == run_id,
            GenerateTextStepOrm.step_name == step_name,
            GenerateTextStepOrm.status == GenerateTextStepStatusType.AWAITING_REVIEW,
        )
        query_result = await db_session.execute(query)
        return query_result.scalar_one_or_none()

    async def find_latest_step(self, run_id: int) -> FindLatestGenerateTextStepResult:
        """Where the run sits, and the text it has produced. These are two different rows:
        a run paused for review sits on its review step, which has no output of its own,
        while the text came from the step before it. Read from the step rows rather than
        the checkpoint, so both survive the checkpoint's TTL."""
        latest_step_query = (
            select(GenerateTextStepOrm.step_name)
            .where(GenerateTextStepOrm.run_id == run_id)
            .order_by(GenerateTextStepOrm.step_number.desc())
            .limit(1)
        )
        latest_output_query = (
            select(GenerateTextStepOrm.output)
            .where(GenerateTextStepOrm.run_id == run_id, GenerateTextStepOrm.output.is_not(None))
            .order_by(GenerateTextStepOrm.step_number.desc())
            .limit(1)
        )
        async with self._db_session_factory() as db_session:
            latest_step_name = await db_session.scalar(latest_step_query)
            latest_output = await db_session.scalar(latest_output_query)

        if latest_step_name is None:
            raise NotFoundException(f"Generate text run {run_id} has no steps")

        step_output = latest_output or {}
        return FindLatestGenerateTextStepResult(
            step_name=latest_step_name, content=step_output.get(STEP_OUTPUT_TEXT_KEY, "")
        )

    async def record_awaiting_review(self, step_id: int, duration_ms: int) -> None:
        """A review node paused rather than failed: the graph will call it again on resume."""
        step_pause_update = (
            update(GenerateTextStepOrm)
            .where(GenerateTextStepOrm.id == step_id)
            .values(
                status=GenerateTextStepStatusType.AWAITING_REVIEW,
                duration_ms=duration_ms,
            )
        )
        async with self._db_session_factory() as db_session, db_session.begin():
            step_pause_update_result = await db_session.execute(step_pause_update)
            if step_pause_update_result.rowcount == 0:
                raise NotFoundException(f"Generate text step {step_id} not found")

    async def _find_llm_call_rollup(
        self, db_session: AsyncSession, step_id: int
    ) -> FindLlmCallRollupResult:
        """Sums this step's pb_llm_call rows."""
        query = select(
            func.count(LlmCallOrm.id),
            func.coalesce(func.sum(LlmCallOrm.input_tokens), 0),
            func.coalesce(func.sum(LlmCallOrm.output_tokens), 0),
            func.coalesce(func.sum(LlmCallOrm.cost_usd), 0),
        ).where(LlmCallOrm.step_id == step_id)
        query_result = await db_session.execute(query)
        llm_call_count, input_tokens, output_tokens, cost_usd = query_result.one()

        return FindLlmCallRollupResult(
            llm_call_count=llm_call_count,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cost_usd=Decimal(cost_usd),
        )

    async def _resolve_next_step_number(self, db_session: AsyncSession, run_id: int) -> int:
        query = select(func.max(GenerateTextStepOrm.step_number)).where(
            GenerateTextStepOrm.run_id == run_id
        )
        query_result = await db_session.execute(query)
        max_step_number = query_result.scalar_one_or_none()
        return (max_step_number or 0) + 1

    async def _resolve_next_attempt(
        self, db_session: AsyncSession, run_id: int, step_name: str
    ) -> int:
        query = select(func.count()).where(
            GenerateTextStepOrm.run_id == run_id, GenerateTextStepOrm.step_name == step_name
        )
        query_result = await db_session.execute(query)
        existing_count = query_result.scalar_one()
        return existing_count + 1
