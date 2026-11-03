from uuid import UUID, uuid4

from libs.auth.results import AuthUser
from libs.permissions.types import PermissionType, RoleType

ALL_PERMISSIONS = frozenset(
    {
        PermissionType.PERSONA_READ,
        PermissionType.PERSONA_WRITE,
        PermissionType.BLOG_POST_READ,
        PermissionType.BLOG_POST_WRITE,
        PermissionType.GENERATE_TEXT_RUN_READ,
        PermissionType.GENERATE_TEXT_RUN_WRITE,
    }
)
PERMISSIONS_BY_ROLE = {
    RoleType.ADMIN: ALL_PERMISSIONS,
    RoleType.CREATOR: ALL_PERMISSIONS,
    RoleType.READER: frozenset({PermissionType.PERSONA_READ, PermissionType.BLOG_POST_READ}),
    RoleType.SYSTEM: frozenset[PermissionType](),
}


def build_auth_user(
    *,
    user_id: int = 1,
    user_identity: UUID | None = None,
    role: RoleType = RoleType.CREATOR,
    permissions: frozenset[PermissionType] | None = None,
) -> AuthUser:
    return AuthUser(
        id=user_id,
        identity=user_identity or uuid4(),
        role=role,
        permissions=PERMISSIONS_BY_ROLE[role] if permissions is None else permissions,
    )
