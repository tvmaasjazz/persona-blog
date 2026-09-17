from collections.abc import AsyncIterator

import httpx
import pytest
from redis.asyncio import Redis

from libs.auth.services import OAuthStateService
from libs.auth.settings import AuthSettings
from libs.google_auth.services import GoogleOAuthService
from libs.google_auth.settings import GoogleAuthSettings
from tests.stubs.http import HttpHandlerStub


@pytest.fixture
def google_handler_stub() -> HttpHandlerStub:
    return HttpHandlerStub()


@pytest.fixture
async def google_oauth_service(
    redis_client: Redis, google_handler_stub: HttpHandlerStub
) -> AsyncIterator[GoogleOAuthService]:
    google_transport = httpx.MockTransport(google_handler_stub.handle)
    oauth_state_service = OAuthStateService(redis_client=redis_client, auth_settings=AuthSettings())
    async with httpx.AsyncClient(transport=google_transport) as google_http_client:
        yield GoogleOAuthService(
            http_client=google_http_client,
            oauth_state_service=oauth_state_service,
            google_auth_settings=GoogleAuthSettings(),
            google_client_id="test-google-client-id",
            google_client_secret="test-google-client-secret",
        )
