from urllib.parse import parse_qs, urlparse

import httpx
import pytest
from redis.asyncio import Redis

from libs.auth.services import OAuthStateService
from libs.auth.settings import AuthSettings
from libs.core.exceptions import ServiceUnavailableException, UnauthorizedException
from libs.google_auth.results import GoogleIdentityResult
from libs.google_auth.services import GoogleOAuthService
from libs.google_auth.settings import GoogleAuthSettings
from tests.payloads.google import build_google_id_token, build_google_token_response_body
from tests.stubs.http import HttpHandlerStub


def _extract_query_params(url: str) -> dict[str, list[str]]:
    return parse_qs(urlparse(url).query)


async def test_build_authorization_url_returns_google_authorization_url_with_query_params(
    google_oauth_service: GoogleOAuthService,
) -> None:
    authorization_url = await google_oauth_service.build_authorization_url()

    parsed_url = urlparse(authorization_url)
    query_params = _extract_query_params(authorization_url)
    assert f"{parsed_url.scheme}://{parsed_url.netloc}{parsed_url.path}" == (
        "https://accounts.google.com/o/oauth2/v2/auth"
    )
    assert query_params["client_id"] == ["test-google-client-id"]
    assert query_params["redirect_uri"] == ["http://localhost:8000/auth/google/callback"]
    assert query_params["response_type"] == ["code"]
    assert query_params["scope"] == ["openid email profile"]
    assert query_params["code_challenge_method"] == ["S256"]
    assert query_params["state"][0] != ""
    assert query_params["nonce"][0] != ""


async def test_build_authorization_url_stores_state_with_ttl(
    redis_client: Redis, google_handler_stub: HttpHandlerStub
) -> None:
    google_transport = httpx.MockTransport(google_handler_stub.handle)
    oauth_state_service = OAuthStateService(
        redis_client=redis_client, auth_settings=AuthSettings(oauth_state_ttl_seconds=120)
    )
    async with httpx.AsyncClient(transport=google_transport) as google_http_client:
        google_oauth_service = GoogleOAuthService(
            http_client=google_http_client,
            oauth_state_service=oauth_state_service,
            google_auth_settings=GoogleAuthSettings(),
            google_client_id="test-google-client-id",
            google_client_secret="test-google-client-secret",
        )

        authorization_url = await google_oauth_service.build_authorization_url()

    oauth_state = _extract_query_params(authorization_url)["state"][0]
    state_ttl_seconds = await redis_client.ttl(f"oauth-state:{oauth_state}")
    assert 0 < state_ttl_seconds <= 120


async def test_build_authorization_url_two_calls_produce_different_state(
    google_oauth_service: GoogleOAuthService,
) -> None:
    first_authorization_url = await google_oauth_service.build_authorization_url()
    second_authorization_url = await google_oauth_service.build_authorization_url()

    first_state = _extract_query_params(first_authorization_url)["state"][0]
    second_state = _extract_query_params(second_authorization_url)["state"][0]
    assert first_state != second_state


async def test_exchange_code_for_identity_returns_identity_and_posts_code_verifier(
    google_oauth_service: GoogleOAuthService, google_handler_stub: HttpHandlerStub
) -> None:
    authorization_url = await google_oauth_service.build_authorization_url()
    query_params = _extract_query_params(authorization_url)
    oauth_state = query_params["state"][0]
    oauth_nonce = query_params["nonce"][0]
    google_id_token = build_google_id_token(
        nonce=oauth_nonce,
        sub="google-subject-9",
        email="ada@example.com",
        name="Ada Lovelace",
        picture="https://example.com/ada.png",
    )
    google_handler_stub.handle_responses.append(
        httpx.Response(200, json=build_google_token_response_body(id_token=google_id_token))
    )

    google_identity_result = await google_oauth_service.exchange_code_for_identity(
        "auth-code-1", oauth_state
    )

    sent_request_body = parse_qs(google_handler_stub.handle_requests[0].content.decode())
    assert google_identity_result == GoogleIdentityResult(
        provider_subject="google-subject-9",
        email="ada@example.com",
        is_email_verified=True,
        display_name="Ada Lovelace",
        avatar_url="https://example.com/ada.png",
    )
    assert sent_request_body["code"] == ["auth-code-1"]
    assert sent_request_body["client_id"] == ["test-google-client-id"]
    assert sent_request_body["client_secret"] == ["test-google-client-secret"]
    assert sent_request_body["redirect_uri"] == ["http://localhost:8000/auth/google/callback"]
    assert sent_request_body["grant_type"] == ["authorization_code"]
    assert sent_request_body["code_verifier"][0] != ""


async def test_exchange_code_for_identity_state_already_consumed_raises_unauthorized_exception(
    google_oauth_service: GoogleOAuthService, google_handler_stub: HttpHandlerStub
) -> None:
    authorization_url = await google_oauth_service.build_authorization_url()
    query_params = _extract_query_params(authorization_url)
    oauth_state = query_params["state"][0]
    oauth_nonce = query_params["nonce"][0]
    google_handler_stub.handle_responses.append(
        httpx.Response(
            200,
            json=build_google_token_response_body(
                id_token=build_google_id_token(nonce=oauth_nonce)
            ),
        )
    )
    await google_oauth_service.exchange_code_for_identity("auth-code-1", oauth_state)

    with pytest.raises(UnauthorizedException):
        await google_oauth_service.exchange_code_for_identity("auth-code-1", oauth_state)


async def test_exchange_code_for_identity_unknown_state_raises_unauthorized_exception(
    google_oauth_service: GoogleOAuthService,
) -> None:
    with pytest.raises(UnauthorizedException):
        await google_oauth_service.exchange_code_for_identity("auth-code-1", "unknown-state")


async def test_exchange_code_for_identity_non_200_token_response_raises_unauthorized_exception(
    google_oauth_service: GoogleOAuthService, google_handler_stub: HttpHandlerStub
) -> None:
    authorization_url = await google_oauth_service.build_authorization_url()
    oauth_state = _extract_query_params(authorization_url)["state"][0]
    google_handler_stub.handle_responses.append(
        httpx.Response(400, json={"error": "invalid_grant"})
    )

    with pytest.raises(UnauthorizedException):
        await google_oauth_service.exchange_code_for_identity("auth-code-1", oauth_state)


async def test_exchange_code_for_identity_missing_id_token_raises_service_unavailable_exception(
    google_oauth_service: GoogleOAuthService, google_handler_stub: HttpHandlerStub
) -> None:
    authorization_url = await google_oauth_service.build_authorization_url()
    oauth_state = _extract_query_params(authorization_url)["state"][0]
    google_handler_stub.handle_responses.append(httpx.Response(200, json={}))

    with pytest.raises(ServiceUnavailableException):
        await google_oauth_service.exchange_code_for_identity("auth-code-1", oauth_state)


async def test_exchange_code_for_identity_transport_error_raises_service_unavailable_exception(
    google_oauth_service: GoogleOAuthService, google_handler_stub: HttpHandlerStub
) -> None:
    authorization_url = await google_oauth_service.build_authorization_url()
    oauth_state = _extract_query_params(authorization_url)["state"][0]
    google_handler_stub.handle_error = httpx.ConnectError("connection refused")

    with pytest.raises(ServiceUnavailableException):
        await google_oauth_service.exchange_code_for_identity("auth-code-1", oauth_state)


async def test_exchange_code_for_identity_wrong_aud_raises_unauthorized_exception(
    google_oauth_service: GoogleOAuthService, google_handler_stub: HttpHandlerStub
) -> None:
    authorization_url = await google_oauth_service.build_authorization_url()
    query_params = _extract_query_params(authorization_url)
    oauth_state = query_params["state"][0]
    oauth_nonce = query_params["nonce"][0]
    google_handler_stub.handle_responses.append(
        httpx.Response(
            200,
            json=build_google_token_response_body(
                id_token=build_google_id_token(aud="another-client-id", nonce=oauth_nonce)
            ),
        )
    )

    with pytest.raises(UnauthorizedException):
        await google_oauth_service.exchange_code_for_identity("auth-code-1", oauth_state)


async def test_exchange_code_for_identity_wrong_iss_raises_unauthorized_exception(
    google_oauth_service: GoogleOAuthService, google_handler_stub: HttpHandlerStub
) -> None:
    authorization_url = await google_oauth_service.build_authorization_url()
    query_params = _extract_query_params(authorization_url)
    oauth_state = query_params["state"][0]
    oauth_nonce = query_params["nonce"][0]
    google_handler_stub.handle_responses.append(
        httpx.Response(
            200,
            json=build_google_token_response_body(
                id_token=build_google_id_token(iss="https://evil.example.com", nonce=oauth_nonce)
            ),
        )
    )

    with pytest.raises(UnauthorizedException):
        await google_oauth_service.exchange_code_for_identity("auth-code-1", oauth_state)


async def test_exchange_code_for_identity_mismatched_nonce_raises_unauthorized_exception(
    google_oauth_service: GoogleOAuthService, google_handler_stub: HttpHandlerStub
) -> None:
    authorization_url = await google_oauth_service.build_authorization_url()
    oauth_state = _extract_query_params(authorization_url)["state"][0]
    google_handler_stub.handle_responses.append(
        httpx.Response(
            200,
            json=build_google_token_response_body(
                id_token=build_google_id_token(nonce="a-different-nonce")
            ),
        )
    )

    with pytest.raises(UnauthorizedException):
        await google_oauth_service.exchange_code_for_identity("auth-code-1", oauth_state)


async def test_exchange_code_for_identity_expired_token_raises_unauthorized_exception(
    google_oauth_service: GoogleOAuthService, google_handler_stub: HttpHandlerStub
) -> None:
    authorization_url = await google_oauth_service.build_authorization_url()
    query_params = _extract_query_params(authorization_url)
    oauth_state = query_params["state"][0]
    oauth_nonce = query_params["nonce"][0]
    google_handler_stub.handle_responses.append(
        httpx.Response(
            200,
            json=build_google_token_response_body(
                id_token=build_google_id_token(nonce=oauth_nonce, exp=1)
            ),
        )
    )

    with pytest.raises(UnauthorizedException):
        await google_oauth_service.exchange_code_for_identity("auth-code-1", oauth_state)
