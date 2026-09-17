from pydantic import BaseModel


class GoogleIdentityResult(BaseModel):
    provider_subject: str
    email: str
    is_email_verified: bool
    display_name: str | None
    avatar_url: str | None


class GoogleSignInResult(BaseModel):
    session_id: str
    is_new_user: bool
