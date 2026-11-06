from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query

from apps.api.core.dependencies import (
    AuthUserDep,
    OptionalAuthUserDep,
    get_optional_auth_user,
    require_permissions,
)
from apps.api.core.dtos import EmptyResponseDto, IdentityResponseDto
from apps.api.domains.blog_posts.dependencies import (
    BlogPostServiceDep,
    validate_new_blog_post_from_run_availability,
    validate_new_blog_post_from_run_visibility,
    validate_new_blog_post_visibility,
    validate_updated_blog_post_visibility,
)
from apps.api.domains.blog_posts.dtos import (
    BlogPostDto,
    BlogPostFetchAllQueryDto,
    BlogPostListResponseDto,
    BlogPostResponseDto,
    CreateBlogPostDto,
    CreateBlogPostFromGenerateTextRunDto,
    PublicBlogPostPageQueryDto,
    PublicBlogPostPageResponseDto,
    PublicBlogPostResponseDto,
)
from libs.permissions.types import PermissionType

blog_post_router = APIRouter(prefix="/blog-posts", tags=["blog-posts"])


@blog_post_router.get(
    "",
    dependencies=[
        Depends(require_permissions(PermissionType.BLOG_POST_READ)),
    ],
)
async def find_user_blog_post_list(
    query_dto: Annotated[BlogPostFetchAllQueryDto, Query()],
    auth_user: AuthUserDep,
    blog_post_service: BlogPostServiceDep,
) -> BlogPostListResponseDto:
    """Lists the signed-in user's blog posts, optionally only those of one persona."""
    find_user_blog_post_list_result = await blog_post_service.find_user_blog_post_list(
        auth_user, query_dto.persona_identity
    )
    return BlogPostListResponseDto.from_result(find_user_blog_post_list_result)


# The page is the same for every caller, so the user isn't passed on, but an expired
# session is still a 401 as on every open route
@blog_post_router.get("/public", dependencies=[Depends(get_optional_auth_user)])
async def find_public_blog_post_page(
    query_dto: Annotated[PublicBlogPostPageQueryDto, Query()],
    blog_post_service: BlogPostServiceDep,
) -> PublicBlogPostPageResponseDto:
    """Returns a page of published public blog posts, the same to anyone, signed in or not:
    the homepage feed sorted by FEED_SCORE, or a persona's page filtered by persona;
    searchable by title, subtitle and persona name."""
    find_public_blog_post_page_result = await blog_post_service.find_public_blog_post_page(
        query_dto.to_input()
    )
    return PublicBlogPostPageResponseDto.from_result(find_public_blog_post_page_result)


@blog_post_router.get(
    "/{blog_post_identity}",
    dependencies=[
        Depends(require_permissions(PermissionType.BLOG_POST_READ)),
    ],
)
async def find_blog_post(
    blog_post_identity: UUID, auth_user: AuthUserDep, blog_post_service: BlogPostServiceDep
) -> BlogPostResponseDto:
    """Returns one of the signed-in user's own blog posts, or 404 for anyone else's."""
    find_blog_post_result = await blog_post_service.find_blog_post(blog_post_identity, auth_user)
    return BlogPostResponseDto.from_result(find_blog_post_result)


@blog_post_router.get("/{blog_post_identity}/public")
async def find_public_blog_post(
    blog_post_identity: UUID,
    auth_user: OptionalAuthUserDep,
    blog_post_service: BlogPostServiceDep,
) -> PublicBlogPostResponseDto:
    """Returns a blog post's public view to anyone, signed in or not; 404 unless it is
    published and public or the signed-in user's own."""
    find_public_blog_post_result = await blog_post_service.find_public_blog_post(
        blog_post_identity, auth_user
    )
    return PublicBlogPostResponseDto.from_result(find_public_blog_post_result)


@blog_post_router.post(
    "",
    status_code=201,
    dependencies=[
        Depends(require_permissions(PermissionType.BLOG_POST_WRITE)),
        Depends(validate_new_blog_post_visibility),
    ],
)
async def create_blog_post(
    dto: CreateBlogPostDto, auth_user: AuthUserDep, blog_post_service: BlogPostServiceDep
) -> IdentityResponseDto:
    """Creates a blog post, or 422 when it is public but its persona is private."""
    create_blog_post_result = await blog_post_service.create_blog_post(dto.to_input(), auth_user)
    return IdentityResponseDto(identity=create_blog_post_result.identity)


@blog_post_router.post(
    "/from-generate-text-run",
    status_code=201,
    dependencies=[
        Depends(require_permissions(PermissionType.BLOG_POST_WRITE)),
        Depends(validate_new_blog_post_from_run_availability),
        Depends(validate_new_blog_post_from_run_visibility),
    ],
)
async def create_blog_post_from_generate_text_run(
    dto: CreateBlogPostFromGenerateTextRunDto,
    auth_user: AuthUserDep,
    blog_post_service: BlogPostServiceDep,
) -> IdentityResponseDto:
    """Saves a completed generate text run's output as a blog post, or 404 when no such run."""
    create_blog_post_result = await blog_post_service.create_blog_post_from_generate_text_run(
        dto.to_input(), auth_user
    )
    return IdentityResponseDto(identity=create_blog_post_result.identity)


@blog_post_router.put(
    "/{blog_post_identity}",
    dependencies=[
        Depends(require_permissions(PermissionType.BLOG_POST_WRITE)),
        Depends(validate_updated_blog_post_visibility),
    ],
)
async def update_blog_post(
    blog_post_identity: UUID,
    dto: BlogPostDto,
    auth_user: AuthUserDep,
    blog_post_service: BlogPostServiceDep,
) -> EmptyResponseDto:
    """Updates a blog post, or 404 when it is missing and 403 when the user isn't its creator."""
    await blog_post_service.update_blog_post(blog_post_identity, dto.to_input(), auth_user)
    return EmptyResponseDto()


@blog_post_router.delete(
    "/{blog_post_identity}",
    dependencies=[
        Depends(require_permissions(PermissionType.BLOG_POST_WRITE)),
    ],
)
async def delete_blog_post(
    blog_post_identity: UUID, auth_user: AuthUserDep, blog_post_service: BlogPostServiceDep
) -> EmptyResponseDto:
    """Soft-deletes a blog post, or 404 when it is missing and 403 when not its creator."""
    await blog_post_service.delete_blog_post(blog_post_identity, auth_user)
    return EmptyResponseDto()
