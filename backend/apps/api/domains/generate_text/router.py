from uuid import UUID

from fastapi import APIRouter

from apps.api.core.dependencies import AuthUserDep
from apps.api.domains.generate_text.dependencies import (
    GenerateTextPersonaDep,
    GenerateTextServiceDep,
)
from apps.api.domains.generate_text.dtos import (
    GenerateBlogPostDto,
    GenerateTextRunResponseDto,
    ResumeGenerateTextDto,
)

generate_text_router = APIRouter(prefix="/generate-text", tags=["generate-text"])


@generate_text_router.post("/blog-post")
async def generate_blog_post(
    dto: GenerateBlogPostDto,
    find_user_persona_result: GenerateTextPersonaDep,
    auth_user: AuthUserDep,
    generate_text_service: GenerateTextServiceDep,
) -> GenerateTextRunResponseDto:
    generate_text_result = await generate_text_service.generate_text(
        dto.to_input(), find_user_persona_result, auth_user
    )
    return GenerateTextRunResponseDto.from_result(generate_text_result)


@generate_text_router.get("/runs/{run_identity}")
async def find_generate_text_run(
    run_identity: UUID, auth_user: AuthUserDep, generate_text_service: GenerateTextServiceDep
) -> GenerateTextRunResponseDto:
    find_generate_text_run_result = await generate_text_service.find_generate_text_run(
        run_identity, auth_user
    )
    return GenerateTextRunResponseDto.from_result(find_generate_text_run_result)


@generate_text_router.post("/runs/{run_identity}/resume")
async def resume_generate_text(
    run_identity: UUID,
    resume_generate_text_dto: ResumeGenerateTextDto,
    auth_user: AuthUserDep,
    generate_text_service: GenerateTextServiceDep,
) -> GenerateTextRunResponseDto:
    resume_generate_text_result = await generate_text_service.resume_generate_text(
        run_identity, resume_generate_text_dto.to_input(), auth_user
    )
    return GenerateTextRunResponseDto.from_result(resume_generate_text_result)
