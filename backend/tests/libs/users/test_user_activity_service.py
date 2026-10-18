from datetime import UTC, datetime

from redis.asyncio import Redis
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from libs.database.orm import UserAuthProviderOrm, UserOrm
from libs.users.services import UserActivityService
from libs.users.settings import UserSettings
from tests.factories.database import fetch_database_utc_now
from tests.factories.users import insert_user_auth_provider_row, insert_user_row


async def test_record_sign_in_sets_last_login_at_and_last_used_at(
    db_session: AsyncSession, redis_client: Redis
) -> None:
    user_record = await insert_user_row(db_session)
    user_auth_provider_record = await insert_user_auth_provider_row(
        db_session, user_id=user_record.id
    )
    user_settings = UserSettings(activity_interval_seconds=120)
    user_activity_service = UserActivityService(
        db_session=db_session, redis_client=redis_client, user_settings=user_settings
    )

    await user_activity_service.record_sign_in(user_record.id, user_auth_provider_record.id)

    database_utc_now = await fetch_database_utc_now(db_session)
    user_query = select(UserOrm.last_login_at).where(UserOrm.id == user_record.id)
    user_auth_provider_query = select(UserAuthProviderOrm.last_used_at).where(
        UserAuthProviderOrm.id == user_auth_provider_record.id
    )
    persisted_last_login_at = await db_session.scalar(user_query)
    persisted_last_used_at = await db_session.scalar(user_auth_provider_query)
    assert persisted_last_login_at == database_utc_now
    assert persisted_last_used_at == database_utc_now


async def test_record_sign_in_earlier_sign_in_moves_both_timestamps_to_now(
    db_session: AsyncSession, redis_client: Redis
) -> None:
    earlier_signed_in_at = datetime(2026, 3, 4, 5, 6, 7, tzinfo=UTC)
    user_record = await insert_user_row(db_session, last_login_at=earlier_signed_in_at)
    user_auth_provider_record = await insert_user_auth_provider_row(
        db_session, user_id=user_record.id, last_used_at=earlier_signed_in_at
    )
    user_settings = UserSettings(activity_interval_seconds=120)
    user_activity_service = UserActivityService(
        db_session=db_session, redis_client=redis_client, user_settings=user_settings
    )

    await user_activity_service.record_sign_in(user_record.id, user_auth_provider_record.id)

    database_utc_now = await fetch_database_utc_now(db_session)
    user_query = select(UserOrm.last_login_at).where(UserOrm.id == user_record.id)
    user_auth_provider_query = select(UserAuthProviderOrm.last_used_at).where(
        UserAuthProviderOrm.id == user_auth_provider_record.id
    )
    persisted_last_login_at = await db_session.scalar(user_query)
    persisted_last_used_at = await db_session.scalar(user_auth_provider_query)
    assert persisted_last_login_at == database_utc_now
    assert persisted_last_used_at == database_utc_now


async def test_record_activity_no_throttle_key_sets_last_activity_at_and_stores_key(
    db_session: AsyncSession, redis_client: Redis
) -> None:
    user_record = await insert_user_row(db_session)
    user_settings = UserSettings(activity_interval_seconds=120)
    user_activity_service = UserActivityService(
        db_session=db_session, redis_client=redis_client, user_settings=user_settings
    )

    await user_activity_service.record_activity(user_record.id)

    user_query = select(UserOrm).where(UserOrm.id == user_record.id)
    updated_user_record = await db_session.scalar(user_query)
    database_utc_now = await fetch_database_utc_now(db_session)
    throttle_key = f"user-activity:{user_record.id}"
    throttle_key_ttl = await redis_client.ttl(throttle_key)
    throttle_key_value = await redis_client.get(throttle_key)
    assert updated_user_record is not None
    assert updated_user_record.last_activity_at == database_utc_now
    assert throttle_key_value == b"1"
    assert 0 < throttle_key_ttl <= 120


async def test_record_activity_within_interval_leaves_last_activity_at_unchanged(
    db_session: AsyncSession, redis_client: Redis
) -> None:
    first_activity_at = datetime(2026, 5, 6, 7, 8, 9, tzinfo=UTC)
    user_record = await insert_user_row(db_session, last_activity_at=first_activity_at)
    user_settings = UserSettings(activity_interval_seconds=120)
    user_activity_service = UserActivityService(
        db_session=db_session, redis_client=redis_client, user_settings=user_settings
    )
    await redis_client.set(f"user-activity:{user_record.id}", "1")

    await user_activity_service.record_activity(user_record.id)

    user_query = select(UserOrm.last_activity_at).where(UserOrm.id == user_record.id)
    persisted_last_activity_at = await db_session.scalar(user_query)
    assert persisted_last_activity_at == first_activity_at


async def test_record_activity_after_throttle_key_expires_writes_again(
    db_session: AsyncSession, redis_client: Redis
) -> None:
    first_activity_at = datetime(2026, 5, 6, 7, 8, 9, tzinfo=UTC)
    user_record = await insert_user_row(db_session, last_activity_at=first_activity_at)
    user_settings = UserSettings(activity_interval_seconds=120)
    user_activity_service = UserActivityService(
        db_session=db_session, redis_client=redis_client, user_settings=user_settings
    )
    await redis_client.set(f"user-activity:{user_record.id}", "1")
    await redis_client.delete(f"user-activity:{user_record.id}")

    await user_activity_service.record_activity(user_record.id)

    database_utc_now = await fetch_database_utc_now(db_session)
    user_query = select(UserOrm.last_activity_at).where(UserOrm.id == user_record.id)
    persisted_last_activity_at = await db_session.scalar(user_query)
    assert persisted_last_activity_at == database_utc_now


async def test_record_activity_unknown_user_id_writes_nothing(
    db_session: AsyncSession, redis_client: Redis
) -> None:
    user_settings = UserSettings(activity_interval_seconds=120)
    user_activity_service = UserActivityService(
        db_session=db_session, redis_client=redis_client, user_settings=user_settings
    )

    await user_activity_service.record_activity(999_999_999)
