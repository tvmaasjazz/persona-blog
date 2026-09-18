from types import SimpleNamespace

from redis.asyncio import Redis
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from apps.api.core.background_tasks import record_user_activity
from apps.api.core.config import AppSettings
from libs.database.orm import UserOrm
from tests.factories.users import insert_user_row


async def test_record_user_activity_writes_through_its_own_session(
    db_session: AsyncSession,
    db_session_factory: async_sessionmaker[AsyncSession],
    redis_client: Redis,
    app_settings: AppSettings,
) -> None:
    user_record = await insert_user_row(db_session)
    await db_session.commit()
    app_state = SimpleNamespace(
        settings=app_settings, db_session_factory=db_session_factory, redis_client=redis_client
    )

    await record_user_activity(app_state, user_record.id)

    last_activity_at_query = select(UserOrm.last_activity_at).where(UserOrm.id == user_record.id)
    persisted_last_activity_at = await db_session.scalar(last_activity_at_query)
    throttle_key_ttl = await redis_client.ttl(f"user-activity:{user_record.id}")
    assert persisted_last_activity_at is not None
    assert 0 < throttle_key_ttl <= app_settings.users.activity_interval_seconds
