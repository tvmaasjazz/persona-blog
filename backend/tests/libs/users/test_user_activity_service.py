from datetime import UTC, datetime

from redis.asyncio import Redis
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from libs.database.orm import UserOrm
from libs.users.services import UserActivityService
from libs.users.settings import UserSettings
from tests.factories.users import insert_user_row


async def test_record_activity_no_throttle_key_sets_last_activity_at_and_stores_key(
    db_session: AsyncSession, redis_client: Redis
) -> None:
    user_record = await insert_user_row(db_session)
    user_settings = UserSettings(activity_interval_seconds=120)
    user_activity_service = UserActivityService(
        db_session=db_session, redis_client=redis_client, user_settings=user_settings
    )
    activity_at = datetime(2026, 5, 6, 7, 8, 9, tzinfo=UTC)

    await user_activity_service.record_activity(user_record.id, activity_at)

    user_query = select(UserOrm).where(UserOrm.id == user_record.id)
    updated_user_record = await db_session.scalar(user_query)
    throttle_key = f"user-activity:{user_record.id}"
    throttle_key_ttl = await redis_client.ttl(throttle_key)
    assert updated_user_record is not None
    assert updated_user_record.last_activity_at == activity_at
    assert 0 < throttle_key_ttl <= 120


async def test_record_activity_within_interval_leaves_last_activity_at_unchanged(
    db_session: AsyncSession, redis_client: Redis
) -> None:
    user_record = await insert_user_row(db_session)
    user_settings = UserSettings(activity_interval_seconds=120)
    user_activity_service = UserActivityService(
        db_session=db_session, redis_client=redis_client, user_settings=user_settings
    )
    first_activity_at = datetime(2026, 5, 6, 7, 8, 9, tzinfo=UTC)
    second_activity_at = datetime(2026, 5, 6, 7, 9, 0, tzinfo=UTC)
    await user_activity_service.record_activity(user_record.id, first_activity_at)

    await user_activity_service.record_activity(user_record.id, second_activity_at)

    user_query = select(UserOrm).where(UserOrm.id == user_record.id)
    updated_user_record = await db_session.scalar(user_query)
    assert updated_user_record is not None
    assert updated_user_record.last_activity_at == first_activity_at


async def test_record_activity_after_throttle_key_expires_writes_again(
    db_session: AsyncSession, redis_client: Redis
) -> None:
    user_record = await insert_user_row(db_session)
    user_settings = UserSettings(activity_interval_seconds=120)
    user_activity_service = UserActivityService(
        db_session=db_session, redis_client=redis_client, user_settings=user_settings
    )
    first_activity_at = datetime(2026, 5, 6, 7, 8, 9, tzinfo=UTC)
    second_activity_at = datetime(2026, 5, 6, 7, 9, 0, tzinfo=UTC)
    await user_activity_service.record_activity(user_record.id, first_activity_at)
    await redis_client.delete(f"user-activity:{user_record.id}")

    await user_activity_service.record_activity(user_record.id, second_activity_at)

    user_query = select(UserOrm).where(UserOrm.id == user_record.id)
    updated_user_record = await db_session.scalar(user_query)
    assert updated_user_record is not None
    assert updated_user_record.last_activity_at == second_activity_at


async def test_record_activity_unknown_user_id_writes_nothing(
    db_session: AsyncSession, redis_client: Redis
) -> None:
    user_settings = UserSettings(activity_interval_seconds=120)
    user_activity_service = UserActivityService(
        db_session=db_session, redis_client=redis_client, user_settings=user_settings
    )
    activity_at = datetime(2026, 5, 6, 7, 8, 9, tzinfo=UTC)

    await user_activity_service.record_activity(999_999_999, activity_at)
