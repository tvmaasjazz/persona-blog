from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from libs.auth.results import AuthUser
from libs.content_items.services import ContentItemValidationService
from libs.database.orm import BlogPostOrm, ContentItemOrm, PersonaOrm


class BlogPostValidationService:
    def __init__(
        self,
        db_session: AsyncSession,
        content_item_validation_service: ContentItemValidationService,
    ) -> None:
        self._db_session = db_session
        self._content_item_validation_service = content_item_validation_service

    async def validate_blog_post_visibility(
        self, blog_post_identity: UUID, is_public: bool, auth_user: AuthUser
    ) -> None:
        persona_identity_query = (
            select(PersonaOrm.identity)
            .select_from(BlogPostOrm)
            .join(ContentItemOrm, BlogPostOrm.content_item_id == ContentItemOrm.id)
            .join(PersonaOrm, ContentItemOrm.persona_id == PersonaOrm.id)
            .where(
                BlogPostOrm.identity == blog_post_identity,
                BlogPostOrm.created_by_id == auth_user.id,
            )
        )
        persona_identity_query_result = await self._db_session.execute(persona_identity_query)
        persona_identity = persona_identity_query_result.scalar_one_or_none()

        if persona_identity is None:
            return
        await self._content_item_validation_service.validate_persona_allows_public(
            persona_identity, is_public, auth_user
        )
