from datetime import datetime
from uuid import UUID

from pydantic import BaseModel

from libs.core.results import PaginationResult


class CreateBlogPostResult(BaseModel):
    identity: UUID


class BlogPostPersonaResult(BaseModel):
    identity: UUID


class BlogPostContentItemResult(BaseModel):
    is_public: bool
    published_at: datetime | None
    persona: BlogPostPersonaResult


class BlogPostDetailResult(BaseModel):
    identity: UUID
    title: str
    subtitle: str | None
    body: str
    created_at: datetime
    updated_at: datetime
    content_item: BlogPostContentItemResult


class BlogPostSummaryResult(BaseModel):
    identity: UUID
    title: str
    subtitle: str | None
    created_at: datetime
    updated_at: datetime
    content_item: BlogPostContentItemResult


class FindPublicBlogPostPageResult(BaseModel):
    blog_posts: list[BlogPostSummaryResult]
    pagination: PaginationResult


class PublicBlogPostResult(BaseModel):
    blog_post: BlogPostDetailResult
    is_owner: bool


class FindUserBlogPostListResult(BaseModel):
    blog_posts: list[BlogPostDetailResult]
