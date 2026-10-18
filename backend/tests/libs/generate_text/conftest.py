import pytest
from redis.asyncio import Redis

from libs.core.services import BackgroundJobService
from libs.generate_text.services.generate_text_run_handoff_queue_service import (
    GenerateTextRunHandoffQueueService,
)


@pytest.fixture
def background_job_service() -> BackgroundJobService:
    return BackgroundJobService(worker_id="test-worker")


@pytest.fixture
def handoff_queue_service(redis_client: Redis) -> GenerateTextRunHandoffQueueService:
    return GenerateTextRunHandoffQueueService(redis_client=redis_client)
