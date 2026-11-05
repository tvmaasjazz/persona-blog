from pydantic import BaseModel

from libs.invites.types import InviteSignInResultType


class GoogleIdentityResult(BaseModel):
    provider_subject: str
    email: str
    is_email_verified: bool
    display_name: str | None
    avatar_url: str | None
    invite_code: str | None


class GoogleSignInResult(BaseModel):
    session_id: str
    is_new_user: bool
    invite_sign_in_result_type: InviteSignInResultType | None
