import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from libs.core.exceptions import (
    ConflictException,
    ForbiddenException,
    NotFoundException,
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
