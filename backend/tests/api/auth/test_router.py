import pytest
from httpx import AsyncClient
from redis.asyncio import Redis


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


async def test_logout_signed_out_returns_401(api_client: AsyncClient) -> None:
    logout_response = await api_client.post("/auth/logout")

    assert logout_response.status_code == 401
