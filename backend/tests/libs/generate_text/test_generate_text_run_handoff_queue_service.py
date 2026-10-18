from redis.asyncio import Redis

from libs.generate_text.services.generate_text_run_handoff_queue_service import (
    GenerateTextRunHandoffQueueService,
)

NO_WAIT_TIMEOUT_SECONDS = 0.01
WAIT_TIMEOUT_SECONDS = 1


async def test_push_run_adds_run_id_to_handoff_list(
    redis_client: Redis, handoff_queue_service: GenerateTextRunHandoffQueueService
) -> None:
    await handoff_queue_service.push_run(42)

    handoff_list_length = await redis_client.llen("generate_text:run_handoff")
    handoff_list_items = await redis_client.lrange("generate_text:run_handoff", 0, -1)
    assert handoff_list_length == 1
    assert handoff_list_items == [b"42"]


async def test_wait_for_run_returns_pushed_run_id(
    handoff_queue_service: GenerateTextRunHandoffQueueService,
) -> None:
    await handoff_queue_service.push_run(42)

    waited_run_id = await handoff_queue_service.wait_for_run(WAIT_TIMEOUT_SECONDS)

    assert waited_run_id == 42


async def test_wait_for_run_two_pushes_return_in_push_order(
    handoff_queue_service: GenerateTextRunHandoffQueueService,
) -> None:
    await handoff_queue_service.push_run(7)
    await handoff_queue_service.push_run(9)

    first_run_id = await handoff_queue_service.wait_for_run(WAIT_TIMEOUT_SECONDS)
    second_run_id = await handoff_queue_service.wait_for_run(WAIT_TIMEOUT_SECONDS)

    assert [first_run_id, second_run_id] == [7, 9]


async def test_wait_for_run_nothing_pushed_returns_none(
    handoff_queue_service: GenerateTextRunHandoffQueueService,
) -> None:
    waited_run_id = await handoff_queue_service.wait_for_run(NO_WAIT_TIMEOUT_SECONDS)

    assert waited_run_id is None
