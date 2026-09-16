import pytest
from pydantic import ValidationError
from redis.asyncio import Redis
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from apps.api.app_factory import create_app
from apps.api.core.config import AppSettings


async def test_lifespan_creates_db_engine_and_redis_client_from_settings(
    app_settings: AppSettings,
) -> None:
    fastapi_app = create_app()

    async with fastapi_app.router.lifespan_context(fastapi_app):
        db_engine: AsyncEngine = fastapi_app.state.db_engine
        redis_client: Redis = fastapi_app.state.redis_client
        database_url = db_engine.url.render_as_string(hide_password=False)
        redis_connection_kwargs = redis_client.connection_pool.connection_kwargs

    assert database_url == app_settings.database_url
    assert redis_connection_kwargs["port"] == 6387
    assert redis_connection_kwargs["db"] == 15


async def test_lifespan_disposes_db_engine_on_shutdown() -> None:
    fastapi_app = create_app()

    async with fastapi_app.router.lifespan_context(fastapi_app):
        db_engine: AsyncEngine = fastapi_app.state.db_engine
        async with db_engine.connect() as db_connection:
            await db_connection.execute(text("SELECT 1"))

    assert db_engine.pool.checkedin() == 0


async def test_lifespan_closes_redis_client_on_shutdown() -> None:
    fastapi_app = create_app()

    async with fastapi_app.router.lifespan_context(fastapi_app):
        redis_client: Redis = fastapi_app.state.redis_client
        redis_connection = await redis_client.connection_pool.get_connection()
        await redis_client.connection_pool.release(redis_connection)

    assert not redis_connection.is_connected


async def test_lifespan_invalid_environment_fails_startup(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("ENVIRONMENT", "STAGING")
    fastapi_app = create_app()

    with pytest.raises(ValidationError):
        async with fastapi_app.router.lifespan_context(fastapi_app):
            pass
