from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from libs.auth.results import AuthUser
from libs.blog_posts.inputs import RecordBlogPostViewInput
from libs.content_engagement.inputs import RecordContentViewInput
from libs.content_engagement.services import ContentViewService
from libs.content_items.utils.content_item_query_utils import ContentItemQueryUtils
from libs.core.exceptions import NotFoundException
from libs.database.orm import BlogPostOrm, ContentItemOrm, PersonaOrm


class BlogPostViewService:
    """Records readers' views of blog posts."""

    def __init__(self, db_session: AsyncSession, content_view_service: ContentViewService) -> None:
        self._db_session = db_session
        self._content_view_service = content_view_service

    async def record_blog_post_view(
        self,
        blog_post_identity: UUID,
        record_blog_post_view_input: RecordBlogPostViewInput,
        anonymous_user_key: str | None,
        auth_user: AuthUser | None,
    ) -> None:
        """Records the reader's view of a post they may read, nothing for the post's own
        creator; NotFoundException when they can't read it."""
        # Find the post under the same access rule as the public read
        auth_user_id = auth_user.id if auth_user is not None else None
        blog_post_query = (
            select(BlogPostOrm.content_item_id, ContentItemOrm.created_by_id)
            .join(ContentItemOrm, BlogPostOrm.content_item_id == ContentItemOrm.id)
            .join(PersonaOrm, ContentItemOrm.persona_id == PersonaOrm.id)
            .where(
                BlogPostOrm.identity == blog_post_identity,
                BlogPostOrm.deleted_at.is_(None),
                ContentItemOrm.deleted_at.is_(None),
                ContentItemQueryUtils.build_accessible_condition(auth_user_id),
            )
        )
        blog_post_query_result = await self._db_session.execute(blog_post_query)
        blog_post_row = blog_post_query_result.one_or_none()
        if blog_post_row is None:
            raise NotFoundException("Blog post not found")

        # A creator reading their own post is not a view
        if auth_user_id is not None and blog_post_row.created_by_id == auth_user_id:
            return

        # Record the view
        record_content_view_input = RecordContentViewInput(
            content_item_id=blog_post_row.content_item_id,
            read_percent=record_blog_post_view_input.read_percent,
            anonymous_user_key=anonymous_user_key,
        )
        await self._content_view_service.record_content_view(record_content_view_input, auth_user)
