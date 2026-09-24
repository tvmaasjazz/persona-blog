from unittest.mock import ANY
from uuid import uuid4

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.core.config import AppSettings
from libs.auth.services import AuthSessionService
from libs.database.orm import UserOrm
from tests.factories.llm import build_llm_completion_result
from tests.factories.users import insert_user_row
from tests.stubs.llm import LlmServiceStub


async def test_generate_text_returns_awaiting_review_with_draft_and_thread_identity(
    api_client: AsyncClient, signed_in_user: UserOrm, llm_service_stub: LlmServiceStub
) -> None:
    llm_service_stub.complete_result = build_llm_completion_result(content="A draft about coffee.")

    generate_text_response = await api_client.post(
        "/generate-text/",
        json={"text_type": "BLOG_POST", "prompt_text": "Write about coffee."},
    )

    assert generate_text_response.status_code == 200
    assert generate_text_response.json() == {
        "thread_identity": ANY,
        "status": "AWAITING_REVIEW",
        "content": "A draft about coffee.",
        "character_count": 21,
    }


async def test_resume_generate_text_rejection_rewrites_and_returns_awaiting_review(
    api_client: AsyncClient, signed_in_user: UserOrm, llm_service_stub: LlmServiceStub
) -> None:
    llm_service_stub.complete_result = build_llm_completion_result(content="A draft about coffee.")
    generate_text_response = await api_client.post(
        "/generate-text/",
        json={"text_type": "BLOG_POST", "prompt_text": "Write about coffee."},
    )
    thread_identity = generate_text_response.json()["thread_identity"]

    llm_service_stub.complete_result = build_llm_completion_result(content="A revised draft.")
    resume_generate_text_response = await api_client.post(
        f"/generate-text/{thread_identity}/resume",
        json={"is_approved": False, "feedback_text": "Make it shorter."},
    )

    assert resume_generate_text_response.status_code == 200
    assert resume_generate_text_response.json() == {
        "thread_identity": thread_identity,
        "status": "AWAITING_REVIEW",
        "content": "A revised draft.",
        "character_count": 16,
    }


async def test_resume_generate_text_approval_returns_completed(
    api_client: AsyncClient, signed_in_user: UserOrm, llm_service_stub: LlmServiceStub
) -> None:
    llm_service_stub.complete_result = build_llm_completion_result(content="A draft about coffee.")
    generate_text_response = await api_client.post(
        "/generate-text/",
        json={"text_type": "BLOG_POST", "prompt_text": "Write about coffee."},
    )
    thread_identity = generate_text_response.json()["thread_identity"]

    resume_generate_text_response = await api_client.post(
        f"/generate-text/{thread_identity}/resume",
        json={"is_approved": True, "feedback_text": None},
    )

    assert resume_generate_text_response.status_code == 200
    assert resume_generate_text_response.json() == {
        "thread_identity": thread_identity,
        "status": "COMPLETED",
        "content": "A draft about coffee.",
        "character_count": 21,
    }


async def test_generate_text_signed_out_returns_401(api_client: AsyncClient) -> None:
    generate_text_response = await api_client.post(
        "/generate-text/",
        json={"text_type": "BLOG_POST", "prompt_text": "Write about coffee."},
    )

    assert generate_text_response.status_code == 401


async def test_resume_generate_text_signed_out_returns_401(api_client: AsyncClient) -> None:
    resume_generate_text_response = await api_client.post(
        f"/generate-text/{uuid4()}/resume",
        json={"is_approved": True, "feedback_text": None},
    )

    assert resume_generate_text_response.status_code == 401


async def test_generate_text_invalid_text_type_returns_422(
    api_client: AsyncClient, signed_in_user: UserOrm
) -> None:
    generate_text_response = await api_client.post(
        "/generate-text/",
        json={"text_type": "NEWSLETTER", "prompt_text": "Write about coffee."},
    )

    response_body = generate_text_response.json()
    assert generate_text_response.status_code == 422
    assert response_body["detail"][0]["loc"] == ["body", "text_type"]


async def test_resume_generate_text_another_users_thread_returns_404(
    api_client: AsyncClient,
    signed_in_user: UserOrm,
    llm_service_stub: LlmServiceStub,
    fastapi_app: FastAPI,
    db_session: AsyncSession,
    redis_client: Redis,
    app_settings: AppSettings,
) -> None:
    llm_service_stub.complete_result = build_llm_completion_result(content="A draft about coffee.")
    generate_text_response = await api_client.post(
        "/generate-text/",
        json={"text_type": "BLOG_POST", "prompt_text": "Write about coffee."},
    )
    thread_identity = generate_text_response.json()["thread_identity"]

    other_user_record = await insert_user_row(db_session)
    auth_session_service = AuthSessionService(
        redis_client=redis_client, auth_settings=app_settings.auth
    )
    other_session_id = await auth_session_service.create_session(
        user_id=other_user_record.id, user_identity=other_user_record.identity
    )
    other_api_transport = ASGITransport(app=fastapi_app)
    async with AsyncClient(
        transport=other_api_transport, base_url="https://test", cookies={"sid": other_session_id}
    ) as other_api_client:
        resume_generate_text_response = await other_api_client.post(
            f"/generate-text/{thread_identity}/resume",
            json={"is_approved": True, "feedback_text": None},
        )

    assert resume_generate_text_response.status_code == 404


async def test_resume_generate_text_finished_thread_returns_409(
    api_client: AsyncClient, signed_in_user: UserOrm, llm_service_stub: LlmServiceStub
) -> None:
    llm_service_stub.complete_result = build_llm_completion_result(content="A draft about coffee.")
    generate_text_response = await api_client.post(
        "/generate-text/",
        json={"text_type": "BLOG_POST", "prompt_text": "Write about coffee."},
    )
    thread_identity = generate_text_response.json()["thread_identity"]
    await api_client.post(
        f"/generate-text/{thread_identity}/resume",
        json={"is_approved": True, "feedback_text": None},
    )

    resume_generate_text_response = await api_client.post(
        f"/generate-text/{thread_identity}/resume",
        json={"is_approved": True, "feedback_text": None},
    )

    assert resume_generate_text_response.status_code == 409


@pytest.mark.usefixtures("signed_in_user")
async def test_resume_generate_text_malformed_thread_identity_returns_422(
    api_client: AsyncClient,
) -> None:
    resume_generate_text_response = await api_client.post(
        "/generate-text/not-a-uuid/resume",
        json={"is_approved": True, "feedback_text": None},
    )

    response_body = resume_generate_text_response.json()
    assert resume_generate_text_response.status_code == 422
    assert response_body["detail"][0]["loc"] == ["path", "thread_identity"]
