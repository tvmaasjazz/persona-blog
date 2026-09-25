from fastapi import APIRouter

from apps.api.core.dependencies import AuthUserDep, GenerateTextServiceDep
from apps.api.domains.generate_text.dtos import GenerateBlogPostDto, GeneratedTextResponseDto

generate_text_router = APIRouter(prefix="/generate-text", tags=["generate-text"])


@generate_text_router.post("/blog-post")
async def generate_blog_post(
    dto: GenerateBlogPostDto,
    auth_user: AuthUserDep,
    generate_text_service: GenerateTextServiceDep,
) -> GeneratedTextResponseDto:
    generate_text_result = await generate_text_service.generate_text(dto.to_input(), auth_user)
    return GeneratedTextResponseDto.from_result(generate_text_result)
