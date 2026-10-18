import pytest

from libs.core.services import BackgroundJobService


@pytest.fixture
def background_job_service() -> BackgroundJobService:
    return BackgroundJobService(worker_id="test-worker")
