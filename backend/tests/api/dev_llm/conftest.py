from collections.abc import AsyncIterator

import pytest
from fastapi import FastAPI
from langgraph.checkpoint.memory import InMemorySaver
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from apps.api.app_factory import create_app
from apps.api.core.dependencies import get_llm_service
from tests.stubs.llm import LlmServiceStub


@pytest.fixture
async def fastapi_app(
    monkeypatch: pytest.MonkeyPatch,
    db_session_factory: async_sessionmaker[AsyncSession],
    redis_client: Redis,
) -> AsyncIterator[FastAPI]:
    monkeypatch.setenv("ENVIRONMENT", "DEVELOPMENT")
    fastapi_app = create_app()
    async with fastapi_app.router.lifespan_context(fastapi_app):
        fastapi_app.state.db_session_factory = db_session_factory
        fastapi_app.state.graph_checkpointer = InMemorySaver()
        yield fastapi_app


@pytest.fixture
def llm_service_stub(fastapi_app: FastAPI) -> LlmServiceStub:
    llm_service_stub = LlmServiceStub()
    fastapi_app.dependency_overrides[get_llm_service] = lambda: llm_service_stub
    return llm_service_stub
