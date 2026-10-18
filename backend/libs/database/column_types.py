from datetime import UTC, datetime

from sqlalchemy import DateTime, Dialect
from sqlalchemy.types import TypeDecorator


class UtcDateTime(TypeDecorator[datetime]):
    """A `TIMESTAMP` column stored as naive UTC that Python sees as aware UTC."""

    impl = DateTime(timezone=False)
    cache_ok = True

    def process_bind_param(self, value: datetime | None, dialect: Dialect) -> datetime | None:
        """Converts an aware datetime to naive UTC for Postgres."""
        if value is None:
            return None
        # A naive datetime has no known time zone
        if value.tzinfo is None:
            raise ValueError("UtcDateTime needs a timezone-aware datetime")
        # asyncpg rejects aware datetimes for a TIMESTAMP column
        return value.astimezone(UTC).replace(tzinfo=None)

    def process_result_value(self, value: datetime | None, dialect: Dialect) -> datetime | None:
        """Marks a value read from Postgres as UTC."""
        if value is None:
            return None
        return value.replace(tzinfo=UTC)
