from unittest.mock import ANY
from uuid import UUID, uuid4

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from libs.database.orm import (
    ContentItemEngagementOrm,
    ContentItemOrm,
    ContentItemViewOrm,
    UserOrm,
)
from tests.factories.blog_posts import VALID_BLOG_POST_BODY


async def _create_blog_post_content_item(
    user_client: AsyncClient,
    *,
    is_persona_public: bool = True,
    is_public: bool = True,
    published_at: str | None = None,
) -> str:
    create_persona_response = await user_client.post(
        "/personas",
        json={"name": "Public Persona", "bio": "Writes essays.", "is_public": is_persona_public},
    )
    create_blog_post_response = await user_client.post(
        "/blog-posts",
        json={
            "persona_identity": create_persona_response.json()["identity"],
            "title": "Public Post",
            "body": VALID_BLOG_POST_BODY,
            "is_public": is_public,
            "published_at": published_at,
        },
    )
    blog_post_identity = create_blog_post_response.json()["identity"]
    find_blog_post_response = await user_client.get(f"/blog-posts/{blog_post_identity}")
    return find_blog_post_response.json()["content_item_identity"]


async def _find_view_rows(
    db_session: AsyncSession, content_item_identity: str
) -> list[tuple[int, str | None, int | None]]:
    view_query = (
        select(
            ContentItemViewOrm.read_percent,
            ContentItemViewOrm.anonymous_user_key,
            ContentItemViewOrm.created_by_id,
        )
        .join(ContentItemOrm, ContentItemOrm.id == ContentItemViewOrm.content_item_id)
        .where(ContentItemOrm.identity == UUID(content_item_identity))
        .order_by(ContentItemViewOrm.id)
    )
    view_query_result = await db_session.execute(view_query)
    return [tuple(view_row) for view_row in view_query_result]


async def _find_engagement_row(
    db_session: AsyncSession, content_item_identity: str
) -> tuple[int, int]:
    engagement_query = (
        select(ContentItemEngagementOrm.view_count, ContentItemEngagementOrm.read_percent_sum)
        .join(ContentItemOrm, ContentItemOrm.id == ContentItemEngagementOrm.content_item_id)
        .where(ContentItemOrm.identity == UUID(content_item_identity))
    )
    engagement_query_result = await db_session.execute(engagement_query)
    return tuple(engagement_query_result.one())


async def test_record_content_item_view_signed_out_returns_200_and_records_view_and_engagement(
    api_client: AsyncClient, other_user_client: AsyncClient, db_session: AsyncSession
) -> None:
    other_content_item_identity = await _create_blog_post_content_item(
        other_user_client, published_at="2020-01-01T00:00:00+00:00"
    )

    record_content_item_view_response = await api_client.put(
        f"/content-items/{other_content_item_identity}/view", json={"read_percent": 50}
    )

    view_rows = await _find_view_rows(db_session, other_content_item_identity)
    engagement_row = await _find_engagement_row(db_session, other_content_item_identity)
    assert record_content_item_view_response.status_code == 200
    assert record_content_item_view_response.json() == {}
    assert view_rows == [(50, ANY, None)]
    assert len(view_rows[0][1]) == 64
    assert engagement_row == (1, 50)


async def test_record_content_item_view_signed_in_as_another_user_returns_200_and_records_view(
    api_client: AsyncClient,
    signed_in_user: UserOrm,
    other_user_client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    other_content_item_identity = await _create_blog_post_content_item(
        other_user_client, published_at="2020-01-01T00:00:00+00:00"
    )

    record_content_item_view_response = await api_client.put(
        f"/content-items/{other_content_item_identity}/view", json={"read_percent": 25}
    )

    view_rows = await _find_view_rows(db_session, other_content_item_identity)
    engagement_row = await _find_engagement_row(db_session, other_content_item_identity)
    assert record_content_item_view_response.status_code == 200
    assert record_content_item_view_response.json() == {}
    assert view_rows == [(25, None, signed_in_user.id)]
    assert engagement_row == (1, 25)


async def test_record_content_item_view_creator_returns_200_and_records_nothing(
    api_client: AsyncClient, signed_in_user: UserOrm, db_session: AsyncSession
) -> None:
    own_content_item_identity = await _create_blog_post_content_item(
        api_client, published_at="2020-01-01T00:00:00+00:00"
    )

    record_content_item_view_response = await api_client.put(
        f"/content-items/{own_content_item_identity}/view", json={"read_percent": 100}
    )

    view_rows = await _find_view_rows(db_session, own_content_item_identity)
    engagement_row = await _find_engagement_row(db_session, own_content_item_identity)
    assert record_content_item_view_response.status_code == 200
    assert record_content_item_view_response.json() == {}
    assert view_rows == []
    assert engagement_row == (0, 0)


@pytest.mark.parametrize(
    ("is_persona_public", "is_public", "published_at"),
    [
        pytest.param(True, False, "2020-01-01T00:00:00+00:00", id="private_content_item"),
        pytest.param(True, True, None, id="draft"),
    ],
)
async def test_record_content_item_view_hidden_signed_out_returns_404_and_records_nothing(
    api_client: AsyncClient,
    other_user_client: AsyncClient,
    db_session: AsyncSession,
    is_persona_public: bool,
    is_public: bool,
    published_at: str | None,
) -> None:
    other_content_item_identity = await _create_blog_post_content_item(
        other_user_client,
        is_persona_public=is_persona_public,
        is_public=is_public,
        published_at=published_at,
    )

    record_content_item_view_response = await api_client.put(
        f"/content-items/{other_content_item_identity}/view", json={"read_percent": 50}
    )

    view_rows = await _find_view_rows(db_session, other_content_item_identity)
    assert record_content_item_view_response.status_code == 404
    assert view_rows == []


async def test_record_content_item_view_never_inserted_returns_404(api_client: AsyncClient) -> None:
    record_content_item_view_response = await api_client.put(
        f"/content-items/{uuid4()}/view", json={"read_percent": 50}
    )

    assert record_content_item_view_response.status_code == 404


@pytest.mark.parametrize(
    ("request_body", "expected_error_location"),
    [
        pytest.param({}, ["body", "read_percent"], id="missing_read_percent"),
        pytest.param({"read_percent": 30}, ["body", "read_percent"], id="read_percent_not_allowed"),
    ],
)
async def test_record_content_item_view_invalid_body_returns_422(
    api_client: AsyncClient,
    request_body: dict[str, int],
    expected_error_location: list[str],
) -> None:
    record_content_item_view_response = await api_client.put(
        f"/content-items/{uuid4()}/view", json=request_body
    )

    response_body = record_content_item_view_response.json()
    assert record_content_item_view_response.status_code == 422
    assert response_body["detail"][0]["loc"] == expected_error_location


async def test_record_content_item_view_no_body_returns_422(api_client: AsyncClient) -> None:
    record_content_item_view_response = await api_client.put(f"/content-items/{uuid4()}/view")

    response_body = record_content_item_view_response.json()
    assert record_content_item_view_response.status_code == 422
    assert response_body["detail"][0]["loc"] == ["body"]


async def test_record_content_item_view_malformed_identity_returns_422(
    api_client: AsyncClient,
) -> None:
    record_content_item_view_response = await api_client.put(
        "/content-items/not-a-uuid/view", json={"read_percent": 50}
    )

    response_body = record_content_item_view_response.json()
    assert record_content_item_view_response.status_code == 422
    assert response_body["detail"][0]["loc"] == ["path", "content_item_identity"]


async def test_record_content_item_view_invalid_session_returns_401(
    api_client: AsyncClient,
) -> None:
    api_client.cookies.set("sid", "not-a-real-session-id")

    record_content_item_view_response = await api_client.put(
        f"/content-items/{uuid4()}/view", json={"read_percent": 50}
    )

    assert record_content_item_view_response.status_code == 401


async def test_record_content_item_view_openapi_limits_read_percent_to_five_values(
    api_client: AsyncClient,
) -> None:
    openapi_response = await api_client.get("/openapi.json")

    read_percent_schema = openapi_response.json()["components"]["schemas"][
        "RecordContentItemViewDto"
    ]["properties"]["read_percent"]
    assert read_percent_schema == {
        "type": "integer",
        "enum": [0, 25, 50, 75, 100],
        "title": "Read Percent",
    }


async def test_record_content_item_view_different_user_agents_create_two_view_rows(
    api_client: AsyncClient, other_user_client: AsyncClient, db_session: AsyncSession
) -> None:
    other_content_item_identity = await _create_blog_post_content_item(
        other_user_client, published_at="2020-01-01T00:00:00+00:00"
    )

    await api_client.put(
        f"/content-items/{other_content_item_identity}/view",
        json={"read_percent": 50},
        headers={"User-Agent": "Firefox/130.0"},
    )
    await api_client.put(
        f"/content-items/{other_content_item_identity}/view",
        json={"read_percent": 50},
        headers={"User-Agent": "Chrome/129.0"},
    )

    view_rows = await _find_view_rows(db_session, other_content_item_identity)
    engagement_row = await _find_engagement_row(db_session, other_content_item_identity)
    assert [view_row[0] for view_row in view_rows] == [50, 50]
    assert view_rows[0][1] != view_rows[1][1]
    assert engagement_row == (2, 100)


async def test_record_content_item_view_same_user_agent_raising_read_percent_updates_one_row(
    api_client: AsyncClient, other_user_client: AsyncClient, db_session: AsyncSession
) -> None:
    other_content_item_identity = await _create_blog_post_content_item(
        other_user_client, published_at="2020-01-01T00:00:00+00:00"
    )
    await api_client.put(
        f"/content-items/{other_content_item_identity}/view",
        json={"read_percent": 50},
        headers={"User-Agent": "Firefox/130.0"},
    )

    await api_client.put(
        f"/content-items/{other_content_item_identity}/view",
        json={"read_percent": 100},
        headers={"User-Agent": "Firefox/130.0"},
    )

    view_rows = await _find_view_rows(db_session, other_content_item_identity)
    engagement_row = await _find_engagement_row(db_session, other_content_item_identity)
    assert view_rows == [(100, ANY, None)]
    assert engagement_row == (1, 100)
