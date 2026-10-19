from decimal import Decimal
from uuid import UUID

from sqlalchemy import func, insert, select, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from libs.auth.results import AuthUser
from libs.core.exceptions import NotFoundException
from libs.database.orm.generate_text_run import GenerateTextRunOrm
from libs.database.orm.llm_call import LlmCallOrm
from libs.database.orm.persona import PersonaOrm
from libs.database.utils import DatabaseClockUtils
from libs.generate_text.inputs import CreateGenerateTextRunInput
from libs.generate_text.results import (
    ClaimExpiredGenerateTextRunResult,
    CreateGenerateTextRunResult,
    FindGenerateTextRunByIdentityResult,
    FindLlmCallRollupResult,
)
from libs.generate_text.types import GenerateTextRunStatusType


class GenerateTextRunService:
    """Writes pb_generate_text_run, each write in its own session and transaction."""

    def __init__(self, db_session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._db_session_factory = db_session_factory

    async def create_run(
        self, create_generate_text_run_input: CreateGenerateTextRunInput, auth_user: AuthUser
    ) -> CreateGenerateTextRunResult:
        """Inserts a run already leased to its creator, so the pickup loop leaves it alone."""
        run_insert = (
            insert(GenerateTextRunOrm)
            .values(
                text_type=create_generate_text_run_input.text_type,
                graph_name=create_generate_text_run_input.graph_name,
                graph_version=create_generate_text_run_input.graph_version,
                prompt_text=create_generate_text_run_input.prompt_text,
                persona_id=create_generate_text_run_input.persona_id,
                tone=create_generate_text_run_input.tone,
                target_audience=create_generate_text_run_input.target_audience,
                additional_context=create_generate_text_run_input.additional_context,
                options=create_generate_text_run_input.options,
                lease_owner=create_generate_text_run_input.lease_owner,
                lease_expires_at=DatabaseClockUtils.build_utc_now_plus_sql(
                    create_generate_text_run_input.lease_seconds
                ),
                created_by_id=auth_user.id,
                updated_by_id=auth_user.id,
            )
            .returning(GenerateTextRunOrm.id, GenerateTextRunOrm.identity)
        )
        async with self._db_session_factory() as db_session, db_session.begin():
            run_insert_result = await db_session.execute(run_insert)
            run_id, run_identity = run_insert_result.one()

        return CreateGenerateTextRunResult(id=run_id, identity=run_identity)

    async def start_run(self, run_id: int) -> None:
        """Marks the run RUNNING and stamps its start; NotFoundException if it is unknown."""
        run_start_update = (
            update(GenerateTextRunOrm)
            .where(GenerateTextRunOrm.id == run_id)
            .values(
                status=GenerateTextRunStatusType.RUNNING,
                started_at=DatabaseClockUtils.build_utc_now_sql(),
            )
        )
        async with self._db_session_factory() as db_session, db_session.begin():
            run_start_update_result = await db_session.execute(run_start_update)
            if run_start_update_result.rowcount == 0:
                raise NotFoundException(f"Generate text run {run_id} not found")

    async def claim_paused_run(self, run_id: int, lease_owner: str, lease_seconds: int) -> bool:
        """Moves a paused run to RUNNING under the given lease. False when it wasn't paused."""
        # One statement tests and sets the status, so of two resumes that arrive together
        # exactly one changes a row
        run_claim_update = (
            update(GenerateTextRunOrm)
            .where(
                GenerateTextRunOrm.id == run_id,
                GenerateTextRunOrm.status == GenerateTextRunStatusType.AWAITING_REVIEW,
            )
            .values(
                status=GenerateTextRunStatusType.RUNNING,
                lease_owner=lease_owner,
                lease_expires_at=DatabaseClockUtils.build_utc_now_plus_sql(lease_seconds),
            )
        )
        async with self._db_session_factory() as db_session, db_session.begin():
            run_claim_update_result = await db_session.execute(run_claim_update)
        return run_claim_update_result.rowcount == 1

    async def claim_expired_run(
        self, lease_owner: str, lease_seconds: int, run_id: int | None = None
    ) -> ClaimExpiredGenerateTextRunResult | None:
        """Takes the lease on an expired run: the given one, else the longest expired."""
        # SKIP LOCKED keeps two processes from claiming the same row; a NULL lease never matches
        expired_run_id_query = (
            select(GenerateTextRunOrm.id)
            .where(
                GenerateTextRunOrm.status.in_(
                    [GenerateTextRunStatusType.PENDING, GenerateTextRunStatusType.RUNNING]
                ),
                # The database clock, so process clock skew can't hide an expiry
                GenerateTextRunOrm.lease_expires_at <= DatabaseClockUtils.build_utc_now_sql(),
                # The session's soft-delete filter covers selects, not this update
                GenerateTextRunOrm.deleted_at.is_(None),
            )
            .order_by(GenerateTextRunOrm.lease_expires_at)
            .limit(1)
            .with_for_update(skip_locked=True)
        )
        if run_id is not None:
            expired_run_id_query = expired_run_id_query.where(GenerateTextRunOrm.id == run_id)
        expired_run_claim_update = (
            update(GenerateTextRunOrm)
            .where(GenerateTextRunOrm.id == expired_run_id_query.scalar_subquery())
            .values(
                lease_owner=lease_owner,
                lease_expires_at=DatabaseClockUtils.build_utc_now_plus_sql(lease_seconds),
                pickup_count=GenerateTextRunOrm.pickup_count + 1,
            )
            .returning(GenerateTextRunOrm)
        )
        async with self._db_session_factory() as db_session, db_session.begin():
            expired_run_claim_update_result = await db_session.execute(expired_run_claim_update)
            run_record = expired_run_claim_update_result.scalar_one_or_none()
            if run_record is None:
                return None
            return ClaimExpiredGenerateTextRunResult.model_validate(
                run_record, from_attributes=True
            )

    async def renew_lease(self, run_id: int, lease_owner: str, lease_seconds: int) -> bool:
        """Extends the lease; False when the lease isn't this owner's."""
        run_lease_renewal_update = (
            update(GenerateTextRunOrm)
            .where(
                GenerateTextRunOrm.id == run_id,
                GenerateTextRunOrm.lease_owner == lease_owner,
            )
            .values(lease_expires_at=DatabaseClockUtils.build_utc_now_plus_sql(lease_seconds))
        )
        async with self._db_session_factory() as db_session, db_session.begin():
            run_lease_renewal_update_result = await db_session.execute(run_lease_renewal_update)
        return run_lease_renewal_update_result.rowcount == 1

    async def release_lease(self, run_id: int, lease_owner: str) -> bool:
        """Expires the lease now; False when the lease isn't this owner's."""
        run_lease_release_update = (
            update(GenerateTextRunOrm)
            .where(
                GenerateTextRunOrm.id == run_id,
                GenerateTextRunOrm.lease_owner == lease_owner,
            )
            .values(lease_expires_at=DatabaseClockUtils.build_utc_now_sql())
        )
        async with self._db_session_factory() as db_session, db_session.begin():
            run_lease_release_update_result = await db_session.execute(run_lease_release_update)
        return run_lease_release_update_result.rowcount == 1

    async def complete_run(self, run_id: int) -> None:
        """Marks the run COMPLETED with its LLM cost totals and clears its lease."""
        async with self._db_session_factory() as db_session, db_session.begin():
            # Sum what the run's LLM calls cost
            llm_call_rollup = await self._find_llm_call_rollup(db_session, run_id)

            # Mark the run completed; a finished run has no lease
            run_completion_update = (
                update(GenerateTextRunOrm)
                .where(GenerateTextRunOrm.id == run_id)
                .values(
                    status=GenerateTextRunStatusType.COMPLETED,
                    finished_at=DatabaseClockUtils.build_utc_now_sql(),
                    lease_owner=None,
                    lease_expires_at=None,
                    llm_call_count=llm_call_rollup.llm_call_count,
                    input_tokens=llm_call_rollup.input_tokens,
                    output_tokens=llm_call_rollup.output_tokens,
                    cost_usd=llm_call_rollup.cost_usd,
                )
            )
            run_completion_update_result = await db_session.execute(run_completion_update)
            if run_completion_update_result.rowcount == 0:
                raise NotFoundException(f"Generate text run {run_id} not found")

    async def record_awaiting_review(self, run_id: int) -> None:
        """Marks the run AWAITING_REVIEW with its cost so far and clears its lease."""
        async with self._db_session_factory() as db_session, db_session.begin():
            # Sum what the run's LLM calls cost so far
            llm_call_rollup = await self._find_llm_call_rollup(db_session, run_id)

            # Mark the run paused; a paused run has no lease
            run_pause_update = (
                update(GenerateTextRunOrm)
                .where(GenerateTextRunOrm.id == run_id)
                .values(
                    status=GenerateTextRunStatusType.AWAITING_REVIEW,
                    lease_owner=None,
                    lease_expires_at=None,
                    llm_call_count=llm_call_rollup.llm_call_count,
                    input_tokens=llm_call_rollup.input_tokens,
                    output_tokens=llm_call_rollup.output_tokens,
                    cost_usd=llm_call_rollup.cost_usd,
                )
            )
            run_pause_update_result = await db_session.execute(run_pause_update)
            if run_pause_update_result.rowcount == 0:
                raise NotFoundException(f"Generate text run {run_id} not found")

    async def fail_run(
        self, run_id: int, error_code: str | None = None, error_message: str | None = None
    ) -> None:
        """Marks the run FAILED, recording an error only when no step owns it."""
        async with self._db_session_factory() as db_session, db_session.begin():
            # Read the status first: a WHERE on it couldn't tell an unknown run from a failed one
            status_query = select(GenerateTextRunOrm.status).where(GenerateTextRunOrm.id == run_id)
            status_query_result = await db_session.execute(status_query)
            run_status = status_query_result.scalar_one_or_none()
            if run_status is None:
                raise NotFoundException(f"Generate text run {run_id} not found")
            if run_status is GenerateTextRunStatusType.FAILED:
                # The first failure wins; a node's failure arrives here again as it propagates
                return

            # Sum what the run's LLM calls cost
            llm_call_rollup = await self._find_llm_call_rollup(db_session, run_id)

            # Mark the run failed; a finished run has no lease
            run_failure_update = (
                update(GenerateTextRunOrm)
                .where(GenerateTextRunOrm.id == run_id)
                .values(
                    status=GenerateTextRunStatusType.FAILED,
                    error_code=error_code,
                    error_message=error_message,
                    finished_at=DatabaseClockUtils.build_utc_now_sql(),
                    lease_owner=None,
                    lease_expires_at=None,
                    llm_call_count=llm_call_rollup.llm_call_count,
                    input_tokens=llm_call_rollup.input_tokens,
                    output_tokens=llm_call_rollup.output_tokens,
                    cost_usd=llm_call_rollup.cost_usd,
                )
            )
            await db_session.execute(run_failure_update)

    async def find_run_by_identity(self, run_identity: UUID) -> FindGenerateTextRunByIdentityResult:
        """Finds any user's run, with a None persona identity once its persona is deleted."""
        async with self._db_session_factory() as db_session:
            # A soft-deleted persona drops out of the join, so its identity is None
            query = (
                select(GenerateTextRunOrm, PersonaOrm.identity)
                .outerjoin(PersonaOrm, PersonaOrm.id == GenerateTextRunOrm.persona_id)
                .where(GenerateTextRunOrm.identity == run_identity)
            )
            query_result = await db_session.execute(query)
            query_row = query_result.one_or_none()

        if query_row is None:
            raise NotFoundException(f"Generate text run {run_identity} not found")
        run_record, persona_identity = query_row
        find_run_result = FindGenerateTextRunByIdentityResult.model_validate(
            run_record, from_attributes=True
        )
        return find_run_result.model_copy(update={"persona_identity": persona_identity})

    async def _find_llm_call_rollup(
        self, db_session: AsyncSession, run_id: int
    ) -> FindLlmCallRollupResult:
        """Sums this run's pb_llm_call rows, including calls made outside a step."""
        query = select(
            func.count(LlmCallOrm.id),
            func.coalesce(func.sum(LlmCallOrm.input_tokens), 0),
            func.coalesce(func.sum(LlmCallOrm.output_tokens), 0),
            func.coalesce(func.sum(LlmCallOrm.cost_usd), 0),
        ).where(LlmCallOrm.run_id == run_id)
        query_result = await db_session.execute(query)
        llm_call_count, input_tokens, output_tokens, cost_usd = query_result.one()

        return FindLlmCallRollupResult(
            llm_call_count=llm_call_count,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cost_usd=Decimal(cost_usd),
        )
