import asyncio
import os
import secrets
import socket
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI
from httpx import AsyncClient
from langgraph.checkpoint.redis.aio import AsyncRedisSaver
from openai import AsyncOpenAI
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import create_async_engine

from apps.api.core.config import AppSettings
from apps.api.core.event_loop_monitor import monitor_event_loop_lag
from apps.api.core.logging import configure_logging
from apps.api.core.types import EnvironmentType
from apps.api.domains.generate_text.dependencies import build_generate_text_run_pickup_service
from libs.core.services import BackgroundJobService
from libs.database.session import create_db_session_factory

logger = structlog.get_logger(__name__)

WORKER_ID_SUFFIX_BYTES = 2
WORKER_ID_REPLICA_LENGTH = 8


def build_worker_id(app_settings: AppSettings) -> str:
    """Names this process by where it runs, its PID and a random suffix."""
    # The suffix keeps a restarted process that reuses a PID from matching the lease its
    # predecessor held
    host_name = app_settings.railway_replica_id or socket.gethostname()
    random_suffix = secrets.token_hex(WORKER_ID_SUFFIX_BYTES)
    return f"{host_name[:WORKER_ID_REPLICA_LENGTH]}-pid{os.getpid()}-{random_suffix}"


@asynccontextmanager
async def lifespan(fastapi_app: FastAPI) -> AsyncIterator[None]:
    app_settings = fastapi_app.state.settings
    configure_logging(app_settings)
    db_engine = create_async_engine(app_settings.database_url)
    redis_client = Redis.from_url(app_settings.redis_url)
    http_client = AsyncClient()
    openai_client = AsyncOpenAI(api_key=app_settings.openai_api_key, max_retries=0)
    background_job_service = BackgroundJobService(worker_id=build_worker_id(app_settings))
    fastapi_app.state.background_job_service = background_job_service
    fastapi_app.state.db_engine = db_engine
    fastapi_app.state.db_session_factory = create_db_session_factory(db_engine)
    fastapi_app.state.redis_client = redis_client
    fastapi_app.state.http_client = http_client
    fastapi_app.state.openai_client = openai_client

    # LangGraph's Redis checkpointer indexes its threads with RediSearch, which only
    # works on database 0. The suite runs on database 15 and puts an InMemorySaver on
    # app.state instead, so graph routes still run there. A production deployment
    # pointed anywhere but database 0 is a misconfiguration: it would start, then answer
    # 503 on every generate route, so it fails here instead.
    redis_database_index = redis_client.connection_pool.connection_kwargs.get("db")
    fastapi_app.state.graph_checkpointer = None
    if redis_database_index != 0 and app_settings.environment is EnvironmentType.PRODUCTION:
        raise RuntimeError(
            f"REDIS_URL must use database 0 for graph checkpointing, not {redis_database_index}"
        )
    if redis_database_index == 0:
        graph_checkpointer = AsyncRedisSaver(
            redis_client=redis_client,
            ttl={
                "default_ttl": app_settings.generate_text.checkpoint_ttl_minutes,
                "refresh_on_read": True,
            },
        )
        await graph_checkpointer.asetup()
        fastapi_app.state.graph_checkpointer = graph_checkpointer
    else:
        logger.warning("graph_checkpointer_unavailable", redis_database_index=redis_database_index)

    logger.info(
        "api_started",
        app_name=app_settings.app_name,
        environment=app_settings.environment,
    )
    event_loop_monitor_task = None
    if app_settings.environment is EnvironmentType.DEVELOPMENT:
        event_loop_monitor_task = asyncio.create_task(monitor_event_loop_lag())
    generate_text_run_pickup_task = None
    if (
        app_settings.environment is not EnvironmentType.TEST
        and fastapi_app.state.graph_checkpointer is not None
    ):
        generate_text_run_pickup_service = build_generate_text_run_pickup_service(fastapi_app.state)
        generate_text_run_pickup_task = asyncio.create_task(
            generate_text_run_pickup_service.pick_up_expired_runs()
        )
    try:
        yield
    finally:
        # First, so a stopping process never claims a new run.
        if generate_text_run_pickup_task is not None:
            generate_text_run_pickup_task.cancel()
            await asyncio.gather(generate_text_run_pickup_task, return_exceptions=True)
        # Before the clients close: a running graph still needs them.
        background_job_service.request_stop()
        await background_job_service.drain(app_settings.background_jobs.shutdown_drain_seconds)
        if event_loop_monitor_task is not None:
            event_loop_monitor_task.cancel()
            await asyncio.gather(event_loop_monitor_task, return_exceptions=True)
        await http_client.aclose()
        await redis_client.aclose()
        await db_engine.dispose()
        await openai_client.close()
        logger.info("api_stopped", app_name=app_settings.app_name)
