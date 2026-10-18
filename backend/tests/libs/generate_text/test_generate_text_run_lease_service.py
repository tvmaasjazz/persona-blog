import asyncio
from datetime import UTC, datetime

import structlog
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from libs.core.services import BackgroundJobService
from libs.generate_text.services.generate_text_run_handoff_queue_service import (
    GenerateTextRunHandoffQueueService,
)
from libs.generate_text.services.generate_text_run_lease_service import (
    GenerateTextRunLeaseService,
)
from libs.generate_text.services.generate_text_run_service import GenerateTextRunService
from libs.generate_text.settings import GenerateTextSettings
from libs.generate_text.types import GenerateTextRunStatusType
from tests.factories.generate_text import insert_generate_text_run_row
from tests.factories.users import insert_user_row
from tests.stubs.generate_text import (
    GenerateTextRunHandoffQueueServiceStub,
    GenerateTextRunServiceStub,
)

EXPIRED_LEASE_EXPIRES_AT = datetime(2026, 1, 2, 3, 4, 5, tzinfo=UTC)
FAR_FUTURE_LEASE_EXPIRES_AT = datetime(2099, 1, 2, 3, 4, 5, tzinfo=UTC)


def _build_lease_service(
    run_service: GenerateTextRunService,
    handoff_queue_service: GenerateTextRunHandoffQueueService,
    background_job_service: BackgroundJobService,
    *,
    lease_heartbeat_seconds: int = 3600,
) -> GenerateTextRunLeaseService:
    return GenerateTextRunLeaseService(
        run_service=run_service,
        handoff_queue_service=handoff_queue_service,
        background_job_service=background_job_service,
        generate_text_settings=GenerateTextSettings(
            lease_seconds=3600, lease_heartbeat_seconds=lease_heartbeat_seconds
        ),
    )


async def test_keep_lease_alive_renewal_moves_lease_expiry_later_and_keeps_owner(
    db_session: AsyncSession,
    db_session_factory: async_sessionmaker[AsyncSession],
    background_job_service: BackgroundJobService,
    handoff_queue_service: GenerateTextRunHandoffQueueService,
) -> None:
    user_record = await insert_user_row(db_session)
    run_record = await insert_generate_text_run_row(
        db_session,
        created_by_id=user_record.id,
        status=GenerateTextRunStatusType.RUNNING,
        lease_owner="test-worker",
        lease_expires_at=EXPIRED_LEASE_EXPIRES_AT,
    )
    await db_session.commit()
    run_service_stub = GenerateTextRunServiceStub(GenerateTextRunService(db_session_factory))
    lease_service = _build_lease_service(
        run_service_stub, handoff_queue_service, background_job_service, lease_heartbeat_seconds=1
    )

    async with lease_service.keep_lease_alive(run_record.id):
        await run_service_stub.renew_lease_event.wait()

    await db_session.refresh(run_record)
    assert run_service_stub.renew_lease_inputs[0][:2] == (run_record.id, "test-worker")
    assert run_record.lease_owner == "test-worker"
    assert run_record.lease_expires_at is not None
    assert run_record.lease_expires_at > EXPIRED_LEASE_EXPIRES_AT


async def test_keep_lease_alive_renewal_raises_logs_failure_and_does_not_cancel_job(
    db_session: AsyncSession,
    db_session_factory: async_sessionmaker[AsyncSession],
    background_job_service: BackgroundJobService,
    handoff_queue_service: GenerateTextRunHandoffQueueService,
) -> None:
    user_record = await insert_user_row(db_session)
    run_record = await insert_generate_text_run_row(
        db_session,
        created_by_id=user_record.id,
        status=GenerateTextRunStatusType.RUNNING,
        lease_owner="test-worker",
        lease_expires_at=FAR_FUTURE_LEASE_EXPIRES_AT,
    )
    await db_session.commit()
    run_service_stub = GenerateTextRunServiceStub(GenerateTextRunService(db_session_factory))
    run_service_stub.renew_lease_error = RuntimeError("database unreachable")
    lease_service = _build_lease_service(
        run_service_stub, handoff_queue_service, background_job_service, lease_heartbeat_seconds=1
    )
    is_block_finished = False

    with structlog.testing.capture_logs() as captured_log_events:
        async with lease_service.keep_lease_alive(run_record.id):
            await run_service_stub.renew_lease_event.wait()
            is_block_finished = True

    renewal_failed_log_events = [
        log_event
        for log_event in captured_log_events
        if log_event["event"] == "lease_renewal_failed"
    ]
    assert is_block_finished is True
    assert len(renewal_failed_log_events) == 1
    assert renewal_failed_log_events[0]["run_id"] == run_record.id


async def test_keep_lease_alive_block_cancelled_releases_lease_pushes_run_and_reraises(
    db_session: AsyncSession,
    db_session_factory: async_sessionmaker[AsyncSession],
    background_job_service: BackgroundJobService,
    handoff_queue_service: GenerateTextRunHandoffQueueService,
    redis_client: Redis,
) -> None:
    user_record = await insert_user_row(db_session)
    run_record = await insert_generate_text_run_row(
        db_session,
        created_by_id=user_record.id,
        status=GenerateTextRunStatusType.RUNNING,
        lease_owner="test-worker",
        lease_expires_at=FAR_FUTURE_LEASE_EXPIRES_AT,
    )
    await db_session.commit()
    lease_service = _build_lease_service(
        GenerateTextRunService(db_session_factory), handoff_queue_service, background_job_service
    )
    block_entered_event = asyncio.Event()

    async def hold_lease() -> None:
        async with lease_service.keep_lease_alive(run_record.id):
            block_entered_event.set()
            await asyncio.Event().wait()

    hold_lease_task = asyncio.create_task(hold_lease())
    await block_entered_event.wait()

    hold_lease_task.cancel()

    await asyncio.gather(hold_lease_task, return_exceptions=True)
    await db_session.refresh(run_record)
    handoff_list_items = await redis_client.lrange("generate_text:run_handoff", 0, -1)
    assert hold_lease_task.cancelled() is True
    assert handoff_list_items == [str(run_record.id).encode()]
    assert run_record.lease_owner == "test-worker"
    assert run_record.lease_expires_at is not None
    assert run_record.lease_expires_at < FAR_FUTURE_LEASE_EXPIRES_AT


async def test_keep_lease_alive_normal_exit_does_not_release_lease(
    db_session: AsyncSession,
    db_session_factory: async_sessionmaker[AsyncSession],
    background_job_service: BackgroundJobService,
    handoff_queue_service: GenerateTextRunHandoffQueueService,
) -> None:
    user_record = await insert_user_row(db_session)
    run_record = await insert_generate_text_run_row(
        db_session,
        created_by_id=user_record.id,
        status=GenerateTextRunStatusType.RUNNING,
        lease_owner="test-worker",
        lease_expires_at=FAR_FUTURE_LEASE_EXPIRES_AT,
    )
    await db_session.commit()
    lease_service = _build_lease_service(
        GenerateTextRunService(db_session_factory), handoff_queue_service, background_job_service
    )

    async with lease_service.keep_lease_alive(run_record.id):
        pass

    await db_session.refresh(run_record)
    assert run_record.lease_owner == "test-worker"
    assert run_record.lease_expires_at == FAR_FUTURE_LEASE_EXPIRES_AT


async def test_hand_off_run_owned_lease_releases_lease_and_pushes_run_id(
    db_session: AsyncSession,
    db_session_factory: async_sessionmaker[AsyncSession],
    background_job_service: BackgroundJobService,
    handoff_queue_service: GenerateTextRunHandoffQueueService,
    redis_client: Redis,
) -> None:
    user_record = await insert_user_row(db_session)
    run_record = await insert_generate_text_run_row(
        db_session,
        created_by_id=user_record.id,
        status=GenerateTextRunStatusType.RUNNING,
        lease_owner="test-worker",
        lease_expires_at=FAR_FUTURE_LEASE_EXPIRES_AT,
    )
    await db_session.commit()
    lease_service = _build_lease_service(
        GenerateTextRunService(db_session_factory), handoff_queue_service, background_job_service
    )

    await lease_service.hand_off_run(run_record.id)

    await db_session.refresh(run_record)
    handoff_list_items = await redis_client.lrange("generate_text:run_handoff", 0, -1)
    assert run_record.lease_owner == "test-worker"
    assert run_record.lease_expires_at is not None
    assert run_record.lease_expires_at < FAR_FUTURE_LEASE_EXPIRES_AT
    assert handoff_list_items == [str(run_record.id).encode()]


async def test_hand_off_run_other_workers_lease_neither_releases_nor_pushes(
    db_session: AsyncSession,
    db_session_factory: async_sessionmaker[AsyncSession],
    background_job_service: BackgroundJobService,
    handoff_queue_service: GenerateTextRunHandoffQueueService,
    redis_client: Redis,
) -> None:
    user_record = await insert_user_row(db_session)
    run_record = await insert_generate_text_run_row(
        db_session,
        created_by_id=user_record.id,
        status=GenerateTextRunStatusType.RUNNING,
        lease_owner="other-worker",
        lease_expires_at=FAR_FUTURE_LEASE_EXPIRES_AT,
    )
    await db_session.commit()
    lease_service = _build_lease_service(
        GenerateTextRunService(db_session_factory), handoff_queue_service, background_job_service
    )

    await lease_service.hand_off_run(run_record.id)

    await db_session.refresh(run_record)
    handoff_list_length = await redis_client.llen("generate_text:run_handoff")
    assert run_record.lease_owner == "other-worker"
    assert run_record.lease_expires_at == FAR_FUTURE_LEASE_EXPIRES_AT
    assert handoff_list_length == 0


async def test_hand_off_run_push_raises_logs_failure_and_still_releases_lease(
    db_session: AsyncSession,
    db_session_factory: async_sessionmaker[AsyncSession],
    background_job_service: BackgroundJobService,
) -> None:
    user_record = await insert_user_row(db_session)
    run_record = await insert_generate_text_run_row(
        db_session,
        created_by_id=user_record.id,
        status=GenerateTextRunStatusType.RUNNING,
        lease_owner="test-worker",
        lease_expires_at=FAR_FUTURE_LEASE_EXPIRES_AT,
    )
    await db_session.commit()
    handoff_queue_service_stub = GenerateTextRunHandoffQueueServiceStub()
    handoff_queue_service_stub.push_run_error = ConnectionError("redis unreachable")
    lease_service = _build_lease_service(
        GenerateTextRunService(db_session_factory),
        handoff_queue_service_stub,
        background_job_service,
    )

    with structlog.testing.capture_logs() as captured_log_events:
        await lease_service.hand_off_run(run_record.id)

    await db_session.refresh(run_record)
    send_failed_log_events = [
        log_event
        for log_event in captured_log_events
        if log_event["event"] == "run_handoff_send_failed"
    ]
    assert len(send_failed_log_events) == 1
    assert send_failed_log_events[0]["run_id"] == run_record.id
    assert handoff_queue_service_stub.push_run_inputs == [run_record.id]
    assert run_record.lease_expires_at is not None
    assert run_record.lease_expires_at < FAR_FUTURE_LEASE_EXPIRES_AT
