from fastapi import APIRouter
from fastapi.responses import RedirectResponse

from apps.api.core.dependencies import AppSettingsDep
from apps.api.core.types import EnvironmentType
from apps.api.domains.google_auth.dependencies import (
    GoogleOAuthServiceDep,
    GoogleSignInServiceDep,
)
from libs.auth.constants import SESSION_COOKIE_NAME
from libs.google_auth.constants import SIGN_IN_ERROR_EXCEPTIONS
from libs.google_auth.utils import GoogleSignInErrorUtils

google_auth_router = APIRouter(prefix="/auth/google", tags=["google-auth"])


@google_auth_router.get("/login")
async def get_google_login(
    google_oauth_service: GoogleOAuthServiceDep,
) -> RedirectResponse:
    """Redirects the browser to Google's sign-in page."""
    authorization_url = await google_oauth_service.build_authorization_url()
    return RedirectResponse(authorization_url, status_code=307)


@google_auth_router.get("/callback")
async def get_google_callback(
    code: str,
    state: str,
    app_settings: AppSettingsDep,
    google_sign_in_service: GoogleSignInServiceDep,
) -> RedirectResponse:
    """Completes Google sign-in, sets the session cookie and redirects to the frontend; a
    known sign-in failure redirects to its sign-in page with the error code instead."""
    try:
        google_sign_in_result = await google_sign_in_service.sign_in_with_google(code, state)
    except SIGN_IN_ERROR_EXCEPTIONS as sign_in_exception:
        sign_in_error_type = GoogleSignInErrorUtils.find_sign_in_error_type(sign_in_exception)
        sign_in_error_url = f"{app_settings.auth.frontend_url}/sign-in?error={sign_in_error_type}"
        return RedirectResponse(sign_in_error_url, status_code=303)

    redirect_response = RedirectResponse(app_settings.auth.frontend_url, status_code=303)
    redirect_response.set_cookie(
        SESSION_COOKIE_NAME,
        google_sign_in_result.session_id,
        httponly=True,
        samesite="lax",
        secure=app_settings.environment != EnvironmentType.DEVELOPMENT,
        max_age=app_settings.auth.session_ttl_seconds,
        path="/",
    )
    return redirect_response
