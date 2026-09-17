from uuid import UUID

from pydantic import BaseModel


class GoogleIdentityResult(BaseModel):
    provider_subject: str
    email: str
    is_email_verified: bool
    display_name: str | None
    avatar_url: str | None


class AuthUser(BaseModel):
    """The signed-in user in request scope, read back from the session."""

    id: int
    identity: UUID
