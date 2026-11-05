from datetime import UTC, datetime
from decimal import Decimal
from uuid import uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from libs.admin.results import AdminFindUserListResult, AdminUserDetailResult
from libs.admin.services import AdminUserService
from libs.core.exceptions import NotFoundException
from libs.permissions.types import RoleType
from tests.factories.users import find_system_user_row, insert_user_row


async def test_find_user_list_returns_users_newest_first_with_role_balance_and_activity(
    db_session: AsyncSession,
) -> None:
    older_created_at = datetime(2026, 1, 1, tzinfo=UTC)
    newer_created_at = datetime(2026, 2, 1, tzinfo=UTC)
    older_user_record = await insert_user_row(
        db_session,
        email="older@example.com",
        display_name=None,
        role=RoleType.READER,
        credit_balance_usd=Decimal("1.50"),
        created_at=older_created_at,
    )
    newer_user_record = await insert_user_row(
        db_session,
        email="newer@example.com",
        display_name="Newer User",
        role=RoleType.ADMIN,
        credit_balance_usd=Decimal("7.25"),
        last_activity_at=datetime(2026, 1, 2, 3, 4, 5, tzinfo=UTC),
        created_at=newer_created_at,
    )
    admin_user_service = AdminUserService(db_session=db_session)

    find_user_list_result = await admin_user_service.find_user_list()

    assert find_user_list_result == AdminFindUserListResult(
        users=[
            AdminUserDetailResult(
                identity=newer_user_record.identity,
                email="newer@example.com",
                display_name="Newer User",
                role=RoleType.ADMIN,
                credit_balance_usd=Decimal("7.25"),
                is_active=True,
                created_at=newer_created_at,
                last_activity_at=datetime(2026, 1, 2, 3, 4, 5, tzinfo=UTC),
            ),
            AdminUserDetailResult(
                identity=older_user_record.identity,
                email="older@example.com",
                display_name=None,
                role=RoleType.READER,
                credit_balance_usd=Decimal("1.50"),
                is_active=True,
                created_at=older_created_at,
                last_activity_at=None,
            ),
        ]
    )


async def test_find_user_list_same_created_at_orders_by_id_descending(
    db_session: AsyncSession,
) -> None:
    first_user_record = await insert_user_row(db_session)
    second_user_record = await insert_user_row(db_session)
    third_user_record = await insert_user_row(db_session)
    admin_user_service = AdminUserService(db_session=db_session)

    find_user_list_result = await admin_user_service.find_user_list()

    listed_identities = [user.identity for user in find_user_list_result.users]
    assert listed_identities == [
        third_user_record.identity,
        second_user_record.identity,
        first_user_record.identity,
    ]


async def test_find_user_list_excludes_system_user(db_session: AsyncSession) -> None:
    user_record = await insert_user_row(db_session)
    system_user_record = await find_system_user_row(db_session)
    admin_user_service = AdminUserService(db_session=db_session)

    find_user_list_result = await admin_user_service.find_user_list()

    listed_identities = [user.identity for user in find_user_list_result.users]
    assert system_user_record.identity not in listed_identities
    assert listed_identities == [user_record.identity]


async def test_find_user_list_excludes_soft_deleted_user_and_includes_inactive_user(
    db_session: AsyncSession,
) -> None:
    inactive_user_record = await insert_user_row(db_session, is_active=False)
    await insert_user_row(db_session, deleted_at=datetime(2026, 1, 2, tzinfo=UTC))
    admin_user_service = AdminUserService(db_session=db_session)

    find_user_list_result = await admin_user_service.find_user_list()

    assert [(user.identity, user.is_active) for user in find_user_list_result.users] == [
        (inactive_user_record.identity, False)
    ]


async def test_find_user_returns_user_detail(db_session: AsyncSession) -> None:
    user_record = await insert_user_row(
        db_session,
        email="ada@example.com",
        display_name="Ada Lovelace",
        role=RoleType.READER,
        credit_balance_usd=Decimal("2.50"),
        is_active=False,
        last_activity_at=datetime(2026, 1, 2, 3, 4, 5, tzinfo=UTC),
    )
    admin_user_service = AdminUserService(db_session=db_session)

    find_user_result = await admin_user_service.find_user(user_record.identity)

    assert find_user_result == AdminUserDetailResult(
        identity=user_record.identity,
        email="ada@example.com",
        display_name="Ada Lovelace",
        role=RoleType.READER,
        credit_balance_usd=Decimal("2.50"),
        is_active=False,
        created_at=user_record.created_at,
        last_activity_at=datetime(2026, 1, 2, 3, 4, 5, tzinfo=UTC),
    )


async def test_find_user_unknown_identity_raises_not_found_exception(
    db_session: AsyncSession,
) -> None:
    admin_user_service = AdminUserService(db_session=db_session)

    with pytest.raises(NotFoundException):
        await admin_user_service.find_user(uuid4())


async def test_find_user_system_user_raises_not_found_exception(
    db_session: AsyncSession,
) -> None:
    system_user_record = await find_system_user_row(db_session)
    admin_user_service = AdminUserService(db_session=db_session)

    with pytest.raises(NotFoundException):
        await admin_user_service.find_user(system_user_record.identity)
