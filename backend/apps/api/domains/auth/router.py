from fastapi import APIRouter, Cookie, Response
from fastapi.responses import RedirectResponse

from apps.api.core.dependencies import AppSettingsDep, AuthUserDep
from apps.api.core.dtos import EmptyResponseDto
from apps.api.core.types import EnvironmentType
from apps.api.domains.auth.dependencies import (
    AuthSessionServiceDep,
    GoogleOAuthServiceDep,
    UserTransactionServiceDep,
)
from libs.auth.constants import SESSION_COOKIE_NAME
from libs.auth.types import AuthProviderType
from libs.users.inputs import FindOrCreateUserFromAuthProviderInput

auth_router = APIRouter(prefix="/auth", tags=["auth"])


@auth_router.get("/google/login")
async def get_google_login(google_oauth_service: GoogleOAuthServiceDep) -> RedirectResponse:
    authorization_url = await google_oauth_service.build_authorization_url()
    return RedirectResponse(authorization_url, status_code=307)


@auth_router.get("/google/callback")
async def get_google_callback(
    code: str,
    state: str,
    app_settings: AppSettingsDep,
    google_oauth_service: GoogleOAuthServiceDep,
    auth_session_service: AuthSessionServiceDep,
    user_service: UserTransactionServiceDep,
) -> RedirectResponse:
    google_identity_result = await google_oauth_service.exchange_code_for_identity(code, state)
    find_or_create_user_from_auth_provider_input = FindOrCreateUserFromAuthProviderInput(
        provider=AuthProviderType.GOOGLE,
        provider_subject=google_identity_result.provider_subject,
        email=google_identity_result.email,
        is_email_verified=google_identity_result.is_email_verified,
        display_name=google_identity_result.display_name,
        avatar_url=google_identity_result.avatar_url,
    )
    find_or_create_user_from_auth_provider_result = (
        await user_service.find_or_create_user_from_auth_provider(
            find_or_create_user_from_auth_provider_input
        )
    )
    session_id = await auth_session_service.create_session(
        user_id=find_or_create_user_from_auth_provider_result.id,
        user_identity=find_or_create_user_from_auth_provider_result.identity,
    )

    redirect_response = RedirectResponse(app_settings.auth.frontend_url, status_code=303)
    redirect_response.set_cookie(
        SESSION_COOKIE_NAME,
        session_id,
        httponly=True,
        samesite="lax",
        secure=app_settings.environment != EnvironmentType.DEVELOPMENT,
        max_age=app_settings.auth.session_ttl_seconds,
        path="/",
    )
    return redirect_response


@auth_router.post("/logout")
async def logout(
    response: Response,
    auth_user: AuthUserDep,
    auth_session_service: AuthSessionServiceDep,
    session_id: str | None = Cookie(default=None, alias=SESSION_COOKIE_NAME),
) -> EmptyResponseDto:
    if session_id is not None:
        await auth_session_service.delete_session(session_id)

    response.delete_cookie(SESSION_COOKIE_NAME, path="/")
    return EmptyResponseDto()
