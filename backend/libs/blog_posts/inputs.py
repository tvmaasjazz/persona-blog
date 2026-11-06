from datetime import datetime
from uuid import UUID

from pydantic import BaseModel

from libs.blog_posts.types import PublicBlogPostSortType
from libs.core.inputs import ListInput


class FindPublicBlogPostListInput(ListInput):
    sort_by: PublicBlogPostSortType
    persona_identity: UUID | None


class CreateBlogPostInput(BaseModel):
    persona_identity: UUID
    title: str
    subtitle: str | None
    body: str
    is_public: bool
    published_at: datetime | None


class CreateBlogPostFromGenerateTextRunInput(BaseModel):
    generate_text_run_identity: UUID
    is_public: bool
    published_at: datetime | None


class UpdateBlogPostInput(BaseModel):
    title: str
    subtitle: str | None
    body: str
    is_public: bool
    published_at: datetime | None
