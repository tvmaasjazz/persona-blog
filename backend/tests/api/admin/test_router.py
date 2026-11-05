from datetime import UTC, datetime
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
from libs.database.orm import CreditLedgerOrm, RoleOrm, UserOrm
from libs.permissions.types import RoleType
from tests.factories.auth import build_auth_user
from tests.factories.credits import insert_credit_ledger_row
from tests.factories.generate_text import insert_generate_text_run_row
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
