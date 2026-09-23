from uuid import UUID, uuid4

from libs.auth.results import AuthUser


def build_auth_user(*, user_id: int = 1, user_identity: UUID | None = None) -> AuthUser:
    return AuthUser(id=user_id, identity=user_identity or uuid4())
