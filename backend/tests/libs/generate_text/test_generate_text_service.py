from datetime import UTC, datetime
from decimal import Decimal
from uuid import uuid4

import pytest
from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.checkpoint.memory import InMemorySaver
from pydantic import BaseModel
from redis.asyncio import Redis
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from libs.auth.results import AuthUser
from libs.core.exceptions import NotFoundException
from libs.core.services import BackgroundJobService
from libs.database.orm.generate_text_run import GenerateTextRunOrm
from libs.database.orm.generate_text_step import GenerateTextStepOrm
from libs.generate_text.exceptions import (
    GenerateTextOptionsInvalidException,
    GenerateTextRunNotPausedException,
    GenerateTextRunVersionMismatchException,
)
from libs.generate_text.graphs.blog_post.inputs import BlogPostOptionsInput
from libs.generate_text.graphs.generate_text_graph_builder_registry import (
    GenerateTextGraphBuilderRegistry,
)
from libs.generate_text.inputs import GenerateTextInput, StepOptionInput
from libs.generate_text.results import GenerateTextRunResult
from libs.generate_text.services.generate_text_instrumentation_service import (
    GenerateTextInstrumentationService,
)
from libs.generate_text.services.generate_text_node_service import GenerateTextNodeService
from libs.generate_text.services.generate_text_run_handoff_queue_service import (
    GenerateTextRunHandoffQueueService,
)
from libs.generate_text.services.generate_text_run_lease_service import (
    GenerateTextRunLeaseService,
)
from libs.generate_text.services.generate_text_run_service import GenerateTextRunService
from libs.generate_text.services.generate_text_service import GenerateTextService
from libs.generate_text.services.generate_text_step_service import GenerateTextStepService
from libs.generate_text.settings import GenerateTextSettings
from libs.generate_text.types import (
    GenerateTextRunStatusType,
    GenerateTextStepStatusType,
    HumanDecisionType,
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
from tests.stubs.generate_text import (
    GenerateTextGraphBuilderRegistryStub,
    GenerateTextStepServiceStub,
)
from tests.stubs.llm import LlmServiceStub

DRAIN_TIMEOUT_SECONDS = 30
# A lease this long (about 95 years) ends after LONG_LEASE_BOUND, and a lease released
# "now" ends before it, so a test can tell the two apart without reading the clock.
LONG_LEASE_SECONDS = 3_000_000_000
LONG_LEASE_BOUND = datetime(2100, 1, 1, tzinfo=UTC)
OTHER_WORKER_LEASE_EXPIRES_AT = datetime(2099, 1, 2, 3, 4, 5, tzinfo=UTC)


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
    background_job_service: BackgroundJobService,
    handoff_queue_service: GenerateTextRunHandoffQueueService,
    *,
    generate_text_settings: GenerateTextSettings | None = None,
    checkpointer: BaseCheckpointSaver | None = None,
    step_service: GenerateTextStepService | None = None,
) -> GenerateTextService:
    """step_service replaces only the one GenerateTextService holds; the graph's nodes keep
    the real one."""
    generate_text_settings = generate_text_settings or GenerateTextSettings()
    run_service = GenerateTextRunService(db_session_factory=db_session_factory)
    real_step_service = GenerateTextStepService(db_session_factory=db_session_factory)
    instrumentation_service = GenerateTextInstrumentationService(
        run_service=run_service, step_service=real_step_service
    )
    node_service = GenerateTextNodeService(
        llm_service=llm_service_stub, generate_text_settings=generate_text_settings
    )
    graph_builder_registry = GenerateTextGraphBuilderRegistry(
        node_service=node_service,
        instrumentation_service=instrumentation_service,
        generate_text_settings=generate_text_settings,
    )
    lease_service = GenerateTextRunLeaseService(
        run_service=run_service,
        handoff_queue_service=handoff_queue_service,
        background_job_service=background_job_service,
        generate_text_settings=generate_text_settings,
    )
    return GenerateTextService(
        graph_builder_registry=graph_builder_registry,
        run_service=run_service,
        step_service=step_service or real_step_service,
        lease_service=lease_service,
        checkpointer=checkpointer or InMemorySaver(),
        background_job_service=background_job_service,
        generate_text_settings=generate_text_settings,
    )


def _build_generate_text_service_with_stub_registry(
    db_session_factory: async_sessionmaker[AsyncSession],
    background_job_service: BackgroundJobService,
    handoff_queue_service: GenerateTextRunHandoffQueueService,
    *,
    generate_text_settings: GenerateTextSettings | None = None,
) -> tuple[GenerateTextService, GenerateTextGraphBuilderRegistryStub]:
    run_service = GenerateTextRunService(db_session_factory=db_session_factory)
    step_service = GenerateTextStepService(db_session_factory=db_session_factory)
    graph_builder_registry_stub = GenerateTextGraphBuilderRegistryStub()
    generate_text_settings = generate_text_settings or GenerateTextSettings()
    lease_service = GenerateTextRunLeaseService(
        run_service=run_service,
        handoff_queue_service=handoff_queue_service,
        background_job_service=background_job_service,
        generate_text_settings=generate_text_settings,
    )
    generate_text_service = GenerateTextService(
        graph_builder_registry=graph_builder_registry_stub,
        run_service=run_service,
        step_service=step_service,
        lease_service=lease_service,
        checkpointer=InMemorySaver(),
        background_job_service=background_job_service,
        generate_text_settings=generate_text_settings,
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


async def test_generate_text_returns_pending_run_before_graph_finishes(
    db_session: AsyncSession,
    db_session_factory: async_sessionmaker[AsyncSession],
    background_job_service: BackgroundJobService,
    handoff_queue_service: GenerateTextRunHandoffQueueService,
) -> None:
    auth_user = await _insert_auth_user(db_session)
    find_user_persona_result = await _insert_owner_persona(db_session, auth_user)
    llm_service_stub = LlmServiceStub()
    llm_service_stub.complete_result = build_llm_completion_result(content="# Final\n\nFinal text.")
    generate_text_service = _build_generate_text_service(
        db_session_factory,
        llm_service_stub,
        background_job_service,
        handoff_queue_service,
        generate_text_settings=GenerateTextSettings(poll_interval_ms=500),
    )
    generate_text_input = build_generate_text_input(
        options=_build_all_auto_approved_options(),
        prompt_text="Write about coffee.",
        tone="Playful",
        target_audience="Home bakers",
        additional_context="Mention rye flour.",
    )

    generate_text_run_result = await generate_text_service.generate_text(
        generate_text_input, find_user_persona_result, auth_user
    )

    await background_job_service.drain(DRAIN_TIMEOUT_SECONDS)
    assert generate_text_run_result == GenerateTextRunResult(
        run_identity=generate_text_run_result.run_identity,
        text_type=TextType.BLOG_POST,
        status=GenerateTextRunStatusType.PENDING,
        last_step=None,
        graph_name="blog_post",
        graph_version="2026-10-07.2",
        persona_identity=find_user_persona_result.identity,
        prompt_text="Write about coffee.",
        tone="Playful",
        target_audience="Home bakers",
        additional_context="Mention rye flour.",
        options={
            "outline": {"is_enabled": True, "is_auto_approved": True},
            "draft": {"is_enabled": True, "is_auto_approved": True},
            "humanize": {"is_enabled": False, "is_auto_approved": True},
        },
        content="",
        character_count=0,
        llm_call_count=0,
        input_tokens=0,
        output_tokens=0,
        cost_usd=Decimal("0"),
        started_at=None,
        finished_at=None,
        poll_interval_ms=500,
    )


async def test_generate_text_all_steps_auto_approved_completes_run_in_background(
    db_session: AsyncSession,
    db_session_factory: async_sessionmaker[AsyncSession],
    background_job_service: BackgroundJobService,
    handoff_queue_service: GenerateTextRunHandoffQueueService,
) -> None:
    auth_user = await _insert_auth_user(db_session)
    find_user_persona_result = await _insert_owner_persona(db_session, auth_user)
    llm_service_stub = LlmServiceStub()
    llm_service_stub.complete_result = build_llm_completion_result(content="# Final\n\nFinal text.")
    generate_text_service = _build_generate_text_service(
        db_session_factory, llm_service_stub, background_job_service, handoff_queue_service
    )
    generate_text_input = build_generate_text_input(options=_build_all_auto_approved_options())

    generate_text_run_result = await generate_text_service.generate_text(
        generate_text_input, find_user_persona_result, auth_user
    )

    await background_job_service.drain(DRAIN_TIMEOUT_SECONDS)
    find_generate_text_run_result = await generate_text_service.find_generate_text_run(
        generate_text_run_result.run_identity, auth_user
    )
    assert find_generate_text_run_result.status == GenerateTextRunStatusType.COMPLETED
    assert find_generate_text_run_result.last_step == "GENERATE_DRAFT"
    assert find_generate_text_run_result.content == "# Final\n\nFinal text."
    assert find_generate_text_run_result.character_count == 20
    assert find_generate_text_run_result.started_at is not None
    assert find_generate_text_run_result.finished_at is not None


async def test_generate_text_step_not_auto_approved_pauses_run_for_review_in_background(
    db_session: AsyncSession,
    db_session_factory: async_sessionmaker[AsyncSession],
    background_job_service: BackgroundJobService,
    handoff_queue_service: GenerateTextRunHandoffQueueService,
) -> None:
    auth_user = await _insert_auth_user(db_session)
    find_user_persona_result = await _insert_owner_persona(db_session, auth_user)
    llm_service_stub = LlmServiceStub()
    llm_service_stub.complete_result = build_llm_completion_result(content="# Draft\n\nA draft.")
    generate_text_service = _build_generate_text_service(
        db_session_factory, llm_service_stub, background_job_service, handoff_queue_service
    )
    generate_text_input = build_generate_text_input(options=_build_draft_needs_review_options())

    generate_text_run_result = await generate_text_service.generate_text(
        generate_text_input, find_user_persona_result, auth_user
    )

    await background_job_service.drain(DRAIN_TIMEOUT_SECONDS)
    find_generate_text_run_result = await generate_text_service.find_generate_text_run(
        generate_text_run_result.run_identity, auth_user
    )
    assert find_generate_text_run_result.status == GenerateTextRunStatusType.AWAITING_REVIEW
    assert find_generate_text_run_result.last_step == "REVIEW_DRAFT"
    assert find_generate_text_run_result.content == "# Draft\n\nA draft."
    assert find_generate_text_run_result.character_count == 17
    assert find_generate_text_run_result.finished_at is None


async def test_resume_generate_text_returns_running_run_with_paused_step_content(
    db_session: AsyncSession,
    db_session_factory: async_sessionmaker[AsyncSession],
    background_job_service: BackgroundJobService,
    handoff_queue_service: GenerateTextRunHandoffQueueService,
) -> None:
    auth_user = await _insert_auth_user(db_session)
    find_user_persona_result = await _insert_owner_persona(db_session, auth_user)
    llm_service_stub = LlmServiceStub()
    llm_service_stub.complete_result = build_llm_completion_result(content="# Draft\n\nA draft.")
    generate_text_service = _build_generate_text_service(
        db_session_factory, llm_service_stub, background_job_service, handoff_queue_service
    )
    generate_text_run_result = await generate_text_service.generate_text(
        build_generate_text_input(options=_build_draft_needs_review_options()),
        find_user_persona_result,
        auth_user,
    )
    await background_job_service.drain(DRAIN_TIMEOUT_SECONDS)

    resume_generate_text_result = await generate_text_service.resume_generate_text(
        generate_text_run_result.run_identity,
        build_resume_generate_text_input(is_approved=True),
        auth_user,
    )

    await background_job_service.drain(DRAIN_TIMEOUT_SECONDS)
    assert resume_generate_text_result.status == GenerateTextRunStatusType.RUNNING
    assert resume_generate_text_result.last_step == "REVIEW_DRAFT"
    assert resume_generate_text_result.content == "# Draft\n\nA draft."
    assert resume_generate_text_result.poll_interval_ms == 2000


async def test_resume_generate_text_approval_completes_run_in_background(
    db_session: AsyncSession,
    db_session_factory: async_sessionmaker[AsyncSession],
    background_job_service: BackgroundJobService,
    handoff_queue_service: GenerateTextRunHandoffQueueService,
) -> None:
    auth_user = await _insert_auth_user(db_session)
    find_user_persona_result = await _insert_owner_persona(db_session, auth_user)
    llm_service_stub = LlmServiceStub()
    llm_service_stub.complete_result = build_llm_completion_result(content="# Draft\n\nA draft.")
    generate_text_service = _build_generate_text_service(
        db_session_factory, llm_service_stub, background_job_service, handoff_queue_service
    )
    generate_text_run_result = await generate_text_service.generate_text(
        build_generate_text_input(options=_build_draft_needs_review_options()),
        find_user_persona_result,
        auth_user,
    )
    await background_job_service.drain(DRAIN_TIMEOUT_SECONDS)

    await generate_text_service.resume_generate_text(
        generate_text_run_result.run_identity,
        build_resume_generate_text_input(is_approved=True),
        auth_user,
    )

    await background_job_service.drain(DRAIN_TIMEOUT_SECONDS)
    find_generate_text_run_result = await generate_text_service.find_generate_text_run(
        generate_text_run_result.run_identity, auth_user
    )
    assert find_generate_text_run_result.status == GenerateTextRunStatusType.COMPLETED
    assert find_generate_text_run_result.content == "# Draft\n\nA draft."
    assert find_generate_text_run_result.character_count == 17
    assert find_generate_text_run_result.finished_at is not None
    review_step_query = select(GenerateTextStepOrm).where(
        GenerateTextStepOrm.step_name == "REVIEW_DRAFT"
    )
    review_step_record = await db_session.scalar(review_step_query)
    assert review_step_record is not None
    assert review_step_record.human_decision == HumanDecisionType.APPROVED


async def test_resume_generate_text_rejection_rewrites_and_pauses_run_again(
    db_session: AsyncSession,
    db_session_factory: async_sessionmaker[AsyncSession],
    background_job_service: BackgroundJobService,
    handoff_queue_service: GenerateTextRunHandoffQueueService,
) -> None:
    auth_user = await _insert_auth_user(db_session)
    find_user_persona_result = await _insert_owner_persona(db_session, auth_user)
    llm_service_stub = LlmServiceStub()
    llm_service_stub.complete_result = build_llm_completion_result(content="# Draft\n\nA draft.")
    generate_text_service = _build_generate_text_service(
        db_session_factory, llm_service_stub, background_job_service, handoff_queue_service
    )
    generate_text_run_result = await generate_text_service.generate_text(
        build_generate_text_input(options=_build_draft_needs_review_options()),
        find_user_persona_result,
        auth_user,
    )
    await background_job_service.drain(DRAIN_TIMEOUT_SECONDS)
    llm_service_stub.complete_result = build_llm_completion_result(
        content="# Draft\n\nA revised draft."
    )

    await generate_text_service.resume_generate_text(
        generate_text_run_result.run_identity,
        build_resume_generate_text_input(is_approved=False, feedback_text="Make it shorter."),
        auth_user,
    )

    await background_job_service.drain(DRAIN_TIMEOUT_SECONDS)
    find_generate_text_run_result = await generate_text_service.find_generate_text_run(
        generate_text_run_result.run_identity, auth_user
    )
    assert find_generate_text_run_result.status == GenerateTextRunStatusType.AWAITING_REVIEW
    assert find_generate_text_run_result.content == "# Draft\n\nA revised draft."
    assert find_generate_text_run_result.character_count == 25
    review_step_query = (
        select(GenerateTextStepOrm)
        .where(GenerateTextStepOrm.step_name == "REVIEW_DRAFT")
        .order_by(GenerateTextStepOrm.step_number)
    )
    review_step_record = await db_session.scalar(review_step_query)
    assert review_step_record is not None
    assert review_step_record.human_decision == HumanDecisionType.REJECTED
    assert review_step_record.human_feedback == "Make it shorter."


async def test_find_generate_text_run_unknown_raises_not_found_exception(
    db_session_factory: async_sessionmaker[AsyncSession],
    background_job_service: BackgroundJobService,
    handoff_queue_service: GenerateTextRunHandoffQueueService,
) -> None:
    generate_text_service = _build_generate_text_service(
        db_session_factory, LlmServiceStub(), background_job_service, handoff_queue_service
    )

    with pytest.raises(NotFoundException):
        await generate_text_service.find_generate_text_run(uuid4(), build_auth_user())


async def test_find_generate_text_run_another_users_run_raises_not_found_exception(
    db_session: AsyncSession,
    db_session_factory: async_sessionmaker[AsyncSession],
    background_job_service: BackgroundJobService,
    handoff_queue_service: GenerateTextRunHandoffQueueService,
) -> None:
    owner_auth_user = await _insert_auth_user(db_session)
    other_auth_user = await _insert_auth_user(db_session)
    find_user_persona_result = await _insert_owner_persona(db_session, owner_auth_user)
    llm_service_stub = LlmServiceStub()
    llm_service_stub.complete_result = build_llm_completion_result(content="# Final\n\nFinal text.")
    generate_text_service = _build_generate_text_service(
        db_session_factory, llm_service_stub, background_job_service, handoff_queue_service
    )
    generate_text_run_result = await generate_text_service.generate_text(
        build_generate_text_input(options=_build_all_auto_approved_options()),
        find_user_persona_result,
        owner_auth_user,
    )
    await background_job_service.drain(DRAIN_TIMEOUT_SECONDS)

    with pytest.raises(NotFoundException):
        await generate_text_service.find_generate_text_run(
            generate_text_run_result.run_identity, other_auth_user
        )


async def test_resume_generate_text_unknown_run_raises_not_found_exception(
    db_session_factory: async_sessionmaker[AsyncSession],
    background_job_service: BackgroundJobService,
    handoff_queue_service: GenerateTextRunHandoffQueueService,
) -> None:
    generate_text_service = _build_generate_text_service(
        db_session_factory, LlmServiceStub(), background_job_service, handoff_queue_service
    )

    with pytest.raises(NotFoundException):
        await generate_text_service.resume_generate_text(
            uuid4(), build_resume_generate_text_input(), build_auth_user()
        )


async def test_resume_generate_text_another_users_run_raises_not_found_exception(
    db_session: AsyncSession,
    db_session_factory: async_sessionmaker[AsyncSession],
    background_job_service: BackgroundJobService,
    handoff_queue_service: GenerateTextRunHandoffQueueService,
) -> None:
    owner_auth_user = await _insert_auth_user(db_session)
    other_auth_user = await _insert_auth_user(db_session)
    find_user_persona_result = await _insert_owner_persona(db_session, owner_auth_user)
    llm_service_stub = LlmServiceStub()
    llm_service_stub.complete_result = build_llm_completion_result(content="# Draft\n\nA draft.")
    generate_text_service = _build_generate_text_service(
        db_session_factory, llm_service_stub, background_job_service, handoff_queue_service
    )
    generate_text_run_result = await generate_text_service.generate_text(
        build_generate_text_input(options=_build_draft_needs_review_options()),
        find_user_persona_result,
        owner_auth_user,
    )
    await background_job_service.drain(DRAIN_TIMEOUT_SECONDS)

    with pytest.raises(NotFoundException):
        await generate_text_service.resume_generate_text(
            generate_text_run_result.run_identity,
            build_resume_generate_text_input(),
            other_auth_user,
        )


async def test_resume_generate_text_run_not_paused_raises_not_paused_exception(
    db_session: AsyncSession,
    db_session_factory: async_sessionmaker[AsyncSession],
    background_job_service: BackgroundJobService,
    handoff_queue_service: GenerateTextRunHandoffQueueService,
) -> None:
    auth_user = await _insert_auth_user(db_session)
    find_user_persona_result = await _insert_owner_persona(db_session, auth_user)
    llm_service_stub = LlmServiceStub()
    llm_service_stub.complete_result = build_llm_completion_result(content="# Final\n\nFinal text.")
    generate_text_service = _build_generate_text_service(
        db_session_factory, llm_service_stub, background_job_service, handoff_queue_service
    )
    generate_text_run_result = await generate_text_service.generate_text(
        build_generate_text_input(options=_build_all_auto_approved_options()),
        find_user_persona_result,
        auth_user,
    )
    await background_job_service.drain(DRAIN_TIMEOUT_SECONDS)

    with pytest.raises(GenerateTextRunNotPausedException):
        await generate_text_service.resume_generate_text(
            generate_text_run_result.run_identity, build_resume_generate_text_input(), auth_user
        )


async def test_resume_generate_text_version_mismatch_raises_version_mismatch_exception(
    db_session: AsyncSession,
    db_session_factory: async_sessionmaker[AsyncSession],
    background_job_service: BackgroundJobService,
    handoff_queue_service: GenerateTextRunHandoffQueueService,
) -> None:
    auth_user = await _insert_auth_user(db_session)
    run_record = await insert_generate_text_run_row(
        db_session,
        created_by_id=auth_user.id,
        graph_version="stale-version",
        status=GenerateTextRunStatusType.AWAITING_REVIEW,
    )
    await db_session.commit()
    generate_text_service = _build_generate_text_service(
        db_session_factory, LlmServiceStub(), background_job_service, handoff_queue_service
    )

    with pytest.raises(GenerateTextRunVersionMismatchException):
        await generate_text_service.resume_generate_text(
            run_record.identity, build_resume_generate_text_input(), auth_user
        )


async def test_resume_generate_text_record_decision_fails_marks_run_failed_and_reraises(
    db_session: AsyncSession,
    db_session_factory: async_sessionmaker[AsyncSession],
    background_job_service: BackgroundJobService,
    handoff_queue_service: GenerateTextRunHandoffQueueService,
) -> None:
    auth_user = await _insert_auth_user(db_session)
    find_user_persona_result = await _insert_owner_persona(db_session, auth_user)
    llm_service_stub = LlmServiceStub()
    llm_service_stub.complete_result = build_llm_completion_result(content="# Draft\n\nA draft.")
    graph_checkpointer = InMemorySaver()
    generate_text_service = _build_generate_text_service(
        db_session_factory,
        llm_service_stub,
        background_job_service,
        handoff_queue_service,
        checkpointer=graph_checkpointer,
    )
    generate_text_run_result = await generate_text_service.generate_text(
        build_generate_text_input(options=_build_draft_needs_review_options()),
        find_user_persona_result,
        auth_user,
    )
    await background_job_service.drain(DRAIN_TIMEOUT_SECONDS)
    generate_text_step_service_stub = GenerateTextStepServiceStub()
    generate_text_step_service_stub.record_decision_error = RuntimeError("decision write failed")
    resuming_generate_text_service = _build_generate_text_service(
        db_session_factory,
        llm_service_stub,
        background_job_service,
        handoff_queue_service,
        checkpointer=graph_checkpointer,
        step_service=generate_text_step_service_stub,
    )

    with pytest.raises(RuntimeError):
        await resuming_generate_text_service.resume_generate_text(
            generate_text_run_result.run_identity, build_resume_generate_text_input(), auth_user
        )

    run_query = select(GenerateTextRunOrm).where(
        GenerateTextRunOrm.identity == generate_text_run_result.run_identity
    )
    run_record = await db_session.scalar(run_query)
    assert run_record is not None
    assert run_record.status == GenerateTextRunStatusType.FAILED
    assert run_record.error_code == "RuntimeError"
    assert run_record.error_message == "decision write failed"


async def test_generate_text_graph_stream_fails_with_no_step_marks_run_failed(
    db_session: AsyncSession,
    db_session_factory: async_sessionmaker[AsyncSession],
    background_job_service: BackgroundJobService,
    handoff_queue_service: GenerateTextRunHandoffQueueService,
) -> None:
    auth_user = await _insert_auth_user(db_session)
    find_user_persona_result = await _insert_owner_persona(db_session, auth_user)
    generate_text_service, graph_builder_registry_stub = (
        _build_generate_text_service_with_stub_registry(
            db_session_factory, background_job_service, handoff_queue_service
        )
    )
    graph_builder_stub = graph_builder_registry_stub.get_by_text_type_result
    graph_builder_stub.build_graph_result.astream_error = RuntimeError("checkpointer unreachable")
    generate_text_input = build_generate_text_input(options=_build_all_auto_approved_options())

    await generate_text_service.generate_text(
        generate_text_input, find_user_persona_result, auth_user
    )

    await background_job_service.drain(DRAIN_TIMEOUT_SECONDS)
    run_query = select(GenerateTextRunOrm).where(GenerateTextRunOrm.created_by_id == auth_user.id)
    run_record = await db_session.scalar(run_query)
    assert run_record is not None
    assert run_record.status == GenerateTextRunStatusType.FAILED
    assert run_record.error_code == "RuntimeError"
    assert run_record.error_message == "checkpointer unreachable"
    assert run_record.finished_at is not None


async def test_generate_text_task_cancelled_mid_run_releases_lease_and_keeps_run_running(
    db_session: AsyncSession,
    db_session_factory: async_sessionmaker[AsyncSession],
    background_job_service: BackgroundJobService,
    handoff_queue_service: GenerateTextRunHandoffQueueService,
) -> None:
    auth_user = await _insert_auth_user(db_session)
    find_user_persona_result = await _insert_owner_persona(db_session, auth_user)
    generate_text_service, graph_builder_registry_stub = (
        _build_generate_text_service_with_stub_registry(
            db_session_factory,
            background_job_service,
            handoff_queue_service,
            generate_text_settings=GenerateTextSettings(lease_seconds=LONG_LEASE_SECONDS),
        )
    )
    graph_stub = graph_builder_registry_stub.get_by_text_type_result.build_graph_result
    graph_stub.astream_is_blocked = True
    generate_text_input = build_generate_text_input(options=_build_all_auto_approved_options())
    await generate_text_service.generate_text(
        generate_text_input, find_user_persona_result, auth_user
    )
    await graph_stub.astream_started_event.wait()

    await background_job_service.drain(0)

    run_query = select(GenerateTextRunOrm).where(GenerateTextRunOrm.created_by_id == auth_user.id)
    run_record = await db_session.scalar(run_query)
    assert run_record is not None
    assert run_record.status == GenerateTextRunStatusType.RUNNING
    assert run_record.error_code is None
    assert run_record.finished_at is None
    assert run_record.lease_owner == "test-worker"
    assert run_record.lease_expires_at is not None
    assert run_record.lease_expires_at < LONG_LEASE_BOUND


async def test_generate_text_creates_run_leased_to_worker(
    db_session: AsyncSession,
    db_session_factory: async_sessionmaker[AsyncSession],
    background_job_service: BackgroundJobService,
    handoff_queue_service: GenerateTextRunHandoffQueueService,
) -> None:
    auth_user = await _insert_auth_user(db_session)
    find_user_persona_result = await _insert_owner_persona(db_session, auth_user)
    generate_text_service, graph_builder_registry_stub = (
        _build_generate_text_service_with_stub_registry(
            db_session_factory,
            background_job_service,
            handoff_queue_service,
            generate_text_settings=GenerateTextSettings(lease_seconds=LONG_LEASE_SECONDS),
        )
    )
    graph_stub = graph_builder_registry_stub.get_by_text_type_result.build_graph_result
    graph_stub.astream_is_blocked = True
    generate_text_input = build_generate_text_input(options=_build_all_auto_approved_options())

    await generate_text_service.generate_text(
        generate_text_input, find_user_persona_result, auth_user
    )

    await graph_stub.astream_started_event.wait()
    run_query = select(GenerateTextRunOrm).where(GenerateTextRunOrm.created_by_id == auth_user.id)
    run_record = await db_session.scalar(run_query)
    await background_job_service.drain(0)
    assert run_record is not None
    assert run_record.lease_owner == "test-worker"
    assert run_record.lease_expires_at is not None
    assert run_record.lease_expires_at > LONG_LEASE_BOUND


async def test_generate_text_draft_never_validates_fails_run_and_records_error_on_step(
    db_session: AsyncSession,
    db_session_factory: async_sessionmaker[AsyncSession],
    background_job_service: BackgroundJobService,
    handoff_queue_service: GenerateTextRunHandoffQueueService,
) -> None:
    auth_user = await _insert_auth_user(db_session)
    find_user_persona_result = await _insert_owner_persona(db_session, auth_user)
    llm_service_stub = LlmServiceStub()
    llm_service_stub.complete_result = build_llm_completion_result(content="Not valid markdown.")
    generate_text_service = _build_generate_text_service(
        db_session_factory,
        llm_service_stub,
        background_job_service,
        handoff_queue_service,
        generate_text_settings=GenerateTextSettings(max_output_format_retries=0),
    )
    generate_text_input = build_generate_text_input(options=_build_all_auto_approved_options())

    await generate_text_service.generate_text(
        generate_text_input, find_user_persona_result, auth_user
    )

    await background_job_service.drain(DRAIN_TIMEOUT_SECONDS)
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
    db_session: AsyncSession,
    db_session_factory: async_sessionmaker[AsyncSession],
    background_job_service: BackgroundJobService,
    handoff_queue_service: GenerateTextRunHandoffQueueService,
) -> None:
    auth_user = await _insert_auth_user(db_session)
    find_user_persona_result = await _insert_owner_persona(db_session, auth_user)
    llm_service_stub = LlmServiceStub()
    llm_service_stub.complete_result = build_llm_completion_result(content="# Final\n\nFinal text.")
    generate_text_service = _build_generate_text_service(
        db_session_factory, llm_service_stub, background_job_service, handoff_queue_service
    )
    generate_text_input = build_generate_text_input(
        options=_build_all_auto_approved_options(),
        tone="Playful",
        target_audience="Home bakers",
    )

    await generate_text_service.generate_text(
        generate_text_input, find_user_persona_result, auth_user
    )

    await background_job_service.drain(DRAIN_TIMEOUT_SECONDS)
    run_query = select(GenerateTextRunOrm).where(GenerateTextRunOrm.created_by_id == auth_user.id)
    run_record = await db_session.scalar(run_query)
    assert run_record is not None
    assert run_record.persona_id == find_user_persona_result.id
    assert run_record.tone == "Playful"
    assert run_record.target_audience == "Home bakers"


async def test_generate_text_invalid_options_raises_and_persists_no_run(
    db_session: AsyncSession,
    db_session_factory: async_sessionmaker[AsyncSession],
    background_job_service: BackgroundJobService,
    handoff_queue_service: GenerateTextRunHandoffQueueService,
) -> None:
    auth_user = await _insert_auth_user(db_session)
    find_user_persona_result = build_find_user_persona_result()
    generate_text_service = _build_generate_text_service(
        db_session_factory, LlmServiceStub(), background_job_service, handoff_queue_service
    )
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


async def test_resume_generate_text_run_without_checkpoint_raises_not_paused_exception(
    db_session: AsyncSession,
    db_session_factory: async_sessionmaker[AsyncSession],
    background_job_service: BackgroundJobService,
    handoff_queue_service: GenerateTextRunHandoffQueueService,
) -> None:
    auth_user = await _insert_auth_user(db_session)
    run_record = await insert_generate_text_run_row(
        db_session,
        created_by_id=auth_user.id,
        graph_version="2026-10-07.2",
        status=GenerateTextRunStatusType.PENDING,
        options={"draft": {"is_enabled": True, "is_auto_approved": False}},
    )
    await db_session.commit()
    generate_text_service = _build_generate_text_service(
        db_session_factory, LlmServiceStub(), background_job_service, handoff_queue_service
    )

    with pytest.raises(GenerateTextRunNotPausedException):
        await generate_text_service.resume_generate_text(
            run_record.identity, build_resume_generate_text_input(), auth_user
        )


async def test_resume_generate_text_leases_claimed_run_to_worker(
    db_session: AsyncSession,
    db_session_factory: async_sessionmaker[AsyncSession],
    background_job_service: BackgroundJobService,
    handoff_queue_service: GenerateTextRunHandoffQueueService,
) -> None:
    auth_user = await _insert_auth_user(db_session)
    run_record = await insert_generate_text_run_row(
        db_session,
        created_by_id=auth_user.id,
        graph_version="stub-version",
        status=GenerateTextRunStatusType.AWAITING_REVIEW,
    )
    await db_session.commit()
    generate_text_service, graph_builder_registry_stub = (
        _build_generate_text_service_with_stub_registry(
            db_session_factory,
            background_job_service,
            handoff_queue_service,
            generate_text_settings=GenerateTextSettings(lease_seconds=LONG_LEASE_SECONDS),
        )
    )
    graph_stub = graph_builder_registry_stub.get_by_text_type_result.build_graph_result
    graph_stub.astream_is_blocked = True

    await generate_text_service.resume_generate_text(
        run_record.identity, build_resume_generate_text_input(), auth_user
    )

    await graph_stub.astream_started_event.wait()
    await db_session.refresh(run_record)
    await background_job_service.drain(0)
    assert run_record.status == GenerateTextRunStatusType.RUNNING
    assert run_record.lease_owner == "test-worker"
    assert run_record.lease_expires_at is not None
    assert run_record.lease_expires_at > LONG_LEASE_BOUND


async def test_generate_text_stop_requested_during_step_saves_step_releases_lease_and_pushes_run_id(
    db_session: AsyncSession,
    db_session_factory: async_sessionmaker[AsyncSession],
    background_job_service: BackgroundJobService,
    handoff_queue_service: GenerateTextRunHandoffQueueService,
    redis_client: Redis,
) -> None:
    auth_user = await _insert_auth_user(db_session)
    find_user_persona_result = await _insert_owner_persona(db_session, auth_user)
    llm_service_stub = LlmServiceStub()
    llm_service_stub.complete_result = build_llm_completion_result(content="# Final\n\nFinal text.")
    llm_service_stub.complete_is_blocked = True
    generate_text_service = _build_generate_text_service(
        db_session_factory,
        llm_service_stub,
        background_job_service,
        handoff_queue_service,
        generate_text_settings=GenerateTextSettings(lease_seconds=LONG_LEASE_SECONDS),
    )
    await generate_text_service.generate_text(
        build_generate_text_input(options=_build_all_auto_approved_options()),
        find_user_persona_result,
        auth_user,
    )
    await llm_service_stub.complete_started_event.wait()

    background_job_service.request_stop()
    llm_service_stub.complete_unblock_event.set()

    await background_job_service.drain(DRAIN_TIMEOUT_SECONDS)
    run_query = select(GenerateTextRunOrm).where(GenerateTextRunOrm.created_by_id == auth_user.id)
    run_record = await db_session.scalar(run_query)
    assert run_record is not None
    assert run_record.status == GenerateTextRunStatusType.RUNNING
    assert run_record.finished_at is None
    assert run_record.lease_owner == "test-worker"
    assert run_record.lease_expires_at is not None
    assert run_record.lease_expires_at < LONG_LEASE_BOUND
    step_query = (
        select(GenerateTextStepOrm)
        .where(GenerateTextStepOrm.run_id == run_record.id)
        .order_by(GenerateTextStepOrm.step_number)
    )
    step_scalars = await db_session.scalars(step_query)
    step_records = step_scalars.all()
    assert [step_record.step_name for step_record in step_records] == ["GENERATE_OUTLINE"]
    assert step_records[0].status == GenerateTextStepStatusType.SUCCEEDED
    assert step_records[0].output == {"text": "# Final\n\nFinal text."}
    assert len(llm_service_stub.complete_inputs) == 1
    handoff_list_items = await redis_client.lrange("generate_text:run_handoff", 0, -1)
    assert handoff_list_items == [str(run_record.id).encode()]


async def test_generate_text_lease_lost_to_another_worker_cancels_job_without_releasing(
    db_session: AsyncSession,
    db_session_factory: async_sessionmaker[AsyncSession],
    background_job_service: BackgroundJobService,
    handoff_queue_service: GenerateTextRunHandoffQueueService,
) -> None:
    auth_user = await _insert_auth_user(db_session)
    find_user_persona_result = await _insert_owner_persona(db_session, auth_user)
    generate_text_service, graph_builder_registry_stub = (
        _build_generate_text_service_with_stub_registry(
            db_session_factory,
            background_job_service,
            handoff_queue_service,
            generate_text_settings=GenerateTextSettings(
                lease_seconds=LONG_LEASE_SECONDS, lease_heartbeat_seconds=1
            ),
        )
    )
    graph_stub = graph_builder_registry_stub.get_by_text_type_result.build_graph_result
    graph_stub.astream_is_blocked = True
    await generate_text_service.generate_text(
        build_generate_text_input(options=_build_all_auto_approved_options()),
        find_user_persona_result,
        auth_user,
    )
    await graph_stub.astream_started_event.wait()
    take_lease_statement = (
        update(GenerateTextRunOrm)
        .where(GenerateTextRunOrm.created_by_id == auth_user.id)
        .values(lease_owner="other-worker", lease_expires_at=OTHER_WORKER_LEASE_EXPIRES_AT)
    )
    await db_session.execute(take_lease_statement)
    await db_session.commit()

    await background_job_service.drain(DRAIN_TIMEOUT_SECONDS)

    run_query = (
        select(GenerateTextRunOrm)
        .where(GenerateTextRunOrm.created_by_id == auth_user.id)
        .execution_options(populate_existing=True)
    )
    run_record = await db_session.scalar(run_query)
    assert graph_stub.astream_is_cancelled is True
    assert run_record is not None
    assert run_record.status == GenerateTextRunStatusType.RUNNING
    assert run_record.lease_owner == "other-worker"
    assert run_record.lease_expires_at == OTHER_WORKER_LEASE_EXPIRES_AT
