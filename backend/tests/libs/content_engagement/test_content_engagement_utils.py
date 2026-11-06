from datetime import UTC, datetime

import pytest
from sqlalchemy import literal, select
from sqlalchemy.ext.asyncio import AsyncSession

from libs.content_engagement.settings import ContentEngagementSettings
from libs.content_engagement.utils import ContentEngagementUtils
from libs.database.column_types import UtcDateTime
from tests.factories.content_engagement import build_content_engagement_settings


async def _select_feed_score(
    db_session: AsyncSession,
    *,
    view_count: int,
    read_percent_sum: int,
    published_at: datetime | None,
    content_engagement_settings: ContentEngagementSettings,
) -> float | None:
    feed_score_sql = ContentEngagementUtils.build_feed_score_sql(
        literal(view_count),
        literal(read_percent_sum),
        literal(published_at, UtcDateTime),
        content_engagement_settings,
    )
    return await db_session.scalar(select(feed_score_sql))


@pytest.mark.parametrize(
    (
        "view_count",
        "read_percent_sum",
        "published_at",
        "view_weight",
        "read_weight",
        "hours_per_tenfold",
        "expected_feed_score",
    ),
    [
        pytest.param(
            0, 0, datetime(2026, 1, 2, tzinfo=UTC), 1.0, 3.0, 24.0, 1.0, id="no_engagement"
        ),
        pytest.param(
            3, 200, datetime(2026, 1, 2, tzinfo=UTC), 1.0, 3.0, 24.0, 2.0, id="nine_units"
        ),
        pytest.param(
            0, 0, datetime(2026, 1, 1, tzinfo=UTC), 1.0, 3.0, 24.0, 0.0, id="at_score_start"
        ),
        pytest.param(
            3, 0, datetime(2026, 1, 1, tzinfo=UTC), 3.0, 3.0, 24.0, 1.0, id="view_weight_three"
        ),
        pytest.param(
            0, 300, datetime(2026, 1, 1, tzinfo=UTC), 1.0, 3.0, 24.0, 1.0, id="read_weight_three"
        ),
        pytest.param(
            0, 100, datetime(2026, 1, 1, tzinfo=UTC), 1.0, 9.0, 24.0, 1.0, id="read_weight_nine"
        ),
        pytest.param(
            0, 0, datetime(2026, 1, 2, tzinfo=UTC), 1.0, 3.0, 12.0, 2.0, id="faster_recency"
        ),
    ],
)
async def test_build_feed_score_sql_returns_score(
    db_session: AsyncSession,
    view_count: int,
    read_percent_sum: int,
    published_at: datetime,
    view_weight: float,
    read_weight: float,
    hours_per_tenfold: float,
    expected_feed_score: float,
) -> None:
    content_engagement_settings = build_content_engagement_settings(
        view_weight=view_weight,
        read_weight=read_weight,
        feed_score_hours_per_tenfold=hours_per_tenfold,
    )

    feed_score = await _select_feed_score(
        db_session,
        view_count=view_count,
        read_percent_sum=read_percent_sum,
        published_at=published_at,
        content_engagement_settings=content_engagement_settings,
    )

    assert feed_score == pytest.approx(expected_feed_score)


async def test_build_feed_score_sql_null_published_at_returns_null(
    db_session: AsyncSession,
) -> None:
    feed_score = await _select_feed_score(
        db_session,
        view_count=3,
        read_percent_sum=200,
        published_at=None,
        content_engagement_settings=build_content_engagement_settings(),
    )

    assert feed_score is None
