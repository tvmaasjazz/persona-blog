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
    find_or_create_input = build_find_or_create_user_from_auth_provider_input(
        provider_subject="google-subject-1",
        email="ada@example.com",
        is_email_verified=True,
        display_name="Ada Lovelace",
        avatar_url="https://example.com/ada.png",
    )

    find_or_create_result = await user_service.find_or_create_user_from_auth_provider(
        find_or_create_input
    )

    user_query = select(UserOrm).where(UserOrm.id == find_or_create_result.id)
    user_orm = await db_session.scalar(user_query)
    user_auth_provider_query = select(UserAuthProviderOrm).where(
        UserAuthProviderOrm.user_id == find_or_create_result.id
    )
    user_auth_provider_orm = await db_session.scalar(user_auth_provider_query)
    assert find_or_create_result == FindOrCreateUserFromAuthProviderResult(
        id=user_orm.id, identity=user_orm.identity, is_new_user=True
    )
    assert user_orm is not None
    assert user_orm.email == "ada@example.com"
    assert user_orm.is_email_verified is True
    assert user_orm.display_name == "Ada Lovelace"
    assert user_orm.avatar_url == "https://example.com/ada.png"
    assert user_orm.created_by_id is None
    assert user_orm.updated_by_id is None
    assert user_auth_provider_orm is not None
    assert user_auth_provider_orm.user_id == user_orm.id
    assert user_auth_provider_orm.provider == AuthProviderType.GOOGLE
    assert user_auth_provider_orm.provider_subject == "google-subject-1"
    assert user_auth_provider_orm.email_at_provider == "ada@example.com"
    assert user_auth_provider_orm.created_by_id == user_orm.id
    assert user_auth_provider_orm.updated_by_id == user_orm.id


async def test_find_or_create_user_from_auth_provider_existing_provider_returns_existing_user(
    db_session: AsyncSession,
) -> None:
    user_orm = await insert_user_row(db_session, email="ada@example.com")
    await insert_user_auth_provider_row(
        db_session,
        user_id=user_orm.id,
        provider_subject="google-subject-2",
        email_at_provider="ada@example.com",
    )
    user_service = UserService(db_session=db_session)
    find_or_create_input = build_find_or_create_user_from_auth_provider_input(
        provider_subject="google-subject-2"
    )

    find_or_create_result = await user_service.find_or_create_user_from_auth_provider(
        find_or_create_input
    )

    user_auth_provider_count_query = select(func.count(UserAuthProviderOrm.id)).where(
        UserAuthProviderOrm.provider_subject == "google-subject-2"
    )
    user_auth_provider_count = await db_session.scalar(user_auth_provider_count_query)
    assert find_or_create_result == FindOrCreateUserFromAuthProviderResult(
        id=user_orm.id, identity=user_orm.identity, is_new_user=False
    )
    assert user_auth_provider_count == 1


async def test_find_or_create_user_from_auth_provider_inactive_user_raises_forbidden_exception(
    db_session: AsyncSession,
) -> None:
    user_orm = await insert_user_row(db_session, is_active=False)
    await insert_user_auth_provider_row(
        db_session, user_id=user_orm.id, provider_subject="google-subject-3"
    )
    user_service = UserService(db_session=db_session)
    find_or_create_input = build_find_or_create_user_from_auth_provider_input(
        provider_subject="google-subject-3"
    )

    with pytest.raises(ForbiddenException):
        await user_service.find_or_create_user_from_auth_provider(find_or_create_input)


async def test_find_or_create_user_from_auth_provider_soft_deleted_user_raises_forbidden_exception(
    db_session: AsyncSession,
) -> None:
    deleted_at = datetime(2026, 1, 2, 3, 4, 5, tzinfo=UTC)
    user_orm = await insert_user_row(db_session, deleted_at=deleted_at)
    await insert_user_auth_provider_row(
        db_session, user_id=user_orm.id, provider_subject="google-subject-4"
    )
    user_service = UserService(db_session=db_session)
    find_or_create_input = build_find_or_create_user_from_auth_provider_input(
        provider_subject="google-subject-4"
    )

    with pytest.raises(ForbiddenException):
        await user_service.find_or_create_user_from_auth_provider(find_or_create_input)


async def test_find_or_create_user_from_auth_provider_email_taken_raises_conflict_exception(
    db_session: AsyncSession,
) -> None:
    await insert_user_row(db_session, email="ada@example.com")
    user_service = UserService(db_session=db_session)
    find_or_create_input = build_find_or_create_user_from_auth_provider_input(
        email="ada@example.com"
    )

    with pytest.raises(ConflictException):
        await user_service.find_or_create_user_from_auth_provider(find_or_create_input)


async def test_find_or_create_user_from_auth_provider_email_case_diff_raises_conflict_exception(
    db_session: AsyncSession,
) -> None:
    await insert_user_row(db_session, email="ADA@example.com")
    user_service = UserService(db_session=db_session)
    find_or_create_input = build_find_or_create_user_from_auth_provider_input(
        email="ada@example.com"
    )

    with pytest.raises(ConflictException):
        await user_service.find_or_create_user_from_auth_provider(find_or_create_input)


async def test_find_or_create_user_from_auth_provider_email_only_on_deleted_user_creates_user(
    db_session: AsyncSession,
) -> None:
    deleted_at = datetime(2026, 1, 2, 3, 4, 5, tzinfo=UTC)
    await insert_user_row(db_session, email="ada@example.com", deleted_at=deleted_at)
    user_service = UserService(db_session=db_session)
    find_or_create_input = build_find_or_create_user_from_auth_provider_input(
        email="ada@example.com"
    )

    find_or_create_result = await user_service.find_or_create_user_from_auth_provider(
        find_or_create_input
    )

    assert find_or_create_result.is_new_user is True


async def test_find_or_create_user_from_auth_provider_soft_deleted_provider_row_creates_new_user(
    db_session: AsyncSession,
) -> None:
    deleted_at = datetime(2026, 1, 2, 3, 4, 5, tzinfo=UTC)
    existing_user_orm = await insert_user_row(db_session)
    await insert_user_auth_provider_row(
        db_session,
        user_id=existing_user_orm.id,
        provider_subject="google-subject-5",
        deleted_at=deleted_at,
    )
    user_service = UserService(db_session=db_session)
    find_or_create_input = build_find_or_create_user_from_auth_provider_input(
        provider_subject="google-subject-5"
    )

    find_or_create_result = await user_service.find_or_create_user_from_auth_provider(
        find_or_create_input
    )

    assert find_or_create_result.is_new_user is True
    assert find_or_create_result.id != existing_user_orm.id
    user_auth_provider_query = select(UserAuthProviderOrm).where(
        UserAuthProviderOrm.user_id == find_or_create_result.id
    )
    new_user_auth_provider_orm = await db_session.scalar(user_auth_provider_query)
    assert new_user_auth_provider_orm is not None
    assert new_user_auth_provider_orm.provider_subject == "google-subject-5"


async def test_find_user_by_identity_returns_user(db_session: AsyncSession) -> None:
    user_orm = await insert_user_row(
        db_session,
        email="ada@example.com",
        display_name="Ada Lovelace",
    )
    user_service = UserService(db_session=db_session)

    find_user_by_identity_result = await user_service.find_user_by_identity(user_orm.identity)

    assert find_user_by_identity_result == FindUserByIdentityResult(
        id=user_orm.id,
        identity=user_orm.identity,
        email="ada@example.com",
        is_email_verified=user_orm.is_email_verified,
        display_name="Ada Lovelace",
        avatar_url=user_orm.avatar_url,
        is_active=user_orm.is_active,
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
    user_orm = await insert_user_row(db_session, deleted_at=deleted_at)
    user_service = UserService(db_session=db_session)

    with pytest.raises(NotFoundException):
        await user_service.find_user_by_identity(user_orm.identity)
