from datetime import UTC, datetime

from sqlalchemy import DateTime, Dialect
from sqlalchemy.types import TypeDecorator


class UtcDateTime(TypeDecorator[datetime]):
    """A `TIMESTAMP` column whose values are always UTC.

    Postgres stores the value without a time zone. Python code only ever sees
    timezone-aware UTC datetimes, so comparisons with `datetime.now(UTC)` work and JSON
    output carries its `+00:00` offset.
    """

    impl = DateTime(timezone=False)
    cache_ok = True

    def process_bind_param(self, value: datetime | None, dialect: Dialect) -> datetime | None:
        """Runs when a value is sent to Postgres: inserts, updates, and query parameters.

        Converts an aware datetime to UTC and drops the time zone, because asyncpg rejects
        aware datetimes for a `TIMESTAMP` column. Raises on a naive datetime, since there's
        no way to know which time zone it was meant to be in.
        """
        if value is None:
            return None
        if value.tzinfo is None:
            raise ValueError("UtcDateTime needs a timezone-aware datetime")
        return value.astimezone(UTC).replace(tzinfo=None)

    def process_result_value(self, value: datetime | None, dialect: Dialect) -> datetime | None:
        """Runs when a value is read back from Postgres. Marks the naive value as UTC."""
        if value is None:
            return None
        return value.replace(tzinfo=UTC)
