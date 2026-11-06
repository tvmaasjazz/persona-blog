from sqlalchemy import Date, cast, literal_column
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from libs.auth.results import AuthUser
from libs.content_engagement.inputs import RecordContentViewInput
from libs.content_engagement.services.content_engagement_service import ContentEngagementService
from libs.database.orm import ContentItemViewOrm
from libs.database.utils import DatabaseClockUtils


class ContentViewService:
    """Records a reader's views of content items, one per reader per UTC day."""

    def __init__(
        self, db_session: AsyncSession, content_engagement_service: ContentEngagementService
    ) -> None:
        self._db_session = db_session
        self._content_engagement_service = content_engagement_service

    async def record_content_view(
        self, record_content_view_input: RecordContentViewInput, auth_user: AuthUser | None
    ) -> None:
        """Records the view, raising the day's read percent only upward, and adds what it
        gained to the item's engagement; a request that raises nothing changes nothing."""
        # Identify the viewer: a signed-in user by id, a signed-out visitor by their key
        if auth_user is not None:
            viewer_id = auth_user.id
            anonymous_user_key = None
        elif record_content_view_input.anonymous_user_key is not None:
            viewer_id = None
            anonymous_user_key = record_content_view_input.anonymous_user_key
        else:
            raise ValueError("A view needs a signed-in user or an anonymous user key")

        # Insert the day's view, or raise its read percent when the new one is higher.
        # The conflict target repeats the WHERE of the viewer kind's partial unique index
        if viewer_id is not None:
            index_elements = ["content_item_id", "created_by_id", "viewed_on"]
            index_where = ContentItemViewOrm.created_by_id.is_not(None) & (
                ContentItemViewOrm.deleted_at.is_(None)
            )
        else:
            index_elements = ["content_item_id", "anonymous_user_key", "viewed_on"]
            index_where = ContentItemViewOrm.anonymous_user_key.is_not(None) & (
                ContentItemViewOrm.deleted_at.is_(None)
            )

        content_item_view_insert = insert(ContentItemViewOrm).values(
            content_item_id=record_content_view_input.content_item_id,
            viewed_on=cast(DatabaseClockUtils.build_utc_now_sql(), Date),
            read_percent=record_content_view_input.read_percent,
            anonymous_user_key=anonymous_user_key,
            created_by_id=viewer_id,
            updated_by_id=viewer_id,
        )
        # SQLAlchemy's onupdate does not fire for ON CONFLICT DO UPDATE, so updated_at is set here
        content_item_view_upsert = content_item_view_insert.on_conflict_do_update(
            index_elements=index_elements,
            index_where=index_where,
            set_={
                "read_percent": content_item_view_insert.excluded.read_percent,
                "updated_at": DatabaseClockUtils.build_utc_now_sql(),
            },
            where=content_item_view_insert.excluded.read_percent > ContentItemViewOrm.read_percent,
        ).returning(
            ContentItemViewOrm.read_percent,
            # Postgres 18: the value before the update, NULL for a row just inserted
            literal_column("old.read_percent").label("old_read_percent"),
        )
        content_item_view_upsert_result = await self._db_session.execute(content_item_view_upsert)
        view_row = content_item_view_upsert_result.one_or_none()

        # Nothing was inserted or raised
        if view_row is None:
            return

        # Add what the view gained to the item's engagement
        if view_row.old_read_percent is None:
            view_count_increase = 1
            read_percent_sum_increase = view_row.read_percent
        else:
            view_count_increase = 0
            read_percent_sum_increase = view_row.read_percent - view_row.old_read_percent
        await self._content_engagement_service.add_engagement(
            record_content_view_input.content_item_id,
            view_count_increase,
            read_percent_sum_increase,
        )
