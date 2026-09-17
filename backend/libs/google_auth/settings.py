from pydantic import BaseModel, ConfigDict


class GoogleAuthSettings(BaseModel):
    model_config = ConfigDict(frozen=True)

    redirect_url: str = "http://localhost:8000/auth/google/callback"
    request_timeout_seconds: int = 10
