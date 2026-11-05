from uuid import UUID

from pydantic import BaseModel

from libs.permissions.types import PermissionType, RoleType


class OAuthStateResult(BaseModel):
    oauth_state: str
    nonce: str
    code_verifier: str
    invite_code: str | None


class AuthUser(BaseModel):
    """The signed-in user in request scope, read back from the session with the role and
    permissions held at sign-in."""

    id: int
    identity: UUID
    role: RoleType
    permissions: frozenset[PermissionType]
