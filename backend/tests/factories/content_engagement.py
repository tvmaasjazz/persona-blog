from datetime import date
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from libs.content_engagement.settings import ContentEngagementSettings
from libs.database.orm import ContentItemEngagementOrm, ContentItemViewOrm


def build_content_engagement_settings(
    *,
    view_weight: float = 1.0,
    read_weight: float = 3.0,
    feed_score_hours_per_tenfold: float = 24.0,
) -> ContentEngagementSettings:
    return ContentEngagementSettings(
        view_weight=view_weight,
        read_weight=read_weight,
        feed_score_hours_per_tenfold=feed_score_hours_per_tenfold,
    )


async def insert_content_item_engagement_row(
    db_session: AsyncSession,
    *,
    content_item_id: int,
    system_user_id: int,
    view_count: int = 0,
    read_percent_sum: int = 0,
    feed_score: float | None = None,
) -> ContentItemEngagementOrm:
    content_item_engagement_record = ContentItemEngagementOrm(
        content_item_id=content_item_id,
        view_count=view_count,
        read_percent_sum=read_percent_sum,
        feed_score=feed_score,
        created_by_id=system_user_id,
        updated_by_id=system_user_id,
    )
    db_session.add(content_item_engagement_record)
    await db_session.flush()
    return content_item_engagement_record


async def insert_signed_in_content_item_view_row(
    db_session: AsyncSession,
    *,
    content_item_id: int,
    created_by_id: int,
    read_percent: int = 0,
    viewed_on: date | None = None,
) -> ContentItemViewOrm:
    content_item_view_record = ContentItemViewOrm(
        content_item_id=content_item_id,
        read_percent=read_percent,
        anonymous_user_key=None,
        created_by_id=created_by_id,
        updated_by_id=created_by_id,
    )
    # Left unset, the column's default fills in today's date
    if viewed_on is not None:
        content_item_view_record.viewed_on = viewed_on
    db_session.add(content_item_view_record)
    await db_session.flush()
    return content_item_view_record


async def insert_signed_out_content_item_view_row(
    db_session: AsyncSession,
    *,
    content_item_id: int,
    anonymous_user_key: str | None = None,
    read_percent: int = 0,
    viewed_on: date | None = None,
) -> ContentItemViewOrm:
    content_item_view_record = ContentItemViewOrm(
        content_item_id=content_item_id,
        read_percent=read_percent,
        anonymous_user_key=anonymous_user_key or str(uuid4()),
        created_by_id=None,
        updated_by_id=None,
    )
    if viewed_on is not None:
        content_item_view_record.viewed_on = viewed_on
    db_session.add(content_item_view_record)
    await db_session.flush()
    return content_item_view_record


async def find_content_item_engagement_row(
    db_session: AsyncSession, *, content_item_id: int
) -> ContentItemEngagementOrm:
    # Re-selects past the session's identity map, since services update the row in SQL
    content_item_engagement_query = (
        select(ContentItemEngagementOrm)
        .where(ContentItemEngagementOrm.content_item_id == content_item_id)
        .execution_options(populate_existing=True)
    )
    content_item_engagement_record = await db_session.scalar(content_item_engagement_query)
    assert content_item_engagement_record is not None
    return content_item_engagement_record
