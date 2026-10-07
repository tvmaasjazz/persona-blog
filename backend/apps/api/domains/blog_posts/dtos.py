from datetime import UTC, datetime
from uuid import UUID

from pydantic import BaseModel, field_validator

from libs.blog_posts.inputs import CreateBlogPostInput, UpdateBlogPostInput
from libs.blog_posts.results import BlogPostDetailResult, FindUserBlogPostListResult


def _validate_timezone_aware(published_at: datetime | None) -> datetime | None:
    if published_at is not None and published_at.tzinfo is None:
        raise ValueError("published_at must be timezone-aware")
    return published_at


class CreateBlogPostDto(BaseModel):
    persona_identity: UUID
    title: str
    subtitle: str | None = None
    body: str
    is_public: bool = False
    published_at: datetime | None = None
    generate_text_run_identity: UUID | None = None

    @field_validator("published_at")
    @classmethod
    def _validate_published_at(cls, published_at: datetime | None) -> datetime | None:
        return _validate_timezone_aware(published_at)

    def to_input(self) -> CreateBlogPostInput:
        return CreateBlogPostInput(
            persona_identity=self.persona_identity,
            title=self.title,
            subtitle=self.subtitle,
            body=self.body,
            is_public=self.is_public,
            published_at=self.published_at.astimezone(UTC) if self.published_at else None,
            generate_text_run_identity=self.generate_text_run_identity,
        )


class BlogPostDto(BaseModel):
    title: str
    subtitle: str | None = None
    body: str
    is_public: bool = False
    published_at: datetime | None = None

    @field_validator("published_at")
    @classmethod
    def _validate_published_at(cls, published_at: datetime | None) -> datetime | None:
        return _validate_timezone_aware(published_at)

    def to_input(self) -> UpdateBlogPostInput:
        return UpdateBlogPostInput(
            title=self.title,
            subtitle=self.subtitle,
            body=self.body,
            is_public=self.is_public,
            published_at=self.published_at.astimezone(UTC) if self.published_at else None,
        )


class BlogPostResponseDto(BaseModel):
    identity: UUID
    persona_identity: UUID
    title: str
    subtitle: str | None
    body: str
    is_public: bool
    published_at: datetime | None
    created_at: datetime
    updated_at: datetime

    @classmethod
    def from_result(cls, blog_post_detail_result: BlogPostDetailResult) -> BlogPostResponseDto:
        return cls(
            identity=blog_post_detail_result.identity,
            persona_identity=blog_post_detail_result.persona_identity,
            title=blog_post_detail_result.title,
            subtitle=blog_post_detail_result.subtitle,
            body=blog_post_detail_result.body,
            is_public=blog_post_detail_result.is_public,
            published_at=blog_post_detail_result.published_at,
            created_at=blog_post_detail_result.created_at,
            updated_at=blog_post_detail_result.updated_at,
        )


class BlogPostListResponseDto(BaseModel):
    blog_posts: list[BlogPostResponseDto]

    @classmethod
    def from_result(
        cls, find_user_blog_post_list_result: FindUserBlogPostListResult
    ) -> BlogPostListResponseDto:
        return cls(
            blog_posts=[
                BlogPostResponseDto.from_result(blog_post_detail_result)
                for blog_post_detail_result in find_user_blog_post_list_result.blog_posts
            ]
        )


class BlogPostFetchAllQueryDto(BaseModel):
    persona_identity: UUID | None = None
