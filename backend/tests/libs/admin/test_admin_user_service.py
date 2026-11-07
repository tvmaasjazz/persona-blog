from datetime import UTC, datetime
from decimal import Decimal
from uuid import uuid4

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from libs.admin.exceptions import AdminUserNotChangeableException
from libs.admin.inputs import AdminSetUserActiveInput, AdminSetUserRoleInput
from libs.admin.results import (
    AdminFindUserPageResult,
    AdminSetUserActiveResult,
    AdminSetUserRoleResult,
    AdminUserDetailResult,
)
from libs.admin.services import AdminUserService
from libs.admin.types import AdminUserSortType
from libs.auth.results import AuthUser
from libs.core.exceptions import NotFoundException
from libs.core.results import PaginationResult
from libs.core.types import SortDirectionType
from libs.database.orm import RoleOrm, UserOrm
from libs.database.services import PaginationService
from libs.permissions.types import RoleType
from tests.factories.admin import build_admin_find_user_page_input
from tests.factories.auth import build_auth_user
from tests.factories.users import find_system_user_row, insert_user_row


@pytest.fixture
def admin_user_service(
    db_session: AsyncSession, pagination_service: PaginationService
) -> AdminUserService:
    return AdminUserService(db_session=db_session, pagination_service=pagination_service)


def _find_user_emails(admin_find_user_page_result: AdminFindUserPageResult) -> list[str]:
    return [user.email for user in admin_find_user_page_result.users]


async def test_find_user_page_returns_users_newest_first_with_role_balance_and_activity(
    db_session: AsyncSession, admin_user_service: AdminUserService
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

    admin_find_user_page_result = await admin_user_service.find_user_page(
        build_admin_find_user_page_input(page_size=5)
    )

    assert admin_find_user_page_result == AdminFindUserPageResult(
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
        ],
        pagination=PaginationResult(page=1, page_size=5, total=2),
    )


async def test_find_user_page_same_created_at_orders_by_id_descending(
    db_session: AsyncSession, admin_user_service: AdminUserService
) -> None:
    first_user_record = await insert_user_row(db_session)
    second_user_record = await insert_user_row(db_session)
    third_user_record = await insert_user_row(db_session)

    admin_find_user_page_result = await admin_user_service.find_user_page(
        build_admin_find_user_page_input()
    )

    listed_identities = [user.identity for user in admin_find_user_page_result.users]
    assert listed_identities == [
        third_user_record.identity,
        second_user_record.identity,
        first_user_record.identity,
    ]


async def test_find_user_page_excludes_system_user(
    db_session: AsyncSession, admin_user_service: AdminUserService
) -> None:
    user_record = await insert_user_row(db_session)
    system_user_record = await find_system_user_row(db_session)

    admin_find_user_page_result = await admin_user_service.find_user_page(
        build_admin_find_user_page_input()
    )

    listed_identities = [user.identity for user in admin_find_user_page_result.users]
    assert system_user_record.identity not in listed_identities
    assert listed_identities == [user_record.identity]
    assert admin_find_user_page_result.pagination.total == 1


async def test_find_user_page_excludes_soft_deleted_user_and_includes_inactive_user(
    db_session: AsyncSession, admin_user_service: AdminUserService
) -> None:
    inactive_user_record = await insert_user_row(db_session, is_active=False)
    await insert_user_row(db_session, deleted_at=datetime(2026, 1, 2, tzinfo=UTC))

    admin_find_user_page_result = await admin_user_service.find_user_page(
        build_admin_find_user_page_input()
    )

    assert [(user.identity, user.is_active) for user in admin_find_user_page_result.users] == [
        (inactive_user_record.identity, False)
    ]
    assert admin_find_user_page_result.pagination.total == 1


async def test_find_user_page_total_counts_every_user_and_pages_slice_them(
    db_session: AsyncSession, admin_user_service: AdminUserService
) -> None:
    for day, email in enumerate(["u1", "u2", "u3", "u4", "u5"], start=1):
        await insert_user_row(
            db_session,
            email=f"{email}@example.com",
            created_at=datetime(2026, 1, day, tzinfo=UTC),
        )

    admin_find_user_page_result = await admin_user_service.find_user_page(
        build_admin_find_user_page_input(page=2, page_size=2)
    )

    assert _find_user_emails(admin_find_user_page_result) == ["u3@example.com", "u2@example.com"]
    assert admin_find_user_page_result.pagination == PaginationResult(page=2, page_size=2, total=5)


async def test_find_user_page_page_past_the_end_returns_no_rows_and_same_total(
    db_session: AsyncSession, admin_user_service: AdminUserService
) -> None:
    for _ in range(3):
        await insert_user_row(db_session)

    admin_find_user_page_result = await admin_user_service.find_user_page(
        build_admin_find_user_page_input(page=3, page_size=2)
    )

    assert admin_find_user_page_result == AdminFindUserPageResult(
        users=[], pagination=PaginationResult(page=3, page_size=2, total=3)
    )


async def test_find_user_page_without_users_returns_empty_page(
    admin_user_service: AdminUserService,
) -> None:
    admin_find_user_page_result = await admin_user_service.find_user_page(
        build_admin_find_user_page_input()
    )

    assert admin_find_user_page_result == AdminFindUserPageResult(
        users=[], pagination=PaginationResult(page=1, page_size=20, total=0)
    )


@pytest.mark.parametrize(
    ("sort_by", "sort_direction", "expected_emails"),
    [
        pytest.param(
            AdminUserSortType.CREATED_AT,
            SortDirectionType.ASC,
            ["b@example.com", "c@example.com", "a@example.com"],
            id="created_at_ascending",
        ),
        pytest.param(
            AdminUserSortType.CREATED_AT,
            SortDirectionType.DESC,
            ["a@example.com", "c@example.com", "b@example.com"],
            id="created_at_descending",
        ),
        pytest.param(
            AdminUserSortType.EMAIL,
            SortDirectionType.ASC,
            ["a@example.com", "b@example.com", "c@example.com"],
            id="email_ascending",
        ),
        pytest.param(
            AdminUserSortType.EMAIL,
            SortDirectionType.DESC,
            ["c@example.com", "b@example.com", "a@example.com"],
            id="email_descending",
        ),
        pytest.param(
            AdminUserSortType.LAST_ACTIVITY_AT,
            SortDirectionType.ASC,
            ["a@example.com", "b@example.com", "c@example.com"],
            id="last_activity_at_ascending_never_active_last",
        ),
        pytest.param(
            AdminUserSortType.LAST_ACTIVITY_AT,
            SortDirectionType.DESC,
            ["b@example.com", "a@example.com", "c@example.com"],
            id="last_activity_at_descending_never_active_last",
        ),
    ],
)
async def test_find_user_page_sorted_by_each_sort_type_and_direction(
    db_session: AsyncSession,
    admin_user_service: AdminUserService,
    sort_by: AdminUserSortType,
    sort_direction: SortDirectionType,
    expected_emails: list[str],
) -> None:
    await insert_user_row(
        db_session,
        email="a@example.com",
        created_at=datetime(2026, 1, 3, tzinfo=UTC),
        last_activity_at=datetime(2026, 2, 1, tzinfo=UTC),
    )
    await insert_user_row(
        db_session,
        email="b@example.com",
        created_at=datetime(2026, 1, 1, tzinfo=UTC),
        last_activity_at=datetime(2026, 3, 1, tzinfo=UTC),
    )
    await insert_user_row(
        db_session,
        email="c@example.com",
        created_at=datetime(2026, 1, 2, tzinfo=UTC),
        last_activity_at=None,
    )

    admin_find_user_page_result = await admin_user_service.find_user_page(
        build_admin_find_user_page_input(sort_by=sort_by, sort_direction=sort_direction)
    )

    assert _find_user_emails(admin_find_user_page_result) == expected_emails


@pytest.mark.parametrize(
    ("search", "expected_emails"),
    [
        pytest.param("ada@", ["ada@example.com"], id="email"),
        pytest.param("HOPPER", ["ada@example.com"], id="display_name_ignores_case"),
        pytest.param("example", ["ada@example.com", "bob@example.com"], id="both_match"),
        pytest.param("ada hopper", ["ada@example.com"], id="every_word_must_match"),
        pytest.param("ada linus", [], id="words_matching_different_users_match_none"),
        pytest.param("%", [], id="percent_is_literal"),
        pytest.param("   ", ["ada@example.com", "bob@example.com"], id="whitespace_is_no_search"),
    ],
)
async def test_find_user_page_search(
    db_session: AsyncSession,
    admin_user_service: AdminUserService,
    search: str,
    expected_emails: list[str],
) -> None:
    await insert_user_row(db_session, email="ada@example.com", display_name="Grace Hopper")
    await insert_user_row(db_session, email="bob@example.com", display_name="Linus")

    admin_find_user_page_result = await admin_user_service.find_user_page(
        build_admin_find_user_page_input(
            search=search, sort_by=AdminUserSortType.EMAIL, sort_direction=SortDirectionType.ASC
        )
    )

    assert _find_user_emails(admin_find_user_page_result) == expected_emails


async def test_find_user_page_search_total_counts_only_matching_users(
    db_session: AsyncSession, admin_user_service: AdminUserService
) -> None:
    await insert_user_row(db_session, email="ada@example.com", display_name=None)
    await insert_user_row(db_session, email="adam@example.com", display_name=None)
    await insert_user_row(db_session, email="bob@example.com", display_name=None)

    admin_find_user_page_result = await admin_user_service.find_user_page(
        build_admin_find_user_page_input(search="ada", page_size=1)
    )

    assert len(admin_find_user_page_result.users) == 1
    assert admin_find_user_page_result.pagination == PaginationResult(page=1, page_size=1, total=2)


async def test_find_user_returns_user_detail(
    db_session: AsyncSession, admin_user_service: AdminUserService
) -> None:
    user_record = await insert_user_row(
        db_session,
        email="ada@example.com",
        display_name="Ada Lovelace",
        role=RoleType.READER,
        credit_balance_usd=Decimal("2.50"),
        is_active=False,
        last_activity_at=datetime(2026, 1, 2, 3, 4, 5, tzinfo=UTC),
    )

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
    db_session: AsyncSession, admin_user_service: AdminUserService
) -> None:

    with pytest.raises(NotFoundException):
        await admin_user_service.find_user(uuid4())


async def test_find_user_system_user_raises_not_found_exception(
    db_session: AsyncSession, admin_user_service: AdminUserService
) -> None:
    system_user_record = await find_system_user_row(db_session)

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
    db_session: AsyncSession, admin_user_service: AdminUserService
) -> None:
    admin_auth_user = await _insert_admin_auth_user(db_session)
    reader_record = await insert_user_row(db_session, role=RoleType.READER)

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
    db_session: AsyncSession, admin_user_service: AdminUserService
) -> None:
    admin_auth_user = await _insert_admin_auth_user(db_session)
    creator_record = await insert_user_row(db_session, role=RoleType.CREATOR)

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
    db_session: AsyncSession, current_role: RoleType, admin_user_service: AdminUserService
) -> None:
    admin_auth_user = await _insert_admin_auth_user(db_session)
    user_record = await insert_user_row(db_session, role=current_role)

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


async def test_set_user_role_inactive_user_changes_role(
    db_session: AsyncSession, admin_user_service: AdminUserService
) -> None:
    admin_auth_user = await _insert_admin_auth_user(db_session)
    inactive_record = await insert_user_row(db_session, role=RoleType.READER, is_active=False)

    set_user_role_result = await admin_user_service.set_user_role(
        inactive_record.identity, AdminSetUserRoleInput(role=RoleType.CREATOR), admin_auth_user
    )

    await db_session.refresh(inactive_record)
    role_code = await _find_role_code(db_session, inactive_record)
    assert set_user_role_result.is_changed is True
    assert role_code == RoleType.CREATOR
    assert inactive_record.is_active is False


async def test_set_user_role_unknown_identity_raises_not_found_exception(
    db_session: AsyncSession, admin_user_service: AdminUserService
) -> None:
    admin_auth_user = await _insert_admin_auth_user(db_session)

    with pytest.raises(NotFoundException):
        await admin_user_service.set_user_role(
            uuid4(), AdminSetUserRoleInput(role=RoleType.CREATOR), admin_auth_user
        )


async def test_set_user_role_system_user_raises_not_found_exception(
    db_session: AsyncSession, admin_user_service: AdminUserService
) -> None:
    admin_auth_user = await _insert_admin_auth_user(db_session)
    system_user_record = await find_system_user_row(db_session)

    with pytest.raises(NotFoundException):
        await admin_user_service.set_user_role(
            system_user_record.identity,
            AdminSetUserRoleInput(role=RoleType.CREATOR),
            admin_auth_user,
        )


async def test_set_user_role_admin_target_raises_not_changeable_and_keeps_role(
    db_session: AsyncSession, admin_user_service: AdminUserService
) -> None:
    admin_auth_user = await _insert_admin_auth_user(db_session)
    other_admin_record = await insert_user_row(db_session, role=RoleType.ADMIN)

    with pytest.raises(AdminUserNotChangeableException):
        await admin_user_service.set_user_role(
            other_admin_record.identity,
            AdminSetUserRoleInput(role=RoleType.READER),
            admin_auth_user,
        )

    role_code = await _find_role_code(db_session, other_admin_record)
    assert role_code == RoleType.ADMIN


async def test_set_user_active_suspend_flips_is_active_and_sets_updated_by(
    db_session: AsyncSession, admin_user_service: AdminUserService
) -> None:
    admin_auth_user = await _insert_admin_auth_user(db_session)
    user_record = await insert_user_row(db_session, role=RoleType.CREATOR)

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
    db_session: AsyncSession, admin_user_service: AdminUserService
) -> None:
    admin_auth_user = await _insert_admin_auth_user(db_session)
    suspended_record = await insert_user_row(db_session, role=RoleType.READER, is_active=False)

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
    db_session: AsyncSession, is_active: bool, admin_user_service: AdminUserService
) -> None:
    admin_auth_user = await _insert_admin_auth_user(db_session)
    user_record = await insert_user_row(db_session, is_active=is_active)

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
    db_session: AsyncSession, admin_user_service: AdminUserService
) -> None:
    admin_auth_user = await _insert_admin_auth_user(db_session)

    with pytest.raises(NotFoundException):
        await admin_user_service.set_user_active(
            uuid4(), AdminSetUserActiveInput(is_active=False), admin_auth_user
        )


async def test_set_user_active_system_user_raises_not_found_exception(
    db_session: AsyncSession, admin_user_service: AdminUserService
) -> None:
    admin_auth_user = await _insert_admin_auth_user(db_session)
    system_user_record = await find_system_user_row(db_session)

    with pytest.raises(NotFoundException):
        await admin_user_service.set_user_active(
            system_user_record.identity, AdminSetUserActiveInput(is_active=False), admin_auth_user
        )


async def test_set_user_active_admin_target_raises_not_changeable_and_stays_active(
    db_session: AsyncSession, admin_user_service: AdminUserService
) -> None:
    admin_auth_user = await _insert_admin_auth_user(db_session)
    other_admin_record = await insert_user_row(db_session, role=RoleType.ADMIN)

    with pytest.raises(AdminUserNotChangeableException):
        await admin_user_service.set_user_active(
            other_admin_record.identity, AdminSetUserActiveInput(is_active=False), admin_auth_user
        )

    await db_session.refresh(other_admin_record)
    assert other_admin_record.is_active is True
