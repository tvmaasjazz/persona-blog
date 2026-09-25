from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from libs.auth.results import AuthUser
from libs.core.exceptions import NotFoundException
from libs.database.orm.generate_text_step import GenerateTextStepOrm
from libs.generate_text.constants import STEP_OUTPUT_TEXT_KEY
from libs.generate_text.inputs import CreateGenerateTextStepInput
from libs.generate_text.results import (
    CreateGenerateTextStepResult,
    GenerateTextRollupResult,
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
                paused_step_record.status = GenerateTextStepStatusType.RUNNING
                await db_session.flush()
                return CreateGenerateTextStepResult(
                    id=paused_step_record.id, identity=paused_step_record.identity
                )

            next_seq = await self._resolve_next_seq(db_session, run_id)
            next_attempt = await self._resolve_next_attempt(db_session, run_id, step_name)

            step_record = GenerateTextStepOrm(
                run_id=run_id,
                seq=next_seq,
                step_name=step_name,
                attempt=next_attempt,
                status=GenerateTextStepStatusType.RUNNING,
                input=create_generate_text_step_input.input,
                started_at=datetime.now(UTC),
                created_by_id=auth_user.id,
                updated_by_id=auth_user.id,
            )
            db_session.add(step_record)
            await db_session.flush()
            step_id = step_record.id
            step_identity = step_record.identity

        return CreateGenerateTextStepResult(id=step_id, identity=step_identity)

    async def complete_step(self, step_id: int, output: str, duration_ms: int) -> None:
        async with self._db_session_factory() as db_session, db_session.begin():
            step_record = await self._get_step(db_session, step_id)
            step_record.status = GenerateTextStepStatusType.SUCCEEDED
            step_record.output = {STEP_OUTPUT_TEXT_KEY: output}
            step_record.duration_ms = duration_ms
            step_record.finished_at = datetime.now(UTC)
            await db_session.flush()

    async def fail_step(
        self, step_id: int, error_code: str, error_message: str, duration_ms: int
    ) -> None:
        async with self._db_session_factory() as db_session, db_session.begin():
            step_record = await self._get_step(db_session, step_id)
            step_record.status = GenerateTextStepStatusType.FAILED
            step_record.error_code = error_code
            step_record.error_message = error_message
            step_record.duration_ms = duration_ms
            step_record.finished_at = datetime.now(UTC)
            await db_session.flush()

    async def record_decision(
        self,
        step_id: int,
        human_decision: HumanDecisionType,
        human_feedback: str | None,
        auth_user: AuthUser,
        decided_at: datetime,
    ) -> None:
        async with self._db_session_factory() as db_session, db_session.begin():
            step_record = await self._get_step(db_session, step_id)
            step_record.human_decision = human_decision
            step_record.human_feedback = human_feedback
            step_record.decided_by_id = auth_user.id
            step_record.decided_at = decided_at
            step_record.updated_by_id = auth_user.id
            await db_session.flush()

    async def record_rollup(self, step_id: int, rollup_result: GenerateTextRollupResult) -> None:
        async with self._db_session_factory() as db_session, db_session.begin():
            step_record = await self._get_step(db_session, step_id)
            step_record.llm_call_count = rollup_result.llm_call_count
            step_record.input_tokens = rollup_result.input_tokens
            step_record.output_tokens = rollup_result.output_tokens
            step_record.cost_usd = rollup_result.cost_usd
            await db_session.flush()

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

    async def find_latest_output(self, run_id: int) -> str:
        """The newest step output for a run, which is what the run produced so far. Read
        from the step rows rather than the checkpoint, so it survives the checkpoint's TTL."""
        query = (
            select(GenerateTextStepOrm.output)
            .where(GenerateTextStepOrm.run_id == run_id, GenerateTextStepOrm.output.is_not(None))
            .order_by(GenerateTextStepOrm.seq.desc())
            .limit(1)
        )
        async with self._db_session_factory() as db_session:
            latest_output = await db_session.scalar(query)

        if latest_output is None:
            return ""
        return latest_output.get(STEP_OUTPUT_TEXT_KEY, "")

    async def record_awaiting_review(self, step_id: int, duration_ms: int) -> None:
        """A review node paused rather than failed: the graph will call it again on resume."""
        async with self._db_session_factory() as db_session, db_session.begin():
            step_record = await db_session.get(GenerateTextStepOrm, step_id)
            if step_record is None:
                raise NotFoundException(f"Generate text step {step_id} not found")

            step_record.status = GenerateTextStepStatusType.AWAITING_REVIEW
            step_record.duration_ms = duration_ms
            await db_session.flush()

    async def _resolve_next_seq(self, db_session: AsyncSession, run_id: int) -> int:
        query = select(func.max(GenerateTextStepOrm.seq)).where(
            GenerateTextStepOrm.run_id == run_id
        )
        query_result = await db_session.execute(query)
        max_seq = query_result.scalar_one_or_none()
        return (max_seq or 0) + 1

    async def _resolve_next_attempt(
        self, db_session: AsyncSession, run_id: int, step_name: str
    ) -> int:
        query = select(func.count()).where(
            GenerateTextStepOrm.run_id == run_id, GenerateTextStepOrm.step_name == step_name
        )
        query_result = await db_session.execute(query)
        existing_count = query_result.scalar_one()
        return existing_count + 1

    async def _get_step(self, db_session: AsyncSession, step_id: int) -> GenerateTextStepOrm:
        step_record = await db_session.get(GenerateTextStepOrm, step_id)
        if step_record is None:
            raise NotFoundException(f"Generate text step {step_id} not found")
        return step_record
