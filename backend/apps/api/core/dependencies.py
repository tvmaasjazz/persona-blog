from collections.abc import AsyncIterator
from typing import Annotated

from fastapi import Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.core.config import AppSettings


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


AppSettingsDep = Annotated[AppSettings, Depends(get_app_settings)]
DbSessionDep = Annotated[AsyncSession, Depends(get_db_session)]
DbTransactionDep = Annotated[AsyncSession, Depends(get_db_transaction)]
