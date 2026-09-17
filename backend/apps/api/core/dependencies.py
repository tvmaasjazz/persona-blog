from collections.abc import AsyncIterator
from typing import Annotated

from fastapi import Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.core.config import AppSettings
from libs.auth.constants import SESSION_COOKIE_NAME
from libs.auth.results import AuthUser
from libs.auth.services import AuthSessionService
from libs.core.exceptions import UnauthorizedException


def get_app_settings(request: Request) -> AppSettings:
    return request.app.state.settings


async def get_db_session(request: Request) -> AsyncIterator[AsyncSession]:
    db_session_factory = request.app.state.db_session_factory
    async with db_session_factory() as db_session:
        yield db_session


async def get_db_transaction(request: Request) -> AsyncIterator[AsyncSession]:
    db_session_factory = request.app.state.db_session_factory
    async with db_session_factory() as db_session, db_session.begin():
        yield db_session


async def get_auth_user(request: Request) -> AuthUser:
    session_id = request.cookies.get(SESSION_COOKIE_NAME)
    if session_id is None:
        raise UnauthorizedException("Not signed in")

    app_settings: AppSettings = request.app.state.settings
    auth_session_service = AuthSessionService(
        redis_client=request.app.state.redis_client, auth_settings=app_settings.auth
    )
    return await auth_session_service.find_session(session_id)


AppSettingsDep = Annotated[AppSettings, Depends(get_app_settings)]
AuthUserDep = Annotated[AuthUser, Depends(get_auth_user)]
DbSessionDep = Annotated[AsyncSession, Depends(get_db_session)]
DbTransactionDep = Annotated[AsyncSession, Depends(get_db_transaction)]
