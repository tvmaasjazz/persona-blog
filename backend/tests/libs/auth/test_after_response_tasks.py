from redis.asyncio import Redis

from libs.auth.after_response_tasks import delete_user_sessions
from libs.auth.services import AuthSessionService
from libs.auth.settings import AuthSettings
from tests.factories.auth import build_auth_user


async def test_delete_user_sessions_signs_the_user_out_everywhere(redis_client: Redis) -> None:
    auth_settings = AuthSettings()
    auth_session_service = AuthSessionService(
        redis_client=redis_client, auth_settings=auth_settings
    )
    auth_user = build_auth_user(user_id=42)
    first_session_id = await auth_session_service.create_session(auth_user)
    second_session_id = await auth_session_service.create_session(auth_user)
    other_session_id = await auth_session_service.create_session(build_auth_user(user_id=43))

    await delete_user_sessions(redis_client=redis_client, auth_settings=auth_settings, user_id=42)

    signed_out_key_count = await redis_client.exists(
        f"session:{first_session_id}", f"session:{second_session_id}", "user-sessions:42"
    )
    other_session_exists = await redis_client.exists(f"session:{other_session_id}")
    assert signed_out_key_count == 0
    assert other_session_exists == 1
