from datetime import datetime
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from libs.blog_posts.inputs import (
    CreateBlogPostInput,
    FindPublicBlogPostPageInput,
    FindUserBlogPostPageInput,
    UpdateBlogPostInput,
)
from libs.blog_posts.types import PublicBlogPostSortType, UserBlogPostSortType
from libs.core.types import SortDirectionType
from libs.database.orm import BlogPostOrm
from tests.factories.core import build_pagination_input

VALID_BLOG_POST_BODY = (
    "A paragraph that opens the post with some context.\n\n"
    "## A Section Heading\n\n"
    "A paragraph that follows the first section heading."
)


def build_create_blog_post_input(
    *,
    persona_identity: UUID,
    title: str = "Why Slow Mornings Make Better Writers",
    subtitle: str | None = None,
    body: str = VALID_BLOG_POST_BODY,
    is_public: bool = False,
    published_at: datetime | None = None,
) -> CreateBlogPostInput:
    return CreateBlogPostInput(
        persona_identity=persona_identity,
        title=title,
        subtitle=subtitle,
        body=body,
        is_public=is_public,
        published_at=published_at,
    )


def build_update_blog_post_input(
    *,
    title: str = "Why Slow Mornings Make Better Writers",
    subtitle: str | None = None,
    body: str = VALID_BLOG_POST_BODY,
    is_public: bool = False,
    published_at: datetime | None = None,
) -> UpdateBlogPostInput:
    return UpdateBlogPostInput(
        title=title,
        subtitle=subtitle,
        body=body,
        is_public=is_public,
        published_at=published_at,
    )


def build_find_public_blog_post_page_input(
    *,
    page: int = 1,
    page_size: int = 20,
    search: str | None = None,
    sort_by: PublicBlogPostSortType = PublicBlogPostSortType.PUBLISHED_AT,
    sort_direction: SortDirectionType = SortDirectionType.DESC,
    persona_identity: UUID | None = None,
) -> FindPublicBlogPostPageInput:
    return FindPublicBlogPostPageInput(
        pagination_input=build_pagination_input(
            page=page, page_size=page_size, search=search, sort_direction=sort_direction
        ),
        sort_by=sort_by,
        persona_identity=persona_identity,
    )


def build_find_user_blog_post_page_input(
    *,
    page: int = 1,
    page_size: int = 20,
    search: str | None = None,
    sort_by: UserBlogPostSortType = UserBlogPostSortType.CREATED_AT,
    sort_direction: SortDirectionType = SortDirectionType.DESC,
    persona_identity: UUID | None = None,
) -> FindUserBlogPostPageInput:
    return FindUserBlogPostPageInput(
        pagination_input=build_pagination_input(
            page=page, page_size=page_size, search=search, sort_direction=sort_direction
        ),
        sort_by=sort_by,
        persona_identity=persona_identity,
    )


async def insert_blog_post_row(
    db_session: AsyncSession,
    *,
    created_by_id: int,
    content_item_id: int,
    title: str = "Why Slow Mornings Make Better Writers",
    subtitle: str | None = None,
    body: str = VALID_BLOG_POST_BODY,
    deleted_at: datetime | None = None,
    deleted_by_id: int | None = None,
) -> BlogPostOrm:
    blog_post_record = BlogPostOrm(
        content_item_id=content_item_id,
        title=title,
        subtitle=subtitle,
        body=body,
        deleted_at=deleted_at,
        created_by_id=created_by_id,
        updated_by_id=created_by_id,
        deleted_by_id=deleted_by_id,
    )
    db_session.add(blog_post_record)
    await db_session.flush()
    return blog_post_record
