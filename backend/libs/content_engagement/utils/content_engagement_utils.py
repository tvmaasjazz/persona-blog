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
        """The feed score as SQL; higher sorts first, and NULL for an unpublished item.

        It adds two parts. Engagement: views and reading earn points, and the log means
        each tenfold more points adds just 1. Recency: every hours-per-tenfold after the
        start date adds 1. So a post published a day later starts 1 ahead and an older
        post passes it only with ten times its engagement. Neither part changes as time
        passes, so the stored score never needs refreshing."""
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
