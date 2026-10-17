import pytest

from libs.core.services import BackgroundTaskService


@pytest.fixture
def background_task_service() -> BackgroundTaskService:
    return BackgroundTaskService()
