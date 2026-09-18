from pydantic import BaseModel, ConfigDict


class UserSettings(BaseModel):
    model_config = ConfigDict(frozen=True)

    activity_interval_seconds: int = 60 * 5
