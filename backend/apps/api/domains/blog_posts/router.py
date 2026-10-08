from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query

from apps.api.core.dependencies import AuthUserDep
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
)

blog_post_router = APIRouter(prefix="/blog-posts", tags=["blog-posts"])


@blog_post_router.get("")
async def find_user_blog_post_list(
    query_dto: Annotated[BlogPostFetchAllQueryDto, Query()],
    auth_user: AuthUserDep,
    blog_post_service: BlogPostServiceDep,
) -> BlogPostListResponseDto:
    find_user_blog_post_list_result = await blog_post_service.find_user_blog_post_list(
        auth_user, query_dto.persona_identity
    )
    return BlogPostListResponseDto.from_result(find_user_blog_post_list_result)


@blog_post_router.get("/{blog_post_identity}")
async def find_blog_post(
    blog_post_identity: UUID, auth_user: AuthUserDep, blog_post_service: BlogPostServiceDep
) -> BlogPostResponseDto:
    find_blog_post_result = await blog_post_service.find_blog_post(blog_post_identity, auth_user)
    return BlogPostResponseDto.from_result(find_blog_post_result)


@blog_post_router.post(
    "",
    status_code=201,
    dependencies=[
        Depends(validate_new_blog_post_visibility),
    ],
)
async def create_blog_post(
    dto: CreateBlogPostDto, auth_user: AuthUserDep, blog_post_service: BlogPostServiceDep
) -> IdentityResponseDto:
    create_blog_post_result = await blog_post_service.create_blog_post(dto.to_input(), auth_user)
    return IdentityResponseDto(identity=create_blog_post_result.identity)


@blog_post_router.post(
    "/from-generate-text-run",
    status_code=201,
    dependencies=[
        Depends(validate_new_blog_post_from_run_availability),
        Depends(validate_new_blog_post_from_run_visibility),
    ],
)
async def create_blog_post_from_generate_text_run(
    dto: CreateBlogPostFromGenerateTextRunDto,
    auth_user: AuthUserDep,
    blog_post_service: BlogPostServiceDep,
) -> IdentityResponseDto:
    create_blog_post_result = await blog_post_service.create_blog_post_from_generate_text_run(
        dto.to_input(), auth_user
    )
    return IdentityResponseDto(identity=create_blog_post_result.identity)


@blog_post_router.put(
    "/{blog_post_identity}",
    dependencies=[
        Depends(validate_updated_blog_post_visibility),
    ],
)
async def update_blog_post(
    blog_post_identity: UUID,
    dto: BlogPostDto,
    auth_user: AuthUserDep,
    blog_post_service: BlogPostServiceDep,
) -> EmptyResponseDto:
    await blog_post_service.update_blog_post(blog_post_identity, dto.to_input(), auth_user)
    return EmptyResponseDto()


@blog_post_router.delete("/{blog_post_identity}")
async def delete_blog_post(
    blog_post_identity: UUID, auth_user: AuthUserDep, blog_post_service: BlogPostServiceDep
) -> EmptyResponseDto:
    await blog_post_service.delete_blog_post(blog_post_identity, auth_user)
    return EmptyResponseDto()
