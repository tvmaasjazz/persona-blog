from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from libs.database.orm import UserOrm
from tests.factories.database import fetch_database_utc_now
from tests.factories.users import insert_user_row


async def test_base_insert_populates_server_defaults(db_session: AsyncSession) -> None:
    user_record = await insert_user_row(db_session)

    assert isinstance(user_record.id, int)
    assert isinstance(user_record.identity, UUID)
    assert user_record.created_at.tzinfo == UTC
    assert user_record.updated_at.tzinfo == UTC


async def test_base_orm_update_sets_updated_at(db_session: AsyncSession) -> None:
    user_record = await insert_user_row(db_session)
    await db_session.execute(
        text("UPDATE pb_user SET updated_at = '2020-01-01' WHERE id = :user_id"),
        {"user_id": user_record.id},
    )

    user_record.display_name = "Grace Hopper"
    await db_session.flush()

    updated_at_query = select(UserOrm.updated_at).where(UserOrm.id == user_record.id)
    persisted_updated_at = await db_session.scalar(updated_at_query)
    assert persisted_updated_at is not None
    assert persisted_updated_at > datetime(2020, 1, 1, tzinfo=UTC)


async def test_base_orm_update_makes_updated_at_readable_after_flush(
    db_session: AsyncSession,
) -> None:
    user_record = await insert_user_row(db_session)
    await db_session.execute(
        text("UPDATE pb_user SET updated_at = '2020-01-01' WHERE id = :user_id"),
        {"user_id": user_record.id},
    )
    await db_session.refresh(user_record)

    user_record.display_name = "Grace Hopper"
    await db_session.flush()

    database_utc_now = await fetch_database_utc_now(db_session)
    assert user_record.updated_at == database_utc_now
