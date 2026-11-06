from datetime import datetime
from typing import Any

from sqlalchemy import ColumnElement, Double, cast, extract, func, literal

from libs.content_engagement.constants import FEED_SCORE_START_AT
from libs.content_engagement.settings import ContentEngagementSettings
from libs.database.column_types import UtcDateTime

SECONDS_PER_HOUR = 3600
PERCENT_DIVISOR = 100.0


class ContentEngagementUtils:
    """Builds the SQL that scores a content item for the feed."""

    @staticmethod
    def build_feed_score_sql(
        view_count_sql: ColumnElement[Any],
        read_percent_sum_sql: ColumnElement[Any],
        published_at_sql: ColumnElement[datetime | None],
        content_engagement_settings: ContentEngagementSettings,
    ) -> ColumnElement[float]:
        """The score's SQL: log10 of weighted engagement plus hours since the start over
        hours per tenfold; NULL when the publish time is NULL."""
        view_weight = literal(content_engagement_settings.view_weight, Double)
        read_weight = literal(content_engagement_settings.read_weight, Double)
        hours_per_tenfold = literal(
            content_engagement_settings.feed_score_hours_per_tenfold, Double
        )
        score_start_at = literal(FEED_SCORE_START_AT, UtcDateTime)

        engagement_sql = (
            view_weight * view_count_sql + read_weight * read_percent_sum_sql / PERCENT_DIVISOR + 1
        )
        seconds_since_start_sql = cast(extract("epoch", published_at_sql - score_start_at), Double)
        recency_sql = seconds_since_start_sql / SECONDS_PER_HOUR / hours_per_tenfold
        return cast(func.log(cast(engagement_sql, Double)) + recency_sql, Double)
