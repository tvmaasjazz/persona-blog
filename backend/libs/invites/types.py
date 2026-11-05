from enum import StrEnum


class InviteStatusType(StrEnum):
    UNUSED = "UNUSED"
    USED = "USED"
    EXPIRED = "EXPIRED"
    REVOKED = "REVOKED"


class InviteSignInResultType(StrEnum):
    ACCEPTED = "ACCEPTED"
    INVITE_NOT_FOUND = "INVITE_NOT_FOUND"
    INVITE_USED = "INVITE_USED"
    INVITE_EXPIRED = "INVITE_EXPIRED"
    INVITE_REVOKED = "INVITE_REVOKED"
