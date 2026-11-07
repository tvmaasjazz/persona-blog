from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import uuid4

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from libs.admin.exceptions import AdminInviteUsedException
from libs.admin.inputs import AdminCreateInviteInput
from libs.admin.results import AdminFindInvitePageResult, AdminInviteDetailResult
from libs.admin.services import AdminInviteService
from libs.admin.types import AdminInviteSortType
from libs.core.exceptions import NotFoundException
from libs.core.results import PaginationResult
from libs.core.types import SortDirectionType
from libs.database.orm import InviteOrm
from libs.database.services import PaginationService
from libs.invites.types import InviteStatusType
from libs.invites.utils import InviteUtils
from libs.permissions.types import RoleType
from tests.factories.admin import build_admin_find_invite_page_input
from tests.factories.auth import build_auth_user
from tests.factories.database import fetch_database_utc_now
from tests.factories.invites import insert_invite_row
from tests.factories.users import insert_user_row

FRONTEND_URL = "https://frontend.test"
PAST = datetime(2026, 1, 2, tzinfo=UTC)


@pytest.fixture
def admin_invite_service(
    db_session: AsyncSession, pagination_service: PaginationService
) -> AdminInviteService:
    return AdminInviteService(
        db_session=db_session, frontend_url=FRONTEND_URL, pagination_service=pagination_service
    )


# create_invite


async def test_create_invite_returns_identity_and_link_and_stores_only_the_code_hash(
    db_session: AsyncSession, admin_invite_service: AdminInviteService
) -> None:
    admin_record = await insert_user_row(db_session, role=RoleType.ADMIN)
    admin_auth_user = build_auth_user(
        user_id=admin_record.id, user_identity=admin_record.identity, role=RoleType.ADMIN
    )
    admin_create_invite_input = AdminCreateInviteInput(
        name="Ada's friends",
        credit_amount_usd=Decimal("7.50"),
        note="Welcome",
        expires_in_days=7,
    )

    admin_create_invite_result = await admin_invite_service.create_invite(
        admin_create_invite_input, admin_auth_user
    )

    invite_query = select(InviteOrm).where(
        InviteOrm.identity == admin_create_invite_result.identity
    )
    invite_record = await db_session.scalar(invite_query)
    assert invite_record is not None
    assert admin_create_invite_result.invite_url.startswith(f"{FRONTEND_URL}/invite/")
    invite_code = admin_create_invite_result.invite_url.removeprefix(f"{FRONTEND_URL}/invite/")
    stored_column_values = [
        str(getattr(invite_record, column.key)) for column in InviteOrm.__table__.columns
    ]
    assert invite_record.code_hash == InviteUtils.hash_code(invite_code)
    assert all(invite_code not in stored_value for stored_value in stored_column_values)
    assert invite_record.name == "Ada's friends"
    assert invite_record.credit_amount_usd == Decimal("7.50")
    assert invite_record.note == "Welcome"
    assert invite_record.created_by_id == admin_record.id
    assert invite_record.updated_by_id == admin_record.id
    assert invite_record.used_at is None
    assert invite_record.revoked_at is None


@pytest.mark.parametrize("expires_in_days", [1, 7, 30])
async def test_create_invite_expires_after_the_given_days(
    db_session: AsyncSession, admin_invite_service: AdminInviteService, expires_in_days: int
) -> None:
    admin_record = await insert_user_row(db_session, role=RoleType.ADMIN)
    admin_auth_user = build_auth_user(
        user_id=admin_record.id, user_identity=admin_record.identity, role=RoleType.ADMIN
    )
    admin_create_invite_input = AdminCreateInviteInput(
        name="Ada's friends",
        credit_amount_usd=Decimal("5.00"),
        note=None,
        expires_in_days=expires_in_days,
    )

    admin_create_invite_result = await admin_invite_service.create_invite(
        admin_create_invite_input, admin_auth_user
    )

    invite_query = select(InviteOrm.expires_at).where(
        InviteOrm.identity == admin_create_invite_result.identity
    )
    expires_at = await db_session.scalar(invite_query)
    database_utc_now = await fetch_database_utc_now(db_session)
    assert expires_at == database_utc_now + timedelta(days=expires_in_days)


async def test_create_invite_two_calls_produce_different_links(
    db_session: AsyncSession, admin_invite_service: AdminInviteService
) -> None:
    admin_record = await insert_user_row(db_session, role=RoleType.ADMIN)
    admin_auth_user = build_auth_user(
        user_id=admin_record.id, user_identity=admin_record.identity, role=RoleType.ADMIN
    )
    admin_create_invite_input = AdminCreateInviteInput(
        name="Ada's friends", credit_amount_usd=Decimal("5.00"), note=None, expires_in_days=7
    )

    first_create_invite_result = await admin_invite_service.create_invite(
        admin_create_invite_input, admin_auth_user
    )
    second_create_invite_result = await admin_invite_service.create_invite(
        admin_create_invite_input, admin_auth_user
    )

    assert first_create_invite_result.invite_url != second_create_invite_result.invite_url


# find_invite_page


def _find_invite_names(admin_find_invite_page_result: AdminFindInvitePageResult) -> list[str]:
    return [invite.name for invite in admin_find_invite_page_result.invites]


async def test_find_invite_page_returns_invites_newest_first_with_status_and_emails(
    db_session: AsyncSession, admin_invite_service: AdminInviteService
) -> None:
    admin_record = await insert_user_row(db_session, email="admin@example.com", role=RoleType.ADMIN)
    user_record = await insert_user_row(db_session, email="ada@example.com")
    unused_invite_record = await insert_invite_row(
        db_session,
        name="Unused",
        credit_amount_usd=Decimal("1.00"),
        note="Hello",
        created_by_id=admin_record.id,
        created_at=datetime(2026, 1, 4, tzinfo=UTC),
    )
    used_invite_record = await insert_invite_row(
        db_session,
        name="Used",
        used_at=datetime(2026, 1, 5, tzinfo=UTC),
        used_by_user_id=user_record.id,
        created_by_id=admin_record.id,
        created_at=datetime(2026, 1, 3, tzinfo=UTC),
    )
    expired_invite_record = await insert_invite_row(
        db_session,
        name="Expired",
        expires_at=PAST,
        created_by_id=admin_record.id,
        created_at=datetime(2026, 1, 2, tzinfo=UTC),
    )
    revoked_invite_record = await insert_invite_row(
        db_session,
        name="Revoked",
        revoked_at=datetime(2026, 1, 6, tzinfo=UTC),
        created_by_id=admin_record.id,
        created_at=datetime(2026, 1, 1, tzinfo=UTC),
    )

    admin_find_invite_page_result = await admin_invite_service.find_invite_page(
        build_admin_find_invite_page_input(page_size=10)
    )

    assert admin_find_invite_page_result == AdminFindInvitePageResult(
        invites=[
            AdminInviteDetailResult(
                identity=unused_invite_record.identity,
                name="Unused",
                credit_amount_usd=Decimal("1.00"),
                note="Hello",
                status=InviteStatusType.UNUSED,
                expires_at=datetime(2099, 1, 1, tzinfo=UTC),
                used_at=None,
                used_by_email=None,
                revoked_at=None,
                created_at=datetime(2026, 1, 4, tzinfo=UTC),
                created_by_email="admin@example.com",
            ),
            AdminInviteDetailResult(
                identity=used_invite_record.identity,
                name="Used",
                credit_amount_usd=Decimal("5.00"),
                note=None,
                status=InviteStatusType.USED,
                expires_at=datetime(2099, 1, 1, tzinfo=UTC),
                used_at=datetime(2026, 1, 5, tzinfo=UTC),
                used_by_email="ada@example.com",
                revoked_at=None,
                created_at=datetime(2026, 1, 3, tzinfo=UTC),
                created_by_email="admin@example.com",
            ),
            AdminInviteDetailResult(
                identity=expired_invite_record.identity,
                name="Expired",
                credit_amount_usd=Decimal("5.00"),
                note=None,
                status=InviteStatusType.EXPIRED,
                expires_at=PAST,
                used_at=None,
                used_by_email=None,
                revoked_at=None,
                created_at=datetime(2026, 1, 2, tzinfo=UTC),
                created_by_email="admin@example.com",
            ),
            AdminInviteDetailResult(
                identity=revoked_invite_record.identity,
                name="Revoked",
                credit_amount_usd=Decimal("5.00"),
                note=None,
                status=InviteStatusType.REVOKED,
                expires_at=datetime(2099, 1, 1, tzinfo=UTC),
                used_at=None,
                used_by_email=None,
                revoked_at=datetime(2026, 1, 6, tzinfo=UTC),
                created_at=datetime(2026, 1, 1, tzinfo=UTC),
                created_by_email="admin@example.com",
            ),
        ],
        pagination=PaginationResult(page=1, page_size=10, total=4),
    )


async def test_find_invite_page_revoked_and_used_win_over_expired(
    db_session: AsyncSession, admin_invite_service: AdminInviteService
) -> None:
    user_record = await insert_user_row(db_session)
    await insert_invite_row(
        db_session,
        name="Revoked And Expired",
        expires_at=PAST,
        revoked_at=PAST,
        created_at=datetime(2026, 1, 2, tzinfo=UTC),
    )
    await insert_invite_row(
        db_session,
        name="Used And Expired",
        expires_at=PAST,
        used_at=PAST,
        used_by_user_id=user_record.id,
        created_at=datetime(2026, 1, 1, tzinfo=UTC),
    )

    admin_find_invite_page_result = await admin_invite_service.find_invite_page(
        build_admin_find_invite_page_input()
    )

    assert [(invite.name, invite.status) for invite in admin_find_invite_page_result.invites] == [
        ("Revoked And Expired", InviteStatusType.REVOKED),
        ("Used And Expired", InviteStatusType.USED),
    ]


async def test_find_invite_page_same_created_at_orders_by_id_descending(
    db_session: AsyncSession, admin_invite_service: AdminInviteService
) -> None:
    first_invite_record = await insert_invite_row(db_session)
    second_invite_record = await insert_invite_row(db_session)

    admin_find_invite_page_result = await admin_invite_service.find_invite_page(
        build_admin_find_invite_page_input()
    )

    listed_identities = [
        admin_invite_detail_result.identity
        for admin_invite_detail_result in admin_find_invite_page_result.invites
    ]
    assert listed_identities == [second_invite_record.identity, first_invite_record.identity]


async def test_find_invite_page_without_invites_returns_empty_page(
    admin_invite_service: AdminInviteService,
) -> None:
    admin_find_invite_page_result = await admin_invite_service.find_invite_page(
        build_admin_find_invite_page_input()
    )

    assert admin_find_invite_page_result == AdminFindInvitePageResult(
        invites=[], pagination=PaginationResult(page=1, page_size=20, total=0)
    )


async def test_find_invite_page_total_counts_every_invite_and_pages_slice_them(
    db_session: AsyncSession, admin_invite_service: AdminInviteService
) -> None:
    for day, name in enumerate(["Invite 1", "Invite 2", "Invite 3", "Invite 4", "Invite 5"], 1):
        await insert_invite_row(
            db_session, name=name, created_at=datetime(2026, 1, day, tzinfo=UTC)
        )

    admin_find_invite_page_result = await admin_invite_service.find_invite_page(
        build_admin_find_invite_page_input(page=2, page_size=2)
    )

    assert _find_invite_names(admin_find_invite_page_result) == ["Invite 3", "Invite 2"]
    assert admin_find_invite_page_result.pagination == PaginationResult(
        page=2, page_size=2, total=5
    )


async def test_find_invite_page_page_past_the_end_returns_no_rows_and_same_total(
    db_session: AsyncSession, admin_invite_service: AdminInviteService
) -> None:
    for _ in range(3):
        await insert_invite_row(db_session)

    admin_find_invite_page_result = await admin_invite_service.find_invite_page(
        build_admin_find_invite_page_input(page=3, page_size=2)
    )

    assert admin_find_invite_page_result == AdminFindInvitePageResult(
        invites=[], pagination=PaginationResult(page=3, page_size=2, total=3)
    )


@pytest.mark.parametrize(
    ("sort_by", "sort_direction", "expected_names"),
    [
        pytest.param(
            AdminInviteSortType.CREATED_AT,
            SortDirectionType.ASC,
            ["Banana", "Cherry", "Apple"],
            id="created_at_ascending",
        ),
        pytest.param(
            AdminInviteSortType.CREATED_AT,
            SortDirectionType.DESC,
            ["Apple", "Cherry", "Banana"],
            id="created_at_descending",
        ),
        pytest.param(
            AdminInviteSortType.NAME,
            SortDirectionType.ASC,
            ["Apple", "Banana", "Cherry"],
            id="name_ascending",
        ),
        pytest.param(
            AdminInviteSortType.NAME,
            SortDirectionType.DESC,
            ["Cherry", "Banana", "Apple"],
            id="name_descending",
        ),
        pytest.param(
            AdminInviteSortType.EXPIRES_AT,
            SortDirectionType.ASC,
            ["Cherry", "Apple", "Banana"],
            id="expires_at_ascending",
        ),
        pytest.param(
            AdminInviteSortType.EXPIRES_AT,
            SortDirectionType.DESC,
            ["Banana", "Apple", "Cherry"],
            id="expires_at_descending",
        ),
    ],
)
async def test_find_invite_page_sorted_by_each_sort_type_and_direction(
    db_session: AsyncSession,
    admin_invite_service: AdminInviteService,
    sort_by: AdminInviteSortType,
    sort_direction: SortDirectionType,
    expected_names: list[str],
) -> None:
    await insert_invite_row(
        db_session,
        name="Apple",
        created_at=datetime(2026, 1, 3, tzinfo=UTC),
        expires_at=datetime(2099, 2, 1, tzinfo=UTC),
    )
    await insert_invite_row(
        db_session,
        name="Banana",
        created_at=datetime(2026, 1, 1, tzinfo=UTC),
        expires_at=datetime(2099, 3, 1, tzinfo=UTC),
    )
    await insert_invite_row(
        db_session,
        name="Cherry",
        created_at=datetime(2026, 1, 2, tzinfo=UTC),
        expires_at=datetime(2099, 1, 1, tzinfo=UTC),
    )

    admin_find_invite_page_result = await admin_invite_service.find_invite_page(
        build_admin_find_invite_page_input(sort_by=sort_by, sort_direction=sort_direction)
    )

    assert _find_invite_names(admin_find_invite_page_result) == expected_names


@pytest.mark.parametrize(
    ("search", "expected_names"),
    [
        pytest.param("friends", ["Ada's friends"], id="name"),
        pytest.param("BETA", ["Beta testers"], id="ignores_case"),
        pytest.param("note", [], id="note_is_not_searched"),
        pytest.param("%", [], id="percent_is_literal"),
        pytest.param("   ", ["Ada's friends", "Beta testers"], id="whitespace_is_no_search"),
    ],
)
async def test_find_invite_page_search(
    db_session: AsyncSession,
    admin_invite_service: AdminInviteService,
    search: str,
    expected_names: list[str],
) -> None:
    await insert_invite_row(db_session, name="Ada's friends", note="A note")
    await insert_invite_row(db_session, name="Beta testers")

    admin_find_invite_page_result = await admin_invite_service.find_invite_page(
        build_admin_find_invite_page_input(
            search=search, sort_by=AdminInviteSortType.NAME, sort_direction=SortDirectionType.ASC
        )
    )

    assert _find_invite_names(admin_find_invite_page_result) == expected_names


async def test_find_invite_page_search_total_counts_only_matching_invites(
    db_session: AsyncSession, admin_invite_service: AdminInviteService
) -> None:
    await insert_invite_row(db_session, name="Beta one")
    await insert_invite_row(db_session, name="Beta two")
    await insert_invite_row(db_session, name="Other")

    admin_find_invite_page_result = await admin_invite_service.find_invite_page(
        build_admin_find_invite_page_input(search="beta", page_size=1)
    )

    assert len(admin_find_invite_page_result.invites) == 1
    assert admin_find_invite_page_result.pagination == PaginationResult(
        page=1, page_size=1, total=2
    )


# revoke_invite


async def test_revoke_invite_unused_invite_sets_revoked_at_to_database_now(
    db_session: AsyncSession, admin_invite_service: AdminInviteService
) -> None:
    admin_record = await insert_user_row(db_session, role=RoleType.ADMIN)
    admin_auth_user = build_auth_user(
        user_id=admin_record.id, user_identity=admin_record.identity, role=RoleType.ADMIN
    )
    invite_record = await insert_invite_row(db_session)

    await admin_invite_service.revoke_invite(invite_record.identity, admin_auth_user)

    await db_session.refresh(invite_record)
    database_utc_now = await fetch_database_utc_now(db_session)
    assert invite_record.revoked_at == database_utc_now
    assert invite_record.updated_by_id == admin_record.id


async def test_revoke_invite_expired_invite_is_revoked(
    db_session: AsyncSession, admin_invite_service: AdminInviteService
) -> None:
    admin_record = await insert_user_row(db_session, role=RoleType.ADMIN)
    admin_auth_user = build_auth_user(
        user_id=admin_record.id, user_identity=admin_record.identity, role=RoleType.ADMIN
    )
    invite_record = await insert_invite_row(db_session, expires_at=PAST)

    await admin_invite_service.revoke_invite(invite_record.identity, admin_auth_user)

    await db_session.refresh(invite_record)
    assert invite_record.revoked_at is not None


async def test_revoke_invite_already_revoked_invite_is_left_unchanged(
    db_session: AsyncSession, admin_invite_service: AdminInviteService
) -> None:
    admin_record = await insert_user_row(db_session, role=RoleType.ADMIN)
    admin_auth_user = build_auth_user(
        user_id=admin_record.id, user_identity=admin_record.identity, role=RoleType.ADMIN
    )
    invite_record = await insert_invite_row(db_session, revoked_at=PAST)

    await admin_invite_service.revoke_invite(invite_record.identity, admin_auth_user)

    await db_session.refresh(invite_record)
    assert invite_record.revoked_at == PAST
    assert invite_record.updated_by_id != admin_record.id


async def test_revoke_invite_used_invite_raises_admin_invite_used_exception(
    db_session: AsyncSession, admin_invite_service: AdminInviteService
) -> None:
    admin_record = await insert_user_row(db_session, role=RoleType.ADMIN)
    admin_auth_user = build_auth_user(
        user_id=admin_record.id, user_identity=admin_record.identity, role=RoleType.ADMIN
    )
    user_record = await insert_user_row(db_session)
    invite_record = await insert_invite_row(
        db_session, used_at=PAST, used_by_user_id=user_record.id
    )

    with pytest.raises(AdminInviteUsedException):
        await admin_invite_service.revoke_invite(invite_record.identity, admin_auth_user)

    await db_session.refresh(invite_record)
    assert invite_record.revoked_at is None


async def test_revoke_invite_unknown_identity_raises_not_found_exception(
    db_session: AsyncSession, admin_invite_service: AdminInviteService
) -> None:
    admin_record = await insert_user_row(db_session, role=RoleType.ADMIN)
    admin_auth_user = build_auth_user(
        user_id=admin_record.id, user_identity=admin_record.identity, role=RoleType.ADMIN
    )

    with pytest.raises(NotFoundException):
        await admin_invite_service.revoke_invite(uuid4(), admin_auth_user)
