from collections.abc import AsyncIterator

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from langgraph.checkpoint.memory import InMemorySaver
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from apps.api.app_factory import create_app
from apps.api.core.config import AppSettings
from apps.api.core.dependencies import get_llm_service
from libs.auth.services import AuthSessionService
from libs.core.services import BackgroundTaskService
from libs.database.orm import UserOrm
from tests.factories.users import insert_user_row
from tests.stubs.llm import LlmServiceStub


@pytest.fixture
async def fastapi_app(
    db_session_factory: async_sessionmaker[AsyncSession], redis_client: Redis
) -> AsyncIterator[FastAPI]:
    fastapi_app = create_app()
    async with fastapi_app.router.lifespan_context(fastapi_app):
        fastapi_app.state.db_session_factory = db_session_factory
        # lifespan leaves this unset under TEST: RediSearch only indexes database 0 and the
        # suite runs on 15, so graph state is kept in memory for the life of the test.
        fastapi_app.state.graph_checkpointer = InMemorySaver()
        yield fastapi_app


@pytest.fixture
async def api_client(fastapi_app: FastAPI) -> AsyncIterator[AsyncClient]:
    api_transport = ASGITransport(app=fastapi_app)
    async with AsyncClient(transport=api_transport, base_url="https://test") as api_client:
        yield api_client


@pytest.fixture
async def signed_in_user(
    api_client: AsyncClient,
    db_session: AsyncSession,
    redis_client: Redis,
    app_settings: AppSettings,
) -> UserOrm:
    user_record = await insert_user_row(db_session)
    auth_session_service = AuthSessionService(
        redis_client=redis_client, auth_settings=app_settings.auth
    )
    session_id = await auth_session_service.create_session(
        user_id=user_record.id, user_identity=user_record.identity
    )
    api_client.cookies.set("sid", session_id)
    return user_record


@pytest.fixture
async def other_user_client(
    fastapi_app: FastAPI,
    db_session: AsyncSession,
    redis_client: Redis,
    app_settings: AppSettings,
) -> AsyncIterator[AsyncClient]:
    other_user_record = await insert_user_row(db_session)
    auth_session_service = AuthSessionService(
        redis_client=redis_client, auth_settings=app_settings.auth
    )
    other_session_id = await auth_session_service.create_session(
        user_id=other_user_record.id, user_identity=other_user_record.identity
    )
    other_api_transport = ASGITransport(app=fastapi_app)
    async with AsyncClient(
        transport=other_api_transport, base_url="https://test", cookies={"sid": other_session_id}
    ) as other_api_client:
        yield other_api_client


@pytest.fixture
def llm_service_stub(fastapi_app: FastAPI) -> LlmServiceStub:
    llm_service_stub = LlmServiceStub()
    fastapi_app.dependency_overrides[get_llm_service] = lambda: llm_service_stub
    return llm_service_stub


@pytest.fixture
def background_task_service(fastapi_app: FastAPI) -> BackgroundTaskService:
    return fastapi_app.state.background_task_service
