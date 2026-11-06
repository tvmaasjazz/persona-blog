from uuid import UUID

from fastapi import APIRouter

from apps.api.core.dependencies import AnonymousUserKeyDep, OptionalAuthUserDep
from apps.api.core.dtos import EmptyResponseDto
from apps.api.domains.content_items.dependencies import ContentItemViewServiceDep
from apps.api.domains.content_items.dtos import RecordContentItemViewDto

content_item_router = APIRouter(prefix="/content-items", tags=["content-items"])


@content_item_router.put("/{content_item_identity}/view")
async def record_content_item_view(
    content_item_identity: UUID,
    dto: RecordContentItemViewDto,
    anonymous_user_key: AnonymousUserKeyDep,
    auth_user: OptionalAuthUserDep,
    content_item_view_service: ContentItemViewServiceDep,
) -> EmptyResponseDto:
    """Records a view of a content item, once per reader per day, with how far it was read;
    404 when the reader can't see the item, and nothing is recorded for its own creator."""
    await content_item_view_service.record_content_item_view(
        content_item_identity, dto.to_input(), anonymous_user_key, auth_user
    )
    return EmptyResponseDto()
