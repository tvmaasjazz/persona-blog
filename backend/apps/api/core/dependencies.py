from collections.abc import AsyncIterator, Awaitable, Callable
from typing import Annotated

from fastapi import BackgroundTasks, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.datastructures import State

from apps.api.core.config import AppSettings
from libs.auth.constants import SESSION_COOKIE_NAME
from libs.auth.results import AuthUser
from libs.auth.services import AuthSessionService
from libs.core.exceptions import ForbiddenException, UnauthorizedException
from libs.llm.services import LlmCallService, LlmService, OpenAiLlmService
from libs.llm.types import LlmProviderType
from libs.permissions.types import PermissionType
from libs.users.after_response_tasks import record_user_activity
from libs.users.services import AnonymousUserKeyService

# Used when a request carries neither the proxy header nor a client address
UNKNOWN_CLIENT_IP = "unknown"


def get_app_settings(request: Request) -> AppSettings:
    return request.app.state.settings


async def get_db_session(request: Request) -> AsyncIterator[AsyncSession]:
    """Yields the request's session in a transaction that commits after the route returns,
    or rolls back if it raises."""
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


async def get_optional_auth_user(
    request: Request, after_response_tasks: BackgroundTasks
) -> AuthUser | None:
    """Returns None when the request has no session cookie; otherwise resolves it like
    get_auth_user, so an expired or invalid session still raises UnauthorizedException
    and activity is still recorded."""
    if request.cookies.get(SESSION_COOKIE_NAME) is None:
        return None
    return await get_auth_user(request, after_response_tasks)


def require_permissions(*permission_types: PermissionType) -> Callable[[AuthUser], Awaitable[None]]:
    """Builds a dependency that raises ForbiddenException unless the signed-in user holds
    every permission named, and records them on `required_permissions`."""
    required_permissions = frozenset(permission_types)

    async def check_permissions(auth_user: AuthUserDep) -> None:
        if not required_permissions <= auth_user.permissions:
            raise ForbiddenException("You don't have permission to do this")

    check_permissions.required_permissions = required_permissions  # type: ignore[attr-defined]
    return check_permissions


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
    return build_llm_service(request.app.state)


LlmServiceDep = Annotated[LlmService, Depends(get_llm_service)]


AppSettingsDep = Annotated[AppSettings, Depends(get_app_settings)]
AuthUserDep = Annotated[AuthUser, Depends(get_auth_user)]
OptionalAuthUserDep = Annotated[AuthUser | None, Depends(get_optional_auth_user)]
DbSessionDep = Annotated[AsyncSession, Depends(get_db_session)]


def get_client_ip(request: Request) -> str:
    """Returns the client's IP: the last entry of the configured proxy header when the
    request has it, otherwise the connection's own address."""
    app_settings: AppSettings = request.app.state.settings
    client_ip_header = app_settings.users.client_ip_header
    if client_ip_header is not None:
        client_ip_header_value = request.headers.get(client_ip_header)
        if client_ip_header_value:
            # A proxy appends the address it saw, so the last entry is the one to trust
            return client_ip_header_value.split(",")[-1].strip()
    if request.client is not None:
        return request.client.host
    return UNKNOWN_CLIENT_IP


ClientIpDep = Annotated[str, Depends(get_client_ip)]


async def get_anonymous_user_key(
    request: Request, auth_user: OptionalAuthUserDep, client_ip: ClientIpDep
) -> str | None:
    """Returns None for a signed-in user; otherwise today's anonymous key for the client's
    IP and user agent."""
    if auth_user is not None:
        return None
    anonymous_user_key_service = AnonymousUserKeyService(
        redis_client=request.app.state.redis_client
    )
    user_agent = request.headers.get("user-agent", "")
    return await anonymous_user_key_service.build_anonymous_user_key(client_ip, user_agent)


AnonymousUserKeyDep = Annotated[str | None, Depends(get_anonymous_user_key)]
