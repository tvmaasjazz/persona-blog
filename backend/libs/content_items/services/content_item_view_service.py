from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from libs.auth.results import AuthUser
from libs.content_engagement.inputs import RecordContentViewInput
from libs.content_engagement.services import ContentViewService
from libs.content_items.inputs import RecordContentItemViewInput
from libs.content_items.utils.content_item_query_utils import ContentItemQueryUtils
from libs.core.exceptions import NotFoundException
from libs.database.orm import ContentItemOrm, PersonaOrm


class ContentItemViewService:
    """Records readers' views of content items they may see."""

    def __init__(self, db_session: AsyncSession, content_view_service: ContentViewService) -> None:
        self._db_session = db_session
        self._content_view_service = content_view_service

    async def record_content_item_view(
        self,
        content_item_identity: UUID,
        record_content_item_view_input: RecordContentItemViewInput,
        anonymous_user_key: str | None,
        auth_user: AuthUser | None,
    ) -> None:
        """Records the reader's view of an item they may see, nothing for the item's own
        creator; NotFoundException when they can't see it."""
        # Find the item under the same access rule as the public reads
        auth_user_id = auth_user.id if auth_user is not None else None
        content_item_query = (
            select(ContentItemOrm.id, ContentItemOrm.created_by_id)
            .join(PersonaOrm, ContentItemOrm.persona_id == PersonaOrm.id)
            .where(
                ContentItemOrm.identity == content_item_identity,
                ContentItemOrm.deleted_at.is_(None),
                ContentItemQueryUtils.build_accessible_condition(auth_user_id),
            )
        )
        content_item_query_result = await self._db_session.execute(content_item_query)
        content_item_row = content_item_query_result.one_or_none()
        if content_item_row is None:
            raise NotFoundException("Content item not found")

        # A creator viewing their own item is not a view
        if auth_user_id is not None and content_item_row.created_by_id == auth_user_id:
            return

        # Record the view
        record_content_view_input = RecordContentViewInput(
            content_item_id=content_item_row.id,
            read_percent=record_content_item_view_input.read_percent,
            anonymous_user_key=anonymous_user_key,
        )
        await self._content_view_service.record_content_view(record_content_view_input, auth_user)
