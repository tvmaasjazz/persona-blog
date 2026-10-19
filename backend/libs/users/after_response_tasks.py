from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from libs.users.services import UserActivityService
from libs.users.settings import UserSettings


async def record_user_activity(
    db_session_factory: async_sessionmaker[AsyncSession],
    redis_client: Redis,
    user_settings: UserSettings,
    user_id: int,
) -> None:
    """Records a user's activity in a session of its own."""
    # The request's session is closed by the time this runs
    async with db_session_factory() as db_session, db_session.begin():
        user_activity_service = UserActivityService(
            db_session=db_session, redis_client=redis_client, user_settings=user_settings
        )
        await user_activity_service.record_activity(user_id)
