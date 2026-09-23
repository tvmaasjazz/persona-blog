import asyncio
import sys
from collections.abc import AsyncIterator, Iterator

import pytest
from redis.asyncio import Redis
from sqlalchemy import make_url, text
from sqlalchemy.ext.asyncio import (
    AsyncConnection,
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from apps.api.core.config import AppSettings
from libs.database.session import create_db_session_factory

TEST_ENVIRONMENT_VARIABLES = {
    "ENVIRONMENT": "TEST",
    "DATABASE_URL": "postgresql+asyncpg://pb:pb@localhost:5437/pb_test",
    "REDIS_URL": "redis://localhost:6387/15",
    "GOOGLE_CLIENT_ID": "test-google-client-id",
    "GOOGLE_CLIENT_SECRET": "test-google-client-secret",
    "OPENAI_API_KEY": "test-openai-api-key",
}
TEST_DATABASE_NAME_SUFFIX = "_test"
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


@pytest.fixture(scope="session")
async def db_engine(
    app_settings: AppSettings, pytestconfig: pytest.Config
) -> AsyncIterator[AsyncEngine]:
    database_url = make_url(app_settings.database_url)
    if database_url.database is None or not database_url.database.endswith(
        TEST_DATABASE_NAME_SUFFIX
    ):
        raise RuntimeError(f"Refusing to reset non-test database {database_url.database!r}")

    db_engine = create_async_engine(database_url)
    async with db_engine.begin() as db_connection:
        await db_connection.execute(text("DROP SCHEMA public CASCADE"))
        await db_connection.execute(text("CREATE SCHEMA public"))
    alembic_process = await asyncio.create_subprocess_exec(
        sys.executable, "-m", "alembic", "upgrade", "head", cwd=pytestconfig.rootpath
    )
    if await alembic_process.wait() != 0:
        raise RuntimeError("alembic upgrade head failed against the test database")
    yield db_engine
    await db_engine.dispose()


@pytest.fixture
async def db_connection(db_engine: AsyncEngine) -> AsyncIterator[AsyncConnection]:
    async with db_engine.connect() as db_connection:
        outer_transaction = await db_connection.begin()
        yield db_connection
        await outer_transaction.rollback()


@pytest.fixture
def db_session_factory(db_connection: AsyncConnection) -> async_sessionmaker[AsyncSession]:
    db_session_factory = create_db_session_factory(db_connection)
    db_session_factory.configure(join_transaction_mode="create_savepoint")
    return db_session_factory


@pytest.fixture
async def db_session(
    db_session_factory: async_sessionmaker[AsyncSession],
) -> AsyncIterator[AsyncSession]:
    async with db_session_factory() as db_session:
        yield db_session


@pytest.fixture
async def redis_client(app_settings: AppSettings) -> AsyncIterator[Redis]:
    redis_client = Redis.from_url(app_settings.redis_url)
    if redis_client.connection_pool.connection_kwargs.get("db") != TEST_REDIS_DB_INDEX:
        raise RuntimeError("Refusing to flush a non-test Redis database")
    await redis_client.flushdb()
    yield redis_client
    await redis_client.flushdb()
    await redis_client.aclose()
