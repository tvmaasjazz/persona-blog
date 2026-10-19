from uuid import UUID

from sqlalchemy import insert, update
from sqlalchemy.ext.asyncio import AsyncSession

from libs.auth.results import AuthUser
from libs.content_items.inputs import CreateContentItemInput, UpdateContentItemInput
from libs.content_items.results import CreateContentItemResult
from libs.core.exceptions import NotFoundException
from libs.database.orm import ContentItemOrm, GenerateTextRunOrm
from libs.database.utils import DatabaseClockUtils


class ContentItemService:
    """Writes the content item row shared by every kind of published content."""

    def __init__(self, db_session: AsyncSession) -> None:
        self._db_session = db_session

    async def create_content_item(
        self, create_content_item_input: CreateContentItemInput, auth_user: AuthUser
    ) -> CreateContentItemResult:
        """Inserts the item and links a generate text run to it when the input names one."""
        content_item_insert = (
            insert(ContentItemOrm)
            .values(
                persona_id=create_content_item_input.persona_id,
                content_type=create_content_item_input.content_type,
                is_public=create_content_item_input.is_public,
                published_at=create_content_item_input.published_at,
                created_by_id=auth_user.id,
                updated_by_id=auth_user.id,
            )
            .returning(ContentItemOrm.id, ContentItemOrm.identity)
        )
        content_item_insert_result = await self._db_session.execute(content_item_insert)
        content_item_row = content_item_insert_result.one()

        if create_content_item_input.generate_text_run_identity is not None:
            await self._link_generate_text_run(
                content_item_row.id, create_content_item_input.generate_text_run_identity
            )

        return CreateContentItemResult(id=content_item_row.id, identity=content_item_row.identity)

    async def update_content_item(
        self,
        content_item_id: int,
        update_content_item_input: UpdateContentItemInput,
        auth_user: AuthUser,
    ) -> None:
        """Sets visibility and publish time; NotFoundException if the item is gone."""
        # The where clause is the lookup; a soft-deleted row counts as missing
        content_item_update = (
            update(ContentItemOrm)
            .where(ContentItemOrm.id == content_item_id, ContentItemOrm.deleted_at.is_(None))
            .values(
                is_public=update_content_item_input.is_public,
                published_at=update_content_item_input.published_at,
                updated_by_id=auth_user.id,
            )
        )
        content_item_update_result = await self._db_session.execute(content_item_update)
        if content_item_update_result.rowcount == 0:
            raise NotFoundException("Content item not found")

    async def delete_content_item(self, content_item_id: int, auth_user: AuthUser) -> None:
        """Soft-deletes the item; NotFoundException if it is missing or already deleted."""
        # The where clause is the lookup; a soft-deleted row counts as missing
        content_item_soft_delete_update = (
            update(ContentItemOrm)
            .where(ContentItemOrm.id == content_item_id, ContentItemOrm.deleted_at.is_(None))
            .values(
                deleted_at=DatabaseClockUtils.build_utc_now_sql(),
                deleted_by_id=auth_user.id,
            )
        )
        content_item_soft_delete_update_result = await self._db_session.execute(
            content_item_soft_delete_update
        )
        if content_item_soft_delete_update_result.rowcount == 0:
            raise NotFoundException("Content item not found")

    async def _link_generate_text_run(
        self, content_item_id: int, generate_text_run_identity: UUID
    ) -> None:
        # The where clause is the lookup; a soft-deleted run counts as missing
        generate_text_run_link_update = (
            update(GenerateTextRunOrm)
            .where(
                GenerateTextRunOrm.identity == generate_text_run_identity,
                GenerateTextRunOrm.deleted_at.is_(None),
            )
            .values(content_item_id=content_item_id)
        )
        generate_text_run_link_update_result = await self._db_session.execute(
            generate_text_run_link_update
        )
        if generate_text_run_link_update_result.rowcount == 0:
            raise NotFoundException("Generate text run not found")
