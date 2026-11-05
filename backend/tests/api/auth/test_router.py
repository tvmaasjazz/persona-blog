import pytest
from httpx import AsyncClient
from redis.asyncio import Redis

from libs.database.orm import UserOrm


@pytest.mark.usefixtures("signed_in_user")
async def test_logout_signed_in_clears_session_and_cookie(
    api_client: AsyncClient, redis_client: Redis
) -> None:
    session_id = api_client.cookies.get("sid")

    logout_response = await api_client.post("/auth/logout")

    session_exists = await redis_client.exists(f"session:{session_id}")
    assert logout_response.status_code == 200
    assert logout_response.json() == {}
    set_cookie_header = logout_response.headers.get_list("set-cookie")[0]
    assert "Max-Age=0" in set_cookie_header
    assert session_exists == 0


async def test_logout_signed_in_removes_session_from_user_sessions_set(
    api_client: AsyncClient, redis_client: Redis, signed_in_user: UserOrm
) -> None:
    session_id = api_client.cookies.get("sid")
    user_session_list_key = f"user-sessions:{signed_in_user.id}"
    session_in_set_before_logout = await redis_client.sismember(user_session_list_key, session_id)

    await api_client.post("/auth/logout")

    session_in_set_after_logout = await redis_client.sismember(user_session_list_key, session_id)
    assert session_in_set_before_logout == 1
    assert session_in_set_after_logout == 0


async def test_logout_signed_out_returns_401(api_client: AsyncClient) -> None:
    logout_response = await api_client.post("/auth/logout")

    assert logout_response.status_code == 401
