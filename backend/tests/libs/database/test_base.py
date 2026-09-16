from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from libs.database.orm import UserOrm
from tests.factories.users import insert_user_row


async def test_base_insert_populates_server_defaults(db_session: AsyncSession) -> None:
    user_orm = await insert_user_row(db_session)

    assert isinstance(user_orm.id, int)
    assert isinstance(user_orm.identity, UUID)
    assert user_orm.created_at.tzinfo == UTC
    assert user_orm.updated_at.tzinfo == UTC


async def test_base_orm_update_sets_updated_at(db_session: AsyncSession) -> None:
    user_orm = await insert_user_row(db_session)
    await db_session.execute(
        text("UPDATE pb_user SET updated_at = '2020-01-01' WHERE id = :user_id"),
        {"user_id": user_orm.id},
    )

    user_orm.display_name = "Grace Hopper"
    await db_session.flush()

    updated_at_query = select(UserOrm.updated_at).where(UserOrm.id == user_orm.id)
    persisted_updated_at = await db_session.scalar(updated_at_query)
    assert persisted_updated_at is not None
    assert persisted_updated_at > datetime(2020, 1, 1, tzinfo=UTC)
