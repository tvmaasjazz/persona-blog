from pydantic import BaseModel

from apps.api.domains.health.health_status_type import HealthStatusType


class HealthResponseDto(BaseModel):
    status: HealthStatusType
    app_name: str
    environment: str
