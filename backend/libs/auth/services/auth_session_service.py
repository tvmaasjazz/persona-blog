import secrets

from pydantic import ValidationError
from redis.asyncio import Redis

from libs.auth.constants import USER_SESSION_KEY_PREFIX, USER_SESSION_LIST_KEY_PREFIX
from libs.auth.results import AuthUser
from libs.auth.settings import AuthSettings
from libs.core.exceptions import UnauthorizedException


class AuthSessionService:
    """Stores signed-in sessions in Redis, keyed by an unguessable session id, with a set of
    each user's session ids so they can all be deleted at once."""

    def __init__(self, redis_client: Redis, auth_settings: AuthSettings) -> None:
        self._redis_client = redis_client
        self._auth_settings = auth_settings

    async def create_session(self, auth_user: AuthUser) -> str:
        """Writes the user to Redis as a session with the configured TTL, adds it to the
        user's set, and returns its new id."""
        session_id = secrets.token_urlsafe(32)
        session_ttl_seconds = self._auth_settings.session_ttl_seconds
        user_session_list_key = f"{USER_SESSION_LIST_KEY_PREFIX}{auth_user.id}"
        async with self._redis_client.pipeline(transaction=True) as redis_pipeline:
            redis_pipeline.set(
                f"{USER_SESSION_KEY_PREFIX}{session_id}",
                auth_user.model_dump_json(),
                ex=session_ttl_seconds,
            )
            # The set lives as long as the newest session; an id whose session already
            # expired is deleted harmlessly later
            redis_pipeline.sadd(user_session_list_key, session_id)
            redis_pipeline.expire(user_session_list_key, session_ttl_seconds)
            await redis_pipeline.execute()
        return session_id

    async def find_session(self, session_id: str) -> AuthUser:
        """The user the session belongs to; UnauthorizedException if it is missing, expired,
        or stored in a shape that no longer validates, such as before roles existed."""
        stored_session = await self._redis_client.get(f"{USER_SESSION_KEY_PREFIX}{session_id}")
        if stored_session is None:
            raise UnauthorizedException("Session is missing or expired")
        try:
            return AuthUser.model_validate_json(stored_session)
        except ValidationError as validation_error:
            raise UnauthorizedException("Session is missing or expired") from validation_error

    async def delete_session(self, session_id: str, user_id: int) -> None:
        """Removes the session and its place in the user's set; an unknown id is not an
        error."""
        async with self._redis_client.pipeline(transaction=True) as redis_pipeline:
            redis_pipeline.delete(f"{USER_SESSION_KEY_PREFIX}{session_id}")
            redis_pipeline.srem(f"{USER_SESSION_LIST_KEY_PREFIX}{user_id}", session_id)
            await redis_pipeline.execute()

    async def delete_user_sessions(self, user_id: int) -> None:
        """Signs the user out everywhere by deleting every session in their set, and the set;
        a user with none is not an error."""
        user_session_list_key = f"{USER_SESSION_LIST_KEY_PREFIX}{user_id}"
        session_ids = await self._redis_client.smembers(user_session_list_key)
        # The client returns bytes, so each id is decoded before it's built into a key
        session_keys = [
            f"{USER_SESSION_KEY_PREFIX}{session_id.decode()}" for session_id in session_ids
        ]
        await self._redis_client.delete(user_session_list_key, *session_keys)
