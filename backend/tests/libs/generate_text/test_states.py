from uuid import uuid4

from libs.auth.results import AuthUser
from libs.permissions.types import PermissionType, RoleType
from tests.factories.generate_text import build_generate_text_state


def test_build_auth_user_returns_role_and_permissions_as_enums() -> None:
    auth_user_identity = uuid4()
    generate_text_state = build_generate_text_state(
        auth_user_id=7,
        auth_user_identity=auth_user_identity,
        auth_user_role="READER",
        auth_user_permissions=["BLOG_POST_WRITE", "PERSONA_WRITE"],
    )

    auth_user = generate_text_state.build_auth_user()

    assert auth_user == AuthUser(
        id=7,
        identity=auth_user_identity,
        role=RoleType.READER,
        permissions=frozenset({PermissionType.BLOG_POST_WRITE, PermissionType.PERSONA_WRITE}),
    )
    assert type(auth_user.role) is RoleType
