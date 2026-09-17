from typing import Annotated

from fastapi import Depends, Request

from apps.api.core.config import AppSettings
from apps.api.core.dependencies import DbTransactionDep
from libs.auth.services import AuthSessionService, GoogleOAuthService
from libs.users.services import UserService


def get_google_oauth_service(request: Request) -> GoogleOAuthService:
    app_settings: AppSettings = request.app.state.settings
    return GoogleOAuthService(
        http_client=request.app.state.http_client,
        redis_client=request.app.state.redis_client,
        auth_settings=app_settings.auth,
        google_client_id=app_settings.google_client_id,
        google_client_secret=app_settings.google_client_secret,
    )


def get_auth_session_service(request: Request) -> AuthSessionService:
    app_settings: AppSettings = request.app.state.settings
    return AuthSessionService(
        redis_client=request.app.state.redis_client, auth_settings=app_settings.auth
    )


def get_user_transaction_service(db_session: DbTransactionDep) -> UserService:
    return UserService(db_session=db_session)


GoogleOAuthServiceDep = Annotated[GoogleOAuthService, Depends(get_google_oauth_service)]
UserTransactionServiceDep = Annotated[UserService, Depends(get_user_transaction_service)]
AuthSessionServiceDep = Annotated[AuthSessionService, Depends(get_auth_session_service)]
