from pydantic import BaseModel

from apps.api.core.types import EnvironmentType
from apps.api.domains.health.types import DependencyStatusType, HealthStatusType


class HealthResponseDto(BaseModel):
    status: HealthStatusType
    app_name: str
    environment: EnvironmentType
    postgres: DependencyStatusType
    redis: DependencyStatusType
