from pydantic import BaseModel, ConfigDict


class AuthSettings(BaseModel):
    model_config = ConfigDict(frozen=True)

    session_ttl_seconds: int = 60 * 60 * 24 * 14
    oauth_state_ttl_seconds: int = 60 * 10
    google_redirect_url: str = "http://localhost:8000/auth/google/callback"
    frontend_url: str = "http://localhost:5173"
    google_request_timeout_seconds: int = 10
