from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from libs.auth.results import AuthUser
from libs.blog_posts.constants import ALLOWED_BODY_HEADING_LEVELS, IMPLICIT_TITLE_HEADING_LEVEL
from libs.blog_posts.exceptions import BlogPostBodyInvalidException
from libs.content_items.services import ContentItemValidationService
from libs.core.utils.markdown_utils import MarkdownUtils
from libs.database.orm import BlogPostOrm, ContentItemOrm, PersonaOrm


class BlogPostValidationService:
    def __init__(
        self,
        db_session: AsyncSession,
        content_item_validation_service: ContentItemValidationService,
    ) -> None:
        self._db_session = db_session
        self._content_item_validation_service = content_item_validation_service

    def validate_blog_post_body(self, body: str) -> None:
        problems: list[str] = []
        heading_levels = MarkdownUtils.find_heading_levels(body)

        if any(heading_level == IMPLICIT_TITLE_HEADING_LEVEL for heading_level in heading_levels):
            problems.append("The body must not contain an H1 heading")
        if any(
            heading_level not in ALLOWED_BODY_HEADING_LEVELS for heading_level in heading_levels
        ):
            problems.append("The body may only use H2 and H3 headings")

        previous_heading_level = IMPLICIT_TITLE_HEADING_LEVEL
        for heading_level in heading_levels:
            if heading_level > previous_heading_level + 1:
                problems.append(
                    f"Heading level jumps from H{previous_heading_level} to "
                    f"H{heading_level} without an H{previous_heading_level + 1} first"
                )
            previous_heading_level = heading_level

        if MarkdownUtils.has_raw_html(body):
            problems.append("The body must not contain raw HTML")
        if MarkdownUtils.has_image(body):
            problems.append("The body must not contain images")

        if problems:
            raise BlogPostBodyInvalidException("; ".join(problems))

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
