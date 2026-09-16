from fastapi import FastAPI
from httpx import AsyncClient

from apps.api.core.config import AppSettings
from apps.api.core.types import EnvironmentType


async def test_get_health_returns_status_and_settings(
    fastapi_app: FastAPI, api_client: AsyncClient
) -> None:
    fastapi_app.state.settings = AppSettings(
        app_name="Health Test API",
        environment=EnvironmentType.TEST,
        database_url=fastapi_app.state.settings.database_url,
        redis_url=fastapi_app.state.settings.redis_url,
    )

    get_health_response = await api_client.get("/health")

    assert get_health_response.status_code == 200
    assert get_health_response.json() == {
        "status": "OK",
        "app_name": "Health Test API",
        "environment": "TEST",
    }
