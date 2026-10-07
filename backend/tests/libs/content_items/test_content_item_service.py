from datetime import UTC, datetime
from uuid import uuid4

import pytest
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from libs.content_items.services import ContentItemService
from libs.core.exceptions import NotFoundException
from libs.database.orm import ContentItemOrm, GenerateTextRunOrm
from tests.factories.auth import build_auth_user
from tests.factories.content_items import (
    build_create_content_item_input,
    build_update_content_item_input,
    insert_content_item_row,
)
from tests.factories.generate_text import insert_generate_text_run_row
from tests.factories.personas import insert_persona_row
from tests.factories.users import insert_user_row


async def test_create_content_item_persists_row(db_session: AsyncSession) -> None:
    user_record = await insert_user_row(db_session)
    auth_user = build_auth_user(user_id=user_record.id, user_identity=user_record.identity)
    persona_record = await insert_persona_row(db_session, created_by_id=user_record.id)
    await db_session.commit()
    content_item_service = ContentItemService(db_session=db_session)
    create_content_item_input = build_create_content_item_input(persona_id=persona_record.id)

    create_content_item_result = await content_item_service.create_content_item(
        create_content_item_input, auth_user
    )

    content_item_query = select(ContentItemOrm).where(
        ContentItemOrm.id == create_content_item_result.id
    )
    content_item_record = await db_session.scalar(content_item_query)
    assert content_item_record is not None
    assert content_item_record.identity == create_content_item_result.identity
    assert content_item_record.persona_id == persona_record.id
    assert content_item_record.created_by_id == auth_user.id
    assert content_item_record.updated_by_id == auth_user.id


async def test_update_content_item_replaces_is_public_and_published_at(
    db_session: AsyncSession,
) -> None:
    user_record = await insert_user_row(db_session)
    auth_user = build_auth_user(user_id=user_record.id, user_identity=user_record.identity)
    persona_record = await insert_persona_row(
        db_session, created_by_id=user_record.id, is_public=True
    )
    content_item_record = await insert_content_item_row(
        db_session, created_by_id=user_record.id, persona_id=persona_record.id, is_public=False
    )
    await db_session.commit()
    content_item_service = ContentItemService(db_session=db_session)
    published_at = datetime(2026, 1, 2, 3, 4, 5, tzinfo=UTC)
    update_content_item_input = build_update_content_item_input(
        is_public=True, published_at=published_at
    )

    await content_item_service.update_content_item(
        content_item_record.id, update_content_item_input, auth_user
    )

    content_item_query = select(ContentItemOrm).where(ContentItemOrm.id == content_item_record.id)
    updated_content_item_record = await db_session.scalar(content_item_query)
    assert updated_content_item_record is not None
    assert updated_content_item_record.is_public is True
    assert updated_content_item_record.published_at == published_at
    assert updated_content_item_record.updated_by_id == auth_user.id


async def test_update_content_item_never_inserted_raises_not_found_exception(
    db_session: AsyncSession,
) -> None:
    user_record = await insert_user_row(db_session)
    auth_user = build_auth_user(user_id=user_record.id, user_identity=user_record.identity)
    await db_session.commit()
    content_item_service = ContentItemService(db_session=db_session)

    with pytest.raises(NotFoundException):
        await content_item_service.update_content_item(
            999999, build_update_content_item_input(), auth_user
        )


async def test_delete_content_item_soft_deletes_row(db_session: AsyncSession) -> None:
    user_record = await insert_user_row(db_session)
    auth_user = build_auth_user(user_id=user_record.id, user_identity=user_record.identity)
    persona_record = await insert_persona_row(db_session, created_by_id=user_record.id)
    content_item_record = await insert_content_item_row(
        db_session, created_by_id=user_record.id, persona_id=persona_record.id
    )
    await db_session.commit()
    content_item_service = ContentItemService(db_session=db_session)

    await content_item_service.delete_content_item(content_item_record.id, auth_user)

    orm_query = select(ContentItemOrm).where(ContentItemOrm.id == content_item_record.id)
    orm_result = await db_session.scalar(orm_query)
    raw_query = text(
        "SELECT deleted_at, deleted_by_id FROM pb_content_item WHERE id = :content_item_id"
    )
    raw_result = (
        await db_session.execute(raw_query, {"content_item_id": content_item_record.id})
    ).one()
    assert orm_result is None
    assert raw_result.deleted_at is not None
    assert raw_result.deleted_by_id == auth_user.id


async def test_delete_content_item_never_inserted_raises_not_found_exception(
    db_session: AsyncSession,
) -> None:
    user_record = await insert_user_row(db_session)
    auth_user = build_auth_user(user_id=user_record.id, user_identity=user_record.identity)
    await db_session.commit()
    content_item_service = ContentItemService(db_session=db_session)

    with pytest.raises(NotFoundException):
        await content_item_service.delete_content_item(999999, auth_user)


async def test_create_content_item_with_generate_text_run_identity_links_run(
    db_session: AsyncSession,
) -> None:
    user_record = await insert_user_row(db_session)
    auth_user = build_auth_user(user_id=user_record.id, user_identity=user_record.identity)
    persona_record = await insert_persona_row(db_session, created_by_id=user_record.id)
    generate_text_run_record = await insert_generate_text_run_row(
        db_session, created_by_id=user_record.id, persona_id=persona_record.id
    )
    await db_session.commit()
    content_item_service = ContentItemService(db_session=db_session)
    create_content_item_input = build_create_content_item_input(
        persona_id=persona_record.id,
        generate_text_run_identity=generate_text_run_record.identity,
    )

    create_content_item_result = await content_item_service.create_content_item(
        create_content_item_input, auth_user
    )

    run_query = select(GenerateTextRunOrm).where(
        GenerateTextRunOrm.id == generate_text_run_record.id
    )
    updated_run_record = await db_session.scalar(run_query)
    assert updated_run_record is not None
    assert updated_run_record.content_item_id == create_content_item_result.id


async def test_create_content_item_unknown_generate_text_run_identity_raises_not_found_exception(
    db_session: AsyncSession,
) -> None:
    user_record = await insert_user_row(db_session)
    auth_user = build_auth_user(user_id=user_record.id, user_identity=user_record.identity)
    persona_record = await insert_persona_row(db_session, created_by_id=user_record.id)
    await db_session.commit()
    content_item_service = ContentItemService(db_session=db_session)
    create_content_item_input = build_create_content_item_input(
        persona_id=persona_record.id, generate_text_run_identity=uuid4()
    )

    with pytest.raises(NotFoundException):
        await content_item_service.create_content_item(create_content_item_input, auth_user)


async def test_create_content_item_without_generate_text_run_identity_touches_no_run(
    db_session: AsyncSession,
) -> None:
    user_record = await insert_user_row(db_session)
    auth_user = build_auth_user(user_id=user_record.id, user_identity=user_record.identity)
    persona_record = await insert_persona_row(db_session, created_by_id=user_record.id)
    generate_text_run_record = await insert_generate_text_run_row(
        db_session, created_by_id=user_record.id, persona_id=persona_record.id
    )
    await db_session.commit()
    content_item_service = ContentItemService(db_session=db_session)
    create_content_item_input = build_create_content_item_input(persona_id=persona_record.id)

    await content_item_service.create_content_item(create_content_item_input, auth_user)

    run_query = select(GenerateTextRunOrm).where(
        GenerateTextRunOrm.id == generate_text_run_record.id
    )
    unchanged_run_record = await db_session.scalar(run_query)
    assert unchanged_run_record is not None
    assert unchanged_run_record.content_item_id is None
