from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from libs.generate_text.after_response_tasks import fail_user_unfinished_runs
from libs.generate_text.types import GenerateTextRunStatusType
from tests.factories.generate_text import insert_generate_text_run_row
from tests.factories.users import insert_user_row


async def test_fail_user_unfinished_runs_fails_each_with_the_code_and_message(
    db_session: AsyncSession, db_session_factory: async_sessionmaker[AsyncSession]
) -> None:
    user_record = await insert_user_row(db_session)
    pending_run_record = await insert_generate_text_run_row(
        db_session, created_by_id=user_record.id, status=GenerateTextRunStatusType.PENDING
    )
    running_run_record = await insert_generate_text_run_row(
        db_session, created_by_id=user_record.id, status=GenerateTextRunStatusType.RUNNING
    )
    awaiting_review_run_record = await insert_generate_text_run_row(
        db_session, created_by_id=user_record.id, status=GenerateTextRunStatusType.AWAITING_REVIEW
    )
    await db_session.commit()

    await fail_user_unfinished_runs(
        db_session_factory=db_session_factory,
        user_id=user_record.id,
        error_code="UserSuspended",
        error_message="Stopped for a test.",
    )

    for run_record in (pending_run_record, running_run_record, awaiting_review_run_record):
        await db_session.refresh(run_record)
        assert run_record.status == GenerateTextRunStatusType.FAILED
        assert run_record.error_code == "UserSuspended"
        assert run_record.error_message == "Stopped for a test."
        assert run_record.finished_at is not None


async def test_fail_user_unfinished_runs_leaves_finished_runs_and_other_users_runs(
    db_session: AsyncSession, db_session_factory: async_sessionmaker[AsyncSession]
) -> None:
    user_record = await insert_user_row(db_session)
    other_user_record = await insert_user_row(db_session)
    completed_run_record = await insert_generate_text_run_row(
        db_session, created_by_id=user_record.id, status=GenerateTextRunStatusType.COMPLETED
    )
    cancelled_run_record = await insert_generate_text_run_row(
        db_session, created_by_id=user_record.id, status=GenerateTextRunStatusType.CANCELLED
    )
    other_users_run_record = await insert_generate_text_run_row(
        db_session, created_by_id=other_user_record.id, status=GenerateTextRunStatusType.RUNNING
    )
    await db_session.commit()

    await fail_user_unfinished_runs(
        db_session_factory=db_session_factory,
        user_id=user_record.id,
        error_code="UserSuspended",
        error_message="Stopped for a test.",
    )

    await db_session.refresh(completed_run_record)
    await db_session.refresh(cancelled_run_record)
    await db_session.refresh(other_users_run_record)
    assert completed_run_record.status == GenerateTextRunStatusType.COMPLETED
    assert completed_run_record.error_code is None
    assert cancelled_run_record.status == GenerateTextRunStatusType.CANCELLED
    assert other_users_run_record.status == GenerateTextRunStatusType.RUNNING
    assert other_users_run_record.error_code is None
