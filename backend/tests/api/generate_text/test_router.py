from unittest.mock import ANY
from uuid import UUID

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from libs.database.orm import UserOrm
from libs.database.orm.generate_text_run import GenerateTextRunOrm
from libs.generate_text.types import GenerateTextRunStatusType
from tests.factories.llm import build_llm_completion_result
from tests.stubs.llm import LlmServiceStub


async def test_generate_blog_post_default_options_returns_completed(
    api_client: AsyncClient, signed_in_user: UserOrm, llm_service_stub: LlmServiceStub
) -> None:
    llm_service_stub.complete_result = build_llm_completion_result(content="A finished blog post.")

    generate_blog_post_response = await api_client.post(
        "/generate-text/blog-post",
        json={"prompt_text": "Write about sourdough starters.", "options": {}},
    )

    assert generate_blog_post_response.status_code == 200
    assert generate_blog_post_response.json() == {
        "run_identity": ANY,
        "status": "COMPLETED",
        "current_step": "GENERATE_DRAFT",
        "content": "A finished blog post.",
        "character_count": 21,
    }


async def test_generate_blog_post_persists_run_row(
    api_client: AsyncClient,
    signed_in_user: UserOrm,
    llm_service_stub: LlmServiceStub,
    db_session: AsyncSession,
) -> None:
    llm_service_stub.complete_result = build_llm_completion_result(content="A finished blog post.")

    generate_blog_post_response = await api_client.post(
        "/generate-text/blog-post",
        json={"prompt_text": "Write about sourdough starters.", "options": {}},
    )

    run_identity = UUID(generate_blog_post_response.json()["run_identity"])
    run_query = select(GenerateTextRunOrm).where(GenerateTextRunOrm.identity == run_identity)
    run_record = await db_session.scalar(run_query)
    assert run_record is not None
    assert run_record.status == GenerateTextRunStatusType.COMPLETED
    assert run_record.prompt_text == "Write about sourdough starters."
    assert run_record.created_by_id == signed_in_user.id


async def test_generate_blog_post_step_not_auto_approved_returns_awaiting_review(
    api_client: AsyncClient, signed_in_user: UserOrm, llm_service_stub: LlmServiceStub
) -> None:
    llm_service_stub.complete_result = build_llm_completion_result(content="A draft.")

    generate_blog_post_response = await api_client.post(
        "/generate-text/blog-post",
        json={
            "prompt_text": "Write about sourdough starters.",
            "options": {"draft": {"is_auto_approved": False}},
        },
    )

    assert generate_blog_post_response.status_code == 200
    assert generate_blog_post_response.json() == {
        "run_identity": ANY,
        "status": "AWAITING_REVIEW",
        "current_step": "REVIEW_DRAFT",
        "content": "A draft.",
        "character_count": 8,
    }


async def test_generate_blog_post_signed_out_returns_401(api_client: AsyncClient) -> None:
    generate_blog_post_response = await api_client.post(
        "/generate-text/blog-post",
        json={"prompt_text": "Write about sourdough starters.", "options": {}},
    )

    assert generate_blog_post_response.status_code == 401


@pytest.mark.usefixtures("signed_in_user")
@pytest.mark.parametrize(
    ("request_body", "expected_error_location"),
    [
        pytest.param({"options": {}}, ["body", "prompt_text"], id="missing_prompt_text"),
        pytest.param(
            {"prompt_text": "Write about sourdough starters."},
            ["body", "options"],
            id="missing_options",
        ),
        pytest.param(
            {
                "prompt_text": "Write about sourdough starters.",
                "options": {"draft": {"is_auto_approved": "not-a-bool"}},
            },
            ["body", "options", "draft", "is_auto_approved"],
            id="invalid_is_auto_approved_type",
        ),
    ],
)
async def test_generate_blog_post_invalid_body_returns_422(
    api_client: AsyncClient,
    request_body: dict,
    expected_error_location: list[str],
) -> None:
    generate_blog_post_response = await api_client.post(
        "/generate-text/blog-post", json=request_body
    )

    response_body = generate_blog_post_response.json()
    assert generate_blog_post_response.status_code == 422
    assert response_body["detail"][0]["loc"] == expected_error_location
