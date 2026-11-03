from uuid import UUID

from pydantic import BaseModel

from libs.permissions.types import RoleType


class FindOrCreateUserFromAuthProviderResult(BaseModel):
    id: int
    identity: UUID
    role: RoleType
    user_auth_provider_id: int
    is_new_user: bool


class FindUserByIdentityResult(BaseModel):
    id: int
    identity: UUID
    email: str
    is_email_verified: bool
    display_name: str | None
    avatar_url: str | None
    is_active: bool
