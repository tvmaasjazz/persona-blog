from uuid import uuid4

import pytest

from libs.generate_text.exceptions import (
    GenerateTextThreadNotFoundException,
    GenerateTextThreadNotPausedException,
)
from libs.generate_text.results import GenerateTextResult
from libs.generate_text.services import GenerateTextService
from libs.generate_text.types import GenerateTextStatusType
from tests.factories.auth import build_auth_user
from tests.factories.generate_text import (
    build_generate_text_input,
    build_resume_generate_text_input,
)
from tests.factories.llm import build_llm_completion_result
from tests.stubs.llm import LlmServiceStub


async def test_generate_text_returns_awaiting_review_with_draft_and_thread_identity(
    generate_text_service: GenerateTextService, llm_service_stub: LlmServiceStub
) -> None:
    llm_service_stub.complete_result = build_llm_completion_result(content="A draft about coffee.")
    auth_user = build_auth_user()
    generate_text_input = build_generate_text_input(prompt_text="Write about coffee.")

    generate_text_result = await generate_text_service.generate_text(generate_text_input, auth_user)

    assert generate_text_result.status == GenerateTextStatusType.AWAITING_REVIEW
    assert generate_text_result.content == "A draft about coffee."
    assert generate_text_result.character_count == 21
    assert generate_text_result.thread_identity is not None


async def test_generate_text_character_count_matches_content(
    generate_text_service: GenerateTextService, llm_service_stub: LlmServiceStub
) -> None:
    llm_service_stub.complete_result = build_llm_completion_result(content="Short.")
    auth_user = build_auth_user()
    generate_text_input = build_generate_text_input()

    generate_text_result = await generate_text_service.generate_text(generate_text_input, auth_user)

    assert generate_text_result.character_count == 6


async def test_resume_generate_text_rejection_returns_new_draft(
    generate_text_service: GenerateTextService, llm_service_stub: LlmServiceStub
) -> None:
    llm_service_stub.complete_result = build_llm_completion_result(content="A draft about coffee.")
    auth_user = build_auth_user()
    generate_text_result = await generate_text_service.generate_text(
        build_generate_text_input(), auth_user
    )

    llm_service_stub.complete_result = build_llm_completion_result(content="A revised draft.")
    resume_generate_text_input = build_resume_generate_text_input(
        is_approved=False, feedback_text="Make it shorter."
    )
    resume_generate_text_result = await generate_text_service.resume_generate_text(
        generate_text_result.thread_identity, resume_generate_text_input, auth_user
    )

    assert resume_generate_text_result == GenerateTextResult(
        thread_identity=generate_text_result.thread_identity,
        status=GenerateTextStatusType.AWAITING_REVIEW,
        content="A revised draft.",
        character_count=16,
    )


async def test_resume_generate_text_approval_returns_completed(
    generate_text_service: GenerateTextService, llm_service_stub: LlmServiceStub
) -> None:
    llm_service_stub.complete_result = build_llm_completion_result(content="A draft about coffee.")
    auth_user = build_auth_user()
    generate_text_result = await generate_text_service.generate_text(
        build_generate_text_input(), auth_user
    )

    resume_generate_text_input = build_resume_generate_text_input(
        is_approved=True, feedback_text=None
    )
    resume_generate_text_result = await generate_text_service.resume_generate_text(
        generate_text_result.thread_identity, resume_generate_text_input, auth_user
    )

    assert resume_generate_text_result == GenerateTextResult(
        thread_identity=generate_text_result.thread_identity,
        status=GenerateTextStatusType.COMPLETED,
        content="A draft about coffee.",
        character_count=21,
    )


async def test_resume_generate_text_unknown_thread_raises_generate_text_thread_not_found_exception(
    generate_text_service: GenerateTextService,
) -> None:
    auth_user = build_auth_user()
    resume_generate_text_input = build_resume_generate_text_input()

    with pytest.raises(GenerateTextThreadNotFoundException):
        await generate_text_service.resume_generate_text(
            uuid4(), resume_generate_text_input, auth_user
        )


async def test_resume_generate_text_another_users_thread_raises_thread_not_found_exception(
    generate_text_service: GenerateTextService, llm_service_stub: LlmServiceStub
) -> None:
    llm_service_stub.complete_result = build_llm_completion_result(content="A draft about coffee.")
    generate_text_result = await generate_text_service.generate_text(
        build_generate_text_input(), build_auth_user()
    )

    resume_generate_text_input = build_resume_generate_text_input()
    with pytest.raises(GenerateTextThreadNotFoundException):
        await generate_text_service.resume_generate_text(
            generate_text_result.thread_identity, resume_generate_text_input, build_auth_user()
        )


async def test_resume_generate_text_finished_thread_raises_thread_not_paused_exception(
    generate_text_service: GenerateTextService, llm_service_stub: LlmServiceStub
) -> None:
    llm_service_stub.complete_result = build_llm_completion_result(content="A draft about coffee.")
    auth_user = build_auth_user()
    generate_text_result = await generate_text_service.generate_text(
        build_generate_text_input(), auth_user
    )
    await generate_text_service.resume_generate_text(
        generate_text_result.thread_identity,
        build_resume_generate_text_input(is_approved=True, feedback_text=None),
        auth_user,
    )

    with pytest.raises(GenerateTextThreadNotPausedException):
        await generate_text_service.resume_generate_text(
            generate_text_result.thread_identity,
            build_resume_generate_text_input(),
            auth_user,
        )
