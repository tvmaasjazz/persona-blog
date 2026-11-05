from redis.asyncio import Redis

from libs.auth.services import AuthSessionService
from libs.auth.settings import AuthSettings


async def delete_user_sessions(
    redis_client: Redis, auth_settings: AuthSettings, user_id: int
) -> None:
    """Signs the user out everywhere, after the change that called for it has committed."""
    auth_session_service = AuthSessionService(
        redis_client=redis_client, auth_settings=auth_settings
    )
    await auth_session_service.delete_user_sessions(user_id)
