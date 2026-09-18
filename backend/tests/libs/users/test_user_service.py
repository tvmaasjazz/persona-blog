from datetime import UTC, datetime
from uuid import uuid4

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from libs.auth.types import AuthProviderType
from libs.core.exceptions import ConflictException, ForbiddenException, NotFoundException
from libs.database.orm import UserAuthProviderOrm, UserOrm
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
    user_service = UserService(db_session=db_session)
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
    assert find_or_create_user_from_auth_provider_result == FindOrCreateUserFromAuthProviderResult(
        id=user_record.id, identity=user_record.identity, is_new_user=True
    )
    assert user_record.email == "ada@example.com"
    assert user_record.is_email_verified is True
    assert user_record.display_name == "Ada Lovelace"
    assert user_record.avatar_url == "https://example.com/ada.png"
    assert user_record.created_by_id is None
    assert user_record.updated_by_id is None
    assert user_auth_provider_record is not None
    assert user_auth_provider_record.user_id == user_record.id
    assert user_auth_provider_record.provider == AuthProviderType.GOOGLE
    assert user_auth_provider_record.provider_subject == "google-subject-1"
    assert user_auth_provider_record.email_at_provider == "ada@example.com"
    assert user_auth_provider_record.created_by_id == user_record.id
    assert user_auth_provider_record.updated_by_id == user_record.id


async def test_find_or_create_user_from_auth_provider_new_user_sets_last_login_and_last_used_at(
    db_session: AsyncSession,
) -> None:
    signed_in_at = datetime(2026, 3, 4, 5, 6, 7, tzinfo=UTC)
    user_service = UserService(db_session=db_session)
    find_or_create_user_from_auth_provider_input = (
        build_find_or_create_user_from_auth_provider_input(
            provider_subject="google-subject-new-login", signed_in_at=signed_in_at
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
    assert user_record.last_login_at == signed_in_at
    assert user_auth_provider_record is not None
    assert user_auth_provider_record.last_used_at == signed_in_at


async def test_find_or_create_user_from_auth_provider_returning_user_updates_login_activity(
    db_session: AsyncSession,
) -> None:
    older_signed_in_at = datetime(2026, 1, 1, 0, 0, 0, tzinfo=UTC)
    newer_signed_in_at = datetime(2026, 2, 2, 0, 0, 0, tzinfo=UTC)
    user_record = await insert_user_row(db_session, last_login_at=older_signed_in_at)
    user_auth_provider_record = await insert_user_auth_provider_row(
        db_session,
        user_id=user_record.id,
        provider_subject="google-subject-returning-login",
        last_used_at=older_signed_in_at,
    )
    user_service = UserService(db_session=db_session)
    find_or_create_user_from_auth_provider_input = (
        build_find_or_create_user_from_auth_provider_input(
            provider_subject="google-subject-returning-login", signed_in_at=newer_signed_in_at
        )
    )

    await user_service.find_or_create_user_from_auth_provider(
        find_or_create_user_from_auth_provider_input
    )

    await db_session.refresh(user_record)
    await db_session.refresh(user_auth_provider_record)
    assert user_record.last_login_at == newer_signed_in_at
    assert user_auth_provider_record.last_used_at == newer_signed_in_at


async def test_find_or_create_user_from_auth_provider_existing_provider_returns_existing_user(
    db_session: AsyncSession,
) -> None:
    user_record = await insert_user_row(db_session, email="ada@example.com")
    await insert_user_auth_provider_row(
        db_session,
        user_id=user_record.id,
        provider_subject="google-subject-2",
        email_at_provider="ada@example.com",
    )
    user_service = UserService(db_session=db_session)
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
        id=user_record.id, identity=user_record.identity, is_new_user=False
    )
    assert user_auth_provider_count == 1


async def test_find_or_create_user_from_auth_provider_inactive_user_raises_forbidden_exception(
    db_session: AsyncSession,
) -> None:
    user_record = await insert_user_row(db_session, is_active=False)
    await insert_user_auth_provider_row(
        db_session, user_id=user_record.id, provider_subject="google-subject-3"
    )
    user_service = UserService(db_session=db_session)
    find_or_create_user_from_auth_provider_input = (
        build_find_or_create_user_from_auth_provider_input(provider_subject="google-subject-3")
    )

    with pytest.raises(ForbiddenException):
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
    user_service = UserService(db_session=db_session)
    find_or_create_user_from_auth_provider_input = (
        build_find_or_create_user_from_auth_provider_input(provider_subject="google-subject-4")
    )

    with pytest.raises(ForbiddenException):
        await user_service.find_or_create_user_from_auth_provider(
            find_or_create_user_from_auth_provider_input
        )


async def test_find_or_create_user_from_auth_provider_email_taken_raises_conflict_exception(
    db_session: AsyncSession,
) -> None:
    await insert_user_row(db_session, email="ada@example.com")
    user_service = UserService(db_session=db_session)
    find_or_create_user_from_auth_provider_input = (
        build_find_or_create_user_from_auth_provider_input(email="ada@example.com")
    )

    with pytest.raises(ConflictException):
        await user_service.find_or_create_user_from_auth_provider(
            find_or_create_user_from_auth_provider_input
        )


async def test_find_or_create_user_from_auth_provider_email_case_diff_raises_conflict_exception(
    db_session: AsyncSession,
) -> None:
    await insert_user_row(db_session, email="ADA@example.com")
    user_service = UserService(db_session=db_session)
    find_or_create_user_from_auth_provider_input = (
        build_find_or_create_user_from_auth_provider_input(email="ada@example.com")
    )

    with pytest.raises(ConflictException):
        await user_service.find_or_create_user_from_auth_provider(
            find_or_create_user_from_auth_provider_input
        )


async def test_find_or_create_user_from_auth_provider_email_only_on_deleted_user_creates_user(
    db_session: AsyncSession,
) -> None:
    deleted_at = datetime(2026, 1, 2, 3, 4, 5, tzinfo=UTC)
    await insert_user_row(db_session, email="ada@example.com", deleted_at=deleted_at)
    user_service = UserService(db_session=db_session)
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
    user_service = UserService(db_session=db_session)
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
    )
    user_service = UserService(db_session=db_session)

    find_user_by_identity_result = await user_service.find_user_by_identity(user_record.identity)

    assert find_user_by_identity_result == FindUserByIdentityResult(
        id=user_record.id,
        identity=user_record.identity,
        email="ada@example.com",
        is_email_verified=user_record.is_email_verified,
        display_name="Ada Lovelace",
        avatar_url=user_record.avatar_url,
        is_active=user_record.is_active,
    )


async def test_find_user_by_identity_never_inserted_raises_not_found_exception(
    db_session: AsyncSession,
) -> None:
    user_service = UserService(db_session=db_session)

    with pytest.raises(NotFoundException):
        await user_service.find_user_by_identity(uuid4())


async def test_find_user_by_identity_soft_deleted_raises_not_found_exception(
    db_session: AsyncSession,
) -> None:
    deleted_at = datetime(2026, 1, 2, 3, 4, 5, tzinfo=UTC)
    user_record = await insert_user_row(db_session, deleted_at=deleted_at)
    user_service = UserService(db_session=db_session)

    with pytest.raises(NotFoundException):
        await user_service.find_user_by_identity(user_record.identity)
