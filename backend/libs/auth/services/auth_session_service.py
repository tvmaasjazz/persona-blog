import secrets
from uuid import UUID

from redis.asyncio import Redis

from libs.auth.constants import SESSION_KEY_PREFIX
from libs.auth.results import AuthUser
from libs.auth.settings import AuthSettings
from libs.core.exceptions import UnauthorizedException


class AuthSessionService:
    """Stores signed-in sessions in Redis, keyed by an unguessable session id."""

    def __init__(self, redis_client: Redis, auth_settings: AuthSettings) -> None:
        self._redis_client = redis_client
        self._auth_settings = auth_settings

    async def create_session(self, user_id: int, user_identity: UUID) -> str:
        """Writes the session to Redis with the configured TTL and returns its new id."""
        session_id = secrets.token_urlsafe(32)
        auth_user = AuthUser(id=user_id, identity=user_identity)
        await self._redis_client.set(
            f"{SESSION_KEY_PREFIX}{session_id}",
            auth_user.model_dump_json(),
            ex=self._auth_settings.session_ttl_seconds,
        )
        return session_id

    async def find_session(self, session_id: str) -> AuthUser:
        """The user the session belongs to; UnauthorizedException if it is missing or expired."""
        stored_session = await self._redis_client.get(f"{SESSION_KEY_PREFIX}{session_id}")
        if stored_session is None:
            raise UnauthorizedException("Session is missing or expired")
        return AuthUser.model_validate_json(stored_session)

    async def delete_session(self, session_id: str) -> None:
        """Removes the session from Redis; an unknown id is not an error."""
        await self._redis_client.delete(f"{SESSION_KEY_PREFIX}{session_id}")
