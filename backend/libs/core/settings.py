from pydantic import BaseModel, ConfigDict


class BackgroundJobSettings(BaseModel):
    model_config = ConfigDict(frozen=True)

    # Keep above the slowest step (STRONG's 120s timeout) and under Railway's drainingSeconds
    shutdown_drain_seconds: int = 150
