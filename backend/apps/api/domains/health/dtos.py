from pydantic import BaseModel

from apps.api.domains.health.types import HealthStatusType


class HealthResponseDto(BaseModel):
    status: HealthStatusType
    app_name: str
    environment: str
