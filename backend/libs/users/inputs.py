from pydantic import BaseModel

from libs.auth.types import AuthProviderType


class FindOrCreateUserFromAuthProviderInput(BaseModel):
    provider: AuthProviderType
    provider_subject: str
    email: str
    is_email_verified: bool
    display_name: str | None
    avatar_url: str | None
