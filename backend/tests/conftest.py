from collections.abc import AsyncIterator, Iterator

import pytest
from redis.asyncio import Redis

from apps.api.core.config import AppSettings

TEST_ENVIRONMENT_VARIABLES = {
    "ENVIRONMENT": "TEST",
    "DATABASE_URL": "postgresql+asyncpg://pb:pb@localhost:5437/pb_test",
    "REDIS_URL": "redis://localhost:6387/15",
}
TEST_REDIS_DB_INDEX = 15


@pytest.fixture(scope="session", autouse=True)
def environment_variables() -> Iterator[None]:
    with pytest.MonkeyPatch.context() as session_monkeypatch:
        for variable_name, variable_value in TEST_ENVIRONMENT_VARIABLES.items():
            session_monkeypatch.setenv(variable_name, variable_value)
        yield


@pytest.fixture(scope="session")
def app_settings() -> AppSettings:
    return AppSettings()


@pytest.fixture
async def redis_client(app_settings: AppSettings) -> AsyncIterator[Redis]:
    redis_client = Redis.from_url(app_settings.redis_url)
    if redis_client.connection_pool.connection_kwargs.get("db") != TEST_REDIS_DB_INDEX:
        raise RuntimeError("Refusing to flush a non-test Redis database")
    await redis_client.flushdb()
    yield redis_client
    await redis_client.flushdb()
    await redis_client.aclose()
