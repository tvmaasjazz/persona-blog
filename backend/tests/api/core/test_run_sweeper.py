import asyncio

from apps.api.core.run_sweeper import sweep_expired_runs
from libs.generate_text.services import GenerateTextService
from tests.stubs.generate_text import GenerateTextServiceStub

LONG_SWEEP_INTERVAL_SECONDS = 3600


async def test_sweep_expired_runs_asks_again_until_no_run_is_picked_up() -> None:
    generate_text_service_stub = GenerateTextServiceStub()
    generate_text_service_stub.pick_up_expired_run_results = [True, True, False]
    sweep_task = asyncio.create_task(
        sweep_expired_runs(lambda: generate_text_service_stub, LONG_SWEEP_INTERVAL_SECONDS)
    )

    await generate_text_service_stub.pick_up_expired_run_exhausted_event.wait()

    sweep_task.cancel()
    await asyncio.gather(sweep_task, return_exceptions=True)
    assert generate_text_service_stub.pick_up_expired_run_call_count == 3


async def test_sweep_expired_runs_failed_sweep_does_not_stop_next_sweep() -> None:
    generate_text_service_stub = GenerateTextServiceStub()
    generate_text_service_stub.pick_up_expired_run_results = [False]
    build_outcomes: list[GenerateTextService | Exception] = [
        RuntimeError("builder failed"),
        generate_text_service_stub,
    ]

    def build_generate_text_service() -> GenerateTextService:
        build_outcome = build_outcomes.pop(0)
        if isinstance(build_outcome, Exception):
            raise build_outcome
        return build_outcome

    sweep_task = asyncio.create_task(sweep_expired_runs(build_generate_text_service, 0))

    await generate_text_service_stub.pick_up_expired_run_exhausted_event.wait()

    sweep_task.cancel()
    await asyncio.gather(sweep_task, return_exceptions=True)
    assert generate_text_service_stub.pick_up_expired_run_call_count == 1
