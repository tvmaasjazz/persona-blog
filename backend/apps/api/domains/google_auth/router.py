from fastapi import APIRouter
from fastapi.responses import RedirectResponse

from apps.api.core.dependencies import AppSettingsDep
from apps.api.core.types import EnvironmentType
from apps.api.domains.google_auth.dependencies import (
    GoogleOAuthServiceDep,
    GoogleSignInServiceDep,
)
from apps.api.domains.invites.dependencies import InviteServiceDep
from libs.auth.constants import SESSION_COOKIE_NAME
from libs.google_auth.constants import SIGN_IN_ERROR_EXCEPTIONS
from libs.google_auth.utils import GoogleSignInErrorUtils
from libs.invites.utils import InviteUtils

google_auth_router = APIRouter(prefix="/auth/google", tags=["google-auth"])


@google_auth_router.get("/login")
async def get_google_login(
    app_settings: AppSettingsDep,
    google_oauth_service: GoogleOAuthServiceDep,
    invite_service: InviteServiceDep,
    invite_code: str | None = None,
) -> RedirectResponse:
    """Redirects the browser to Google's sign-in page, carrying the invite code if it can
    still be used; an invite that can't be used redirects to the frontend's sign-in page with
    the reason instead."""
    # Refuse an invite that can't be used before going to Google
    if invite_code is not None:
        invite_sign_in_refusal = await invite_service.find_invite_sign_in_refusal(invite_code)
        if invite_sign_in_refusal is not None:
            invite_refusal_url = InviteUtils.build_sign_in_redirect_url(
                app_settings.auth.frontend_url, invite_sign_in_refusal
            )
            return RedirectResponse(invite_refusal_url, status_code=303)

    authorization_url = await google_oauth_service.build_authorization_url(invite_code)
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

    # The frontend root, or its sign-in page with the invite's outcome
    sign_in_redirect_url = InviteUtils.build_sign_in_redirect_url(
        app_settings.auth.frontend_url, google_sign_in_result.invite_sign_in_result_type
    )
    redirect_response = RedirectResponse(sign_in_redirect_url, status_code=303)
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
