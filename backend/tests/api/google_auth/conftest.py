import pytest
from fastapi import FastAPI
from redis.asyncio import Redis

from apps.api.core.config import AppSettings
from apps.api.domains.google_auth.dependencies import get_google_oauth_service
from libs.auth.services import OAuthStateService
from tests.stubs.google_auth import GoogleOAuthServiceStub


@pytest.fixture(autouse=True)
def google_oauth_service_stub(
    fastapi_app: FastAPI, redis_client: Redis, app_settings: AppSettings
) -> GoogleOAuthServiceStub:
    google_oauth_service_stub = GoogleOAuthServiceStub()
    google_oauth_service_stub.build_authorization_url_oauth_state_service = OAuthStateService(
        redis_client=redis_client, auth_settings=app_settings.auth
    )
    fastapi_app.dependency_overrides[get_google_oauth_service] = lambda: google_oauth_service_stub
    return google_oauth_service_stub
