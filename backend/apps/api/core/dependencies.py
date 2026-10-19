from collections.abc import AsyncIterator
from typing import Annotated

from fastapi import BackgroundTasks, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.datastructures import State

from apps.api.core.config import AppSettings
from libs.auth.constants import SESSION_COOKIE_NAME
from libs.auth.results import AuthUser
from libs.auth.services import AuthSessionService
from libs.core.exceptions import UnauthorizedException
from libs.llm.services import LlmCallService, LlmService, OpenAiLlmService
from libs.llm.types import LlmProviderType
from libs.users.after_response_tasks import record_user_activity


def get_app_settings(request: Request) -> AppSettings:
    """Returns the settings instance stored on app state at startup."""
    return request.app.state.settings


async def get_db_session(request: Request) -> AsyncIterator[AsyncSession]:
    """Yields a db session for the request that never commits, so writes through it are lost."""
    db_session_factory = request.app.state.db_session_factory
    async with db_session_factory() as db_session:
        yield db_session


async def get_db_transaction(request: Request) -> AsyncIterator[AsyncSession]:
    """Yields a db session inside a transaction that commits after the route returns."""
    db_session_factory = request.app.state.db_session_factory
    async with db_session_factory() as db_session, db_session.begin():
        yield db_session


async def get_auth_user(request: Request, after_response_tasks: BackgroundTasks) -> AuthUser:
    """Resolves the session cookie to the signed-in user, raising UnauthorizedException
    when there isn't one, and records their activity after the response."""
    # Read the session cookie
    session_id = request.cookies.get(SESSION_COOKIE_NAME)
    if session_id is None:
        raise UnauthorizedException("Not signed in")

    # Resolve the session to its user
    app_settings: AppSettings = request.app.state.settings
    auth_session_service = AuthSessionService(
        redis_client=request.app.state.redis_client, auth_settings=app_settings.auth
    )
    auth_user = await auth_session_service.find_session(session_id)

    # Record activity after the response, so the request never waits on the write
    after_response_tasks.add_task(
        record_user_activity,
        db_session_factory=request.app.state.db_session_factory,
        redis_client=request.app.state.redis_client,
        user_settings=app_settings.users,
        user_id=auth_user.id,
    )
    return auth_user


def build_llm_service(app_state: State) -> LlmService:
    """Builds the LLM service from app state, so lifespan and routes can both use it."""
    app_settings: AppSettings = app_state.settings
    openai_llm_service = OpenAiLlmService(
        openai_client=app_state.openai_client,
        llm_settings=app_settings.llm,
    )
    llm_call_service = LlmCallService(db_session_factory=app_state.db_session_factory)
    return LlmService(
        llm_provider_services={LlmProviderType.OPENAI: openai_llm_service},
        llm_call_service=llm_call_service,
        llm_settings=app_settings.llm,
    )


def get_llm_service(request: Request) -> LlmService:
    """Builds the LLM service from the app state of the request's app."""
    return build_llm_service(request.app.state)


LlmServiceDep = Annotated[LlmService, Depends(get_llm_service)]


AppSettingsDep = Annotated[AppSettings, Depends(get_app_settings)]
AuthUserDep = Annotated[AuthUser, Depends(get_auth_user)]
DbSessionDep = Annotated[AsyncSession, Depends(get_db_session)]
DbTransactionDep = Annotated[AsyncSession, Depends(get_db_transaction)]
