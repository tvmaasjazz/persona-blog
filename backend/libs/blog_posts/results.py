from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class CreateBlogPostResult(BaseModel):
    identity: UUID


class BlogPostDetailResult(BaseModel):
    identity: UUID
    persona_identity: UUID
    title: str
    subtitle: str | None
    body: str
    is_public: bool
    published_at: datetime | None
    created_at: datetime
    updated_at: datetime


class FindUserBlogPostListResult(BaseModel):
    blog_posts: list[BlogPostDetailResult]
