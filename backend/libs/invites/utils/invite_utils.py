import hashlib
import secrets
from datetime import datetime

from libs.invites.constants import (
    INVITE_CODE_BYTES,
    INVITE_SIGN_IN_RESULT_TYPE_BY_STATUS_TYPE,
)
from libs.invites.types import InviteSignInResultType, InviteStatusType


class InviteUtils:
    """Builds invite codes, hashes, links, statuses and sign-in redirects; static methods
    only."""

    @staticmethod
    def build_code() -> str:
        """Returns a new random URL-safe invite code."""
        return secrets.token_urlsafe(INVITE_CODE_BYTES)

    @staticmethod
    def hash_code(code: str) -> str:
        """Returns the SHA-256 hex digest of the code, the only form of it that is stored."""
        return hashlib.sha256(code.encode()).hexdigest()

    @staticmethod
    def build_invite_url(frontend_url: str, code: str) -> str:
        """Returns the link the admin sends for the code."""
        return f"{frontend_url}/invite/{code}"

    @staticmethod
    def build_status_type(
        revoked_at: datetime | None, used_at: datetime | None, is_expired: bool
    ) -> InviteStatusType:
        """Returns the invite's status; revoked wins over used, and used over expired."""
        if revoked_at is not None:
            return InviteStatusType.REVOKED
        if used_at is not None:
            return InviteStatusType.USED
        if is_expired:
            return InviteStatusType.EXPIRED
        return InviteStatusType.UNUSED

    @staticmethod
    def build_sign_in_result_type(status_type: InviteStatusType) -> InviteSignInResultType:
        """Returns the sign-in result for a status that stops a code; NotImplementedError for
        UNUSED, which stops nothing."""
        sign_in_result_type = INVITE_SIGN_IN_RESULT_TYPE_BY_STATUS_TYPE.get(status_type)
        if sign_in_result_type is None:
            raise NotImplementedError(f"No sign-in result registered for {status_type}")
        return sign_in_result_type

    @staticmethod
    def build_sign_in_redirect_url(
        frontend_url: str, invite_sign_in_result_type: InviteSignInResultType | None
    ) -> str:
        """Returns where sign-in sends the browser: the frontend root without an invite,
        otherwise its sign-in page with the invite's outcome."""
        if invite_sign_in_result_type is None:
            return frontend_url
        if invite_sign_in_result_type == InviteSignInResultType.ACCEPTED:
            return f"{frontend_url}/sign-in?invite={invite_sign_in_result_type}"
        return f"{frontend_url}/sign-in?invite_error={invite_sign_in_result_type}"
