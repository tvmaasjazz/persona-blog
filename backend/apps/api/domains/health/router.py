from fastapi import APIRouter

from apps.api.core.dependencies import AppSettingsDep
from apps.api.domains.health.dtos import HealthResponseDto
from apps.api.domains.health.types import HealthStatusType

health_router = APIRouter(tags=["health"])


@health_router.get("/health")
async def get_health(app_settings: AppSettingsDep) -> HealthResponseDto:
    """Reports that the API is up, with its app name and environment."""
    return HealthResponseDto(
        status=HealthStatusType.OK,
        app_name=app_settings.app_name,
        environment=app_settings.environment,
    )
