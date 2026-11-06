from typing import Annotated

from fastapi import Depends, Request

from apps.api.core.config import AppSettings
from apps.api.core.dependencies import DbSessionDep
from libs.content_engagement.services import ContentEngagementService, ContentViewService
from libs.content_items.services import ContentItemViewService


def get_content_engagement_service(
    request: Request, db_session: DbSessionDep
) -> ContentEngagementService:
    app_settings: AppSettings = request.app.state.settings
    return ContentEngagementService(
        db_session=db_session, content_engagement_settings=app_settings.content_engagement
    )


ContentEngagementServiceDep = Annotated[
    ContentEngagementService, Depends(get_content_engagement_service)
]


def get_content_view_service(
    db_session: DbSessionDep, content_engagement_service: ContentEngagementServiceDep
) -> ContentViewService:
    return ContentViewService(
        db_session=db_session, content_engagement_service=content_engagement_service
    )


ContentViewServiceDep = Annotated[ContentViewService, Depends(get_content_view_service)]


def get_content_item_view_service(
    db_session: DbSessionDep, content_view_service: ContentViewServiceDep
) -> ContentItemViewService:
    return ContentItemViewService(db_session=db_session, content_view_service=content_view_service)


ContentItemViewServiceDep = Annotated[
    ContentItemViewService, Depends(get_content_item_view_service)
]
