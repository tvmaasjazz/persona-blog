from pydantic import BaseModel, ConfigDict


class BackgroundJobSettings(BaseModel):
    model_config = ConfigDict(frozen=True)

    # How long shutdown waits for running jobs before cancelling them. Keep it above the
    # slowest single step (STRONG's 120s timeout) and under the platform's own kill
    # timeout (Railway's drainingSeconds).
    shutdown_drain_seconds: int = 150
