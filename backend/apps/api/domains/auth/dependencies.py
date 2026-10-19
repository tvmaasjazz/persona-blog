from typing import Annotated

from fastapi import Depends, Request

from apps.api.core.config import AppSettings
from libs.auth.services import AuthSessionService


def get_auth_session_service(request: Request) -> AuthSessionService:
    """Builds the auth session service on the app's Redis client and auth settings."""
    app_settings: AppSettings = request.app.state.settings
    return AuthSessionService(
        redis_client=request.app.state.redis_client, auth_settings=app_settings.auth
    )


AuthSessionServiceDep = Annotated[AuthSessionService, Depends(get_auth_session_service)]
