import os
import re

from redis.asyncio import Redis
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker

from apps.api.app_factory import create_app
from apps.api.core.config import AppSettings
from apps.api.lifespan import build_worker_id


async def test_lifespan_creates_db_resources_and_redis_client_from_settings(
    app_settings: AppSettings,
) -> None:
    fastapi_app = create_app()

    async with fastapi_app.router.lifespan_context(fastapi_app):
        db_engine: AsyncEngine = fastapi_app.state.db_engine
        redis_client: Redis = fastapi_app.state.redis_client
        db_session_factory = fastapi_app.state.db_session_factory
        database_url = db_engine.url.render_as_string(hide_password=False)
        redis_connection_kwargs = redis_client.connection_pool.connection_kwargs

    assert database_url == app_settings.database_url
    assert isinstance(db_session_factory, async_sessionmaker)
    assert db_session_factory.kw["bind"] is db_engine
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


def test_build_worker_id_uses_truncated_replica_id_and_pid() -> None:
    app_settings = AppSettings(railway_replica_id="abcdef0123456789")

    worker_id = build_worker_id(app_settings)

    assert re.fullmatch(rf"abcdef01-pid{os.getpid()}-[0-9a-f]{{4}}", worker_id)


def test_build_worker_id_without_replica_id_uses_host_name_and_pid() -> None:
    app_settings = AppSettings(railway_replica_id=None)

    worker_id = build_worker_id(app_settings)

    assert re.fullmatch(rf".{{1,8}}-pid{os.getpid()}-[0-9a-f]{{4}}", worker_id)


async def test_lifespan_gives_background_job_service_a_worker_id() -> None:
    fastapi_app = create_app()

    async with fastapi_app.router.lifespan_context(fastapi_app):
        worker_id = fastapi_app.state.background_job_service.worker_id

    assert re.fullmatch(rf".{{1,8}}-pid{os.getpid()}-[0-9a-f]{{4}}", worker_id)


async def test_lifespan_shutdown_requests_stop_and_drains_running_jobs() -> None:
    fastapi_app = create_app()
    finished_labels: list[str] = []

    async def record_finished() -> None:
        finished_labels.append("finished")

    async with fastapi_app.router.lifespan_context(fastapi_app):
        background_job_service = fastapi_app.state.background_job_service
        is_stopping_while_running = background_job_service.is_stopping
        background_job_service.start(record_finished())

    assert is_stopping_while_running is False
    assert background_job_service.is_stopping is True
    assert finished_labels == ["finished"]
