from datetime import UTC, datetime
from unittest.mock import ANY
from uuid import UUID, uuid4

import pytest
from httpx import AsyncClient
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from libs.core.services import BackgroundJobService
from libs.database.orm import (
    BlogPostOrm,
    ContentItemOrm,
    GenerateTextRunOrm,
    UserOrm,
)
from libs.generate_text.types import GenerateTextRunStatusType, GenerateTextStepStatusType
from tests.factories.blog_posts import VALID_BLOG_POST_BODY, insert_blog_post_row
from tests.factories.content_engagement import insert_content_item_engagement_row
from tests.factories.content_items import insert_content_item_row
from tests.factories.generate_text import (
    insert_generate_text_run_row,
    insert_generate_text_step_row,
)
from tests.factories.llm import build_llm_completion_result
from tests.factories.personas import insert_persona_row
from tests.factories.users import find_system_user_row
from tests.stubs.llm import LlmServiceStub

DRAIN_TIMEOUT_SECONDS = 30
VALID_GENERATE_TEXT_RUN_OUTPUT = (
    "# The Title\n*A subtitle.*\n\nA paragraph.\n\n## A Section\n\nMore text."
)


async def _create_completed_run(
    api_client: AsyncClient,
    llm_service_stub: LlmServiceStub,
    background_job_service: BackgroundJobService,
    persona_identity: str,
    *,
    content: str = VALID_GENERATE_TEXT_RUN_OUTPUT,
) -> str:
    llm_service_stub.complete_result = build_llm_completion_result(content=content)
    generate_blog_post_response = await api_client.post(
        "/generate-text/blog-post",
        json={
            "prompt_text": "Write about coffee.",
            "persona_identity": persona_identity,
            "options": {},
        },
    )
    await background_job_service.drain(DRAIN_TIMEOUT_SECONDS)
    return generate_blog_post_response.json()["run_identity"]


async def test_create_blog_post_returns_identity_and_persists_rows(
    api_client: AsyncClient, signed_in_user: UserOrm, db_session: AsyncSession
) -> None:
    persona_record = await insert_persona_row(db_session, created_by_id=signed_in_user.id)
    await db_session.commit()

    create_blog_post_response = await api_client.post(
        "/blog-posts",
        json={
            "persona_identity": str(persona_record.identity),
            "title": "Why Slow Mornings Make Better Writers",
            "subtitle": "A short note on mornings",
            "body": VALID_BLOG_POST_BODY,
            "is_public": False,
        },
    )

    response_body = create_blog_post_response.json()
    blog_post_query = select(BlogPostOrm).where(BlogPostOrm.identity == response_body["identity"])
    blog_post_record = await db_session.scalar(blog_post_query)
    content_item_query = select(ContentItemOrm).where(
        ContentItemOrm.id == blog_post_record.content_item_id
    )
    content_item_record = await db_session.scalar(content_item_query)
    assert create_blog_post_response.status_code == 201
    assert response_body == {"identity": str(blog_post_record.identity)}
    assert blog_post_record.title == "Why Slow Mornings Make Better Writers"
    assert blog_post_record.subtitle == "A short note on mornings"
    assert blog_post_record.body == VALID_BLOG_POST_BODY
    assert blog_post_record.created_by_id == signed_in_user.id
    assert blog_post_record.updated_by_id == signed_in_user.id
    assert content_item_record.persona_id == persona_record.id
    assert content_item_record.is_public is False
    assert content_item_record.published_at is None
    assert content_item_record.created_by_id == signed_in_user.id


@pytest.mark.parametrize(
    ("request_body", "expected_error_location"),
    [
        pytest.param(
            {"title": "A Title", "body": VALID_BLOG_POST_BODY},
            ["body", "persona_identity"],
            id="missing_persona_identity",
        ),
        pytest.param(
            {"persona_identity": str(uuid4()), "body": VALID_BLOG_POST_BODY},
            ["body", "title"],
            id="missing_title",
        ),
        pytest.param(
            {"persona_identity": str(uuid4()), "title": "A Title"},
            ["body", "body"],
            id="missing_body",
        ),
    ],
)
async def test_create_blog_post_missing_required_field_returns_422(
    api_client: AsyncClient,
    signed_in_user: UserOrm,
    request_body: dict[str, str],
    expected_error_location: list[str],
) -> None:
    create_blog_post_response = await api_client.post("/blog-posts", json=request_body)

    response_body = create_blog_post_response.json()
    assert create_blog_post_response.status_code == 422
    assert response_body["detail"][0]["loc"] == expected_error_location


@pytest.mark.usefixtures("signed_in_user")
async def test_create_blog_post_malformed_persona_identity_returns_422(
    api_client: AsyncClient,
) -> None:
    create_blog_post_response = await api_client.post(
        "/blog-posts",
        json={"persona_identity": "not-a-uuid", "title": "A Title", "body": VALID_BLOG_POST_BODY},
    )

    response_body = create_blog_post_response.json()
    assert create_blog_post_response.status_code == 422
    assert response_body["detail"][0]["loc"] == ["body", "persona_identity"]


async def test_create_blog_post_another_users_persona_returns_404(
    api_client: AsyncClient,
    signed_in_user: UserOrm,
    other_user_client: AsyncClient,
) -> None:
    other_create_persona_response = await other_user_client.post(
        "/personas", json={"name": "Not Yours", "bio": "Writes essays."}
    )
    other_persona_identity = other_create_persona_response.json()["identity"]

    create_blog_post_response = await api_client.post(
        "/blog-posts",
        json={
            "persona_identity": other_persona_identity,
            "title": "A Title",
            "body": VALID_BLOG_POST_BODY,
        },
    )

    assert create_blog_post_response.status_code == 404


async def test_create_blog_post_naive_published_at_returns_422(
    api_client: AsyncClient, signed_in_user: UserOrm, db_session: AsyncSession
) -> None:
    persona_record = await insert_persona_row(db_session, created_by_id=signed_in_user.id)
    await db_session.commit()

    create_blog_post_response = await api_client.post(
        "/blog-posts",
        json={
            "persona_identity": str(persona_record.identity),
            "title": "A Title",
            "body": VALID_BLOG_POST_BODY,
            "published_at": "2026-01-01T00:00:00",
        },
    )

    response_body = create_blog_post_response.json()
    assert create_blog_post_response.status_code == 422
    assert response_body["detail"][0]["loc"] == ["body", "published_at"]


@pytest.mark.parametrize(
    "invalid_body",
    [
        pytest.param("# A Title\n\nA paragraph.", id="h1_heading"),
        pytest.param("#### A Deep Heading\n\nA paragraph.", id="heading_level_too_deep"),
        pytest.param("<div>Raw HTML</div>\n\nA paragraph.", id="raw_html"),
    ],
)
async def test_create_blog_post_invalid_body_returns_422(
    api_client: AsyncClient, signed_in_user: UserOrm, db_session: AsyncSession, invalid_body: str
) -> None:
    persona_record = await insert_persona_row(db_session, created_by_id=signed_in_user.id)
    await db_session.commit()

    create_blog_post_response = await api_client.post(
        "/blog-posts",
        json={
            "persona_identity": str(persona_record.identity),
            "title": "A Title",
            "body": invalid_body,
        },
    )

    response_body = create_blog_post_response.json()
    assert create_blog_post_response.status_code == 422
    assert response_body["detail"][0]["loc"] == ["body", "body"]


async def test_create_blog_post_is_public_on_private_persona_returns_422(
    api_client: AsyncClient, signed_in_user: UserOrm, db_session: AsyncSession
) -> None:
    persona_record = await insert_persona_row(
        db_session, created_by_id=signed_in_user.id, is_public=False
    )
    await db_session.commit()

    create_blog_post_response = await api_client.post(
        "/blog-posts",
        json={
            "persona_identity": str(persona_record.identity),
            "title": "A Title",
            "body": VALID_BLOG_POST_BODY,
            "is_public": True,
        },
    )

    assert create_blog_post_response.status_code == 422


async def test_create_blog_post_from_generate_text_run_returns_identity_and_persists_split(
    api_client: AsyncClient,
    signed_in_user: UserOrm,
    llm_service_stub: LlmServiceStub,
    db_session: AsyncSession,
    background_job_service: BackgroundJobService,
) -> None:
    create_persona_response = await api_client.post(
        "/personas", json={"name": "Marta Quill", "bio": "Writes about slow mornings."}
    )
    persona_identity = create_persona_response.json()["identity"]
    run_identity = await _create_completed_run(
        api_client, llm_service_stub, background_job_service, persona_identity
    )

    create_blog_post_response = await api_client.post(
        "/blog-posts/from-generate-text-run", json={"generate_text_run_identity": run_identity}
    )

    response_body = create_blog_post_response.json()
    blog_post_query = select(BlogPostOrm).where(
        BlogPostOrm.identity == UUID(response_body["identity"])
    )
    blog_post_record = await db_session.scalar(blog_post_query)
    run_query = select(GenerateTextRunOrm).where(GenerateTextRunOrm.identity == UUID(run_identity))
    run_record = await db_session.scalar(run_query)
    assert create_blog_post_response.status_code == 201
    assert response_body == {"identity": str(blog_post_record.identity)}
    assert run_record.content_item_id == blog_post_record.content_item_id
    content_item_query = select(ContentItemOrm).where(
        ContentItemOrm.id == blog_post_record.content_item_id
    )
    content_item_record = await db_session.scalar(content_item_query)

    find_blog_post_response = await api_client.get(f"/blog-posts/{blog_post_record.identity}")

    assert find_blog_post_response.status_code == 200
    assert find_blog_post_response.json() == {
        "identity": str(blog_post_record.identity),
        "content_item_identity": str(content_item_record.identity),
        "persona_identity": persona_identity,
        "persona_name": "Marta Quill",
        "persona_avatar_url": None,
        "is_persona_public": False,
        "title": "The Title",
        "subtitle": "A subtitle.",
        "body": "A paragraph.\n\n## A Section\n\nMore text.",
        "is_public": False,
        "published_at": None,
        "created_at": ANY,
        "updated_at": ANY,
    }


async def test_create_blog_post_from_generate_text_run_already_saved_returns_409(
    api_client: AsyncClient,
    signed_in_user: UserOrm,
    llm_service_stub: LlmServiceStub,
    background_job_service: BackgroundJobService,
) -> None:
    create_persona_response = await api_client.post(
        "/personas", json={"name": "Marta Quill", "bio": "Writes about slow mornings."}
    )
    persona_identity = create_persona_response.json()["identity"]
    run_identity = await _create_completed_run(
        api_client, llm_service_stub, background_job_service, persona_identity
    )
    await api_client.post(
        "/blog-posts/from-generate-text-run", json={"generate_text_run_identity": run_identity}
    )

    create_blog_post_response = await api_client.post(
        "/blog-posts/from-generate-text-run", json={"generate_text_run_identity": run_identity}
    )

    assert create_blog_post_response.status_code == 409


async def test_create_blog_post_from_generate_text_run_invalid_output_returns_422(
    api_client: AsyncClient, signed_in_user: UserOrm, db_session: AsyncSession
) -> None:
    # Built directly: the real draft step rejects a body with no leading "# Title".
    persona_record = await insert_persona_row(db_session, created_by_id=signed_in_user.id)
    run_record = await insert_generate_text_run_row(
        db_session,
        created_by_id=signed_in_user.id,
        persona_id=persona_record.id,
        status=GenerateTextRunStatusType.COMPLETED,
    )
    await insert_generate_text_step_row(
        db_session,
        run_id=run_record.id,
        created_by_id=signed_in_user.id,
        status=GenerateTextStepStatusType.SUCCEEDED,
        output_text="Plain text with no title.",
    )
    await db_session.commit()

    create_blog_post_response = await api_client.post(
        "/blog-posts/from-generate-text-run",
        json={"generate_text_run_identity": str(run_record.identity)},
    )

    assert create_blog_post_response.status_code == 422


async def test_create_blog_post_from_generate_text_run_is_public_on_private_persona_returns_422(
    api_client: AsyncClient,
    signed_in_user: UserOrm,
    llm_service_stub: LlmServiceStub,
    background_job_service: BackgroundJobService,
) -> None:
    create_persona_response = await api_client.post(
        "/personas", json={"name": "Marta Quill", "bio": "Writes about slow mornings."}
    )
    persona_identity = create_persona_response.json()["identity"]
    run_identity = await _create_completed_run(
        api_client, llm_service_stub, background_job_service, persona_identity
    )

    create_blog_post_response = await api_client.post(
        "/blog-posts/from-generate-text-run",
        json={"generate_text_run_identity": run_identity, "is_public": True},
    )

    assert create_blog_post_response.status_code == 422


async def test_create_blog_post_from_generate_text_run_another_users_run_returns_404(
    api_client: AsyncClient,
    signed_in_user: UserOrm,
    other_user_client: AsyncClient,
    llm_service_stub: LlmServiceStub,
    background_job_service: BackgroundJobService,
) -> None:
    other_create_persona_response = await other_user_client.post(
        "/personas", json={"name": "Other Persona", "bio": "Writes essays."}
    )
    other_persona_identity = other_create_persona_response.json()["identity"]
    other_run_identity = await _create_completed_run(
        other_user_client, llm_service_stub, background_job_service, other_persona_identity
    )

    create_blog_post_response = await api_client.post(
        "/blog-posts/from-generate-text-run",
        json={"generate_text_run_identity": other_run_identity},
    )

    assert create_blog_post_response.status_code == 404


async def test_create_blog_post_from_generate_text_run_unknown_run_returns_404(
    api_client: AsyncClient, signed_in_user: UserOrm
) -> None:
    create_blog_post_response = await api_client.post(
        "/blog-posts/from-generate-text-run", json={"generate_text_run_identity": str(uuid4())}
    )

    assert create_blog_post_response.status_code == 404


@pytest.mark.usefixtures("signed_in_user")
async def test_create_blog_post_from_generate_text_run_malformed_identity_returns_422(
    api_client: AsyncClient,
) -> None:
    create_blog_post_response = await api_client.post(
        "/blog-posts/from-generate-text-run", json={"generate_text_run_identity": "not-a-uuid"}
    )

    response_body = create_blog_post_response.json()
    assert create_blog_post_response.status_code == 422
    assert response_body["detail"][0]["loc"] == ["body", "generate_text_run_identity"]


@pytest.mark.usefixtures("signed_in_user")
async def test_create_blog_post_from_generate_text_run_naive_published_at_returns_422(
    api_client: AsyncClient,
) -> None:
    create_blog_post_response = await api_client.post(
        "/blog-posts/from-generate-text-run",
        json={"generate_text_run_identity": str(uuid4()), "published_at": "2026-01-01T00:00:00"},
    )

    response_body = create_blog_post_response.json()
    assert create_blog_post_response.status_code == 422
    assert response_body["detail"][0]["loc"] == ["body", "published_at"]


async def test_create_blog_post_from_generate_text_run_is_public_and_published_at_round_trip(
    api_client: AsyncClient,
    signed_in_user: UserOrm,
    llm_service_stub: LlmServiceStub,
    background_job_service: BackgroundJobService,
) -> None:
    create_persona_response = await api_client.post(
        "/personas",
        json={"name": "Marta Quill", "bio": "Writes about slow mornings.", "is_public": True},
    )
    persona_identity = create_persona_response.json()["identity"]
    run_identity = await _create_completed_run(
        api_client, llm_service_stub, background_job_service, persona_identity
    )

    create_blog_post_response = await api_client.post(
        "/blog-posts/from-generate-text-run",
        json={
            "generate_text_run_identity": run_identity,
            "is_public": True,
            "published_at": "2026-01-01T00:00:00+00:00",
        },
    )

    blog_post_identity = create_blog_post_response.json()["identity"]
    find_blog_post_response = await api_client.get(f"/blog-posts/{blog_post_identity}")
    find_blog_post_body = find_blog_post_response.json()
    assert create_blog_post_response.status_code == 201
    assert find_blog_post_body["is_public"] is True
    assert find_blog_post_body["published_at"] == "2026-01-01T00:00:00Z"


async def test_create_blog_post_from_generate_text_run_signed_out_returns_401(
    api_client: AsyncClient,
) -> None:
    create_blog_post_response = await api_client.post(
        "/blog-posts/from-generate-text-run", json={"generate_text_run_identity": str(uuid4())}
    )

    assert create_blog_post_response.status_code == 401


async def test_create_blog_post_signed_out_returns_401(api_client: AsyncClient) -> None:
    create_blog_post_response = await api_client.post(
        "/blog-posts",
        json={
            "persona_identity": str(uuid4()),
            "title": "A Title",
            "body": VALID_BLOG_POST_BODY,
        },
    )

    assert create_blog_post_response.status_code == 401


async def _create_other_users_blog_post(
    other_user_client: AsyncClient,
    *,
    is_persona_public: bool = True,
    is_public: bool = True,
    published_at: str | None = None,
    title: str = "Public Post",
) -> tuple[str, str]:
    create_persona_response = await other_user_client.post(
        "/personas",
        json={"name": "Public Persona", "bio": "Writes essays.", "is_public": is_persona_public},
    )
    persona_identity = create_persona_response.json()["identity"]
    create_blog_post_response = await other_user_client.post(
        "/blog-posts",
        json={
            "persona_identity": persona_identity,
            "title": title,
            "body": VALID_BLOG_POST_BODY,
            "is_public": is_public,
            "published_at": published_at,
        },
    )
    return persona_identity, create_blog_post_response.json()["identity"]


async def _find_content_item_identity(db_session: AsyncSession, blog_post_identity: str) -> str:
    content_item_identity_query = (
        select(ContentItemOrm.identity)
        .join(BlogPostOrm, BlogPostOrm.content_item_id == ContentItemOrm.id)
        .where(BlogPostOrm.identity == UUID(blog_post_identity))
    )
    content_item_identity = await db_session.scalar(content_item_identity_query)
    return str(content_item_identity)


async def test_find_user_blog_post_page_returns_only_signed_in_users_summaries_newest_first(
    api_client: AsyncClient,
    signed_in_user: UserOrm,
    db_session: AsyncSession,
    other_user_client: AsyncClient,
) -> None:
    persona_record = await insert_persona_row(
        db_session,
        created_by_id=signed_in_user.id,
        name="Slow Mornings Sam",
        avatar_url="https://example.com/sam.png",
    )
    oldest_content_item_record = await insert_content_item_row(
        db_session,
        created_by_id=signed_in_user.id,
        persona_id=persona_record.id,
        created_at=datetime(2026, 1, 1, tzinfo=UTC),
    )
    oldest_blog_post_record = await insert_blog_post_row(
        db_session,
        created_by_id=signed_in_user.id,
        content_item_id=oldest_content_item_record.id,
        title="Oldest Draft",
    )
    newest_content_item_record = await insert_content_item_row(
        db_session,
        created_by_id=signed_in_user.id,
        persona_id=persona_record.id,
        is_public=True,
        published_at=datetime(2020, 1, 1, tzinfo=UTC),
        created_at=datetime(2026, 1, 3, tzinfo=UTC),
    )
    newest_blog_post_record = await insert_blog_post_row(
        db_session,
        created_by_id=signed_in_user.id,
        content_item_id=newest_content_item_record.id,
        title="Newest Published",
        subtitle="A Subtitle",
    )
    await db_session.commit()
    await _create_other_users_blog_post(other_user_client, published_at="2020-01-01T00:00:00+00:00")

    find_user_blog_post_page_response = await api_client.get("/blog-posts")

    assert find_user_blog_post_page_response.status_code == 200
    assert find_user_blog_post_page_response.json() == {
        "blog_posts": [
            {
                "identity": str(newest_blog_post_record.identity),
                "content_item_identity": str(newest_content_item_record.identity),
                "persona_identity": str(persona_record.identity),
                "persona_name": "Slow Mornings Sam",
                "persona_avatar_url": "https://example.com/sam.png",
                "is_persona_public": False,
                "title": "Newest Published",
                "subtitle": "A Subtitle",
                "is_public": True,
                "published_at": "2020-01-01T00:00:00Z",
                "created_at": ANY,
                "updated_at": ANY,
            },
            {
                "identity": str(oldest_blog_post_record.identity),
                "content_item_identity": str(oldest_content_item_record.identity),
                "persona_identity": str(persona_record.identity),
                "persona_name": "Slow Mornings Sam",
                "persona_avatar_url": "https://example.com/sam.png",
                "is_persona_public": False,
                "title": "Oldest Draft",
                "subtitle": None,
                "is_public": False,
                "published_at": None,
                "created_at": ANY,
                "updated_at": ANY,
            },
        ],
        "pagination": {"page": 1, "page_size": 20, "total": 2},
    }


@pytest.mark.parametrize(
    ("is_public", "published_at"),
    [
        pytest.param(False, None, id="draft"),
        pytest.param(False, datetime(2020, 1, 1, tzinfo=UTC), id="private_post"),
        pytest.param(True, None, id="public_draft"),
        pytest.param(True, datetime(2099, 1, 1, tzinfo=UTC), id="scheduled_post"),
    ],
)
async def test_find_user_blog_post_page_lists_own_posts_the_public_page_hides(
    api_client: AsyncClient,
    signed_in_user: UserOrm,
    db_session: AsyncSession,
    is_public: bool,
    published_at: datetime | None,
) -> None:
    persona_record = await insert_persona_row(db_session, created_by_id=signed_in_user.id)
    await _insert_own_blog_post(
        db_session,
        user_record=signed_in_user,
        persona_id=persona_record.id,
        title="Hidden From Others",
        is_public=is_public,
        published_at=published_at,
    )
    await db_session.commit()

    find_user_blog_post_page_response = await api_client.get("/blog-posts")

    response_body = find_user_blog_post_page_response.json()
    assert [blog_post["title"] for blog_post in response_body["blog_posts"]] == [
        "Hidden From Others"
    ]


async def test_find_user_blog_post_page_excludes_another_users_published_post(
    api_client: AsyncClient, signed_in_user: UserOrm, other_user_client: AsyncClient
) -> None:
    await _create_other_users_blog_post(other_user_client, published_at="2020-01-01T00:00:00+00:00")

    find_user_blog_post_page_response = await api_client.get("/blog-posts")

    assert find_user_blog_post_page_response.json() == {
        "blog_posts": [],
        "pagination": {"page": 1, "page_size": 20, "total": 0},
    }


async def test_find_user_blog_post_page_excludes_deleted(
    api_client: AsyncClient, signed_in_user: UserOrm, db_session: AsyncSession
) -> None:
    persona_record = await insert_persona_row(db_session, created_by_id=signed_in_user.id)
    await db_session.commit()
    create_blog_post_response = await api_client.post(
        "/blog-posts",
        json={
            "persona_identity": str(persona_record.identity),
            "title": "A Title",
            "body": VALID_BLOG_POST_BODY,
        },
    )
    blog_post_identity = create_blog_post_response.json()["identity"]
    await api_client.delete(f"/blog-posts/{blog_post_identity}")

    find_user_blog_post_page_response = await api_client.get("/blog-posts")

    assert find_user_blog_post_page_response.status_code == 200
    assert find_user_blog_post_page_response.json() == {
        "blog_posts": [],
        "pagination": {"page": 1, "page_size": 20, "total": 0},
    }


async def test_find_user_blog_post_page_signed_out_returns_401(api_client: AsyncClient) -> None:
    find_user_blog_post_page_response = await api_client.get("/blog-posts")

    assert find_user_blog_post_page_response.status_code == 401


@pytest.mark.usefixtures("signed_in_user")
@pytest.mark.parametrize(
    ("query_params", "expected_error_location"),
    [
        pytest.param({"page": "0"}, ["query", "page"], id="page_zero"),
        pytest.param({"page": "10001"}, ["query", "page"], id="page_over_max"),
        pytest.param({"page_size": "0"}, ["query", "page_size"], id="page_size_zero"),
        pytest.param({"page_size": "101"}, ["query", "page_size"], id="page_size_over_max"),
        pytest.param({"sort_by": "FEED_SCORE"}, ["query", "sort_by"], id="unknown_sort_by"),
        pytest.param(
            {"sort_direction": "SIDEWAYS"}, ["query", "sort_direction"], id="unknown_sort_direction"
        ),
        pytest.param(
            {"persona_identity": "not-a-uuid"}, ["query", "persona_identity"], id="bad_persona"
        ),
        pytest.param({"search": "a" * 201}, ["query", "search"], id="search_too_long"),
        pytest.param({"search": "rye\x00"}, ["query", "search"], id="search_with_nul_byte"),
    ],
)
async def test_find_user_blog_post_page_invalid_query_returns_422(
    api_client: AsyncClient, query_params: dict[str, str], expected_error_location: list[str]
) -> None:
    find_user_blog_post_page_response = await api_client.get("/blog-posts", params=query_params)

    response_body = find_user_blog_post_page_response.json()
    assert find_user_blog_post_page_response.status_code == 422
    assert response_body["detail"][0]["loc"] == expected_error_location


async def test_find_user_blog_post_page_pages_and_reports_total_of_every_row(
    api_client: AsyncClient, signed_in_user: UserOrm, db_session: AsyncSession
) -> None:
    persona_record = await insert_persona_row(db_session, created_by_id=signed_in_user.id)
    for day, title in enumerate(["Post 1", "Post 2", "Post 3"], start=1):
        await _insert_own_blog_post(
            db_session,
            user_record=signed_in_user,
            persona_id=persona_record.id,
            title=title,
            created_at=datetime(2026, 1, day, tzinfo=UTC),
        )
    await db_session.commit()

    find_user_blog_post_page_response = await api_client.get(
        "/blog-posts", params={"page": "2", "page_size": "2"}
    )

    response_body = find_user_blog_post_page_response.json()
    assert [blog_post["title"] for blog_post in response_body["blog_posts"]] == ["Post 1"]
    assert response_body["pagination"] == {"page": 2, "page_size": 2, "total": 3}


async def test_find_user_blog_post_page_page_past_the_end_returns_no_rows_and_same_total(
    api_client: AsyncClient, signed_in_user: UserOrm, db_session: AsyncSession
) -> None:
    persona_record = await insert_persona_row(db_session, created_by_id=signed_in_user.id)
    await _insert_own_blog_post(
        db_session, user_record=signed_in_user, persona_id=persona_record.id, title="Only Post"
    )
    await db_session.commit()

    find_user_blog_post_page_response = await api_client.get("/blog-posts", params={"page": "5"})

    assert find_user_blog_post_page_response.json() == {
        "blog_posts": [],
        "pagination": {"page": 5, "page_size": 20, "total": 1},
    }


@pytest.mark.parametrize(
    ("sort_by", "sort_direction", "expected_titles"),
    [
        pytest.param("CREATED_AT", "ASC", ["Cherry", "Apple", "Banana"], id="created_at_asc"),
        pytest.param("CREATED_AT", "DESC", ["Banana", "Apple", "Cherry"], id="created_at_desc"),
        pytest.param("PUBLISHED_AT", "ASC", ["Banana", "Cherry", "Apple"], id="published_at_asc"),
        pytest.param("PUBLISHED_AT", "DESC", ["Cherry", "Banana", "Apple"], id="published_at_desc"),
        pytest.param("TITLE", "ASC", ["Apple", "Banana", "Cherry"], id="title_asc"),
        pytest.param("TITLE", "DESC", ["Cherry", "Banana", "Apple"], id="title_desc"),
    ],
)
async def test_find_user_blog_post_page_sorts_by_each_sort_type_in_both_directions(
    api_client: AsyncClient,
    signed_in_user: UserOrm,
    db_session: AsyncSession,
    sort_by: str,
    sort_direction: str,
    expected_titles: list[str],
) -> None:
    # Created in the order Cherry, Apple, Banana; Apple is an unpublished draft, listed last
    # when sorting by PUBLISHED_AT in either direction
    persona_record = await insert_persona_row(db_session, created_by_id=signed_in_user.id)
    for day, (title, published_at) in enumerate(
        [
            ("Cherry", datetime(2021, 1, 1, tzinfo=UTC)),
            ("Apple", None),
            ("Banana", datetime(2020, 1, 1, tzinfo=UTC)),
        ],
        start=1,
    ):
        await _insert_own_blog_post(
            db_session,
            user_record=signed_in_user,
            persona_id=persona_record.id,
            title=title,
            published_at=published_at,
            created_at=datetime(2026, 1, day, tzinfo=UTC),
        )
    await db_session.commit()

    find_user_blog_post_page_response = await api_client.get(
        "/blog-posts", params={"sort_by": sort_by, "sort_direction": sort_direction}
    )

    response_body = find_user_blog_post_page_response.json()
    assert find_user_blog_post_page_response.status_code == 200
    assert [blog_post["title"] for blog_post in response_body["blog_posts"]] == expected_titles


@pytest.mark.parametrize(
    ("search", "expected_titles"),
    [
        pytest.param("coffee", ["Morning Coffee"], id="title"),
        pytest.param("brewing", ["Morning Coffee"], id="subtitle"),
        pytest.param("zebra", [], id="body_is_not_searched"),
        pytest.param("%", [], id="percent_is_literal"),
        pytest.param("   ", ["Evening Tea", "Morning Coffee"], id="whitespace_means_no_search"),
    ],
)
async def test_find_user_blog_post_page_search_matches_title_and_subtitle(
    api_client: AsyncClient,
    signed_in_user: UserOrm,
    db_session: AsyncSession,
    search: str,
    expected_titles: list[str],
) -> None:
    persona_record = await insert_persona_row(db_session, created_by_id=signed_in_user.id)
    await _insert_own_blog_post(
        db_session,
        user_record=signed_in_user,
        persona_id=persona_record.id,
        title="Morning Coffee",
        subtitle="Slow brewing",
        body="A body mentioning a zebra.",
    )
    await _insert_own_blog_post(
        db_session, user_record=signed_in_user, persona_id=persona_record.id, title="Evening Tea"
    )
    await db_session.commit()

    find_user_blog_post_page_response = await api_client.get(
        "/blog-posts", params={"search": search, "sort_by": "TITLE", "sort_direction": "ASC"}
    )

    response_body = find_user_blog_post_page_response.json()
    assert [blog_post["title"] for blog_post in response_body["blog_posts"]] == expected_titles


async def test_find_user_blog_post_page_persona_identity_limits_rows_to_that_persona(
    api_client: AsyncClient, signed_in_user: UserOrm, db_session: AsyncSession
) -> None:
    matching_persona_record = await insert_persona_row(db_session, created_by_id=signed_in_user.id)
    other_persona_record = await insert_persona_row(db_session, created_by_id=signed_in_user.id)
    await _insert_own_blog_post(
        db_session,
        user_record=signed_in_user,
        persona_id=matching_persona_record.id,
        title="Matching Post",
    )
    await _insert_own_blog_post(
        db_session,
        user_record=signed_in_user,
        persona_id=other_persona_record.id,
        title="Other Persona Post",
    )
    await db_session.commit()

    find_user_blog_post_page_response = await api_client.get(
        "/blog-posts", params={"persona_identity": str(matching_persona_record.identity)}
    )

    response_body = find_user_blog_post_page_response.json()
    assert find_user_blog_post_page_response.status_code == 200
    assert [blog_post["title"] for blog_post in response_body["blog_posts"]] == ["Matching Post"]
    assert response_body["pagination"]["total"] == 1


async def test_find_blog_post_returns_blog_post_response(
    api_client: AsyncClient, signed_in_user: UserOrm, db_session: AsyncSession
) -> None:
    persona_record = await insert_persona_row(
        db_session,
        created_by_id=signed_in_user.id,
        name="Slow Mornings Sam",
        avatar_url="https://example.com/sam.png",
    )
    content_item_record = await insert_content_item_row(
        db_session, created_by_id=signed_in_user.id, persona_id=persona_record.id
    )
    blog_post_record = await insert_blog_post_row(
        db_session,
        created_by_id=signed_in_user.id,
        content_item_id=content_item_record.id,
        title="A Title",
        subtitle="A Subtitle",
    )
    await db_session.commit()

    find_blog_post_response = await api_client.get(f"/blog-posts/{blog_post_record.identity}")

    assert find_blog_post_response.status_code == 200
    assert find_blog_post_response.json() == {
        "identity": str(blog_post_record.identity),
        "content_item_identity": str(content_item_record.identity),
        "persona_identity": str(persona_record.identity),
        "persona_name": "Slow Mornings Sam",
        "persona_avatar_url": "https://example.com/sam.png",
        "is_persona_public": False,
        "title": "A Title",
        "subtitle": "A Subtitle",
        "body": VALID_BLOG_POST_BODY,
        "is_public": False,
        "published_at": None,
        "created_at": ANY,
        "updated_at": ANY,
    }


async def test_find_blog_post_public_persona_flags_persona_public(
    api_client: AsyncClient, signed_in_user: UserOrm, db_session: AsyncSession
) -> None:
    persona_record = await insert_persona_row(
        db_session, created_by_id=signed_in_user.id, is_public=True
    )
    content_item_record = await insert_content_item_row(
        db_session, created_by_id=signed_in_user.id, persona_id=persona_record.id
    )
    blog_post_record = await insert_blog_post_row(
        db_session, created_by_id=signed_in_user.id, content_item_id=content_item_record.id
    )
    await db_session.commit()

    find_blog_post_response = await api_client.get(f"/blog-posts/{blog_post_record.identity}")

    response_body = find_blog_post_response.json()
    assert find_blog_post_response.status_code == 200
    assert response_body["is_persona_public"] is True


async def test_find_blog_post_never_inserted_returns_404(
    api_client: AsyncClient, signed_in_user: UserOrm
) -> None:
    find_blog_post_response = await api_client.get(f"/blog-posts/{uuid4()}")

    assert find_blog_post_response.status_code == 404


async def test_find_blog_post_another_users_public_published_post_returns_404(
    api_client: AsyncClient, signed_in_user: UserOrm, other_user_client: AsyncClient
) -> None:
    _, other_blog_post_identity = await _create_other_users_blog_post(
        other_user_client, published_at="2020-01-01T00:00:00+00:00"
    )

    find_blog_post_response = await api_client.get(f"/blog-posts/{other_blog_post_identity}")

    assert find_blog_post_response.status_code == 404


async def test_find_public_blog_post_signed_out_published_post_returns_public_response(
    api_client: AsyncClient, other_user_client: AsyncClient, db_session: AsyncSession
) -> None:
    other_persona_identity, other_blog_post_identity = await _create_other_users_blog_post(
        other_user_client, published_at="2020-01-01T00:00:00+00:00"
    )
    other_content_item_identity = await _find_content_item_identity(
        db_session, other_blog_post_identity
    )

    find_public_blog_post_response = await api_client.get(
        f"/blog-posts/{other_blog_post_identity}/public"
    )

    assert find_public_blog_post_response.status_code == 200
    assert find_public_blog_post_response.json() == {
        "identity": other_blog_post_identity,
        "content_item_identity": other_content_item_identity,
        "persona_identity": other_persona_identity,
        "persona_name": "Public Persona",
        "persona_avatar_url": None,
        "is_persona_public": True,
        "title": "Public Post",
        "subtitle": None,
        "body": VALID_BLOG_POST_BODY,
        "is_public": True,
        "published_at": "2020-01-01T00:00:00Z",
        "created_at": ANY,
        "updated_at": ANY,
        "is_owner": False,
    }


async def test_find_public_blog_post_signed_in_as_another_user_is_not_owner(
    api_client: AsyncClient, signed_in_user: UserOrm, other_user_client: AsyncClient
) -> None:
    _, other_blog_post_identity = await _create_other_users_blog_post(
        other_user_client, published_at="2020-01-01T00:00:00+00:00"
    )

    find_public_blog_post_response = await api_client.get(
        f"/blog-posts/{other_blog_post_identity}/public"
    )

    assert find_public_blog_post_response.status_code == 200
    assert find_public_blog_post_response.json()["is_owner"] is False


async def test_find_public_blog_post_signed_in_as_owner_private_post_flags_owner(
    api_client: AsyncClient, signed_in_user: UserOrm, db_session: AsyncSession
) -> None:
    persona_record = await insert_persona_row(
        db_session,
        created_by_id=signed_in_user.id,
        name="Slow Mornings Sam",
        avatar_url="https://example.com/sam.png",
    )
    content_item_record = await insert_content_item_row(
        db_session, created_by_id=signed_in_user.id, persona_id=persona_record.id
    )
    blog_post_record = await insert_blog_post_row(
        db_session,
        created_by_id=signed_in_user.id,
        content_item_id=content_item_record.id,
        title="A Title",
        subtitle="A Subtitle",
    )
    await db_session.commit()

    find_public_blog_post_response = await api_client.get(
        f"/blog-posts/{blog_post_record.identity}/public"
    )

    assert find_public_blog_post_response.status_code == 200
    assert find_public_blog_post_response.json() == {
        "identity": str(blog_post_record.identity),
        "content_item_identity": str(content_item_record.identity),
        "persona_identity": str(persona_record.identity),
        "persona_name": "Slow Mornings Sam",
        "persona_avatar_url": "https://example.com/sam.png",
        "is_persona_public": False,
        "title": "A Title",
        "subtitle": "A Subtitle",
        "body": VALID_BLOG_POST_BODY,
        "is_public": False,
        "published_at": None,
        "created_at": ANY,
        "updated_at": ANY,
        "is_owner": True,
    }


@pytest.mark.parametrize(
    ("is_persona_public", "is_public", "published_at"),
    [
        pytest.param(True, False, "2020-01-01T00:00:00+00:00", id="private_post"),
        pytest.param(True, True, None, id="unpublished_post"),
        pytest.param(True, True, "2030-01-01T00:00:00+00:00", id="scheduled_post"),
        pytest.param(False, False, None, id="post_on_private_persona"),
    ],
)
async def test_find_public_blog_post_signed_out_hidden_post_returns_404(
    api_client: AsyncClient,
    other_user_client: AsyncClient,
    is_persona_public: bool,
    is_public: bool,
    published_at: str | None,
) -> None:
    _, other_blog_post_identity = await _create_other_users_blog_post(
        other_user_client,
        is_persona_public=is_persona_public,
        is_public=is_public,
        published_at=published_at,
    )

    find_public_blog_post_response = await api_client.get(
        f"/blog-posts/{other_blog_post_identity}/public"
    )

    assert find_public_blog_post_response.status_code == 404


async def test_find_public_blog_post_persona_made_private_after_publishing_returns_404(
    api_client: AsyncClient, other_user_client: AsyncClient
) -> None:
    other_persona_identity, other_blog_post_identity = await _create_other_users_blog_post(
        other_user_client, published_at="2020-01-01T00:00:00+00:00"
    )
    await other_user_client.put(
        f"/personas/{other_persona_identity}",
        json={"name": "Public Persona", "bio": "Writes essays.", "is_public": False},
    )

    find_public_blog_post_response = await api_client.get(
        f"/blog-posts/{other_blog_post_identity}/public"
    )

    assert find_public_blog_post_response.status_code == 404


async def test_find_public_blog_post_never_inserted_returns_404(api_client: AsyncClient) -> None:
    find_public_blog_post_response = await api_client.get(f"/blog-posts/{uuid4()}/public")

    assert find_public_blog_post_response.status_code == 404


async def test_find_public_blog_post_malformed_identity_returns_422(
    api_client: AsyncClient,
) -> None:
    find_public_blog_post_response = await api_client.get("/blog-posts/not-a-uuid/public")

    response_body = find_public_blog_post_response.json()
    assert find_public_blog_post_response.status_code == 422
    assert response_body["detail"][0]["loc"] == ["path", "blog_post_identity"]


async def test_find_public_blog_post_invalid_session_returns_401(api_client: AsyncClient) -> None:
    api_client.cookies.set("sid", "not-a-real-session-id")

    find_public_blog_post_response = await api_client.get(f"/blog-posts/{uuid4()}/public")

    assert find_public_blog_post_response.status_code == 401


async def test_find_blog_post_another_users_draft_returns_404(
    api_client: AsyncClient, signed_in_user: UserOrm, other_user_client: AsyncClient
) -> None:
    other_create_persona_response = await other_user_client.post(
        "/personas", json={"name": "Public Persona", "bio": "Writes essays.", "is_public": True}
    )
    other_persona_identity = other_create_persona_response.json()["identity"]
    other_create_blog_post_response = await other_user_client.post(
        "/blog-posts",
        json={
            "persona_identity": other_persona_identity,
            "title": "Draft Post",
            "body": VALID_BLOG_POST_BODY,
            "is_public": True,
        },
    )
    other_blog_post_identity = other_create_blog_post_response.json()["identity"]

    find_blog_post_response = await api_client.get(f"/blog-posts/{other_blog_post_identity}")

    assert find_blog_post_response.status_code == 404


async def test_find_blog_post_another_users_future_scheduled_returns_404(
    api_client: AsyncClient, signed_in_user: UserOrm, other_user_client: AsyncClient
) -> None:
    other_create_persona_response = await other_user_client.post(
        "/personas", json={"name": "Public Persona", "bio": "Writes essays.", "is_public": True}
    )
    other_persona_identity = other_create_persona_response.json()["identity"]
    other_create_blog_post_response = await other_user_client.post(
        "/blog-posts",
        json={
            "persona_identity": other_persona_identity,
            "title": "Scheduled Post",
            "body": VALID_BLOG_POST_BODY,
            "is_public": True,
            "published_at": "2030-01-01T00:00:00+00:00",
        },
    )
    other_blog_post_identity = other_create_blog_post_response.json()["identity"]

    find_blog_post_response = await api_client.get(f"/blog-posts/{other_blog_post_identity}")

    assert find_blog_post_response.status_code == 404


async def test_find_blog_post_another_users_private_returns_404(
    api_client: AsyncClient, signed_in_user: UserOrm, other_user_client: AsyncClient
) -> None:
    other_create_persona_response = await other_user_client.post(
        "/personas", json={"name": "Public Persona", "bio": "Writes essays.", "is_public": True}
    )
    other_persona_identity = other_create_persona_response.json()["identity"]
    other_create_blog_post_response = await other_user_client.post(
        "/blog-posts",
        json={
            "persona_identity": other_persona_identity,
            "title": "Private Post",
            "body": VALID_BLOG_POST_BODY,
        },
    )
    other_blog_post_identity = other_create_blog_post_response.json()["identity"]

    find_blog_post_response = await api_client.get(f"/blog-posts/{other_blog_post_identity}")

    assert find_blog_post_response.status_code == 404


async def test_find_blog_post_another_users_private_persona_returns_404(
    api_client: AsyncClient, signed_in_user: UserOrm, other_user_client: AsyncClient
) -> None:
    other_create_persona_response = await other_user_client.post(
        "/personas", json={"name": "Private Persona", "bio": "Writes essays."}
    )
    other_persona_identity = other_create_persona_response.json()["identity"]
    other_create_blog_post_response = await other_user_client.post(
        "/blog-posts",
        json={
            "persona_identity": other_persona_identity,
            "title": "Post On Private Persona",
            "body": VALID_BLOG_POST_BODY,
        },
    )
    other_blog_post_identity = other_create_blog_post_response.json()["identity"]

    find_blog_post_response = await api_client.get(f"/blog-posts/{other_blog_post_identity}")

    assert find_blog_post_response.status_code == 404


@pytest.mark.usefixtures("signed_in_user")
async def test_find_blog_post_malformed_identity_returns_422(api_client: AsyncClient) -> None:
    find_blog_post_response = await api_client.get("/blog-posts/not-a-uuid")

    response_body = find_blog_post_response.json()
    assert find_blog_post_response.status_code == 422
    assert response_body["detail"][0]["loc"] == ["path", "blog_post_identity"]


async def test_find_blog_post_signed_out_returns_401(api_client: AsyncClient) -> None:
    find_blog_post_response = await api_client.get(f"/blog-posts/{uuid4()}")

    assert find_blog_post_response.status_code == 401


async def test_update_blog_post_full_replacement_persists(
    api_client: AsyncClient, signed_in_user: UserOrm, db_session: AsyncSession
) -> None:
    persona_record = await insert_persona_row(
        db_session, created_by_id=signed_in_user.id, is_public=True
    )
    content_item_record = await insert_content_item_row(
        db_session, created_by_id=signed_in_user.id, persona_id=persona_record.id
    )
    blog_post_record = await insert_blog_post_row(
        db_session,
        created_by_id=signed_in_user.id,
        content_item_id=content_item_record.id,
        title="Old Title",
        subtitle="Old Subtitle",
    )
    await db_session.commit()

    update_blog_post_response = await api_client.put(
        f"/blog-posts/{blog_post_record.identity}",
        json={
            "title": "New Title",
            "body": "A new paragraph.\n\n## New Heading\n\nMore text.",
            "is_public": True,
        },
    )

    await db_session.refresh(blog_post_record)
    await db_session.refresh(content_item_record)
    assert update_blog_post_response.status_code == 200
    assert update_blog_post_response.json() == {}
    assert blog_post_record.title == "New Title"
    assert blog_post_record.subtitle is None
    assert blog_post_record.body == "A new paragraph.\n\n## New Heading\n\nMore text."
    assert content_item_record.is_public is True
    assert blog_post_record.updated_by_id == signed_in_user.id


async def test_update_blog_post_publish_sets_published_at(
    api_client: AsyncClient, signed_in_user: UserOrm, db_session: AsyncSession
) -> None:
    persona_record = await insert_persona_row(db_session, created_by_id=signed_in_user.id)
    content_item_record = await insert_content_item_row(
        db_session, created_by_id=signed_in_user.id, persona_id=persona_record.id
    )
    blog_post_record = await insert_blog_post_row(
        db_session, created_by_id=signed_in_user.id, content_item_id=content_item_record.id
    )
    await db_session.commit()

    update_blog_post_response = await api_client.put(
        f"/blog-posts/{blog_post_record.identity}",
        json={
            "title": "A Title",
            "body": VALID_BLOG_POST_BODY,
            "published_at": "2026-01-01T00:00:00+00:00",
        },
    )

    await db_session.refresh(content_item_record)
    assert update_blog_post_response.status_code == 200
    assert content_item_record.published_at == datetime(2026, 1, 1, tzinfo=UTC)


async def test_update_blog_post_unpublish_clears_published_at(
    api_client: AsyncClient, signed_in_user: UserOrm, db_session: AsyncSession
) -> None:
    persona_record = await insert_persona_row(db_session, created_by_id=signed_in_user.id)
    content_item_record = await insert_content_item_row(
        db_session,
        created_by_id=signed_in_user.id,
        persona_id=persona_record.id,
        published_at=datetime(2026, 1, 1, tzinfo=UTC),
    )
    blog_post_record = await insert_blog_post_row(
        db_session, created_by_id=signed_in_user.id, content_item_id=content_item_record.id
    )
    await db_session.commit()

    update_blog_post_response = await api_client.put(
        f"/blog-posts/{blog_post_record.identity}",
        json={"title": "A Title", "body": VALID_BLOG_POST_BODY},
    )

    await db_session.refresh(content_item_record)
    assert update_blog_post_response.status_code == 200
    assert content_item_record.published_at is None


async def test_update_blog_post_is_public_on_private_persona_returns_422(
    api_client: AsyncClient, signed_in_user: UserOrm, db_session: AsyncSession
) -> None:
    persona_record = await insert_persona_row(
        db_session, created_by_id=signed_in_user.id, is_public=False
    )
    content_item_record = await insert_content_item_row(
        db_session, created_by_id=signed_in_user.id, persona_id=persona_record.id
    )
    blog_post_record = await insert_blog_post_row(
        db_session, created_by_id=signed_in_user.id, content_item_id=content_item_record.id
    )
    await db_session.commit()

    update_blog_post_response = await api_client.put(
        f"/blog-posts/{blog_post_record.identity}",
        json={"title": "A Title", "body": VALID_BLOG_POST_BODY, "is_public": True},
    )

    assert update_blog_post_response.status_code == 422


async def test_update_blog_post_already_public_on_private_persona_keeping_public_returns_200(
    api_client: AsyncClient, signed_in_user: UserOrm, db_session: AsyncSession
) -> None:
    persona_record = await insert_persona_row(
        db_session, created_by_id=signed_in_user.id, is_public=False
    )
    content_item_record = await insert_content_item_row(
        db_session, created_by_id=signed_in_user.id, persona_id=persona_record.id, is_public=True
    )
    blog_post_record = await insert_blog_post_row(
        db_session, created_by_id=signed_in_user.id, content_item_id=content_item_record.id
    )
    await db_session.commit()

    update_blog_post_response = await api_client.put(
        f"/blog-posts/{blog_post_record.identity}",
        json={"title": "New Title", "body": VALID_BLOG_POST_BODY, "is_public": True},
    )

    await db_session.refresh(blog_post_record)
    await db_session.refresh(content_item_record)
    assert update_blog_post_response.status_code == 200
    assert update_blog_post_response.json() == {}
    assert blog_post_record.title == "New Title"
    assert content_item_record.is_public is True


async def test_update_blog_post_already_public_on_private_persona_made_private_returns_200(
    api_client: AsyncClient, signed_in_user: UserOrm, db_session: AsyncSession
) -> None:
    persona_record = await insert_persona_row(
        db_session, created_by_id=signed_in_user.id, is_public=False
    )
    content_item_record = await insert_content_item_row(
        db_session, created_by_id=signed_in_user.id, persona_id=persona_record.id, is_public=True
    )
    blog_post_record = await insert_blog_post_row(
        db_session, created_by_id=signed_in_user.id, content_item_id=content_item_record.id
    )
    await db_session.commit()

    update_blog_post_response = await api_client.put(
        f"/blog-posts/{blog_post_record.identity}",
        json={"title": "A Title", "body": VALID_BLOG_POST_BODY, "is_public": False},
    )

    await db_session.refresh(content_item_record)
    assert update_blog_post_response.status_code == 200
    assert content_item_record.is_public is False


@pytest.mark.parametrize(
    ("request_body", "expected_error_location"),
    [
        pytest.param({"body": VALID_BLOG_POST_BODY}, ["body", "title"], id="missing_title"),
        pytest.param({"title": "A Title"}, ["body", "body"], id="missing_body"),
    ],
)
async def test_update_blog_post_invalid_body_returns_422(
    api_client: AsyncClient,
    signed_in_user: UserOrm,
    db_session: AsyncSession,
    request_body: dict[str, str],
    expected_error_location: list[str],
) -> None:
    persona_record = await insert_persona_row(db_session, created_by_id=signed_in_user.id)
    content_item_record = await insert_content_item_row(
        db_session, created_by_id=signed_in_user.id, persona_id=persona_record.id
    )
    blog_post_record = await insert_blog_post_row(
        db_session, created_by_id=signed_in_user.id, content_item_id=content_item_record.id
    )
    await db_session.commit()

    update_blog_post_response = await api_client.put(
        f"/blog-posts/{blog_post_record.identity}", json=request_body
    )

    response_body = update_blog_post_response.json()
    assert update_blog_post_response.status_code == 422
    assert response_body["detail"][0]["loc"] == expected_error_location


async def test_update_blog_post_never_inserted_returns_404(
    api_client: AsyncClient, signed_in_user: UserOrm
) -> None:
    update_blog_post_response = await api_client.put(
        f"/blog-posts/{uuid4()}", json={"title": "A Title", "body": VALID_BLOG_POST_BODY}
    )

    assert update_blog_post_response.status_code == 404


async def test_update_blog_post_another_users_visible_post_returns_403(
    api_client: AsyncClient, signed_in_user: UserOrm, other_user_client: AsyncClient
) -> None:
    other_create_persona_response = await other_user_client.post(
        "/personas", json={"name": "Public Persona", "bio": "Writes essays.", "is_public": True}
    )
    other_persona_identity = other_create_persona_response.json()["identity"]
    other_create_blog_post_response = await other_user_client.post(
        "/blog-posts",
        json={
            "persona_identity": other_persona_identity,
            "title": "Public Post",
            "body": VALID_BLOG_POST_BODY,
            "is_public": True,
            "published_at": "2020-01-01T00:00:00+00:00",
        },
    )
    other_blog_post_identity = other_create_blog_post_response.json()["identity"]

    update_blog_post_response = await api_client.put(
        f"/blog-posts/{other_blog_post_identity}",
        json={"title": "New Title", "body": VALID_BLOG_POST_BODY},
    )

    assert update_blog_post_response.status_code == 403


async def test_update_blog_post_hidden_returns_404(
    api_client: AsyncClient, signed_in_user: UserOrm, other_user_client: AsyncClient
) -> None:
    other_create_persona_response = await other_user_client.post(
        "/personas", json={"name": "Private Persona", "bio": "Writes essays."}
    )
    other_persona_identity = other_create_persona_response.json()["identity"]
    other_create_blog_post_response = await other_user_client.post(
        "/blog-posts",
        json={
            "persona_identity": other_persona_identity,
            "title": "Private Post",
            "body": VALID_BLOG_POST_BODY,
        },
    )
    other_blog_post_identity = other_create_blog_post_response.json()["identity"]

    update_blog_post_response = await api_client.put(
        f"/blog-posts/{other_blog_post_identity}",
        json={"title": "New Title", "body": VALID_BLOG_POST_BODY},
    )

    assert update_blog_post_response.status_code == 404


@pytest.mark.usefixtures("signed_in_user")
async def test_update_blog_post_malformed_identity_returns_422(api_client: AsyncClient) -> None:
    update_blog_post_response = await api_client.put(
        "/blog-posts/not-a-uuid", json={"title": "A Title", "body": VALID_BLOG_POST_BODY}
    )

    response_body = update_blog_post_response.json()
    assert update_blog_post_response.status_code == 422
    assert response_body["detail"][0]["loc"] == ["path", "blog_post_identity"]


async def test_update_blog_post_signed_out_returns_401(api_client: AsyncClient) -> None:
    update_blog_post_response = await api_client.put(
        f"/blog-posts/{uuid4()}", json={"title": "A Title", "body": VALID_BLOG_POST_BODY}
    )

    assert update_blog_post_response.status_code == 401


async def test_delete_blog_post_soft_deletes_and_becomes_not_found(
    api_client: AsyncClient, signed_in_user: UserOrm, db_session: AsyncSession
) -> None:
    persona_record = await insert_persona_row(db_session, created_by_id=signed_in_user.id)
    content_item_record = await insert_content_item_row(
        db_session, created_by_id=signed_in_user.id, persona_id=persona_record.id
    )
    blog_post_record = await insert_blog_post_row(
        db_session, created_by_id=signed_in_user.id, content_item_id=content_item_record.id
    )
    await db_session.commit()

    delete_blog_post_response = await api_client.delete(f"/blog-posts/{blog_post_record.identity}")

    blog_post_query = select(BlogPostOrm).where(BlogPostOrm.identity == blog_post_record.identity)
    orm_result = await db_session.scalar(blog_post_query)
    find_blog_post_response = await api_client.get(f"/blog-posts/{blog_post_record.identity}")
    assert delete_blog_post_response.status_code == 200
    assert delete_blog_post_response.json() == {}
    assert orm_result is None
    assert find_blog_post_response.status_code == 404


async def test_delete_blog_post_never_inserted_returns_404(
    api_client: AsyncClient, signed_in_user: UserOrm
) -> None:
    delete_blog_post_response = await api_client.delete(f"/blog-posts/{uuid4()}")

    assert delete_blog_post_response.status_code == 404


async def test_delete_blog_post_another_users_visible_returns_403(
    api_client: AsyncClient, signed_in_user: UserOrm, other_user_client: AsyncClient
) -> None:
    other_create_persona_response = await other_user_client.post(
        "/personas", json={"name": "Public Persona", "bio": "Writes essays.", "is_public": True}
    )
    other_persona_identity = other_create_persona_response.json()["identity"]
    other_create_blog_post_response = await other_user_client.post(
        "/blog-posts",
        json={
            "persona_identity": other_persona_identity,
            "title": "Public Post",
            "body": VALID_BLOG_POST_BODY,
            "is_public": True,
            "published_at": "2020-01-01T00:00:00+00:00",
        },
    )
    other_blog_post_identity = other_create_blog_post_response.json()["identity"]

    delete_blog_post_response = await api_client.delete(f"/blog-posts/{other_blog_post_identity}")

    assert delete_blog_post_response.status_code == 403


@pytest.mark.usefixtures("signed_in_user")
async def test_delete_blog_post_malformed_identity_returns_422(api_client: AsyncClient) -> None:
    delete_blog_post_response = await api_client.delete("/blog-posts/not-a-uuid")

    response_body = delete_blog_post_response.json()
    assert delete_blog_post_response.status_code == 422
    assert response_body["detail"][0]["loc"] == ["path", "blog_post_identity"]


async def test_delete_blog_post_signed_out_returns_401(api_client: AsyncClient) -> None:
    delete_blog_post_response = await api_client.delete(f"/blog-posts/{uuid4()}")

    assert delete_blog_post_response.status_code == 401


async def test_create_blog_post_reader_returns_403_and_writes_no_row(
    api_client: AsyncClient, signed_in_reader: UserOrm, db_session: AsyncSession
) -> None:
    persona_record = await insert_persona_row(db_session, created_by_id=signed_in_reader.id)
    await db_session.commit()

    create_blog_post_response = await api_client.post(
        "/blog-posts",
        json={
            "persona_identity": str(persona_record.identity),
            "title": "Why Slow Mornings Make Better Writers",
            "body": VALID_BLOG_POST_BODY,
        },
    )

    blog_post_count_query = select(func.count(BlogPostOrm.id)).where(
        BlogPostOrm.created_by_id == signed_in_reader.id
    )
    blog_post_count = await db_session.scalar(blog_post_count_query)
    assert create_blog_post_response.status_code == 403
    assert blog_post_count == 0


async def test_create_blog_post_from_generate_text_run_reader_returns_403_and_writes_no_row(
    api_client: AsyncClient, signed_in_reader: UserOrm, db_session: AsyncSession
) -> None:
    persona_record = await insert_persona_row(db_session, created_by_id=signed_in_reader.id)
    generate_text_run_record = await insert_generate_text_run_row(
        db_session,
        created_by_id=signed_in_reader.id,
        persona_id=persona_record.id,
        status=GenerateTextRunStatusType.COMPLETED,
    )
    await db_session.commit()

    create_blog_post_response = await api_client.post(
        "/blog-posts/from-generate-text-run",
        json={"generate_text_run_identity": str(generate_text_run_record.identity)},
    )

    blog_post_count_query = select(func.count(BlogPostOrm.id)).where(
        BlogPostOrm.created_by_id == signed_in_reader.id
    )
    blog_post_count = await db_session.scalar(blog_post_count_query)
    assert create_blog_post_response.status_code == 403
    assert blog_post_count == 0


async def test_update_blog_post_reader_returns_403_and_leaves_row_unchanged(
    api_client: AsyncClient, signed_in_reader: UserOrm, db_session: AsyncSession
) -> None:
    persona_record = await insert_persona_row(db_session, created_by_id=signed_in_reader.id)
    content_item_record = await insert_content_item_row(
        db_session, created_by_id=signed_in_reader.id, persona_id=persona_record.id
    )
    blog_post_record = await insert_blog_post_row(
        db_session,
        created_by_id=signed_in_reader.id,
        content_item_id=content_item_record.id,
        title="Old Title",
    )
    await db_session.commit()

    update_blog_post_response = await api_client.put(
        f"/blog-posts/{blog_post_record.identity}",
        json={"title": "New Title", "body": VALID_BLOG_POST_BODY},
    )

    await db_session.refresh(blog_post_record)
    assert update_blog_post_response.status_code == 403
    assert blog_post_record.title == "Old Title"


async def test_delete_blog_post_reader_returns_403_and_keeps_row(
    api_client: AsyncClient, signed_in_reader: UserOrm, db_session: AsyncSession
) -> None:
    persona_record = await insert_persona_row(db_session, created_by_id=signed_in_reader.id)
    content_item_record = await insert_content_item_row(
        db_session, created_by_id=signed_in_reader.id, persona_id=persona_record.id
    )
    blog_post_record = await insert_blog_post_row(
        db_session, created_by_id=signed_in_reader.id, content_item_id=content_item_record.id
    )
    await db_session.commit()

    delete_blog_post_response = await api_client.delete(f"/blog-posts/{blog_post_record.identity}")

    await db_session.refresh(blog_post_record)
    assert delete_blog_post_response.status_code == 403
    assert blog_post_record.deleted_at is None


@pytest.mark.usefixtures("signed_in_reader")
async def test_find_user_blog_post_page_reader_returns_200(api_client: AsyncClient) -> None:
    find_user_blog_post_page_response = await api_client.get("/blog-posts")

    assert find_user_blog_post_page_response.status_code == 200
    assert find_user_blog_post_page_response.json() == {
        "blog_posts": [],
        "pagination": {"page": 1, "page_size": 20, "total": 0},
    }


async def _insert_own_blog_post(
    db_session: AsyncSession,
    *,
    user_record: UserOrm,
    persona_id: int,
    title: str,
    subtitle: str | None = None,
    body: str = VALID_BLOG_POST_BODY,
    is_public: bool = True,
    published_at: datetime | None = datetime(2020, 1, 1, tzinfo=UTC),
    feed_score: float | None = None,
    created_at: datetime | None = None,
) -> BlogPostOrm:
    content_item_record = await insert_content_item_row(
        db_session,
        created_by_id=user_record.id,
        persona_id=persona_id,
        is_public=is_public,
        published_at=published_at,
        created_at=created_at,
    )
    system_user_record = await find_system_user_row(db_session)
    await insert_content_item_engagement_row(
        db_session,
        content_item_id=content_item_record.id,
        system_user_id=system_user_record.id,
        feed_score=feed_score,
    )
    return await insert_blog_post_row(
        db_session,
        created_by_id=user_record.id,
        content_item_id=content_item_record.id,
        title=title,
        subtitle=subtitle,
        body=body,
    )


async def test_find_public_blog_post_page_signed_out_returns_other_users_published_post(
    api_client: AsyncClient, other_user_client: AsyncClient, db_session: AsyncSession
) -> None:
    other_persona_identity, other_blog_post_identity = await _create_other_users_blog_post(
        other_user_client, published_at="2020-01-01T00:00:00+00:00"
    )
    other_content_item_identity = await _find_content_item_identity(
        db_session, other_blog_post_identity
    )

    find_public_blog_post_page_response = await api_client.get("/blog-posts/public")

    assert find_public_blog_post_page_response.status_code == 200
    assert find_public_blog_post_page_response.json() == {
        "blog_posts": [
            {
                "identity": other_blog_post_identity,
                "content_item_identity": other_content_item_identity,
                "persona_identity": other_persona_identity,
                "persona_name": "Public Persona",
                "persona_avatar_url": None,
                "is_persona_public": True,
                "title": "Public Post",
                "subtitle": None,
                "is_public": True,
                "published_at": "2020-01-01T00:00:00Z",
                "created_at": ANY,
                "updated_at": ANY,
            }
        ],
        "pagination": {"page": 1, "page_size": 20, "total": 1},
    }


@pytest.mark.parametrize(
    ("is_persona_public", "is_public", "published_at"),
    [
        pytest.param(True, False, "2020-01-01T00:00:00+00:00", id="private_post"),
        pytest.param(True, True, None, id="draft"),
        pytest.param(True, True, "2099-01-01T00:00:00+00:00", id="scheduled_post"),
        pytest.param(False, False, None, id="post_on_private_persona"),
    ],
)
async def test_find_public_blog_post_page_signed_out_hidden_post_is_not_listed(
    api_client: AsyncClient,
    other_user_client: AsyncClient,
    is_persona_public: bool,
    is_public: bool,
    published_at: str | None,
) -> None:
    await _create_other_users_blog_post(
        other_user_client,
        is_persona_public=is_persona_public,
        is_public=is_public,
        published_at=published_at,
    )

    find_public_blog_post_page_response = await api_client.get("/blog-posts/public")

    assert find_public_blog_post_page_response.status_code == 200
    assert find_public_blog_post_page_response.json() == {
        "blog_posts": [],
        "pagination": {"page": 1, "page_size": 20, "total": 0},
    }


async def test_find_public_blog_post_page_signed_in_does_not_list_own_draft_or_private_post(
    api_client: AsyncClient,
    signed_in_user: UserOrm,
    db_session: AsyncSession,
    other_user_client: AsyncClient,
) -> None:
    private_persona_record = await insert_persona_row(
        db_session, created_by_id=signed_in_user.id, is_public=False
    )
    await _insert_own_blog_post(
        db_session,
        user_record=signed_in_user,
        persona_id=private_persona_record.id,
        title="My Draft",
        is_public=False,
        published_at=None,
    )
    await _insert_own_blog_post(
        db_session,
        user_record=signed_in_user,
        persona_id=private_persona_record.id,
        title="My Private Post",
        is_public=False,
    )
    await db_session.commit()
    await _create_other_users_blog_post(
        other_user_client, published_at="2020-01-01T00:00:00+00:00", title="Their Post"
    )

    find_public_blog_post_page_response = await api_client.get("/blog-posts/public")

    response_body = find_public_blog_post_page_response.json()
    assert find_public_blog_post_page_response.status_code == 200
    assert [blog_post["title"] for blog_post in response_body["blog_posts"]] == ["Their Post"]
    assert response_body["pagination"] == {"page": 1, "page_size": 20, "total": 1}


async def test_find_public_blog_post_page_signed_in_does_not_list_others_drafts(
    api_client: AsyncClient, signed_in_user: UserOrm, other_user_client: AsyncClient
) -> None:
    await _create_other_users_blog_post(other_user_client, published_at=None)

    find_public_blog_post_page_response = await api_client.get("/blog-posts/public")

    assert find_public_blog_post_page_response.status_code == 200
    assert find_public_blog_post_page_response.json()["blog_posts"] == []


async def test_find_public_blog_post_page_invalid_session_returns_401(
    api_client: AsyncClient,
) -> None:
    api_client.cookies.set("sid", "not-a-real-session-id")

    find_public_blog_post_page_response = await api_client.get("/blog-posts/public")

    assert find_public_blog_post_page_response.status_code == 401


@pytest.mark.parametrize(
    ("query_params", "expected_error_location"),
    [
        pytest.param({"page": "0"}, ["query", "page"], id="page_zero"),
        pytest.param({"page": "10001"}, ["query", "page"], id="page_over_max"),
        pytest.param({"page_size": "0"}, ["query", "page_size"], id="page_size_zero"),
        pytest.param({"page_size": "101"}, ["query", "page_size"], id="page_size_over_max"),
        pytest.param({"sort_by": "CREATED_AT"}, ["query", "sort_by"], id="unknown_sort_by"),
        pytest.param(
            {"sort_direction": "SIDEWAYS"}, ["query", "sort_direction"], id="unknown_sort_direction"
        ),
        pytest.param(
            {"persona_identity": "not-a-uuid"}, ["query", "persona_identity"], id="bad_persona"
        ),
        pytest.param({"search": "a" * 201}, ["query", "search"], id="search_too_long"),
        pytest.param({"search": "rye\x00"}, ["query", "search"], id="search_with_nul_byte"),
    ],
)
async def test_find_public_blog_post_page_invalid_query_returns_422(
    api_client: AsyncClient, query_params: dict[str, str], expected_error_location: list[str]
) -> None:
    find_public_blog_post_page_response = await api_client.get(
        "/blog-posts/public", params=query_params
    )

    response_body = find_public_blog_post_page_response.json()
    assert find_public_blog_post_page_response.status_code == 422
    assert response_body["detail"][0]["loc"] == expected_error_location


async def test_find_public_blog_post_page_pages_and_reports_total_of_every_row(
    api_client: AsyncClient, signed_in_user: UserOrm, db_session: AsyncSession
) -> None:
    persona_record = await insert_persona_row(
        db_session, created_by_id=signed_in_user.id, is_public=True
    )
    for title in ["Post 1", "Post 2", "Post 3"]:
        await _insert_own_blog_post(
            db_session, user_record=signed_in_user, persona_id=persona_record.id, title=title
        )
    await db_session.commit()

    find_public_blog_post_page_response = await api_client.get(
        "/blog-posts/public", params={"page": "2", "page_size": "2"}
    )

    response_body = find_public_blog_post_page_response.json()
    assert [blog_post["title"] for blog_post in response_body["blog_posts"]] == ["Post 1"]
    assert response_body["pagination"] == {"page": 2, "page_size": 2, "total": 3}


async def test_find_public_blog_post_page_page_past_the_end_returns_no_rows_and_same_total(
    api_client: AsyncClient, signed_in_user: UserOrm, db_session: AsyncSession
) -> None:
    persona_record = await insert_persona_row(
        db_session, created_by_id=signed_in_user.id, is_public=True
    )
    await _insert_own_blog_post(
        db_session, user_record=signed_in_user, persona_id=persona_record.id, title="Only Post"
    )
    await db_session.commit()

    find_public_blog_post_page_response = await api_client.get(
        "/blog-posts/public", params={"page": "5"}
    )

    assert find_public_blog_post_page_response.json() == {
        "blog_posts": [],
        "pagination": {"page": 5, "page_size": 20, "total": 1},
    }


@pytest.mark.parametrize(
    ("sort_direction", "expected_titles"),
    [
        pytest.param("DESC", ["High", "Low", "Unscored"], id="descending"),
        pytest.param("ASC", ["Low", "High", "Unscored"], id="ascending"),
    ],
)
async def test_find_public_blog_post_page_sorted_by_feed_score(
    api_client: AsyncClient,
    signed_in_user: UserOrm,
    db_session: AsyncSession,
    sort_direction: str,
    expected_titles: list[str],
) -> None:
    persona_record = await insert_persona_row(
        db_session, created_by_id=signed_in_user.id, is_public=True
    )
    for title, feed_score in [("Low", 1.5), ("Unscored", None), ("High", 9.5)]:
        await _insert_own_blog_post(
            db_session,
            user_record=signed_in_user,
            persona_id=persona_record.id,
            title=title,
            feed_score=feed_score,
        )
    await db_session.commit()

    find_public_blog_post_page_response = await api_client.get(
        "/blog-posts/public", params={"sort_by": "FEED_SCORE", "sort_direction": sort_direction}
    )

    response_body = find_public_blog_post_page_response.json()
    assert find_public_blog_post_page_response.status_code == 200
    assert [blog_post["title"] for blog_post in response_body["blog_posts"]] == expected_titles


async def test_find_public_blog_post_page_search_matches_persona_name(
    api_client: AsyncClient, signed_in_user: UserOrm, db_session: AsyncSession
) -> None:
    for persona_name, title in [("Slow Mornings Sam", "Toast"), ("Night Owl Nora", "Tea")]:
        persona_record = await insert_persona_row(
            db_session, created_by_id=signed_in_user.id, name=persona_name, is_public=True
        )
        await _insert_own_blog_post(
            db_session, user_record=signed_in_user, persona_id=persona_record.id, title=title
        )
    await db_session.commit()

    find_public_blog_post_page_response = await api_client.get(
        "/blog-posts/public", params={"search": "night owl"}
    )

    response_body = find_public_blog_post_page_response.json()
    assert [blog_post["title"] for blog_post in response_body["blog_posts"]] == ["Tea"]
    assert response_body["blog_posts"][0]["persona_name"] == "Night Owl Nora"


@pytest.mark.parametrize(
    ("sort_direction", "expected_titles"),
    [
        pytest.param("ASC", ["Apple", "Banana", "Cherry"], id="ascending"),
        pytest.param("DESC", ["Cherry", "Banana", "Apple"], id="descending"),
    ],
)
async def test_find_public_blog_post_page_sorted_by_title(
    api_client: AsyncClient,
    signed_in_user: UserOrm,
    db_session: AsyncSession,
    sort_direction: str,
    expected_titles: list[str],
) -> None:
    persona_record = await insert_persona_row(
        db_session, created_by_id=signed_in_user.id, is_public=True
    )
    for title in ["Banana", "Cherry", "Apple"]:
        await _insert_own_blog_post(
            db_session, user_record=signed_in_user, persona_id=persona_record.id, title=title
        )
    await db_session.commit()

    find_public_blog_post_page_response = await api_client.get(
        "/blog-posts/public", params={"sort_by": "TITLE", "sort_direction": sort_direction}
    )

    response_body = find_public_blog_post_page_response.json()
    assert [blog_post["title"] for blog_post in response_body["blog_posts"]] == expected_titles


async def test_find_public_blog_post_page_persona_identity_limits_rows_to_that_persona(
    api_client: AsyncClient, signed_in_user: UserOrm, db_session: AsyncSession
) -> None:
    matching_persona_record = await insert_persona_row(
        db_session, created_by_id=signed_in_user.id, is_public=True
    )
    other_persona_record = await insert_persona_row(
        db_session, created_by_id=signed_in_user.id, is_public=True
    )
    await _insert_own_blog_post(
        db_session,
        user_record=signed_in_user,
        persona_id=matching_persona_record.id,
        title="Matching Post",
    )
    await _insert_own_blog_post(
        db_session,
        user_record=signed_in_user,
        persona_id=other_persona_record.id,
        title="Other Persona Post",
    )
    await db_session.commit()

    find_public_blog_post_page_response = await api_client.get(
        "/blog-posts/public", params={"persona_identity": str(matching_persona_record.identity)}
    )

    response_body = find_public_blog_post_page_response.json()
    assert [blog_post["title"] for blog_post in response_body["blog_posts"]] == ["Matching Post"]
    assert response_body["pagination"]["total"] == 1


@pytest.mark.parametrize(
    ("search", "expected_titles"),
    [
        pytest.param("coffee", ["Morning Coffee"], id="title"),
        pytest.param("brewing", ["Morning Coffee"], id="subtitle"),
        pytest.param("zebra", [], id="body_is_not_searched"),
        pytest.param("%", [], id="percent_is_literal"),
        pytest.param("   ", ["Evening Tea", "Morning Coffee"], id="whitespace_means_no_search"),
    ],
)
async def test_find_public_blog_post_page_search(
    api_client: AsyncClient,
    signed_in_user: UserOrm,
    db_session: AsyncSession,
    search: str,
    expected_titles: list[str],
) -> None:
    persona_record = await insert_persona_row(
        db_session, created_by_id=signed_in_user.id, is_public=True
    )
    await _insert_own_blog_post(
        db_session,
        user_record=signed_in_user,
        persona_id=persona_record.id,
        title="Morning Coffee",
        subtitle="Slow brewing",
        body="A body mentioning a zebra.",
    )
    await _insert_own_blog_post(
        db_session, user_record=signed_in_user, persona_id=persona_record.id, title="Evening Tea"
    )
    await db_session.commit()

    find_public_blog_post_page_response = await api_client.get(
        "/blog-posts/public", params={"search": search, "sort_by": "TITLE", "sort_direction": "ASC"}
    )

    response_body = find_public_blog_post_page_response.json()
    assert [blog_post["title"] for blog_post in response_body["blog_posts"]] == expected_titles
