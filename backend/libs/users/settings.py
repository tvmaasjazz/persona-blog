from pydantic import BaseModel, ConfigDict


class UserSettings(BaseModel):
    model_config = ConfigDict(frozen=True)

    activity_interval_seconds: int = 60 * 5
    # The header the hosting proxy sets to the client's IP; unset means the connection's own
    client_ip_header: str | None = None
