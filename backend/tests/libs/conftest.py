import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from libs.content_engagement.services import ContentEngagementService
from tests.factories.content_engagement import build_content_engagement_settings


@pytest.fixture
def content_engagement_service(db_session: AsyncSession) -> ContentEngagementService:
    return ContentEngagementService(
        db_session=db_session, content_engagement_settings=build_content_engagement_settings()
    )
