from redis.asyncio import Redis
from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession

from libs.database.orm import UserAuthProviderOrm, UserOrm
from libs.database.utils import DatabaseClockUtils
from libs.users.constants import USER_ACTIVITY_KEY_PREFIX, USER_ACTIVITY_KEY_VALUE
from libs.users.settings import UserSettings


class UserActivityService:
    """Keeps `last_activity_at` roughly current without writing on every request."""

    def __init__(
        self, db_session: AsyncSession, redis_client: Redis, user_settings: UserSettings
    ) -> None:
        self._db_session = db_session
        self._redis_client = redis_client
        self._user_settings = user_settings

    async def record_sign_in(self, user_id: int, user_auth_provider_id: int) -> None:
        """Stamps the user's last login and the auth provider's last use."""
        sign_in_update = (
            update(UserOrm)
            .where(UserOrm.id == user_id)
            .values(last_login_at=DatabaseClockUtils.build_utc_now_sql())
        )
        auth_provider_update = (
            update(UserAuthProviderOrm)
            .where(UserAuthProviderOrm.id == user_auth_provider_id)
            .values(last_used_at=DatabaseClockUtils.build_utc_now_sql())
        )
        await self._db_session.execute(sign_in_update)
        await self._db_session.execute(auth_provider_update)

    async def record_activity(self, user_id: int) -> None:
        """Stamps the user's last activity, at most once per configured interval."""
        # The Redis key is the throttle: it sets only when absent, so one request per
        # interval writes to the database
        is_activity_due = await self._redis_client.set(
            f"{USER_ACTIVITY_KEY_PREFIX}{user_id}",
            USER_ACTIVITY_KEY_VALUE,
            nx=True,
            ex=self._user_settings.activity_interval_seconds,
        )
        if not is_activity_due:
            return

        activity_update = (
            update(UserOrm)
            .where(UserOrm.id == user_id)
            .values(last_activity_at=DatabaseClockUtils.build_utc_now_sql())
        )
        await self._db_session.execute(activity_update)
