from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI
from httpx import AsyncClient
from openai import AsyncOpenAI
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import create_async_engine

from apps.api.core.logging import configure_logging
from libs.database.session import create_db_session_factory

logger = structlog.get_logger(__name__)


@asynccontextmanager
async def lifespan(fastapi_app: FastAPI) -> AsyncIterator[None]:
    app_settings = fastapi_app.state.settings
    configure_logging(app_settings)
    db_engine = create_async_engine(app_settings.database_url)
    redis_client = Redis.from_url(app_settings.redis_url)
    http_client = AsyncClient()
    # A blank OPENAI_API_KEY means no key, not a broken one: the LLM routes answer 503
    # rather than the app refusing to start.
    openai_client = (
        AsyncOpenAI(api_key=app_settings.openai_api_key, max_retries=app_settings.llm.max_retries)
        if app_settings.openai_api_key
        else None
    )
    fastapi_app.state.db_engine = db_engine
    fastapi_app.state.db_session_factory = create_db_session_factory(db_engine)
    fastapi_app.state.redis_client = redis_client
    fastapi_app.state.http_client = http_client
    fastapi_app.state.openai_client = openai_client

    logger.info(
        "api_started",
        app_name=app_settings.app_name,
        environment=app_settings.environment,
    )
    try:
        yield
    finally:
        await http_client.aclose()
        await redis_client.aclose()
        await db_engine.dispose()
        if openai_client is not None:
            await openai_client.close()
        logger.info("api_stopped", app_name=app_settings.app_name)
