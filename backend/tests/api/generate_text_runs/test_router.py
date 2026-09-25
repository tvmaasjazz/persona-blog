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
from libs.generate_text.types import GenerateTextRunStatusType
from tests.factories.generate_text import insert_generate_text_run_row
from tests.factories.llm import build_llm_completion_result
from tests.factories.users import insert_user_row
from tests.stubs.llm import LlmServiceStub


async def _create_review_pending_run(
    api_client: AsyncClient, llm_service_stub: LlmServiceStub
) -> str:
    llm_service_stub.complete_result = build_llm_completion_result(content="A draft.")
    generate_blog_post_response = await api_client.post(
        "/generate-text/blog-post",
        json={
            "prompt_text": "Write about sourdough starters.",
            "options": {"draft": {"is_auto_approved": False}},
        },
    )
    return generate_blog_post_response.json()["run_identity"]


async def _open_other_user_client(
    fastapi_app: FastAPI, db_session: AsyncSession, redis_client: Redis, app_settings: AppSettings
) -> AsyncClient:
    other_user_record = await insert_user_row(db_session)
    auth_session_service = AuthSessionService(
        redis_client=redis_client, auth_settings=app_settings.auth
    )
    other_session_id = await auth_session_service.create_session(
        user_id=other_user_record.id, user_identity=other_user_record.identity
    )
    other_api_transport = ASGITransport(app=fastapi_app)
    return AsyncClient(
        transport=other_api_transport, base_url="https://test", cookies={"sid": other_session_id}
    )


async def test_find_generate_text_run_returns_run_response(
    api_client: AsyncClient, signed_in_user: UserOrm, llm_service_stub: LlmServiceStub
) -> None:
    run_identity = await _create_review_pending_run(api_client, llm_service_stub)

    find_generate_text_run_response = await api_client.get(f"/generate-text-runs/{run_identity}")

    assert find_generate_text_run_response.status_code == 200
    assert find_generate_text_run_response.json() == {
        "run_identity": run_identity,
        "text_type": "BLOG_POST",
        "status": "AWAITING_REVIEW",
        "current_step": "REVIEW_DRAFT",
        "graph_name": "blog_post",
        "graph_version": ANY,
        "content": "A draft.",
        "character_count": 8,
        "llm_call_count": ANY,
        "input_tokens": ANY,
        "output_tokens": ANY,
        "cost_usd": ANY,
        "started_at": ANY,
        "finished_at": None,
    }


async def test_find_generate_text_run_signed_out_returns_401(api_client: AsyncClient) -> None:
    find_generate_text_run_response = await api_client.get(f"/generate-text-runs/{uuid4()}")

    assert find_generate_text_run_response.status_code == 401


@pytest.mark.usefixtures("signed_in_user")
async def test_find_generate_text_run_malformed_identity_returns_422(
    api_client: AsyncClient,
) -> None:
    find_generate_text_run_response = await api_client.get("/generate-text-runs/not-a-uuid")

    response_body = find_generate_text_run_response.json()
    assert find_generate_text_run_response.status_code == 422
    assert response_body["detail"][0]["loc"] == ["path", "run_identity"]


async def test_find_generate_text_run_another_users_run_returns_404(
    api_client: AsyncClient,
    signed_in_user: UserOrm,
    llm_service_stub: LlmServiceStub,
    fastapi_app: FastAPI,
    db_session: AsyncSession,
    redis_client: Redis,
    app_settings: AppSettings,
) -> None:
    run_identity = await _create_review_pending_run(api_client, llm_service_stub)

    async with await _open_other_user_client(
        fastapi_app, db_session, redis_client, app_settings
    ) as other_api_client:
        find_generate_text_run_response = await other_api_client.get(
            f"/generate-text-runs/{run_identity}"
        )

    assert find_generate_text_run_response.status_code == 404


async def test_resume_generate_text_approval_returns_completed(
    api_client: AsyncClient, signed_in_user: UserOrm, llm_service_stub: LlmServiceStub
) -> None:
    run_identity = await _create_review_pending_run(api_client, llm_service_stub)

    resume_generate_text_response = await api_client.post(
        f"/generate-text-runs/{run_identity}/resume",
        json={"is_approved": True, "feedback_text": None},
    )

    assert resume_generate_text_response.status_code == 200
    assert resume_generate_text_response.json() == {
        "run_identity": run_identity,
        "status": "COMPLETED",
        "current_step": "REVIEW_DRAFT",
        "content": "A draft.",
        "character_count": 8,
        "text_type": "BLOG_POST",
        "graph_name": "blog_post",
        "graph_version": ANY,
        "llm_call_count": ANY,
        "input_tokens": ANY,
        "output_tokens": ANY,
        "cost_usd": ANY,
        "started_at": ANY,
        "finished_at": ANY,
    }


async def test_resume_generate_text_rejection_rewrites_and_returns_awaiting_review(
    api_client: AsyncClient, signed_in_user: UserOrm, llm_service_stub: LlmServiceStub
) -> None:
    run_identity = await _create_review_pending_run(api_client, llm_service_stub)

    llm_service_stub.complete_result = build_llm_completion_result(content="A revised draft.")
    resume_generate_text_response = await api_client.post(
        f"/generate-text-runs/{run_identity}/resume",
        json={"is_approved": False, "feedback_text": "Make it shorter."},
    )

    assert resume_generate_text_response.status_code == 200
    assert resume_generate_text_response.json() == {
        "run_identity": run_identity,
        "status": "AWAITING_REVIEW",
        "current_step": "REVIEW_DRAFT",
        "content": "A revised draft.",
        "character_count": 16,
        "text_type": "BLOG_POST",
        "graph_name": "blog_post",
        "graph_version": ANY,
        "llm_call_count": ANY,
        "input_tokens": ANY,
        "output_tokens": ANY,
        "cost_usd": ANY,
        "started_at": ANY,
        "finished_at": None,
    }


async def test_resume_generate_text_signed_out_returns_401(api_client: AsyncClient) -> None:
    resume_generate_text_response = await api_client.post(
        f"/generate-text-runs/{uuid4()}/resume",
        json={"is_approved": True, "feedback_text": None},
    )

    assert resume_generate_text_response.status_code == 401


@pytest.mark.usefixtures("signed_in_user")
async def test_resume_generate_text_malformed_identity_returns_422(api_client: AsyncClient) -> None:
    resume_generate_text_response = await api_client.post(
        "/generate-text-runs/not-a-uuid/resume",
        json={"is_approved": True, "feedback_text": None},
    )

    response_body = resume_generate_text_response.json()
    assert resume_generate_text_response.status_code == 422
    assert response_body["detail"][0]["loc"] == ["path", "run_identity"]


async def test_resume_generate_text_missing_is_approved_returns_422(
    api_client: AsyncClient, signed_in_user: UserOrm, llm_service_stub: LlmServiceStub
) -> None:
    run_identity = await _create_review_pending_run(api_client, llm_service_stub)

    resume_generate_text_response = await api_client.post(
        f"/generate-text-runs/{run_identity}/resume", json={"feedback_text": "Make it shorter."}
    )

    response_body = resume_generate_text_response.json()
    assert resume_generate_text_response.status_code == 422
    assert response_body["detail"][0]["loc"] == ["body", "is_approved"]


async def test_resume_generate_text_another_users_run_returns_404(
    api_client: AsyncClient,
    signed_in_user: UserOrm,
    llm_service_stub: LlmServiceStub,
    fastapi_app: FastAPI,
    db_session: AsyncSession,
    redis_client: Redis,
    app_settings: AppSettings,
) -> None:
    run_identity = await _create_review_pending_run(api_client, llm_service_stub)

    async with await _open_other_user_client(
        fastapi_app, db_session, redis_client, app_settings
    ) as other_api_client:
        resume_generate_text_response = await other_api_client.post(
            f"/generate-text-runs/{run_identity}/resume",
            json={"is_approved": True, "feedback_text": None},
        )

    assert resume_generate_text_response.status_code == 404


async def test_resume_generate_text_finished_run_returns_409(
    api_client: AsyncClient, signed_in_user: UserOrm, llm_service_stub: LlmServiceStub
) -> None:
    run_identity = await _create_review_pending_run(api_client, llm_service_stub)
    await api_client.post(
        f"/generate-text-runs/{run_identity}/resume",
        json={"is_approved": True, "feedback_text": None},
    )

    resume_generate_text_response = await api_client.post(
        f"/generate-text-runs/{run_identity}/resume",
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
        f"/generate-text-runs/{run_record.identity}/resume",
        json={"is_approved": True, "feedback_text": None},
    )

    assert resume_generate_text_response.status_code == 409
