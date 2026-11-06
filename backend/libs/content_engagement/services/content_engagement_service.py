from sqlalchemy import ColumnElement, insert, literal, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from libs.content_engagement.settings import ContentEngagementSettings
from libs.content_engagement.utils import ContentEngagementUtils
from libs.database.orm import ContentItemEngagementOrm, ContentItemOrm, UserOrm


class ContentEngagementService:
    """Keeps each content item's engagement counts and feed score."""

    def __init__(
        self, db_session: AsyncSession, content_engagement_settings: ContentEngagementSettings
    ) -> None:
        self._db_session = db_session
        self._content_engagement_settings = content_engagement_settings

    async def create_engagement(self, content_item_id: int) -> None:
        """Inserts the item's engagement row with no views, scored from its publish time."""
        system_user_id_sql = self._build_system_user_id_sql()
        feed_score_sql = ContentEngagementUtils.build_feed_score_sql(
            literal(0), literal(0), ContentItemOrm.published_at, self._content_engagement_settings
        )
        content_item_query = select(
            ContentItemOrm.id,
            literal(0),
            literal(0),
            feed_score_sql,
            system_user_id_sql,
            system_user_id_sql,
        ).where(ContentItemOrm.id == content_item_id)
        content_item_engagement_insert = insert(ContentItemEngagementOrm).from_select(
            [
                "content_item_id",
                "view_count",
                "read_percent_sum",
                "feed_score",
                "created_by_id",
                "updated_by_id",
            ],
            content_item_query,
        )
        await self._db_session.execute(content_item_engagement_insert)

    async def rescore_engagement(self, content_item_id: int) -> None:
        """Recomputes the item's feed score from its counts and current publish time."""
        feed_score_sql = ContentEngagementUtils.build_feed_score_sql(
            ContentItemEngagementOrm.view_count,
            ContentItemEngagementOrm.read_percent_sum,
            ContentItemOrm.published_at,
            self._content_engagement_settings,
        )
        content_item_engagement_rescore_update = (
            update(ContentItemEngagementOrm)
            .where(
                ContentItemEngagementOrm.content_item_id == content_item_id,
                ContentItemOrm.id == ContentItemEngagementOrm.content_item_id,
            )
            .values(feed_score=feed_score_sql, updated_by_id=self._build_system_user_id_sql())
        )
        await self._db_session.execute(content_item_engagement_rescore_update)

    async def add_engagement(
        self, content_item_id: int, view_count_increase: int, read_percent_sum_increase: int
    ) -> None:
        """Adds to the item's counts and rewrites its feed score in one statement."""
        # In an UPDATE's SET the columns are the old values, so the score adds the increases itself
        new_view_count_sql = ContentItemEngagementOrm.view_count + view_count_increase
        new_read_percent_sum_sql = (
            ContentItemEngagementOrm.read_percent_sum + read_percent_sum_increase
        )
        feed_score_sql = ContentEngagementUtils.build_feed_score_sql(
            new_view_count_sql,
            new_read_percent_sum_sql,
            ContentItemOrm.published_at,
            self._content_engagement_settings,
        )
        content_item_engagement_add_update = (
            update(ContentItemEngagementOrm)
            .where(
                ContentItemEngagementOrm.content_item_id == content_item_id,
                ContentItemOrm.id == ContentItemEngagementOrm.content_item_id,
            )
            .values(
                view_count=new_view_count_sql,
                read_percent_sum=new_read_percent_sum_sql,
                feed_score=feed_score_sql,
                updated_by_id=self._build_system_user_id_sql(),
            )
        )
        await self._db_session.execute(content_item_engagement_add_update)

    async def rescore_all_engagement(self) -> int:
        """Recomputes every item's feed score, returning how many rows it rescored."""
        feed_score_sql = ContentEngagementUtils.build_feed_score_sql(
            ContentItemEngagementOrm.view_count,
            ContentItemEngagementOrm.read_percent_sum,
            ContentItemOrm.published_at,
            self._content_engagement_settings,
        )
        content_item_engagement_rescore_all_update = (
            update(ContentItemEngagementOrm)
            .where(ContentItemOrm.id == ContentItemEngagementOrm.content_item_id)
            .values(feed_score=feed_score_sql, updated_by_id=self._build_system_user_id_sql())
        )
        rescore_all_update_result = await self._db_session.execute(
            content_item_engagement_rescore_all_update
        )
        return rescore_all_update_result.rowcount

    def _build_system_user_id_sql(self) -> ColumnElement[int]:
        return select(UserOrm.id).where(UserOrm.is_system_user).scalar_subquery()
