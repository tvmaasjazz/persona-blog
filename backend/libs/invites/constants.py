from libs.invites.types import InviteSignInResultType, InviteStatusType

# 16 random bytes is 128 bits, so a code can't be guessed
INVITE_CODE_BYTES = 16

DEFAULT_INVITE_EXPIRES_IN_DAYS = 7
MAX_INVITE_EXPIRES_IN_DAYS = 30

SECONDS_PER_DAY = 86400

# The sign-in result each status that stops a code shows the user; UNUSED stops nothing
INVITE_SIGN_IN_RESULT_TYPE_BY_STATUS_TYPE: dict[InviteStatusType, InviteSignInResultType] = {
    InviteStatusType.USED: InviteSignInResultType.INVITE_USED,
    InviteStatusType.EXPIRED: InviteSignInResultType.INVITE_EXPIRED,
    InviteStatusType.REVOKED: InviteSignInResultType.INVITE_REVOKED,
}
