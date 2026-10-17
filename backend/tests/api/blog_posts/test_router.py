from datetime import UTC, datetime
from unittest.mock import ANY
from uuid import UUID, uuid4

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from libs.core.services import BackgroundJobService
from libs.database.orm import BlogPostOrm, ContentItemOrm, GenerateTextRunOrm, UserOrm
from libs.generate_text.types import GenerateTextRunStatusType, GenerateTextStepStatusType
from tests.factories.blog_posts import VALID_BLOG_POST_BODY, insert_blog_post_row
from tests.factories.content_items import insert_content_item_row
from tests.factories.generate_text import (
    insert_generate_text_run_row,
    insert_generate_text_step_row,
)
from tests.factories.llm import build_llm_completion_result
from tests.factories.personas import insert_persona_row
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

    find_blog_post_response = await api_client.get(f"/blog-posts/{blog_post_record.identity}")

    assert find_blog_post_response.status_code == 200
    assert find_blog_post_response.json() == {
        "identity": str(blog_post_record.identity),
        "persona_identity": persona_identity,
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
    # Setup bypasses generation: the real draft step already fails its own format check
    # (BlogPostBodyOutputFormat.validate_output) before a run with no leading "# Title" can
    # ever reach COMPLETED, so the run and its step output are built directly here instead.
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


async def test_find_user_blog_post_list_returns_only_signed_in_users_newest_first(
    api_client: AsyncClient,
    signed_in_user: UserOrm,
    db_session: AsyncSession,
    other_user_client: AsyncClient,
) -> None:
    persona_record = await insert_persona_row(db_session, created_by_id=signed_in_user.id)
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
        title="Oldest Post",
    )
    newest_content_item_record = await insert_content_item_row(
        db_session,
        created_by_id=signed_in_user.id,
        persona_id=persona_record.id,
        created_at=datetime(2026, 1, 3, tzinfo=UTC),
    )
    newest_blog_post_record = await insert_blog_post_row(
        db_session,
        created_by_id=signed_in_user.id,
        content_item_id=newest_content_item_record.id,
        title="Newest Post",
    )
    await db_session.commit()
    other_create_persona_response = await other_user_client.post(
        "/personas", json={"name": "Other Persona", "bio": "Writes essays.", "is_public": True}
    )
    other_persona_identity = other_create_persona_response.json()["identity"]
    await other_user_client.post(
        "/blog-posts",
        json={
            "persona_identity": other_persona_identity,
            "title": "Other User's Post",
            "body": VALID_BLOG_POST_BODY,
            "is_public": True,
            "published_at": "2020-01-01T00:00:00+00:00",
        },
    )

    find_user_blog_post_list_response = await api_client.get("/blog-posts")

    assert find_user_blog_post_list_response.status_code == 200
    assert find_user_blog_post_list_response.json() == {
        "blog_posts": [
            {
                "identity": str(newest_blog_post_record.identity),
                "persona_identity": str(persona_record.identity),
                "title": "Newest Post",
                "subtitle": None,
                "body": VALID_BLOG_POST_BODY,
                "is_public": False,
                "published_at": None,
                "created_at": ANY,
                "updated_at": ANY,
            },
            {
                "identity": str(oldest_blog_post_record.identity),
                "persona_identity": str(persona_record.identity),
                "title": "Oldest Post",
                "subtitle": None,
                "body": VALID_BLOG_POST_BODY,
                "is_public": False,
                "published_at": None,
                "created_at": ANY,
                "updated_at": ANY,
            },
        ]
    }


async def test_find_user_blog_post_list_filters_by_persona_identity(
    api_client: AsyncClient, signed_in_user: UserOrm, db_session: AsyncSession
) -> None:
    matching_persona_record = await insert_persona_row(db_session, created_by_id=signed_in_user.id)
    other_persona_record = await insert_persona_row(db_session, created_by_id=signed_in_user.id)
    matching_content_item_record = await insert_content_item_row(
        db_session, created_by_id=signed_in_user.id, persona_id=matching_persona_record.id
    )
    matching_blog_post_record = await insert_blog_post_row(
        db_session,
        created_by_id=signed_in_user.id,
        content_item_id=matching_content_item_record.id,
        title="Matching Post",
    )
    other_content_item_record = await insert_content_item_row(
        db_session, created_by_id=signed_in_user.id, persona_id=other_persona_record.id
    )
    await insert_blog_post_row(
        db_session,
        created_by_id=signed_in_user.id,
        content_item_id=other_content_item_record.id,
        title="Other Post",
    )
    await db_session.commit()

    find_user_blog_post_list_response = await api_client.get(
        "/blog-posts", params={"persona_identity": str(matching_persona_record.identity)}
    )

    response_body = find_user_blog_post_list_response.json()
    assert find_user_blog_post_list_response.status_code == 200
    assert [blog_post["identity"] for blog_post in response_body["blog_posts"]] == [
        str(matching_blog_post_record.identity)
    ]


@pytest.mark.usefixtures("signed_in_user")
async def test_find_user_blog_post_list_malformed_filter_returns_422(
    api_client: AsyncClient,
) -> None:
    find_user_blog_post_list_response = await api_client.get(
        "/blog-posts", params={"persona_identity": "not-a-uuid"}
    )

    response_body = find_user_blog_post_list_response.json()
    assert find_user_blog_post_list_response.status_code == 422
    assert response_body["detail"][0]["loc"] == ["query", "persona_identity"]


async def test_find_user_blog_post_list_excludes_deleted(
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

    find_user_blog_post_list_response = await api_client.get("/blog-posts")

    assert find_user_blog_post_list_response.status_code == 200
    assert find_user_blog_post_list_response.json() == {"blog_posts": []}


async def test_find_user_blog_post_list_signed_out_returns_401(api_client: AsyncClient) -> None:
    find_user_blog_post_list_response = await api_client.get("/blog-posts")

    assert find_user_blog_post_list_response.status_code == 401


async def test_find_blog_post_returns_blog_post_response(
    api_client: AsyncClient, signed_in_user: UserOrm, db_session: AsyncSession
) -> None:
    persona_record = await insert_persona_row(db_session, created_by_id=signed_in_user.id)
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
        "persona_identity": str(persona_record.identity),
        "title": "A Title",
        "subtitle": "A Subtitle",
        "body": VALID_BLOG_POST_BODY,
        "is_public": False,
        "published_at": None,
        "created_at": ANY,
        "updated_at": ANY,
    }


async def test_find_blog_post_never_inserted_returns_404(
    api_client: AsyncClient, signed_in_user: UserOrm
) -> None:
    find_blog_post_response = await api_client.get(f"/blog-posts/{uuid4()}")

    assert find_blog_post_response.status_code == 404


async def test_find_blog_post_another_users_public_published_post_on_public_persona_returns_200(
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

    find_blog_post_response = await api_client.get(f"/blog-posts/{other_blog_post_identity}")

    assert find_blog_post_response.status_code == 200
    assert find_blog_post_response.json() == {
        "identity": other_blog_post_identity,
        "persona_identity": other_persona_identity,
        "title": "Public Post",
        "subtitle": None,
        "body": VALID_BLOG_POST_BODY,
        "is_public": True,
        "published_at": "2020-01-01T00:00:00Z",
        "created_at": ANY,
        "updated_at": ANY,
    }


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
