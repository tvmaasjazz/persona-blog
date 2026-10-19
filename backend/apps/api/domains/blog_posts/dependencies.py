from typing import Annotated
from uuid import UUID

from fastapi import Depends, Request

from apps.api.core.dependencies import AuthUserDep, DbSessionDep
from apps.api.domains.blog_posts.dtos import (
    BlogPostDto,
    CreateBlogPostDto,
    CreateBlogPostFromGenerateTextRunDto,
)
from libs.blog_posts.services import BlogPostService, BlogPostValidationService
from libs.content_items.services import ContentItemService, ContentItemValidationService
from libs.generate_text.services import GenerateTextRunService, GenerateTextStepService
from libs.personas.services import PersonaService


def get_content_item_service(db_session: DbSessionDep) -> ContentItemService:
    return ContentItemService(db_session=db_session)


ContentItemServiceDep = Annotated[ContentItemService, Depends(get_content_item_service)]


def get_content_item_validation_service(
    db_session: DbSessionDep,
) -> ContentItemValidationService:
    return ContentItemValidationService(db_session=db_session)


ContentItemValidationServiceDep = Annotated[
    ContentItemValidationService, Depends(get_content_item_validation_service)
]


def get_persona_service(db_session: DbSessionDep) -> PersonaService:
    return PersonaService(db_session=db_session)


PersonaServiceDep = Annotated[PersonaService, Depends(get_persona_service)]


def get_generate_text_run_service(request: Request) -> GenerateTextRunService:
    """Builds the generate text run service on the app's session factory, not a request session."""
    db_session_factory = request.app.state.db_session_factory
    return GenerateTextRunService(db_session_factory=db_session_factory)


GenerateTextRunServiceDep = Annotated[
    GenerateTextRunService, Depends(get_generate_text_run_service)
]


def get_generate_text_step_service(request: Request) -> GenerateTextStepService:
    """Builds the generate text step service on the app's session factory, not a request session."""
    db_session_factory = request.app.state.db_session_factory
    return GenerateTextStepService(db_session_factory=db_session_factory)


GenerateTextStepServiceDep = Annotated[
    GenerateTextStepService, Depends(get_generate_text_step_service)
]


def get_blog_post_service(
    db_session: DbSessionDep,
    content_item_service: ContentItemServiceDep,
    persona_service: PersonaServiceDep,
    generate_text_run_service: GenerateTextRunServiceDep,
    generate_text_step_service: GenerateTextStepServiceDep,
) -> BlogPostService:
    return BlogPostService(
        db_session=db_session,
        content_item_service=content_item_service,
        persona_service=persona_service,
        generate_text_run_service=generate_text_run_service,
        generate_text_step_service=generate_text_step_service,
    )


BlogPostServiceDep = Annotated[BlogPostService, Depends(get_blog_post_service)]


def get_blog_post_validation_service(
    db_session: DbSessionDep,
    content_item_validation_service: ContentItemValidationServiceDep,
) -> BlogPostValidationService:
    return BlogPostValidationService(
        db_session=db_session,
        content_item_validation_service=content_item_validation_service,
    )


BlogPostValidationServiceDep = Annotated[
    BlogPostValidationService, Depends(get_blog_post_validation_service)
]


async def validate_new_blog_post_visibility(
    dto: CreateBlogPostDto,
    auth_user: AuthUserDep,
    content_item_validation_service: ContentItemValidationServiceDep,
) -> None:
    """Rejects a new public blog post whose persona is private."""
    await content_item_validation_service.validate_persona_allows_public(
        dto.persona_identity, dto.is_public, auth_user
    )


async def validate_updated_blog_post_visibility(
    blog_post_identity: UUID,
    dto: BlogPostDto,
    auth_user: AuthUserDep,
    blog_post_validation_service: BlogPostValidationServiceDep,
) -> None:
    """Rejects making a blog post public when its persona is private."""
    await blog_post_validation_service.validate_blog_post_visibility(
        blog_post_identity, dto.is_public, auth_user
    )


async def validate_new_blog_post_from_run_availability(
    dto: CreateBlogPostFromGenerateTextRunDto,
    auth_user: AuthUserDep,
    content_item_validation_service: ContentItemValidationServiceDep,
) -> None:
    """Rejects a run that isn't found, isn't completed, or was already saved as a blog post."""
    await content_item_validation_service.validate_generate_text_run_available(
        dto.generate_text_run_identity, auth_user
    )


async def validate_new_blog_post_from_run_visibility(
    dto: CreateBlogPostFromGenerateTextRunDto,
    auth_user: AuthUserDep,
    content_item_validation_service: ContentItemValidationServiceDep,
) -> None:
    """Rejects a public blog post from a run whose persona is private."""
    await content_item_validation_service.validate_generate_text_run_allows_public(
        dto.generate_text_run_identity, dto.is_public, auth_user
    )
