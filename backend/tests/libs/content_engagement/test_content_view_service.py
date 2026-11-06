from datetime import UTC, date, datetime

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from libs.auth.results import AuthUser
from libs.content_engagement.inputs import RecordContentViewInput
from libs.content_engagement.services import ContentEngagementService, ContentViewService
from libs.database.orm import ContentItemEngagementOrm, ContentItemViewOrm
from tests.factories.auth import build_auth_user
from tests.factories.content_engagement import (
    insert_content_item_engagement_row,
    insert_signed_in_content_item_view_row,
    insert_signed_out_content_item_view_row,
)
from tests.factories.content_items import insert_content_item_row
from tests.factories.database import fetch_database_utc_now
from tests.factories.personas import insert_persona_row
from tests.factories.users import find_system_user_row, insert_user_row


@pytest.fixture
def content_view_service(
    db_session: AsyncSession, content_engagement_service: ContentEngagementService
) -> ContentViewService:
    return ContentViewService(
        db_session=db_session, content_engagement_service=content_engagement_service
    )


async def _insert_engaged_content_item_id(db_session: AsyncSession) -> int:
    system_user_record = await find_system_user_row(db_session)
    author_record = await insert_user_row(db_session)
    persona_record = await insert_persona_row(db_session, created_by_id=author_record.id)
    content_item_record = await insert_content_item_row(
        db_session,
        created_by_id=author_record.id,
        persona_id=persona_record.id,
        published_at=datetime(2026, 1, 2, tzinfo=UTC),
    )
    await insert_content_item_engagement_row(
        db_session,
        content_item_id=content_item_record.id,
        system_user_id=system_user_record.id,
        feed_score=1.0,
    )
    return content_item_record.id


async def _insert_auth_user(db_session: AsyncSession) -> AuthUser:
    user_record = await insert_user_row(db_session)
    return build_auth_user(user_id=user_record.id, user_identity=user_record.identity)


async def _select_view_records(
    db_session: AsyncSession, content_item_id: int
) -> list[ContentItemViewOrm]:
    view_query = (
        select(ContentItemViewOrm)
        .where(ContentItemViewOrm.content_item_id == content_item_id)
        .order_by(ContentItemViewOrm.id)
        .execution_options(populate_existing=True)
    )
    return list((await db_session.scalars(view_query)).all())


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


def _build_record_content_view_input(
    content_item_id: int, *, read_percent: int, anonymous_user_key: str | None = None
) -> RecordContentViewInput:
    return RecordContentViewInput(
        content_item_id=content_item_id,
        read_percent=read_percent,
        anonymous_user_key=anonymous_user_key,
    )


async def test_record_content_view_signed_in_creates_row_and_adds_engagement(
    db_session: AsyncSession, content_view_service: ContentViewService
) -> None:
    content_item_id = await _insert_engaged_content_item_id(db_session)
    auth_user = await _insert_auth_user(db_session)
    database_utc_now = await fetch_database_utc_now(db_session)

    await content_view_service.record_content_view(
        _build_record_content_view_input(content_item_id, read_percent=50), auth_user
    )

    view_records = await _select_view_records(db_session, content_item_id)
    engagement_record = await _select_engagement(db_session, content_item_id)
    assert len(view_records) == 1
    assert view_records[0].created_by_id == auth_user.id
    assert view_records[0].updated_by_id == auth_user.id
    assert view_records[0].anonymous_user_key is None
    assert view_records[0].read_percent == 50
    assert view_records[0].viewed_on == database_utc_now.date()
    assert engagement_record.view_count == 1
    assert engagement_record.read_percent_sum == 50


async def test_record_content_view_signed_out_creates_row_and_adds_engagement(
    db_session: AsyncSession, content_view_service: ContentViewService
) -> None:
    content_item_id = await _insert_engaged_content_item_id(db_session)
    database_utc_now = await fetch_database_utc_now(db_session)

    await content_view_service.record_content_view(
        _build_record_content_view_input(
            content_item_id, read_percent=50, anonymous_user_key="visitor-a"
        ),
        None,
    )

    view_records = await _select_view_records(db_session, content_item_id)
    engagement_record = await _select_engagement(db_session, content_item_id)
    assert len(view_records) == 1
    assert view_records[0].anonymous_user_key == "visitor-a"
    assert view_records[0].created_by_id is None
    assert view_records[0].updated_by_id is None
    assert view_records[0].read_percent == 50
    assert view_records[0].viewed_on == database_utc_now.date()
    assert engagement_record.view_count == 1
    assert engagement_record.read_percent_sum == 50


async def test_record_content_view_signed_in_higher_percent_raises_existing_row(
    db_session: AsyncSession, content_view_service: ContentViewService
) -> None:
    content_item_id = await _insert_engaged_content_item_id(db_session)
    auth_user = await _insert_auth_user(db_session)
    database_utc_now = await fetch_database_utc_now(db_session)
    view_record = await insert_signed_in_content_item_view_row(
        db_session, content_item_id=content_item_id, created_by_id=auth_user.id, read_percent=25
    )
    view_record.updated_at = datetime(2026, 1, 2, tzinfo=UTC)
    await db_session.flush()
    engagement_record = await _select_engagement(db_session, content_item_id)
    engagement_record.view_count = 1
    engagement_record.read_percent_sum = 25
    await db_session.flush()

    await content_view_service.record_content_view(
        _build_record_content_view_input(content_item_id, read_percent=75), auth_user
    )

    view_records = await _select_view_records(db_session, content_item_id)
    engagement_record = await _select_engagement(db_session, content_item_id)
    assert len(view_records) == 1
    assert view_records[0].read_percent == 75
    assert view_records[0].updated_at == database_utc_now
    assert engagement_record.view_count == 1
    assert engagement_record.read_percent_sum == 75


async def test_record_content_view_signed_out_higher_percent_raises_existing_row(
    db_session: AsyncSession, content_view_service: ContentViewService
) -> None:
    content_item_id = await _insert_engaged_content_item_id(db_session)
    await insert_signed_out_content_item_view_row(
        db_session, content_item_id=content_item_id, anonymous_user_key="visitor-a", read_percent=25
    )
    engagement_record = await _select_engagement(db_session, content_item_id)
    engagement_record.view_count = 1
    engagement_record.read_percent_sum = 25
    await db_session.flush()

    await content_view_service.record_content_view(
        _build_record_content_view_input(
            content_item_id, read_percent=75, anonymous_user_key="visitor-a"
        ),
        None,
    )

    view_records = await _select_view_records(db_session, content_item_id)
    engagement_record = await _select_engagement(db_session, content_item_id)
    assert len(view_records) == 1
    assert view_records[0].read_percent == 75
    assert engagement_record.view_count == 1
    assert engagement_record.read_percent_sum == 75


@pytest.mark.parametrize(
    "new_read_percent", [pytest.param(75, id="same"), pytest.param(50, id="lower")]
)
async def test_record_content_view_not_higher_percent_changes_nothing(
    db_session: AsyncSession, content_view_service: ContentViewService, new_read_percent: int
) -> None:
    content_item_id = await _insert_engaged_content_item_id(db_session)
    auth_user = await _insert_auth_user(db_session)
    view_record = await insert_signed_in_content_item_view_row(
        db_session, content_item_id=content_item_id, created_by_id=auth_user.id, read_percent=75
    )
    view_record.updated_at = datetime(2026, 1, 2, tzinfo=UTC)
    engagement_record = await _select_engagement(db_session, content_item_id)
    engagement_record.view_count = 1
    engagement_record.read_percent_sum = 75
    engagement_record.feed_score = 5.0
    await db_session.flush()

    await content_view_service.record_content_view(
        _build_record_content_view_input(content_item_id, read_percent=new_read_percent),
        auth_user,
    )

    view_records = await _select_view_records(db_session, content_item_id)
    engagement_record = await _select_engagement(db_session, content_item_id)
    assert len(view_records) == 1
    assert view_records[0].read_percent == 75
    assert view_records[0].updated_at == datetime(2026, 1, 2, tzinfo=UTC)
    assert engagement_record.view_count == 1
    assert engagement_record.read_percent_sum == 75
    assert engagement_record.feed_score == pytest.approx(5.0)


async def test_record_content_view_signed_in_different_day_creates_new_row(
    db_session: AsyncSession, content_view_service: ContentViewService
) -> None:
    content_item_id = await _insert_engaged_content_item_id(db_session)
    auth_user = await _insert_auth_user(db_session)
    await insert_signed_in_content_item_view_row(
        db_session,
        content_item_id=content_item_id,
        created_by_id=auth_user.id,
        read_percent=50,
        viewed_on=date(2026, 1, 2),
    )
    engagement_record = await _select_engagement(db_session, content_item_id)
    engagement_record.view_count = 1
    engagement_record.read_percent_sum = 50
    await db_session.flush()

    await content_view_service.record_content_view(
        _build_record_content_view_input(content_item_id, read_percent=25), auth_user
    )

    view_records = await _select_view_records(db_session, content_item_id)
    engagement_record = await _select_engagement(db_session, content_item_id)
    assert [view_record.read_percent for view_record in view_records] == [50, 25]
    assert engagement_record.view_count == 2
    assert engagement_record.read_percent_sum == 75


async def test_record_content_view_two_signed_out_keys_create_two_rows(
    db_session: AsyncSession, content_view_service: ContentViewService
) -> None:
    content_item_id = await _insert_engaged_content_item_id(db_session)
    await content_view_service.record_content_view(
        _build_record_content_view_input(
            content_item_id, read_percent=25, anonymous_user_key="visitor-a"
        ),
        None,
    )

    await content_view_service.record_content_view(
        _build_record_content_view_input(
            content_item_id, read_percent=50, anonymous_user_key="visitor-b"
        ),
        None,
    )

    view_records = await _select_view_records(db_session, content_item_id)
    engagement_record = await _select_engagement(db_session, content_item_id)
    assert [view_record.anonymous_user_key for view_record in view_records] == [
        "visitor-a",
        "visitor-b",
    ]
    assert engagement_record.view_count == 2
    assert engagement_record.read_percent_sum == 75


async def test_record_content_view_signed_in_and_signed_out_same_day_create_two_rows(
    db_session: AsyncSession, content_view_service: ContentViewService
) -> None:
    content_item_id = await _insert_engaged_content_item_id(db_session)
    auth_user = await _insert_auth_user(db_session)
    await insert_signed_out_content_item_view_row(
        db_session, content_item_id=content_item_id, anonymous_user_key="visitor-a", read_percent=25
    )

    await content_view_service.record_content_view(
        _build_record_content_view_input(content_item_id, read_percent=50), auth_user
    )

    view_records = await _select_view_records(db_session, content_item_id)
    assert [view_record.created_by_id for view_record in view_records] == [None, auth_user.id]


async def test_record_content_view_no_user_and_no_key_raises_value_error(
    db_session: AsyncSession, content_view_service: ContentViewService
) -> None:
    content_item_id = await _insert_engaged_content_item_id(db_session)

    with pytest.raises(ValueError):
        await content_view_service.record_content_view(
            _build_record_content_view_input(content_item_id, read_percent=25), None
        )

    assert await _select_view_records(db_session, content_item_id) == []


async def test_record_content_view_raises_feed_score(
    db_session: AsyncSession, content_view_service: ContentViewService
) -> None:
    content_item_id = await _insert_engaged_content_item_id(db_session)
    auth_user = await _insert_auth_user(db_session)

    await content_view_service.record_content_view(
        _build_record_content_view_input(content_item_id, read_percent=100), auth_user
    )

    # 1 view and 100 read percent make 1 + 3 + 1 = 5 units, and log10(5) is 0.69897
    engagement_record = await _select_engagement(db_session, content_item_id)
    assert engagement_record.feed_score == pytest.approx(1.69897)
