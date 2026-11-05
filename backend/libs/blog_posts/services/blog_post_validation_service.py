from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from libs.auth.results import AuthUser
from libs.content_items.services import ContentItemValidationService
from libs.database.orm import BlogPostOrm, ContentItemOrm, PersonaOrm


class BlogPostValidationService:
    """The checks on an incoming blog post payload that need the database."""

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
        """Rejects turning the caller's private post public when its persona is private; a post
        already public passes."""
        persona_identity_query = (
            select(PersonaOrm.identity, ContentItemOrm.is_public)
            .select_from(BlogPostOrm)
            .join(ContentItemOrm, BlogPostOrm.content_item_id == ContentItemOrm.id)
            .join(PersonaOrm, ContentItemOrm.persona_id == PersonaOrm.id)
            .where(
                BlogPostOrm.identity == blog_post_identity,
                BlogPostOrm.created_by_id == auth_user.id,
            )
        )
        persona_identity_query_result = await self._db_session.execute(persona_identity_query)
        persona_identity_row = persona_identity_query_result.one_or_none()

        if persona_identity_row is None:
            return
        persona_identity, is_already_public = persona_identity_row
        # A post already public stays valid even if its persona has since gone private
        if is_already_public:
            return
        await self._content_item_validation_service.validate_persona_allows_public(
            persona_identity, is_public, auth_user
        )
