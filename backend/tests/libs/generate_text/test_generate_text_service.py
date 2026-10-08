from uuid import uuid4

import pytest
from langgraph.checkpoint.memory import InMemorySaver
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from libs.auth.results import AuthUser
from libs.core.exceptions import NotFoundException
from libs.database.orm.generate_text_run import GenerateTextRunOrm
from libs.database.orm.generate_text_step import GenerateTextStepOrm
from libs.generate_text.exceptions import (
    GenerateTextOptionsInvalidException,
    GenerateTextOutputInvalidException,
    GenerateTextRunNotPausedException,
    GenerateTextRunVersionMismatchException,
)
from libs.generate_text.graphs.blog_post.inputs import BlogPostOptionsInput
from libs.generate_text.graphs.generate_text_graph_builder_registry import (
    GenerateTextGraphBuilderRegistry,
)
from libs.generate_text.inputs import GenerateTextInput, StepOptionInput
from libs.generate_text.services.generate_text_instrumentation_service import (
    GenerateTextInstrumentationService,
)
from libs.generate_text.services.generate_text_node_service import GenerateTextNodeService
from libs.generate_text.services.generate_text_run_service import GenerateTextRunService
from libs.generate_text.services.generate_text_service import GenerateTextService
from libs.generate_text.services.generate_text_step_service import GenerateTextStepService
from libs.generate_text.settings import GenerateTextSettings
from libs.generate_text.types import (
    GenerateTextRunStatusType,
    GenerateTextStepStatusType,
    TextType,
)
from libs.personas.results import FindUserPersonaResult
from tests.factories.auth import build_auth_user
from tests.factories.generate_text import (
    build_generate_text_input,
    build_resume_generate_text_input,
    insert_generate_text_run_row,
)
from tests.factories.llm import build_llm_completion_result
from tests.factories.personas import build_find_user_persona_result, insert_persona_row
from tests.factories.users import insert_user_row
from tests.stubs.generate_text import GenerateTextGraphBuilderRegistryStub
from tests.stubs.llm import LlmServiceStub


class _InvalidBlogPostOptionsInput(BaseModel):
    """A wrong-shaped options payload: BlogPostOptionsInput.draft expects an object,
    not an int, so build_graph's model_validate rejects it."""

    draft: int = 5


async def _insert_auth_user(db_session: AsyncSession) -> AuthUser:
    user_record = await insert_user_row(db_session)
    await db_session.commit()
    return build_auth_user(user_id=user_record.id, user_identity=user_record.identity)


async def _insert_owner_persona(
    db_session: AsyncSession, auth_user: AuthUser
) -> FindUserPersonaResult:
    """A persona a run's real FK must point at, so every generate_text() call that
    reaches create_run needs one inserted first."""
    persona_record = await insert_persona_row(db_session, created_by_id=auth_user.id)
    await db_session.commit()
    return FindUserPersonaResult.model_validate(persona_record, from_attributes=True)


def _build_generate_text_service(
    db_session_factory: async_sessionmaker[AsyncSession],
    llm_service_stub: LlmServiceStub,
    generate_text_settings: GenerateTextSettings | None = None,
) -> GenerateTextService:
    generate_text_settings = generate_text_settings or GenerateTextSettings()
    run_service = GenerateTextRunService(db_session_factory=db_session_factory)
    step_service = GenerateTextStepService(db_session_factory=db_session_factory)
    instrumentation_service = GenerateTextInstrumentationService(
        run_service=run_service, step_service=step_service
    )
    node_service = GenerateTextNodeService(
        llm_service=llm_service_stub, generate_text_settings=generate_text_settings
    )
    graph_builder_registry = GenerateTextGraphBuilderRegistry(
        node_service=node_service,
        instrumentation_service=instrumentation_service,
        generate_text_settings=generate_text_settings,
    )
    return GenerateTextService(
        graph_builder_registry=graph_builder_registry,
        run_service=run_service,
        step_service=step_service,
        checkpointer=InMemorySaver(),
    )


def _build_generate_text_service_with_stub_registry(
    db_session_factory: async_sessionmaker[AsyncSession],
) -> tuple[GenerateTextService, GenerateTextGraphBuilderRegistryStub]:
    run_service = GenerateTextRunService(db_session_factory=db_session_factory)
    step_service = GenerateTextStepService(db_session_factory=db_session_factory)
    graph_builder_registry_stub = GenerateTextGraphBuilderRegistryStub()
    generate_text_service = GenerateTextService(
        graph_builder_registry=graph_builder_registry_stub,
        run_service=run_service,
        step_service=step_service,
        checkpointer=InMemorySaver(),
    )
    return generate_text_service, graph_builder_registry_stub


def _build_all_auto_approved_options() -> BlogPostOptionsInput:
    return BlogPostOptionsInput(
        outline=StepOptionInput(is_enabled=True, is_auto_approved=True),
        draft=StepOptionInput(is_auto_approved=True),
        humanize=StepOptionInput(is_enabled=False),
    )


def _build_draft_needs_review_options() -> BlogPostOptionsInput:
    return BlogPostOptionsInput(
        outline=None, draft=StepOptionInput(is_auto_approved=False), humanize=None
    )


async def test_generate_text_all_steps_auto_approved_returns_completed(
    db_session: AsyncSession, db_session_factory: async_sessionmaker[AsyncSession]
) -> None:
    auth_user = await _insert_auth_user(db_session)
    find_user_persona_result = await _insert_owner_persona(db_session, auth_user)
    llm_service_stub = LlmServiceStub()
    llm_service_stub.complete_result = build_llm_completion_result(content="# Final\n\nFinal text.")
    generate_text_service = _build_generate_text_service(db_session_factory, llm_service_stub)
    generate_text_input = build_generate_text_input(options=_build_all_auto_approved_options())

    generate_text_result = await generate_text_service.generate_text(
        generate_text_input, find_user_persona_result, auth_user
    )

    assert generate_text_result.status == GenerateTextRunStatusType.COMPLETED
    assert generate_text_result.last_step == "GENERATE_DRAFT"
    assert generate_text_result.content == "# Final\n\nFinal text."
    assert generate_text_result.character_count == 20


async def test_generate_text_step_not_auto_approved_returns_awaiting_review(
    db_session: AsyncSession, db_session_factory: async_sessionmaker[AsyncSession]
) -> None:
    auth_user = await _insert_auth_user(db_session)
    find_user_persona_result = await _insert_owner_persona(db_session, auth_user)
    llm_service_stub = LlmServiceStub()
    llm_service_stub.complete_result = build_llm_completion_result(content="# Draft\n\nA draft.")
    generate_text_service = _build_generate_text_service(db_session_factory, llm_service_stub)
    generate_text_input = build_generate_text_input(options=_build_draft_needs_review_options())

    generate_text_result = await generate_text_service.generate_text(
        generate_text_input, find_user_persona_result, auth_user
    )

    assert generate_text_result.status == GenerateTextRunStatusType.AWAITING_REVIEW
    assert generate_text_result.last_step == "REVIEW_DRAFT"
    assert generate_text_result.content == "# Draft\n\nA draft."
    assert generate_text_result.character_count == 17


async def test_resume_generate_text_approval_returns_completed(
    db_session: AsyncSession, db_session_factory: async_sessionmaker[AsyncSession]
) -> None:
    auth_user = await _insert_auth_user(db_session)
    find_user_persona_result = await _insert_owner_persona(db_session, auth_user)
    llm_service_stub = LlmServiceStub()
    llm_service_stub.complete_result = build_llm_completion_result(content="# Draft\n\nA draft.")
    generate_text_service = _build_generate_text_service(db_session_factory, llm_service_stub)
    generate_text_result = await generate_text_service.generate_text(
        build_generate_text_input(options=_build_draft_needs_review_options()),
        find_user_persona_result,
        auth_user,
    )

    resume_generate_text_result = await generate_text_service.resume_generate_text(
        generate_text_result.run_identity,
        build_resume_generate_text_input(is_approved=True),
        auth_user,
    )

    assert resume_generate_text_result.status == GenerateTextRunStatusType.COMPLETED
    assert resume_generate_text_result.content == "# Draft\n\nA draft."
    assert resume_generate_text_result.character_count == 17


async def test_resume_generate_text_rejection_rewrites_and_returns_awaiting_review(
    db_session: AsyncSession, db_session_factory: async_sessionmaker[AsyncSession]
) -> None:
    auth_user = await _insert_auth_user(db_session)
    find_user_persona_result = await _insert_owner_persona(db_session, auth_user)
    llm_service_stub = LlmServiceStub()
    llm_service_stub.complete_result = build_llm_completion_result(content="# Draft\n\nA draft.")
    generate_text_service = _build_generate_text_service(db_session_factory, llm_service_stub)
    generate_text_result = await generate_text_service.generate_text(
        build_generate_text_input(options=_build_draft_needs_review_options()),
        find_user_persona_result,
        auth_user,
    )

    llm_service_stub.complete_result = build_llm_completion_result(
        content="# Draft\n\nA revised draft."
    )
    resume_generate_text_result = await generate_text_service.resume_generate_text(
        generate_text_result.run_identity,
        build_resume_generate_text_input(is_approved=False, feedback_text="Make it shorter."),
        auth_user,
    )

    assert resume_generate_text_result.status == GenerateTextRunStatusType.AWAITING_REVIEW
    assert resume_generate_text_result.content == "# Draft\n\nA revised draft."
    assert resume_generate_text_result.character_count == 25


async def test_find_generate_text_run_returns_result(
    db_session: AsyncSession, db_session_factory: async_sessionmaker[AsyncSession]
) -> None:
    auth_user = await _insert_auth_user(db_session)
    find_user_persona_result = await _insert_owner_persona(db_session, auth_user)
    llm_service_stub = LlmServiceStub()
    llm_service_stub.complete_result = build_llm_completion_result(content="# Final\n\nFinal text.")
    generate_text_service = _build_generate_text_service(db_session_factory, llm_service_stub)
    generate_text_result = await generate_text_service.generate_text(
        build_generate_text_input(options=_build_all_auto_approved_options()),
        find_user_persona_result,
        auth_user,
    )

    find_generate_text_run_result = await generate_text_service.find_generate_text_run(
        generate_text_result.run_identity, auth_user
    )

    assert find_generate_text_run_result.run_identity == generate_text_result.run_identity
    assert find_generate_text_run_result.text_type == TextType.BLOG_POST
    assert find_generate_text_run_result.graph_name == "blog_post"
    assert find_generate_text_run_result.status == GenerateTextRunStatusType.COMPLETED
    assert find_generate_text_run_result.last_step == "GENERATE_DRAFT"
    assert find_generate_text_run_result.started_at is not None
    assert find_generate_text_run_result.finished_at is not None
    assert find_generate_text_run_result.content == "# Final\n\nFinal text."
    assert find_generate_text_run_result.character_count == 20


async def test_find_generate_text_run_unknown_raises_not_found_exception(
    db_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    llm_service_stub = LlmServiceStub()
    generate_text_service = _build_generate_text_service(db_session_factory, llm_service_stub)

    with pytest.raises(NotFoundException):
        await generate_text_service.find_generate_text_run(uuid4(), build_auth_user())


async def test_find_generate_text_run_another_users_run_raises_not_found_exception(
    db_session: AsyncSession, db_session_factory: async_sessionmaker[AsyncSession]
) -> None:
    owner_auth_user = await _insert_auth_user(db_session)
    other_auth_user = await _insert_auth_user(db_session)
    find_user_persona_result = await _insert_owner_persona(db_session, owner_auth_user)
    llm_service_stub = LlmServiceStub()
    llm_service_stub.complete_result = build_llm_completion_result(content="# Final\n\nFinal text.")
    generate_text_service = _build_generate_text_service(db_session_factory, llm_service_stub)
    generate_text_result = await generate_text_service.generate_text(
        build_generate_text_input(options=_build_all_auto_approved_options()),
        find_user_persona_result,
        owner_auth_user,
    )

    with pytest.raises(NotFoundException):
        await generate_text_service.find_generate_text_run(
            generate_text_result.run_identity, other_auth_user
        )


async def test_resume_generate_text_unknown_run_raises_not_found_exception(
    db_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    llm_service_stub = LlmServiceStub()
    generate_text_service = _build_generate_text_service(db_session_factory, llm_service_stub)

    with pytest.raises(NotFoundException):
        await generate_text_service.resume_generate_text(
            uuid4(), build_resume_generate_text_input(), build_auth_user()
        )


async def test_resume_generate_text_another_users_run_raises_not_found_exception(
    db_session: AsyncSession, db_session_factory: async_sessionmaker[AsyncSession]
) -> None:
    owner_auth_user = await _insert_auth_user(db_session)
    other_auth_user = await _insert_auth_user(db_session)
    find_user_persona_result = await _insert_owner_persona(db_session, owner_auth_user)
    llm_service_stub = LlmServiceStub()
    llm_service_stub.complete_result = build_llm_completion_result(content="# Draft\n\nA draft.")
    generate_text_service = _build_generate_text_service(db_session_factory, llm_service_stub)
    generate_text_result = await generate_text_service.generate_text(
        build_generate_text_input(options=_build_draft_needs_review_options()),
        find_user_persona_result,
        owner_auth_user,
    )

    with pytest.raises(NotFoundException):
        await generate_text_service.resume_generate_text(
            generate_text_result.run_identity, build_resume_generate_text_input(), other_auth_user
        )


async def test_resume_generate_text_run_not_paused_raises_not_paused_exception(
    db_session: AsyncSession, db_session_factory: async_sessionmaker[AsyncSession]
) -> None:
    auth_user = await _insert_auth_user(db_session)
    find_user_persona_result = await _insert_owner_persona(db_session, auth_user)
    llm_service_stub = LlmServiceStub()
    llm_service_stub.complete_result = build_llm_completion_result(content="# Final\n\nFinal text.")
    generate_text_service = _build_generate_text_service(db_session_factory, llm_service_stub)
    generate_text_result = await generate_text_service.generate_text(
        build_generate_text_input(options=_build_all_auto_approved_options()),
        find_user_persona_result,
        auth_user,
    )

    with pytest.raises(GenerateTextRunNotPausedException):
        await generate_text_service.resume_generate_text(
            generate_text_result.run_identity, build_resume_generate_text_input(), auth_user
        )


async def test_resume_generate_text_version_mismatch_raises_version_mismatch_exception(
    db_session: AsyncSession, db_session_factory: async_sessionmaker[AsyncSession]
) -> None:
    auth_user = await _insert_auth_user(db_session)
    run_record = await insert_generate_text_run_row(
        db_session,
        created_by_id=auth_user.id,
        graph_version="stale-version",
        status=GenerateTextRunStatusType.AWAITING_REVIEW,
    )
    await db_session.commit()
    llm_service_stub = LlmServiceStub()
    generate_text_service = _build_generate_text_service(db_session_factory, llm_service_stub)

    with pytest.raises(GenerateTextRunVersionMismatchException):
        await generate_text_service.resume_generate_text(
            run_record.identity, build_resume_generate_text_input(), auth_user
        )


async def test_generate_text_graph_invoke_fails_with_no_step_marks_run_failed(
    db_session: AsyncSession, db_session_factory: async_sessionmaker[AsyncSession]
) -> None:
    auth_user = await _insert_auth_user(db_session)
    find_user_persona_result = await _insert_owner_persona(db_session, auth_user)
    generate_text_service, graph_builder_registry_stub = (
        _build_generate_text_service_with_stub_registry(db_session_factory)
    )
    graph_builder_stub = graph_builder_registry_stub.get_by_text_type_result
    graph_builder_stub.build_graph_result.ainvoke_error = RuntimeError("checkpointer unreachable")
    generate_text_input = build_generate_text_input(options=_build_all_auto_approved_options())

    with pytest.raises(RuntimeError):
        await generate_text_service.generate_text(
            generate_text_input, find_user_persona_result, auth_user
        )

    run_query = select(GenerateTextRunOrm).where(GenerateTextRunOrm.created_by_id == auth_user.id)
    run_record = await db_session.scalar(run_query)
    assert run_record is not None
    assert run_record.status == GenerateTextRunStatusType.FAILED
    assert run_record.error_code == "RuntimeError"
    assert run_record.error_message == "checkpointer unreachable"
    assert run_record.finished_at is not None


async def test_generate_text_draft_never_validates_fails_run_and_records_error_on_step(
    db_session: AsyncSession, db_session_factory: async_sessionmaker[AsyncSession]
) -> None:
    auth_user = await _insert_auth_user(db_session)
    find_user_persona_result = await _insert_owner_persona(db_session, auth_user)
    llm_service_stub = LlmServiceStub()
    llm_service_stub.complete_result = build_llm_completion_result(content="Not valid markdown.")
    generate_text_service = _build_generate_text_service(
        db_session_factory,
        llm_service_stub,
        generate_text_settings=GenerateTextSettings(max_output_format_retries=0),
    )
    generate_text_input = build_generate_text_input(options=_build_all_auto_approved_options())

    with pytest.raises(GenerateTextOutputInvalidException):
        await generate_text_service.generate_text(
            generate_text_input, find_user_persona_result, auth_user
        )

    run_query = select(GenerateTextRunOrm).where(GenerateTextRunOrm.created_by_id == auth_user.id)
    run_record = await db_session.scalar(run_query)
    assert run_record is not None
    assert run_record.status == GenerateTextRunStatusType.FAILED
    assert run_record.error_code is None
    step_query = select(GenerateTextStepOrm).where(
        GenerateTextStepOrm.run_id == run_record.id,
        GenerateTextStepOrm.step_name == "GENERATE_DRAFT",
    )
    step_record = await db_session.scalar(step_query)
    assert step_record is not None
    assert step_record.status == GenerateTextStepStatusType.FAILED
    assert step_record.error_code == "GenerateTextOutputInvalidException"


async def test_generate_text_persists_persona_id_tone_and_target_audience(
    db_session: AsyncSession, db_session_factory: async_sessionmaker[AsyncSession]
) -> None:
    auth_user = await _insert_auth_user(db_session)
    find_user_persona_result = await _insert_owner_persona(db_session, auth_user)
    llm_service_stub = LlmServiceStub()
    llm_service_stub.complete_result = build_llm_completion_result(content="# Final\n\nFinal text.")
    generate_text_service = _build_generate_text_service(db_session_factory, llm_service_stub)
    generate_text_input = build_generate_text_input(
        options=_build_all_auto_approved_options(),
        tone="Playful",
        target_audience="Home bakers",
    )

    await generate_text_service.generate_text(
        generate_text_input, find_user_persona_result, auth_user
    )

    run_query = select(GenerateTextRunOrm).where(GenerateTextRunOrm.created_by_id == auth_user.id)
    run_record = await db_session.scalar(run_query)
    assert run_record is not None
    assert run_record.persona_id == find_user_persona_result.id
    assert run_record.tone == "Playful"
    assert run_record.target_audience == "Home bakers"


async def test_generate_text_invalid_options_raises_and_persists_no_run(
    db_session: AsyncSession, db_session_factory: async_sessionmaker[AsyncSession]
) -> None:
    auth_user = await _insert_auth_user(db_session)
    find_user_persona_result = build_find_user_persona_result()
    llm_service_stub = LlmServiceStub()
    generate_text_service = _build_generate_text_service(db_session_factory, llm_service_stub)
    generate_text_input = GenerateTextInput[_InvalidBlogPostOptionsInput](
        text_type=TextType.BLOG_POST,
        prompt_text="Write about coffee.",
        options=_InvalidBlogPostOptionsInput(),
    )

    with pytest.raises(GenerateTextOptionsInvalidException):
        await generate_text_service.generate_text(
            generate_text_input, find_user_persona_result, auth_user
        )

    run_query = select(GenerateTextRunOrm).where(GenerateTextRunOrm.created_by_id == auth_user.id)
    run_record = await db_session.scalar(run_query)
    assert run_record is None
