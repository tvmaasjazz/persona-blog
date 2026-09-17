from fastapi import FastAPI

from apps.api.core.exception_handlers import register_exception_handlers
from apps.api.domains.auth.router import auth_router
from apps.api.domains.health.router import health_router
from apps.api.domains.users.router import user_router
from apps.api.lifespan import lifespan


def create_app() -> FastAPI:
    fastapi_app = FastAPI(lifespan=lifespan)
    register_exception_handlers(fastapi_app)

    fastapi_app.include_router(health_router)
    fastapi_app.include_router(auth_router)
    fastapi_app.include_router(user_router)

    return fastapi_app
