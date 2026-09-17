from pydantic import BaseModel, ConfigDict


class AuthSettings(BaseModel):
    model_config = ConfigDict(frozen=True)

    session_ttl_seconds: int = 60 * 60 * 24 * 14
    oauth_state_ttl_seconds: int = 60 * 10
    frontend_url: str = "http://localhost:5173"
