from datetime import UTC, datetime
from decimal import Decimal
from uuid import uuid4

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from libs.admin.exceptions import AdminUserNotChangeableException
from libs.admin.inputs import AdminSetUserActiveInput, AdminSetUserRoleInput
from libs.admin.results import (
    AdminFindUserListResult,
    AdminSetUserActiveResult,
    AdminSetUserRoleResult,
    AdminUserDetailResult,
)
from libs.admin.services import AdminUserService
from libs.auth.results import AuthUser
from libs.core.exceptions import NotFoundException
from libs.database.orm import RoleOrm, UserOrm
from libs.permissions.types import RoleType
from tests.factories.auth import build_auth_user
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


async def _insert_admin_auth_user(db_session: AsyncSession) -> AuthUser:
    admin_record = await insert_user_row(db_session, role=RoleType.ADMIN)
    return build_auth_user(
        user_id=admin_record.id, user_identity=admin_record.identity, role=RoleType.ADMIN
    )


async def _find_role_code(db_session: AsyncSession, user_record: UserOrm) -> RoleType:
    role_code_query = select(RoleOrm.code).join(UserOrm, UserOrm.role_id == RoleOrm.id)
    role_code = await db_session.scalar(role_code_query.where(UserOrm.id == user_record.id))
    assert role_code is not None
    return role_code


async def test_set_user_role_reader_to_creator_changes_role_and_sets_updated_by(
    db_session: AsyncSession,
) -> None:
    admin_auth_user = await _insert_admin_auth_user(db_session)
    reader_record = await insert_user_row(db_session, role=RoleType.READER)
    admin_user_service = AdminUserService(db_session=db_session)

    set_user_role_result = await admin_user_service.set_user_role(
        reader_record.identity, AdminSetUserRoleInput(role=RoleType.CREATOR), admin_auth_user
    )

    await db_session.refresh(reader_record)
    role_code = await _find_role_code(db_session, reader_record)
    assert set_user_role_result == AdminSetUserRoleResult(
        user_id=reader_record.id, is_changed=True, is_demoted_to_reader=False
    )
    assert role_code == RoleType.CREATOR
    assert reader_record.updated_by_id == admin_auth_user.id


async def test_set_user_role_creator_to_reader_changes_role_and_reports_demotion(
    db_session: AsyncSession,
) -> None:
    admin_auth_user = await _insert_admin_auth_user(db_session)
    creator_record = await insert_user_row(db_session, role=RoleType.CREATOR)
    admin_user_service = AdminUserService(db_session=db_session)

    set_user_role_result = await admin_user_service.set_user_role(
        creator_record.identity, AdminSetUserRoleInput(role=RoleType.READER), admin_auth_user
    )

    await db_session.refresh(creator_record)
    role_code = await _find_role_code(db_session, creator_record)
    assert set_user_role_result == AdminSetUserRoleResult(
        user_id=creator_record.id, is_changed=True, is_demoted_to_reader=True
    )
    assert role_code == RoleType.READER
    assert creator_record.updated_by_id == admin_auth_user.id


@pytest.mark.parametrize("current_role", [RoleType.READER, RoleType.CREATOR])
async def test_set_user_role_same_role_changes_nothing(
    db_session: AsyncSession, current_role: RoleType
) -> None:
    admin_auth_user = await _insert_admin_auth_user(db_session)
    user_record = await insert_user_row(db_session, role=current_role)
    admin_user_service = AdminUserService(db_session=db_session)

    set_user_role_result = await admin_user_service.set_user_role(
        user_record.identity, AdminSetUserRoleInput(role=current_role), admin_auth_user
    )

    await db_session.refresh(user_record)
    role_code = await _find_role_code(db_session, user_record)
    assert set_user_role_result == AdminSetUserRoleResult(
        user_id=user_record.id, is_changed=False, is_demoted_to_reader=False
    )
    assert role_code == current_role
    assert user_record.updated_by_id is None


async def test_set_user_role_inactive_user_changes_role(db_session: AsyncSession) -> None:
    admin_auth_user = await _insert_admin_auth_user(db_session)
    inactive_record = await insert_user_row(db_session, role=RoleType.READER, is_active=False)
    admin_user_service = AdminUserService(db_session=db_session)

    set_user_role_result = await admin_user_service.set_user_role(
        inactive_record.identity, AdminSetUserRoleInput(role=RoleType.CREATOR), admin_auth_user
    )

    await db_session.refresh(inactive_record)
    role_code = await _find_role_code(db_session, inactive_record)
    assert set_user_role_result.is_changed is True
    assert role_code == RoleType.CREATOR
    assert inactive_record.is_active is False


async def test_set_user_role_unknown_identity_raises_not_found_exception(
    db_session: AsyncSession,
) -> None:
    admin_auth_user = await _insert_admin_auth_user(db_session)
    admin_user_service = AdminUserService(db_session=db_session)

    with pytest.raises(NotFoundException):
        await admin_user_service.set_user_role(
            uuid4(), AdminSetUserRoleInput(role=RoleType.CREATOR), admin_auth_user
        )


async def test_set_user_role_system_user_raises_not_found_exception(
    db_session: AsyncSession,
) -> None:
    admin_auth_user = await _insert_admin_auth_user(db_session)
    system_user_record = await find_system_user_row(db_session)
    admin_user_service = AdminUserService(db_session=db_session)

    with pytest.raises(NotFoundException):
        await admin_user_service.set_user_role(
            system_user_record.identity,
            AdminSetUserRoleInput(role=RoleType.CREATOR),
            admin_auth_user,
        )


async def test_set_user_role_admin_target_raises_not_changeable_and_keeps_role(
    db_session: AsyncSession,
) -> None:
    admin_auth_user = await _insert_admin_auth_user(db_session)
    other_admin_record = await insert_user_row(db_session, role=RoleType.ADMIN)
    admin_user_service = AdminUserService(db_session=db_session)

    with pytest.raises(AdminUserNotChangeableException):
        await admin_user_service.set_user_role(
            other_admin_record.identity,
            AdminSetUserRoleInput(role=RoleType.READER),
            admin_auth_user,
        )

    role_code = await _find_role_code(db_session, other_admin_record)
    assert role_code == RoleType.ADMIN


async def test_set_user_active_suspend_flips_is_active_and_sets_updated_by(
    db_session: AsyncSession,
) -> None:
    admin_auth_user = await _insert_admin_auth_user(db_session)
    user_record = await insert_user_row(db_session, role=RoleType.CREATOR)
    admin_user_service = AdminUserService(db_session=db_session)

    set_user_active_result = await admin_user_service.set_user_active(
        user_record.identity, AdminSetUserActiveInput(is_active=False), admin_auth_user
    )

    await db_session.refresh(user_record)
    assert set_user_active_result == AdminSetUserActiveResult(
        user_id=user_record.id, is_changed=True
    )
    assert user_record.is_active is False
    assert user_record.updated_by_id == admin_auth_user.id


async def test_set_user_active_reactivate_flips_is_active_and_keeps_role(
    db_session: AsyncSession,
) -> None:
    admin_auth_user = await _insert_admin_auth_user(db_session)
    suspended_record = await insert_user_row(db_session, role=RoleType.READER, is_active=False)
    admin_user_service = AdminUserService(db_session=db_session)

    set_user_active_result = await admin_user_service.set_user_active(
        suspended_record.identity, AdminSetUserActiveInput(is_active=True), admin_auth_user
    )

    await db_session.refresh(suspended_record)
    role_code = await _find_role_code(db_session, suspended_record)
    assert set_user_active_result == AdminSetUserActiveResult(
        user_id=suspended_record.id, is_changed=True
    )
    assert suspended_record.is_active is True
    assert role_code == RoleType.READER


@pytest.mark.parametrize("is_active", [True, False])
async def test_set_user_active_same_value_changes_nothing(
    db_session: AsyncSession, is_active: bool
) -> None:
    admin_auth_user = await _insert_admin_auth_user(db_session)
    user_record = await insert_user_row(db_session, is_active=is_active)
    admin_user_service = AdminUserService(db_session=db_session)

    set_user_active_result = await admin_user_service.set_user_active(
        user_record.identity, AdminSetUserActiveInput(is_active=is_active), admin_auth_user
    )

    await db_session.refresh(user_record)
    assert set_user_active_result == AdminSetUserActiveResult(
        user_id=user_record.id, is_changed=False
    )
    assert user_record.is_active is is_active
    assert user_record.updated_by_id is None


async def test_set_user_active_unknown_identity_raises_not_found_exception(
    db_session: AsyncSession,
) -> None:
    admin_auth_user = await _insert_admin_auth_user(db_session)
    admin_user_service = AdminUserService(db_session=db_session)

    with pytest.raises(NotFoundException):
        await admin_user_service.set_user_active(
            uuid4(), AdminSetUserActiveInput(is_active=False), admin_auth_user
        )


async def test_set_user_active_system_user_raises_not_found_exception(
    db_session: AsyncSession,
) -> None:
    admin_auth_user = await _insert_admin_auth_user(db_session)
    system_user_record = await find_system_user_row(db_session)
    admin_user_service = AdminUserService(db_session=db_session)

    with pytest.raises(NotFoundException):
        await admin_user_service.set_user_active(
            system_user_record.identity, AdminSetUserActiveInput(is_active=False), admin_auth_user
        )


async def test_set_user_active_admin_target_raises_not_changeable_and_stays_active(
    db_session: AsyncSession,
) -> None:
    admin_auth_user = await _insert_admin_auth_user(db_session)
    other_admin_record = await insert_user_row(db_session, role=RoleType.ADMIN)
    admin_user_service = AdminUserService(db_session=db_session)

    with pytest.raises(AdminUserNotChangeableException):
        await admin_user_service.set_user_active(
            other_admin_record.identity, AdminSetUserActiveInput(is_active=False), admin_auth_user
        )

    await db_session.refresh(other_admin_record)
    assert other_admin_record.is_active is True
