from collections.abc import AsyncIterator

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from redis.asyncio import Redis

from apps.api.app_factory import create_app


@pytest.fixture
async def fastapi_app(redis_client: Redis) -> AsyncIterator[FastAPI]:
    fastapi_app = create_app()
    async with fastapi_app.router.lifespan_context(fastapi_app):
        yield fastapi_app


@pytest.fixture
async def api_client(fastapi_app: FastAPI) -> AsyncIterator[AsyncClient]:
    api_transport = ASGITransport(app=fastapi_app)
    async with AsyncClient(transport=api_transport, base_url="https://test") as api_client:
        yield api_client
