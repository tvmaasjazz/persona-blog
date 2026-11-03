from datetime import UTC, datetime

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
    }


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
