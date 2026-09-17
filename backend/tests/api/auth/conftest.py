import pytest
from fastapi import FastAPI

from apps.api.domains.auth.dependencies import get_google_oauth_service
from tests.stubs.auth import GoogleOAuthServiceStub


@pytest.fixture(autouse=True)
def google_oauth_service_stub(fastapi_app: FastAPI) -> GoogleOAuthServiceStub:
    google_oauth_service_stub = GoogleOAuthServiceStub()
    fastapi_app.dependency_overrides[get_google_oauth_service] = lambda: google_oauth_service_stub
    return google_oauth_service_stub
