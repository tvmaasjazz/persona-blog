import secrets

from redis.asyncio import Redis

from libs.auth.constants import OAUTH_STATE_KEY_PREFIX
from libs.auth.results import OAuthStateResult
from libs.auth.settings import AuthSettings
from libs.core.exceptions import UnauthorizedException


class OAuthStateService:
    """The short-lived record tying one sign-in attempt to its redirect back."""

    def __init__(self, redis_client: Redis, auth_settings: AuthSettings) -> None:
        self._redis_client = redis_client
        self._auth_settings = auth_settings

    async def create_state(self) -> OAuthStateResult:
        """Stores a fresh state, nonce and PKCE code verifier in Redis and returns them."""
        oauth_state_result = OAuthStateResult(
            oauth_state=secrets.token_urlsafe(32),
            nonce=secrets.token_urlsafe(32),
            code_verifier=secrets.token_urlsafe(64),
        )
        await self._redis_client.set(
            f"{OAUTH_STATE_KEY_PREFIX}{oauth_state_result.oauth_state}",
            oauth_state_result.model_dump_json(),
            ex=self._auth_settings.oauth_state_ttl_seconds,
        )
        return oauth_state_result

    async def consume_state(self, oauth_state: str) -> OAuthStateResult:
        """Reads the state and deletes it, so one sign-in attempt can't be replayed."""
        stored_state = await self._redis_client.getdel(f"{OAUTH_STATE_KEY_PREFIX}{oauth_state}")
        if stored_state is None:
            raise UnauthorizedException("Sign-in state is missing or expired")
        return OAuthStateResult.model_validate_json(stored_state)
