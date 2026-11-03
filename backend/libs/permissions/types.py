from enum import StrEnum


class RoleType(StrEnum):
    """A user's role; each role grants a fixed set of permissions."""

    ADMIN = "ADMIN"
    CREATOR = "CREATOR"
    READER = "READER"
    SYSTEM = "SYSTEM"


class PermissionType(StrEnum):
    """An action a role may be allowed to take."""

    PERSONA_WRITE = "PERSONA_WRITE"
    BLOG_POST_WRITE = "BLOG_POST_WRITE"
    GENERATE_TEXT_RUN_WRITE = "GENERATE_TEXT_RUN_WRITE"
