from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import uuid4

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from libs.admin.exceptions import AdminInviteUsedException
from libs.admin.inputs import AdminCreateInviteInput
from libs.admin.results import AdminFindInviteListResult, AdminInviteDetailResult
from libs.admin.services import AdminInviteService
from libs.core.exceptions import NotFoundException
from libs.database.orm import InviteOrm
from libs.invites.types import InviteStatusType
from libs.invites.utils import InviteUtils
from libs.permissions.types import RoleType
from tests.factories.auth import build_auth_user
from tests.factories.database import fetch_database_utc_now
from tests.factories.invites import insert_invite_row
from tests.factories.users import insert_user_row

FRONTEND_URL = "https://frontend.test"
PAST = datetime(2026, 1, 2, tzinfo=UTC)


@pytest.fixture
def admin_invite_service(db_session: AsyncSession) -> AdminInviteService:
    return AdminInviteService(db_session=db_session, frontend_url=FRONTEND_URL)


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


# find_invite_list


async def test_find_invite_list_returns_invites_newest_first_with_status_and_emails(
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

    admin_find_invite_list_result = await admin_invite_service.find_invite_list()

    assert admin_find_invite_list_result == AdminFindInviteListResult(
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
        ]
    )


async def test_find_invite_list_same_created_at_orders_by_id_descending(
    db_session: AsyncSession, admin_invite_service: AdminInviteService
) -> None:
    first_invite_record = await insert_invite_row(db_session)
    second_invite_record = await insert_invite_row(db_session)

    admin_find_invite_list_result = await admin_invite_service.find_invite_list()

    listed_identities = [
        admin_invite_detail_result.identity
        for admin_invite_detail_result in admin_find_invite_list_result.invites
    ]
    assert listed_identities == [second_invite_record.identity, first_invite_record.identity]


async def test_find_invite_list_without_invites_returns_empty_list(
    admin_invite_service: AdminInviteService,
) -> None:
    admin_find_invite_list_result = await admin_invite_service.find_invite_list()

    assert admin_find_invite_list_result == AdminFindInviteListResult(invites=[])


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
