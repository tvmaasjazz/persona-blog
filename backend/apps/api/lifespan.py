from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI

from apps.api.core.config import AppSettings
from apps.api.core.logging import configure_logging

logger = structlog.get_logger(__name__)


@asynccontextmanager
async def lifespan(fastapi_app: FastAPI) -> AsyncIterator[None]:
    app_settings = AppSettings()
    configure_logging(app_settings)
    fastapi_app.state.settings = app_settings

    logger.info(
        "api_started",
        app_name=app_settings.app_name,
        environment=app_settings.environment,
    )
    yield
    logger.info("api_stopped", app_name=app_settings.app_name)
