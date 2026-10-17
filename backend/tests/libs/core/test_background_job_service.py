import asyncio

import structlog.testing

from libs.core.services import BackgroundJobService


async def test_start_task_runs_to_completion() -> None:
    background_job_service = BackgroundJobService(worker_id="test-worker")
    finished_labels: list[str] = []

    async def finish_after_yield() -> None:
        await asyncio.sleep(0)
        finished_labels.append("finished")

    background_job_service.start(finish_after_yield())
    await background_job_service.drain(timeout_seconds=5)

    assert finished_labels == ["finished"]


async def test_start_task_exception_is_logged_and_does_not_propagate() -> None:
    background_job_service = BackgroundJobService(worker_id="test-worker")
    task_failure = ValueError("boom")

    async def raise_failure() -> None:
        raise task_failure

    with structlog.testing.capture_logs() as captured_log_events:
        background_job_service.start(raise_failure())
        await background_job_service.drain(timeout_seconds=5)

    background_job_failed_events = [
        log_event
        for log_event in captured_log_events
        if log_event["event"] == "background_job_failed"
    ]
    assert len(background_job_failed_events) == 1
    assert background_job_failed_events[0]["log_level"] == "error"
    assert background_job_failed_events[0]["exc_info"] is task_failure


async def test_drain_waits_for_tasks_that_finish_within_timeout() -> None:
    background_job_service = BackgroundJobService(worker_id="test-worker")
    finished_labels: list[str] = []
    cancelled_labels: list[str] = []

    async def finish_after_yields(label: str) -> None:
        try:
            await asyncio.sleep(0)
            await asyncio.sleep(0)
            finished_labels.append(label)
        except asyncio.CancelledError:
            cancelled_labels.append(label)
            raise

    background_job_service.start(finish_after_yields("first"))
    background_job_service.start(finish_after_yields("second"))
    await background_job_service.drain(timeout_seconds=5)

    assert sorted(finished_labels) == ["first", "second"]
    assert cancelled_labels == []


async def test_drain_cancels_tasks_still_running_after_timeout() -> None:
    background_job_service = BackgroundJobService(worker_id="test-worker")
    never_set_event = asyncio.Event()
    cancelled_labels: list[str] = []

    async def wait_forever() -> None:
        try:
            await never_set_event.wait()
        except asyncio.CancelledError:
            cancelled_labels.append("stuck")
            raise

    background_job_service.start(wait_forever())
    await asyncio.sleep(0)
    with structlog.testing.capture_logs() as captured_log_events:
        await background_job_service.drain(timeout_seconds=0)

    assert cancelled_labels == ["stuck"]
    assert [log_event["event"] for log_event in captured_log_events] == []


def test_worker_id_returns_id_given_at_construction() -> None:
    background_job_service = BackgroundJobService(worker_id="replica-pid42-ab12")

    assert background_job_service.worker_id == "replica-pid42-ab12"


def test_is_stopping_new_service_is_false() -> None:
    background_job_service = BackgroundJobService(worker_id="test-worker")

    assert background_job_service.is_stopping is False


def test_request_stop_sets_is_stopping() -> None:
    background_job_service = BackgroundJobService(worker_id="test-worker")

    background_job_service.request_stop()

    assert background_job_service.is_stopping is True


async def test_drain_does_not_set_is_stopping() -> None:
    background_job_service = BackgroundJobService(worker_id="test-worker")

    await background_job_service.drain(timeout_seconds=0)

    assert background_job_service.is_stopping is False
