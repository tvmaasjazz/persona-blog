from datetime import datetime
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from libs.content_items.inputs import CreateContentItemInput, UpdateContentItemInput
from libs.content_items.types import ContentType
from libs.database.orm import ContentItemOrm


def build_create_content_item_input(
    *,
    persona_id: int,
    content_type: ContentType = ContentType.BLOG_POST,
    is_public: bool = False,
    published_at: datetime | None = None,
    generate_text_run_identity: UUID | None = None,
) -> CreateContentItemInput:
    return CreateContentItemInput(
        persona_id=persona_id,
        content_type=content_type,
        is_public=is_public,
        published_at=published_at,
        generate_text_run_identity=generate_text_run_identity,
    )


def build_update_content_item_input(
    *, is_public: bool = False, published_at: datetime | None = None
) -> UpdateContentItemInput:
    return UpdateContentItemInput(is_public=is_public, published_at=published_at)


async def insert_content_item_row(
    db_session: AsyncSession,
    *,
    created_by_id: int,
    persona_id: int,
    content_type: ContentType = ContentType.BLOG_POST,
    is_public: bool = False,
    published_at: datetime | None = None,
    created_at: datetime | None = None,
    deleted_at: datetime | None = None,
    deleted_by_id: int | None = None,
) -> ContentItemOrm:
    content_item_record = ContentItemOrm(
        persona_id=persona_id,
        content_type=content_type,
        is_public=is_public,
        published_at=published_at,
        deleted_at=deleted_at,
        created_by_id=created_by_id,
        updated_by_id=created_by_id,
        deleted_by_id=deleted_by_id,
    )
    if created_at is not None:
        content_item_record.created_at = created_at
    db_session.add(content_item_record)
    await db_session.flush()
    return content_item_record
