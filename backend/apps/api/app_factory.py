from fastapi import FastAPI

from apps.api.core.config import AppSettings
from apps.api.core.exception_handlers import register_exception_handlers
from apps.api.core.types import EnvironmentType
from apps.api.domains.auth.router import auth_router
from apps.api.domains.blog_posts.router import blog_post_router
from apps.api.domains.dev_llm.router import dev_llm_router
from apps.api.domains.generate_text.router import generate_text_router
from apps.api.domains.google_auth.router import google_auth_router
from apps.api.domains.health.router import health_router
from apps.api.domains.personas.router import persona_router
from apps.api.domains.users.router import user_router
from apps.api.lifespan import lifespan


def create_app() -> FastAPI:
    app_settings = AppSettings()
    fastapi_app = FastAPI(lifespan=lifespan)
    fastapi_app.state.settings = app_settings
    register_exception_handlers(fastapi_app)

    fastapi_app.include_router(health_router)
    fastapi_app.include_router(auth_router)
    fastapi_app.include_router(google_auth_router)
    fastapi_app.include_router(user_router)
    fastapi_app.include_router(persona_router)
    fastapi_app.include_router(blog_post_router)
    fastapi_app.include_router(generate_text_router)
    if app_settings.environment is EnvironmentType.DEVELOPMENT:
        fastapi_app.include_router(dev_llm_router)

    return fastapi_app
