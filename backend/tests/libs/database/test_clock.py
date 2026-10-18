from datetime import UTC, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from libs.database.clock import build_utc_now_plus_sql, build_utc_now_sql, fetch_utc_now
from tests.factories.database import fetch_database_utc_now


async def test_fetch_utc_now_returns_aware_utc_database_time(db_session: AsyncSession) -> None:
    fetch_utc_now_result = await fetch_utc_now(db_session)

    database_utc_now = await fetch_database_utc_now(db_session)
    assert fetch_utc_now_result.tzinfo == UTC
    assert fetch_utc_now_result == database_utc_now


async def test_build_utc_now_sql_selects_database_time(db_session: AsyncSession) -> None:
    utc_now_query = select(build_utc_now_sql())

    selected_utc_now = await db_session.scalar(utc_now_query)

    database_utc_now = await fetch_database_utc_now(db_session)
    assert selected_utc_now == database_utc_now


async def test_build_utc_now_plus_sql_selects_database_time_plus_seconds(
    db_session: AsyncSession,
) -> None:
    utc_now_plus_query = select(build_utc_now_plus_sql(60))

    selected_utc_now_plus = await db_session.scalar(utc_now_plus_query)

    database_utc_now = await fetch_database_utc_now(db_session)
    assert selected_utc_now_plus == database_utc_now + timedelta(seconds=60)
