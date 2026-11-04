from datetime import UTC, datetime
from decimal import Decimal

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from libs.database.orm import UserOrm


async def test_find_signed_in_user_returns_user_response(
    api_client: AsyncClient, signed_in_user: UserOrm
) -> None:
    find_signed_in_user_response = await api_client.get("/users/me")

    assert find_signed_in_user_response.status_code == 200
    assert find_signed_in_user_response.json() == {
        "identity": str(signed_in_user.identity),
        "email": signed_in_user.email,
        "display_name": signed_in_user.display_name,
        "avatar_url": signed_in_user.avatar_url,
        "role": "CREATOR",
        "permissions": [
            "BLOG_POST_READ",
            "BLOG_POST_WRITE",
            "GENERATE_TEXT_RUN_READ",
            "GENERATE_TEXT_RUN_WRITE",
            "PERSONA_READ",
            "PERSONA_WRITE",
        ],
        "credit_balance_usd": "5.0000000000",
        "is_credit_balance_low": False,
    }


async def test_find_signed_in_user_reader_returns_role_and_read_permissions(
    api_client: AsyncClient, signed_in_reader: UserOrm
) -> None:
    find_signed_in_user_response = await api_client.get("/users/me")

    assert find_signed_in_user_response.status_code == 200
    assert find_signed_in_user_response.json() == {
        "identity": str(signed_in_reader.identity),
        "email": signed_in_reader.email,
        "display_name": signed_in_reader.display_name,
        "avatar_url": signed_in_reader.avatar_url,
        "role": "READER",
        "permissions": ["BLOG_POST_READ", "PERSONA_READ"],
        "credit_balance_usd": "0E-10",
        "is_credit_balance_low": True,
    }


@pytest.mark.parametrize(
    ("credit_balance_usd", "expected_credit_balance_usd", "expected_is_credit_balance_low"),
    [
        pytest.param(Decimal("0.49"), "0.4900000000", True, id="below_threshold"),
        pytest.param(Decimal("0.50"), "0.5000000000", False, id="at_threshold"),
    ],
)
async def test_find_signed_in_user_flags_balance_below_fifty_cents_as_low(
    api_client: AsyncClient,
    signed_in_user: UserOrm,
    db_session: AsyncSession,
    credit_balance_usd: Decimal,
    expected_credit_balance_usd: str,
    expected_is_credit_balance_low: bool,
) -> None:
    signed_in_user.credit_balance_usd = credit_balance_usd
    await db_session.flush()

    find_signed_in_user_response = await api_client.get("/users/me")

    response_body = find_signed_in_user_response.json()
    assert find_signed_in_user_response.status_code == 200
    assert response_body["credit_balance_usd"] == expected_credit_balance_usd
    assert response_body["is_credit_balance_low"] is expected_is_credit_balance_low


async def test_find_signed_in_user_signed_out_returns_401(api_client: AsyncClient) -> None:
    find_signed_in_user_response = await api_client.get("/users/me")

    assert find_signed_in_user_response.status_code == 401


async def test_find_signed_in_user_soft_deleted_returns_404(
    api_client: AsyncClient, db_session: AsyncSession, signed_in_user: UserOrm
) -> None:
    signed_in_user.deleted_at = datetime(2026, 1, 2, 3, 4, 5, tzinfo=UTC)
    await db_session.flush()

    find_signed_in_user_response = await api_client.get("/users/me")

    assert find_signed_in_user_response.status_code == 404
