from fastapi import FastAPI

from apps.api.core.exception_handlers import register_exception_handlers
from apps.api.domains.health.router import health_router
from apps.api.lifespan import lifespan


def create_app() -> FastAPI:
    fastapi_app = FastAPI(lifespan=lifespan)
    register_exception_handlers(fastapi_app)

    fastapi_app.include_router(health_router)

    return fastapi_app
