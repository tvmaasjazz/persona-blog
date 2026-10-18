import asyncio
from datetime import UTC, datetime

import structlog
from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.checkpoint.memory import InMemorySaver
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from libs.auth.results import AuthUser
from libs.core.services import BackgroundJobService
from libs.database.orm.generate_text_run import GenerateTextRunOrm
from libs.database.orm.generate_text_step import GenerateTextStepOrm
from libs.generate_text.graphs.blog_post.inputs import BlogPostOptionsInput
from libs.generate_text.graphs.generate_text_graph_builder_registry import (
    GenerateTextGraphBuilderRegistry,
)
from libs.generate_text.inputs import StepOptionInput
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
from libs.generate_text.services.generate_text_run_pickup_service import (
    GenerateTextRunPickupService,
)
from libs.generate_text.services.generate_text_run_service import GenerateTextRunService
from libs.generate_text.services.generate_text_service import GenerateTextService
from libs.generate_text.services.generate_text_step_service import GenerateTextStepService
from libs.generate_text.settings import GenerateTextSettings
from libs.generate_text.types import GenerateTextRunStatusType
from libs.personas.results import FindUserPersonaResult
from tests.factories.auth import build_auth_user
from tests.factories.generate_text import build_generate_text_input, insert_generate_text_run_row
from tests.factories.llm import build_llm_completion_result
from tests.factories.personas import insert_persona_row
from tests.factories.users import insert_user_row
from tests.stubs.generate_text import (
    GenerateTextGraphBuilderRegistryStub,
    GenerateTextRunHandoffQueueServiceStub,
    GenerateTextRunPickupServiceStub,
)
from tests.stubs.llm import LlmServiceStub

DRAIN_TIMEOUT_SECONDS = 30
LONG_PICKUP_INTERVAL_SECONDS = 3600
# A lease this long (about 95 years) ends after LONG_LEASE_BOUND, so a test can tell a
# fresh lease from a released one without reading the clock.
LONG_LEASE_SECONDS = 3_000_000_000
LONG_LEASE_BOUND = datetime(2100, 1, 1, tzinfo=UTC)
EXPIRED_LEASE_EXPIRES_AT = datetime(2026, 1, 2, 3, 4, 5, tzinfo=UTC)
OTHER_WORKER_LEASE_EXPIRES_AT = datetime(2099, 1, 2, 3, 4, 5, tzinfo=UTC)


async def _insert_auth_user(db_session: AsyncSession) -> AuthUser:
    user_record = await insert_user_row(db_session)
    await db_session.commit()
    return build_auth_user(user_id=user_record.id, user_identity=user_record.identity)


async def _insert_owner_persona(
    db_session: AsyncSession, auth_user: AuthUser
) -> FindUserPersonaResult:
    persona_record = await insert_persona_row(db_session, created_by_id=auth_user.id)
    await db_session.commit()
    return FindUserPersonaResult.model_validate(persona_record, from_attributes=True)


def _build_all_auto_approved_options() -> BlogPostOptionsInput:
    return BlogPostOptionsInput(
        outline=StepOptionInput(is_enabled=True, is_auto_approved=True),
        draft=StepOptionInput(is_auto_approved=True),
        humanize=StepOptionInput(is_enabled=False),
    )


def _build_real_graph_builder_registry(
    db_session_factory: async_sessionmaker[AsyncSession],
    llm_service_stub: LlmServiceStub,
    generate_text_settings: GenerateTextSettings,
) -> GenerateTextGraphBuilderRegistry:
    run_service = GenerateTextRunService(db_session_factory=db_session_factory)
    step_service = GenerateTextStepService(db_session_factory=db_session_factory)
    instrumentation_service = GenerateTextInstrumentationService(
        run_service=run_service, step_service=step_service
    )
    node_service = GenerateTextNodeService(
        llm_service=llm_service_stub, generate_text_settings=generate_text_settings
    )
    return GenerateTextGraphBuilderRegistry(
        node_service=node_service,
        instrumentation_service=instrumentation_service,
        generate_text_settings=generate_text_settings,
    )


def _build_generate_text_service(
    db_session_factory: async_sessionmaker[AsyncSession],
    graph_builder_registry: GenerateTextGraphBuilderRegistry | GenerateTextGraphBuilderRegistryStub,
    background_job_service: BackgroundJobService,
    handoff_queue_service: GenerateTextRunHandoffQueueService,
    generate_text_settings: GenerateTextSettings,
    checkpointer: BaseCheckpointSaver,
) -> GenerateTextService:
    run_service = GenerateTextRunService(db_session_factory=db_session_factory)
    lease_service = GenerateTextRunLeaseService(
        run_service=run_service,
        handoff_queue_service=handoff_queue_service,
        background_job_service=background_job_service,
        generate_text_settings=generate_text_settings,
    )
    return GenerateTextService(
        graph_builder_registry=graph_builder_registry,
        run_service=run_service,
        step_service=GenerateTextStepService(db_session_factory=db_session_factory),
        lease_service=lease_service,
        checkpointer=checkpointer,
        background_job_service=background_job_service,
        generate_text_settings=generate_text_settings,
    )


def _build_pickup_service(
    db_session_factory: async_sessionmaker[AsyncSession],
    graph_builder_registry: GenerateTextGraphBuilderRegistry | GenerateTextGraphBuilderRegistryStub,
    background_job_service: BackgroundJobService,
    handoff_queue_service: GenerateTextRunHandoffQueueService,
    *,
    generate_text_settings: GenerateTextSettings | None = None,
    checkpointer: BaseCheckpointSaver | None = None,
) -> GenerateTextRunPickupService:
    generate_text_settings = generate_text_settings or GenerateTextSettings()
    generate_text_service = _build_generate_text_service(
        db_session_factory,
        graph_builder_registry,
        background_job_service,
        handoff_queue_service,
        generate_text_settings,
        checkpointer or InMemorySaver(),
    )
    run_service = GenerateTextRunService(db_session_factory=db_session_factory)
    lease_service = GenerateTextRunLeaseService(
        run_service=run_service,
        handoff_queue_service=handoff_queue_service,
        background_job_service=background_job_service,
        generate_text_settings=generate_text_settings,
    )
    return GenerateTextRunPickupService(
        generate_text_service=generate_text_service,
        lease_service=lease_service,
        handoff_queue_service=handoff_queue_service,
        run_service=run_service,
        background_job_service=background_job_service,
        generate_text_settings=generate_text_settings,
    )


async def test_pick_up_next_expired_run_released_run_resumes_from_checkpoint_to_completion(
    db_session: AsyncSession,
    db_session_factory: async_sessionmaker[AsyncSession],
    background_job_service: BackgroundJobService,
    handoff_queue_service: GenerateTextRunHandoffQueueService,
) -> None:
    auth_user = await _insert_auth_user(db_session)
    find_user_persona_result = await _insert_owner_persona(db_session, auth_user)
    llm_service_stub = LlmServiceStub()
    llm_service_stub.complete_result = build_llm_completion_result(content="# Final\n\nFinal text.")
    llm_service_stub.complete_is_blocked = True
    graph_checkpointer = InMemorySaver()
    generate_text_settings = GenerateTextSettings()
    stopping_generate_text_service = _build_generate_text_service(
        db_session_factory,
        _build_real_graph_builder_registry(
            db_session_factory, llm_service_stub, generate_text_settings
        ),
        background_job_service,
        handoff_queue_service,
        generate_text_settings,
        graph_checkpointer,
    )
    await stopping_generate_text_service.generate_text(
        build_generate_text_input(options=_build_all_auto_approved_options()),
        find_user_persona_result,
        auth_user,
    )
    await llm_service_stub.complete_started_event.wait()
    background_job_service.request_stop()
    llm_service_stub.complete_unblock_event.set()
    await background_job_service.drain(DRAIN_TIMEOUT_SECONDS)
    picking_up_job_service = BackgroundJobService(worker_id="other-worker")
    run_pickup_service = _build_pickup_service(
        db_session_factory,
        _build_real_graph_builder_registry(
            db_session_factory, llm_service_stub, generate_text_settings
        ),
        picking_up_job_service,
        handoff_queue_service,
        checkpointer=graph_checkpointer,
    )

    is_picked_up = await run_pickup_service.pick_up_next_expired_run()

    await picking_up_job_service.drain(DRAIN_TIMEOUT_SECONDS)
    run_query = select(GenerateTextRunOrm).where(GenerateTextRunOrm.created_by_id == auth_user.id)
    run_record = await db_session.scalar(run_query)
    assert is_picked_up is True
    assert run_record is not None
    assert run_record.status == GenerateTextRunStatusType.COMPLETED
    assert run_record.pickup_count == 1
    assert run_record.lease_owner is None
    assert run_record.lease_expires_at is None
    assert run_record.finished_at is not None
    step_query = (
        select(GenerateTextStepOrm.step_name)
        .where(GenerateTextStepOrm.run_id == run_record.id)
        .order_by(GenerateTextStepOrm.step_number)
    )
    step_name_scalars = await db_session.scalars(step_query)
    step_names = step_name_scalars.all()
    assert step_names == ["GENERATE_OUTLINE", "GENERATE_DRAFT"]
    assert len(llm_service_stub.complete_inputs) == 2


async def test_pick_up_next_expired_run_resumes_with_no_graph_input_under_new_lease(
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
        status=GenerateTextRunStatusType.RUNNING,
        lease_owner="dead-worker",
        lease_expires_at=EXPIRED_LEASE_EXPIRES_AT,
    )
    await db_session.commit()
    graph_builder_registry_stub = GenerateTextGraphBuilderRegistryStub()
    graph_stub = graph_builder_registry_stub.get_by_text_type_result.build_graph_result
    graph_stub.astream_is_blocked = True
    run_pickup_service = _build_pickup_service(
        db_session_factory,
        graph_builder_registry_stub,
        background_job_service,
        handoff_queue_service,
        generate_text_settings=GenerateTextSettings(lease_seconds=LONG_LEASE_SECONDS),
    )

    is_picked_up = await run_pickup_service.pick_up_next_expired_run()

    await graph_stub.astream_started_event.wait()
    await db_session.refresh(run_record)
    await background_job_service.drain(0)
    assert is_picked_up is True
    assert graph_stub.astream_inputs == [None]
    assert run_record.status == GenerateTextRunStatusType.RUNNING
    assert run_record.lease_owner == "test-worker"
    assert run_record.lease_expires_at is not None
    assert run_record.lease_expires_at > LONG_LEASE_BOUND


async def test_pick_up_next_expired_run_at_pickup_limit_still_resumes_run(
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
        status=GenerateTextRunStatusType.RUNNING,
        lease_owner="dead-worker",
        lease_expires_at=EXPIRED_LEASE_EXPIRES_AT,
        pickup_count=2,
    )
    await db_session.commit()
    run_pickup_service = _build_pickup_service(
        db_session_factory,
        GenerateTextGraphBuilderRegistryStub(),
        background_job_service,
        handoff_queue_service,
        generate_text_settings=GenerateTextSettings(max_run_pickups=3),
    )

    is_picked_up = await run_pickup_service.pick_up_next_expired_run()

    await background_job_service.drain(DRAIN_TIMEOUT_SECONDS)
    await db_session.refresh(run_record)
    assert is_picked_up is True
    assert run_record.status == GenerateTextRunStatusType.COMPLETED
    assert run_record.pickup_count == 3


async def test_pick_up_next_expired_run_nothing_expired_returns_false(
    db_session: AsyncSession,
    db_session_factory: async_sessionmaker[AsyncSession],
    background_job_service: BackgroundJobService,
    handoff_queue_service: GenerateTextRunHandoffQueueService,
) -> None:
    auth_user = await _insert_auth_user(db_session)
    await insert_generate_text_run_row(
        db_session,
        created_by_id=auth_user.id,
        status=GenerateTextRunStatusType.RUNNING,
        lease_owner="live-worker",
        lease_expires_at=OTHER_WORKER_LEASE_EXPIRES_AT,
    )
    await db_session.commit()
    run_pickup_service = _build_pickup_service(
        db_session_factory,
        GenerateTextGraphBuilderRegistryStub(),
        background_job_service,
        handoff_queue_service,
    )

    is_picked_up = await run_pickup_service.pick_up_next_expired_run()

    assert is_picked_up is False


async def test_pick_up_next_expired_run_stopping_returns_false_and_claims_nothing(
    db_session: AsyncSession,
    db_session_factory: async_sessionmaker[AsyncSession],
    background_job_service: BackgroundJobService,
    handoff_queue_service: GenerateTextRunHandoffQueueService,
) -> None:
    auth_user = await _insert_auth_user(db_session)
    run_record = await insert_generate_text_run_row(
        db_session,
        created_by_id=auth_user.id,
        status=GenerateTextRunStatusType.RUNNING,
        lease_owner="dead-worker",
        lease_expires_at=EXPIRED_LEASE_EXPIRES_AT,
    )
    await db_session.commit()
    run_pickup_service = _build_pickup_service(
        db_session_factory,
        GenerateTextGraphBuilderRegistryStub(),
        background_job_service,
        handoff_queue_service,
    )
    background_job_service.request_stop()

    is_picked_up = await run_pickup_service.pick_up_next_expired_run()

    await db_session.refresh(run_record)
    assert is_picked_up is False
    assert run_record.lease_owner == "dead-worker"
    assert run_record.pickup_count == 0


async def test_pick_up_next_expired_run_pending_run_fails_as_never_started(
    db_session: AsyncSession,
    db_session_factory: async_sessionmaker[AsyncSession],
    background_job_service: BackgroundJobService,
    handoff_queue_service: GenerateTextRunHandoffQueueService,
) -> None:
    auth_user = await _insert_auth_user(db_session)
    run_record = await insert_generate_text_run_row(
        db_session,
        created_by_id=auth_user.id,
        status=GenerateTextRunStatusType.PENDING,
        lease_owner="dead-worker",
        lease_expires_at=EXPIRED_LEASE_EXPIRES_AT,
    )
    await db_session.commit()
    run_pickup_service = _build_pickup_service(
        db_session_factory,
        GenerateTextGraphBuilderRegistryStub(),
        background_job_service,
        handoff_queue_service,
    )

    is_picked_up = await run_pickup_service.pick_up_next_expired_run()

    await db_session.refresh(run_record)
    assert is_picked_up is True
    assert run_record.status == GenerateTextRunStatusType.FAILED
    assert run_record.error_code == "RunNeverStarted"
    assert run_record.lease_owner is None
    assert run_record.lease_expires_at is None
    assert run_record.finished_at is not None


async def test_pick_up_next_expired_run_picked_up_too_often_fails_run(
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
        status=GenerateTextRunStatusType.RUNNING,
        lease_owner="dead-worker",
        lease_expires_at=EXPIRED_LEASE_EXPIRES_AT,
        pickup_count=3,
    )
    await db_session.commit()
    run_pickup_service = _build_pickup_service(
        db_session_factory,
        GenerateTextGraphBuilderRegistryStub(),
        background_job_service,
        handoff_queue_service,
        generate_text_settings=GenerateTextSettings(max_run_pickups=3),
    )

    is_picked_up = await run_pickup_service.pick_up_next_expired_run()

    await db_session.refresh(run_record)
    assert is_picked_up is True
    assert run_record.status == GenerateTextRunStatusType.FAILED
    assert run_record.error_code == "RunPickedUpTooOften"
    assert run_record.pickup_count == 4
    assert run_record.lease_owner is None


async def test_pick_up_next_expired_run_graph_version_mismatch_fails_run(
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
        status=GenerateTextRunStatusType.RUNNING,
        lease_owner="dead-worker",
        lease_expires_at=EXPIRED_LEASE_EXPIRES_AT,
    )
    await db_session.commit()
    generate_text_settings = GenerateTextSettings()
    run_pickup_service = _build_pickup_service(
        db_session_factory,
        _build_real_graph_builder_registry(
            db_session_factory, LlmServiceStub(), generate_text_settings
        ),
        background_job_service,
        handoff_queue_service,
        generate_text_settings=generate_text_settings,
    )

    is_picked_up = await run_pickup_service.pick_up_next_expired_run()

    await db_session.refresh(run_record)
    assert is_picked_up is True
    assert run_record.status == GenerateTextRunStatusType.FAILED
    assert run_record.error_code == "GenerateTextRunVersionMismatchException"
    assert run_record.lease_owner is None


async def test_pick_up_next_expired_run_unbuildable_graph_fails_run(
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
        status=GenerateTextRunStatusType.RUNNING,
        options={"draft": 5},
        lease_owner="dead-worker",
        lease_expires_at=EXPIRED_LEASE_EXPIRES_AT,
    )
    await db_session.commit()
    generate_text_settings = GenerateTextSettings()
    run_pickup_service = _build_pickup_service(
        db_session_factory,
        _build_real_graph_builder_registry(
            db_session_factory, LlmServiceStub(), generate_text_settings
        ),
        background_job_service,
        handoff_queue_service,
        generate_text_settings=generate_text_settings,
    )

    is_picked_up = await run_pickup_service.pick_up_next_expired_run()

    await db_session.refresh(run_record)
    assert is_picked_up is True
    assert run_record.status == GenerateTextRunStatusType.FAILED
    assert run_record.error_code == "GenerateTextOptionsInvalidException"


async def test_pick_up_expired_runs_asks_again_until_no_run_is_picked_up() -> None:
    run_pickup_service_stub = GenerateTextRunPickupServiceStub(
        run_pickup_interval_seconds=LONG_PICKUP_INTERVAL_SECONDS
    )
    run_pickup_service_stub.pick_up_next_expired_run_results = [True, True, False]
    pickup_task = asyncio.create_task(run_pickup_service_stub.pick_up_expired_runs())

    await run_pickup_service_stub.pick_up_next_expired_run_exhausted_event.wait()

    pickup_task.cancel()
    await asyncio.gather(pickup_task, return_exceptions=True)
    assert run_pickup_service_stub.pick_up_next_expired_run_call_count == 3


async def test_pick_up_expired_runs_failed_pickup_does_not_stop_next_pickup() -> None:
    run_pickup_service_stub = GenerateTextRunPickupServiceStub(run_pickup_interval_seconds=0)
    run_pickup_service_stub.pick_up_next_expired_run_results = [
        RuntimeError("pickup failed"),
        False,
    ]
    pickup_task = asyncio.create_task(run_pickup_service_stub.pick_up_expired_runs())

    await run_pickup_service_stub.pick_up_next_expired_run_exhausted_event.wait()

    pickup_task.cancel()
    await asyncio.gather(pickup_task, return_exceptions=True)
    assert run_pickup_service_stub.pick_up_next_expired_run_call_count == 2


async def test_pick_up_handed_off_runs_received_run_id_picks_up_that_run() -> None:
    handoff_queue_service_stub = GenerateTextRunHandoffQueueServiceStub()
    handoff_queue_service_stub.wait_for_run_results = [7]
    run_pickup_service_stub = GenerateTextRunPickupServiceStub(
        run_handoff_wait_seconds=2, handoff_queue_service=handoff_queue_service_stub
    )
    pickup_task = asyncio.create_task(run_pickup_service_stub.pick_up_handed_off_runs())

    await run_pickup_service_stub.pick_up_handed_off_run_event.wait()

    pickup_task.cancel()
    await asyncio.gather(pickup_task, return_exceptions=True)
    assert run_pickup_service_stub.pick_up_handed_off_run_inputs == [7]
    assert handoff_queue_service_stub.wait_for_run_inputs[0] == 2


async def test_pick_up_handed_off_runs_empty_wait_picks_up_nothing() -> None:
    handoff_queue_service_stub = GenerateTextRunHandoffQueueServiceStub()
    handoff_queue_service_stub.wait_for_run_results = [None]
    run_pickup_service_stub = GenerateTextRunPickupServiceStub(
        run_handoff_wait_seconds=0, handoff_queue_service=handoff_queue_service_stub
    )
    pickup_task = asyncio.create_task(run_pickup_service_stub.pick_up_handed_off_runs())

    await handoff_queue_service_stub.wait_for_run_exhausted_event.wait()

    pickup_task.cancel()
    await asyncio.gather(pickup_task, return_exceptions=True)
    assert run_pickup_service_stub.pick_up_handed_off_run_inputs == []


async def test_pick_up_handed_off_runs_wait_raises_logs_failure_and_carries_on() -> None:
    handoff_queue_service_stub = GenerateTextRunHandoffQueueServiceStub()
    handoff_queue_service_stub.wait_for_run_results = [ConnectionError("redis unreachable"), 7]
    run_pickup_service_stub = GenerateTextRunPickupServiceStub(
        run_handoff_wait_seconds=0, handoff_queue_service=handoff_queue_service_stub
    )
    pickup_task = asyncio.create_task(run_pickup_service_stub.pick_up_handed_off_runs())

    with structlog.testing.capture_logs() as captured_log_events:
        await run_pickup_service_stub.pick_up_handed_off_run_event.wait()

    pickup_task.cancel()
    await asyncio.gather(pickup_task, return_exceptions=True)
    handoff_pickup_failed_log_events = [
        log_event
        for log_event in captured_log_events
        if log_event["event"] == "run_handoff_pickup_failed"
    ]
    assert len(handoff_pickup_failed_log_events) >= 1
    assert run_pickup_service_stub.pick_up_handed_off_run_inputs == [7]


async def test_pick_up_handed_off_run_named_run_continues_and_leaves_older_expired_run_alone(
    db_session: AsyncSession,
    db_session_factory: async_sessionmaker[AsyncSession],
    background_job_service: BackgroundJobService,
    handoff_queue_service: GenerateTextRunHandoffQueueService,
) -> None:
    auth_user = await _insert_auth_user(db_session)
    older_run_record = await insert_generate_text_run_row(
        db_session,
        created_by_id=auth_user.id,
        graph_version="stub-version",
        status=GenerateTextRunStatusType.RUNNING,
        lease_owner="dead-worker",
        lease_expires_at=datetime(2026, 1, 1, tzinfo=UTC),
    )
    handed_off_run_record = await insert_generate_text_run_row(
        db_session,
        created_by_id=auth_user.id,
        graph_version="stub-version",
        status=GenerateTextRunStatusType.RUNNING,
        lease_owner="dead-worker",
        lease_expires_at=EXPIRED_LEASE_EXPIRES_AT,
    )
    await db_session.commit()
    run_pickup_service = _build_pickup_service(
        db_session_factory,
        GenerateTextGraphBuilderRegistryStub(),
        background_job_service,
        handoff_queue_service,
    )

    await run_pickup_service.pick_up_handed_off_run(handed_off_run_record.id)

    await background_job_service.drain(DRAIN_TIMEOUT_SECONDS)
    await db_session.refresh(older_run_record)
    await db_session.refresh(handed_off_run_record)
    assert handed_off_run_record.status == GenerateTextRunStatusType.COMPLETED
    assert handed_off_run_record.pickup_count == 1
    assert older_run_record.status == GenerateTextRunStatusType.RUNNING
    assert older_run_record.lease_owner == "dead-worker"
    assert older_run_record.pickup_count == 0


async def test_pick_up_handed_off_run_pending_run_fails_as_never_started(
    db_session: AsyncSession,
    db_session_factory: async_sessionmaker[AsyncSession],
    background_job_service: BackgroundJobService,
    handoff_queue_service: GenerateTextRunHandoffQueueService,
) -> None:
    auth_user = await _insert_auth_user(db_session)
    run_record = await insert_generate_text_run_row(
        db_session,
        created_by_id=auth_user.id,
        status=GenerateTextRunStatusType.PENDING,
        lease_owner="dead-worker",
        lease_expires_at=EXPIRED_LEASE_EXPIRES_AT,
    )
    await db_session.commit()
    run_pickup_service = _build_pickup_service(
        db_session_factory,
        GenerateTextGraphBuilderRegistryStub(),
        background_job_service,
        handoff_queue_service,
    )

    await run_pickup_service.pick_up_handed_off_run(run_record.id)

    await db_session.refresh(run_record)
    assert run_record.status == GenerateTextRunStatusType.FAILED
    assert run_record.error_code == "RunNeverStarted"


async def test_pick_up_handed_off_run_picked_up_too_often_fails_run(
    db_session: AsyncSession,
    db_session_factory: async_sessionmaker[AsyncSession],
    background_job_service: BackgroundJobService,
    handoff_queue_service: GenerateTextRunHandoffQueueService,
) -> None:
    auth_user = await _insert_auth_user(db_session)
    run_record = await insert_generate_text_run_row(
        db_session,
        created_by_id=auth_user.id,
        status=GenerateTextRunStatusType.RUNNING,
        lease_owner="dead-worker",
        lease_expires_at=EXPIRED_LEASE_EXPIRES_AT,
        pickup_count=3,
    )
    await db_session.commit()
    run_pickup_service = _build_pickup_service(
        db_session_factory,
        GenerateTextGraphBuilderRegistryStub(),
        background_job_service,
        handoff_queue_service,
        generate_text_settings=GenerateTextSettings(max_run_pickups=3),
    )

    await run_pickup_service.pick_up_handed_off_run(run_record.id)

    await db_session.refresh(run_record)
    assert run_record.status == GenerateTextRunStatusType.FAILED
    assert run_record.error_code == "RunPickedUpTooOften"
    assert run_record.pickup_count == 4


async def test_pick_up_handed_off_run_unexpired_lease_claims_nothing(
    db_session: AsyncSession,
    db_session_factory: async_sessionmaker[AsyncSession],
    background_job_service: BackgroundJobService,
    handoff_queue_service: GenerateTextRunHandoffQueueService,
) -> None:
    auth_user = await _insert_auth_user(db_session)
    run_record = await insert_generate_text_run_row(
        db_session,
        created_by_id=auth_user.id,
        status=GenerateTextRunStatusType.RUNNING,
        lease_owner="live-worker",
        lease_expires_at=OTHER_WORKER_LEASE_EXPIRES_AT,
    )
    await db_session.commit()
    run_pickup_service = _build_pickup_service(
        db_session_factory,
        GenerateTextGraphBuilderRegistryStub(),
        background_job_service,
        handoff_queue_service,
    )

    await run_pickup_service.pick_up_handed_off_run(run_record.id)

    await db_session.refresh(run_record)
    assert run_record.status == GenerateTextRunStatusType.RUNNING
    assert run_record.lease_owner == "live-worker"
    assert run_record.pickup_count == 0


async def test_pick_up_handed_off_run_already_claimed_run_claims_nothing_again(
    db_session: AsyncSession,
    db_session_factory: async_sessionmaker[AsyncSession],
    background_job_service: BackgroundJobService,
    handoff_queue_service: GenerateTextRunHandoffQueueService,
) -> None:
    auth_user = await _insert_auth_user(db_session)
    run_record = await insert_generate_text_run_row(
        db_session,
        created_by_id=auth_user.id,
        status=GenerateTextRunStatusType.RUNNING,
        lease_owner="dead-worker",
        lease_expires_at=EXPIRED_LEASE_EXPIRES_AT,
        pickup_count=3,
    )
    await db_session.commit()
    run_pickup_service = _build_pickup_service(
        db_session_factory,
        GenerateTextGraphBuilderRegistryStub(),
        background_job_service,
        handoff_queue_service,
        generate_text_settings=GenerateTextSettings(max_run_pickups=3),
    )
    await run_pickup_service.pick_up_handed_off_run(run_record.id)

    await run_pickup_service.pick_up_handed_off_run(run_record.id)

    await db_session.refresh(run_record)
    assert run_record.pickup_count == 4


async def test_pick_up_handed_off_run_stopping_claims_nothing(
    db_session: AsyncSession,
    db_session_factory: async_sessionmaker[AsyncSession],
    background_job_service: BackgroundJobService,
    handoff_queue_service: GenerateTextRunHandoffQueueService,
) -> None:
    auth_user = await _insert_auth_user(db_session)
    run_record = await insert_generate_text_run_row(
        db_session,
        created_by_id=auth_user.id,
        status=GenerateTextRunStatusType.RUNNING,
        lease_owner="dead-worker",
        lease_expires_at=EXPIRED_LEASE_EXPIRES_AT,
    )
    await db_session.commit()
    run_pickup_service = _build_pickup_service(
        db_session_factory,
        GenerateTextGraphBuilderRegistryStub(),
        background_job_service,
        handoff_queue_service,
    )
    background_job_service.request_stop()

    await run_pickup_service.pick_up_handed_off_run(run_record.id)

    await db_session.refresh(run_record)
    assert run_record.lease_owner == "dead-worker"
    assert run_record.pickup_count == 0
