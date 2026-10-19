from datetime import datetime, timedelta

from sqlalchemy import ColumnElement, Interval, literal, literal_column

from libs.database.column_types import UtcDateTime
from libs.database.constants import UTC_NOW_SQL


class DatabaseClockUtils:
    """Builds SQL for the database's clock, the one time source every server shares."""

    @staticmethod
    def build_utc_now_sql() -> ColumnElement[datetime]:
        """The database's current UTC time, as SQL."""
        return literal_column(UTC_NOW_SQL, UtcDateTime)

    @staticmethod
    def build_utc_now_plus_sql(seconds: float) -> ColumnElement[datetime]:
        """The database's current UTC time plus the given seconds."""
        # Typed as an interval: the UtcDateTime column type would reject a timedelta
        return DatabaseClockUtils.build_utc_now_sql() + literal(
            timedelta(seconds=seconds), Interval()
        )
