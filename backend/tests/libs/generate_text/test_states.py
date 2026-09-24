from uuid import uuid4

from libs.auth.results import AuthUser
from tests.factories.generate_text import build_generate_text_state


def test_build_auth_user_returns_auth_user_with_stored_id_and_identity() -> None:
    auth_user_identity = uuid4()
    generate_text_state = build_generate_text_state(
        auth_user_id=7, auth_user_identity=auth_user_identity
    )

    auth_user = generate_text_state.build_auth_user()

    assert auth_user == AuthUser(id=7, identity=auth_user_identity)
