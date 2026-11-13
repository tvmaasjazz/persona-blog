from fastapi import APIRouter

from apps.api.core.dependencies import AppSettingsDep, ClientIpDep
from apps.api.domains.health.dtos import HealthResponseDto
from apps.api.domains.health.types import HealthStatusType

health_router = APIRouter(tags=["health"])


@health_router.get("/health")
async def get_health(app_settings: AppSettingsDep, client_ip: ClientIpDep) -> HealthResponseDto:
    """Reports that the API is up, with its app name, environment and the caller's IP as
    the API resolved it."""
    return HealthResponseDto(
        status=HealthStatusType.OK,
        app_name=app_settings.app_name,
        environment=app_settings.environment,
        client_ip=client_ip,
    )
