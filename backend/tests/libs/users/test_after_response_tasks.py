from redis.asyncio import Redis
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from libs.database.orm import UserOrm
from libs.users.after_response_tasks import record_user_activity
from libs.users.settings import UserSettings
from tests.factories.database import fetch_database_utc_now
from tests.factories.users import insert_user_row


async def test_record_user_activity_writes_through_its_own_session(
    db_session: AsyncSession,
    db_session_factory: async_sessionmaker[AsyncSession],
    redis_client: Redis,
) -> None:
    user_record = await insert_user_row(db_session)
    await db_session.commit()
    user_settings = UserSettings()

    await record_user_activity(
        db_session_factory=db_session_factory,
        redis_client=redis_client,
        user_settings=user_settings,
        user_id=user_record.id,
    )

    database_utc_now = await fetch_database_utc_now(db_session)
    last_activity_at_query = select(UserOrm.last_activity_at).where(UserOrm.id == user_record.id)
    persisted_last_activity_at = await db_session.scalar(last_activity_at_query)
    throttle_key_ttl = await redis_client.ttl(f"user-activity:{user_record.id}")
    assert persisted_last_activity_at == database_utc_now
    assert 0 < throttle_key_ttl <= user_settings.activity_interval_seconds
