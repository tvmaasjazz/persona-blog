from collections.abc import AsyncIterator
from datetime import UTC, datetime
from typing import Annotated

from fastapi import BackgroundTasks, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.core.config import AppSettings
from libs.auth.constants import SESSION_COOKIE_NAME
from libs.auth.results import AuthUser
from libs.auth.services import AuthSessionService
from libs.core.exceptions import UnauthorizedException
from libs.llm.services import LlmCallService, LlmService, OpenAiLlmService
from libs.llm.types import LlmProviderType
from libs.users.tasks import record_user_activity


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


async def get_auth_user(request: Request, background_tasks: BackgroundTasks) -> AuthUser:
    session_id = request.cookies.get(SESSION_COOKIE_NAME)
    if session_id is None:
        raise UnauthorizedException("Not signed in")

    app_settings: AppSettings = request.app.state.settings
    auth_session_service = AuthSessionService(
        redis_client=request.app.state.redis_client, auth_settings=app_settings.auth
    )
    auth_user = await auth_session_service.find_session(session_id)

    # After the response, so a signed-in request never waits on the activity write.
    background_tasks.add_task(
        record_user_activity,
        db_session_factory=request.app.state.db_session_factory,
        redis_client=request.app.state.redis_client,
        user_settings=app_settings.users,
        user_id=auth_user.id,
        activity_at=datetime.now(UTC),
    )
    return auth_user


# This sits in core/ rather than a domain even though only dev_llm uses it today, which the
# Layer rules' "used by only two domains" line argues against. Domains can't import each
# other, so the alternative is every domain that reaches an LLM rebuilding the same provider
# map. generate_text is the second consumer in the next step; revisit the placement, and the
# rule, once it's clear how many domains really need it.
def get_llm_service(request: Request) -> LlmService:
    app_settings: AppSettings = request.app.state.settings
    openai_llm_service = OpenAiLlmService(openai_client=request.app.state.openai_client)
    llm_call_service = LlmCallService(db_session_factory=request.app.state.db_session_factory)
    return LlmService(
        llm_provider_services={LlmProviderType.OPENAI: openai_llm_service},
        llm_call_service=llm_call_service,
        llm_settings=app_settings.llm,
    )


AppSettingsDep = Annotated[AppSettings, Depends(get_app_settings)]
AuthUserDep = Annotated[AuthUser, Depends(get_auth_user)]
DbSessionDep = Annotated[AsyncSession, Depends(get_db_session)]
DbTransactionDep = Annotated[AsyncSession, Depends(get_db_transaction)]
LlmServiceDep = Annotated[LlmService, Depends(get_llm_service)]
