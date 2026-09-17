from uuid import UUID

from pydantic import BaseModel


class OAuthStateResult(BaseModel):
    oauth_state: str
    nonce: str
    code_verifier: str


class AuthUser(BaseModel):
    """The signed-in user in request scope, read back from the session."""

    id: int
    identity: UUID
