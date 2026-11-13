from pydantic import BaseModel, ConfigDict

from libs.users.types import ClientIpSourceType


class UserSettings(BaseModel):
    model_config = ConfigDict(frozen=True)

    activity_interval_seconds: int = 60 * 5
    client_ip_source: ClientIpSourceType = ClientIpSourceType.CONNECTION
