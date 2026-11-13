from pydantic import BaseModel

from apps.api.core.types import EnvironmentType
from apps.api.domains.health.types import HealthStatusType


class HealthResponseDto(BaseModel):
    status: HealthStatusType
    app_name: str
    environment: EnvironmentType
    # The caller's own IP as the API resolved it, to check the proxies in front of it
    client_ip: str
