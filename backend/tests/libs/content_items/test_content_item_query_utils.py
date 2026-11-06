from datetime import UTC, datetime

import pytest
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
    db_session: AsyncSession, auth_user_id: int | None
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


async def test_build_accessible_condition_other_user_does_not_see_content_of_inactive_creator(
    db_session: AsyncSession,
) -> None:
    suspended_owner_record = await insert_user_row(db_session, is_active=False)
    other_user_record = await insert_user_row(db_session)
    persona_record = await insert_persona_row(
        db_session, created_by_id=suspended_owner_record.id, is_public=True
    )
    content_item_record = await insert_content_item_row(
        db_session,
        created_by_id=suspended_owner_record.id,
        persona_id=persona_record.id,
        is_public=True,
        published_at=PAST_PUBLISHED_AT,
    )
    await db_session.commit()

    accessible_content_item_ids = await _find_accessible_content_item_ids(
        db_session, other_user_record.id
    )

    assert content_item_record.id not in accessible_content_item_ids


async def test_build_accessible_condition_inactive_owner_still_sees_own_content_item(
    db_session: AsyncSession,
) -> None:
    suspended_owner_record = await insert_user_row(db_session, is_active=False)
    persona_record = await insert_persona_row(
        db_session, created_by_id=suspended_owner_record.id, is_public=True
    )
    content_item_record = await insert_content_item_row(
        db_session,
        created_by_id=suspended_owner_record.id,
        persona_id=persona_record.id,
        is_public=True,
        published_at=PAST_PUBLISHED_AT,
    )
    await db_session.commit()

    accessible_content_item_ids = await _find_accessible_content_item_ids(
        db_session, suspended_owner_record.id
    )

    assert content_item_record.id in accessible_content_item_ids


async def test_build_accessible_condition_no_user_sees_published_content_on_public_persona(
    db_session: AsyncSession,
) -> None:
    owner_record = await insert_user_row(db_session)
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

    accessible_content_item_ids = await _find_accessible_content_item_ids(db_session, None)

    assert content_item_record.id in accessible_content_item_ids


async def test_build_accessible_condition_no_user_does_not_see_private_content_item(
    db_session: AsyncSession,
) -> None:
    owner_record = await insert_user_row(db_session)
    persona_record = await insert_persona_row(
        db_session, created_by_id=owner_record.id, is_public=True
    )
    content_item_record = await insert_content_item_row(
        db_session,
        created_by_id=owner_record.id,
        persona_id=persona_record.id,
        is_public=False,
        published_at=PAST_PUBLISHED_AT,
    )
    await db_session.commit()

    accessible_content_item_ids = await _find_accessible_content_item_ids(db_session, None)

    assert content_item_record.id not in accessible_content_item_ids


async def test_build_accessible_condition_no_user_does_not_see_unpublished_content_item(
    db_session: AsyncSession,
) -> None:
    owner_record = await insert_user_row(db_session)
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

    accessible_content_item_ids = await _find_accessible_content_item_ids(db_session, None)

    assert content_item_record.id not in accessible_content_item_ids


async def test_build_accessible_condition_no_user_does_not_see_future_published_content_item(
    db_session: AsyncSession,
) -> None:
    owner_record = await insert_user_row(db_session)
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

    accessible_content_item_ids = await _find_accessible_content_item_ids(db_session, None)

    assert content_item_record.id not in accessible_content_item_ids


async def test_build_accessible_condition_no_user_does_not_see_content_on_private_persona(
    db_session: AsyncSession,
) -> None:
    owner_record = await insert_user_row(db_session)
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

    accessible_content_item_ids = await _find_accessible_content_item_ids(db_session, None)

    assert content_item_record.id not in accessible_content_item_ids


async def test_build_accessible_condition_no_user_does_not_see_content_of_inactive_creator(
    db_session: AsyncSession,
) -> None:
    suspended_owner_record = await insert_user_row(db_session, is_active=False)
    persona_record = await insert_persona_row(
        db_session, created_by_id=suspended_owner_record.id, is_public=True
    )
    content_item_record = await insert_content_item_row(
        db_session,
        created_by_id=suspended_owner_record.id,
        persona_id=persona_record.id,
        is_public=True,
        published_at=PAST_PUBLISHED_AT,
    )
    await db_session.commit()

    accessible_content_item_ids = await _find_accessible_content_item_ids(db_session, None)

    assert content_item_record.id not in accessible_content_item_ids


async def _find_published_public_content_item_ids(db_session: AsyncSession) -> list[int]:
    query = (
        select(ContentItemOrm.id)
        .join(PersonaOrm, ContentItemOrm.persona_id == PersonaOrm.id)
        .where(ContentItemQueryUtils.build_published_public_condition())
    )
    query_result = await db_session.execute(query)
    return list(query_result.scalars().all())


async def test_build_published_public_condition_matches_published_content_on_public_persona(
    db_session: AsyncSession,
) -> None:
    owner_record = await insert_user_row(db_session)
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

    published_public_content_item_ids = await _find_published_public_content_item_ids(db_session)

    assert content_item_record.id in published_public_content_item_ids


@pytest.mark.parametrize(
    ("is_persona_public", "is_public", "published_at", "is_creator_active"),
    [
        pytest.param(True, False, PAST_PUBLISHED_AT, True, id="private_content_item"),
        pytest.param(True, True, None, True, id="draft"),
        pytest.param(True, True, FUTURE_PUBLISHED_AT, True, id="future_published_at"),
        pytest.param(False, True, PAST_PUBLISHED_AT, True, id="private_persona"),
        pytest.param(True, True, PAST_PUBLISHED_AT, False, id="inactive_creator"),
    ],
)
async def test_build_published_public_condition_hidden_content_item_not_matched_even_for_its_owner(
    db_session: AsyncSession,
    is_persona_public: bool,
    is_public: bool,
    published_at: datetime | None,
    is_creator_active: bool,
) -> None:
    owner_record = await insert_user_row(db_session, is_active=is_creator_active)
    persona_record = await insert_persona_row(
        db_session, created_by_id=owner_record.id, is_public=is_persona_public
    )
    content_item_record = await insert_content_item_row(
        db_session,
        created_by_id=owner_record.id,
        persona_id=persona_record.id,
        is_public=is_public,
        published_at=published_at,
    )
    await db_session.commit()

    published_public_content_item_ids = await _find_published_public_content_item_ids(db_session)

    assert content_item_record.id not in published_public_content_item_ids


async def test_build_published_public_condition_soft_deleted_persona_not_matched(
    db_session: AsyncSession,
) -> None:
    owner_record = await insert_user_row(db_session)
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

    published_public_content_item_ids = await _find_published_public_content_item_ids(db_session)

    assert content_item_record.id not in published_public_content_item_ids
