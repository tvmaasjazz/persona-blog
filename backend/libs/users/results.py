from uuid import UUID

from pydantic import BaseModel, ConfigDict


class FindOrCreateUserFromAuthProviderResult(BaseModel):
    id: int
    identity: UUID
    is_new_user: bool


class FindUserByIdentityResult(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    identity: UUID
    email: str
    is_email_verified: bool
    display_name: str | None
    avatar_url: str | None
    is_active: bool
