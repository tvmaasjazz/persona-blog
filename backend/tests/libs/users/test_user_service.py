from datetime import UTC, datetime
from decimal import Decimal
from uuid import uuid4

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from libs.auth.types import AuthProviderType
from libs.core.exceptions import ForbiddenException, NotFoundException
from libs.database.orm import RoleOrm, UserAuthProviderOrm, UserOrm
from libs.permissions.types import RoleType
from libs.users.exceptions import UserEmailTakenException, UserInactiveException
from libs.users.results import FindOrCreateUserFromAuthProviderResult, FindUserByIdentityResult
from libs.users.services import UserService
from tests.factories.users import (
    build_find_or_create_user_from_auth_provider_input,
    insert_user_auth_provider_row,
    insert_user_row,
)


async def test_find_or_create_user_from_auth_provider_creates_user_and_provider_row(
    db_session: AsyncSession,
) -> None:
    user_service = UserService(
        db_session=db_session, low_credit_balance_threshold_usd=Decimal("0.50")
    )
    find_or_create_user_from_auth_provider_input = (
        build_find_or_create_user_from_auth_provider_input(
            provider_subject="google-subject-1",
            email="ada@example.com",
            is_email_verified=True,
            display_name="Ada Lovelace",
            avatar_url="https://example.com/ada.png",
        )
    )

    find_or_create_user_from_auth_provider_result = (
        await user_service.find_or_create_user_from_auth_provider(
            find_or_create_user_from_auth_provider_input
        )
    )

    user_query = select(UserOrm).where(
        UserOrm.id == find_or_create_user_from_auth_provider_result.id
    )
    user_record = await db_session.scalar(user_query)
    user_auth_provider_query = select(UserAuthProviderOrm).where(
        UserAuthProviderOrm.user_id == find_or_create_user_from_auth_provider_result.id
    )
    user_auth_provider_record = await db_session.scalar(user_auth_provider_query)
    assert user_record is not None
    assert user_auth_provider_record is not None
    assert find_or_create_user_from_auth_provider_result == FindOrCreateUserFromAuthProviderResult(
        id=user_record.id,
        identity=user_record.identity,
        role=RoleType.READER,
        user_auth_provider_id=user_auth_provider_record.id,
        is_new_user=True,
    )
    assert user_record.email == "ada@example.com"
    assert user_record.is_email_verified is True
    assert user_record.display_name == "Ada Lovelace"
    assert user_record.avatar_url == "https://example.com/ada.png"
    assert user_record.created_by_id is None
    assert user_record.updated_by_id is None
    assert user_auth_provider_record.user_id == user_record.id
    assert user_auth_provider_record.provider == AuthProviderType.GOOGLE
    assert user_auth_provider_record.provider_subject == "google-subject-1"
    assert user_auth_provider_record.email_at_provider == "ada@example.com"
    assert user_auth_provider_record.created_by_id == user_record.id
    assert user_auth_provider_record.updated_by_id == user_record.id


async def test_find_or_create_user_from_auth_provider_new_user_is_stored_as_reader(
    db_session: AsyncSession,
) -> None:
    user_service = UserService(
        db_session=db_session, low_credit_balance_threshold_usd=Decimal("0.50")
    )
    find_or_create_user_from_auth_provider_input = (
        build_find_or_create_user_from_auth_provider_input()
    )

    find_or_create_user_from_auth_provider_result = (
        await user_service.find_or_create_user_from_auth_provider(
            find_or_create_user_from_auth_provider_input
        )
    )

    role_query = (
        select(RoleOrm.code)
        .join(UserOrm, UserOrm.role_id == RoleOrm.id)
        .where(UserOrm.id == find_or_create_user_from_auth_provider_result.id)
    )
    stored_role = await db_session.scalar(role_query)
    assert stored_role == RoleType.READER


async def test_find_or_create_user_from_auth_provider_existing_provider_returns_existing_user(
    db_session: AsyncSession,
) -> None:
    user_record = await insert_user_row(db_session, email="ada@example.com")
    user_auth_provider_record = await insert_user_auth_provider_row(
        db_session,
        user_id=user_record.id,
        provider_subject="google-subject-2",
        email_at_provider="ada@example.com",
    )
    user_service = UserService(
        db_session=db_session, low_credit_balance_threshold_usd=Decimal("0.50")
    )
    find_or_create_user_from_auth_provider_input = (
        build_find_or_create_user_from_auth_provider_input(provider_subject="google-subject-2")
    )

    find_or_create_user_from_auth_provider_result = (
        await user_service.find_or_create_user_from_auth_provider(
            find_or_create_user_from_auth_provider_input
        )
    )

    user_auth_provider_count_query = select(func.count(UserAuthProviderOrm.id)).where(
        UserAuthProviderOrm.provider_subject == "google-subject-2"
    )
    user_auth_provider_count = await db_session.scalar(user_auth_provider_count_query)
    assert find_or_create_user_from_auth_provider_result == FindOrCreateUserFromAuthProviderResult(
        id=user_record.id,
        identity=user_record.identity,
        role=RoleType.CREATOR,
        user_auth_provider_id=user_auth_provider_record.id,
        is_new_user=False,
    )
    assert user_auth_provider_count == 1


async def test_find_or_create_user_from_auth_provider_existing_provider_returns_stored_role(
    db_session: AsyncSession,
) -> None:
    user_record = await insert_user_row(db_session, role=RoleType.ADMIN)
    await insert_user_auth_provider_row(
        db_session, user_id=user_record.id, provider_subject="google-subject-5"
    )
    user_service = UserService(
        db_session=db_session, low_credit_balance_threshold_usd=Decimal("0.50")
    )
    find_or_create_user_from_auth_provider_input = (
        build_find_or_create_user_from_auth_provider_input(provider_subject="google-subject-5")
    )

    find_or_create_user_from_auth_provider_result = (
        await user_service.find_or_create_user_from_auth_provider(
            find_or_create_user_from_auth_provider_input
        )
    )

    assert find_or_create_user_from_auth_provider_result.role == RoleType.ADMIN


async def test_find_or_create_user_from_auth_provider_inactive_user_raises_user_inactive(
    db_session: AsyncSession,
) -> None:
    user_record = await insert_user_row(db_session, is_active=False)
    await insert_user_auth_provider_row(
        db_session, user_id=user_record.id, provider_subject="google-subject-3"
    )
    user_service = UserService(
        db_session=db_session, low_credit_balance_threshold_usd=Decimal("0.50")
    )
    find_or_create_user_from_auth_provider_input = (
        build_find_or_create_user_from_auth_provider_input(provider_subject="google-subject-3")
    )

    with pytest.raises(UserInactiveException):
        await user_service.find_or_create_user_from_auth_provider(
            find_or_create_user_from_auth_provider_input
        )


async def test_find_or_create_user_from_auth_provider_soft_deleted_user_raises_forbidden_exception(
    db_session: AsyncSession,
) -> None:
    deleted_at = datetime(2026, 1, 2, 3, 4, 5, tzinfo=UTC)
    user_record = await insert_user_row(db_session, deleted_at=deleted_at)
    await insert_user_auth_provider_row(
        db_session, user_id=user_record.id, provider_subject="google-subject-4"
    )
    user_service = UserService(
        db_session=db_session, low_credit_balance_threshold_usd=Decimal("0.50")
    )
    find_or_create_user_from_auth_provider_input = (
        build_find_or_create_user_from_auth_provider_input(provider_subject="google-subject-4")
    )

    with pytest.raises(ForbiddenException):
        await user_service.find_or_create_user_from_auth_provider(
            find_or_create_user_from_auth_provider_input
        )


async def test_find_or_create_user_from_auth_provider_email_taken_raises_user_email_taken(
    db_session: AsyncSession,
) -> None:
    await insert_user_row(db_session, email="ada@example.com")
    user_service = UserService(
        db_session=db_session, low_credit_balance_threshold_usd=Decimal("0.50")
    )
    find_or_create_user_from_auth_provider_input = (
        build_find_or_create_user_from_auth_provider_input(email="ada@example.com")
    )

    with pytest.raises(UserEmailTakenException):
        await user_service.find_or_create_user_from_auth_provider(
            find_or_create_user_from_auth_provider_input
        )


async def test_find_or_create_user_from_auth_provider_email_case_diff_raises_user_email_taken(
    db_session: AsyncSession,
) -> None:
    await insert_user_row(db_session, email="ADA@example.com")
    user_service = UserService(
        db_session=db_session, low_credit_balance_threshold_usd=Decimal("0.50")
    )
    find_or_create_user_from_auth_provider_input = (
        build_find_or_create_user_from_auth_provider_input(email="ada@example.com")
    )

    with pytest.raises(UserEmailTakenException):
        await user_service.find_or_create_user_from_auth_provider(
            find_or_create_user_from_auth_provider_input
        )


async def test_find_or_create_user_from_auth_provider_email_only_on_deleted_user_creates_user(
    db_session: AsyncSession,
) -> None:
    deleted_at = datetime(2026, 1, 2, 3, 4, 5, tzinfo=UTC)
    await insert_user_row(db_session, email="ada@example.com", deleted_at=deleted_at)
    user_service = UserService(
        db_session=db_session, low_credit_balance_threshold_usd=Decimal("0.50")
    )
    find_or_create_user_from_auth_provider_input = (
        build_find_or_create_user_from_auth_provider_input(email="ada@example.com")
    )

    find_or_create_user_from_auth_provider_result = (
        await user_service.find_or_create_user_from_auth_provider(
            find_or_create_user_from_auth_provider_input
        )
    )

    assert find_or_create_user_from_auth_provider_result.is_new_user is True


async def test_find_or_create_user_from_auth_provider_soft_deleted_provider_row_creates_new_user(
    db_session: AsyncSession,
) -> None:
    deleted_at = datetime(2026, 1, 2, 3, 4, 5, tzinfo=UTC)
    existing_user_record = await insert_user_row(db_session)
    await insert_user_auth_provider_row(
        db_session,
        user_id=existing_user_record.id,
        provider_subject="google-subject-5",
        deleted_at=deleted_at,
    )
    user_service = UserService(
        db_session=db_session, low_credit_balance_threshold_usd=Decimal("0.50")
    )
    find_or_create_user_from_auth_provider_input = (
        build_find_or_create_user_from_auth_provider_input(provider_subject="google-subject-5")
    )

    find_or_create_user_from_auth_provider_result = (
        await user_service.find_or_create_user_from_auth_provider(
            find_or_create_user_from_auth_provider_input
        )
    )

    assert find_or_create_user_from_auth_provider_result.is_new_user is True
    assert find_or_create_user_from_auth_provider_result.id != existing_user_record.id
    user_auth_provider_query = select(UserAuthProviderOrm).where(
        UserAuthProviderOrm.user_id == find_or_create_user_from_auth_provider_result.id
    )
    new_user_auth_provider_record = await db_session.scalar(user_auth_provider_query)
    assert new_user_auth_provider_record is not None
    assert new_user_auth_provider_record.provider_subject == "google-subject-5"


async def test_find_user_by_identity_returns_user(db_session: AsyncSession) -> None:
    user_record = await insert_user_row(
        db_session,
        email="ada@example.com",
        display_name="Ada Lovelace",
        credit_balance_usd=Decimal("2.5"),
    )
    user_service = UserService(
        db_session=db_session, low_credit_balance_threshold_usd=Decimal("0.50")
    )

    find_user_by_identity_result = await user_service.find_user_by_identity(user_record.identity)

    assert find_user_by_identity_result == FindUserByIdentityResult(
        id=user_record.id,
        identity=user_record.identity,
        email="ada@example.com",
        is_email_verified=user_record.is_email_verified,
        display_name="Ada Lovelace",
        avatar_url=user_record.avatar_url,
        is_active=user_record.is_active,
        credit_balance_usd=Decimal("2.5"),
        is_credit_balance_low=False,
    )


@pytest.mark.parametrize(
    ("credit_balance_usd", "expected_is_credit_balance_low"),
    [
        pytest.param(Decimal("0.4999999999"), True, id="just_below_threshold"),
        pytest.param(Decimal("0"), True, id="zero"),
        pytest.param(Decimal("0.50"), False, id="at_threshold"),
        pytest.param(Decimal("3.00"), False, id="above_threshold"),
    ],
)
async def test_find_user_by_identity_flags_balance_below_threshold_as_low(
    db_session: AsyncSession, credit_balance_usd: Decimal, expected_is_credit_balance_low: bool
) -> None:
    user_record = await insert_user_row(db_session, credit_balance_usd=credit_balance_usd)
    user_service = UserService(
        db_session=db_session, low_credit_balance_threshold_usd=Decimal("0.50")
    )

    find_user_by_identity_result = await user_service.find_user_by_identity(user_record.identity)

    assert find_user_by_identity_result.is_credit_balance_low is expected_is_credit_balance_low


async def test_find_user_by_identity_uses_the_threshold_it_was_built_with(
    db_session: AsyncSession,
) -> None:
    user_record = await insert_user_row(db_session, credit_balance_usd=Decimal("0.75"))
    user_service = UserService(
        db_session=db_session, low_credit_balance_threshold_usd=Decimal("1.00")
    )

    find_user_by_identity_result = await user_service.find_user_by_identity(user_record.identity)

    assert find_user_by_identity_result.is_credit_balance_low is True


async def test_find_user_by_identity_never_inserted_raises_not_found_exception(
    db_session: AsyncSession,
) -> None:
    user_service = UserService(
        db_session=db_session, low_credit_balance_threshold_usd=Decimal("0.50")
    )

    with pytest.raises(NotFoundException):
        await user_service.find_user_by_identity(uuid4())


async def test_find_user_by_identity_soft_deleted_raises_not_found_exception(
    db_session: AsyncSession,
) -> None:
    deleted_at = datetime(2026, 1, 2, 3, 4, 5, tzinfo=UTC)
    user_record = await insert_user_row(db_session, deleted_at=deleted_at)
    user_service = UserService(
        db_session=db_session, low_credit_balance_threshold_usd=Decimal("0.50")
    )

    with pytest.raises(NotFoundException):
        await user_service.find_user_by_identity(user_record.identity)


async def test_make_reader_creator_reader_returns_true_and_becomes_creator(
    db_session: AsyncSession,
) -> None:
    user_record = await insert_user_row(db_session, role=RoleType.READER)
    admin_record = await insert_user_row(db_session, role=RoleType.ADMIN)
    user_service = UserService(
        db_session=db_session, low_credit_balance_threshold_usd=Decimal("0.50")
    )

    is_made_creator = await user_service.make_reader_creator(user_record.id, admin_record.id)

    role_code_query = (
        select(RoleOrm.code)
        .join(UserOrm, UserOrm.role_id == RoleOrm.id)
        .where(UserOrm.id == user_record.id)
    )
    updated_by_id_query = select(UserOrm.updated_by_id).where(UserOrm.id == user_record.id)
    role_code = await db_session.scalar(role_code_query)
    updated_by_id = await db_session.scalar(updated_by_id_query)
    assert is_made_creator is True
    assert role_code == RoleType.CREATOR
    assert updated_by_id == admin_record.id


@pytest.mark.parametrize("role", [RoleType.CREATOR, RoleType.ADMIN])
async def test_make_reader_creator_creator_or_admin_returns_false_and_keeps_role(
    db_session: AsyncSession, role: RoleType
) -> None:
    user_record = await insert_user_row(db_session, role=role)
    admin_record = await insert_user_row(db_session, role=RoleType.ADMIN)
    user_service = UserService(
        db_session=db_session, low_credit_balance_threshold_usd=Decimal("0.50")
    )

    is_made_creator = await user_service.make_reader_creator(user_record.id, admin_record.id)

    role_code_query = (
        select(RoleOrm.code)
        .join(UserOrm, UserOrm.role_id == RoleOrm.id)
        .where(UserOrm.id == user_record.id)
    )
    updated_by_id_query = select(UserOrm.updated_by_id).where(UserOrm.id == user_record.id)
    role_code = await db_session.scalar(role_code_query)
    updated_by_id = await db_session.scalar(updated_by_id_query)
    assert is_made_creator is False
    assert role_code == role
    assert updated_by_id != admin_record.id
