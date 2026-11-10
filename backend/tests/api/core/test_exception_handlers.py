from uuid import uuid4

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient, Response

from libs.core.exceptions import (
    ConflictException,
    ForbiddenException,
    NotFoundException,
    PaymentRequiredException,
    RateLimitedException,
    ServiceUnavailableException,
    UnauthorizedException,
    UnprocessableException,
)


@pytest.mark.parametrize(
    ("standard_exception", "expected_status_code"),
    [
        pytest.param(NotFoundException("Blog post 7 not found"), 404, id="not_found"),
        pytest.param(ConflictException("Email already taken"), 409, id="conflict"),
        pytest.param(UnauthorizedException("Not signed in"), 401, id="unauthorized"),
        pytest.param(
            PaymentRequiredException("Credit balance too low"), 402, id="payment_required"
        ),
        pytest.param(ForbiddenException("Not allowed"), 403, id="forbidden"),
        pytest.param(UnprocessableException("Invalid input"), 422, id="unprocessable"),
        pytest.param(RateLimitedException("Generation limit reached"), 429, id="rate_limited"),
        pytest.param(ServiceUnavailableException("LLM unavailable"), 503, id="service_unavailable"),
    ],
)
async def test_exception_handler_maps_standard_exception_to_status_code(
    fastapi_app: FastAPI,
    api_client: AsyncClient,
    standard_exception: Exception,
    expected_status_code: int,
) -> None:
    @fastapi_app.get("/raise-standard-exception")
    async def raise_standard_exception() -> None:
        raise standard_exception

    raise_standard_exception_response = await api_client.get("/raise-standard-exception")

    assert raise_standard_exception_response.status_code == expected_status_code
    assert raise_standard_exception_response.json() == {"detail": str(standard_exception)}


async def test_unhandled_error_returns_500_without_internals(fastapi_app: FastAPI) -> None:
    @fastapi_app.get("/raise-unhandled-error")
    async def raise_unhandled_error() -> None:
        raise RuntimeError("secret-internal-detail")

    api_transport = ASGITransport(app=fastapi_app, raise_app_exceptions=False)
    async with AsyncClient(transport=api_transport, base_url="https://test") as api_client:
        raise_unhandled_error_response = await api_client.get("/raise-unhandled-error")

    assert raise_unhandled_error_response.status_code == 500
    assert "secret-internal-detail" not in raise_unhandled_error_response.text


class _SessionExpiredException(UnauthorizedException):
    pass


def _find_cleared_session_cookie_headers(response: Response) -> list[str]:
    set_cookie_headers = response.headers.get_list("set-cookie")
    return [header for header in set_cookie_headers if header.startswith('sid=""')]


@pytest.mark.parametrize(
    "unauthorized_exception",
    [
        pytest.param(UnauthorizedException("Not signed in"), id="standard"),
        pytest.param(_SessionExpiredException("Session expired"), id="subclass"),
    ],
)
async def test_exception_handler_unauthorized_deletes_session_cookie(
    fastapi_app: FastAPI, api_client: AsyncClient, unauthorized_exception: Exception
) -> None:
    @fastapi_app.get("/raise-unauthorized-exception")
    async def raise_unauthorized_exception() -> None:
        raise unauthorized_exception

    raise_unauthorized_exception_response = await api_client.get("/raise-unauthorized-exception")

    cleared_cookie_headers = _find_cleared_session_cookie_headers(
        raise_unauthorized_exception_response
    )
    assert raise_unauthorized_exception_response.status_code == 401
    assert len(cleared_cookie_headers) == 1
    assert "Max-Age=0" in cleared_cookie_headers[0]
    assert "Path=/" in cleared_cookie_headers[0]


async def test_exception_handler_guarded_route_without_cookie_deletes_session_cookie(
    api_client: AsyncClient,
) -> None:
    find_user_blog_post_page_response = await api_client.get("/blog-posts")

    cleared_cookie_headers = _find_cleared_session_cookie_headers(find_user_blog_post_page_response)
    assert find_user_blog_post_page_response.status_code == 401
    assert len(cleared_cookie_headers) == 1


async def test_exception_handler_guarded_route_with_unknown_session_deletes_session_cookie(
    api_client: AsyncClient,
) -> None:
    api_client.cookies.set("sid", "not-a-real-session-id")

    find_user_blog_post_page_response = await api_client.get("/blog-posts")

    cleared_cookie_headers = _find_cleared_session_cookie_headers(find_user_blog_post_page_response)
    assert find_user_blog_post_page_response.status_code == 401
    assert len(cleared_cookie_headers) == 1


async def test_exception_handler_open_route_with_stale_session_deletes_session_cookie(
    api_client: AsyncClient,
) -> None:
    api_client.cookies.set("sid", "not-a-real-session-id")

    find_public_blog_post_response = await api_client.get(f"/blog-posts/{uuid4()}/public")

    cleared_cookie_headers = _find_cleared_session_cookie_headers(find_public_blog_post_response)
    assert find_public_blog_post_response.status_code == 401
    assert len(cleared_cookie_headers) == 1


async def test_exception_handler_open_route_after_stale_session_cleared_succeeds(
    api_client: AsyncClient,
) -> None:
    api_client.cookies.set("sid", "not-a-real-session-id", domain="test", path="/")
    await api_client.get("/blog-posts/public")

    find_public_blog_post_page_response = await api_client.get("/blog-posts/public")

    assert find_public_blog_post_page_response.status_code == 200


async def test_exception_handler_non_unauthorized_error_sets_no_cookie(
    fastapi_app: FastAPI, api_client: AsyncClient
) -> None:
    @fastapi_app.get("/raise-not-found-exception")
    async def raise_not_found_exception() -> None:
        raise NotFoundException("Blog post 7 not found")

    raise_not_found_exception_response = await api_client.get("/raise-not-found-exception")

    assert raise_not_found_exception_response.status_code == 404
    assert raise_not_found_exception_response.headers.get_list("set-cookie") == []
