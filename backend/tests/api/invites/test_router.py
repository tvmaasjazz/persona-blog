from datetime import UTC, datetime
from decimal import Decimal

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from libs.invites.utils import InviteUtils
from tests.factories.invites import insert_invite_row
from tests.factories.users import insert_user_row


async def test_find_invite_status_unused_invite_returns_status_and_amount_when_signed_out(
    api_client: AsyncClient, db_session: AsyncSession
) -> None:
    await insert_invite_row(
        db_session,
        name="Ada's friends",
        note="Welcome to the beta",
        credit_amount_usd=Decimal("7.50"),
        code_hash=InviteUtils.hash_code("known-code"),
    )

    find_invite_status_response = await api_client.post(
        "/invites/check", json={"code": "known-code"}
    )

    assert find_invite_status_response.status_code == 200
    assert find_invite_status_response.json() == {
        "status": "UNUSED",
        "credit_amount_usd": "7.5000000000",
    }


async def test_find_invite_status_used_invite_returns_used(
    api_client: AsyncClient, db_session: AsyncSession
) -> None:
    user_record = await insert_user_row(db_session)
    await insert_invite_row(
        db_session,
        code_hash=InviteUtils.hash_code("known-code"),
        used_at=datetime(2026, 1, 2, tzinfo=UTC),
        used_by_user_id=user_record.id,
    )

    find_invite_status_response = await api_client.post(
        "/invites/check", json={"code": "known-code"}
    )

    assert find_invite_status_response.status_code == 200
    assert find_invite_status_response.json() == {
        "status": "USED",
        "credit_amount_usd": "5.0000000000",
    }


async def test_find_invite_status_expired_invite_returns_expired(
    api_client: AsyncClient, db_session: AsyncSession
) -> None:
    await insert_invite_row(
        db_session,
        code_hash=InviteUtils.hash_code("known-code"),
        expires_at=datetime(2026, 1, 2, tzinfo=UTC),
    )

    find_invite_status_response = await api_client.post(
        "/invites/check", json={"code": "known-code"}
    )

    assert find_invite_status_response.status_code == 200
    assert find_invite_status_response.json() == {
        "status": "EXPIRED",
        "credit_amount_usd": "5.0000000000",
    }


async def test_find_invite_status_revoked_invite_returns_revoked(
    api_client: AsyncClient, db_session: AsyncSession
) -> None:
    await insert_invite_row(
        db_session,
        code_hash=InviteUtils.hash_code("known-code"),
        revoked_at=datetime(2026, 1, 2, tzinfo=UTC),
    )

    find_invite_status_response = await api_client.post(
        "/invites/check", json={"code": "known-code"}
    )

    assert find_invite_status_response.status_code == 200
    assert find_invite_status_response.json() == {
        "status": "REVOKED",
        "credit_amount_usd": "5.0000000000",
    }


async def test_find_invite_status_unknown_code_returns_404(api_client: AsyncClient) -> None:
    find_invite_status_response = await api_client.post(
        "/invites/check", json={"code": "unknown-code"}
    )

    assert find_invite_status_response.status_code == 404


@pytest.mark.parametrize(
    ("request_body", "expected_error_location"),
    [
        pytest.param({}, ["body", "code"], id="missing_code"),
        pytest.param({"code": "   "}, ["body", "code"], id="blank_code"),
        pytest.param({"code": "a" * 101}, ["body", "code"], id="code_too_long"),
    ],
)
async def test_find_invite_status_invalid_body_returns_422(
    api_client: AsyncClient, request_body: dict[str, str], expected_error_location: list[str]
) -> None:
    find_invite_status_response = await api_client.post("/invites/check", json=request_body)

    response_body = find_invite_status_response.json()
    assert find_invite_status_response.status_code == 422
    assert response_body["detail"][0]["loc"] == expected_error_location
