from enum import StrEnum


class RoleType(StrEnum):
    """A user's role; each role grants a fixed set of permissions."""

    ADMIN = "ADMIN"
    CREATOR = "CREATOR"
    READER = "READER"
    SYSTEM = "SYSTEM"


class PermissionType(StrEnum):
    """An action a role may be allowed to take."""

    PERSONA_READ = "PERSONA_READ"
    PERSONA_WRITE = "PERSONA_WRITE"
    BLOG_POST_READ = "BLOG_POST_READ"
    BLOG_POST_WRITE = "BLOG_POST_WRITE"
    GENERATE_TEXT_RUN_READ = "GENERATE_TEXT_RUN_READ"
    GENERATE_TEXT_RUN_WRITE = "GENERATE_TEXT_RUN_WRITE"
    USER_READ = "USER_READ"
    CREDIT_READ = "CREDIT_READ"
    CREDIT_WRITE = "CREDIT_WRITE"
    USER_WRITE = "USER_WRITE"
