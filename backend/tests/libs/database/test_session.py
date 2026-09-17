from datetime import UTC, datetime

from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from libs.database.orm import UserOrm
from tests.factories.users import insert_user_row


async def test_orm_select_excludes_soft_deleted_rows(db_session: AsyncSession) -> None:
    live_user_orm = await insert_user_row(db_session)
    deleted_user_orm = await insert_user_row(
        db_session, deleted_at=datetime(2026, 1, 2, 3, 4, 5, tzinfo=UTC)
    )
    user_ids = [live_user_orm.id, deleted_user_orm.id]

    user_id_query = select(UserOrm.id).where(UserOrm.id.in_(user_ids))
    visible_user_ids = (await db_session.scalars(user_id_query)).all()
    stored_row_count = await db_session.scalar(
        text("SELECT count(*) FROM pb_user WHERE id = ANY(:user_ids)"),
        {"user_ids": user_ids},
    )

    assert visible_user_ids == [live_user_orm.id]
    assert stored_row_count == 2


async def test_orm_aggregate_excludes_soft_deleted_rows(db_session: AsyncSession) -> None:
    await insert_user_row(db_session, email="live@example.com")
    await insert_user_row(
        db_session,
        email="deleted@example.com",
        deleted_at=datetime(2026, 1, 2, 3, 4, 5, tzinfo=UTC),
    )

    user_count_query = select(func.count(UserOrm.id)).where(
        UserOrm.email.in_(["live@example.com", "deleted@example.com"])
    )
    visible_user_count = await db_session.scalar(user_count_query)

    assert visible_user_count == 1
