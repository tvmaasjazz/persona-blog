import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from libs.generate_text.exceptions import GenerateTextActiveRunLimitException
from libs.generate_text.services import GenerateTextValidationService
from libs.generate_text.types import GenerateTextRunStatusType
from tests.factories.auth import build_auth_user
from tests.factories.generate_text import insert_generate_text_run_row
from tests.factories.users import insert_user_row


@pytest.mark.parametrize(
    "active_status",
    [GenerateTextRunStatusType.PENDING, GenerateTextRunStatusType.RUNNING],
)
async def test_validate_active_run_count_below_limit_at_limit_raises_active_run_limit_exception(
    db_session: AsyncSession, active_status: GenerateTextRunStatusType
) -> None:
    user_record = await insert_user_row(db_session)
    await insert_generate_text_run_row(
        db_session, created_by_id=user_record.id, status=active_status
    )
    await insert_generate_text_run_row(
        db_session, created_by_id=user_record.id, status=active_status
    )
    auth_user = build_auth_user(user_id=user_record.id, user_identity=user_record.identity)
    generate_text_validation_service = GenerateTextValidationService(db_session=db_session)

    with pytest.raises(GenerateTextActiveRunLimitException):
        await generate_text_validation_service.validate_active_run_count_below_limit(auth_user, 2)


async def test_validate_active_run_count_below_limit_over_limit_raises_active_run_limit_exception(
    db_session: AsyncSession,
) -> None:
    user_record = await insert_user_row(db_session)
    await insert_generate_text_run_row(
        db_session, created_by_id=user_record.id, status=GenerateTextRunStatusType.PENDING
    )
    await insert_generate_text_run_row(
        db_session, created_by_id=user_record.id, status=GenerateTextRunStatusType.RUNNING
    )
    auth_user = build_auth_user(user_id=user_record.id, user_identity=user_record.identity)
    generate_text_validation_service = GenerateTextValidationService(db_session=db_session)

    with pytest.raises(GenerateTextActiveRunLimitException):
        await generate_text_validation_service.validate_active_run_count_below_limit(auth_user, 1)


async def test_validate_active_run_count_below_limit_below_limit_passes(
    db_session: AsyncSession,
) -> None:
    user_record = await insert_user_row(db_session)
    await insert_generate_text_run_row(
        db_session, created_by_id=user_record.id, status=GenerateTextRunStatusType.RUNNING
    )
    auth_user = build_auth_user(user_id=user_record.id, user_identity=user_record.identity)
    generate_text_validation_service = GenerateTextValidationService(db_session=db_session)

    await generate_text_validation_service.validate_active_run_count_below_limit(auth_user, 2)


@pytest.mark.parametrize(
    "inactive_status",
    [
        GenerateTextRunStatusType.AWAITING_REVIEW,
        GenerateTextRunStatusType.COMPLETED,
        GenerateTextRunStatusType.FAILED,
        GenerateTextRunStatusType.CANCELLED,
    ],
)
async def test_validate_active_run_count_below_limit_ignores_runs_that_are_not_pending_or_running(
    db_session: AsyncSession, inactive_status: GenerateTextRunStatusType
) -> None:
    user_record = await insert_user_row(db_session)
    await insert_generate_text_run_row(
        db_session, created_by_id=user_record.id, status=inactive_status
    )
    await insert_generate_text_run_row(
        db_session, created_by_id=user_record.id, status=inactive_status
    )
    auth_user = build_auth_user(user_id=user_record.id, user_identity=user_record.identity)
    generate_text_validation_service = GenerateTextValidationService(db_session=db_session)

    await generate_text_validation_service.validate_active_run_count_below_limit(auth_user, 2)


async def test_validate_active_run_count_below_limit_ignores_another_users_runs(
    db_session: AsyncSession,
) -> None:
    user_record = await insert_user_row(db_session)
    other_user_record = await insert_user_row(db_session)
    await insert_generate_text_run_row(
        db_session, created_by_id=other_user_record.id, status=GenerateTextRunStatusType.RUNNING
    )
    await insert_generate_text_run_row(
        db_session, created_by_id=other_user_record.id, status=GenerateTextRunStatusType.PENDING
    )
    auth_user = build_auth_user(user_id=user_record.id, user_identity=user_record.identity)
    generate_text_validation_service = GenerateTextValidationService(db_session=db_session)

    await generate_text_validation_service.validate_active_run_count_below_limit(auth_user, 2)
