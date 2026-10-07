from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from libs.content_items.utils.content_item_query_utils import ContentItemQueryUtils
from libs.database.orm import ContentItemOrm, PersonaOrm
from tests.factories.content_items import insert_content_item_row
from tests.factories.personas import insert_persona_row
from tests.factories.users import insert_user_row

PAST_PUBLISHED_AT = datetime(2020, 1, 1, tzinfo=UTC)
FUTURE_PUBLISHED_AT = datetime(2999, 1, 1, tzinfo=UTC)


async def _find_accessible_content_item_ids(
    db_session: AsyncSession, auth_user_id: int
) -> list[int]:
    query = (
        select(ContentItemOrm.id)
        .join(PersonaOrm, ContentItemOrm.persona_id == PersonaOrm.id)
        .where(ContentItemQueryUtils.build_accessible_condition(auth_user_id))
    )
    query_result = await db_session.execute(query)
    return list(query_result.scalars().all())


async def test_build_accessible_condition_owner_sees_own_draft_private_content_item(
    db_session: AsyncSession,
) -> None:
    user_record = await insert_user_row(db_session)
    persona_record = await insert_persona_row(
        db_session, created_by_id=user_record.id, is_public=False
    )
    content_item_record = await insert_content_item_row(
        db_session,
        created_by_id=user_record.id,
        persona_id=persona_record.id,
        is_public=False,
        published_at=None,
    )
    await db_session.commit()

    accessible_content_item_ids = await _find_accessible_content_item_ids(
        db_session, user_record.id
    )

    assert content_item_record.id in accessible_content_item_ids


async def test_build_accessible_condition_other_user_sees_published_content_on_public_persona(
    db_session: AsyncSession,
) -> None:
    owner_record = await insert_user_row(db_session)
    other_user_record = await insert_user_row(db_session)
    persona_record = await insert_persona_row(
        db_session, created_by_id=owner_record.id, is_public=True
    )
    content_item_record = await insert_content_item_row(
        db_session,
        created_by_id=owner_record.id,
        persona_id=persona_record.id,
        is_public=True,
        published_at=PAST_PUBLISHED_AT,
    )
    await db_session.commit()

    accessible_content_item_ids = await _find_accessible_content_item_ids(
        db_session, other_user_record.id
    )

    assert content_item_record.id in accessible_content_item_ids


async def test_build_accessible_condition_other_user_future_published_at_hidden(
    db_session: AsyncSession,
) -> None:
    owner_record = await insert_user_row(db_session)
    other_user_record = await insert_user_row(db_session)
    persona_record = await insert_persona_row(
        db_session, created_by_id=owner_record.id, is_public=True
    )
    content_item_record = await insert_content_item_row(
        db_session,
        created_by_id=owner_record.id,
        persona_id=persona_record.id,
        is_public=True,
        published_at=FUTURE_PUBLISHED_AT,
    )
    await db_session.commit()

    accessible_content_item_ids = await _find_accessible_content_item_ids(
        db_session, other_user_record.id
    )

    assert content_item_record.id not in accessible_content_item_ids


async def test_build_accessible_condition_other_user_draft_hidden(
    db_session: AsyncSession,
) -> None:
    owner_record = await insert_user_row(db_session)
    other_user_record = await insert_user_row(db_session)
    persona_record = await insert_persona_row(
        db_session, created_by_id=owner_record.id, is_public=True
    )
    content_item_record = await insert_content_item_row(
        db_session,
        created_by_id=owner_record.id,
        persona_id=persona_record.id,
        is_public=True,
        published_at=None,
    )
    await db_session.commit()

    accessible_content_item_ids = await _find_accessible_content_item_ids(
        db_session, other_user_record.id
    )

    assert content_item_record.id not in accessible_content_item_ids


async def test_build_accessible_condition_private_persona_hides_public_post(
    db_session: AsyncSession,
) -> None:
    owner_record = await insert_user_row(db_session)
    other_user_record = await insert_user_row(db_session)
    persona_record = await insert_persona_row(
        db_session, created_by_id=owner_record.id, is_public=False
    )
    content_item_record = await insert_content_item_row(
        db_session,
        created_by_id=owner_record.id,
        persona_id=persona_record.id,
        is_public=True,
        published_at=PAST_PUBLISHED_AT,
    )
    await db_session.commit()

    accessible_content_item_ids = await _find_accessible_content_item_ids(
        db_session, other_user_record.id
    )

    assert content_item_record.id not in accessible_content_item_ids


async def test_build_accessible_condition_soft_deleted_persona_hides_content_item(
    db_session: AsyncSession,
) -> None:
    owner_record = await insert_user_row(db_session)
    other_user_record = await insert_user_row(db_session)
    persona_record = await insert_persona_row(
        db_session,
        created_by_id=owner_record.id,
        is_public=True,
        deleted_at=datetime(2026, 1, 2, 3, 4, 5, tzinfo=UTC),
        deleted_by_id=owner_record.id,
    )
    content_item_record = await insert_content_item_row(
        db_session,
        created_by_id=owner_record.id,
        persona_id=persona_record.id,
        is_public=True,
        published_at=PAST_PUBLISHED_AT,
    )
    await db_session.commit()

    accessible_content_item_ids = await _find_accessible_content_item_ids(
        db_session, other_user_record.id
    )

    assert content_item_record.id not in accessible_content_item_ids
