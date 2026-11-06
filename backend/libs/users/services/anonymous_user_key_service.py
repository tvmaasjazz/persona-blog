import hmac
import secrets
from datetime import UTC, datetime, time, timedelta
from hashlib import sha256

from redis.asyncio import Redis

from libs.users.constants import ANONYMOUS_USER_KEY_SALT_KEY_PREFIX

SALT_BYTE_COUNT = 32


class AnonymousUserKeyService:
    """Identifies a signed-out visitor for one UTC day without storing their IP."""

    def __init__(self, redis_client: Redis) -> None:
        self._redis_client = redis_client

    async def build_anonymous_user_key(self, client_ip: str, user_agent: str) -> str:
        """An HMAC-SHA256 hex of the IP and user agent, keyed by today's random salt."""
        salt = await self._find_or_create_daily_salt()
        # The newline can't appear in an IP, so two different pairs never join to the same text
        visitor_text = f"{client_ip}\n{user_agent}"
        return hmac.new(salt.encode(), visitor_text.encode(), sha256).hexdigest()

    async def _find_or_create_daily_salt(self) -> str:
        now = datetime.now(UTC)
        today = now.date()
        next_midnight = datetime.combine(today + timedelta(days=1), time.min, tzinfo=UTC)
        new_salt = secrets.token_hex(SALT_BYTE_COUNT)

        # The salt lives only in Redis and expires at the next UTC midnight. Once it is gone a
        # stored key can't be traced back to an IP, which is the privacy design.
        # SET NX GET returns the existing salt, or nil when ours was just set
        existing_salt = await self._redis_client.set(
            f"{ANONYMOUS_USER_KEY_SALT_KEY_PREFIX}{today.isoformat()}",
            new_salt,
            nx=True,
            exat=int(next_midnight.timestamp()),
            get=True,
        )
        if existing_salt is None:
            return new_salt
        if isinstance(existing_salt, bytes):
            return existing_salt.decode()
        return existing_salt
