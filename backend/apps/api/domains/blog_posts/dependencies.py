from typing import Annotated
from uuid import UUID

from fastapi import Depends

from apps.api.core.dependencies import AuthUserDep, DbTransactionDep
from apps.api.domains.blog_posts.dtos import BlogPostDto, CreateBlogPostDto
from libs.blog_posts.services import BlogPostService, BlogPostValidationService
from libs.content_items.services import ContentItemService, ContentItemValidationService
from libs.personas.services import PersonaService


def get_content_item_service(db_session: DbTransactionDep) -> ContentItemService:
    return ContentItemService(db_session=db_session)


ContentItemServiceDep = Annotated[ContentItemService, Depends(get_content_item_service)]


def get_content_item_validation_service(
    db_session: DbTransactionDep,
) -> ContentItemValidationService:
    return ContentItemValidationService(db_session=db_session)


ContentItemValidationServiceDep = Annotated[
    ContentItemValidationService, Depends(get_content_item_validation_service)
]


def get_persona_service(db_session: DbTransactionDep) -> PersonaService:
    return PersonaService(db_session=db_session)


PersonaServiceDep = Annotated[PersonaService, Depends(get_persona_service)]


def get_blog_post_service(
    db_session: DbTransactionDep,
    content_item_service: ContentItemServiceDep,
    persona_service: PersonaServiceDep,
) -> BlogPostService:
    return BlogPostService(
        db_session=db_session,
        content_item_service=content_item_service,
        persona_service=persona_service,
    )


BlogPostServiceDep = Annotated[BlogPostService, Depends(get_blog_post_service)]


def get_blog_post_validation_service(
    db_session: DbTransactionDep,
    content_item_validation_service: ContentItemValidationServiceDep,
) -> BlogPostValidationService:
    return BlogPostValidationService(
        db_session=db_session,
        content_item_validation_service=content_item_validation_service,
    )


BlogPostValidationServiceDep = Annotated[
    BlogPostValidationService, Depends(get_blog_post_validation_service)
]


async def validate_new_blog_post_body(
    dto: CreateBlogPostDto,
    blog_post_validation_service: BlogPostValidationServiceDep,
) -> None:
    blog_post_validation_service.validate_blog_post_body(dto.body)


async def validate_updated_blog_post_body(
    dto: BlogPostDto,
    blog_post_validation_service: BlogPostValidationServiceDep,
) -> None:
    blog_post_validation_service.validate_blog_post_body(dto.body)


async def validate_new_blog_post_visibility(
    dto: CreateBlogPostDto,
    auth_user: AuthUserDep,
    content_item_validation_service: ContentItemValidationServiceDep,
) -> None:
    await content_item_validation_service.validate_persona_allows_public(
        dto.persona_identity, dto.is_public, auth_user
    )


async def validate_updated_blog_post_visibility(
    blog_post_identity: UUID,
    dto: BlogPostDto,
    auth_user: AuthUserDep,
    blog_post_validation_service: BlogPostValidationServiceDep,
) -> None:
    await blog_post_validation_service.validate_blog_post_visibility(
        blog_post_identity, dto.is_public, auth_user
    )


async def validate_new_blog_post_generate_text_run(
    dto: CreateBlogPostDto,
    auth_user: AuthUserDep,
    content_item_validation_service: ContentItemValidationServiceDep,
) -> None:
    if dto.generate_text_run_identity is None:
        return
    await content_item_validation_service.validate_generate_text_run_available(
        dto.generate_text_run_identity, dto.persona_identity, auth_user
    )
