from datetime import datetime, timedelta

from sqlalchemy import ColumnElement, Interval, literal, literal_column, select
from sqlalchemy.ext.asyncio import AsyncSession

from libs.database.column_types import UtcDateTime
from libs.database.constants import UTC_NOW_SQL


def build_utc_now_sql() -> ColumnElement[datetime]:
    """The database's current UTC time, for a query or an update() to compare with or write."""
    return literal_column(UTC_NOW_SQL, UtcDateTime)


def build_utc_now_plus_sql(seconds: float) -> ColumnElement[datetime]:
    """The database's current UTC time plus the given seconds."""
    # Typed as an interval: the UtcDateTime column type would reject a timedelta
    return build_utc_now_sql() + literal(timedelta(seconds=seconds), Interval())


async def fetch_utc_now(db_session: AsyncSession) -> datetime:
    """The database's current UTC time, the same for the rest of the session's transaction."""
    # An Orm attribute set to SQL can't be read back in async code until it's reloaded,
    # so an Orm write assigns this value instead
    utc_now = await db_session.scalar(select(build_utc_now_sql()))
    if utc_now is None:
        raise RuntimeError("The database returned no current time")
    return utc_now
