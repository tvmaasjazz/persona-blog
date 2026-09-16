from collections.abc import AsyncIterator

import pytest
from fastapi import FastAPI
from httpx import AsyncClient
from redis.asyncio import Redis
from sqlalchemy import make_url
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine

from apps.api.core.config import AppSettings
from apps.api.core.types import EnvironmentType


@pytest.fixture
async def unreachable_db_engine(app_settings: AppSettings) -> AsyncIterator[AsyncEngine]:
    unreachable_database_url = make_url(app_settings.database_url).set(port=1)
    unreachable_db_engine = create_async_engine(unreachable_database_url)
    yield unreachable_db_engine
    await unreachable_db_engine.dispose()


@pytest.fixture
async def unreachable_redis_client() -> AsyncIterator[Redis]:
    unreachable_redis_client = Redis.from_url("redis://localhost:1/0")
    yield unreachable_redis_client
    await unreachable_redis_client.aclose()


async def test_get_health_returns_status_and_settings(
    fastapi_app: FastAPI, api_client: AsyncClient
) -> None:
    fastapi_app.state.settings = AppSettings(
        app_name="Health Test API",
        environment=EnvironmentType.TEST,
        database_url=fastapi_app.state.settings.database_url,
        redis_url=fastapi_app.state.settings.redis_url,
    )

    get_health_response = await api_client.get("/health")

    assert get_health_response.status_code == 200
    assert get_health_response.json() == {
        "status": "OK",
        "app_name": "Health Test API",
        "environment": "TEST",
        "postgres": "REACHABLE",
        "redis": "REACHABLE",
    }


async def test_get_health_postgres_unreachable_returns_degraded(
    fastapi_app: FastAPI, api_client: AsyncClient, unreachable_db_engine: AsyncEngine
) -> None:
    fastapi_app.state.db_engine = unreachable_db_engine

    get_health_response = await api_client.get("/health")

    response_body = get_health_response.json()
    assert get_health_response.status_code == 200
    assert response_body["status"] == "DEGRADED"
    assert response_body["postgres"] == "UNREACHABLE"
    assert response_body["redis"] == "REACHABLE"


async def test_get_health_redis_unreachable_returns_degraded(
    fastapi_app: FastAPI, api_client: AsyncClient, unreachable_redis_client: Redis
) -> None:
    fastapi_app.state.redis_client = unreachable_redis_client

    get_health_response = await api_client.get("/health")

    response_body = get_health_response.json()
    assert get_health_response.status_code == 200
    assert response_body["status"] == "DEGRADED"
    assert response_body["postgres"] == "REACHABLE"
    assert response_body["redis"] == "UNREACHABLE"
