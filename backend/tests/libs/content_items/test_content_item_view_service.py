from datetime import UTC, datetime
from uuid import UUID

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from libs.content_engagement.services import ContentEngagementService, ContentViewService
from libs.content_items.inputs import RecordContentItemViewInput
from libs.content_items.services import ContentItemViewService
from libs.core.exceptions import NotFoundException
from libs.database.orm import (
    ContentItemEngagementOrm,
    ContentItemOrm,
    ContentItemViewOrm,
    UserOrm,
)
from tests.factories.auth import build_auth_user
from tests.factories.content_engagement import insert_content_item_engagement_row
from tests.factories.content_items import insert_content_item_row
from tests.factories.personas import insert_persona_row
from tests.factories.users import find_system_user_row, insert_user_row

PUBLISHED_AT = datetime(2020, 1, 2, 3, 4, 5, tzinfo=UTC)
DELETED_AT = datetime(2021, 1, 2, 3, 4, 5, tzinfo=UTC)
UUID_NEVER_INSERTED = UUID("00000000-0000-4000-8000-000000000001")


def _build_content_item_view_service(
    db_session: AsyncSession, content_engagement_service: ContentEngagementService
) -> ContentItemViewService:
    content_view_service = ContentViewService(
        db_session=db_session, content_engagement_service=content_engagement_service
    )
    return ContentItemViewService(db_session=db_session, content_view_service=content_view_service)


async def _insert_content_item_with_engagement(
    db_session: AsyncSession,
    creator_record: UserOrm,
    *,
    is_persona_public: bool = True,
    is_public: bool = True,
    published_at: datetime | None = PUBLISHED_AT,
    deleted_at: datetime | None = None,
) -> ContentItemOrm:
    system_user_record = await find_system_user_row(db_session)
    persona_record = await insert_persona_row(
        db_session, created_by_id=creator_record.id, is_public=is_persona_public
    )
    content_item_record = await insert_content_item_row(
        db_session,
        created_by_id=creator_record.id,
        persona_id=persona_record.id,
        is_public=is_public,
        published_at=published_at,
        deleted_at=deleted_at,
        deleted_by_id=creator_record.id if deleted_at is not None else None,
    )
    await insert_content_item_engagement_row(
        db_session, content_item_id=content_item_record.id, system_user_id=system_user_record.id
    )
    return content_item_record


async def test_record_content_item_view_signed_out_records_view_and_engagement(
    db_session: AsyncSession, content_engagement_service: ContentEngagementService
) -> None:
    creator_record = await insert_user_row(db_session)
    content_item_record = await _insert_content_item_with_engagement(db_session, creator_record)
    content_item_view_service = _build_content_item_view_service(
        db_session, content_engagement_service
    )

    await content_item_view_service.record_content_item_view(
        content_item_record.identity,
        RecordContentItemViewInput(read_percent=50),
        "visitor-key",
        None,
    )

    view_query = select(
        ContentItemViewOrm.read_percent,
        ContentItemViewOrm.anonymous_user_key,
        ContentItemViewOrm.created_by_id,
    ).where(ContentItemViewOrm.content_item_id == content_item_record.id)
    engagement_query = select(
        ContentItemEngagementOrm.view_count, ContentItemEngagementOrm.read_percent_sum
    ).where(ContentItemEngagementOrm.content_item_id == content_item_record.id)
    view_query_result = await db_session.execute(view_query)
    engagement_query_result = await db_session.execute(engagement_query)
    assert [tuple(view_row) for view_row in view_query_result] == [(50, "visitor-key", None)]
    assert [tuple(engagement_row) for engagement_row in engagement_query_result] == [(1, 50)]


async def test_record_content_item_view_other_signed_in_user_records_view_and_engagement(
    db_session: AsyncSession, content_engagement_service: ContentEngagementService
) -> None:
    creator_record = await insert_user_row(db_session)
    reader_record = await insert_user_row(db_session)
    content_item_record = await _insert_content_item_with_engagement(db_session, creator_record)
    reader_auth_user = build_auth_user(
        user_id=reader_record.id, user_identity=reader_record.identity
    )
    content_item_view_service = _build_content_item_view_service(
        db_session, content_engagement_service
    )

    await content_item_view_service.record_content_item_view(
        content_item_record.identity,
        RecordContentItemViewInput(read_percent=75),
        None,
        reader_auth_user,
    )

    view_query = select(
        ContentItemViewOrm.read_percent,
        ContentItemViewOrm.anonymous_user_key,
        ContentItemViewOrm.created_by_id,
    ).where(ContentItemViewOrm.content_item_id == content_item_record.id)
    engagement_query = select(
        ContentItemEngagementOrm.view_count, ContentItemEngagementOrm.read_percent_sum
    ).where(ContentItemEngagementOrm.content_item_id == content_item_record.id)
    view_query_result = await db_session.execute(view_query)
    engagement_query_result = await db_session.execute(engagement_query)
    assert [tuple(view_row) for view_row in view_query_result] == [(75, None, reader_record.id)]
    assert [tuple(engagement_row) for engagement_row in engagement_query_result] == [(1, 75)]


async def test_record_content_item_view_creator_records_nothing(
    db_session: AsyncSession, content_engagement_service: ContentEngagementService
) -> None:
    creator_record = await insert_user_row(db_session)
    content_item_record = await _insert_content_item_with_engagement(db_session, creator_record)
    creator_auth_user = build_auth_user(
        user_id=creator_record.id, user_identity=creator_record.identity
    )
    content_item_view_service = _build_content_item_view_service(
        db_session, content_engagement_service
    )

    await content_item_view_service.record_content_item_view(
        content_item_record.identity,
        RecordContentItemViewInput(read_percent=100),
        None,
        creator_auth_user,
    )

    view_query = select(ContentItemViewOrm.id).where(
        ContentItemViewOrm.content_item_id == content_item_record.id
    )
    engagement_query = select(
        ContentItemEngagementOrm.view_count, ContentItemEngagementOrm.read_percent_sum
    ).where(ContentItemEngagementOrm.content_item_id == content_item_record.id)
    view_query_result = await db_session.execute(view_query)
    engagement_query_result = await db_session.execute(engagement_query)
    assert view_query_result.all() == []
    assert [tuple(engagement_row) for engagement_row in engagement_query_result] == [(0, 0)]


@pytest.mark.parametrize(
    ("is_persona_public", "is_public", "published_at", "deleted_at"),
    [
        pytest.param(True, True, None, None, id="draft"),
        pytest.param(True, False, PUBLISHED_AT, None, id="private_content_item"),
        pytest.param(False, True, PUBLISHED_AT, None, id="content_item_under_private_persona"),
        pytest.param(True, True, PUBLISHED_AT, DELETED_AT, id="soft_deleted_content_item"),
    ],
)
async def test_record_content_item_view_hidden_content_item_signed_out_raises_not_found(
    db_session: AsyncSession,
    content_engagement_service: ContentEngagementService,
    is_persona_public: bool,
    is_public: bool,
    published_at: datetime | None,
    deleted_at: datetime | None,
) -> None:
    creator_record = await insert_user_row(db_session)
    content_item_record = await _insert_content_item_with_engagement(
        db_session,
        creator_record,
        is_persona_public=is_persona_public,
        is_public=is_public,
        published_at=published_at,
        deleted_at=deleted_at,
    )
    content_item_view_service = _build_content_item_view_service(
        db_session, content_engagement_service
    )

    with pytest.raises(NotFoundException):
        await content_item_view_service.record_content_item_view(
            content_item_record.identity,
            RecordContentItemViewInput(read_percent=50),
            "visitor-key",
            None,
        )

    view_query = select(ContentItemViewOrm.id).where(
        ContentItemViewOrm.content_item_id == content_item_record.id
    )
    view_query_result = await db_session.execute(view_query)
    assert view_query_result.all() == []


async def test_record_content_item_view_unknown_identity_raises_not_found(
    db_session: AsyncSession, content_engagement_service: ContentEngagementService
) -> None:
    content_item_view_service = _build_content_item_view_service(
        db_session, content_engagement_service
    )

    with pytest.raises(NotFoundException):
        await content_item_view_service.record_content_item_view(
            UUID_NEVER_INSERTED, RecordContentItemViewInput(read_percent=50), "visitor-key", None
        )


async def test_record_content_item_view_other_users_draft_raises_not_found(
    db_session: AsyncSession, content_engagement_service: ContentEngagementService
) -> None:
    creator_record = await insert_user_row(db_session)
    reader_record = await insert_user_row(db_session)
    content_item_record = await _insert_content_item_with_engagement(
        db_session, creator_record, published_at=None
    )
    reader_auth_user = build_auth_user(
        user_id=reader_record.id, user_identity=reader_record.identity
    )
    content_item_view_service = _build_content_item_view_service(
        db_session, content_engagement_service
    )

    with pytest.raises(NotFoundException):
        await content_item_view_service.record_content_item_view(
            content_item_record.identity,
            RecordContentItemViewInput(read_percent=50),
            None,
            reader_auth_user,
        )

    view_query = select(ContentItemViewOrm.id).where(
        ContentItemViewOrm.content_item_id == content_item_record.id
    )
    view_query_result = await db_session.execute(view_query)
    assert view_query_result.all() == []
