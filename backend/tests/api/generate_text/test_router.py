from unittest.mock import ANY
from uuid import UUID, uuid4

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from libs.database.orm import PersonaOrm, UserOrm
from libs.database.orm.generate_text_run import GenerateTextRunOrm
from libs.generate_text.types import GenerateTextRunStatusType
from tests.factories.generate_text import insert_generate_text_run_row
from tests.factories.llm import build_llm_completion_result
from tests.stubs.llm import LlmServiceStub

pytestmark = pytest.mark.usefixtures("llm_service_stub")


async def _create_persona(api_client: AsyncClient) -> str:
    create_persona_response = await api_client.post(
        "/personas",
        json={"name": "Marta Quill", "bio": "Writes about slow mornings."},
    )
    return create_persona_response.json()["identity"]


async def _create_review_pending_run(
    api_client: AsyncClient, llm_service_stub: LlmServiceStub, persona_identity: str
) -> str:
    llm_service_stub.complete_result = build_llm_completion_result(content="# Draft\n\nA draft.")
    generate_blog_post_response = await api_client.post(
        "/generate-text/blog-post",
        json={
            "prompt_text": "Write about sourdough starters.",
            "persona_identity": persona_identity,
            "options": {"draft": {"is_auto_approved": False}},
        },
    )
    return generate_blog_post_response.json()["run_identity"]


async def test_generate_blog_post_default_options_returns_completed(
    api_client: AsyncClient, signed_in_user: UserOrm, llm_service_stub: LlmServiceStub
) -> None:
    persona_identity = await _create_persona(api_client)
    llm_service_stub.complete_result = build_llm_completion_result(
        content="# Finished\n\nA finished blog post."
    )

    generate_blog_post_response = await api_client.post(
        "/generate-text/blog-post",
        json={
            "prompt_text": "Write about sourdough starters.",
            "persona_identity": persona_identity,
            "options": {},
        },
    )

    assert generate_blog_post_response.status_code == 200
    assert generate_blog_post_response.json() == {
        "run_identity": ANY,
        "text_type": "BLOG_POST",
        "status": "COMPLETED",
        "last_step": "GENERATE_DRAFT",
        "graph_name": "blog_post",
        "graph_version": "2026-10-07.2",
        "content": "# Finished\n\nA finished blog post.",
        "character_count": 33,
        "llm_call_count": 0,
        "input_tokens": 0,
        "output_tokens": 0,
        "cost_usd": "0E-10",
        "started_at": ANY,
        "finished_at": ANY,
    }


async def test_generate_blog_post_persists_run_row_with_persona_tone_and_target_audience(
    api_client: AsyncClient,
    signed_in_user: UserOrm,
    llm_service_stub: LlmServiceStub,
    db_session: AsyncSession,
) -> None:
    persona_identity = await _create_persona(api_client)
    llm_service_stub.complete_result = build_llm_completion_result(
        content="# Finished\n\nA finished blog post."
    )

    generate_blog_post_response = await api_client.post(
        "/generate-text/blog-post",
        json={
            "prompt_text": "Write about sourdough starters.",
            "persona_identity": persona_identity,
            "tone": "Playful",
            "target_audience": "Home bakers",
            "options": {},
        },
    )

    run_identity = UUID(generate_blog_post_response.json()["run_identity"])
    run_query = select(GenerateTextRunOrm).where(GenerateTextRunOrm.identity == run_identity)
    run_record = await db_session.scalar(run_query)
    persona_query = select(PersonaOrm).where(PersonaOrm.identity == UUID(persona_identity))
    persona_record = await db_session.scalar(persona_query)
    assert run_record is not None
    assert run_record.status == GenerateTextRunStatusType.COMPLETED
    assert run_record.prompt_text == "Write about sourdough starters."
    assert run_record.created_by_id == signed_in_user.id
    assert run_record.persona_id == persona_record.id
    assert run_record.tone == "Playful"
    assert run_record.target_audience == "Home bakers"


async def test_generate_blog_post_step_not_auto_approved_returns_awaiting_review(
    api_client: AsyncClient, signed_in_user: UserOrm, llm_service_stub: LlmServiceStub
) -> None:
    persona_identity = await _create_persona(api_client)
    llm_service_stub.complete_result = build_llm_completion_result(content="# Draft\n\nA draft.")

    generate_blog_post_response = await api_client.post(
        "/generate-text/blog-post",
        json={
            "prompt_text": "Write about sourdough starters.",
            "persona_identity": persona_identity,
            "options": {"draft": {"is_auto_approved": False}},
        },
    )

    assert generate_blog_post_response.status_code == 200
    assert generate_blog_post_response.json() == {
        "run_identity": ANY,
        "text_type": "BLOG_POST",
        "status": "AWAITING_REVIEW",
        "last_step": "REVIEW_DRAFT",
        "graph_name": "blog_post",
        "graph_version": "2026-10-07.2",
        "content": "# Draft\n\nA draft.",
        "character_count": 17,
        "llm_call_count": 0,
        "input_tokens": 0,
        "output_tokens": 0,
        "cost_usd": "0E-10",
        "started_at": ANY,
        "finished_at": None,
    }


async def test_generate_blog_post_signed_out_returns_401(api_client: AsyncClient) -> None:
    generate_blog_post_response = await api_client.post(
        "/generate-text/blog-post",
        json={
            "prompt_text": "Write about sourdough starters.",
            "persona_identity": str(uuid4()),
            "options": {},
        },
    )

    assert generate_blog_post_response.status_code == 401


@pytest.mark.usefixtures("signed_in_user")
@pytest.mark.parametrize(
    ("request_body", "expected_error_location"),
    [
        pytest.param(
            {"persona_identity": str(uuid4()), "options": {}},
            ["body", "prompt_text"],
            id="missing_prompt_text",
        ),
        pytest.param(
            {"prompt_text": "Write about sourdough starters.", "options": {}},
            ["body", "persona_identity"],
            id="missing_persona_identity",
        ),
        pytest.param(
            {
                "prompt_text": "Write about sourdough starters.",
                "persona_identity": "not-a-uuid",
                "options": {},
            },
            ["body", "persona_identity"],
            id="malformed_persona_identity",
        ),
        pytest.param(
            {"prompt_text": "Write about sourdough starters.", "persona_identity": str(uuid4())},
            ["body", "options"],
            id="missing_options",
        ),
        pytest.param(
            {
                "prompt_text": "Write about sourdough starters.",
                "persona_identity": str(uuid4()),
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


async def test_generate_blog_post_draft_never_validates_returns_503(
    api_client: AsyncClient, signed_in_user: UserOrm, llm_service_stub: LlmServiceStub
) -> None:
    persona_identity = await _create_persona(api_client)
    llm_service_stub.complete_result = build_llm_completion_result(content="Not valid markdown.")

    generate_blog_post_response = await api_client.post(
        "/generate-text/blog-post",
        json={
            "prompt_text": "Write about sourdough starters.",
            "persona_identity": persona_identity,
            "options": {},
        },
    )

    assert generate_blog_post_response.status_code == 503


@pytest.mark.usefixtures("signed_in_user")
async def test_generate_blog_post_unknown_persona_returns_404(api_client: AsyncClient) -> None:
    generate_blog_post_response = await api_client.post(
        "/generate-text/blog-post",
        json={
            "prompt_text": "Write about sourdough starters.",
            "persona_identity": str(uuid4()),
            "options": {},
        },
    )

    assert generate_blog_post_response.status_code == 404


async def test_generate_blog_post_another_users_private_persona_returns_404(
    api_client: AsyncClient,
    signed_in_user: UserOrm,
    other_user_client: AsyncClient,
) -> None:
    persona_identity = await _create_persona(other_user_client)

    generate_blog_post_response = await api_client.post(
        "/generate-text/blog-post",
        json={
            "prompt_text": "Write about sourdough starters.",
            "persona_identity": persona_identity,
            "options": {},
        },
    )

    assert generate_blog_post_response.status_code == 404


async def test_generate_blog_post_another_users_public_persona_returns_404(
    api_client: AsyncClient,
    signed_in_user: UserOrm,
    other_user_client: AsyncClient,
) -> None:
    create_persona_response = await other_user_client.post(
        "/personas",
        json={"name": "Marta Quill", "bio": "Writes about slow mornings.", "is_public": True},
    )
    persona_identity = create_persona_response.json()["identity"]

    generate_blog_post_response = await api_client.post(
        "/generate-text/blog-post",
        json={
            "prompt_text": "Write about sourdough starters.",
            "persona_identity": persona_identity,
            "options": {},
        },
    )

    assert generate_blog_post_response.status_code == 404


async def test_find_generate_text_run_returns_run_response(
    api_client: AsyncClient, signed_in_user: UserOrm, llm_service_stub: LlmServiceStub
) -> None:
    persona_identity = await _create_persona(api_client)
    run_identity = await _create_review_pending_run(api_client, llm_service_stub, persona_identity)

    find_generate_text_run_response = await api_client.get(f"/generate-text/runs/{run_identity}")

    assert find_generate_text_run_response.status_code == 200
    assert find_generate_text_run_response.json() == {
        "run_identity": run_identity,
        "text_type": "BLOG_POST",
        "status": "AWAITING_REVIEW",
        "last_step": "REVIEW_DRAFT",
        "graph_name": "blog_post",
        "graph_version": "2026-10-07.2",
        "content": "# Draft\n\nA draft.",
        "character_count": 17,
        "llm_call_count": 0,
        "input_tokens": 0,
        "output_tokens": 0,
        "cost_usd": "0E-10",
        "started_at": ANY,
        "finished_at": None,
    }


async def test_find_generate_text_run_signed_out_returns_401(api_client: AsyncClient) -> None:
    find_generate_text_run_response = await api_client.get(f"/generate-text/runs/{uuid4()}")

    assert find_generate_text_run_response.status_code == 401


@pytest.mark.usefixtures("signed_in_user")
async def test_find_generate_text_run_malformed_identity_returns_422(
    api_client: AsyncClient,
) -> None:
    find_generate_text_run_response = await api_client.get("/generate-text/runs/not-a-uuid")

    response_body = find_generate_text_run_response.json()
    assert find_generate_text_run_response.status_code == 422
    assert response_body["detail"][0]["loc"] == ["path", "run_identity"]


async def test_find_generate_text_run_another_users_run_returns_404(
    api_client: AsyncClient,
    signed_in_user: UserOrm,
    llm_service_stub: LlmServiceStub,
    other_user_client: AsyncClient,
) -> None:
    persona_identity = await _create_persona(api_client)
    run_identity = await _create_review_pending_run(api_client, llm_service_stub, persona_identity)

    find_generate_text_run_response = await other_user_client.get(
        f"/generate-text/runs/{run_identity}"
    )

    assert find_generate_text_run_response.status_code == 404


async def test_resume_generate_text_approval_returns_completed(
    api_client: AsyncClient, signed_in_user: UserOrm, llm_service_stub: LlmServiceStub
) -> None:
    persona_identity = await _create_persona(api_client)
    run_identity = await _create_review_pending_run(api_client, llm_service_stub, persona_identity)

    resume_generate_text_response = await api_client.post(
        f"/generate-text/runs/{run_identity}/resume",
        json={"is_approved": True, "feedback_text": None},
    )

    assert resume_generate_text_response.status_code == 200
    assert resume_generate_text_response.json() == {
        "run_identity": run_identity,
        "text_type": "BLOG_POST",
        "status": "COMPLETED",
        "last_step": "REVIEW_DRAFT",
        "graph_name": "blog_post",
        "graph_version": "2026-10-07.2",
        "content": "# Draft\n\nA draft.",
        "character_count": 17,
        "llm_call_count": 0,
        "input_tokens": 0,
        "output_tokens": 0,
        "cost_usd": "0E-10",
        "started_at": ANY,
        "finished_at": ANY,
    }


async def test_resume_generate_text_rejection_rewrites_and_returns_awaiting_review(
    api_client: AsyncClient, signed_in_user: UserOrm, llm_service_stub: LlmServiceStub
) -> None:
    persona_identity = await _create_persona(api_client)
    run_identity = await _create_review_pending_run(api_client, llm_service_stub, persona_identity)

    llm_service_stub.complete_result = build_llm_completion_result(
        content="# Draft\n\nA revised draft."
    )
    resume_generate_text_response = await api_client.post(
        f"/generate-text/runs/{run_identity}/resume",
        json={"is_approved": False, "feedback_text": "Make it shorter."},
    )

    assert resume_generate_text_response.status_code == 200
    assert resume_generate_text_response.json() == {
        "run_identity": run_identity,
        "text_type": "BLOG_POST",
        "status": "AWAITING_REVIEW",
        "last_step": "REVIEW_DRAFT",
        "graph_name": "blog_post",
        "graph_version": "2026-10-07.2",
        "content": "# Draft\n\nA revised draft.",
        "character_count": 25,
        "llm_call_count": 0,
        "input_tokens": 0,
        "output_tokens": 0,
        "cost_usd": "0E-10",
        "started_at": ANY,
        "finished_at": None,
    }


async def test_resume_generate_text_signed_out_returns_401(api_client: AsyncClient) -> None:
    resume_generate_text_response = await api_client.post(
        f"/generate-text/runs/{uuid4()}/resume",
        json={"is_approved": True, "feedback_text": None},
    )

    assert resume_generate_text_response.status_code == 401


@pytest.mark.usefixtures("signed_in_user")
async def test_resume_generate_text_malformed_identity_returns_422(api_client: AsyncClient) -> None:
    resume_generate_text_response = await api_client.post(
        "/generate-text/runs/not-a-uuid/resume",
        json={"is_approved": True, "feedback_text": None},
    )

    response_body = resume_generate_text_response.json()
    assert resume_generate_text_response.status_code == 422
    assert response_body["detail"][0]["loc"] == ["path", "run_identity"]


async def test_resume_generate_text_missing_is_approved_returns_422(
    api_client: AsyncClient, signed_in_user: UserOrm, llm_service_stub: LlmServiceStub
) -> None:
    persona_identity = await _create_persona(api_client)
    run_identity = await _create_review_pending_run(api_client, llm_service_stub, persona_identity)

    resume_generate_text_response = await api_client.post(
        f"/generate-text/runs/{run_identity}/resume", json={"feedback_text": "Make it shorter."}
    )

    response_body = resume_generate_text_response.json()
    assert resume_generate_text_response.status_code == 422
    assert response_body["detail"][0]["loc"] == ["body", "is_approved"]


async def test_resume_generate_text_another_users_run_returns_404(
    api_client: AsyncClient,
    signed_in_user: UserOrm,
    llm_service_stub: LlmServiceStub,
    other_user_client: AsyncClient,
) -> None:
    persona_identity = await _create_persona(api_client)
    run_identity = await _create_review_pending_run(api_client, llm_service_stub, persona_identity)

    resume_generate_text_response = await other_user_client.post(
        f"/generate-text/runs/{run_identity}/resume",
        json={"is_approved": True, "feedback_text": None},
    )

    assert resume_generate_text_response.status_code == 404


async def test_resume_generate_text_finished_run_returns_409(
    api_client: AsyncClient, signed_in_user: UserOrm, llm_service_stub: LlmServiceStub
) -> None:
    persona_identity = await _create_persona(api_client)
    run_identity = await _create_review_pending_run(api_client, llm_service_stub, persona_identity)
    await api_client.post(
        f"/generate-text/runs/{run_identity}/resume",
        json={"is_approved": True, "feedback_text": None},
    )

    resume_generate_text_response = await api_client.post(
        f"/generate-text/runs/{run_identity}/resume",
        json={"is_approved": True, "feedback_text": None},
    )

    assert resume_generate_text_response.status_code == 409


async def test_resume_generate_text_version_mismatch_returns_409(
    api_client: AsyncClient, signed_in_user: UserOrm, db_session: AsyncSession
) -> None:
    run_record = await insert_generate_text_run_row(
        db_session,
        created_by_id=signed_in_user.id,
        graph_version="stale-version",
        status=GenerateTextRunStatusType.AWAITING_REVIEW,
    )
    await db_session.commit()

    resume_generate_text_response = await api_client.post(
        f"/generate-text/runs/{run_record.identity}/resume",
        json={"is_approved": True, "feedback_text": None},
    )

    assert resume_generate_text_response.status_code == 409
