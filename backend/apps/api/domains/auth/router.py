from fastapi import APIRouter, Cookie, Response

from apps.api.core.dependencies import AuthUserDep
from apps.api.core.dtos import EmptyResponseDto
from apps.api.domains.auth.dependencies import AuthSessionServiceDep
from libs.auth.constants import SESSION_COOKIE_NAME

auth_router = APIRouter(prefix="/auth", tags=["auth"])


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
