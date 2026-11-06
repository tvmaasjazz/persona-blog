from sqlalchemy import literal_column
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
        # Identify the viewer: a signed-in user by id, else a signed-out visitor by their key
        viewer_id = auth_user.id if auth_user is not None else None
        anonymous_user_key = (
            record_content_view_input.anonymous_user_key if auth_user is None else None
        )
        if viewer_id is None and anonymous_user_key is None:
            raise ValueError("A view needs a signed-in user or an anonymous user key")
        viewer_column = (
            ContentItemViewOrm.created_by_id
            if viewer_id is not None
            else ContentItemViewOrm.anonymous_user_key
        )

        # Upsert today's view: insert it, or when the viewer already has one today, raise
        # its read percent only if the new one is higher. viewed_on takes its UTC-date default
        content_item_view_insert = insert(ContentItemViewOrm).values(
            content_item_id=record_content_view_input.content_item_id,
            read_percent=record_content_view_input.read_percent,
            anonymous_user_key=anonymous_user_key,
            created_by_id=viewer_id,
            updated_by_id=viewer_id,
        )
        content_item_view_upsert = content_item_view_insert.on_conflict_do_update(
            # The viewer already has a view today when a live row of their viewer kind has the
            # same item, viewer and day. Postgres checks that with the viewer kind's partial
            # unique index, found from its columns (index_elements) and WHERE (index_where)
            index_elements=[
                ContentItemViewOrm.content_item_id,
                viewer_column,
                ContentItemViewOrm.viewed_on,
            ],
            index_where=viewer_column.is_not(None) & ContentItemViewOrm.deleted_at.is_(None),
            # SQLAlchemy's onupdate does not fire here, so updated_at is set explicitly
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
