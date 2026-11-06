from datetime import UTC, datetime

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from libs.content_engagement.services import ContentEngagementService
from libs.database.orm import ContentItemEngagementOrm
from tests.factories.content_engagement import (
    build_content_engagement_settings,
    insert_content_item_engagement_row,
)
from tests.factories.content_items import insert_content_item_row
from tests.factories.personas import insert_persona_row
from tests.factories.users import find_system_user_row, insert_user_row


async def _select_engagement(
    db_session: AsyncSession, content_item_id: int
) -> ContentItemEngagementOrm:
    engagement_query = (
        select(ContentItemEngagementOrm)
        .where(ContentItemEngagementOrm.content_item_id == content_item_id)
        .execution_options(populate_existing=True)
    )
    engagement_record = await db_session.scalar(engagement_query)
    assert engagement_record is not None
    return engagement_record


async def _insert_content_item_id(
    db_session: AsyncSession, *, published_at: datetime | None
) -> int:
    user_record = await insert_user_row(db_session)
    persona_record = await insert_persona_row(db_session, created_by_id=user_record.id)
    content_item_record = await insert_content_item_row(
        db_session,
        created_by_id=user_record.id,
        persona_id=persona_record.id,
        published_at=published_at,
    )
    return content_item_record.id


async def test_create_engagement_inserts_scored_row(
    db_session: AsyncSession, content_engagement_service: ContentEngagementService
) -> None:
    system_user_record = await find_system_user_row(db_session)
    content_item_id = await _insert_content_item_id(
        db_session, published_at=datetime(2026, 1, 2, tzinfo=UTC)
    )

    await content_engagement_service.create_engagement(content_item_id)

    engagement_record = await _select_engagement(db_session, content_item_id)
    assert engagement_record.view_count == 0
    assert engagement_record.read_percent_sum == 0
    assert engagement_record.feed_score == pytest.approx(1.0)
    assert engagement_record.created_by_id == system_user_record.id


async def test_add_engagement_adds_counts_and_scores_from_new_counts(
    db_session: AsyncSession, content_engagement_service: ContentEngagementService
) -> None:
    system_user_record = await find_system_user_row(db_session)
    content_item_id = await _insert_content_item_id(
        db_session, published_at=datetime(2026, 1, 2, tzinfo=UTC)
    )
    await insert_content_item_engagement_row(
        db_session,
        content_item_id=content_item_id,
        system_user_id=system_user_record.id,
        view_count=1,
        read_percent_sum=100,
        feed_score=0.0,
    )

    await content_engagement_service.add_engagement(content_item_id, 2, 100)

    # 1 + 2 views and 100 + 100 read percent: 3 + 3 * 200 / 100 = 9 units, so log10 is 1
    engagement_record = await _select_engagement(db_session, content_item_id)
    assert engagement_record.view_count == 3
    assert engagement_record.read_percent_sum == 200
    assert engagement_record.feed_score == pytest.approx(2.0)


async def test_add_engagement_sets_updated_by_to_system_user(
    db_session: AsyncSession, content_engagement_service: ContentEngagementService
) -> None:
    system_user_record = await find_system_user_row(db_session)
    other_user_record = await insert_user_row(db_session)
    content_item_id = await _insert_content_item_id(
        db_session, published_at=datetime(2026, 1, 2, tzinfo=UTC)
    )
    engagement_record = await insert_content_item_engagement_row(
        db_session, content_item_id=content_item_id, system_user_id=other_user_record.id
    )

    await content_engagement_service.add_engagement(content_item_id, 1, 0)

    await db_session.refresh(engagement_record)
    assert engagement_record.updated_by_id == system_user_record.id


async def test_add_engagement_null_published_at_leaves_score_null(
    db_session: AsyncSession, content_engagement_service: ContentEngagementService
) -> None:
    system_user_record = await find_system_user_row(db_session)
    content_item_id = await _insert_content_item_id(db_session, published_at=None)
    await insert_content_item_engagement_row(
        db_session, content_item_id=content_item_id, system_user_id=system_user_record.id
    )

    await content_engagement_service.add_engagement(content_item_id, 1, 0)

    engagement_record = await _select_engagement(db_session, content_item_id)
    assert engagement_record.view_count == 1
    assert engagement_record.feed_score is None


async def test_rescore_engagement_uses_current_published_at(
    db_session: AsyncSession,
) -> None:
    content_engagement_service = ContentEngagementService(
        db_session=db_session,
        content_engagement_settings=build_content_engagement_settings(),
    )
    system_user_record = await find_system_user_row(db_session)
    user_record = await insert_user_row(db_session)
    persona_record = await insert_persona_row(db_session, created_by_id=user_record.id)
    content_item_record = await insert_content_item_row(
        db_session,
        created_by_id=user_record.id,
        persona_id=persona_record.id,
        published_at=datetime(2026, 1, 2, tzinfo=UTC),
    )
    await insert_content_item_engagement_row(
        db_session,
        content_item_id=content_item_record.id,
        system_user_id=system_user_record.id,
        feed_score=99.0,
    )
    content_item_record.published_at = datetime(2026, 1, 3, tzinfo=UTC)
    await db_session.flush()

    await content_engagement_service.rescore_engagement(content_item_record.id)

    engagement_record = await _select_engagement(db_session, content_item_record.id)
    assert engagement_record.feed_score == pytest.approx(2.0)
    assert engagement_record.updated_by_id == system_user_record.id


async def test_rescore_engagement_leaves_other_rows_untouched(
    db_session: AsyncSession, content_engagement_service: ContentEngagementService
) -> None:
    system_user_record = await find_system_user_row(db_session)
    content_item_id = await _insert_content_item_id(
        db_session, published_at=datetime(2026, 1, 2, tzinfo=UTC)
    )
    other_content_item_id = await _insert_content_item_id(
        db_session, published_at=datetime(2026, 1, 2, tzinfo=UTC)
    )
    for item_id in (content_item_id, other_content_item_id):
        await insert_content_item_engagement_row(
            db_session,
            content_item_id=item_id,
            system_user_id=system_user_record.id,
            feed_score=99.0,
        )

    await content_engagement_service.rescore_engagement(content_item_id)

    other_engagement_record = await _select_engagement(db_session, other_content_item_id)
    assert other_engagement_record.feed_score == pytest.approx(99.0)


async def test_rescore_all_engagement_rescores_every_row_and_returns_count(
    db_session: AsyncSession, content_engagement_service: ContentEngagementService
) -> None:
    system_user_record = await find_system_user_row(db_session)
    first_content_item_id = await _insert_content_item_id(
        db_session, published_at=datetime(2026, 1, 2, tzinfo=UTC)
    )
    second_content_item_id = await _insert_content_item_id(
        db_session, published_at=datetime(2026, 1, 3, tzinfo=UTC)
    )
    for item_id in (first_content_item_id, second_content_item_id):
        await insert_content_item_engagement_row(
            db_session,
            content_item_id=item_id,
            system_user_id=system_user_record.id,
            feed_score=99.0,
        )

    rescored_count = await content_engagement_service.rescore_all_engagement()

    first_engagement_record = await _select_engagement(db_session, first_content_item_id)
    second_engagement_record = await _select_engagement(db_session, second_content_item_id)
    assert rescored_count == 2
    assert first_engagement_record.feed_score == pytest.approx(1.0)
    assert second_engagement_record.feed_score == pytest.approx(2.0)
