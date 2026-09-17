from datetime import UTC, datetime, timedelta, timezone

import pytest
from sqlalchemy import select, text
from sqlalchemy.exc import StatementError
from sqlalchemy.ext.asyncio import AsyncSession

from libs.database.orm import UserOrm
from tests.factories.users import insert_user_row


async def test_utc_date_time_stores_aware_datetime_as_naive_utc(
    db_session: AsyncSession,
) -> None:
    plus_two_hours = timezone(timedelta(hours=2))
    user_record = await insert_user_row(
        db_session, last_login_at=datetime(2026, 1, 2, 5, 4, 5, tzinfo=plus_two_hours)
    )

    stored_last_login_at = await db_session.scalar(
        text("SELECT last_login_at FROM pb_user WHERE id = :user_id"),
        {"user_id": user_record.id},
    )

    assert stored_last_login_at == datetime(2026, 1, 2, 3, 4, 5)


async def test_utc_date_time_loads_stored_value_as_aware_utc(db_session: AsyncSession) -> None:
    user_record = await insert_user_row(
        db_session, last_login_at=datetime(2026, 1, 2, 3, 4, 5, tzinfo=UTC)
    )

    last_login_at_query = select(UserOrm.last_login_at).where(UserOrm.id == user_record.id)
    loaded_last_login_at = await db_session.scalar(last_login_at_query)

    assert loaded_last_login_at == datetime(2026, 1, 2, 3, 4, 5, tzinfo=UTC)
    assert loaded_last_login_at.tzinfo == UTC


async def test_utc_date_time_naive_datetime_raises(db_session: AsyncSession) -> None:
    with pytest.raises(StatementError):
        await insert_user_row(db_session, last_login_at=datetime(2026, 1, 2, 3, 4, 5))
