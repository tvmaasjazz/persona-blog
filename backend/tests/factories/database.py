from datetime import UTC, datetime

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


async def fetch_database_utc_now(db_session: AsyncSession) -> datetime:
    """The database's now as an aware UTC datetime, read with plain SQL.

    Inside a test's outer transaction it is the same value every database-clock write stores.
    """
    naive_utc_now = await db_session.scalar(text("SELECT (now() AT TIME ZONE 'utc')"))
    return naive_utc_now.replace(tzinfo=UTC)
