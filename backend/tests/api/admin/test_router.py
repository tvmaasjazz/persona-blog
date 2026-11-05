from datetime import UTC, datetime, timedelta
from decimal import Decimal
from unittest.mock import ANY
from uuid import UUID

import pytest
from httpx import AsyncClient
from redis.asyncio import Redis
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.core.config import AppSettings
from libs.auth.services import AuthSessionService
from libs.credits.types import CreditLedgerEntryType
from libs.database.orm import CreditLedgerOrm, InviteOrm, RoleOrm, UserOrm
from libs.generate_text.types import GenerateTextRunStatusType
from libs.invites.utils import InviteUtils
from libs.permissions.types import RoleType
from tests.factories.auth import build_auth_user
from tests.factories.credits import insert_credit_ledger_row
from tests.factories.database import fetch_database_utc_now
from tests.factories.generate_text import insert_generate_text_run_row
from tests.factories.invites import insert_invite_row
from tests.factories.users import find_system_user_row, insert_user_row

UNKNOWN_USER_IDENTITY = "7b0f3c1e-5d2a-4e8b-9a61-0c4d2f8e1a53"


async def _count_ledger_rows(db_session: AsyncSession, user_id: int) -> int:
    ledger_count_query = select(func.count(CreditLedgerOrm.id)).where(
        CreditLedgerOrm.user_id == user_id
    )
    ledger_count = await db_session.scalar(ledger_count_query)
    assert ledger_count is not None
    return ledger_count


async def _create_sessions(
    redis_client: Redis, app_settings: AppSettings, user_record: UserOrm, role: RoleType
) -> list[str]:
    auth_session_service = AuthSessionService(
        redis_client=redis_client, auth_settings=app_settings.auth
    )
    auth_user = build_auth_user(
        user_id=user_record.id, user_identity=user_record.identity, role=role
    )
    first_session_id = await auth_session_service.create_session(auth_user)
    second_session_id = await auth_session_service.create_session(auth_user)
    return [first_session_id, second_session_id]


# GET /admin/users


async def test_find_user_list_returns_every_user_but_system_user_newest_first(
    api_client: AsyncClient, signed_in_admin: UserOrm, db_session: AsyncSession
) -> None:
    older_user_record = await insert_user_row(
        db_session,
        email="older@example.com",
        display_name=None,
        role=RoleType.READER,
        credit_balance_usd=Decimal("2.50"),
        is_active=False,
    )
    newer_user_record = await insert_user_row(
        db_session,
        email="newer@example.com",
        display_name="Newer User",
        credit_balance_usd=Decimal("5"),
        last_activity_at=datetime(2026, 1, 2, 3, 4, 5, tzinfo=UTC),
    )

    find_user_list_response = await api_client.get("/admin/users")

    assert find_user_list_response.status_code == 200
    assert find_user_list_response.json() == {
        "users": [
            {
                "identity": str(newer_user_record.identity),
                "email": "newer@example.com",
                "display_name": "Newer User",
                "role": "CREATOR",
                "credit_balance_usd": "5.0000000000",
                "is_active": True,
                "created_at": ANY,
                "last_activity_at": "2026-01-02T03:04:05Z",
            },
            {
                "identity": str(older_user_record.identity),
                "email": "older@example.com",
                "display_name": None,
                "role": "READER",
                "credit_balance_usd": "2.5000000000",
                "is_active": False,
                "created_at": ANY,
                "last_activity_at": None,
            },
            {
                "identity": str(signed_in_admin.identity),
                "email": signed_in_admin.email,
                "display_name": "Ada Lovelace",
                "role": "ADMIN",
                "credit_balance_usd": "0.0000000000",
                "is_active": True,
                "created_at": ANY,
                "last_activity_at": None,
            },
        ]
    }


async def test_find_user_list_signed_out_returns_401(api_client: AsyncClient) -> None:
    find_user_list_response = await api_client.get("/admin/users")

    assert find_user_list_response.status_code == 401


@pytest.mark.usefixtures("signed_in_user")
async def test_find_user_list_creator_returns_403(api_client: AsyncClient) -> None:
    find_user_list_response = await api_client.get("/admin/users")

    assert find_user_list_response.status_code == 403


@pytest.mark.usefixtures("signed_in_reader")
async def test_find_user_list_reader_returns_403(api_client: AsyncClient) -> None:
    find_user_list_response = await api_client.get("/admin/users")

    assert find_user_list_response.status_code == 403


# GET /admin/users/{user_identity}


@pytest.mark.usefixtures("signed_in_admin")
async def test_find_user_returns_user_response(
    api_client: AsyncClient, db_session: AsyncSession
) -> None:
    user_record = await insert_user_row(
        db_session,
        email="ada@example.com",
        display_name="Ada Lovelace",
        role=RoleType.READER,
        credit_balance_usd=Decimal("1.25"),
        last_activity_at=datetime(2026, 1, 2, 3, 4, 5, tzinfo=UTC),
    )

    find_user_response = await api_client.get(f"/admin/users/{user_record.identity}")

    assert find_user_response.status_code == 200
    assert find_user_response.json() == {
        "identity": str(user_record.identity),
        "email": "ada@example.com",
        "display_name": "Ada Lovelace",
        "role": "READER",
        "credit_balance_usd": "1.2500000000",
        "is_active": True,
        "created_at": ANY,
        "last_activity_at": "2026-01-02T03:04:05Z",
    }


@pytest.mark.usefixtures("signed_in_admin")
async def test_find_user_unknown_user_returns_404(api_client: AsyncClient) -> None:
    find_user_response = await api_client.get(f"/admin/users/{UNKNOWN_USER_IDENTITY}")

    assert find_user_response.status_code == 404


@pytest.mark.usefixtures("signed_in_admin")
async def test_find_user_system_user_returns_404(
    api_client: AsyncClient, db_session: AsyncSession
) -> None:
    system_user_record = await find_system_user_row(db_session)

    find_user_response = await api_client.get(f"/admin/users/{system_user_record.identity}")

    assert find_user_response.status_code == 404


async def test_find_user_creator_returns_403(
    api_client: AsyncClient, signed_in_user: UserOrm
) -> None:
    find_user_response = await api_client.get(f"/admin/users/{signed_in_user.identity}")

    assert find_user_response.status_code == 403


async def test_find_user_signed_out_returns_401(api_client: AsyncClient) -> None:
    find_user_response = await api_client.get(f"/admin/users/{UNKNOWN_USER_IDENTITY}")

    assert find_user_response.status_code == 401


# GET /admin/users/{user_identity}/credit-ledger


@pytest.mark.usefixtures("signed_in_admin")
async def test_find_user_credit_ledger_returns_entries_newest_first(
    api_client: AsyncClient, db_session: AsyncSession
) -> None:
    user_record = await insert_user_row(db_session, email="ada@example.com")
    run_record = await insert_generate_text_run_row(db_session, created_by_id=user_record.id)
    grant_record = await insert_credit_ledger_row(
        db_session,
        user_id=user_record.id,
        amount_usd=Decimal("5.00"),
        entry_type=CreditLedgerEntryType.GRANT,
        note="Welcome credit",
    )
    charge_record = await insert_credit_ledger_row(
        db_session,
        user_id=user_record.id,
        amount_usd=Decimal("-0.25"),
        entry_type=CreditLedgerEntryType.CHARGE,
        generate_text_run_id=run_record.id,
    )

    find_user_credit_ledger_response = await api_client.get(
        f"/admin/users/{user_record.identity}/credit-ledger"
    )

    assert find_user_credit_ledger_response.status_code == 200
    assert find_user_credit_ledger_response.json() == {
        "credit_ledger_entries": [
            {
                "identity": str(charge_record.identity),
                "entry_type": "CHARGE",
                "amount_usd": "-0.2500000000",
                "note": None,
                "generate_text_run_identity": str(run_record.identity),
                "created_by_email": "ada@example.com",
                "created_at": ANY,
            },
            {
                "identity": str(grant_record.identity),
                "entry_type": "GRANT",
                "amount_usd": "5.0000000000",
                "note": "Welcome credit",
                "generate_text_run_identity": None,
                "created_by_email": "ada@example.com",
                "created_at": ANY,
            },
        ]
    }


@pytest.mark.usefixtures("signed_in_admin")
async def test_find_user_credit_ledger_no_entries_returns_empty_list(
    api_client: AsyncClient, db_session: AsyncSession
) -> None:
    user_record = await insert_user_row(db_session)

    find_user_credit_ledger_response = await api_client.get(
        f"/admin/users/{user_record.identity}/credit-ledger"
    )

    assert find_user_credit_ledger_response.status_code == 200
    assert find_user_credit_ledger_response.json() == {"credit_ledger_entries": []}


@pytest.mark.usefixtures("signed_in_admin")
async def test_find_user_credit_ledger_unknown_user_returns_404(api_client: AsyncClient) -> None:
    find_user_credit_ledger_response = await api_client.get(
        f"/admin/users/{UNKNOWN_USER_IDENTITY}/credit-ledger"
    )

    assert find_user_credit_ledger_response.status_code == 404


@pytest.mark.usefixtures("signed_in_admin")
async def test_find_user_credit_ledger_system_user_returns_404(
    api_client: AsyncClient, db_session: AsyncSession
) -> None:
    system_user_record = await find_system_user_row(db_session)

    find_user_credit_ledger_response = await api_client.get(
        f"/admin/users/{system_user_record.identity}/credit-ledger"
    )

    assert find_user_credit_ledger_response.status_code == 404


async def test_find_user_credit_ledger_creator_returns_403(
    api_client: AsyncClient, signed_in_user: UserOrm
) -> None:
    find_user_credit_ledger_response = await api_client.get(
        f"/admin/users/{signed_in_user.identity}/credit-ledger"
    )

    assert find_user_credit_ledger_response.status_code == 403


async def test_find_user_credit_ledger_signed_out_returns_401(api_client: AsyncClient) -> None:
    find_user_credit_ledger_response = await api_client.get(
        f"/admin/users/{UNKNOWN_USER_IDENTITY}/credit-ledger"
    )

    assert find_user_credit_ledger_response.status_code == 401


# POST /admin/users/{user_identity}/credit-grants


async def test_grant_user_credits_returns_grant_identity_and_persists_row(
    api_client: AsyncClient, signed_in_admin: UserOrm, db_session: AsyncSession
) -> None:
    user_record = await insert_user_row(db_session, credit_balance_usd=Decimal("1.00"))

    grant_user_credits_response = await api_client.post(
        f"/admin/users/{user_record.identity}/credit-grants",
        json={"amount_usd": "7.25", "note": "Support goodwill"},
    )

    grant_identity = UUID(grant_user_credits_response.json()["identity"])
    grant_query = select(CreditLedgerOrm).where(CreditLedgerOrm.identity == grant_identity)
    grant_record = await db_session.scalar(grant_query)
    await db_session.refresh(user_record)
    assert grant_user_credits_response.status_code == 201
    assert grant_user_credits_response.json() == {"identity": str(grant_identity)}
    assert grant_record is not None
    assert grant_record.user_id == user_record.id
    assert grant_record.entry_type == CreditLedgerEntryType.GRANT
    assert grant_record.amount_usd == Decimal("7.25")
    assert grant_record.note == "Support goodwill"
    assert grant_record.created_by_id == signed_in_admin.id
    assert user_record.credit_balance_usd == Decimal("8.25")


@pytest.mark.usefixtures("signed_in_admin")
async def test_grant_user_credits_maximum_amount_returns_201(
    api_client: AsyncClient, db_session: AsyncSession
) -> None:
    user_record = await insert_user_row(db_session)

    grant_user_credits_response = await api_client.post(
        f"/admin/users/{user_record.identity}/credit-grants",
        json={"amount_usd": "100", "note": "Largest allowed grant"},
    )

    await db_session.refresh(user_record)
    assert grant_user_credits_response.status_code == 201
    assert user_record.credit_balance_usd == Decimal("100")


async def test_grant_user_credits_reader_becomes_creator_and_all_sessions_deleted(
    api_client: AsyncClient,
    signed_in_admin: UserOrm,
    db_session: AsyncSession,
    redis_client: Redis,
    app_settings: AppSettings,
) -> None:
    reader_record = await insert_user_row(db_session, role=RoleType.READER)
    reader_session_ids = await _create_sessions(
        redis_client, app_settings, reader_record, RoleType.READER
    )

    grant_user_credits_response = await api_client.post(
        f"/admin/users/{reader_record.identity}/credit-grants",
        json={"amount_usd": "5", "note": "Welcome"},
    )

    await db_session.refresh(reader_record)
    role_code_query = select(RoleOrm.code).where(RoleOrm.id == reader_record.role_id)
    role_code = await db_session.scalar(role_code_query)
    first_session_exists = await redis_client.exists(f"session:{reader_session_ids[0]}")
    second_session_exists = await redis_client.exists(f"session:{reader_session_ids[1]}")
    user_sessions_exists = await redis_client.exists(f"user-sessions:{reader_record.id}")
    assert grant_user_credits_response.status_code == 201
    assert role_code == RoleType.CREATOR
    assert reader_record.updated_by_id == signed_in_admin.id
    assert first_session_exists == 0
    assert second_session_exists == 0
    assert user_sessions_exists == 0


async def test_grant_user_credits_creator_keeps_role_and_sessions(
    api_client: AsyncClient,
    signed_in_admin: UserOrm,
    db_session: AsyncSession,
    redis_client: Redis,
    app_settings: AppSettings,
) -> None:
    creator_record = await insert_user_row(db_session, role=RoleType.CREATOR)
    creator_session_ids = await _create_sessions(
        redis_client, app_settings, creator_record, RoleType.CREATOR
    )

    grant_user_credits_response = await api_client.post(
        f"/admin/users/{creator_record.identity}/credit-grants",
        json={"amount_usd": "5", "note": "Top up"},
    )

    await db_session.refresh(creator_record)
    role_code_query = select(RoleOrm.code).where(RoleOrm.id == creator_record.role_id)
    role_code = await db_session.scalar(role_code_query)
    first_session_exists = await redis_client.exists(f"session:{creator_session_ids[0]}")
    second_session_exists = await redis_client.exists(f"session:{creator_session_ids[1]}")
    user_sessions_member_count = await redis_client.scard(f"user-sessions:{creator_record.id}")
    assert grant_user_credits_response.status_code == 201
    assert role_code == RoleType.CREATOR
    assert first_session_exists == 1
    assert second_session_exists == 1
    assert user_sessions_member_count == 2


@pytest.mark.usefixtures("signed_in_admin")
async def test_grant_user_credits_unknown_user_returns_404(api_client: AsyncClient) -> None:
    grant_user_credits_response = await api_client.post(
        f"/admin/users/{UNKNOWN_USER_IDENTITY}/credit-grants",
        json={"amount_usd": "5", "note": "Welcome"},
    )

    assert grant_user_credits_response.status_code == 404


@pytest.mark.usefixtures("signed_in_admin")
async def test_grant_user_credits_system_user_returns_409_and_writes_nothing(
    api_client: AsyncClient, db_session: AsyncSession
) -> None:
    system_user_record = await find_system_user_row(db_session)

    grant_user_credits_response = await api_client.post(
        f"/admin/users/{system_user_record.identity}/credit-grants",
        json={"amount_usd": "5", "note": "Welcome"},
    )

    ledger_row_count = await _count_ledger_rows(db_session, system_user_record.id)
    await db_session.refresh(system_user_record)
    assert grant_user_credits_response.status_code == 409
    assert ledger_row_count == 0
    assert system_user_record.credit_balance_usd == Decimal(0)


async def test_grant_user_credits_creator_returns_403_and_writes_nothing(
    api_client: AsyncClient, signed_in_user: UserOrm, db_session: AsyncSession
) -> None:
    grant_user_credits_response = await api_client.post(
        f"/admin/users/{signed_in_user.identity}/credit-grants",
        json={"amount_usd": "5", "note": "Welcome"},
    )

    ledger_row_count = await _count_ledger_rows(db_session, signed_in_user.id)
    await db_session.refresh(signed_in_user)
    assert grant_user_credits_response.status_code == 403
    assert ledger_row_count == 0
    assert signed_in_user.credit_balance_usd == Decimal("5.00")


async def test_grant_user_credits_signed_out_returns_401(api_client: AsyncClient) -> None:
    grant_user_credits_response = await api_client.post(
        f"/admin/users/{UNKNOWN_USER_IDENTITY}/credit-grants",
        json={"amount_usd": "5", "note": "Welcome"},
    )

    assert grant_user_credits_response.status_code == 401


@pytest.mark.usefixtures("signed_in_admin")
@pytest.mark.parametrize(
    ("request_body", "expected_error_location"),
    [
        pytest.param({"note": "Welcome"}, ["body", "amount_usd"], id="missing_amount"),
        pytest.param({"amount_usd": "0", "note": "Welcome"}, ["body", "amount_usd"], id="zero"),
        pytest.param(
            {"amount_usd": "-1", "note": "Welcome"}, ["body", "amount_usd"], id="negative"
        ),
        pytest.param(
            {"amount_usd": "100.01", "note": "Welcome"}, ["body", "amount_usd"], id="above_limit"
        ),
        pytest.param(
            {"amount_usd": "0.00000000001", "note": "Welcome"},
            ["body", "amount_usd"],
            id="eleven_decimal_places",
        ),
        pytest.param({"amount_usd": "5"}, ["body", "note"], id="missing_note"),
        pytest.param({"amount_usd": "5", "note": "   "}, ["body", "note"], id="blank_note"),
        pytest.param({"amount_usd": "5", "note": "a" * 501}, ["body", "note"], id="note_too_long"),
    ],
)
async def test_grant_user_credits_invalid_body_returns_422(
    api_client: AsyncClient,
    request_body: dict[str, str],
    expected_error_location: list[str],
) -> None:
    grant_user_credits_response = await api_client.post(
        f"/admin/users/{UNKNOWN_USER_IDENTITY}/credit-grants", json=request_body
    )

    response_body = grant_user_credits_response.json()
    assert grant_user_credits_response.status_code == 422
    assert response_body["detail"][0]["loc"] == expected_error_location


@pytest.mark.usefixtures("signed_in_admin")
@pytest.mark.parametrize(
    ("request_method", "request_path"),
    [
        pytest.param("GET", "/admin/users/not-a-uuid", id="find_user"),
        pytest.param("GET", "/admin/users/not-a-uuid/credit-ledger", id="find_user_credit_ledger"),
        pytest.param("POST", "/admin/users/not-a-uuid/credit-grants", id="grant_user_credits"),
    ],
)
async def test_admin_route_malformed_user_identity_returns_422(
    api_client: AsyncClient, request_method: str, request_path: str
) -> None:
    admin_response = await api_client.request(
        request_method, request_path, json={"amount_usd": "5", "note": "Welcome"}
    )

    response_body = admin_response.json()
    assert admin_response.status_code == 422
    assert response_body["detail"][0]["loc"] == ["path", "user_identity"]


# PUT /admin/users/{user_identity}/role


async def _find_role_code(db_session: AsyncSession, user_record: UserOrm) -> RoleType:
    await db_session.refresh(user_record)
    role_code_query = select(RoleOrm.code).where(RoleOrm.id == user_record.role_id)
    role_code = await db_session.scalar(role_code_query)
    assert role_code is not None
    return role_code


async def _count_existing_session_keys(redis_client: Redis, session_ids: list[str]) -> int:
    session_keys = [f"session:{session_id}" for session_id in session_ids]
    return await redis_client.exists(*session_keys)


async def test_set_user_role_reader_to_creator_returns_empty_and_persists_role(
    api_client: AsyncClient, signed_in_admin: UserOrm, db_session: AsyncSession
) -> None:
    reader_record = await insert_user_row(db_session, role=RoleType.READER)

    set_user_role_response = await api_client.put(
        f"/admin/users/{reader_record.identity}/role", json={"role": "CREATOR"}
    )

    role_code = await _find_role_code(db_session, reader_record)
    assert set_user_role_response.status_code == 200
    assert set_user_role_response.json() == {}
    assert role_code == RoleType.CREATOR
    assert reader_record.updated_by_id == signed_in_admin.id


async def test_set_user_role_creator_to_reader_persists_role(
    api_client: AsyncClient, signed_in_admin: UserOrm, db_session: AsyncSession
) -> None:
    creator_record = await insert_user_row(db_session, role=RoleType.CREATOR)

    set_user_role_response = await api_client.put(
        f"/admin/users/{creator_record.identity}/role", json={"role": "READER"}
    )

    role_code = await _find_role_code(db_session, creator_record)
    assert set_user_role_response.status_code == 200
    assert set_user_role_response.json() == {}
    assert role_code == RoleType.READER
    assert creator_record.updated_by_id == signed_in_admin.id


@pytest.mark.usefixtures("signed_in_admin")
async def test_set_user_role_inactive_user_persists_role(
    api_client: AsyncClient, db_session: AsyncSession
) -> None:
    inactive_record = await insert_user_row(db_session, role=RoleType.READER, is_active=False)

    set_user_role_response = await api_client.put(
        f"/admin/users/{inactive_record.identity}/role", json={"role": "CREATOR"}
    )

    role_code = await _find_role_code(db_session, inactive_record)
    assert set_user_role_response.status_code == 200
    assert role_code == RoleType.CREATOR
    assert inactive_record.is_active is False


@pytest.mark.usefixtures("signed_in_admin")
async def test_set_user_role_same_role_returns_empty_and_changes_nothing(
    api_client: AsyncClient, db_session: AsyncSession
) -> None:
    creator_record = await insert_user_row(db_session, role=RoleType.CREATOR)

    set_user_role_response = await api_client.put(
        f"/admin/users/{creator_record.identity}/role", json={"role": "CREATOR"}
    )

    role_code = await _find_role_code(db_session, creator_record)
    assert set_user_role_response.status_code == 200
    assert set_user_role_response.json() == {}
    assert role_code == RoleType.CREATOR
    assert creator_record.updated_by_id is None


@pytest.mark.usefixtures("signed_in_admin")
@pytest.mark.parametrize(
    ("current_role", "new_role"),
    [
        pytest.param(RoleType.READER, "CREATOR", id="promoted_to_creator"),
        pytest.param(RoleType.CREATOR, "READER", id="demoted_to_reader"),
    ],
)
async def test_set_user_role_changed_deletes_all_the_users_sessions(
    api_client: AsyncClient,
    db_session: AsyncSession,
    redis_client: Redis,
    app_settings: AppSettings,
    current_role: RoleType,
    new_role: str,
) -> None:
    user_record = await insert_user_row(db_session, role=current_role)
    user_session_ids = await _create_sessions(redis_client, app_settings, user_record, current_role)

    set_user_role_response = await api_client.put(
        f"/admin/users/{user_record.identity}/role", json={"role": new_role}
    )

    remaining_session_count = await _count_existing_session_keys(redis_client, user_session_ids)
    user_sessions_exists = await redis_client.exists(f"user-sessions:{user_record.id}")
    assert set_user_role_response.status_code == 200
    assert remaining_session_count == 0
    assert user_sessions_exists == 0


@pytest.mark.usefixtures("signed_in_admin")
async def test_set_user_role_same_role_keeps_the_users_sessions(
    api_client: AsyncClient,
    db_session: AsyncSession,
    redis_client: Redis,
    app_settings: AppSettings,
) -> None:
    creator_record = await insert_user_row(db_session, role=RoleType.CREATOR)
    creator_session_ids = await _create_sessions(
        redis_client, app_settings, creator_record, RoleType.CREATOR
    )

    set_user_role_response = await api_client.put(
        f"/admin/users/{creator_record.identity}/role", json={"role": "CREATOR"}
    )

    remaining_session_count = await _count_existing_session_keys(redis_client, creator_session_ids)
    assert set_user_role_response.status_code == 200
    assert remaining_session_count == 2


@pytest.mark.usefixtures("signed_in_admin")
async def test_set_user_role_creator_to_reader_fails_unfinished_runs_and_keeps_finished_ones(
    api_client: AsyncClient, db_session: AsyncSession
) -> None:
    creator_record = await insert_user_row(db_session, role=RoleType.CREATOR)
    pending_run_record = await insert_generate_text_run_row(
        db_session, created_by_id=creator_record.id, status=GenerateTextRunStatusType.PENDING
    )
    awaiting_review_run_record = await insert_generate_text_run_row(
        db_session,
        created_by_id=creator_record.id,
        status=GenerateTextRunStatusType.AWAITING_REVIEW,
    )
    completed_run_record = await insert_generate_text_run_row(
        db_session, created_by_id=creator_record.id, status=GenerateTextRunStatusType.COMPLETED
    )

    set_user_role_response = await api_client.put(
        f"/admin/users/{creator_record.identity}/role", json={"role": "READER"}
    )

    await db_session.refresh(pending_run_record)
    await db_session.refresh(awaiting_review_run_record)
    await db_session.refresh(completed_run_record)
    assert set_user_role_response.status_code == 200
    assert pending_run_record.status == GenerateTextRunStatusType.FAILED
    assert pending_run_record.error_code == "UserRoleChanged"
    assert awaiting_review_run_record.status == GenerateTextRunStatusType.FAILED
    assert awaiting_review_run_record.error_code == "UserRoleChanged"
    assert completed_run_record.status == GenerateTextRunStatusType.COMPLETED


@pytest.mark.usefixtures("signed_in_admin")
async def test_set_user_role_reader_to_creator_fails_no_runs(
    api_client: AsyncClient, db_session: AsyncSession
) -> None:
    reader_record = await insert_user_row(db_session, role=RoleType.READER)
    running_run_record = await insert_generate_text_run_row(
        db_session, created_by_id=reader_record.id, status=GenerateTextRunStatusType.RUNNING
    )

    set_user_role_response = await api_client.put(
        f"/admin/users/{reader_record.identity}/role", json={"role": "CREATOR"}
    )

    await db_session.refresh(running_run_record)
    assert set_user_role_response.status_code == 200
    assert running_run_record.status == GenerateTextRunStatusType.RUNNING


@pytest.mark.usefixtures("signed_in_admin")
async def test_set_user_role_same_reader_role_fails_no_runs(
    api_client: AsyncClient, db_session: AsyncSession
) -> None:
    reader_record = await insert_user_row(db_session, role=RoleType.READER)
    running_run_record = await insert_generate_text_run_row(
        db_session, created_by_id=reader_record.id, status=GenerateTextRunStatusType.RUNNING
    )

    set_user_role_response = await api_client.put(
        f"/admin/users/{reader_record.identity}/role", json={"role": "READER"}
    )

    await db_session.refresh(running_run_record)
    assert set_user_role_response.status_code == 200
    assert running_run_record.status == GenerateTextRunStatusType.RUNNING


@pytest.mark.usefixtures("signed_in_admin")
@pytest.mark.parametrize(
    "request_body",
    [
        pytest.param({}, id="missing_role"),
        pytest.param({"role": "ADMIN"}, id="admin_role"),
        pytest.param({"role": "SYSTEM"}, id="system_role"),
        pytest.param({"role": "OWNER"}, id="unknown_role"),
    ],
)
async def test_set_user_role_invalid_body_returns_422(
    api_client: AsyncClient, request_body: dict[str, str]
) -> None:
    set_user_role_response = await api_client.put(
        f"/admin/users/{UNKNOWN_USER_IDENTITY}/role", json=request_body
    )

    response_body = set_user_role_response.json()
    assert set_user_role_response.status_code == 422
    assert response_body["detail"][0]["loc"] == ["body", "role"]


@pytest.mark.usefixtures("signed_in_admin")
async def test_set_user_role_malformed_user_identity_returns_422(api_client: AsyncClient) -> None:
    set_user_role_response = await api_client.put(
        "/admin/users/not-a-uuid/role", json={"role": "CREATOR"}
    )

    response_body = set_user_role_response.json()
    assert set_user_role_response.status_code == 422
    assert response_body["detail"][0]["loc"] == ["path", "user_identity"]


@pytest.mark.usefixtures("signed_in_admin")
async def test_set_user_role_unknown_user_returns_404(api_client: AsyncClient) -> None:
    set_user_role_response = await api_client.put(
        f"/admin/users/{UNKNOWN_USER_IDENTITY}/role", json={"role": "CREATOR"}
    )

    assert set_user_role_response.status_code == 404


@pytest.mark.usefixtures("signed_in_admin")
async def test_set_user_role_system_user_returns_404(
    api_client: AsyncClient, db_session: AsyncSession
) -> None:
    system_user_record = await find_system_user_row(db_session)

    set_user_role_response = await api_client.put(
        f"/admin/users/{system_user_record.identity}/role", json={"role": "CREATOR"}
    )

    assert set_user_role_response.status_code == 404


async def test_set_user_role_acting_admin_returns_409_and_keeps_role(
    api_client: AsyncClient, signed_in_admin: UserOrm, db_session: AsyncSession
) -> None:
    set_user_role_response = await api_client.put(
        f"/admin/users/{signed_in_admin.identity}/role", json={"role": "READER"}
    )

    role_code = await _find_role_code(db_session, signed_in_admin)
    assert set_user_role_response.status_code == 409
    assert role_code == RoleType.ADMIN


@pytest.mark.usefixtures("signed_in_admin")
async def test_set_user_role_another_admin_returns_409_and_keeps_role(
    api_client: AsyncClient, db_session: AsyncSession
) -> None:
    other_admin_record = await insert_user_row(db_session, role=RoleType.ADMIN)

    set_user_role_response = await api_client.put(
        f"/admin/users/{other_admin_record.identity}/role", json={"role": "READER"}
    )

    role_code = await _find_role_code(db_session, other_admin_record)
    assert set_user_role_response.status_code == 409
    assert role_code == RoleType.ADMIN


async def test_set_user_role_creator_returns_403_and_changes_nothing(
    api_client: AsyncClient, signed_in_user: UserOrm, db_session: AsyncSession
) -> None:
    reader_record = await insert_user_row(db_session, role=RoleType.READER)

    set_user_role_response = await api_client.put(
        f"/admin/users/{reader_record.identity}/role", json={"role": "CREATOR"}
    )

    role_code = await _find_role_code(db_session, reader_record)
    assert set_user_role_response.status_code == 403
    assert role_code == RoleType.READER


async def test_set_user_role_signed_out_returns_401(api_client: AsyncClient) -> None:
    set_user_role_response = await api_client.put(
        f"/admin/users/{UNKNOWN_USER_IDENTITY}/role", json={"role": "CREATOR"}
    )

    assert set_user_role_response.status_code == 401


# PUT /admin/users/{user_identity}/active


async def test_set_user_active_suspend_returns_empty_and_persists_state(
    api_client: AsyncClient, signed_in_admin: UserOrm, db_session: AsyncSession
) -> None:
    user_record = await insert_user_row(db_session, role=RoleType.CREATOR)

    set_user_active_response = await api_client.put(
        f"/admin/users/{user_record.identity}/active", json={"is_active": False}
    )

    await db_session.refresh(user_record)
    assert set_user_active_response.status_code == 200
    assert set_user_active_response.json() == {}
    assert user_record.is_active is False
    assert user_record.updated_by_id == signed_in_admin.id


async def test_set_user_active_reactivate_returns_empty_and_persists_state(
    api_client: AsyncClient, signed_in_admin: UserOrm, db_session: AsyncSession
) -> None:
    suspended_record = await insert_user_row(db_session, is_active=False)

    set_user_active_response = await api_client.put(
        f"/admin/users/{suspended_record.identity}/active", json={"is_active": True}
    )

    await db_session.refresh(suspended_record)
    assert set_user_active_response.status_code == 200
    assert set_user_active_response.json() == {}
    assert suspended_record.is_active is True
    assert suspended_record.updated_by_id == signed_in_admin.id


@pytest.mark.usefixtures("signed_in_admin")
@pytest.mark.parametrize(
    ("is_user_active", "new_is_active"),
    [
        pytest.param(True, False, id="suspended"),
        pytest.param(False, True, id="reactivated"),
    ],
)
async def test_set_user_active_changed_deletes_all_the_users_sessions(
    api_client: AsyncClient,
    db_session: AsyncSession,
    redis_client: Redis,
    app_settings: AppSettings,
    is_user_active: bool,
    new_is_active: bool,
) -> None:
    user_record = await insert_user_row(db_session, is_active=is_user_active)
    user_session_ids = await _create_sessions(
        redis_client, app_settings, user_record, RoleType.CREATOR
    )

    set_user_active_response = await api_client.put(
        f"/admin/users/{user_record.identity}/active", json={"is_active": new_is_active}
    )

    remaining_session_count = await _count_existing_session_keys(redis_client, user_session_ids)
    user_sessions_exists = await redis_client.exists(f"user-sessions:{user_record.id}")
    assert set_user_active_response.status_code == 200
    assert remaining_session_count == 0
    assert user_sessions_exists == 0


@pytest.mark.usefixtures("signed_in_admin")
async def test_set_user_active_same_value_returns_empty_and_keeps_sessions_and_runs(
    api_client: AsyncClient,
    db_session: AsyncSession,
    redis_client: Redis,
    app_settings: AppSettings,
) -> None:
    active_record = await insert_user_row(db_session, is_active=True)
    active_session_ids = await _create_sessions(
        redis_client, app_settings, active_record, RoleType.CREATOR
    )
    running_run_record = await insert_generate_text_run_row(
        db_session, created_by_id=active_record.id, status=GenerateTextRunStatusType.RUNNING
    )

    set_user_active_response = await api_client.put(
        f"/admin/users/{active_record.identity}/active", json={"is_active": True}
    )

    await db_session.refresh(running_run_record)
    remaining_session_count = await _count_existing_session_keys(redis_client, active_session_ids)
    assert set_user_active_response.status_code == 200
    assert set_user_active_response.json() == {}
    assert remaining_session_count == 2
    assert running_run_record.status == GenerateTextRunStatusType.RUNNING


@pytest.mark.usefixtures("signed_in_admin")
async def test_set_user_active_suspend_fails_unfinished_runs_and_keeps_finished_ones(
    api_client: AsyncClient, db_session: AsyncSession
) -> None:
    user_record = await insert_user_row(db_session)
    pending_run_record = await insert_generate_text_run_row(
        db_session, created_by_id=user_record.id, status=GenerateTextRunStatusType.PENDING
    )
    awaiting_review_run_record = await insert_generate_text_run_row(
        db_session, created_by_id=user_record.id, status=GenerateTextRunStatusType.AWAITING_REVIEW
    )
    completed_run_record = await insert_generate_text_run_row(
        db_session, created_by_id=user_record.id, status=GenerateTextRunStatusType.COMPLETED
    )

    set_user_active_response = await api_client.put(
        f"/admin/users/{user_record.identity}/active", json={"is_active": False}
    )

    await db_session.refresh(pending_run_record)
    await db_session.refresh(awaiting_review_run_record)
    await db_session.refresh(completed_run_record)
    assert set_user_active_response.status_code == 200
    assert pending_run_record.status == GenerateTextRunStatusType.FAILED
    assert pending_run_record.error_code == "UserSuspended"
    assert awaiting_review_run_record.status == GenerateTextRunStatusType.FAILED
    assert awaiting_review_run_record.error_code == "UserSuspended"
    assert completed_run_record.status == GenerateTextRunStatusType.COMPLETED


@pytest.mark.usefixtures("signed_in_admin")
async def test_set_user_active_reactivate_fails_no_runs(
    api_client: AsyncClient, db_session: AsyncSession
) -> None:
    suspended_record = await insert_user_row(db_session, is_active=False)
    pending_run_record = await insert_generate_text_run_row(
        db_session, created_by_id=suspended_record.id, status=GenerateTextRunStatusType.PENDING
    )

    set_user_active_response = await api_client.put(
        f"/admin/users/{suspended_record.identity}/active", json={"is_active": True}
    )

    await db_session.refresh(pending_run_record)
    assert set_user_active_response.status_code == 200
    assert pending_run_record.status == GenerateTextRunStatusType.PENDING


@pytest.mark.usefixtures("signed_in_admin")
@pytest.mark.parametrize(
    "request_body",
    [
        pytest.param({}, id="missing_is_active"),
        pytest.param({"is_active": "maybe"}, id="not_a_boolean"),
    ],
)
async def test_set_user_active_invalid_body_returns_422(
    api_client: AsyncClient, request_body: dict[str, str]
) -> None:
    set_user_active_response = await api_client.put(
        f"/admin/users/{UNKNOWN_USER_IDENTITY}/active", json=request_body
    )

    response_body = set_user_active_response.json()
    assert set_user_active_response.status_code == 422
    assert response_body["detail"][0]["loc"] == ["body", "is_active"]


@pytest.mark.usefixtures("signed_in_admin")
async def test_set_user_active_malformed_user_identity_returns_422(
    api_client: AsyncClient,
) -> None:
    set_user_active_response = await api_client.put(
        "/admin/users/not-a-uuid/active", json={"is_active": False}
    )

    response_body = set_user_active_response.json()
    assert set_user_active_response.status_code == 422
    assert response_body["detail"][0]["loc"] == ["path", "user_identity"]


@pytest.mark.usefixtures("signed_in_admin")
async def test_set_user_active_unknown_user_returns_404(api_client: AsyncClient) -> None:
    set_user_active_response = await api_client.put(
        f"/admin/users/{UNKNOWN_USER_IDENTITY}/active", json={"is_active": False}
    )

    assert set_user_active_response.status_code == 404


@pytest.mark.usefixtures("signed_in_admin")
async def test_set_user_active_system_user_returns_404(
    api_client: AsyncClient, db_session: AsyncSession
) -> None:
    system_user_record = await find_system_user_row(db_session)

    set_user_active_response = await api_client.put(
        f"/admin/users/{system_user_record.identity}/active", json={"is_active": False}
    )

    assert set_user_active_response.status_code == 404


async def test_set_user_active_acting_admin_returns_409_and_stays_active(
    api_client: AsyncClient, signed_in_admin: UserOrm, db_session: AsyncSession
) -> None:
    set_user_active_response = await api_client.put(
        f"/admin/users/{signed_in_admin.identity}/active", json={"is_active": False}
    )

    await db_session.refresh(signed_in_admin)
    assert set_user_active_response.status_code == 409
    assert signed_in_admin.is_active is True


@pytest.mark.usefixtures("signed_in_admin")
async def test_set_user_active_another_admin_returns_409_and_stays_active(
    api_client: AsyncClient, db_session: AsyncSession
) -> None:
    other_admin_record = await insert_user_row(db_session, role=RoleType.ADMIN)

    set_user_active_response = await api_client.put(
        f"/admin/users/{other_admin_record.identity}/active", json={"is_active": False}
    )

    await db_session.refresh(other_admin_record)
    assert set_user_active_response.status_code == 409
    assert other_admin_record.is_active is True


async def test_set_user_active_creator_returns_403_and_changes_nothing(
    api_client: AsyncClient, signed_in_user: UserOrm, db_session: AsyncSession
) -> None:
    user_record = await insert_user_row(db_session)

    set_user_active_response = await api_client.put(
        f"/admin/users/{user_record.identity}/active", json={"is_active": False}
    )

    await db_session.refresh(user_record)
    assert set_user_active_response.status_code == 403
    assert user_record.is_active is True


async def test_set_user_active_signed_out_returns_401(api_client: AsyncClient) -> None:
    set_user_active_response = await api_client.put(
        f"/admin/users/{UNKNOWN_USER_IDENTITY}/active", json={"is_active": False}
    )

    assert set_user_active_response.status_code == 401


# POST /admin/invites

INVITE_URL_PREFIX = "http://localhost:5173/invite/"


async def _count_invite_rows(db_session: AsyncSession) -> int | None:
    invite_count_query = select(func.count(InviteOrm.id))
    return await db_session.scalar(invite_count_query)


async def test_create_invite_returns_identity_and_link_and_stores_only_the_code_hash(
    api_client: AsyncClient, signed_in_admin: UserOrm, db_session: AsyncSession
) -> None:
    create_invite_response = await api_client.post(
        "/admin/invites",
        json={
            "name": "Ada's friends",
            "credit_amount_usd": "7.50",
            "note": "Welcome to the beta",
            "expires_in_days": 3,
        },
    )

    response_body = create_invite_response.json()
    invite_identity = UUID(response_body["identity"])
    invite_query = select(InviteOrm).where(InviteOrm.identity == invite_identity)
    invite_record = await db_session.scalar(invite_query)
    assert create_invite_response.status_code == 201
    assert response_body == {"identity": str(invite_identity), "invite_url": ANY}
    assert response_body["invite_url"].startswith(INVITE_URL_PREFIX)
    invite_code = response_body["invite_url"].removeprefix(INVITE_URL_PREFIX)
    assert invite_record is not None
    stored_column_values = [
        str(getattr(invite_record, column.key)) for column in InviteOrm.__table__.columns
    ]
    assert invite_record.code_hash == InviteUtils.hash_code(invite_code)
    assert all(invite_code not in stored_value for stored_value in stored_column_values)
    assert invite_record.name == "Ada's friends"
    assert invite_record.credit_amount_usd == Decimal("7.50")
    assert invite_record.note == "Welcome to the beta"
    assert invite_record.created_by_id == signed_in_admin.id
    assert invite_record.used_at is None
    assert invite_record.revoked_at is None


@pytest.mark.usefixtures("signed_in_admin")
async def test_create_invite_without_expires_in_days_expires_in_seven_days(
    api_client: AsyncClient, db_session: AsyncSession
) -> None:
    create_invite_response = await api_client.post(
        "/admin/invites", json={"name": "Ada's friends", "credit_amount_usd": "5"}
    )

    invite_identity = UUID(create_invite_response.json()["identity"])
    expires_at_query = select(InviteOrm.expires_at).where(InviteOrm.identity == invite_identity)
    expires_at = await db_session.scalar(expires_at_query)
    database_utc_now = await fetch_database_utc_now(db_session)
    assert create_invite_response.status_code == 201
    assert expires_at == database_utc_now + timedelta(days=7)


@pytest.mark.usefixtures("signed_in_admin")
@pytest.mark.parametrize("expires_in_days", [1, 30])
async def test_create_invite_expires_in_days_limits_set_the_expiry(
    api_client: AsyncClient, db_session: AsyncSession, expires_in_days: int
) -> None:
    create_invite_response = await api_client.post(
        "/admin/invites",
        json={
            "name": "Ada's friends",
            "credit_amount_usd": "5",
            "expires_in_days": expires_in_days,
        },
    )

    invite_identity = UUID(create_invite_response.json()["identity"])
    expires_at_query = select(InviteOrm.expires_at).where(InviteOrm.identity == invite_identity)
    expires_at = await db_session.scalar(expires_at_query)
    database_utc_now = await fetch_database_utc_now(db_session)
    assert create_invite_response.status_code == 201
    assert expires_at == database_utc_now + timedelta(days=expires_in_days)


@pytest.mark.usefixtures("signed_in_admin")
async def test_create_invite_blank_note_is_stored_as_no_note(
    api_client: AsyncClient, db_session: AsyncSession
) -> None:
    create_invite_response = await api_client.post(
        "/admin/invites",
        json={"name": "Ada's friends", "credit_amount_usd": "5", "note": "   "},
    )

    invite_identity = UUID(create_invite_response.json()["identity"])
    invite_note_query = select(InviteOrm.note).where(InviteOrm.identity == invite_identity)
    invite_note = await db_session.scalar(invite_note_query)
    assert create_invite_response.status_code == 201
    assert invite_note is None


@pytest.mark.usefixtures("signed_in_admin")
@pytest.mark.parametrize(
    ("request_body", "expected_error_location"),
    [
        pytest.param({"credit_amount_usd": "5"}, ["body", "name"], id="missing_name"),
        pytest.param({"name": "   ", "credit_amount_usd": "5"}, ["body", "name"], id="blank_name"),
        pytest.param(
            {"name": "a" * 201, "credit_amount_usd": "5"}, ["body", "name"], id="name_too_long"
        ),
        pytest.param({"name": "Ada"}, ["body", "credit_amount_usd"], id="missing_amount"),
        pytest.param(
            {"name": "Ada", "credit_amount_usd": "0"}, ["body", "credit_amount_usd"], id="zero"
        ),
        pytest.param(
            {"name": "Ada", "credit_amount_usd": "100.01"},
            ["body", "credit_amount_usd"],
            id="above_limit",
        ),
        pytest.param(
            {"name": "Ada", "credit_amount_usd": "5", "expires_in_days": 0},
            ["body", "expires_in_days"],
            id="expires_in_days_zero",
        ),
        pytest.param(
            {"name": "Ada", "credit_amount_usd": "5", "expires_in_days": 31},
            ["body", "expires_in_days"],
            id="expires_in_days_above_limit",
        ),
        pytest.param(
            {"name": "Ada", "credit_amount_usd": "5", "note": "a" * 501},
            ["body", "note"],
            id="note_too_long",
        ),
    ],
)
async def test_create_invite_invalid_body_returns_422(
    api_client: AsyncClient,
    db_session: AsyncSession,
    request_body: dict[str, str | int],
    expected_error_location: list[str],
) -> None:
    create_invite_response = await api_client.post("/admin/invites", json=request_body)

    response_body = create_invite_response.json()
    invite_row_count = await _count_invite_rows(db_session)
    assert create_invite_response.status_code == 422
    assert response_body["detail"][0]["loc"] == expected_error_location
    assert invite_row_count == 0


async def test_create_invite_signed_out_returns_401(api_client: AsyncClient) -> None:
    create_invite_response = await api_client.post(
        "/admin/invites", json={"name": "Ada", "credit_amount_usd": "5"}
    )

    assert create_invite_response.status_code == 401


@pytest.mark.usefixtures("signed_in_user")
async def test_create_invite_creator_returns_403_and_writes_nothing(
    api_client: AsyncClient, db_session: AsyncSession
) -> None:
    create_invite_response = await api_client.post(
        "/admin/invites", json={"name": "Ada", "credit_amount_usd": "5"}
    )

    invite_row_count = await _count_invite_rows(db_session)
    assert create_invite_response.status_code == 403
    assert invite_row_count == 0


# GET /admin/invites


async def test_find_invite_list_returns_invites_newest_first_with_status_and_emails(
    api_client: AsyncClient, signed_in_admin: UserOrm, db_session: AsyncSession
) -> None:
    user_record = await insert_user_row(db_session, email="ada@example.com")
    older_invite_record = await insert_invite_row(
        db_session,
        name="Used",
        credit_amount_usd=Decimal("2.50"),
        note="Hello",
        used_at=datetime(2026, 1, 5, tzinfo=UTC),
        used_by_user_id=user_record.id,
        created_by_id=signed_in_admin.id,
        created_at=datetime(2026, 1, 1, tzinfo=UTC),
    )
    newer_invite_record = await insert_invite_row(
        db_session,
        name="Expired",
        expires_at=datetime(2026, 1, 3, tzinfo=UTC),
        created_by_id=signed_in_admin.id,
        created_at=datetime(2026, 1, 2, tzinfo=UTC),
    )

    find_invite_list_response = await api_client.get("/admin/invites")

    assert find_invite_list_response.status_code == 200
    assert find_invite_list_response.json() == {
        "invites": [
            {
                "identity": str(newer_invite_record.identity),
                "name": "Expired",
                "credit_amount_usd": "5.0000000000",
                "note": None,
                "status": "EXPIRED",
                "expires_at": "2026-01-03T00:00:00Z",
                "used_at": None,
                "used_by_email": None,
                "revoked_at": None,
                "created_at": "2026-01-02T00:00:00Z",
                "created_by_email": signed_in_admin.email,
            },
            {
                "identity": str(older_invite_record.identity),
                "name": "Used",
                "credit_amount_usd": "2.5000000000",
                "note": "Hello",
                "status": "USED",
                "expires_at": "2099-01-01T00:00:00Z",
                "used_at": "2026-01-05T00:00:00Z",
                "used_by_email": "ada@example.com",
                "revoked_at": None,
                "created_at": "2026-01-01T00:00:00Z",
                "created_by_email": signed_in_admin.email,
            },
        ]
    }


async def test_find_invite_list_unused_and_revoked_invites_return_their_status(
    api_client: AsyncClient, signed_in_admin: UserOrm, db_session: AsyncSession
) -> None:
    await insert_invite_row(
        db_session,
        name="Revoked",
        revoked_at=datetime(2026, 1, 6, tzinfo=UTC),
        created_by_id=signed_in_admin.id,
        created_at=datetime(2026, 1, 1, tzinfo=UTC),
    )
    await insert_invite_row(
        db_session,
        name="Unused",
        created_by_id=signed_in_admin.id,
        created_at=datetime(2026, 1, 2, tzinfo=UTC),
    )

    find_invite_list_response = await api_client.get("/admin/invites")

    invite_statuses = {
        invite["name"]: invite["status"] for invite in find_invite_list_response.json()["invites"]
    }
    assert invite_statuses == {"Unused": "UNUSED", "Revoked": "REVOKED"}


async def test_find_invite_list_signed_out_returns_401(api_client: AsyncClient) -> None:
    find_invite_list_response = await api_client.get("/admin/invites")

    assert find_invite_list_response.status_code == 401


@pytest.mark.usefixtures("signed_in_user")
async def test_find_invite_list_creator_returns_403(api_client: AsyncClient) -> None:
    find_invite_list_response = await api_client.get("/admin/invites")

    assert find_invite_list_response.status_code == 403


# POST /admin/invites/{invite_identity}/revoke


async def test_revoke_invite_returns_empty_and_sets_revoked_at(
    api_client: AsyncClient, signed_in_admin: UserOrm, db_session: AsyncSession
) -> None:
    invite_record = await insert_invite_row(db_session, created_by_id=signed_in_admin.id)

    revoke_invite_response = await api_client.post(
        f"/admin/invites/{invite_record.identity}/revoke"
    )

    await db_session.refresh(invite_record)
    database_utc_now = await fetch_database_utc_now(db_session)
    assert revoke_invite_response.status_code == 200
    assert revoke_invite_response.json() == {}
    assert invite_record.revoked_at == database_utc_now
    assert invite_record.updated_by_id == signed_in_admin.id


@pytest.mark.usefixtures("signed_in_admin")
async def test_revoke_invite_expired_invite_is_revoked(
    api_client: AsyncClient, db_session: AsyncSession
) -> None:
    invite_record = await insert_invite_row(db_session, expires_at=datetime(2026, 1, 2, tzinfo=UTC))

    revoke_invite_response = await api_client.post(
        f"/admin/invites/{invite_record.identity}/revoke"
    )

    await db_session.refresh(invite_record)
    assert revoke_invite_response.status_code == 200
    assert invite_record.revoked_at is not None


@pytest.mark.usefixtures("signed_in_admin")
async def test_revoke_invite_already_revoked_returns_empty_and_changes_nothing(
    api_client: AsyncClient, db_session: AsyncSession
) -> None:
    invite_record = await insert_invite_row(db_session, revoked_at=datetime(2026, 1, 2, tzinfo=UTC))

    revoke_invite_response = await api_client.post(
        f"/admin/invites/{invite_record.identity}/revoke"
    )

    await db_session.refresh(invite_record)
    assert revoke_invite_response.status_code == 200
    assert revoke_invite_response.json() == {}
    assert invite_record.revoked_at == datetime(2026, 1, 2, tzinfo=UTC)


@pytest.mark.usefixtures("signed_in_admin")
async def test_revoke_invite_used_invite_returns_409_and_stays_unrevoked(
    api_client: AsyncClient, db_session: AsyncSession
) -> None:
    user_record = await insert_user_row(db_session)
    invite_record = await insert_invite_row(
        db_session, used_at=datetime(2026, 1, 2, tzinfo=UTC), used_by_user_id=user_record.id
    )

    revoke_invite_response = await api_client.post(
        f"/admin/invites/{invite_record.identity}/revoke"
    )

    await db_session.refresh(invite_record)
    assert revoke_invite_response.status_code == 409
    assert invite_record.revoked_at is None


@pytest.mark.usefixtures("signed_in_admin")
async def test_revoke_invite_unknown_invite_returns_404(api_client: AsyncClient) -> None:
    revoke_invite_response = await api_client.post(f"/admin/invites/{UNKNOWN_USER_IDENTITY}/revoke")

    assert revoke_invite_response.status_code == 404


@pytest.mark.usefixtures("signed_in_admin")
async def test_revoke_invite_malformed_invite_identity_returns_422(api_client: AsyncClient) -> None:
    revoke_invite_response = await api_client.post("/admin/invites/not-a-uuid/revoke")

    response_body = revoke_invite_response.json()
    assert revoke_invite_response.status_code == 422
    assert response_body["detail"][0]["loc"] == ["path", "invite_identity"]


@pytest.mark.usefixtures("signed_in_user")
async def test_revoke_invite_creator_returns_403_and_changes_nothing(
    api_client: AsyncClient, db_session: AsyncSession
) -> None:
    invite_record = await insert_invite_row(db_session)

    revoke_invite_response = await api_client.post(
        f"/admin/invites/{invite_record.identity}/revoke"
    )

    await db_session.refresh(invite_record)
    assert revoke_invite_response.status_code == 403
    assert invite_record.revoked_at is None


async def test_revoke_invite_signed_out_returns_401(api_client: AsyncClient) -> None:
    revoke_invite_response = await api_client.post(f"/admin/invites/{UNKNOWN_USER_IDENTITY}/revoke")

    assert revoke_invite_response.status_code == 401
