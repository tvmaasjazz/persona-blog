from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from libs.auth.results import AuthUser
from libs.content_items.inputs import CreateContentItemInput, UpdateContentItemInput
from libs.content_items.results import CreateContentItemResult
from libs.core.exceptions import NotFoundException
from libs.database.orm import ContentItemOrm, GenerateTextRunOrm


class ContentItemService:
    def __init__(self, db_session: AsyncSession) -> None:
        self._db_session = db_session

    async def create_content_item(
        self, create_content_item_input: CreateContentItemInput, auth_user: AuthUser
    ) -> CreateContentItemResult:
        content_item_record = ContentItemOrm(
            persona_id=create_content_item_input.persona_id,
            content_type=create_content_item_input.content_type,
            is_public=create_content_item_input.is_public,
            published_at=create_content_item_input.published_at,
            created_by_id=auth_user.id,
            updated_by_id=auth_user.id,
        )
        self._db_session.add(content_item_record)
        await self._db_session.flush()

        if create_content_item_input.generate_text_run_identity is not None:
            await self._link_generate_text_run(
                content_item_record.id, create_content_item_input.generate_text_run_identity
            )

        return CreateContentItemResult(
            id=content_item_record.id, identity=content_item_record.identity
        )

    async def update_content_item(
        self,
        content_item_id: int,
        update_content_item_input: UpdateContentItemInput,
        auth_user: AuthUser,
    ) -> None:
        content_item_record = await self._find_content_item_record(content_item_id)
        content_item_record.is_public = update_content_item_input.is_public
        content_item_record.published_at = update_content_item_input.published_at
        content_item_record.updated_by_id = auth_user.id
        await self._db_session.flush()

    async def delete_content_item(self, content_item_id: int, auth_user: AuthUser) -> None:
        content_item_record = await self._find_content_item_record(content_item_id)
        # TODO(db-clock): the database's now, once this write is an update() statement
        content_item_record.deleted_at = datetime.now(UTC)
        content_item_record.deleted_by_id = auth_user.id
        await self._db_session.flush()

    async def _link_generate_text_run(
        self, content_item_id: int, generate_text_run_identity: UUID
    ) -> None:
        run_query = select(GenerateTextRunOrm).where(
            GenerateTextRunOrm.identity == generate_text_run_identity
        )
        run_query_result = await self._db_session.execute(run_query)
        generate_text_run_record = run_query_result.scalar_one_or_none()

        if generate_text_run_record is None:
            raise NotFoundException("Generate text run not found")
        generate_text_run_record.content_item_id = content_item_id
        await self._db_session.flush()

    async def _find_content_item_record(self, content_item_id: int) -> ContentItemOrm:
        content_item_query = select(ContentItemOrm).where(ContentItemOrm.id == content_item_id)
        content_item_query_result = await self._db_session.execute(content_item_query)
        content_item_record = content_item_query_result.scalar_one_or_none()

        if content_item_record is None:
            raise NotFoundException("Content item not found")
        return content_item_record
