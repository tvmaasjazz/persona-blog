from datetime import UTC, datetime
from uuid import UUID

from pydantic import BaseModel, field_validator

from libs.blog_posts.inputs import (
    CreateBlogPostFromGenerateTextRunInput,
    CreateBlogPostInput,
    UpdateBlogPostInput,
)
from libs.blog_posts.results import BlogPostDetailResult, FindUserBlogPostListResult
from libs.blog_posts.utils import BlogPostValidationUtils


def _validate_body(body: str) -> str:
    body_problems = BlogPostValidationUtils.find_body_problems(body)
    if body_problems:
        raise ValueError("; ".join(body_problems))
    return body


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

    @field_validator("body")
    @classmethod
    def _validate_body(cls, body: str) -> str:
        return _validate_body(body)

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
        )


class CreateBlogPostFromGenerateTextRunDto(BaseModel):
    generate_text_run_identity: UUID
    is_public: bool = False
    published_at: datetime | None = None

    @field_validator("published_at")
    @classmethod
    def _validate_published_at(cls, published_at: datetime | None) -> datetime | None:
        return _validate_timezone_aware(published_at)

    def to_input(self) -> CreateBlogPostFromGenerateTextRunInput:
        return CreateBlogPostFromGenerateTextRunInput(
            generate_text_run_identity=self.generate_text_run_identity,
            is_public=self.is_public,
            published_at=self.published_at.astimezone(UTC) if self.published_at else None,
        )


class BlogPostDto(BaseModel):
    title: str
    subtitle: str | None = None
    body: str
    is_public: bool = False
    published_at: datetime | None = None

    @field_validator("body")
    @classmethod
    def _validate_body(cls, body: str) -> str:
        return _validate_body(body)

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
        content_item_result = blog_post_detail_result.content_item
        return cls(
            identity=blog_post_detail_result.identity,
            persona_identity=content_item_result.persona.identity,
            title=blog_post_detail_result.title,
            subtitle=blog_post_detail_result.subtitle,
            body=blog_post_detail_result.body,
            is_public=content_item_result.is_public,
            published_at=content_item_result.published_at,
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
